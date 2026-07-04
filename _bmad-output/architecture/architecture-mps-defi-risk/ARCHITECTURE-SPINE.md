---
name: 'QuantumRadar'
type: architecture-spine
purpose: build-substrate
altitude: feature
paradigm: 'Pipes and Filters (Data Ingestion -> MPS Engine -> Webhook Emitter)'
scope: 'QuantumRadar API Backend'
status: final
created: '2026-07-03'
updated: '2026-07-03'
binds: ['CAP-1', 'CAP-2', 'CAP-3']
sources: ['SPEC-mps-defi-risk']
companions: ['PRESENTATION.md']
---

# Architecture Spine — QuantumRadar

## Design Paradigm

**Pipes and Filters (Streaming Architecture)**
Dữ liệu liên tục chảy từ các nguồn on-chain vào một bộ đệm vòng (Ring Buffer). Lõi Tensor Network (MPS Engine) liên tục tiêu thụ dữ liệu từ bộ đệm này để cập nhật trạng thái đồ thị. Bất kỳ khi nào Chỉ số Fragility vượt ngưỡng, tín hiệu sẽ được đẩy qua bộ lọc cuối cùng là Webhook Emitter để gửi ra ngoài.

## Invariants & Rules

### AD-1 — Tách biệt luồng I/O và lõi Toán học (CPU-Bound vs I/O-Bound)

- **Binds:** `CAP-1`, `CAP-2`, `CAP-3`
- **Prevents:** Trạng thái hệ thống bị nghẽn (latency spike) khi mạng lưới RPC bị lag hoặc Webhook khách hàng bị timeout.
- **Rule:** Lõi toán học (PyTorch) PHẢI chạy trên một Process/Thread riêng biệt. Việc đọc RPC và bắn Webhook PHẢI chạy hoàn toàn bất đồng bộ (asyncio).

### AD-2 — Cấu trúc dữ liệu Ring Buffer in-memory

- **Binds:** `CAP-1`, `CAP-2`
- **Prevents:** Chi phí OpEx tăng cao do phụ thuộc vào Database (PostgreSQL/Redis) hoặc Disk I/O làm chậm hệ thống.
- **Rule:** Trạng thái tick-data 10 block gần nhất PHẢI được lưu trữ trên bộ nhớ RAM dưới dạng `collections.deque` hoặc mảng Numpy tĩnh. Không ghi xuống đĩa khi đang chạy realtime.

### AD-3 — Hợp đồng Dữ liệu Webhook (JSON Schema)

- **Binds:** `CAP-3`
- **Prevents:** Khách hàng không thể parse được tín hiệu, dẫn đến bot giao dịch sụp đổ.
- **Rule:** Payload Webhook PHẢI tuân thủ một JSON schema cố định gồm: `timestamp`, `fragility_score`, `alert_level` (YELLOW/RED), và `trigger_protocols`.

### AD-4 — Giao thức Mạng (Data Ingestion Protocol)

- **Binds:** `CAP-1`
- **Prevents:** Độ trễ indexing quá lớn từ The Graph hay REST API khiến hệ thống báo động chậm hơn diễn biến thị trường.
- **Rule:** Lấy dữ liệu Real-time PHẢI dùng WebSocket (`eth_subscribe` / WSS) kết nối thẳng vào Alchemy/Infura node. Dữ liệu lịch sử (backtest) dùng CSV/BigQuery.

### AD-5 — Bộ lọc Sự kiện (Event Targeting)

- **Binds:** `CAP-1`, `CAP-2`
- **Prevents:** Phình to bộ nhớ (Memory bloat) do lưu trữ toàn bộ lịch sử giao dịch không liên quan của mạng lưới.
- **Rule:** Chỉ lắng nghe và parse các Smart Contract Events sinh ra rủi ro lây lan: `Swap`, `Mint`, `Burn` (DEX - Uniswap V3) và `Borrow`, `Supply`, `Withdraw`, `LiquidationCall` (Lending - Aave V3).

## Consistency Conventions

| Concern | Convention |
| --- | --- |
| Naming (entities, files, interfaces, events) | Rắn cắn (snake_case) cho Python. PascalCase cho Class. |
| Data & formats (ids, dates, error shapes, envelopes) | Timestamps chuẩn ISO 8601 (UTC). |
| State & cross-cutting (mutation, errors, logging, config, auth) | Log JSON qua stdout để dễ dàng ingest vào Datadog/ELK sau này. |

## Stack

| Name | Version |
| --- | --- |
| Python | 3.11+ |
| PyTorch | 2.1+ |
| Web3.py | 6.11+ |
| FastAPI | 0.104+ |
| Uvicorn | 0.23+ |

## Structural Seed

```text
quantum_radar/
  ingestion/       # Kết nối RPC WebSocket, bộ lọc Event (Uniswap/Aave), CSV Loader
  engine/          # Lõi PyTorch Tensor Network (MPS)
  emitter/         # Quản lý Webhook & FastAPI endpoints
  core/            # Config, Logging, Shared Data Structures (Ring Buffer)
```

## Capability → Architecture Map

| Capability / Area | Lives in | Governed by |
| --- | --- | --- |
| CAP-1 (Dữ liệu) | `ingestion/` | AD-1, AD-2, AD-4, AD-5 |
| CAP-2 (Lõi Toán) | `engine/` | AD-1, AD-2, AD-5 |
| CAP-3 (Đầu ra) | `emitter/` | AD-1, AD-3 |

## Deferred

- Cơ sở dữ liệu lưu trữ lịch sử dài hạn (Sẽ xử lý ở v2 khi cần backtest quy mô lớn).
- Cụm GPU phân tán (Chỉ chạy CPU local cho PoC để tối ưu chi phí).
