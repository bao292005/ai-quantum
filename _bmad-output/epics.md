---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: ["SPEC-mps-defi-risk", "ARCHITECTURE-SPINE.md"]
---

# QuantumRadar - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for QuantumRadar, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Hệ thống đọc dữ liệu tick-data lịch sử và real-time (từ file CSV hoặc Web3 RPC).
FR2: Chỉ lọc các sự kiện Swap, Mint, Burn (DEX) và Borrow, Supply, Withdraw, LiquidationCall (Lending).
FR3: Lõi toán học PyTorch tính toán Sự vướng víu (Entanglement) bằng MPS và xuất ra Fragility Index (0-100%).
FR4: Gửi tín hiệu Webhook (Cảnh báo Vàng/Đỏ) dựa trên ngưỡng 70% và 90%.
FR5: Tín hiệu Webhook tuân thủ JSON schema cố định (timestamp, fragility_score, alert_level, trigger_protocols).

### NonFunctional Requirements

NFR1: Độ trễ (Latency) từ lúc có block mới đến lúc gửi Webhook phải < 50ms.
NFR2: Toàn bộ việc kết nối I/O (WebSocket, Webhook) phải chạy bất đồng bộ (asyncio).
NFR3: Lõi toán học (PyTorch) phải chạy trên Process/Thread riêng biệt.
NFR4: Trạng thái 10 block gần nhất lưu trữ in-memory (RAM) dạng Ring Buffer, không ghi đĩa.
NFR5: Hoạt động cục bộ (Local-First) trên CPU tiêu chuẩn, không cần GPU.

### Additional Requirements

- [Stack Pinned] Sử dụng Python 3.11+, PyTorch 2.1+, Web3.py 6.11+, FastAPI 0.104+, Uvicorn 0.23+.
- [Structure] Tổ chức thư mục: `ingestion/`, `engine/`, `emitter/`, `core/`.

### UX Design Requirements

N/A

### FR Coverage Map

FR1: Epic 1 - Ingestion
FR2: Epic 1 - Lọc sự kiện
FR3: Epic 2, Epic 3, Epic 4 - Toán học, Tối ưu hóa, Hiệu chuẩn
FR4: Epic 5 - Alert System
FR5: Epic 5 - Payload Format

## Epic List

### Epic 1: Data Ingestion & State Management
Hệ thống cào dữ liệu từ Blockchain, lọc nhiễu và lưu trữ trên RAM theo thời gian thực.
**FRs covered:** FR1, FR2

### Epic 2: Tensor Graph Modeling
R&D Khởi tạo Mô hình: Biểu diễn thị trường DeFi dưới dạng Tensor.
**FRs covered:** FR3

### Epic 3: MPS Algorithm Optimization
R&D Tối ưu Thuật toán: Ép tốc độ chạy <30ms trên CPU.
**FRs covered:** FR3

### Epic 4: Risk Calibration & System Isolation
Hiệu chuẩn công thức và Đóng gói tiến trình.
**FRs covered:** FR3

### Epic 5: Alert System & API
Hệ thống API và Webhook tự động bắn tín hiệu Vàng/Đỏ.
**FRs covered:** FR4, FR5

## Epic 1: Data Ingestion & State Management

Hệ thống cào dữ liệu từ Blockchain, lọc nhiễu và lưu trữ trên RAM theo thời gian thực.

### Story 1.1: Web3 RPC WebSocket Connection

As a Kỹ sư Dữ liệu,
I want hệ thống mở một kết nối WebSocket duy trì liên tục vào Alchemy/Infura,
So that luồng dữ liệu thô từ Ethereum được đẩy về hệ thống với độ trễ tối thiểu (<50ms).

**Acceptance Criteria:**

**Given** URL WebSocket hợp lệ của Alchemy/Infura.
**When** khởi động module `ingestion`.
**Then** hệ thống kết nối thành công và in ra terminal luồng log thô.
**And** hệ thống tự động kết nối lại (auto-reconnect) bằng `asyncio` nếu bị rớt mạng.

### Story 1.2: DeFi Event Filter

As a Kỹ sư Dữ liệu,
I want hệ thống bóc tách chính xác các sự kiện (Swap, Mint, Burn, Borrow, Supply, Withdraw, LiquidationCall) từ Uniswap V3 và Aave V3,
So that loại bỏ hoàn toàn giao dịch rác, tiết kiệm dung lượng tính toán.

**Acceptance Criteria:**

**Given** luồng log thô đang chạy từ Story 1.1.
**When** dữ liệu đi qua lớp Filter.
**Then** hệ thống chỉ parse và trả về định dạng JSON của các sự kiện đã chỉ định.
**And** từ chối 100% các sự kiện chuyển token thông thường không tác động thanh khoản pool.

### Story 1.3: In-Memory Ring Buffer

As a Lõi Toán học,
I want duy trì một bộ nhớ đệm (Ring Buffer) lưu trữ chính xác trạng thái tick-data của 10 block gần nhất,
So that tôi luôn có dữ liệu mới nhất trên RAM để tính toán mà không bị nghẽn ổ đĩa.

**Acceptance Criteria:**

**Given** dữ liệu sạch (JSON) liên tục đổ về từ Story 1.2.
**When** thao tác đẩy (push) vào Buffer được gọi.
**Then** dữ liệu được lưu vào bộ nhớ, nếu vượt 10 block thì dữ liệu cũ nhất bị đẩy ra (FIFO).
**And** thao tác đọc/ghi vào `collections.deque` hoặc Numpy array hoàn thành < 5ms.

### Story 1.4: Orchestrate Data Pipeline

As a Kỹ sư Dữ liệu,
I want hệ thống có một luồng chính (Main Async Loop) tự động kết nối đầu ra WebSocket vào Filter và bơm vào Buffer,
So that dữ liệu chảy liên tục từ Ethereum vào tận lõi RAM mà không cần can thiệp thủ công.

**Acceptance Criteria:**

**Given** 3 module (WebSocket, Filter, Buffer) đã hoàn thiện.
**When** khởi động kịch bản `ingestion_pipeline.py`.
**Then** dữ liệu bắt đầu chảy mượt mà xuyên suốt qua 3 lớp không rò rỉ block nào.
**And** hệ thống in ra log giám sát pipeline (ví dụ: "Nhận Block -> Lọc X sự kiện -> Đẩy vào Buffer").

### Story 1.5: Data Quality Validation & Profiling

As a Data Analyst,
I want có một bộ công cụ (script/notebook) để trích xuất ngẫu nhiên dữ liệu từ Ring Buffer và chạy thống kê,
So that tôi có thể đối chiếu (reconcile) với Etherscan đảm bảo tính toàn vẹn của dữ liệu trước khi cấp phép cho Lõi Tensor sử dụng.

**Acceptance Criteria:**

**Given** Data Pipeline đang chạy liên tục.
**When** chạy script kiểm định `profiling.py` (hoặc mở Jupyter Notebook).
**Then** hệ thống xuất ra báo cáo tóm tắt chất lượng (tổng số lượng từng loại sự kiện, block rớt).
**And** khi chọn ngẫu nhiên 3 block đối chiếu tay với Etherscan, dữ liệu trùng khớp 100%.

### Story 1.6: Airflow Batch Orchestration & Automation

As a Kỹ sư Dữ liệu,
I want thiết lập Apache Airflow để tự động hóa các luồng dữ liệu chạy theo lô (batch jobs) và giám sát hệ thống,
So that việc cào dữ liệu lịch sử và kiểm định chất lượng diễn ra hoàn toàn tự động theo lịch trình (cron) mà không cần sức người.

**Acceptance Criteria:**

**Given** môi trường Airflow (Local hoặc Docker) đã được cài đặt.
**When** đến khung giờ định trước (VD: 00:00 mỗi đêm).
**Then** Airflow tự động kích hoạt DAG để cào dữ liệu block của ngày hôm đó và chạy luồng Kiểm định Chất lượng.
**And** Airflow cập nhật trạng thái xanh (Thành công) hoặc đỏ (Thất bại) trên Dashboard.

## Epic 2: Tensor Graph Modeling

R&D Khởi tạo Mô hình: Biểu diễn thị trường DeFi dưới dạng Tensor.

### Story 2.1: JSON to Graph Data Adapter

As an Kỹ sư AI,
I want chuyển đổi dữ liệu JSON từ bộ đệm thành cấu trúc Đồ thị (Graph Nodes/Edges),
So that thiết lập được nền tảng vật lý cho thuật toán.

**Acceptance Criteria:**

**Given** mảng JSON thô.
**When** parse.
**Then** trả về Graph object chuẩn.

### Story 2.2: Graph to PyTorch Tensor Mapping

As an Kỹ sư AI,
I want ánh xạ cấu trúc Đồ thị thành các Ma trận (State Vectors) tương thích PyTorch,
So that thư viện Tensor có thể thực thi.

**Acceptance Criteria:**

**Given** Graph object.
**When** map.
**Then** trả về PyTorch Tensors.

### Story 2.3: Tensor Representation Validation (Human Review)

As a Quants,
I want hệ thống xuất các ma trận mẫu để tôi review,
So that đảm bảo cấu trúc Tensor phản ánh chính xác dòng tiền.

**Acceptance Criteria:**

**Given** Tensors.
**When** xuất log/visualize.
**Then** con người chốt nghiệm thu.

## Epic 3: MPS Algorithm Optimization

R&D Tối ưu Thuật toán: Ép tốc độ chạy <30ms trên CPU.

### Story 3.1: MPS Baseline Benchmark

As an Kỹ sư AI,
I want cài đặt hàm MPS nguyên bản và đo đạc,
So that lấy được thông số thời gian chạy/RAM làm chuẩn (Baseline).

**Acceptance Criteria:**

**Given** Tensors từ Epic 2.
**When** chạy hàm forward.
**Then** output log benchmark.

### Story 3.2: Bond Dimension Tuning Profiler (Human Tuning)

As an Kỹ sư AI,
I want script hỗ trợ thay đổi tham số `bond_dimension` liên tục,
So that tôi trực tiếp quan sát trade-off giữa Tốc độ và Độ chính xác.

**Acceptance Criteria:**

**Given** script tuning.
**When** nhập bond dimension khác nhau.
**Then** xuất báo cáo so sánh.

### Story 3.3: SVD Truncation Implementation (Human Tuning)

As an Kỹ sư AI,
I want triển khai kỹ thuật SVD Truncation để nén ma trận,
So that tôi tinh chỉnh ngưỡng cắt tỉa sao cho thời gian chạy dưới 30ms.

**Acceptance Criteria:**

**Given** MPS Baseline.
**When** áp dụng SVD.
**Then** cắt bỏ giá trị suy biến, mô hình chạy nhanh hơn.

## Epic 4: Risk Calibration & System Isolation

Hiệu chuẩn công thức và Đóng gói tiến trình.

### Story 4.1: Fragility Index Calibration (Human Calibration)

As a Quản lý Rủi ro,
I want chạy dữ liệu FTX/LUNA qua mô hình MPS,
So that tôi điều chỉnh hàm Sigmoid/Min-Max để chỉ số báo đỏ (>=90%) đúng lúc.

**Acceptance Criteria:**

**Given** dữ liệu backtest.
**When** điều chỉnh tham số chuẩn hóa.
**Then** chỉ số khớp thực tế lịch sử.

### Story 4.2: Math Engine Multiprocessing Wrapper

As a Kiến trúc sư Hệ thống,
I want bọc toàn bộ mô hình đã chốt vào `multiprocessing.Process`,
So that lõi CPU chạy độc lập không treo WebSocket.

**Acceptance Criteria:**

**Given** lõi toán học hoàn thiện.
**When** khởi động tiến trình.
**Then** PID khác biệt, giao tiếp qua Queue/SharedMemory an toàn.

## Epic 5: Alert System & API

Hệ thống API và Webhook tự động bắn tín hiệu Vàng/Đỏ khi chỉ số vượt ngưỡng.

### Story 5.1: FastAPI Webhook Subscription

As a Quỹ Market Maker,
I want hệ thống có một API `/subscribe` để tôi đăng ký URL Webhook của bot giao dịch,
So that QuantumRadar biết phải gửi tín hiệu cảnh báo đi đâu khi có biến động.

**Acceptance Criteria:**

**Given** ứng dụng FastAPI đang chạy.
**When** gửi một POST request chứa URL hợp lệ lên endpoint `/subscribe`.
**Then** hệ thống lưu URL đó vào danh sách khách hàng nhận cảnh báo.
**And** có endpoint `/unsubscribe` để gỡ bỏ URL.

### Story 5.2: JSON Payload Formatter

As a Quỹ Market Maker,
I want tín hiệu nhận được phải tuân thủ đúng một chuẩn JSON thống nhất,
So that con bot giao dịch của tôi có thể dễ dàng đọc hiểu.

**Acceptance Criteria:**

**Given** kết quả Fragility Index từ Epic 4.
**When** đi qua lớp Formatter.
**Then** hệ thống tạo ra một chuỗi JSON chứa đúng 4 trường: `timestamp`, `fragility_score`, `alert_level`, `trigger_protocols`.
**And** `alert_level` tự động gán là "YELLOW" nếu điểm >= 70% và "RED" nếu >= 90%.

### Story 5.3: Async Webhook Emitter

As a Hệ thống,
I want một cơ chế bắn tín hiệu hàng loạt một cách bất đồng bộ tới tất cả khách hàng,
So that hệ thống có thể thông báo cho nhiều quỹ Market Maker cùng lúc mà tổng độ trễ < 50ms.

**Acceptance Criteria:**

**Given** JSON Payload và danh sách URL khách hàng.
**When** điều kiện báo động được kích hoạt.
**Then** hệ thống sử dụng `aiohttp` để bắn song song tất cả các request.
**And** các request bị lỗi/timeout sẽ không làm treo hệ thống chính, chỉ retry 1 lần.
