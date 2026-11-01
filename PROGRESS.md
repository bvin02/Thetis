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
