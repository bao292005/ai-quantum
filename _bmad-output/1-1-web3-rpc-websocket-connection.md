# Story 1.1: Web3 RPC WebSocket Connection

## 1. Story Foundation
**Epic:** Epic 1 - Data Ingestion & State Management
**Business Value:** This is the bedrock of the real-time capabilities for QuantumRadar. Without a stable, low-latency stream, the Tensor Engine will process outdated or missing data, rendering the Fragility Index useless.

**User Story:** 
As a Kỹ sư Dữ liệu,
I want hệ thống mở một kết nối WebSocket duy trì liên tục vào Alchemy/Infura,
So that luồng dữ liệu thô từ Ethereum được đẩy về hệ thống với độ trễ tối thiểu (<50ms).

**Acceptance Criteria:**
*   **Given** URL WebSocket hợp lệ của Alchemy/Infura.
*   **When** khởi động module `ingestion`.
*   **Then** hệ thống kết nối thành công và in ra terminal luồng log thô.
*   **And** hệ thống tự động kết nối lại (auto-reconnect) bằng `asyncio` nếu bị rớt mạng.

## 2. Developer Context & Technical Requirements

### Architecture Compliance
*   **Ngôn ngữ:** Python 3.11+
*   **Thư viện bắt buộc:** `web3` (Phiên bản 6.11+), `asyncio`, `websockets` (khuyến nghị dùng backend mặc định của AsyncWeb3).
*   **Quy tắc hệ thống:** Nghiêm cấm sử dụng bất kỳ thư viện chặn luồng (blocking I/O) nào. Mọi I/O phải là `async/await` để đáp ứng NFR1 (<50ms latency).

### File Structure Requirements
Tạo mới cấu trúc thư mục sau:
```text
├── ingestion/
│   ├── __init__.py
│   ├── config.py             # Load biến môi trường (WSS_URL, ALCHEMY_KEY)
│   ├── websocket_client.py   # Chứa class/hàm kết nối và reconnect
└── main.py                   # Entry point để chạy asyncio loop
```

### Library/Framework Implementation Details
Đội ngũ kiến trúc yêu cầu sử dụng **Web3.py v6+ Async API**:
*   Sử dụng `AsyncWeb3(WebSocketProvider(wss_url))` thay vì `Web3`.
*   Để lấy dữ liệu liên tục, thay vì dùng `get_logs` theo định kỳ (polling gây trễ), hãy sử dụng cơ chế **Subscriptions** của Ethereum qua WebSocket: `w3.eth.subscribe('newHeads')` hoặc `w3.eth.subscribe('logs', ...)` (Để đơn giản cho Story 1.1, hãy subscribe vào `newHeads` (block mới) hoặc in ra log rác bất kỳ để chứng minh luồng đang chảy).
*   **Auto-reconnect Pattern:** Cần bọc logic subscribe trong một khối `try-except`. Bắt lỗi `websockets.exceptions.ConnectionClosedError` và `asyncio.TimeoutError` để kích hoạt vòng lặp kết nối lại (ví dụ dùng `while True:` kết hợp `await asyncio.sleep(2)` để backoff).

### Testing Requirements
1.  **Chạy bình thường:** Chạy `python main.py`, quan sát terminal log in ra block/hash mới liên tục (<50ms kể từ khi block được đào trên etherscan).
2.  **Chaos Testing (Giả lập rớt mạng):** Trong lúc hệ thống đang chạy, hãy ngắt kết nối Wifi của máy tính trong 10 giây, sau đó bật lại. Màn hình console phải in ra "Connection lost... Retrying", và sau đó tự động khôi phục luồng dữ liệu mà không bị crash văng khỏi chương trình (exit code 1).

## 3. Implementation Steps (To-Do List for Dev)
- [ ] Thiết lập file `.env` mẫu (`.env.example`) chứa biến `WSS_URL`.
- [ ] Viết hàm đọc file `.env` vào `ingestion/config.py`.
- [ ] Viết class `EthereumStreamer` trong `ingestion/websocket_client.py`.
- [ ] Cài đặt hàm `async def start()` chứa vòng lặp `while True` với try/except để tự động reconnect.
- [ ] Cài đặt đoạn logic subscribe vào mạng Ethereum và `print()` kết quả ra terminal.
- [ ] Gọi hàm `start()` thông qua `asyncio.run()` tại `main.py`.

## 4. Status
**Status:** ready-for-dev
**Last Updated:** {{date}}
