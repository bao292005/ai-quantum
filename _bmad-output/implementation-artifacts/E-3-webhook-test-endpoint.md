---
baseline_commit: 0e04db60825409ad60bf9c50f73db6977cb733f6
type: setup
---

# Story E.3: Webhook Test Endpoint Config

Status: ready-for-dev

## Story

As a **Kỹ sư Backend**,
I want **cấu hình 1 webhook URL nhận thử để test luồng alert (Epic 5)**,
so that **có thể kiểm chứng RED/YELLOW payload được gửi đúng mà chưa cần client thật**.

## Acceptance Criteria

1. **AC1 — Hai lựa chọn endpoint được ghi rõ:** `docs/environment_setup.md` mô tả 2 cách lấy webhook test:
   - Public: https://webhook.site → copy unique URL
   - Local: `python -m tools.webhook_echo` listen `http://localhost:9000/hook`, in payload nhận được ra stdout

2. **AC2 — Cấu hình qua env:** URL test lưu vào `.env` là `WEBHOOK_TEST_URL`, không hard-code trong source.

3. **AC3 — Nhận đúng payload:** Gửi thử 1 payload mẫu (POST JSON) → endpoint nhận đúng và payload khớp `contracts/fragility_alert.schema.json` (4 field: timestamp, fragility_score, alert_level, trigger_protocols).

4. **AC4 — Local echo server (nếu chọn local):** `tools/webhook_echo.py` chạy được standalone, in mỗi request nhận được (method, headers tối thiểu, body JSON) và trả HTTP 200.

## Tasks / Subtasks

- [ ] **Task 1 — Viết hướng dẫn webhook test** (AC1, AC2)
  - [ ] Thêm section "Webhook test endpoint" vào `docs/environment_setup.md`
  - [ ] Ghi cách đăng ký URL qua `/subscribe` (Epic 5) khi API sẵn sàng
- [ ] **Task 2 — (Tùy chọn) Local echo server** (AC4)
  - [ ] `tools/webhook_echo.py` dùng `http.server` stdlib, listen port 9000, in body + trả 200
- [ ] **Task 3 — Gửi thử payload mẫu** (AC3)
  - [ ] `curl -X POST $WEBHOOK_TEST_URL -H "Content-Type: application/json" -d @sample_alert.json`
  - [ ] Xác nhận endpoint nhận + payload khớp schema 0.3

## Dev Notes

**Loại story:** `[SETUP]` — config/ops. Task 2 (echo server) là code nhỏ tùy chọn dùng **stdlib `http.server`** — không thêm dependency.

**Payload mẫu (`sample_alert.json`) khớp schema 0.3:**
```json
{
  "timestamp": "2022-05-07T21:04:48Z",
  "fragility_score": 92.5,
  "alert_level": "RED",
  "trigger_protocols": ["aave_v2"]
}
```

**Local echo server tham khảo (stdlib, không dependency):**
```python
# tools/webhook_echo.py
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        print("RECV:", json.dumps(json.loads(body or b"{}"), indent=2))
        self.send_response(200); self.end_headers()

if __name__ == "__main__":
    HTTPServer(("localhost", 9000), Handler).serve_forever()
```
> skipped: auth/TLS on echo server — add when testing production webhook delivery. Đây chỉ là receiver dev cục bộ.

**Lưu ý:** webhook.site tiện cho demo (thấy payload trên browser) nhưng dữ liệu đi qua bên thứ 3 — không dùng cho payload nhạy cảm. Với alert test (chỉ có fragility score, không có secret) thì an toàn.

### Project Structure Notes

```
.env                       ← thêm WEBHOOK_TEST_URL (local)
docs/environment_setup.md  ← UPDATE (section webhook test)
tools/webhook_echo.py      ← TẠO MỚI (tùy chọn, nếu chọn local)
```

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

- `docs/environment_setup.md` (UPDATE)
- `tools/webhook_echo.py` (NEW — optional local receiver)
- `.env` (LOCAL — thêm WEBHOOK_TEST_URL)
