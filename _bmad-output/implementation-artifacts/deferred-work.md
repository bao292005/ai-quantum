# Deferred Work

## Deferred from: code review of story-0.5 (2026-07-05)

- **`_first_sub` one-shot never re-armed** — a client subscribing after the replay finishes gets a silent dead subscription. By-design "replay từ đầu file, không lưu offset"; late-join re-arm is v2. [`tools/mock_wss/server.py`]
- **Unbounded `client.subs` (sub-count DoS)** — no cap on subscriptions per client. Mock/CI tool, not production-exposed. [`tools/mock_wss/server.py`]
- **`_drain_and_close` emptiness-based drain races in-flight send** — drain checks queue-empty, not send-complete. 2s bounded shutdown is acceptable for a mock. [`tools/mock_wss/server.py`]
- **`asyncio.sleep` not interruptible by `_stop` mid-sleep** — a long 1x inter-event gap delays shutdown up to that gap. Only affects 1x manual runs, not CI (asap/100x). [`tools/mock_wss/server.py` — `_replay_loop`]
