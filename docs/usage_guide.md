# QuantumRadar — Usage Guide

Basic guide to set up, run, and test the ingestion pipeline locally. New to the
repo? Start here.

## 1. Prerequisites

- **Python 3.11+** (`python3 --version`)
- **git**
- No GPU required — the project is local-first CPU.

## 2. Clone

```bash
git clone <repo-url> quantumradar
cd quantumradar
```

## 3. Set up environment variables

```bash
cp .env.example .env
```

Then open `.env` and fill in your keys. For **local dev / CI you can skip real
keys** and use the mock WebSocket (see step 5) — set `WSS_URL=ws://localhost:8546`.

For real mainnet keys (Alchemy/Infura/Etherscan) and where to get them, see
[environment_setup.md](environment_setup.md).

> `.env` is git-ignored — never commit it. Only `.env.example` is committed.

## 4. Install dependencies

Use a virtualenv, then install the package in editable mode with dev extras:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

This installs runtime deps (web3, jsonschema, numpy, pyyaml, requests,
prometheus-client, aiohttp, websockets) plus dev deps (pytest, matplotlib).

## 5. Run

### Option A — Realtime pipeline against the mock WebSocket (no keys needed)

Start the mock WSS server (replays a historical fixture as live blocks):

```bash
python3 -m tools.mock_wss --scenario luna --speed asap
# serves ws://localhost:8546, health check on :8547
```

In a second terminal, run the pipeline against it:

```bash
python3 -m ingestion.pipeline --source mock
# Ctrl-C for graceful shutdown
```

`--scenario` accepts `luna`, `ftx`, or `normal`. Prometheus metrics are exposed
on `--metrics-port` (default 9090): `curl http://127.0.0.1:9090/metrics`.

### Option B — Historical backtest replay (no server, no keys)

```bash
python3 -m ingestion.pipeline --source backtest --scenario luna --speed 100x
```

`--speed` accepts `1x`, `100x`, or `asap` (backtest only; ignored for `--source mock`).

### Option C — Realtime against real mainnet

Fill a real `WSS_URL` in `.env` (see [environment_setup.md](environment_setup.md)),
then:

```bash
python3 -m ingestion.pipeline --source mock --wss-url "$WSS_URL"
```

## 6. Run tests

```bash
python3 -m pytest              # full suite
python3 -m pytest tests/unit   # unit tests only
python3 -m pytest -k router    # match by keyword
```

Tests use `asyncio_mode=auto` (configured in `pyproject.toml`), so async tests
need no extra decorators.

## 7. Project layout

| Path | What it holds |
| --- | --- |
| `ingestion/` | Realtime WS client, decoders, CSV loader, pipeline orchestrator |
| `core/` | Ring buffer implementations |
| `tools/` | Mock WSS server, fixture extraction, reconciliation, profiling |
| `contracts/` | JSON schemas (tick-data, graph, fragility payload) |
| `fixtures/backtest/` | Historical LUNA/FTX/normal datasets (`.csv.gz`) |
| `tests/` | Unit + integration tests |
| `docs/` | This guide, environment setup, git workflow |

## 8. Contributing

See [git_workflow.md](git_workflow.md) for branch/commit conventions and
[../CONTRIBUTING.md](../CONTRIBUTING.md) for the contribution checklist.
