---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: ["SPEC-mps-defi-risk", "ARCHITECTURE-SPINE.md", "implementation-readiness-report-2026-07-05"]
revision: v3.1-research-build-split
revisionDate: 2026-07-06
revisionNotes: "v2: Chia nhỏ Epic 0/1/2/3 thành story atomic để nhiều dev/agent làm song song. v3: Sau khi Epic 0 done, gắn nhãn [RESEARCH]/[BUILD] cho Epic 2/3/4 (research-nặng) để tách spike/R&D khỏi code production — research chốt decision trước, build tiêu thụ decision sau. Story không nhãn = [BUILD]. v3.1: Thêm 12 story non-code (research/design) vào Epic 1-4 để dựng bức tranh chi tiết trước khi code — Track 1R (data sourcing), 2R (model input design), 3R (math model — TIÊN QUYẾT), 4R (architecture & latency)."
---

# QuantumRadar - Epic Breakdown (v2, Parallel-Detailed)

## Overview

This document provides the complete epic and story breakdown for QuantumRadar, decomposing SPEC + ARCHITECTURE-SPINE requirements into atomic stories that can be executed by multiple developers/agents in parallel via contract-first design.

## Requirements Inventory

### Functional Requirements

FR1: Hệ thống đọc dữ liệu tick-data lịch sử (CSV) và real-time (Web3 RPC WebSocket).
FR2: Lọc các sự kiện Swap/Mint/Burn (Uniswap V3) và Borrow/Supply/Withdraw/LiquidationCall (Aave V3).
FR3: Lõi PyTorch tính Entanglement bằng MPS và xuất Fragility Index (0-100%).
FR4: Gửi tín hiệu Webhook Yellow (≥70%) / Red (≥90%).
FR5: Payload Webhook tuân JSON schema cố định (timestamp, fragility_score, alert_level, trigger_protocols).

### Non-Functional Requirements

NFR1: E2E latency (block-mới → Webhook) < 50ms.
NFR2: I/O bất đồng bộ (asyncio).
NFR3: Lõi PyTorch chạy trên Process riêng biệt.
NFR4: Ring buffer 10 blocks in-memory, no disk I/O runtime.
NFR5: Local-first CPU, không GPU.

### Additional Requirements

- Stack Pinned: Python 3.11+, PyTorch 2.1+, Web3.py 6.11+, FastAPI 0.104+, Uvicorn 0.23+.
- Structure: `ingestion/`, `engine/`, `emitter/`, `core/`, `contracts/`.
- Success Signal: Backtest LUNA/UST hoặc FTX bắn RED ≥10 phút trước liquidation dây chuyền.

### UX Design Requirements

N/A — API-only product.

### FR Coverage Map

- FR1: Epic 1 (Track 1A WebSocket + Track 1D CSV)
- FR2: Epic 1 (Track 1B Event Decoding)
- FR3: Epic 2 (Graph→Tensor) + Epic 3 (MPS Algorithm) + Epic 4 (Calibration)
- FR4: Epic 5 (Alert System)
- FR5: Epic 0 (Schema) + Epic 5 (Payload Formatter)

## Epic List

### Epic 0: Contracts & Test Fixtures (NEW — unblocks parallel work)
Chốt các JSON schema và fixtures đầu tiên để 4 Epic sau chạy song song bằng mock.
**FRs covered:** partial FR1, FR5 foundation

### Epic 1: Data Ingestion & State Management
Realtime WebSocket + Event Decoding + Ring Buffer + Historical CSV.
**FRs covered:** FR1, FR2

### Epic 2: Tensor Graph Modeling
Chuyển JSON events → Graph → PyTorch Tensor representation.
**FRs covered:** FR3 (representation)

### Epic 3: MPS Algorithm Optimization
Baseline → Bond Dimension R&D → SVD Truncation → Kernel Optimization → <30ms verify.
**FRs covered:** FR3 (computation)

### Epic 4: Risk Calibration & System Isolation
Hiệu chuẩn Fragility trên LUNA/FTX + Multiprocessing wrapper + E2E backtest verify.
**FRs covered:** FR3 (calibration), Success Signal

### Epic 5: Alert System & API
FastAPI subscription + JSON Payload + Async Webhook Emitter.
**FRs covered:** FR4, FR5

### Epic 6: End-to-End Verification & NFR Audit
E2E latency benchmark + no-GPU verify + Success Signal proof.
**FRs covered:** NFR1, NFR5, Success Signal

---

## Epic 0: Contracts & Test Fixtures

Chốt hợp đồng dữ liệu và fixtures TRƯỚC để mọi Epic có thể start song song bằng mock data thay vì chờ upstream.

### Story 0.1: Tick-Data JSON Schema

As a Kiến trúc sư,
I want định nghĩa formal JSON schema cho một normalized tick-data event,
So that ingestion (Epic 1) và consumers (Epic 2) đều tuân cùng contract.

**Acceptance Criteria:**
**Given** yêu cầu decode Uniswap V3 và Aave V3 events.
**When** publish schema tại `contracts/tick_data.schema.json`.
**Then** schema cover: `block_number`, `block_timestamp`, `protocol` (uniswap_v3|aave_v3), `event_type` (swap|mint|burn|borrow|supply|withdraw|liquidation), `pool_address`, `token0`, `token1`, `amount0`, `amount1`, `tx_hash`.
**And** có ít nhất 3 unit test validate 3 example event khớp schema (JSON Schema Draft 2020-12).

### Story 0.2: Graph Object JSON Schema

As a Kỹ sư AI,
I want schema cho `GraphSnapshot` (nodes + edges) mà Epic 2 output ra,
So that Epic 3 mock được input mà chưa cần Epic 2 xong.

**Acceptance Criteria:**
**Given** yêu cầu MPS input.
**When** publish schema tại `contracts/graph_snapshot.schema.json`.
**Then** schema cover: `snapshot_id`, `block_range`, `nodes[]` (id, type, features), `edges[]` (src, dst, weight, edge_type).
**And** kèm 1 example `graph_snapshot_example.json` validate pass.

### Story 0.3: Fragility Payload Schema

As a Đội Emitter,
I want schema cho webhook payload chuẩn,
So that Epic 5 formatter và consumer test cùng lúc.

**Acceptance Criteria:**
**Given** AD-3 spec.
**When** publish `contracts/fragility_alert.schema.json`.
**Then** enforce 4 field: `timestamp` (ISO 8601 UTC), `fragility_score` (0-100 float), `alert_level` (YELLOW|RED), `trigger_protocols[]`.
**And** contract test reject payload thiếu bất kỳ field nào.

### Story 0.4: Historical Backtest Fixtures

As a QA + Calibration engineer,
I want dataset LUNA/UST và FTX 24h trước sự kiện + 1 ngày bình thường,
So that Epic 3, 4, 6 dùng chung ground truth để verify Success Signal.

**Acceptance Criteria:**
**Given** dữ liệu on-chain public (Etherscan/Dune).
**When** kết xuất CSV vào `fixtures/backtest/{luna_2022_05_09.csv, ftx_2022_11_08.csv, normal_2023_03_15.csv}`.
**Then** mỗi file có ít nhất 1000 events, khớp schema Story 0.1.
**And** file `fixtures/backtest/README.md` ghi rõ block range, expected liquidation timestamp, expected RED alert deadline.

### Story 0.5: Mock WebSocket Server

As a Dev track B/C/D,
I want một mock WSS server phát fake `newHeads` + logs theo tốc độ realtime,
So that có thể phát triển Epic 1 downstream (filter, buffer) và test Epic 2/3 mà không cần Alchemy key.

**Acceptance Criteria:**
**Given** fixture file từ Story 0.4.
**When** chạy `python -m tools.mock_wss --file=luna_2022_05_09.csv --speed=1x`.
**Then** server listen `ws://localhost:8546`, phát log JSON đúng shape tương ứng `eth_subscribe`.
**And** có flag `--speed=100x` để test nhanh.

---

## Epic 1: Data Ingestion & State Management

Chia thành 6 track: 1R (research nền tảng) + 5 track thực thi (1A-1E) chạy song song sau khi Epic 0 xong.

**Phân loại:** `[RESEARCH]` toàn bộ Track 1R · còn lại `[BUILD]`.

### Track 1R — Data Sourcing & Ground Truth (Research)

#### Story 1R.1: Data Source Assessment `[RESEARCH]`

As a Kỹ sư Dữ liệu,
I want đánh giá Etherscan / Dune / Alchemy về độ phủ, rate limit, chi phí, độ sâu archival,
So that chốt nguồn primary + fallback trước khi code ingestion.

**Acceptance Criteria:**
**Given** yêu cầu realtime WSS + historical backfill.
**When** khảo sát 3 nhà cung cấp.
**Then** publish `research/data_sources.md` với bảng so sánh (rate limit, cost/tháng, archival depth, WSS support) + khuyến nghị primary/fallback.
**And** ghi rõ block-range LUNA/FTX có lấy được từ nguồn đã chọn không.

#### Story 1R.2: Event Schema ↔ ABI Reconciliation `[RESEARCH]`

As a Kỹ sư Dữ liệu,
I want đối chiếu `contracts/tick_data.schema.json` (Story 0.1) với ABI thật của Uniswap V3 + Aave V3,
So that phát hiện field thiếu/sai trước khi viết decoder (Track 1B).

**Acceptance Criteria:**
**Given** ABI chính thức 2 protocol.
**When** map từng event (Swap/Mint/Burn, Borrow/Supply/Withdraw/LiquidationCall) sang schema.
**Then** publish `research/schema_abi_gap.md` liệt kê field khớp, field thiếu, field cần thêm.
**And** đề xuất bản vá schema nếu có gap (feed lại Story 0.1).

#### Story 1R.3: Ground-Truth Labeling Methodology `[RESEARCH]`

As a Calibration engineer,
I want định nghĩa chính xác "thời điểm cascade bắt đầu" và "RED deadline" cho LUNA/FTX,
So that nhãn ground-truth trong fixtures (0.4) có căn cứ, Epic 4 verify được khách quan.

**Acceptance Criteria:**
**Given** dữ liệu on-chain + tường thuật sự kiện LUNA (2022-05) và FTX (2022-11).
**When** xác định tiêu chí liquidation cascade (VD liquidation đầu tiên > $X, hoặc chuỗi ≥ N liquidation/block).
**Then** publish `research/ground_truth_labeling.md` với tiêu chí + timestamp + nguồn dẫn chứng cho từng fixture.
**And** đối chiếu khớp với `fixtures/backtest/README.md`, cập nhật nếu lệch.

### Track 1A — Realtime WebSocket Connection

#### Story 1A.1: Environment & Secrets Loader

As a Kỹ sư Dữ liệu,
I want một module đọc `.env` (WSS_URL, ALCHEMY_KEY) với validation,
So that không hard-code credential.

**Acceptance Criteria:**
**Given** file `.env.example`.
**When** `python -c "from ingestion.config import load; print(load())"`.
**Then** trả về dataclass `IngestionConfig` với typed fields.
**And** raise `ConfigError` nếu thiếu biến bắt buộc.

#### Story 1A.2: AsyncWeb3 Client Wrapper

As a Kỹ sư Dữ liệu,
I want class `EthereumClient` wrap `AsyncWeb3(WebSocketProvider)`,
So that mọi consumer dùng cùng interface.

**Acceptance Criteria:**
**Given** URL WSS hợp lệ.
**When** `await client.connect()`.
**Then** trả về `AsyncWeb3` instance sẵn sàng subscribe.
**And** raise `ConnectionError` sau 3s timeout.

#### Story 1A.3: Exponential Backoff Reconnector

As a Kỹ sư Dữ liệu,
I want decorator `@auto_reconnect(max_retries=None, base=0.5, cap=30)`,
So that mọi coroutine dùng WebSocket tự retry khi đứt mạng.

**Acceptance Criteria:**
**Given** mock server chủ động close connection.
**When** decorated coroutine chạy.
**Then** retry với delay 0.5, 1, 2, 4, 8, 16, 30 giây.
**And** log mỗi retry với structured JSON.

#### Story 1A.4: newHeads Subscription

As a Kỹ sư Dữ liệu,
I want subscribe `newHeads` và yield block header mới ra async generator,
So that downstream filter tiêu thụ được.

**Acceptance Criteria:**
**Given** mock WSS server từ Story 0.5.
**When** `async for head in stream_new_heads(client): ...`.
**Then** nhận đúng số block phát ra từ mock, độ lệch thời gian < 100ms.
**And** exit sạch khi consumer cancel task.

#### Story 1A.5: Heartbeat & Metrics

As a SRE,
I want metric `ingestion_ws_last_message_seconds`,
So that alert được khi luồng đứng.

**Acceptance Criteria:**
**Given** `EthereumClient` đang chạy.
**When** không có message trong 15s.
**Then** metric > 15 và log WARN "stream stalled".
**And** expose qua endpoint `/metrics` (Prometheus text format).

### Track 1B — Event Decoding

#### Story 1B.1: Uniswap V3 Event Decoder

As a Kỹ sư Dữ liệu,
I want decoder parse `Swap`, `Mint`, `Burn` events của Uniswap V3 pool,
So that convert raw log → schema Story 0.1.

**Acceptance Criteria:**
**Given** raw log Uniswap V3 (topic0 = Swap signature).
**When** `UniswapDecoder.decode(log)`.
**Then** trả về `TickDataEvent` khớp schema 0.1.
**And** unit test cover ít nhất 5 log thật từ mainnet, khớp giá trị Etherscan.

#### Story 1B.2: Aave V3 Event Decoder

As a Kỹ sư Dữ liệu,
I want decoder parse `Borrow`, `Supply`, `Withdraw`, `LiquidationCall` của Aave V3,
So that convert raw log → schema Story 0.1.

**Acceptance Criteria:**
**Given** raw log Aave V3 pool.
**When** `AaveDecoder.decode(log)`.
**Then** trả về `TickDataEvent` khớp schema 0.1.
**And** unit test cover 5 log thật, khớp Etherscan.

#### Story 1B.3: Contract Address Whitelist Config

As a Kỹ sư Dữ liệu,
I want YAML `contracts_whitelist.yaml` liệt kê 3-5 pool Uniswap + Aave core,
So that dễ mở rộng scope mà không đụng code.

**Acceptance Criteria:**
**Given** file whitelist.
**When** `load_whitelist()`.
**Then** trả về `dict[address → (protocol, pool_meta)]`.
**And** schema validation reject địa chỉ sai checksum.

#### Story 1B.4: Event Router & Normalizer

As a Kỹ sư Dữ liệu,
I want router nhận raw log → tra whitelist → gọi đúng decoder → phát `TickDataEvent`,
So that unify luồng 2 protocol.

**Acceptance Criteria:**
**Given** log của địa chỉ ngoài whitelist.
**When** đi qua router.
**Then** log bị drop, metric `events_dropped_total{reason="not_in_whitelist"}` tăng.
**And** log trong whitelist được decode và emit.

### Track 1C — Ring Buffer Storage

#### Story 1C.1: Ring Buffer Interface

As a Lõi Toán học,
I want interface `RingBuffer[T]` với `push(t)`, `snapshot() -> list[T]`, `size()`,
So that consumer thay đổi implementation không phá contract.

**Acceptance Criteria:**
**Given** interface đăng ký tại `core/ring_buffer.py`.
**When** import.
**Then** có abstract base class + type hints đầy đủ.
**And** có markdown docstring mô tả invariant.

#### Story 1C.2: Deque-based Ring Buffer

As a Lõi Toán học,
I want implementation dùng `collections.deque(maxlen=10 * events_per_block_hint)`,
So that có baseline hoạt động ngay.

**Acceptance Criteria:**
**Given** stream 1000 event.
**When** push liên tục.
**Then** `size() <= maxlen`, oldest bị FIFO out.
**And** micro-benchmark push < 1μs/op.

#### Story 1C.3: Numpy Static Array Variant

As a Lõi Toán học,
I want variant dùng preallocated numpy array + head index,
So that so sánh throughput với deque.

**Acceptance Criteria:**
**Given** cùng workload Story 1C.2.
**When** benchmark.
**Then** báo cáo comparison `benchmarks/ring_buffer_deque_vs_numpy.md`.
**And** cả 2 implementation pass cùng contract test.

#### Story 1C.4: Asyncio-safe Wrapper

As a Kỹ sư Dữ liệu,
I want wrap ring buffer với `asyncio.Lock` cho write, snapshot lockless copy,
So that ingestion loop và engine loop chia sẻ an toàn.

**Acceptance Criteria:**
**Given** 2 coroutine concurrent (writer 10k/s, reader 1k/s).
**When** chạy 30 giây.
**Then** không có race condition (kiểm bằng hash sequence).
**And** overhead < 5% so với non-locked.

### Track 1D — Historical CSV Ingestion

#### Story 1D.1: CSV Schema Mapping

As a Data Analyst,
I want quy tắc map CSV column → `TickDataEvent`,
So that fixture Story 0.4 dùng chung schema với realtime.

**Acceptance Criteria:**
**Given** file `luna_2022_05_09.csv`.
**When** đọc.
**Then** mỗi row → `TickDataEvent` khớp schema 0.1.
**And** row lỗi format ghi vào `csv_errors.log` không crash pipeline.

#### Story 1D.2: CSV Streamer

As a Data Analyst,
I want async generator `stream_csv(path)` phát event theo thứ tự timestamp,
So that Epic 4 replay backtest.

**Acceptance Criteria:**
**Given** CSV 10k row.
**When** iterate.
**Then** yield theo thứ tự thời gian.
**And** memory footprint < 50MB.

#### Story 1D.3: Backtest Replay Driver

As a Calibration engineer,
I want `ReplayDriver(rate="1x"|"100x"|"asap")` bơm CSV vào ring buffer đúng nhịp thời gian,
So that Epic 4 test Fragility trên timeline thật.

**Acceptance Criteria:**
**Given** CSV 24h.
**When** `rate="100x"`.
**Then** replay xong trong ≤ 15 phút wall-clock.
**And** khoảng cách timestamp giữa event giữ tỉ lệ chính xác.

### Track 1E — Integration & Quality

#### Story 1E.1: Pipeline Orchestrator

As a Kỹ sư Dữ liệu,
I want main script `python -m ingestion.pipeline` nối 1A → 1B → 1C,
So that realtime chảy end-to-end.

**Acceptance Criteria:**
**Given** mock WSS Story 0.5.
**When** chạy `--source=mock`.
**Then** metrics `events_ingested_total`, `blocks_processed_total` tăng.
**And** graceful shutdown khi SIGTERM (drain queue < 2s).

#### Story 1E.2: Etherscan Reconciliation Tool

As a Data Analyst,
I want script chọn ngẫu nhiên 3 block trong buffer + gọi Etherscan API + so sánh,
So that verify tính toàn vẹn data.

**Acceptance Criteria:**
**Given** buffer đang chạy realtime 5 phút.
**When** chạy `python -m tools.reconcile_etherscan`.
**Then** báo cáo `reconcile_report.md` với 3 block, tỉ lệ trùng khớp 100%.
**And** fail nếu tỉ lệ < 99.5%.

#### Story 1E.3: Data Quality Profiling Report

As a Data Analyst,
I want notebook `notebooks/profile.ipynb` xuất bảng số lượng event/protocol/type, block drop rate,
So that team đánh giá chất lượng.

**Acceptance Criteria:**
**Given** buffer chạy 1h.
**When** run notebook.
**Then** xuất HTML report với 4 chart (event count, drop rate, per-protocol breakdown, timestamp gap histogram).
**And** report chỉ ra bất kỳ gap > 30s.

---

## Research / Build Split (áp dụng cho Epic 2, 3, 4)

Epic 2/3/4 trộn spike/R&D (kết quả không chắc chắn) với code production. Từ v3, mỗi story được phân loại để tách "nghiên cứu" khỏi "code":

- **`[RESEARCH]`** — spike / R&D / phân tích. Output chính là **decision hoặc report** (chốt tham số, chọn thuật toán, xác nhận biểu diễn), có thể throwaway. **Chạy TRƯỚC** để mở khoá phần build phụ thuộc.
- **`[RESEARCH→BUILD]`** — story lai: thí nghiệm chọn phương án rồi productionize ngay trong cùng story.
- **`[BUILD]`** *(mặc định — story không gắn nhãn)* — code production theo spec/decision đã chốt. Chạy song song nếu độc lập, hoặc sau khi `[RESEARCH]` liên quan chốt decision.

**Nguyên tắc handoff:** mỗi `[RESEARCH]` phải kết bằng 1 quyết định ghi ra file (VD `metrics/*.md`, `calibration/*.md`) → story `[BUILD]` tham chiếu decision đó làm input, không tự phát minh lại.

---

## Epic 2: Tensor Graph Modeling

Chia thành 4 track: 2R (research input design) + 3 track thực thi (2A-2C), start ngay sau Epic 0 xong (dùng mock).

**Phân loại:** `[RESEARCH]` toàn bộ 2R, 2A.4, 2C.3 · `[RESEARCH→BUILD]` 2B.3 · còn lại `[BUILD]`.

### Track 2R — Model Input Design (Research)

#### Story 2R.1: Node Feature Catalog & Sourcing `[RESEARCH]`

As a Kỹ sư AI,
I want catalog chính xác cho từng node feature (tvl, utilization, price_delta, volatility, borrow_rate): công thức tính, nguồn dữ liệu, nhịp cập nhật, chính sách khi thiếu,
So that Story 2B.2 (Node Feature Tensor) có spec rõ thay vì đoán.

**Acceptance Criteria:**
**Given** danh sách feature trong Story 2B.2.
**When** định nghĩa từng feature.
**Then** publish `research/feature_catalog.md`: mỗi feature có (công thức, input event/field, đơn vị, range kỳ vọng, missing-data policy).
**And** chỉ ra feature nào tính được từ schema 0.1, feature nào cần nguồn phụ.

#### Story 2R.2: Graph Topology Design `[RESEARCH]`

As a Kỹ sư AI,
I want chốt cách dựng đồ hình: loại node, quy tắc nối cạnh, kích thước N kỳ vọng lúc runtime, độ thưa,
So that quyết định tensor shape và có cần sparse variant (2B.4) hay không.

**Acceptance Criteria:**
**Given** scope 3-5 pool Uniswap + Aave core (whitelist 1B.3).
**When** phác đồ hình đại diện.
**Then** publish `research/graph_topology.md` với sơ đồ mẫu, N ước lượng, ma trận sparsity ước lượng.
**And** khuyến nghị dense hay sparse cho v1 + ngưỡng chuyển sang sparse.

### Track 2A — Graph Construction

#### Story 2A.1: Node Type Schema

As a Kỹ sư AI,
I want định nghĩa node type: `Protocol`, `Pool`, `Token`,
So that graph có typology rõ ràng.

**Acceptance Criteria:**
**Given** design doc.
**When** publish `engine/graph/node_types.py` (Pydantic model).
**Then** mỗi node type có fields: `id`, `features: dict[str, float]`.
**And** unit test tạo 3 node mỗi type, validate qua Pydantic.

#### Story 2A.2: Edge Type Schema

As a Kỹ sư AI,
I want định nghĩa edge type: `LiquidityFlow`, `BorrowPosition`, `SharedCollateral`,
So that entanglement thể hiện đúng.

**Acceptance Criteria:**
**Given** design doc.
**When** publish `engine/graph/edge_types.py`.
**Then** edge có: `src`, `dst`, `edge_type`, `weight: float`, `metadata: dict`.
**And** invariant test: weight >= 0.

#### Story 2A.3: Graph Builder (JSON → NetworkX)

As a Kỹ sư AI,
I want function `build_graph(events: list[TickDataEvent]) -> GraphSnapshot`,
So that convert được raw events → graph.

**Acceptance Criteria:**
**Given** 100 mock events từ fixture 0.4.
**When** build.
**Then** trả về `GraphSnapshot` khớp schema 0.2.
**And** benchmark < 20ms cho 1000 events trên 1 CPU core.

#### Story 2A.4: Edge Weight Formula `[RESEARCH]`

As a Quants,
I want weight = f(volume_usd, time_decay, protocol_correlation),
So that phản ánh liquidity flow thực.

**Acceptance Criteria:**
**Given** 3 pool cùng khối lượng nhưng khác nhau về thời gian.
**When** apply formula.
**Then** edge mới nhất có weight lớn nhất (time-decay), tổng weight normalize về [0,1].
**And** unit test cho 5 case biên.

### Track 2B — Tensor Mapping

#### Story 2B.1: Adjacency Tensor Constructor

As a Kỹ sư AI,
I want `adjacency_tensor(graph) -> torch.Tensor` với shape `(N, N)`,
So that MPS engine tiêu thụ.

**Acceptance Criteria:**
**Given** `GraphSnapshot` với 50 node.
**When** convert.
**Then** trả về tensor 50x50 float32, đối xứng cho undirected edges.
**And** benchmark < 5ms.

#### Story 2B.2: Node Feature Tensor

As a Kỹ sư AI,
I want `feature_tensor(graph) -> torch.Tensor` shape `(N, F)`,
So that node embedding có input.

**Acceptance Criteria:**
**Given** node có 5 feature (tvl, utilization, price_delta, volatility, borrow_rate).
**When** convert.
**Then** trả về tensor `(N, 5)`.
**And** NaN được thay bằng 0 với warning.

#### Story 2B.3: Normalization Layer `[RESEARCH→BUILD]`

As a Kỹ sư AI,
I want `normalize(tensor, method="minmax"|"zscore")` toggle,
So that thử nghiệm scheme nào giúp MPS ổn định hơn.

**Acceptance Criteria:**
**Given** tensor có outlier.
**When** normalize.
**Then** output range đúng (minmax → [0,1], zscore → mean≈0 std≈1).
**And** parameter được persist trong `NormalizationState` để dùng lại lúc inference.

#### Story 2B.4: Sparse Tensor Variant

As a Kỹ sư AI,
I want variant sparse (COO) cho graph có >90% zero entries,
So that giảm memory cho graph lớn v2.

**Acceptance Criteria:**
**Given** graph 500 node, sparsity 95%.
**When** convert dense vs sparse.
**Then** sparse tiết kiệm ≥ 80% RAM.
**And** cùng kết quả contraction (tolerance 1e-6).

### Track 2C — Validation

#### Story 2C.1: Tensor Invariant Unit Tests

As a Quants,
I want test suite verify: symmetry, non-negative weight, mass conservation,
So that bug math bị bắt sớm.

**Acceptance Criteria:**
**Given** 20 sample graph.
**When** run `pytest tests/test_tensor_invariants.py`.
**Then** all pass.
**And** test cover cả sparse và dense variant.

#### Story 2C.2: Heatmap Visualization

As a Quants,
I want script vẽ adjacency heatmap + node feature bar chart,
So that mắt thường xác nhận đồ hình.

**Acceptance Criteria:**
**Given** `GraphSnapshot`.
**When** chạy `python -m tools.visualize --input=snapshot.json --out=graph.png`.
**Then** file PNG + JSON legend được tạo.
**And** README chỉ cách interpret heatmap.

#### Story 2C.3: Reference Dataset Comparison `[RESEARCH]`

As a Quants,
I want so sánh tensor generated từ LUNA fixture vs baseline (Nansen public data),
So that verify representation không lệch thị trường thật.

**Acceptance Criteria:**
**Given** fixture LUNA + baseline reference.
**When** so sánh top-10 edge theo weight.
**Then** ≥ 7/10 edge trùng đối tác.
**And** report `references/luna_comparison.md`.

---

## Epic 3: MPS Algorithm Optimization

Chia thành 6 track: 3R (model design — TIÊN QUYẾT) + 5 track thực thi. Track 3A độc lập với 3B/3C/3D. 3E là gate cuối.

**Phân loại:** `[RESEARCH]` toàn bộ Track 3R (TIÊN QUYẾT), 3A.4, 3B.1, 3B.2, 3B.3 · `[RESEARCH→BUILD]` 3C.3 · còn lại `[BUILD]`. Track 3B (Bond Dimension R&D) là research thuần → chốt `bond_dim` trước, các track build (3C/3D) tiêu thụ giá trị đã chốt.

### Track 3R — Model & Math Design (Research) — TIÊN QUYẾT

Track này phải xong trước Track 3A: hiện chưa có định nghĩa toán chính thức cho việc graph→Fragility.

#### Story 3R.1: MPS Fragility Math Spec `[RESEARCH]`

As a Kỹ sư AI / Quants,
I want đặc tả toán chính thức: adjacency + feature tensor → phân rã MPS/tensor-train → entanglement entropy → Fragility raw scalar,
So that Story 3A.1 (Naive Contraction) có công thức để implement thay vì đoán.

**Acceptance Criteria:**
**Given** input tensor shape từ Epic 2 (2B.1/2B.2).
**When** đặc tả mô hình.
**Then** publish `research/mps_fragility_model.md`: ký hiệu, chiều tensor, thứ tự contraction, công thức entanglement entropy, ánh xạ entropy→Fragility raw.
**And** kèm 1 ví dụ numeric nhỏ (graph 3 node) tính tay để 3A.1 dùng làm test oracle.

#### Story 3R.2: Tensor-Network Systemic-Risk Literature Review `[RESEARCH]`

As a Quants,
I want khảo sát prior art (entanglement entropy làm proxy rủi ro, tensor network trong tài chính),
So that biện minh cách tiếp cận và tránh phát minh lại / đi sai hướng.

**Acceptance Criteria:**
**Given** chủ đề MPS + systemic risk.
**When** review ≥ 5 nguồn.
**Then** publish `research/literature_review.md` tóm tắt + trích dẫn + bài học áp dụng cho QuantumRadar.
**And** nêu rõ giả định nào của ta chưa có tiền lệ (rủi ro nghiên cứu).

#### Story 3R.3: Naive Baseline Detector Design `[RESEARCH]`

As a Quants,
I want thiết kế 1 detector đơn giản không dùng MPS (VD ngưỡng trên tổng leverage/utilization hoặc graph centrality),
So that có mốc so sánh chứng minh MPS thực sự thêm giá trị.

**Acceptance Criteria:**
**Given** cùng fixture LUNA/FTX.
**When** định nghĩa baseline.
**Then** publish `research/baseline_detector.md` với thuật toán baseline + cách so sánh (lead-time, false positive) với MPS.
**And** baseline đủ đơn giản để implement trong ≤ 1 story build sau này.

### Track 3A — Baseline Implementation

#### Story 3A.1: Naive Tensor Contraction

As a Kỹ sư AI,
I want implement naive MPS contraction dùng `torch.einsum` không tối ưu,
So that có baseline correctness (không care performance).

**Acceptance Criteria:**
**Given** tensor 50x50 + feature tensor.
**When** forward.
**Then** trả về scalar Fragility raw (chưa normalize).
**And** result deterministic (seed torch).

#### Story 3A.2: Pytest Benchmark Harness

As a SRE,
I want `pytest-benchmark` cấu hình đo p50/p95/p99 latency,
So that mọi PR đo được regression.

**Acceptance Criteria:**
**Given** test suite `tests/bench_mps.py`.
**When** `pytest --benchmark-only`.
**Then** báo cáo HTML tại `bench_report/`.
**And** CI fail nếu p95 tăng > 10% so với baseline.

#### Story 3A.3: Memory Profiler Integration

As a SRE,
I want dùng `tracemalloc` đo peak memory mỗi forward pass,
So that phát hiện leak sớm.

**Acceptance Criteria:**
**Given** benchmark chạy.
**When** collect.
**Then** report `bench_report/memory.md` với peak RSS + tensor allocation breakdown.
**And** fail nếu peak > 500MB (giới hạn PoC).

#### Story 3A.4: Baseline Metrics Report `[RESEARCH]`

As a PM,
I want document `metrics/baseline.md` chốt số baseline: latency p50/p95, memory, output range,
So that cả team biết mục tiêu tối ưu.

**Acceptance Criteria:**
**Given** kết quả Story 3A.1–3A.3.
**When** publish.
**Then** file có 3 bảng metrics + note assumption (CPU spec, torch version).
**And** git tag `baseline-v0`.

### Track 3B — Bond Dimension R&D

#### Story 3B.1: Bond Dimension Parametrized Runner `[RESEARCH]`

As a Kỹ sư AI,
I want script `python -m engine.mps.tune --bond=8,16,32,64` chạy sweep,
So that dễ thí nghiệm giá trị.

**Acceptance Criteria:**
**Given** graph fixture.
**When** chạy sweep.
**Then** output CSV `tune_results.csv` với column `(bond_dim, latency_ms, accuracy_vs_baseline, memory_mb)`.
**And** hỗ trợ resume nếu crash giữa chừng.

#### Story 3B.2: Trade-off Matrix Generator `[RESEARCH]`

As a Quants,
I want function tạo bảng Pareto từ `tune_results.csv`,
So that chọn bond_dim tối ưu.

**Acceptance Criteria:**
**Given** CSV có ≥ 4 điểm sweep.
**When** run.
**Then** báo cáo markdown highlight Pareto front + gợi ý điểm tốt nhất theo weight (latency 60%, accuracy 40%).
**And** kèm scatter plot `tune_pareto.png`.

#### Story 3B.3: Accuracy-vs-Speed Visualization `[RESEARCH]`

As a Kỹ sư AI,
I want plot latency vs accuracy loss,
So that trực quan hoá trade-off.

**Acceptance Criteria:**
**Given** CSV Story 3B.1.
**When** chạy `python -m tools.plot_tradeoff`.
**Then** file `pareto.png` + `pareto.html` (interactive).
**And** annotate baseline point.

### Track 3C — SVD Truncation

#### Story 3C.1: SVD Decomposition Wrapper

As a Kỹ sư AI,
I want function `truncated_svd(matrix, rank) -> (U, S, Vh)`,
So that nén ma trận.

**Acceptance Criteria:**
**Given** matrix 128x128.
**When** truncate rank=32.
**Then** reconstruction error < 5%.
**And** benchmark < 3ms.

#### Story 3C.2: Truncation Threshold Selector

As a Kỹ sư AI,
I want auto-chọn rank giữ 95% năng lượng (singular values²),
So that không phải hard-code rank.

**Acceptance Criteria:**
**Given** matrix bất kỳ.
**When** `auto_rank(matrix, energy=0.95)`.
**Then** trả về rank R sao cho `sum(S[:R]²)/sum(S²) ≥ 0.95`.
**And** unit test cho 5 matrix synthetic.

#### Story 3C.3: Recompression Pipeline `[RESEARCH→BUILD]`

As a Kỹ sư AI,
I want áp SVD truncation vào full MPS chain,
So that end-to-end tăng tốc.

**Acceptance Criteria:**
**Given** baseline p95 = X ms.
**When** áp truncation.
**Then** p95 giảm ≥ 40% (khớp target < 30ms nếu baseline < 60ms).
**And** accuracy loss < 5% so với baseline.

#### Story 3C.4: Numerical Stability Guard

As a Kỹ sư AI,
I want detect rank-deficient case (S[-1] < 1e-10) và fallback,
So that không crash trên edge case.

**Acceptance Criteria:**
**Given** matrix rank-deficient.
**When** chạy pipeline.
**Then** fallback về full rank + log WARN, không crash.
**And** test synthetic rank-deficient matrix pass.

### Track 3D — Kernel Optimization

#### Story 3D.1: Contraction Path Optimizer (opt_einsum)

As a Kỹ sư AI,
I want dùng `opt_einsum.contract_path` chọn đường contraction tối ưu,
So that giảm FLOPs.

**Acceptance Criteria:**
**Given** MPS 5 tensor.
**When** so sánh naive vs opt_einsum.
**Then** FLOPs report giảm ≥ 30%.
**And** latency đo được giảm tương ứng.

#### Story 3D.2: TorchScript Compilation

As a Kỹ sư AI,
I want `torch.jit.script` compile hot path,
So that loại Python overhead.

**Acceptance Criteria:**
**Given** hot loop.
**When** compile + benchmark.
**Then** p95 giảm ≥ 15% so với eager mode.
**And** unit test verify output bit-identical.

#### Story 3D.3: Tensor Reuse & Cache Warmup

As a Kỹ sư AI,
I want preallocate output tensor và reuse giữa các forward pass,
So that giảm allocation overhead.

**Acceptance Criteria:**
**Given** 1000 forward pass liên tiếp.
**When** apply pattern.
**Then** tracemalloc allocation giảm ≥ 50%.
**And** không có memory growth (leak check).

### Track 3E — End-to-End Verification

#### Story 3E.1: MPS Forward Pass < 30ms Gate

As a Kỹ sư AI,
I want gated benchmark: reject bất kỳ commit nào p95 forward pass > 30ms,
So that NFR1 subcomponent budget được bảo vệ.

**Acceptance Criteria:**
**Given** benchmark suite 3A.2 + optimizations Track 3B/3C/3D.
**When** chạy CI.
**Then** p95 ≤ 30ms trên reference machine (spec ghi trong `metrics/reference_machine.md`).
**And** fail build nếu vượt.

#### Story 3E.2: Regression Suite

As a SRE,
I want lock kết quả tối ưu vào `metrics/optimized.md` + tag `mps-optimized-v1`,
So that future PR không regress.

**Acceptance Criteria:**
**Given** tối ưu xong.
**When** publish.
**Then** file có bảng so sánh baseline vs optimized (latency, memory, accuracy).
**And** CI check compare mọi PR với `mps-optimized-v1`.

---

## Epic 4: Risk Calibration & System Isolation

**Phân loại:** `[RESEARCH]` 4R.1-4R.4 (architecture & latency design), 4.1, 4.2 (calibration/validation) · `[BUILD]` 4.3, 4.4 (engineering thuần). Architecture design (4R.*) nên chốt sớm vì ràng buộc mọi perf gate; calibration phải chốt tham số trước khi Epic 6 demo Success Signal.

### Story 4R.1: End-to-End Latency Budget `[RESEARCH]`

As a Kiến trúc sư Hệ thống,
I want phân bổ NFR1 (<50ms) thành budget cho từng stage (WS recv → decode → ring buffer → graph build → tensor → MPS forward → payload → webhook),
So that mỗi Epic có ngân sách latency rõ ràng thay vì tối ưu mù.

**Acceptance Criteria:**
**Given** các pipeline stage.
**When** chia budget.
**Then** publish `research/latency_budget.md` với bảng (stage, budget ms, căn cứ) tổng ≤ 50ms + buffer dự phòng.
**And** budget này thành target cho các gate 3E.1, 5.3, 6.1.

### Story 4R.2: IPC Mechanism Spike `[RESEARCH]`

As a Kiến trúc sư Hệ thống,
I want spike so sánh SharedMemory vs Queue vs Pipe cho main↔engine, đo overhead serialize tensor/graph,
So that Story 4.3 (Multiprocessing Wrapper) chọn cơ chế đúng.

**Acceptance Criteria:**
**Given** payload đại diện (graph snapshot + tensor).
**When** benchmark 3 cơ chế.
**Then** publish `research/ipc_decision.md` với số đo overhead + khuyến nghị.
**And** khớp latency budget 4R.1 (IPC không ăn quá phần đã cấp).

### Story 4R.3: Failure Mode & Recovery Analysis `[RESEARCH]`

As a Kiến trúc sư Hệ thống,
I want FMEA cho các sự cố: WS đứt, engine crash, queue overflow, data malformed, webhook timeout,
So that hành vi kỳ vọng được định nghĩa trước khi code, không vá chắp vá.

**Acceptance Criteria:**
**Given** kiến trúc pipeline.
**When** liệt kê failure mode.
**Then** publish `research/failure_modes.md`: mỗi mode có (nguyên nhân, phát hiện, hành vi kỳ vọng, recovery).
**And** map mỗi mode tới story build chịu trách nhiệm (VD 1A.3 reconnect, 4.4 backpressure).

### Story 4R.4: System Data-Flow Diagram `[RESEARCH]`

As a Kiến trúc sư Hệ thống,
I want sơ đồ data-flow chi tiết toàn pipeline với kiểu dữ liệu tại mỗi ranh giới,
So that cả team có 1 bức tranh chung trước khi code.

**Acceptance Criteria:**
**Given** các story Epic 0-6.
**When** vẽ luồng.
**Then** publish `docs/data_flow.md` với diagram (mermaid) + kiểu dữ liệu mỗi cạnh (TickDataEvent, GraphSnapshot, tensor, FragilityPayload).
**And** đánh dấu ranh giới process (asyncio main vs engine process).

### Story 4.1: LUNA/UST Fragility Calibration `[RESEARCH]`

As a Quản lý Rủi ro,
I want tune tham số Sigmoid/Min-Max để LUNA fixture chạy qua model bắn RED trong khoảng [10, 30] phút trước liquidation đầu tiên,
So that Success Signal đạt được.

**Acceptance Criteria:**
**Given** fixture `luna_2022_05_09.csv`.
**When** replay 100x qua pipeline.
**Then** RED signal xuất hiện ≥ 10 phút trước timestamp liquidation ground truth.
**And** false positive trên `normal_2023_03_15.csv` < 5%.

### Story 4.2: FTX Cross-validation `[RESEARCH]`

As a Quản lý Rủi ro,
I want áp cùng tham số cho FTX fixture không tune lại,
So that verify không overfit.

**Acceptance Criteria:**
**Given** `ftx_2022_11_08.csv`.
**When** replay.
**Then** RED signal ≥ 10 phút trước liquidation.
**And** báo cáo `calibration/ftx_validation.md`.

### Story 4.3: Multiprocessing Wrapper

As a Kiến trúc sư Hệ thống,
I want bọc engine vào `multiprocessing.Process`, communicate qua `SharedMemory` + `Queue`,
So that CPU-bound không treo asyncio loop.

**Acceptance Criteria:**
**Given** engine hoàn thiện.
**When** khởi động.
**Then** PID engine khác main, main event loop response < 5ms trong khi engine đang chạy.
**And** clean shutdown, không zombie process.

### Story 4.4: Backpressure & Circuit Breaker

As a Kiến trúc sư Hệ thống,
I want engine drop frame cũ nếu queue > threshold,
So that latency không tăng vô hạn khi ingestion nhanh hơn engine.

**Acceptance Criteria:**
**Given** ingestion 500 events/s, engine chỉ xử lý 100 events/s.
**When** chạy 60s.
**Then** metric `engine_frames_dropped_total` tăng, latency p99 vẫn < 60ms.
**And** log INFO đợt drop.

---

## Epic 5: Alert System & API

### Story 5.1: FastAPI Subscribe / Unsubscribe

As a Quỹ Market Maker,
I want POST `/subscribe {url}` và DELETE `/unsubscribe {url}`,
So that đăng ký webhook.

**Acceptance Criteria:**
**Given** FastAPI running.
**When** POST url hợp lệ.
**Then** lưu vào registry (in-memory + JSON persistence).
**And** DELETE gỡ khỏi registry.

### Story 5.2: JSON Payload Formatter

As a Hệ thống,
I want format Fragility Index thành payload khớp schema 0.3,
So that emitter dùng ngay.

**Acceptance Criteria:**
**Given** Fragility 92.
**When** format.
**Then** payload có `alert_level: "RED"`, `fragility_score: 92`, timestamp ISO 8601 UTC.
**And** contract test 0.3 pass.

### Story 5.3: Async Webhook Emitter

As a Hệ thống,
I want `aiohttp` bắn parallel tới toàn bộ subscriber, retry 1 lần nếu fail,
So that không blocking.

**Acceptance Criteria:**
**Given** 10 subscriber (5 healthy, 5 timeout).
**When** emit.
**Then** healthy nhận trong < 50ms, timeout retry 1 lần rồi log ERROR.
**And** không làm treo emit tiếp theo.

### Story 5.4: API Authentication (Enterprise Key)

As a Quỹ Market Maker,
I want header `X-API-Key` verify để bảo vệ subscribe endpoint,
So that không ai đăng ký lạm dụng.

**Acceptance Criteria:**
**Given** whitelist API keys trong `.env`.
**When** POST không có key.
**Then** 401.
**And** key hợp lệ được rate-limit 100 req/min.

---

## Epic 6: End-to-End Verification & NFR Audit

### Story 6.1: End-to-End Latency Benchmark (NFR1)

As a SRE,
I want script `python -m tests.e2e_latency` đo p50/p95/p99 từ block-mới → webhook sent,
So that NFR1 được prove.

**Acceptance Criteria:**
**Given** mock WSS + mock subscriber echo server.
**When** chạy 10k block.
**Then** p95 < 50ms, p99 < 80ms.
**And** báo cáo `benchmarks/e2e_latency.md`.

### Story 6.2: No-GPU Runtime Verify (NFR5)

As a SRE,
I want test verify `torch.cuda.is_available() == False` không ảnh hưởng pipeline,
So that Local-first CPU được prove.

**Acceptance Criteria:**
**Given** environment CPU-only.
**When** chạy toàn bộ E2E.
**Then** không có exception, kết quả trùng khớp (tolerance 1e-6) với GPU case.
**And** CI matrix bao gồm 1 job CPU-only.

### Story 6.3: Success Signal Proof

As a PM,
I want E2E demo chạy LUNA + FTX fixture cuối cùng bắn RED trước 10 phút,
So that ship sản phẩm được.

**Acceptance Criteria:**
**Given** pipeline production-like.
**When** replay `luna_2022_05_09.csv` và `ftx_2022_11_08.csv`.
**Then** cả hai đều fire RED ≥ 10 phút trước liquidation timestamp.
**And** báo cáo `demo/success_signal_proof.md` + video screencast.

---

## Parallelization Guide

Sau khi Epic 0 xong (~1 tuần với 2 dev), 6 track có thể chạy song song:

| Track | Owner Role | Depends on Epic 0 stories | Parallel with |
| --- | --- | --- | --- |
| 1A (Realtime WS) | Data Engineer 1 | 0.1, 0.5 | 1B, 1C, 1D, 2*, 3*, 5* |
| 1B (Event Decoding) | Data Engineer 2 | 0.1 | 1A, 1C, 1D, 2*, 3*, 5* |
| 1C (Ring Buffer) | Data Engineer 3 | 0.1 | 1A, 1B, 1D, 2*, 3*, 5* |
| 1D (CSV Historical) | Data Engineer 4 | 0.1, 0.4 | 1A, 1B, 1C, 2*, 3*, 5* |
| 2A (Graph) | AI Engineer 1 | 0.1, 0.2 | 2B, 3*, 5* |
| 2B (Tensor Map) | AI Engineer 2 | 0.2 | 2A, 3*, 5* |
| 2C (Validation) | Quants | 0.2 | 2A, 2B (dùng mock trước) |
| 3A (Baseline) | AI Engineer 3 | 0.2 | 3B, 3C, 3D, 5* |
| 3B (Bond Dim) | AI Engineer 4 | 0.2 | 3A, 3C, 3D, 5* |
| 3C (SVD) | AI Engineer 5 | 0.2 | 3A, 3B, 3D, 5* |
| 3D (Kernel) | AI Engineer 6 | 0.2 | 3A, 3B, 3C, 5* |
| 5A (API/Emitter) | Backend Engineer | 0.3 | tất cả track khác |

Epic 4 gate sau Epic 3E xong. Epic 6 gate sau Epic 4 + Epic 5 xong.

**Kết quả:** Từ **max 2 dev song song → 10-12 dev/agent song song**.

### Research / Build Split (Epic 2, 3, 4)

Trong các epic research-nặng, tách rõ 2 luồng chạy song song: **Researcher** cày `[RESEARCH]` để chốt decision, **Engineer** cày `[BUILD]` (dùng mock/decision tạm cho tới khi có decision thật).

| Story | Loại | Decision output (file) | Build phụ thuộc decision |
| --- | --- | --- | --- |
| 2A.4 Edge Weight Formula | `[RESEARCH]` | công thức weight `f()` chốt trong design/PR note | 2A.3 Graph Builder (áp công thức) |
| 2B.3 Normalization Layer | `[RESEARCH→BUILD]` | scheme minmax/zscore chốt trong story | 3A.1 (input tensor ổn định) |
| 2C.3 Reference Comparison | `[RESEARCH]` | `references/luna_comparison.md` | (gate chất lượng biểu diễn, không block code) |
| 3A.4 Baseline Metrics | `[RESEARCH]` | `metrics/baseline.md` + tag `baseline-v0` | mọi story tối ưu 3B/3C/3D |
| 3B.1–3B.3 Bond Dim R&D | `[RESEARCH]` | `bond_dim` tối ưu → `tune_pareto` report | 3A.1 / 3C.3 (dùng bond_dim đã chốt) |
| 3C.3 Recompression | `[RESEARCH→BUILD]` | rank/energy threshold chốt trong story | 3E.1 gate <30ms |
| 4.1 LUNA Calibration | `[RESEARCH]` | tham số Sigmoid/MinMax → `calibration/*.md` | 4.2, 6.3 Success Signal proof |
| 4.2 FTX Cross-val | `[RESEARCH]` | `calibration/ftx_validation.md` | 6.3 Success Signal proof |

**Thứ tự khuyến nghị:** chạy `[RESEARCH]` nền tảng trước (3A.4 baseline → 3B bond_dim; 2A.4 formula; 4.1 calibration) để mở khoá `[BUILD]` phụ thuộc. Các `[BUILD]` độc lập (2A.1-2A.3, 2B.1-2B.2, 2B.4, 2C.1-2C.2, 3A.1-3A.3, 3C.1-3C.2/3C.4, 3D.*, 3E.*, 4.3, 4.4) vẫn start ngay sau Epic 0 bằng mock, không chờ research.

### Pre-Code Research Backlog (làm TRƯỚC khi code — bức tranh chi tiết)

12 story non-code mới (v3.1) dựng blueprint trước khi implement. Ưu tiên P0 = chặn code, phải xong trước.

| Story | Domain | Artifact output | Ưu tiên |
| --- | --- | --- | --- |
| 3R.1 MPS Fragility Math Spec | Math model | `research/mps_fragility_model.md` (+ oracle 3-node) | **P0** — chặn toàn bộ Epic 3 |
| 3R.2 Literature Review | Math model | `research/literature_review.md` | P1 |
| 3R.3 Naive Baseline Detector | Math model | `research/baseline_detector.md` | P1 |
| 2R.1 Node Feature Catalog | Data/feature | `research/feature_catalog.md` | **P0** — chặn 2B.2 |
| 2R.2 Graph Topology Design | Data/feature | `research/graph_topology.md` | **P0** — chặn tensor shape 2B.* |
| 1R.1 Data Source Assessment | Data/feature | `research/data_sources.md` | P1 — chặn 1A (nguồn thật) |
| 1R.2 Schema ↔ ABI Reconciliation | Data/feature | `research/schema_abi_gap.md` | **P0** — chặn decoder 1B |
| 1R.3 Ground-Truth Labeling | Data/feature | `research/ground_truth_labeling.md` | P1 — chặn Epic 4 verify |
| 4R.1 Latency Budget | Architecture | `research/latency_budget.md` | **P0** — chặn mọi perf gate |
| 4R.2 IPC Mechanism Spike | Architecture | `research/ipc_decision.md` | P1 — chặn 4.3 |
| 4R.3 Failure Mode Analysis | Architecture | `research/failure_modes.md` | P1 |
| 4R.4 Data-Flow Diagram | Architecture | `docs/data_flow.md` | P1 |

**Khuyến nghị:** chạy 5 story **P0** (3R.1, 2R.1, 2R.2, 1R.2, 4R.1) như 1 "sprint research" ngay sau Epic 0, trước khi mở các track code phụ thuộc. Các P1 chạy song song, không chặn nhánh code độc lập.
