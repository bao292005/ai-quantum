# Hướng dẫn Thiết lập Môi trường (Environment Setup)

Tài liệu này hướng dẫn chi tiết các bước thiết lập biến môi trường và kiểm tra kết nối để phục vụ dự án `ai-quantum`.

---

## 1. Cấu hình Alchemy / Infura (RPC Provider)

- **Link đăng ký:** Truy cập và tạo tài khoản tại [Alchemy Dashboard](https://dashboard.alchemy.com) hoặc [Infura](https://infura.io).
- **Chọn Network:** Trong giao diện cấu hình App, chọn mạng **Ethereum Mainnet**.
- **Lấy Endpoint:** Copy đường dẫn **WSS Endpoint** (có dạng `wss://eth-mainnet.g.alchemy.com/v2/...`).

## 2. Cấu hình Etherscan API

- **Link đăng ký:** Truy cập [Etherscan API Keys](https://etherscan.io/myapikey).
- **Tạo Key:** Đăng ký tài khoản miễn phí và nhấn nút **+ Add** để tạo một API Key mới.

## 3. Khởi tạo và điền file .env

Thực hiện sao chép file cấu hình mẫu và điền các khóa bí mật của bạn ở môi trường cục bộ (Local):

```bash
# Tạo file .env từ file mẫu
cp .env.example .env
```
