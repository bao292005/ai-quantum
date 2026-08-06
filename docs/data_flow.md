# Story 4R.4 — System Data-Flow Diagram `[RESEARCH]`

Date: 2026-08-06 · Refs: `research/decision_b0_v1_detector.md`, `research/latency_budget.md`

End-to-end data flow for the **v1 (B0)** pipeline, with the data type at every
boundary. Unlike the original MPS design, v1 runs **single-process async** — there
is no separate engine process (NFR3 was motivated by the CPU-bound MPS core, which
is parked; see the decision record).

## v1 (B0) flow

```mermaid
flowchart TD
    WSS[("Ethereum WSS / CSV fixture")]
    subgraph proc["asyncio process (single, v1)"]
        A["ingestion: streams / csv_loader\nraw log dict"]
        B["Track 1B router + decoders\nTickDataEvent (schema 0.1, 11 fields)"]
        C["Track 1C ring buffer\nlist[TickDataEvent] (~10 blocks)"]
        D["engine.baseline.borrow_activity\nint (borrow count / window)"]
        E["score map (Epic 5)\nfragility_score float [0,100]"]
        F["payload formatter (5.2)\nFragilityAlert dict (schema 0.3)"]
        G["aiohttp emitter (5.3)\nHTTP POST"]
    end
    SUB[("Webhook subscribers")]

    WSS -->|"newHeads + logs"| A
    A -->|"raw log dict"| B
    B -->|"TickDataEvent"| C
    C -->|"windowed events"| D
    D -->|"borrow rate"| E
    E -->|"score ≥90 RED / ≥70 YELLOW"| F
    F -->|"JSON payload"| G
    G -->|"POST {timestamp, fragility_score,\nalert_level, trigger_protocols}"| SUB
```

## Boundary data contracts

| Edge | Type | Contract |
|---|---|---|
| WSS → ingest | raw log / block header | web3 `AttributeDict` / CSV row |
| decode → buffer | `TickDataEvent` | `contracts/tick_data.schema.json` (11 fields) |
| buffer → B0 | `list[TickDataEvent]` | last ~10 blocks (NFR4) |
| B0 → score | `int` (borrow count) | `engine.baseline.borrow_activity` |
| score → payload | `float` `fragility_score` ∈ [0,100] | `calibration/luna_calibration.md` mapping |
| payload → emitter | `FragilityAlert` | `contracts/fragility_alert.schema.json` (timestamp, fragility_score, alert_level, trigger_protocols) |
| emitter → subscriber | HTTP POST JSON | webhook body = FragilityAlert |

## Parked MPS path (for reference)

If MPS is ever un-parked, insert between "ring buffer" and "detector":
`build_graph → GraphSnapshot → adjacency_tensor + feature_tensor → normalize(minmax)
→ fragility_raw → score`, and move that block to a **separate process** (NFR3) with
SharedMemory/Queue IPC (4R.2) — none of which v1 needs.
