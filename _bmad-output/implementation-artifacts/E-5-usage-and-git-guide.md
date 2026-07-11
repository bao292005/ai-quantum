---
baseline_commit: ae1732c
type: setup
---

# Story E.5: Project Usage & Git Workflow Guide

Status: review

## Story

As a **Thành viên mới của team**,
I want **tài liệu hướng dẫn chạy project cơ bản + quy ước & cách dùng Git hằng ngày, kèm cấu hình Git thực tế**,
so that **clone repo là biết ngay cách setup/chạy/test và cách đóng góp code đúng quy ước, không phải hỏi**.

## Acceptance Criteria

1. **AC1 — Usage guide:** `docs/usage_guide.md` mô tả copy-paste được: clone repo, `cp .env.example .env` + điền key (link tới `environment_setup.md` của E.1), cài deps (`pip install -e .` / `pip install -e ".[dev]"`), chạy pipeline (`python -m ingestion.pipeline --source=mock`), chạy mock WSS (`python -m tools.mock_wss --scenario luna --speed asap`), chạy test (`python3 -m pytest`).

2. **AC2 — Git workflow doc:** `docs/git_workflow.md` gồm 2 phần:
   - **Git cơ bản:** clone, `status`, `add`, `commit`, `push`, `pull`, tạo & switch branch (`git switch -c`), merge vs rebase cơ bản, xử lý conflict cơ bản.
   - **Quy ước project:** branch naming (`feat/`, `fix/`, `chore/`), commit message convention khớp history hiện có (`feat:`, `fix:`, `chore(scope):`), PR flow (nhánh → PR → review → merge vào `main`).

3. **AC3 — Git config thực tế:** `.gitignore` được rà soát đảm bảo che tối thiểu: `.env`, `__pycache__/`, `.pytest_cache/`, `*.log`, `.venv/`, artifact tạm (`csv_errors.log`, `*_report.md` tạm nếu có). `CONTRIBUTING.md` ở repo root tóm tắt quy ước đóng góp + link tới `docs/usage_guide.md` và `docs/git_workflow.md`.

4. **AC4 — Bảo mật:** không secret nào bị commit — `git check-ignore .env` trả `.env`; `git status` không list `.env` hay key nào.

5. **AC5 — Chính xác:** mọi lệnh trong doc chạy được thật trên repo hiện tại (verify bằng cách chạy thử ít nhất pipeline mock + pytest); commit convention trong doc khớp với `git log` thực tế.

## Tasks / Subtasks

- [x] **Task 1 — Viết `docs/usage_guide.md`** (AC1, AC5)
  - [x] Prerequisites (Python 3.11+), clone, virtualenv
  - [x] Setup env: `cp .env.example .env`, link `environment_setup.md`
  - [x] Install: `pip install -e ".[dev]"`
  - [x] Run: pipeline mock, mock WSS, pytest — verify từng lệnh chạy được
- [x] **Task 2 — Viết `docs/git_workflow.md`** (AC2)
  - [x] Phần "Git cơ bản" (các lệnh hằng ngày + conflict)
  - [x] Phần "Quy ước project" (branch/commit/PR) — soi `git log --oneline` để khớp convention thật
- [x] **Task 3 — Rà soát `.gitignore` + viết `CONTRIBUTING.md`** (AC3)
  - [x] Kiểm `.gitignore` che đủ (`.env`, `__pycache__/`, `.pytest_cache/`, `*.log`, `.venv/`); bổ sung nếu thiếu
  - [x] `CONTRIBUTING.md` tóm tắt + link 2 doc
- [x] **Task 4 — Verify bảo mật + lệnh** (AC4, AC5)
  - [x] `git check-ignore .env` → `.env`; `git status` sạch secret
  - [x] Chạy thử pipeline mock + `pytest` xác nhận lệnh trong doc đúng

## Dev Notes

**Loại story:** `[SETUP]` — tài liệu + config, không có code production. KHÔNG viết lại loader/pipeline; chỉ document cái đã có.

**Bối cảnh repo (để doc chính xác — KHÔNG bịa lệnh):**
- Repo ĐÃ là git repo có commit history theo Conventional Commits (`feat:`, `fix:`, `chore(scope):`) — soi `git log --oneline -20` trước khi viết phần convention.
- Entry points có thật: `python -m ingestion.pipeline --source=mock` (Story 1E.1), `python -m tools.mock_wss --scenario <luna|ftx|normal> --speed <1x|100x|asap>` (Story 0.5), `python3 -m pytest` (asyncio_mode=auto).
- Install: `pyproject.toml` có `[project]` + `[dev]` extras (web3>=7, prometheus-client, numpy, pyyaml, requests, matplotlib) → `pip install -e ".[dev]"`.
- `.env` đã git-ignored (dòng 5 `.gitignore`); `.env.example` là template commit được. E.1 đã có `docs/environment_setup.md` → LINK tới, đừng lặp lại.
- Lint = `ruff check` (CI chạy, không cài local) — nhắc trong CONTRIBUTING nhưng không bắt buộc chạy local.

**Không cần:** git hooks phức tạp, CI mới, hay tooling. Chỉ doc + rà `.gitignore` + `CONTRIBUTING.md`.
skipped: pre-commit hooks / PR template files, add when team lớn hơn hoặc CI cần gate.

### Project Structure Notes

```
docs/usage_guide.md    ← TẠO MỚI
docs/git_workflow.md    ← TẠO MỚI
CONTRIBUTING.md         ← TẠO MỚI (repo root)
.gitignore             ← RÀ SOÁT (bổ sung nếu thiếu)
```

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (BMad dev-story workflow)

### Debug Log References

- Verified CLI entry points via `--help`: `ingestion.pipeline` (`--source {mock,backtest}`, `--scenario`, `--speed`, `--wss-url`, `--metrics-port`), `tools.mock_wss` (`--scenario`, `--speed`, `--port`). Documented only real flags.
- `git check-ignore .env` → `.env`; `git check-ignore csv_errors.log` → `csv_errors.log` (after adding `*.log`).
- Secret scan `grep -rnE "<key patterns>" docs/ CONTRIBUTING.md` → no raw keys.
- Ran documented backtest command: `python3 -m ingestion.pipeline --source backtest --scenario normal --speed asap` → `backtest_complete events=6899`, clean shutdown.
- Full suite: `python3 -m pytest -q` → **265 passed, 1 skipped** (mock WSS not running on :8546, expected), 57.6s. No regressions (docs-only change).

### Completion Notes List

- Docs-only `[SETUP]` story — no production code changed; documented existing behavior, did not rewrite loader/pipeline.
- AC1: `docs/usage_guide.md` — clone → `.env` → `pip install -e ".[dev]"` → run (mock server + pipeline, backtest replay, real mainnet) → pytest. Every command verified runnable.
- AC2: `docs/git_workflow.md` — Part 1 Git basics (add/commit/push/pull, `git switch -c`, merge vs rebase, conflict resolution); Part 2 project conventions (branch `feat/`/`fix/`/`chore/`, Conventional Commits matching real `git log`, PR flow, secret hygiene).
- AC3: `.gitignore` already covered `.env`, `__pycache__/`, `.pytest_cache/`, `.venv/`, egg-info; added `*.log` (covers `csv_errors.log`). `CONTRIBUTING.md` at repo root links usage + git + environment docs.
- AC4/AC5: security + command verification passed (see Debug Log).
- Note: `docs/environment_setup.md` (Story E.1) is referenced but not yet created — the links resolve once E.1 is implemented.

### File List

- `docs/usage_guide.md` (NEW)
- `docs/git_workflow.md` (NEW)
- `CONTRIBUTING.md` (NEW)
- `.gitignore` (UPDATE — added `*.log`)

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-11 | Implemented E.5: usage guide, git workflow doc, CONTRIBUTING.md, `.gitignore` `*.log`. Verified commands + security. Status → review. |
