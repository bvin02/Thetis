# Thetis

A localhost web app for shellfish hatcheries:
- analyze microscope photos of oyster larvae (OpenCV)
- let a tech correct the calls
- save checks to tanks
- flag tanks at risk with explainable rules
- let a manager approve recommended actions

The full spec is `SPEC.md`. Build **one phase at a time** (SPEC §14) and stop at the end of each
phase with a short summary and how to verify it.

## Stack
- `backend/`: Python 3.12 via **uv**, FastAPI, OpenCV, SQLModel on SQLite, anthropic SDK, pytest.
- `frontend/`: Vite + React + TypeScript (strict) + Tailwind v4, React Router, TanStack Query.
- Runs only on localhost. Vite (5173) proxies `/api` to FastAPI (8000). No cloud services, no auth.

## Commands
- `npm run setup`: install everything on a fresh clone (root, frontend, backend)
- `npm run dev`: both servers
- `npm test`: backend tests (`cd backend && uv run pytest -q`)
- `npm run seed` (demo state) / `npm run seed:full` (the designed Floor's state), both with
  `--reset`. Stop `npm run dev` first.
- `npm run slides`: regenerate the synthetic test slides (`tools/gen_slides.py`)
- `cd backend && uv add <pkg>`: add a Python dependency. Never `pip install` into the system.

## Rules
- **Secrets**:
  - Never open, print, copy or commit `.env`.
  - Only `app/services/claude.py` reads `ANTHROPIC_API_KEY`, as a `SecretStr`. Never put it in a
    config object, an API response or the frontend, and never make a `VITE_`-prefixed copy.
  - Tests blank the key in `conftest.py`.
  - Don't log prompts or keys.
- **Time**: use naive local datetimes everywhere; "today" is the local date.
- **Pure core**: `app/analysis` and `app/rules` are pure functions (no DB, no FastAPI, no I/O
  except reading the image they're given) with unit tests. DB and HTTP glue lives in
  `app/services` and `app/api`.
- **Config**:
  - Every threshold and engine parameter lives in `app/config.py` (`DEFAULTS`, `EngineParams`).
    Never hardcode one inside a function.
  - Units go in names: `length_um`, `length_px`, `temp_c`, `do_mgl`, `pct_dead` (0–100).
- **History**: `assess()` may only read checks up to `upto`. Each saved check stores its risk
  snapshot.
- **Tests**:
  - Don't weaken a test to make it pass. Tune parameters, or stop and report the numbers.
  - Engine tuning is time-boxed (SPEC §14).
- **Wording**:
  - Say "pattern matches", never "diagnosis".
  - Label forecasts "Rules-based".
  - Recommendations are approved by a person; nothing acts on equipment.
- **Honesty**:
  - Example rows have `is_example = true` and the UI shows the "Example data" badge.
  - Photos from `fixtures/` show "Synthetic sample".
  - `fixtures/real/` (no license) is for tests only: never shown in the UI and never committed.
  - Write debug images and overlays only under `data/` (gitignored).
- **Claude API**: optional, hidden without a key, cached by input hash, capped by
  `CLAUDE_DAILY_LIMIT`, every call logged with token counts (SPEC §8).

## UI
- Match `design/` exactly:
  - `design/screens/*.png` show what it looks like
  - `design/html/*.html` give the exact CSS
  - `design/README.md` has the tokens and component rules
- Screens that aren't designed reuse the same components.
- No gradients, glows, neon, emoji or illustrations. Status colours are only for problems; Normal
  is grey.
- After building a screen, take a Playwright screenshot at 1440 px wide and compare it with the
  design PNG. Fix the differences before calling the phase done.
- Keyboard and screen-reader basics: a visible focus ring, aria labels on icon buttons, and text
  summaries for charts.
- Check 390 px wide: no horizontal page scroll.

## Git
Commit at the end of each phase with a clear message. `.env` and `fixtures/real/` are gitignored:
keep it that way. A snapshot of `data/` is committed because the owner asked for it, while new files
in it stay ignored. Running or seeding the app shows that snapshot as changed: don't commit the
churn unless asked. The GitHub repo is public, so check before pushing anything new.
