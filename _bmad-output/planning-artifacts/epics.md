---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - "_bmad-output/briefs/brief-mps-defi-risk-20260703/brief.md"
  - "_bmad-output/specs/spec-mps-defi-risk/SPEC.md"
  - "_bmad-output/architecture/architecture-mps-defi-risk/ARCHITECTURE-SPINE.md"
  - "_bmad-output/architecture/architecture-mps-defi-risk/PRESENTATION.md"
  - "_bmad-output/planning-artifacts/implementation-readiness-report-2026-07-05.md"
competition: "AI-Quantum Challenge 2026 — HVTC"
registration_deadline: "2026-07-30"
prototype_deadline: "2026-10-10"
semifinal: "2026-10-25"
final: "2026-11-10"
---

# QuantumRadar - Epic Breakdown (Competition Edition)

## Overview

This document provides the complete epic and story breakdown for QuantumRadar, covering both product development and all competition submission requirements for the AI-Quantum Challenge 2026 (HVTC). Competition deadline: registration by 30/07/2026, prototype by 10/10/2026.

## Requirements Inventory

### Functional Requirements

FR1: Real-time WebSocket data ingestion — ETH L1 via WSS eth_subscribe (Alchemy/Infura), continuous block-by-block streaming.
FR2: Historical CSV data replay — backtest playback of LUNA/FTX/normal fixture files at configurable speed.
FR3: Event filtering and decoding — Uniswap V3 (Swap, Mint, Burn) and Aave V3 (Borrow, Supply, Withdraw, LiquidationCall) from contract whitelist.
FR4: MPS risk engine — Bond Dimension compression of liquidity graph → Entanglement calculation → Fragility Index 0-100%.
FR5: Webhook alert system — YELLOW (≥70%) and RED (≥90%) alerts with fixed JSON payload (timestamp, fragility_score, alert_level, trigger_protocols).
FR6: Backtest success signal — system fires RED alert ≥10 minutes before LUNA/FTX liquidation cascade in historical replay.
FR7: Demo dashboard — Streamlit app showing real-time Fragility Index, alert timeline, protocol graph for judges and stakeholders.
FR8: Competition registration package — team information, project description, data sources declaration per HVTC requirements.
FR9: Technical/academic report — methodology, architecture, backtest results, mathematical foundation (MPS theory).
FR10: Presentation slides — semi-final deck (25/10) and final pitch deck (10/11) covering problem, solution, demo, market.
FR11: Demo video and prototype submission package — recorded walkthrough + deployable prototype for 10/10 deadline.

### Non-Functional Requirements

NFR1: E2E latency < 50ms (new block received → webhook fired).
NFR2: Async I/O throughout — asyncio for all network operations; MPS engine on separate CPU process.
NFR3: CPU-only runtime — no GPU dependency; runs on standard server (AWS t3.large or local machine).
NFR4: Ring buffer in-memory — 10 most recent blocks in RAM via collections.deque or static numpy array; no disk write during real-time.
NFR5: False positive rate < 5% in backtest across LUNA, FTX, and normal market periods.
NFR6: OpEx < $100/month for 10 clients (free-tier RPC + CPU-only compute).
NFR7: HARD DEADLINE — competition registration closes 30/07/2026.

### Additional Requirements

- Stack: Python 3.11+, PyTorch 2.1+, Web3.py 6.11+, FastAPI 0.104+, Uvicorn 0.23+, Streamlit (dashboard).
- Naming: snake_case Python files/functions, PascalCase classes, ISO 8601 UTC timestamps.
- Logging: JSON stdout for all services (compatible with Datadog/ELK).
- Package structure: ingestion/, engine/, emitter/, core/; Streamlit dashboard in dashboard/.
- Contracts already done (Epic 0): tick_data.schema.json, graph_snapshot.schema.json, fragility_alert.schema.json, fixture CSVs, mock WSS.

### UX Design Requirements

N/A — API-only product. Demo dashboard (FR7) uses Streamlit for rapid prototype visualization; no formal UX spec required.

### FR Coverage Map

FR1: Epic 1 — WebSocket ingestion pipeline
FR2: Epic 1 — CSV historical replay
FR3: Epic 1 — Event decoding and filtering
FR4: Epic 2 — MPS tensor engine
FR5: Epic 3 — FastAPI alert system and webhook
FR6: Epic 2 (calibration) + Epic 4 (demo proof) + Epic 6 (final verification)
FR7: Epic 4 — Streamlit demo dashboard
FR8: Epic 5 — Competition registration (URGENT)
FR9: Epic 5 — Technical report
FR10: Epic 5 — Presentation slides
FR11: Epic 4 (demo scenario) + Epic 5 (video + package)

## Epic List

### Epic 0: Contracts & Test Fixtures
Foundation contracts (JSON schemas) and historical backtest fixtures enabling all downstream epics to work with mock data.
**Status: DONE ✅**
**FRs covered:** Foundation for FR1, FR2, FR3, FR5

### Epic R: Research Foundation `[RESEARCH]`
Team produces decision documents on MPS mathematics and DeFi domain analysis that ground the algorithm implementation and the academic technical report.
**FRs covered:** Enables FR4 (math spec → Epic 2), FR6 (ground truth → Epic 6), FR9 (academic citations → Epic 5)
**Must complete before:** Epic 2 (math), Epic 5 Story 5.2 (report)

### Epic 1: Live Data Pipeline
Engineers can stream real-time Ethereum events via WebSocket and replay historical fixture data through a unified normalized pipeline into the ring buffer — feeding the MPS engine.
**FRs covered:** FR1, FR2, FR3

### Epic 2: MPS Risk Engine
The system computes a live Fragility Index from on-chain event data using Matrix Product State tensor compression, calibrated and validated against LUNA/FTX historical events.
**FRs covered:** FR4, FR6 (partial)

### Epic 3: Alert API
Clients can subscribe to QuantumRadar risk alerts and receive real-time YELLOW/RED webhook notifications with a fixed JSON payload via a FastAPI service.
**FRs covered:** FR5

### Epic 4: Competition Demo
Judges and stakeholders can witness a live demonstration of QuantumRadar detecting the LUNA/FTX crisis through a Streamlit dashboard and automated replay scenario.
**FRs covered:** FR6 (proof), FR7, FR11 (partial)

### Epic 5: Competition Submission ⚠️ URGENT
Team successfully submits all required materials to AI-Quantum Challenge 2026 (HVTC) — from initial registration through final presentation.
**FRs covered:** FR8, FR9, FR10, FR11
**HARD DEADLINE: Story 5.1 by 30/07/2026**

### Epic 6: E2E Verification & NFR Audit
The complete system is verified end-to-end to meet all performance (latency, accuracy, cost) and competition judging requirements.
**FRs covered:** FR6 (final proof), NFR1–NFR6

---

## Epic 0: Contracts & Test Fixtures

DONE — see existing implementation artifacts.

---

## Epic R: Research Foundation `[RESEARCH]`

Team produces decision documents on MPS mathematics and DeFi domain analysis, grounding the algorithm implementation in theory and providing the academic foundation for the competition technical report.

### Story R.1: MPS Mathematical Specification

As an AI Engineer,
I want a precise mathematical specification of how tick-data maps to MPS tensors and how Bond Dimension compression produces a Fragility Index,
So that Epic 2 implementation is mathematically correct from the start and the competition report has a rigorous theoretical foundation.

**Acceptance Criteria:**

**Given** literature on Matrix Product State tensor networks and the SPEC CAP-2 capability.
**When** the math spec is written.
**Then** `research/mps_math_spec.md` exists and defines: (1) the liquidity graph → tensor mapping (nodes, edges → matrix dimensions), (2) Bond Dimension R and its role in compression, (3) the Entanglement entropy formula used as Fragility proxy, (4) how Fragility Index 0-100% is derived from entanglement values.
**And** includes worked numerical example with small mock graph (≥3 nodes) showing each step of the computation.
**And** specifies recommended hyperparameter ranges: bond dimension R ∈ [2, 8], SVD truncation threshold, normalization approach.
**And** cites ≥2 academic references (MPS in physics or tensor networks in ML).

### Story R.2: Graph Topology & Node Feature Design

As an AI Engineer,
I want a validated design document defining what nodes, edges, and feature vectors the liquidity graph uses,
So that Epic 2 Story 2.1 (Graph Constructor) implements the correct structure without rework.

**Acceptance Criteria:**

**Given** DeFi protocol event types (Uniswap V3 Swap/Mint/Burn, Aave V3 Borrow/Supply/Withdraw/LiquidationCall).
**When** the graph design document is written.
**Then** `research/graph_design.md` defines: node types (e.g. liquidity pool, lending reserve, stablecoin), edge types (e.g. fund flow, collateral link, liquidity dependency) with directionality.
**And** defines node feature vector: which numeric fields from tick-data become features (e.g. liquidity_delta, volume_24h, utilization_rate, liquidation_count) with normalization strategy.
**And** defines edge weight formula (e.g. volume-weighted flow between pool pairs over last N blocks).
**And** validates design against existing fixture data — spot-checks that at least 5 LUNA-period events produce a non-trivial graph (≥3 nodes, ≥2 edges).

### Story R.3: LUNA/FTX Ground Truth & Cascade Timeline

As a Calibration Engineer,
I want a thoroughly researched ground-truth document pinning exact cascade timestamps for LUNA/UST and FTX on Ethereum mainnet,
So that the 10-minute early warning Success Signal claim is objectively verifiable with block-level evidence.

**Acceptance Criteria:**

**Given** `fixtures/backtest/README.md` (existing ground truth) and on-chain data sources (Etherscan, Nansen/Chainalysis reports).
**When** the ground-truth document is written.
**Then** `research/ground_truth_labeling.md` defines cascade criterion for each event (e.g. "≥3 LiquidationCall events within same block, or total liquidated USD > $X in 1h").
**And** documents for LUNA: `cascade_start` block + UTC datetime, `red_deadline` = cascade_start − 10 min (~50 blocks), with ≥1 Etherscan tx citation.
**And** documents for FTX: same fields, using Ethereum mainnet on-chain events only (NOT Solana bankruptcy announcement — must be Alameda collateral dump or Aave V2 liquidation event).
**And** reconciles with fixtures/backtest/README.md — confirms or corrects existing timestamps, explains any discrepancy.
**And** explains in 1 paragraph why normal_2023_03_15 is a valid negative control (no cascade events in block range).

### Story R.4: DeFi Contagion Analysis & Literature Foundation

As a Technical Writer,
I want a DeFi contagion analysis document synthesizing why MPS/quantum-inspired methods are the right tool for systemic DeFi risk,
So that the competition technical report has strong academic grounding and judges can follow the reasoning from problem to solution.

**Acceptance Criteria:**

**Given** LUNA/FTX event history and academic literature on tensor networks and systemic financial risk.
**When** the analysis document is written.
**Then** `research/defi_contagion_analysis.md` covers: (1) why DeFi composability creates contagion faster than TradFi (with LUNA/FTX as case studies), (2) why price-based models fail (correlation breakdown during crisis), (3) why graph entanglement captures structural fragility that price models miss.
**And** includes literature review section: ≥3 papers on (a) tensor networks / MPS in ML or finance, (b) systemic risk in financial networks, (c) DeFi-specific risk analysis.
**And** provides a "Quantum Angle" section explaining how MPS is quantum-inspired (not claiming quantum hardware) — suitable for HVTC judges evaluating the quantum computing category.
**And** all citations formatted consistently (APA or IEEE style).

---

## Epic 1: Live Data Pipeline

Engineers can stream real-time Ethereum events via WebSocket and replay historical fixture data through a unified normalized pipeline into the ring buffer — feeding the MPS engine.

### Story 1.1: WebSocket Ingestion Client

As a Data Engineer,
I want a resilient WebSocket client that connects to Ethereum nodes, subscribes to newHeads and log events, and auto-reconnects with exponential backoff,
So that the pipeline always stays live regardless of network instability.

**Acceptance Criteria:**

**Given** WSS_URL configured in environment.
**When** `python -m ingestion.run` starts.
**Then** client connects to Alchemy/Infura WSS, subscribes to newHeads, and streams block headers.
**And** on disconnection, retries with delays 0.5→1→2→4→8→16→30s (capped), logs each attempt as structured JSON.
**And** raises ConfigError if WSS_URL is missing.
**And** `ingestion/config.py`, `ingestion/client.py`, `ingestion/reconnect.py`, `ingestion/streams.py` are implemented with unit + integration tests against mock WSS (ws://localhost:8546).

### Story 1.2: Event Decoder & Router

As a Data Engineer,
I want decoded, normalized tick-data events from Uniswap V3 and Aave V3 logs routed into a unified stream,
So that the MPS engine consumes a single normalized format regardless of protocol source.

**Acceptance Criteria:**

**Given** raw eth_subscription log events from WSS.
**When** the decoder receives a log matching the contract whitelist.
**Then** Uniswap V3 Swap/Mint/Burn and Aave V3 Borrow/Supply/Withdraw/LiquidationCall are decoded using correct ABI and topic0.
**And** each event is normalized to tick_data.schema.json format.
**And** events from unknown contracts are silently dropped (not raising errors).
**And** `ingestion/decoders.py`, `ingestion/router.py` implemented with unit tests covering all 7 event types.

### Story 1.3: Ring Buffer & CSV Historical Loader

As a Data Engineer,
I want a ring buffer storing the 10 most recent blocks in RAM and a CSV loader that replays fixture files at adjustable speed,
So that the MPS engine can consume both real-time and historical data through the same interface.

**Acceptance Criteria:**

**Given** normalized tick-data events arriving from the router.
**When** events are written to the ring buffer.
**Then** buffer holds exactly the last N blocks in memory (deque or numpy array), with O(1) write and read.
**And** `python -m ingestion.csv_loader --file luna_2022_05_09.csv.gz --speed 100x` replays the fixture into the ring buffer at 100x speed.
**And** `core/ring_buffer.py`, `ingestion/csv_loader.py` implemented with unit tests verifying buffer eviction and CSV replay timing.

---

## Epic 2: MPS Risk Engine

The system computes a live Fragility Index from on-chain event data using Matrix Product State tensor compression, calibrated and validated against LUNA/FTX historical events.

### Story 2.1: Graph Constructor & Tensor Representation

As an AI Engineer,
I want a graph builder that converts ring buffer tick-data into a PyTorch tensor representation (node features + adjacency),
So that the MPS algorithm has a numerical input it can compress.

**Acceptance Criteria:**

**Given** a ring buffer snapshot of 10 blocks.
**When** `GraphBuilder.build(snapshot)` is called.
**Then** returns a GraphSnapshot conforming to graph_snapshot.schema.json with nodes (protocol pools) and edges (fund flows with weights).
**And** node features are tensorized: liquidity depth, volume delta, borrow rate per pool.
**And** adjacency tensor and node feature tensor are PyTorch float32 with correct shape.
**And** `engine/graph_builder.py`, `engine/tensor_map.py` implemented with invariant tests.

### Story 2.2: MPS Algorithm Core

As an AI Engineer,
I want the MPS tensor contraction algorithm that computes Bond Dimension entanglement and outputs a Fragility Index,
So that the system has the core mathematical capability to detect systemic risk.

**Acceptance Criteria:**

**Given** node feature tensor and adjacency tensor from Story 2.1.
**When** `MPSEngine.compute(graph_tensor)` is called.
**Then** returns `fragility_score` float in [0.0, 100.0].
**And** SVD truncation with configurable bond dimension reduces computation by ≥80% vs naive contraction.
**And** engine runs on CPU without GPU — torch device is always "cpu".
**And** single inference latency (without I/O) < 30ms on standard hardware.
**And** `engine/mps_core.py`, `engine/svd_truncation.py` implemented with benchmark harness and regression tests.

### Story 2.3: Risk Calibration (LUNA / FTX)

As a Calibration Engineer,
I want the MPS engine calibrated on LUNA/UST and FTX historical fixtures so that fragility thresholds (YELLOW=70, RED=90) are empirically grounded,
So that the Success Signal claim is verifiable and defensible to competition judges.

**Acceptance Criteria:**

**Given** `fixtures/backtest/luna_2022_05_09.csv.gz` and `ftx_2022_11_08.csv.gz`.
**When** backtest replay drives the MPS engine through the full event sequence.
**Then** Fragility Index crosses RED (90%) ≥10 minutes before cascade_start timestamp in fixtures/backtest/README.md for both LUNA and FTX.
**And** on `normal_2023_03_15.csv.gz`, Fragility Index never crosses YELLOW (70%) — false positive guard.
**And** MPS engine runs in a separate multiprocessing.Process, communicating with asyncio pipeline via Queue.
**And** `engine/calibration.py`, `engine/multiprocess_wrapper.py` implemented; calibration results logged as JSON.

---

## Epic 3: Alert API

Clients can subscribe to QuantumRadar risk alerts and receive real-time YELLOW/RED webhook notifications with a fixed JSON payload via a FastAPI service.

### Story 3.1: FastAPI Alert System & Webhook Emitter

As a Market Maker (client),
I want to subscribe my webhook URL to QuantumRadar and automatically receive RED/YELLOW alerts when Fragility Index crosses thresholds,
So that my trading bot can act on systemic risk signals without manual monitoring.

**Acceptance Criteria:**

**Given** a running QuantumRadar FastAPI service.
**When** client POSTs to `/subscribe` with `{"url": "https://bot.example.com/hook", "min_level": "RED"}`.
**Then** client is registered and receives POST webhooks when Fragility Index ≥ 90%.
**And** webhook payload conforms to `contracts/fragility_alert.schema.json` (timestamp, fragility_score, alert_level, trigger_protocols).
**And** E2E: from fragility threshold crossed → webhook delivered < 50ms.
**And** `emitter/fastapi_app.py`, `emitter/webhook_emitter.py` implemented; API has basic token authentication; contract tests validate payload schema.

---

## Epic 4: Competition Demo

Judges and stakeholders can witness a live demonstration of QuantumRadar detecting the LUNA/FTX crisis through a Streamlit dashboard and automated replay scenario.

### Story 4.1: Streamlit Risk Dashboard

As a Competition Judge / Stakeholder,
I want a visual dashboard showing the Fragility Index over time, active alerts, and protocol contribution breakdown,
So that I can understand QuantumRadar's value without reading code.

**Acceptance Criteria:**

**Given** `streamlit run dashboard/app.py`.
**When** dashboard loads.
**Then** displays: real-time Fragility Index gauge (0-100%), alert timeline (YELLOW/RED events with timestamps), protocol breakdown bar chart (which protocols contributed most to fragility).
**And** dashboard connects to QuantumRadar API (or reads from replay log) — updates every 2 seconds.
**And** includes QuantumRadar branding, clean layout suitable for screen recording.
**And** `dashboard/app.py` implemented using Streamlit; runs without additional API keys in demo mode (uses fixture replay).

### Story 4.2: Demo Scenario Runner & Success Signal Visualization

As a Competition Judge,
I want to run a one-command demo that replays the LUNA/FTX crisis and shows exactly when QuantumRadar fired the RED alert vs when the cascade happened,
So that the 10-minute early warning claim is visually proved.

**Acceptance Criteria:**

**Given** `python -m tools.demo_run --scenario luna`.
**When** the demo runs end-to-end.
**Then** replays luna_2022_05_09.csv.gz at 100x speed, drives MPS engine, displays Fragility Index rising in Streamlit dashboard.
**And** at RED alert moment, dashboard highlights "⚠️ RED ALERT fired at 21:04:48 UTC" and "Cascade occurred at 21:14:48 UTC — 10 min AFTER our alert".
**And** generates `demo_output/luna_proof.png` — a chart of Fragility Index timeline with RED alert marker and cascade marker annotated.
**And** demo completes in < 2 minutes real time; `tools/demo_run.py` implemented.

---

## Epic 5: Competition Submission

Team successfully submits all required materials to AI-Quantum Challenge 2026 (HVTC) — from initial registration through final presentation.

### Story 5.1: Team Registration & Initial Application ⚠️ DEADLINE 30/07/2026

As a Team Leader,
I want to complete and submit the official registration package to AI-Quantum Challenge 2026 before the 30/07/2026 deadline,
So that the team is officially entered in the competition and eligible for all subsequent rounds.

**Acceptance Criteria:**

**Given** HVTC competition requirements at ai-quantum.hvtc.edu.vn.
**When** registration is submitted.
**Then** completed: phiếu đăng ký (team form), danh sách thành viên (3-5 người), mô tả ý tưởng (QuantumRadar brief), nguồn dữ liệu dự kiến (Etherscan/Alchemy).
**And** project positioned under "Quản trị rủi ro" + "Quantum computing" categories.
**And** confirmation email received from HVTC before 30/07/2026.
**And** all registration documents saved to `competition/registration/`.

### Story 5.2: Technical Report & Academic Documentation

As a Technical Writer,
I want a comprehensive technical report documenting QuantumRadar's methodology, architecture, and backtest results,
So that competition judges can evaluate the scientific and technical depth of the solution.

**Acceptance Criteria:**

**Given** completed Epics 1-4 with working prototype.
**When** technical report is written.
**Then** report covers: Problem Statement, MPS mathematical foundation (Bond Dimension, Entanglement formalism), System Architecture (Pipes & Filters, AD-1 to AD-5), Backtest Results (LUNA/FTX with graphs), NFR compliance (latency, cost, accuracy).
**And** includes `research/ground_truth_labeling.md` ground truth methodology as appendix.
**And** minimum 15 pages, proper academic citations for MPS theory.
**And** saved to `competition/technical_report.pdf` (or .md rendered to PDF).

### Story 5.3: Pitch Deck & Presentation

As a Team Presenter,
I want polished pitch decks for the semi-final (25/10) and final (10/11) rounds,
So that the team communicates QuantumRadar's value, technical innovation, and market opportunity convincingly to judges.

**Acceptance Criteria:**

**Given** competition judging criteria (innovation, practical value, technical quality, presentation).
**When** pitch deck is prepared.
**Then** semi-final deck (≤15 slides) covers: Hook story (LUNA/FTX losses), Problem, Solution (MPS + quantum angle), Live Demo link, Architecture overview, Backtest proof, Market size, Team.
**And** final deck adds: competitive differentiation, business model, roadmap to v2.
**And** both decks use consistent QuantumRadar branding from PRESENTATION.md.
**And** saved to `competition/slides_semifinal.pdf` and `competition/slides_final.pdf`.

### Story 5.4: Demo Video & Final Submission Package

As a Team Leader,
I want a recorded demo video and a complete submission package ready for the 10/10/2026 prototype deadline,
So that the team can submit a polished, complete entry that maximizes judging score.

**Acceptance Criteria:**

**Given** working prototype from Epics 1-4 and dashboard from Epic 4.
**When** demo video is recorded.
**Then** 3-5 minute screen recording shows: start mock WSS, run LUNA scenario, dashboard shows Fragility rising, RED alert fires 10 min before cascade — all in real time.
**And** video includes voice-over narration explaining each step in Vietnamese.
**And** submission package contains: demo video, technical report, runnable Docker image (`docker-compose up`), README with 3-step quick start.
**And** all materials saved to `competition/submission_package/` and backed up to cloud storage.

---

## Epic 6: E2E Verification & NFR Audit

The complete system is verified end-to-end to meet all performance, accuracy, and cost requirements — providing evidence for competition judging.

### Story 6.1: E2E Latency Benchmark & Success Signal Proof

As a QA Engineer,
I want automated end-to-end tests that measure block-to-webhook latency and prove the 10-minute early warning on LUNA/FTX,
So that NFR1 (< 50ms) and the core Success Signal claim are verifiable with numbers, not just claims.

**Acceptance Criteria:**

**Given** complete system running with mock WSS at speed=asap.
**When** E2E latency benchmark runs (`pytest tests/e2e/test_latency.py`).
**Then** p95 latency from new block received → webhook fired < 50ms (measured over 1000 blocks).
**And** LUNA backtest: RED alert fired at block before (cascade_start − 10 min) — asserted programmatically.
**And** FTX backtest: same assertion.
**And** normal_2023_03_15: zero RED alerts fired.
**And** benchmark results saved as `tests/e2e/results/benchmark_report.json`.

### Story 6.2: No-GPU Runtime & NFR Audit Report

As a DevOps Engineer,
I want a verified audit confirming QuantumRadar runs fully on CPU with no GPU dependency and estimated OpEx < $100/month,
So that the "Local-First, zero-cost" claim in the competition pitch is backed by evidence.

**Acceptance Criteria:**

**Given** full system running in Docker (`docker-compose up`).
**When** NFR audit runs.
**Then** `torch.cuda.is_available()` returns False at runtime — system explicitly sets device="cpu" everywhere.
**And** memory profile: peak RAM usage < 2GB during LUNA full replay.
**And** OpEx estimate document: Alchemy free tier compute units, CPU server cost → total < $100/month for 10 webhook clients.
**And** audit report saved to `competition/nfr_audit.md`.
