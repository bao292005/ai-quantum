# QuantumRadar

> DeFi systemic-risk detection API powered by **Matrix Product State (MPS) tensor
> networks**. QuantumRadar ingests Uniswap V3 / Aave events, models the on-chain
> liquidity graph as tensors, computes a **Fragility Index (0–100%)** via tensor
> contraction, and fires **webhook alerts** (Yellow ≥ 70%, Red ≥ 90%) before a
> liquidation cascade unfolds.

**Success signal:** replaying the LUNA/UST (2022-05) or FTX (2022-11) collapse
must fire a **RED alert ≥ 10 minutes before** the first on-chain liquidation
cascade.

---

## Table of contents

- [Concept](#concept)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Project status](#project-status)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Running the pipeline](#running-the-pipeline)
- [Data contracts](#data-contracts)
- [Repository layout](#repository-layout)
- [Testing](#testing)
- [Tooling](#tooling)
- [Docker](#docker)
- [Documentation](#documentation)
- [Development workflow](#development-workflow)

---

## Concept

Traditional risk metrics (LTV, utilization, simple leverage) look at protocols in
isolation. QuantumRadar instead treats the DeFi market as an **entangled quantum
many-body system**: pools, tokens, and lending markets are nodes in a graph whose
edges carry liquidity-flow / borrow / shared-collateral coupling.

By encoding this graph as an adjacency tensor + node-feature tensor and running an
**MPS / tensor-train decomposition**, the system measures the **entanglement
entropy** of the network. Rising entanglement = tightly-coupled positions that can
unwind together = **systemic fragility**. That entropy is mapped to a single
Fragility Index scalar and thresholded into alert levels.

**Design constraints (NFRs):**

| NFR | Constraint |
| --- | --- |
| NFR1 | End-to-end latency (new block → webhook) **< 50 ms** |
| NFR2 | Async I/O throughout (`asyncio`) |
| NFR3 | PyTorch core runs in a **separate process** (CPU-bound isolation) |
| NFR4 | In-memory **ring buffer of ~10 blocks**, no runtime disk I/O |
| NFR5 | **Local-first, CPU-only** — no GPU required |

---

## How it works

```
  On-chain events                Graph model               Tensor core            Alerting
 ┌────────────────┐   decode   ┌──────────────┐  build   ┌───────────────┐  MPS ┌──────────────┐
 │ Uniswap V3     │──────────▶ │ TickDataEvent│────────▶ │ GraphSnapshot │────▶ │ Fragility    │
 │ Aave V2 / V3   │  whitelist │ (normalized) │  events  │ nodes + edges │      │ Index 0–100% │
 │ WSS / CSV      │   router   └──────────────┘          └───────┬───────┘      └──────┬───────┘
 └────────────────┘                                              │ tensorize          │ ≥70% / ≥90%
                                                         ┌───────▼───────┐      ┌──────▼───────┐
                                                         │ (A, X) tensors│      │ Webhook      │
                                                         │ adjacency +   │      │ YELLOW / RED │
                                                         │ features      │      └──────────────┘
                                                         └───────────────┘
```

1. **Ingest** — realtime `newHeads` + logs over Web3 WebSocket, or historical
   CSV replay of past collapses.
2. **Decode** — raw logs → normalized `TickDataEvent` (Uniswap V3 Swap/Mint/Burn,
   Aave Supply/Borrow/Withdraw/Liquidation), filtered by a contract whitelist.
3. **Buffer** — events land in an async-safe ring buffer (last ~10 blocks).
4. **Graph** — events are folded into a `GraphSnapshot` (protocol/pool/token nodes;
   liquidity-flow / borrow-position / shared-collateral edges).
5. **Tensorize** — the graph becomes an adjacency tensor `(N, N)` and a node
   feature tensor `(N, F=5)`, normalized for the MPS engine.
6. **Score** *(Epic 3, upcoming)* — MPS contraction → entanglement entropy →
   Fragility Index.
7. **Alert** *(Epic 5, upcoming)* — FastAPI subscription + async webhook emitter
   fires YELLOW/RED payloads.

---

## Architecture

| Layer | Package | Responsibility |
| --- | --- | --- |
| **Ingestion** | `ingestion/` | WSS client, reconnection, decoders, whitelist, router, CSV loader, pipeline orchestrator, metrics |
| **State** | `core/` | Ring buffer protocol + deque / numpy / asyncio-safe implementations, JSON schema validators |
| **Engine** | `engine/graph/`, `engine/tensor/` | Graph node/edge models, NetworkX graph builder, adjacency & feature tensors, normalization, sparse variant |
| **Contracts** | `contracts/` | JSON Schemas (Draft 2020-12) for tick-data, graph snapshot, fragility payload |
| **Tooling** | `tools/` | Mock WSS server, fixture extraction, Etherscan reconciliation, data-quality profiling, graph visualization |

**Stack:** Python 3.11+ · PyTorch 2.1+ (CPU) · web3.py 7.x · NetworkX 3+ ·
Pydantic 2+ · NumPy · jsonschema · prometheus-client · aiohttp / websockets.

---

## Project status

QuantumRadar is under active development, planned through the **BMad** epic/story
workflow (`_bmad-output/epics.md`, `_bmad-output/sprint-status.yaml`).

| Epic | Scope | Status |
| --- | --- | --- |
| **0 — Contracts & Fixtures** | JSON schemas, backtest fixtures, mock WSS | ✅ done |
| **E — Environment Provisioning** | Credentials, whitelist, webhook config, docs | 🟡 partial (docs in review) |
| **1 — Data Ingestion** | Realtime WS, decoders, ring buffer, CSV replay, pipeline | ✅ done (review) |
| **2 — Tensor Graph Modeling** | Graph builder, adjacency/feature tensors, normalize, sparse | 🟡 in review |
| **3 — MPS Algorithm** | Baseline contraction, bond-dim R&D, SVD truncation, <30 ms gate | ⬜ backlog |
| **4 — Risk Calibration & Isolation** | LUNA/FTX calibration, multiprocessing, backpressure | ⬜ backlog |
| **5 — Alert System & API** | FastAPI subscribe, payload formatter, webhook emitter | ⬜ backlog |
| **6 — E2E Verification & NFR Audit** | Latency benchmark, no-GPU verify, success-signal proof | ⬜ backlog |

**Working today:** end-to-end data ingestion (mock realtime + historical replay),
graph construction, and tensor mapping with a full unit/integration test suite.
The MPS scoring engine and alert emitter are the next milestones.

---

## Requirements

- **Python 3.11+** (`python3 --version`)
- **git**
- No GPU required — everything runs CPU-only.

---

## Quick start

```bash
# 1. Clone
git clone <repo-url> quantumradar
cd quantumradar

# 2. Environment variables (mock mode needs no real keys)
cp .env.example .env
#   For local/CI, set: WSS_URL=ws://localhost:8546

# 3. Install (editable + dev extras)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 4. Run tests to verify the setup
python3 -m pytest
```

For real mainnet keys (Alchemy / Infura / Etherscan) and where to obtain them,
see [docs/environment_setup.md](docs/environment_setup.md).

> `.env` is git-ignored — never commit real credentials. Only `.env.example`
> is committed.

---

## Running the pipeline

### Option A — Realtime pipeline against the mock WebSocket (no keys)

The mock server replays a historical fixture as if it were live blocks, speaking
the real `eth_subscribe` protocol so no Alchemy/Infura key is needed.

```bash
# Terminal 1 — mock WSS (ws://localhost:8546, health on :8547)
python3 -m tools.mock_wss --scenario luna --speed asap

# Terminal 2 — pipeline
python3 -m ingestion.pipeline --source mock
#   Ctrl-C for graceful shutdown
```

`--scenario` accepts `luna`, `ftx`, or `normal`. Prometheus metrics are exposed
on `--metrics-port` (default 9090):

```bash
curl http://127.0.0.1:9090/metrics
```

### Option B — Historical backtest replay (no server, no keys)

```bash
python3 -m ingestion.pipeline --source backtest --scenario luna --speed 100x
```

`--speed` accepts `1x`, `100x`, or `asap` (backtest only; ignored for `--source mock`).

### Option C — Realtime against real mainnet

Fill a real `WSS_URL` in `.env`, then:

```bash
python3 -m ingestion.pipeline --source mock --wss-url "$WSS_URL"
```

---

## Data contracts

All cross-boundary data conforms to JSON Schema (Draft 2020-12) under
`contracts/`. Schemas are the shared contract that let epics build in parallel
against mocks.

| Schema | Purpose |
| --- | --- |
| `tick_data.schema.json` | Normalized on-chain event (11 required fields: `block_number`, `block_timestamp`, `protocol`, `event_type`, `pool_address`, `token0/1`, `amount0/1`, `tx_hash`, `log_index`) |
| `graph_snapshot.schema.json` | `GraphSnapshot` = `snapshot_id` + `block_range` + `nodes[]` (id, type, features) + `edges[]` (src, dst, weight, edge_type) |
| `fragility_alert.schema.json` | Webhook payload = `timestamp` (ISO 8601 UTC), `fragility_score` (0–100), `alert_level` (YELLOW\|RED), `trigger_protocols[]` |

**Node features (F=5, fixed order):** `tvl_usd`, `volume_24h_usd`, `price_usd`,
`volatility`, `connectivity`.

**Node types:** `protocol`, `pool`, `token`.
**Edge types:** `liquidity_flow`, `borrow_position`, `shared_collateral`.

Validators live in `core/schemas/` (`validate_tick`, `validate_graph_snapshot`,
`validate_alert_payload`).

---

## Repository layout

```
quantumradar/
├── ingestion/            # Data ingestion (Epic 1)
│   ├── config.py         #   .env loader → IngestionConfig
│   ├── client.py         #   EthereumClient (AsyncWeb3 WebSocket wrapper)
│   ├── reconnect.py      #   exponential-backoff auto-reconnect
│   ├── streams.py        #   newHeads / logs subscription generators
│   ├── metrics.py        #   Prometheus metrics + stall watchdog
│   ├── decoders/         #   uniswap_v3.py, aave_v3.py → TickDataEvent
│   ├── whitelist.py      #   contract whitelist (YAML-backed)
│   ├── router.py         #   raw log → whitelist → decoder → event
│   ├── csv_loader.py     #   historical CSV stream + ReplayDriver
│   └── pipeline.py       #   orchestrator (python -m ingestion.pipeline)
├── core/                 # Shared state (Epic 1C + Epic 0)
│   ├── ring_buffer.py    #   RingBuffer protocol + deque/numpy/async impls
│   └── schemas/          #   JSON schema loaders & validators
├── engine/               # Graph → Tensor modeling (Epic 2)
│   ├── graph/            #   node_types, edge_types, builder (NetworkX)
│   └── tensor/           #   adjacency, features, normalize, sparse
├── contracts/            # JSON Schemas (Draft 2020-12) + examples
├── tools/                # CLI utilities
│   ├── mock_wss/         #   mock Ethereum WebSocket server (Story 0.5/0.6)
│   ├── visualize.py      #   adjacency heatmap + feature bar chart
│   ├── reconcile_etherscan.py
│   ├── profile_quality.py
│   └── extract_fixtures.py / verify_fixtures.py
├── fixtures/backtest/    # LUNA / FTX / normal datasets (.csv.gz)
├── tests/                # unit/ + integration/ + fixtures/
├── docs/                 # usage guide, environment setup, git workflow, visualization
├── research/             # design decisions (feature catalog, topology, edge weight, ...)
├── references/           # e.g. luna_comparison.md
├── design-artifacts/     # product brief, trigger map, UX, dev artifacts
├── _bmad-output/         # epics.md, sprint-status.yaml, story artifacts
├── Dockerfile            # mock WSS image
├── docker-compose.yml    # mock WSS service
└── pyproject.toml        # package + deps + pytest config
```

---

## Testing

```bash
python3 -m pytest              # full suite (unit + integration)
python3 -m pytest tests/unit   # unit tests only
python3 -m pytest -k router    # match by keyword
```

- `asyncio_mode=auto` (in `pyproject.toml`) — async tests need no extra decorators.
- Integration tests self-host a `MockWssServer` on an ephemeral port; they do not
  depend on an externally running `:8546`.
- The linter is **ruff** (`ruff check`), run in CI.

---

## Tooling

| Command | What it does |
| --- | --- |
| `python3 -m tools.mock_wss --scenario luna --speed asap` | Replay a fixture as a live Ethereum WSS server (`:8546`, health `:8547`) |
| `python3 -m ingestion.pipeline --source mock` | Run the realtime ingestion pipeline |
| `python3 -m ingestion.pipeline --source backtest --scenario ftx --speed 100x` | Historical backtest replay |
| `python3 -m tools.visualize --input snapshot.json --out graph.png [--legend]` | Render adjacency heatmap + node-feature bar chart (+ JSON legend) |
| `python3 -m tools.reconcile_etherscan` | Cross-check buffered blocks against the Etherscan API |
| `python3 -m tools.profile_quality` | Data-quality profiling report |

Fixtures cover three scenarios in `fixtures/backtest/`:
`luna_2022_05_09`, `ftx_2022_11_08`, `normal_2023_03_15` (gzip CSV, 11-field
schema, pre-sorted by block).

---

## Docker

A container image is provided for the **mock WSS server** (useful for CI or
developing downstream consumers without a mainnet key):

```bash
docker compose up --build
#   ws://localhost:8546  (eth_subscribe)
#   http://localhost:8547/health
```

---

## Documentation

- [Usage guide](docs/usage_guide.md) — install & run, step by step
- [Environment setup](docs/environment_setup.md) — API keys & credentials
- [Visualization](docs/visualization.md) — interpreting the heatmap output
- [Git workflow](docs/git_workflow.md) — branch/commit conventions
- [Contributing](CONTRIBUTING.md) — contribution checklist
- [Epic breakdown](_bmad-output/epics.md) — full requirements & story map
- **Research / design decisions** in `research/`:
  `feature_catalog.md`, `graph_topology.md`, `edge_weight_formula.md`,
  `schema_abi_gap.md`, `data_sources.md`, `ground_truth_labeling.md`

---

## Development workflow

The project is planned via the **BMad** method: epics and atomic stories live in
`_bmad-output/`, with `[RESEARCH]` stories (decisions/reports) unblocking
`[BUILD]` stories (production code). Commit messages follow Conventional Commits
(`feat:`, `fix:`, `chore:`). See [docs/git_workflow.md](docs/git_workflow.md) and
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

Proprietary — © QuantumRadar Team.
```