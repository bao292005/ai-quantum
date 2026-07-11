# Git Workflow

Two parts: a **Git basics** cheat sheet for everyday use, and the **project
conventions** we follow in this repo.

---

## Part 1 — Git basics

### One-time setup

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

### Everyday commands

```bash
git status                 # what changed / staged
git diff                   # unstaged changes
git diff --staged          # staged changes
git add <file>             # stage a specific file (prefer over `git add .`)
git commit -m "feat: ..."  # commit staged changes
git pull                   # fetch + merge remote changes into current branch
git push                   # publish your commits
git log --oneline -15      # recent history, compact
```

### Branching

```bash
git switch -c feat/my-feature   # create + switch to a new branch
git switch main                 # switch back to main
git branch                      # list local branches
```

### Keeping a branch up to date

```bash
git switch feat/my-feature
git fetch origin
git merge origin/main           # simple: brings main into your branch
# or, for a linear history:
git rebase origin/main          # replays your commits on top of main
```

Use **merge** if unsure — it is the safest. Use **rebase** only on branches you
have not shared yet (rebasing rewrites commit history).

### Resolving a conflict

When merge/rebase reports a conflict:

1. `git status` lists the conflicted files.
2. Open each file; conflict markers look like:
   ```
   <<<<<<< HEAD
   your version
   =======
   their version
   >>>>>>> origin/main
   ```
3. Edit to the correct result, delete the markers.
4. `git add <file>` for each resolved file.
5. Finish: `git commit` (merge) or `git rebase --continue` (rebase).
   Bail out any time with `git merge --abort` / `git rebase --abort`.

---

## Part 2 — Project conventions

### Branch naming

| Prefix | Use for |
| --- | --- |
| `feat/` | new feature or story implementation |
| `fix/` | bug fix |
| `chore/` | tooling, deps, docs, config, tracker updates |

Example: `feat/1b-uniswap-decoder`, `fix/ring-buffer-overflow`.

Do not commit directly to `main` — open a pull request.

### Commit messages — Conventional Commits

This repo already uses [Conventional Commits](https://www.conventionalcommits.org/).
Format:

```
<type>(<optional scope>): <short summary in imperative>
```

Types used here: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.

Real examples from this repo's history:

```
feat: implement core ingestion pipeline with ring buffers, message decoders...
chore(tracker): sync Excel with v3.1 epics + add Roadmap sheet
docs(epics): add research/build split + 12 non-code pre-code stories
```

Keep the summary under ~72 chars; add a body after a blank line if you need to
explain *why*.

### Pull request flow

1. Branch off `main`: `git switch -c feat/my-story`.
2. Commit in small, focused steps.
3. Push: `git push -u origin feat/my-story`.
4. Open a PR against `main`. Describe what changed and why; link the story
   (e.g. `E.5`).
5. Ensure `python3 -m pytest` passes (CI runs `ruff check` + tests).
6. Merge after review. Delete the branch.

### Secrets — never commit

- `.env` is git-ignored (verify: `git check-ignore .env`).
- Never paste API keys into commits, docs, or PR descriptions.
- If a key leaks, **revoke/regenerate it** — removing it in a later commit is
  not enough (it stays in history).

See [../CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution checklist.
