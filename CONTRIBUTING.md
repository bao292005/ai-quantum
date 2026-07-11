# Contributing to QuantumRadar

Thanks for contributing. This is the short checklist; the detailed guides live in
`docs/`.

## Get started

- **Setup & run:** [docs/usage_guide.md](docs/usage_guide.md)
- **Environment / API keys:** [docs/environment_setup.md](docs/environment_setup.md)
- **Git conventions:** [docs/git_workflow.md](docs/git_workflow.md)

## Before you open a PR

1. **Branch** off `main`: `feat/…`, `fix/…`, or `chore/…`.
2. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/):
   `feat: …`, `fix: …`, `chore(scope): …`.
3. **Test** — `python3 -m pytest` passes with no regressions.
4. **Lint** — CI runs `ruff check`; keep it clean (ruff is not required locally).
5. **No secrets** — never commit `.env` or API keys. Verify with
   `git check-ignore .env`. If a key leaks, revoke and regenerate it.
6. **Docs** — update the relevant `docs/` file if behavior or commands change.

## Story-driven work

This project follows the BMad workflow. Stories live in
`_bmad-output/implementation-artifacts/` and status is tracked in
`_bmad-output/sprint-status.yaml`. Reference the story key (e.g. `E.5`) in your
branch name and PR description.
