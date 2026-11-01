# Thetis build progress

Autonomous overnight build of `SPEC.md`. Newest phase last. The "Good morning" summary goes at the
top when the run ends.

## Working notes (read me first after a context reset)

- Product name is **Thetis** (the starter pack said "Hatchery Autopilot"; renamed in docs and code).
- Work happens on git branch `build/mvp`. `main` holds only the starter pack. Nothing is pushed.
- Never open `.env`. Debug images only under `data/` (gitignored).
- Use absolute paths in shell commands: the shell's working directory can drift between calls.
- Screenshot helper: `cd frontend && node scripts/shot.mjs <path> ../data/shots/x.png <w> <h> [--full]`.

## Phase 0: scaffold

**Built:** starter pack moved to the repo root, git repo with `.env` and `fixtures/real/` ignored,
`backend/` (uv, Python 3.12, FastAPI, health route, `config.py` with every parameter, test
`conftest.py` that blanks the key and uses a temp data folder), `frontend/` (Vite, React, strict
TypeScript, Tailwind v4 with the design tokens, Router, TanStack Query, Geist fonts, Recharts,
lucide, Playwright), root scripts exactly as in SPEC §2, and the app shell (sidebar, panel, header).

**Tests:** 1 passed (`test_health`). `npm run dev` serves the shell at :5173 and `/api/health` is ok
through the Vite proxy. No console errors, no horizontal overflow at 1440 px or 390 px.

**Decisions:**
- `HATCHERY_DATA_DIR` is now `THETIS_DATA_DIR` and the database is `data/thetis.db`.
- Git: starter pack is the first commit on `main`; all build work is on branch `build/mvp`.
- Root `.env.example` from before the pack was replaced by the pack's version, as SETUP.md says.
  Your `.env` was not touched. It may still hold lines from the old example (for example
  `CLAUDE_MODEL=claude-opus-5-5`); the app will use whatever model it says.

**Still open:** nothing.
