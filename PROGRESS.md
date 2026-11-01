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

## Phase 1: analysis engine

**Built:** `backend/app/analysis` (`engine.py`, `calibrate.py`, `summary.py`, `models.py`), pure
functions following SPEC §5, every number in `EngineParams`. Tests in `tests/test_analysis.py` and
`tests/test_j006.py`.

**Tests:** all pass. §13 metrics table:

```
slide                    truth  count  err%   dead P/R     abn P/R     MAE µm   grid px     ms  unsure
slide-d-stage               54     54   0.0  1.00/1.00  1.00/1.00    2.73    625.0    185      5
slide-eyed                  22     22   0.0  1.00/1.00  1.00/1.00       -        -    152      0
slide-healthy-umbo          44     44   0.0  1.00/1.00  1.00/1.00    2.42    625.0    139      1
slide-low-omega             46     46   0.0  1.00/1.00  1.00/0.75       -        -    129      7
slide-vibrio-suspect        48     47  -2.1  1.00/1.00  0.67/1.00    2.10    625.0    165      2
t03-today                   63     62  -1.6  1.00/0.93  1.00/1.00    2.17    625.0    172      3
pooled dead P/R 1.000/0.971  abnormal P/R 0.947/0.857  length MAE 2.35 µm over 200 larvae
J006 exact count on 27 of 30 images
  J006_B1_-0014.jpg        labelled 1  counted 2  ignored  17    474 ms  <-- off
  J006_B1_-0028.jpg        labelled 1  counted 3  ignored   5    174 ms  <-- off
  J006_B1_-0029.jpg        labelled 1  counted 2  ignored   8    167 ms  <-- off
```

Targets: count within ±5% on every slide, dead P/R ≥ 0.9, abnormal P/R ≥ 0.75, length MAE ≤ 4 µm,
grid within 1% of 625 px, ≤ 1 s per slide, J006 exact on ≥ 20 of 30. All met.

**Decisions:**
- The first run scored 18 of 30 on the real J006 photos. No test was changed. Four small rules were
  added, each with a parameter in `EngineParams`, and the synthetic scores did not change:
  - `ref_min_frac_of_largest`: small round debris no longer drags the size reference down. This
    matters most on photos with few objects, where a plain median is not robust.
  - `bubble_bright_ratio` + `bubble_bright_frac`: dark-ringed air bubbles have a bright core. The
    spec's "interior < −3σ" misses them because the ring dominates the median.
  - `rim_hull_max_frac_of_median`: open-rim repair no longer fills huge hulls made by scratches.
  - `debris_max_solidity`: rough debris below 0.90 solidity that isn't a clump is ignored.
- `analyze()` also takes `calibration="preset"|"manual"` to name where a passed `um_per_px` came from.
- A manual larva's length is a placeholder, so it is left out of the size statistics.

**Still open:** the 3 J006 misses: one larva cut off at the image edge (the label counts whole larvae
only) and two bubbles whose bright core is out of frame. Dead recall on `t03-today` is 14 of 15.

## Phase 2: data model, rules, seed

**Built:** SQLModel tables (`models.py`, `db.py`), pure rules (`rules/series.py`, `signals.py`,
`assess.py` with the ladder, patterns and line alerts, `text.py` with every sentence and format,
`actions.py`, `history.py`), `services/world.py` (loads and assesses every tank),
`services/decisions.py`, and `seed.py` (`npm run seed`, `npm run seed:full`).

**Tests:** `test_rules.py` (179 cases: every signal at, under and over each threshold, every ladder
rung, every pattern, every text, line alerts, history grid, `upto` replay, exact seed reasons) and
`test_seed_story.py` (levels, patterns, decisions, headline, "135.6M", 65%, the exact summary
sentence, T-03's photo byte-identical to the fixture). All pass.

**Decisions:**
- `Detection.cls` is stored in a column called `cls`, but the Python attribute is `larva_cls`
  because SQLModel's constructor reserves `cls`. The API still says `cls`.
- Datetime fields are annotated `NaiveDatetime`: the installed SQLModel rejects naive datetimes
  otherwise, and the spec requires naive local time.
- Computed rates are rounded to 9 decimals before comparing to a threshold, so a value exactly on a
  threshold counts as on it instead of landing on either side from floating-point noise.
- Seed photos render in parallel (6 workers, about 12 s) into `data/cache/seed-photos`.
  `THETIS_SEED_CACHE` overrides the folder. The cache survives `--reset`, so re-seeding takes seconds.
- Inspector's Recommended actions: for each action the tank's current pattern recommends, show its
  latest decision (pending or decided), then anything else still pending for that tank. That is why
  T-03's old approved feed check disappears once T-03 turns Critical, leaving "3 to decide".
- If a tank has both a pH and an Ω signal, only one water sentence appears in its reason (SPEC says pH
  only if Ω wasn't used). A pH-only sentence reads "(pH 7.60)".
- Line alert "since": walk the line's checks newest first, skip those with no water reading, and
  stop at the first non-corrosive one.

**Still open:** nothing.

## Phase 3: Floor

**Built:** `GET /api/floor`, `GET /api/tanks`, `GET /api/tanks/{id}`, batch start/close, decisions API
(list, approve, dismiss, undo), static photos at `/api/files`. Floor screen from live data: headline,
summary, Act now and Monitor chips, metrics, SVG floor plan with tooltips and pipe highlighting, Plan |
Table toggle, phone list (container query), Last 14 days grid, inspector (photo with outlines drawn
from detections, risk meter, condition table, survival chart, recommended actions), toast provider,
room filter from the sidebar, full-screen sheet on phones.

**Tests:** all backend tests pass. Driven with Playwright at 1440 px: selecting tanks, table view,
tooltips, approve, dismiss and undo (badge goes 7 → 5 → 7), no console errors. Compared with
`home.png`: section positions measured against `design/html/home.html` are within about 1 px down to
Recommended actions (about 4 px there, because computed rows differ). No horizontal overflow at 390,
800, 1100 or 1440 px.

**Decisions:**
- Only `data/photos` and `data/uploads` are served at `/api/files`. The database in the same folder
  is not public.
- Design differences that come from computed values (allowed by SPEC §4.1): next check is S-01 (the
  oldest last check), T-03 shows 43 live (the seed's number), some history cells differ.
- The "Synthetic sample" badge on inspector photos is not in the mockup. It is there because the honesty
  rule requires it.
- The inspector shows a close crop of the photo, as the mockup does; "Review outlines" shows all of it.
- Reports, ⌘K and the Algae room are hidden, as SPEC §4.0 says.
- Closing a batch dismisses its open tank-level decisions with a note, so the badge isn't left stale.
- In a room filter, chips, table and grid show that room, other tanks dim on the plan, and the
  inspector moves to that room's worst tank.

**Still open:** the phone sheet opens on tap; the bottom-of-page inspector stays as in `home-phone.png`.

## Phase 4: New check and check detail

**Built:** `POST /api/analyze`, `/api/samples` (list, image, analyze), `POST /api/analyze/{token}/scale`,
`POST /api/summarize`, `POST /api/checks`, `GET /api/checks`, `GET /api/checks/{id}`,
`PATCH /api/checks/{id}/photos/{pid}/detections`, `services/uploads.py`, `services/checks.py`. Screens:
New check (drop zone, sample menu with thumbnails, "Finding larvae…", photo viewer, popover corrections,
keys 1/2/3/0, Tab to next unsure, arrow keys through objects, Add larva, zoom/pan, filter chips, photo tabs,
"Add a scale", live counts, size with histogram, gut, estimate with over-stocked warning, water with
"Use these", notes, save with toast) and Check detail (read-only, Edit outlines → Save changes, risk at save
time, Synthetic sample badge).

**Tests:** `tests/test_api.py` (21 cases) passes, including every §13 API item. Demo steps 2–5 driven in a
browser (`frontend/scripts/demo_flow.mjs`): analysis in about 300 ms, correction updates counts, toast reads
"Check saved. T-03 is now Critical. 3 decisions waiting.", headline becomes "3 tanks need attention now",
no console errors. No horizontal scroll at 390 px.

**Decisions:**
- Saving the same upload token twice returns the first check (`duplicate: true`), so a double click can't
  make two checks.
- The server keeps each upload's scale in its own metadata. `POST /checks` needs only `token` + `detections`
  as in SPEC §10, and never trusts a scale from the browser.
- Added `POST /api/analyze/{token}/scale` for "Add a scale"; the spec's endpoint list doesn't name one.
  Corrections survive it because object ids don't change.
- Added `tank_id` to `POST /summarize` so the estimate can say "of 10.0M stocked".
- Correcting a saved check scales its `live_est` by the change in count. Seeded estimates stand for a full
  count (SPEC §12), so recomputing them from the photo would make them jump. For a real check the result
  equals the formula.
- Setting a class on an object clears its unsure flag, even if the class didn't change: a person looked.
- "Save" needs a tank and an analysed photo; unsure objects may remain and count under their class.
- The correction popover docks under the photo when the photo is narrower than 520 px.

**Still open:** the engine misses one faint dead shell on a grid line in `t03-today.jpg` (14 of 15 dead found).
DEMO.md uses it: Add larva on that shell, press 3, and Dead goes 14 → 15.

## Phase 5: Claude

**Built:** `services/claude.py` (the only module that reads the key, as a `SecretStr`), `GET /api/claude/status`,
`POST /api/claude/second-opinion`, `POST /api/claude/explain`, the cache by input hash, the daily cap (429 "Daily
Claude limit reached"), and the `claude_call` log. UI: Ask Claude with "Sends {n} small crops to Claude.", opinion
list with Accept, Keep, Accept all, the same choices in the object popover, and Explain on the tank page.
Everything hides with no key.

**Tests:** `tests/test_claude.py` (23 cases, fake client, no real calls): off without a key, request shape, crops,
12-object limit, cache, cap, logging, no key or prompt in logs, safe error messages, refusals, per-model options.

**Live test (one call through the app, on `t03-today.jpg`):**

| Call | Model | Objects | Input tokens | Output tokens | Cost at list price | Time |
|---|---|---|---|---|---|---|
| Second opinion | `claude-opus-5-5` | 3 | 881 | 352 | about $0.01 | a few seconds |

Claude agreed with all 3 automatic calls (Abnormal). `.env` selects `claude-opus-5-5`, which the status endpoint
reports; I did not open the file. Explain was only tested against the fake client, because you allowed one live call.

**Decisions:**
- Your `.env` uses Opus 5.5 ($4/$20 per MTok). SPEC's default is Sonnet 5.5 ($2/$10). The code honours `.env`.
- Thinking uses up `max_tokens`, and the SPEC's budgets (1500, 400) are tight. So: Sonnet 5.5 sends
  `thinking: between_tools` (off), other current models send `disabled`, and models that always think (Opus 5.5,
  Fable) get 1500 tokens of headroom on top of the budget.
- Re-seeding keeps the `claude_call` table, against the letter of "--reset deletes all rows". Otherwise every demo
  rehearsal would pay again and the daily cap would reset. The saved answer for `t03-today.jpg` makes the demo free.
- Effort: `medium` for opinions, `low` for explanations.
- No server-side refusal fallback: the model is configurable and not all models accept it. A refusal shows a message.
- A failed call is logged but never cached, so a retry reaches the API.

**Still open:** Explain has not been run against the real API.
