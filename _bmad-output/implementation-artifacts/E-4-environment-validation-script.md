---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: build
---

# Story E.4: Environment Validation Script

Status: ready-for-dev

## Story

As a **Kỹ sư Dữ liệu**,
I want **1 lệnh `python -m tools.check_env` kiểm tra đủ biến môi trường + ping mọi dịch vụ ngoài và in PASS/FAIL**,
so that **thành viên mới biết ngay môi trường đã sẵn sàng hay còn thiếu gì, không phải dò tay từng bước**.

## Acceptance Criteria

1. **AC1 — Module tồn tại:** `tools/check_env.py` chạy được qua `python -m tools.check_env`.

2. **AC2 — Kiểm 5 mục, in ✅/❌ mỗi dòng:**
   1. Biến bắt buộc có mặt (`WSS_URL`, `ETHERSCAN_API_KEY`, `WEBHOOK_TEST_URL`)
   2. WSS kết nối + nhận 1 block (`eth_subscribe`/`eth_blockNumber`)
   3. Etherscan trả HTTP 200
   4. `ingestion/whitelist.yaml` load được + `len >= 3`
   5. Webhook test URL nhận payload mẫu (nếu cấu hình)

3. **AC3 — Exit code:** `0` nếu tất cả PASS, `1` nếu có ≥1 FAIL.

4. **AC4 — Mỗi FAIL kèm gợi ý:** Dòng ❌ ghi rõ lý do + hành động khắc phục (VD "thiếu WSS_URL → xem docs/environment_setup.md E.1").

5. **AC5 — Chạy sạch sau clone:** Ngay sau `cp .env.example .env` (chưa điền key), chạy được và báo FAIL rõ ràng — KHÔNG traceback/crash.

6. **AC6 — Unit test:** `tests/unit/test_check_env.py` cover: (a) thiếu biến → FAIL + exit 1, (b) đủ biến (mock services) → PASS + exit 0.

## Tasks / Subtasks

- [ ] **Task 1 — Implement check_env** (AC1–AC5)
  - [ ] `tools/check_env.py`: mỗi check là 1 hàm trả `(ok: bool, msg: str)`
  - [ ] Reuse loader `ingestion/config.py` (1A.1) để đọc env; `ContractWhitelist` (1B.3) cho check whitelist
  - [ ] Bọc mỗi check trong try/except → lỗi thành FAIL có message, không raise ra ngoài (AC5)
  - [ ] Tổng hợp: in bảng ✅/❌, `sys.exit(0 if all else 1)`
- [ ] **Task 2 — Unit tests** (AC6)
  - [ ] `tests/unit/test_check_env.py`: monkeypatch env + mock network calls
  - [ ] Test thiếu biến → exit 1; đủ biến (mock) → exit 0

## Dev Notes

**Loại story:** `[BUILD]`. **BlockedBy:** 1A.1 (config loader), 1B.3 (whitelist loader). Nên chạy sau E.1–E.3 để có gì đó thật để kiểm, nhưng script tự nó viết độc lập được (báo FAIL khi thiếu).

**Nguyên tắc:** network check phải có timeout ngắn (VD 5s) để không treo. Check webhook có thể "skip" (⚠️) nếu `WEBHOOK_TEST_URL` trống thay vì FAIL cứng — do webhook là tùy chọn ở giai đoạn đầu.

### Skeleton tham khảo

```python
# tools/check_env.py
from __future__ import annotations
import os, sys, urllib.request, json

REQUIRED = ["WSS_URL", "ETHERSCAN_API_KEY"]

def check_env_vars() -> tuple[bool, str]:
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        return False, f"thiếu {missing} → xem docs/environment_setup.md (E.1)"
    return True, "biến bắt buộc đủ"

def check_etherscan() -> tuple[bool, str]:
    key = os.environ.get("ETHERSCAN_API_KEY", "")
    try:
        url = f"https://api.etherscan.io/api?module=proxy&action=eth_blockNumber&apikey={key}"
        with urllib.request.urlopen(url, timeout=5) as r:
            return (r.status == 200), f"Etherscan HTTP {r.status}"
    except Exception as e:
        return False, f"Etherscan lỗi: {e} → kiểm ETHERSCAN_API_KEY"

def check_whitelist() -> tuple[bool, str]:
    try:
        from ingestion.whitelist import ContractWhitelist
        w = ContractWhitelist.from_yaml("ingestion/whitelist.yaml")
        return (len(w) >= 3), f"whitelist {len(w)} entries"
    except Exception as e:
        return False, f"whitelist lỗi: {e} → xem E.2"

CHECKS = [
    ("Env vars", check_env_vars),
    ("Etherscan", check_etherscan),
    ("Whitelist", check_whitelist),
    # ("WSS", check_wss), ("Webhook", check_webhook),  # thêm sau
]

def main() -> int:
    all_ok = True
    for name, fn in CHECKS:
        ok, msg = fn()
        all_ok &= ok
        print(f"{'✅' if ok else '❌'} {name}: {msg}")
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
```
> skipped: WSS + webhook check trong skeleton — add khi E.1/E.3 xong. WSS dùng loader 1A.1 (async), webhook POST payload mẫu tới WEBHOOK_TEST_URL.

### Project Conventions

- Python 3.12, pytest (`asyncio_mode=auto`)
- `ruff check` cho linting
- Test dùng `monkeypatch` cho env, mock network (không gọi thật trong unit test)
- Chỉ dùng stdlib cho HTTP đơn giản (`urllib`) — không thêm dependency

### Project Structure Notes

```
tools/check_env.py            ← TẠO MỚI
tests/unit/test_check_env.py  ← TẠO MỚI
```

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

- `tools/check_env.py` (NEW)
- `tests/unit/test_check_env.py` (NEW)
