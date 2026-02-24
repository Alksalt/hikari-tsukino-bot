# AGENTS.md

> Repository instructions for AI coding agents (Codex/Copilot/Claude/Cursor/Gemini/etc.).
> Keep this file short and actionable. Put deep SOPs in `directives/` and link them here.

## Quick start (UV-only; do not use pip)

**Package manager:** `uv` (required).  
**Rule:** never use `pip install ...` in this repo.

- Install deps (recommended):
  - `uv sync`
- Run a Python command:
  - `uv run python -m <module>`
- Run tests:
  - `uv run pytest`
- Lint/format (examples; match repo tooling):
  - `uv run ruff check .`
  - `uv run ruff format .`

**Virtual env policy:** let `uv` manage it. Don’t create/manual-activate venvs unless the repo explicitly requires it.

**Env vars:** copy `.env.example` → `.env` (never commit secrets).

If any command is missing, search the repo for `pyproject.toml`, `uv.lock`, `Makefile`, or `README.md` and update this block.

---

## What “done” means (definition of done)

A change is complete only if:
1) It solves the stated task (no partials).
2) It includes tests or updates existing tests where appropriate.
3) It passes the repo’s test + lint/format commands (or explains precisely why it can’t).
4) It does not introduce new warnings, failing checks, or secret leaks.
5) It includes a short summary + how to verify.

---

## Workflow contract (how to work in this repo)

1) **Plan first (brief)**
   - Restate the goal and constraints.
   - Identify files to inspect/change.
   - Choose the smallest viable diff.

2) **Prefer existing tools/scripts**
   - Before creating anything new, check `execution/` (or repo tooling) for an existing script.
   - Only add new scripts if none exist and it clearly reduces repeated manual work.

3) **Implement → test → iterate (“self-anneal”)**
   - Read error output carefully.
   - Fix the cause, re-run the smallest relevant test, then re-run the full test/lint step if feasible.
   - If a fix would spend paid tokens/credits or touch production credentials, stop and ask for approval.

4) **Update docs/SOPs when you learn**
   - If you discover a recurring pitfall, add it to the relevant file under `directives/`.
   - Do not overwrite existing directives unless explicitly asked.

---

## Repo layout (expected; adjust if different)

- `directives/` — Markdown SOPs (the instruction set). Agents should follow them when present.
- `execution/` — Deterministic scripts/tools (preferred for repeated operations).
- `inputs/` — Raw user-provided data/files.
- `outputs/` — Deliverables (generated artifacts meant to be used externally).
- `.tmp/` — Scratch space (never commit).
- `.env` — Local secrets/config (never commit).

If the repo is a monorepo, subdirectories may contain their own `AGENTS.md` files.
**Rule:** closer `AGENTS.md` overrides/extends the root for that subtree.

---

## Coding standards (defaults)

- Make the smallest change that solves the problem.
- Prefer clarity over cleverness.
- Keep functions small; name things explicitly.
- Avoid large refactors unless requested or necessary.
- Add/adjust tests alongside behavior changes.
- Keep formatting consistent with the repo tools.
- Don’t change public APIs without updating docs and tests.

### Safety / security

- Never print, log, or commit secrets.
- Don’t add new network calls, telemetry, or background jobs without explicit requirement.
- Be careful with destructive commands (`rm -rf`, migrations, prod deletes). Require confirmation.

---

## Communication (what to output after changes)

When you finish a task, include:
- Summary of what changed (bullet list)
- Files touched
- Commands run (tests/lint) + results
- How the user can verify locally

---

## Project-specific SOPs (entry points)

If applicable, follow these SOPs:
- `directives/<TASK>.md` — task-specific workflows
- Any `directives/*` referenced by the user request

If an SOP conflicts with this file, the SOP wins for that task.