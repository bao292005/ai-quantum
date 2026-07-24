# Environment Setup
## Webhook test endpoint
Để test luồng gửi alert RED/YELLOW (Epic 5) mà chưa cần tích hợp client
thật, ta cần 1 URL webhook nhận thử. Có 2 cách lấy URL này:
### Cách 1 — Public: webhook.site
1. Mở https://webhook.site trên trình duyệt.
2. Trang tự sinh "Your unique URL" — copy URL này.
3. Dùng URL đó làm giá trị cho `WEBHOOK_TEST_URL` trong `.env`.
> ⚠️ Dữ liệu đi qua bên thứ 3 — không dùng cho payload nhạy cảm.
> Với alert test (chỉ có fragility score) thì an toàn.
### Cách 2 — Local: echo server
```bash
python -m tools.webhook_echo listen http://localhost:9000/hook
```
Server in ra stdout mỗi request POST nhận được (method, header, body
JSON) và trả về HTTP 200. Dùng thư viện chuẩn, không cần cài thêm gì.
Dùng `http://localhost:9000/hook` làm giá trị `WEBHOOK_TEST_URL`.
## Cấu hình qua env
URL webhook test lưu trong `.env` (không commit), key `WEBHOOK_TEST_URL`,
không hard-code trong source:
```dotenv
WEBHOOK_TEST_URL=https://webhook.site/xxxx-xxxx-xxxx
# hoặc: WEBHOOK_TEST_URL=http://localhost:9000/hook
```
### Đăng ký URL qua /subscribe (Epic 5)
Khi API `/subscribe` sẵn sàng, đăng ký `WEBHOOK_TEST_URL` bằng:
```bash
curl -X POST "$API_BASE_URL/subscribe" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"$WEBHOOK_TEST_URL\"}"
```
(Endpoint thuộc Epic 5 — ghi chú tham chiếu, chưa triển khai ở story này.)