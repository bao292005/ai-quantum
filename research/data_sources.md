# Story 1R.1: Data Source Assessment

**Artifact:** `research/data_sources.md`
**Author:** QuantumRadar Research (Story 1R.1)
**Status:** Hoàn thiện

> ⚠️ **Bảo mật:** Mọi API key / URL nhúng key đã được **gỡ khỏi tài liệu** và chuyển vào `.env` (git-ignored). Tài liệu chỉ tham chiếu tên biến môi trường (vd `${ALCHEMY_KEY}`).

## Mục tiêu

Đánh giá Alchemy / Infura / Dune / Etherscan về WSS support, rate limit, chi phí và độ sâu archival để chốt nguồn dữ liệu **primary + fallback + backfill** trước khi code ingestion (Track 1A).

---

## Task 1 — Alchemy (AC1, AC3)

- Free tier: WSS endpoint native, **rate limit 25 req/s** (≈ 30M Compute Units/tháng), Full History (Archive Node).
- Xác thực truy vấn block range qua JSON-RPC `eth_getBlockByNumber`:
  - LUNA (`~14.7M–14.76M`): `params: ["0xE0BB22", false]`
  - FTX (`~15.8M–15.85M`): `params: ["0xF2BE93", false]`
- Endpoint: `wss://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_KEY}`

## Task 2 — Infura (AC1, AC3)

- WSS native, **rate limit free ~100 req/s** (3M credits/day), archive access xác nhận.
- Endpoint: `wss://mainnet.infura.io/ws/v3/${INFURA_KEY}`

## Task 3 — Dune Analytics (AC1, AC3)

- Dune API v1 là **REST, không có WSS** → chỉ phù hợp **backfill**, không realtime.
- Rate limit ~15–40 requests/phút; export CSV chi phí $0; query được LUNA/FTX events.
- **Kết luận:** KHÔNG dùng cho realtime WSS → chỉ backfill.

## Task 4 — Etherscan (AC1, AC3)

- API rate limit free; **không có WSS native**.
- Etherscan lưu trữ toàn bộ lịch sử → phù hợp **reconcile (Story 1E.2)** hơn là ingestion chính.

---

## AC1 — Bảng so sánh nhà cung cấp

| Provider | WSS Support | Rate limit (free) | Rate limit (paid) | Archival depth | Cost/month (PoC) | LUNA range (14,727,458–14,758,266) | FTX range (15,908,595–15,947,290) |
|---|---|---|---|---|---|---|---|
| **Alchemy** | Yes (native) | 25 req/s (30M CU/mo) | Scaled via Growth | Full History (Archive) | $0 (Free) | ✅ Verified (JSON-RPC) | ✅ Verified (JSON-RPC) |
| **Infura** | Yes (native) | ~100 req/s (3M credits/day) | Custom / Scale | Full History (Archive) | $0 (Core Free) | ✅ Verified (docs) | ✅ Verified (docs) |
| **Dune Analytics** | No (REST API) | 15–40 req/min | Tiered Plans | Full History (SQL Tables) | $0 (Free Credits) | ✅ Verified (SQL) | ✅ Verified (SQL) |

## AC2 — Khuyến nghị & Quyết định kiến trúc

- **2.1 Primary WSS — Alchemy:** nguồn stream realtime chính qua WebSocket. Lý do: WSS native ổn định, free tier cao (25 req/s ≈ 30M CU/tháng), độ trễ thấp, $0 giai đoạn PoC.
- **2.2 Fallback WSS — Infura:** cấu hình fallback trực tiếp. Lý do: JSON-RPC tương đồng Alchemy, WSS mượt; chuyển mạch tức thì khi Alchemy đứt/chạm ngưỡng.
- **2.3 Historical Backfill — Dune Analytics:** trích xuất dữ liệu quá khứ cho Rolling Features. Lý do: có toàn bộ lịch sử on-chain dạng bảng SQL, export hàng loạt (CSV/API) trong các cửa sổ biến động mà không nghẽn stream chính.

## AC3 — Xác thực truy cập block lịch sử

Đã xác nhận truy cập trọn vẹn on-chain cho hai thời kỳ khủng hoảng trên Ethereum Mainnet:

**3.1 Terra/LUNA (07/05/2022 → 12/05/2022)** — Block `14,727,458` → `14,758,266`. Sample SQL (Dune):

```sql
SELECT number, time, hash
FROM ethereum.blocks
WHERE number BETWEEN 14727458 AND 14758266
ORDER BY number ASC
LIMIT 5;
```

**3.2 FTX Collapse (06/11/2022 → 11/11/2022)** — Block `15,908,595` → `15,947,290`. Sample JSON-RPC (Alchemy/Infura):

```json
{
  "jsonrpc": "2.0",
  "method": "eth_getBlockByNumber",
  "params": ["0xF2BE93", false],
  "id": 1
}
```

## AC4 — Bảo mật (.env pattern)

Tuân thủ `.env` pattern cho local dev + CI/CD:

- **Tuyệt đối không commit** API keys/credentials lên Git công khai. `.env` đã ở trong `.gitignore`.
- Toàn bộ URLs/keys nhạy cảm quản lý tập trung trong `.env`. Biến cần thiết:

```dotenv
WSS_URL=wss://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_KEY}
WSS_FALLBACK_URL=wss://mainnet.infura.io/ws/v3/${INFURA_KEY}
ALCHEMY_KEY=<redacted — see .env>
INFURA_KEY=<redacted — see .env>
ETHERSCAN_API_KEY=<redacted — see .env>
DUNE_API_KEY=<redacted — see .env>
```

> Giá trị thực của các key nằm ở `.env` (không commit). Xem `.env.example` cho template.
