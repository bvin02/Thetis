# Hatchery Autopilot: MVP Build Spec (localhost)

Hand this file to Claude Code together with `CLAUDE.md`. Build one phase at a time (§14) and stop
at the end of each phase. Section numbers (§) are referenced by the phase prompts.

---

## 0. Ground rules

- **Runs on localhost only.** No cloud services, no hosting, no accounts, no login. One command
  starts everything (`npm run dev`).
- **One secret:** `ANTHROPIC_API_KEY` in the root `.env`. Only `backend/app/services/claude.py`
  reads it, as a pydantic `SecretStr`. It is never part of a settings or config object, an API
  response, a log line, test output, the frontend, or git. Tests blank it in `conftest.py`, and
  one test asserts that no API response contains `sk-ant`.
- **Time:** the app uses the local time of the computer it runs on. Store naive local datetimes,
  and take "today" as the local date. The seed's relative days and times are local as well.
- **The app works fully without Claude.** Claude features (§8) are optional, hidden when there is
  no key, and capped per day to protect the $200 of credits.
- **Honesty.** Example data and synthetic photos are always labelled in the UI. The risk forecast
  is a rules engine, and the UI says "Rules-based" and "pattern matches", never "diagnosis".
- **Design is final.** Match `design/` exactly (§11). No gradients, glows, neon colours, emoji or
  decorative illustrations. When a screen isn't designed, build it from the same components.

---

## 1. What we are building

A web app for shellfish hatcheries. At each drain-down, a tech photographs a larvae sample through
the microscope they already own and uploads the photo. The app:

1. **Finds, measures and classifies every larva** in the photo with classical computer vision
   (OpenCV): live, abnormal or dead. It marks the ones it is unsure about and draws coloured
   outlines that the tech can click to correct.
2. **Saves the check to a tank**, with optional water readings, and estimates the larvae left in
   the tank.
3. **Tracks every tank over time**: survival, growth, size spread, % dead, % abnormal, gut
   fullness and water chemistry.
4. **Flags tanks at risk of crashing** with explainable rules. It shows the evidence, names the
   pattern it matches, and recommends actions that a manager approves or dismisses.
5. **Optionally asks Claude** for a second opinion on the larvae it is unsure about, and for a
   plain-English explanation of a tank's status.

### The demo the YC video must show (build to this)
1. Floor (home) with example data: "2 tanks need attention now". Line 2 water is corrosive, and
   T-04 and T-05 are At risk.
2. **New check** for T-03. Upload `fixtures/demo/t03-today.jpg` (a labelled synthetic slide).
   About 1 s later, every larva is outlined: green live, orange abnormal, red dead. A few are
   marked "unsure".
3. Click one wrong call to fix it, and the counts update. Click **Ask Claude** on the unsure ones
   and accept the suggestions.
4. Add water readings (one click copies the line's last readings) and click **Save check**.
5. Back on the Floor: "3 tanks need attention now". T-03 is now **Critical**, with "Pattern
   matches a bacterial outbreak", the evidence table and 3 recommended actions. Click
   **Approve isolation**.
6. Open T-03: survival and growth charts, the check history, and "Explain" (Claude).

### Not in the MVP
Hardware, automatic dosing, probe and sensor integrations, auth or multiple users, cloud hosting,
a mobile app, a trained ML model, seed (spat) counting, a backtest screen, a settings UI, Reports,
⌘K search, and the algae room.

---

## 2. Stack and repo layout

| Layer | Choice |
|---|---|
| Backend | Python 3.12 managed by **uv**. FastAPI + Uvicorn, OpenCV (`opencv-python-headless`), NumPy, Pillow, SQLModel on **SQLite**, `python-multipart`, `python-dotenv`, `anthropic`. Tests: pytest + httpx. Lint: ruff |
| Frontend | **Vite + React + TypeScript (strict)**, **Tailwind CSS v4** (`@tailwindcss/vite`), React Router, TanStack Query, Recharts (tank charts only), `@fontsource-variable/geist` and `@fontsource-variable/geist-mono`, `lucide-react` icons (stroke 1.75). No UI kit: hand-build the components so they match the design |
| Storage | `data/hatchery.db` (SQLite) and `data/photos/…` (JPEG files). Both are gitignored |
| Dev | Root `package.json` runs both servers with `concurrently`. Vite (port 5173) proxies `/api` to FastAPI (port 8000) |

```
.
├── SPEC.md  CLAUDE.md  SETUP.md  .env.example  .gitignore   (.env is yours: never committed)
├── .claude/settings.json      # stops Claude Code from reading .env
├── package.json               # root scripts (below)
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py            # FastAPI app, routers, static files at /api/files
│   │   ├── config.py          # env vars + DEFAULTS: every threshold and parameter lives here
│   │   ├── db.py  models.py   # SQLModel tables (§9)
│   │   ├── analysis/          # PURE: engine.py, calibrate.py, summary.py (§5)
│   │   ├── rules/             # PURE: series.py, signals.py, assess.py, text.py, actions.py, history.py (§6, §7)
│   │   ├── services/          # glue with DB: checks.py (save flow), decisions.py, claude.py (§8)
│   │   ├── api/               # routers (§10)
│   │   └── seed.py            # loads seed/example_hatchery.json (§12)
│   └── tests/
├── frontend/src/              # app shell, routes, components, api client, styles/tokens.css
├── tools/gen_slides.py        # synthetic slide generator with ground truth (provided)
├── seed/example_hatchery.json # the example hatchery (provided, verified against §7)
├── fixtures/
│   ├── slides/                # 5 synthetic test slides + truth JSON (provided)
│   ├── demo/t03-today.*       # the demo photo for T-03 + truth (provided)
│   ├── real/j006/             # 30 real photos + labels.json (provided, NO license, gitignored)
│   └── sources/               # where other photos come from + fetch script (optional)
├── design/                    # final UI: screens/*.png, html/*.html, source/*.dc.html, README.md
└── data/                      # created at runtime, gitignored
```

Root `package.json` scripts (exact):
```json
{
  "setup": "npm install && npm --prefix frontend install && cd backend && uv sync",
  "dev": "concurrently -k -n api,web -c blue,green \"npm:dev:api\" \"npm:dev:web\"",
  "dev:api": "cd backend && uv run uvicorn app.main:app --reload --port 8000",
  "dev:web": "npm --prefix frontend run dev",
  "test": "cd backend && uv run pytest -q",
  "seed": "cd backend && uv run python -m app.seed --reset",
  "seed:full": "cd backend && uv run python -m app.seed --reset --full",
  "slides": "uv run --project backend python tools/gen_slides.py fixtures/slides"
}
```
Dev dependencies:
- `concurrently` is a root devDependency.
- `@playwright/test` is a frontend devDependency. Run `npx playwright install chromium` once; it
  is used for screenshot comparisons.

`npm run setup` installs everything on a fresh clone.

The data folder defaults to `<repo>/data`. `HATCHERY_DATA_DIR` overrides it, and tests always use
a temp folder.

The backend loads the root `.env` with `load_dotenv(<repo root>/.env)`. Paths are relative to the
repo root, so commands work from any directory. Run CPU work (analysis) in a thread pool
(`run_in_threadpool`) so the server stays responsive.

---

## 3. Words, users and the core loop

| Word | Meaning |
|---|---|
| **Tank** | A physical larval tank (T-01) or setting downweller (S-01). It sits in a **room** and is fed by a seawater **line**. |
| **Batch** | One spawn raised in a tank (NW-1021): spawn date, number stocked, active or closed (moved to setting, harvested, crashed, discarded). |
| **Check** | One drain-down sample of a batch: photos, counts, sizes, water readings, and the risk snapshot computed when it was saved. |
| **Detection** | One object found in a photo: outline, length, class, unsure flag, and where its class came from (auto, corrected or manual). |
| **Signal** | One measured warning sign (for example dead larvae ≥ 20%) with a severity: watch, risk or critical. |
| **Level** | A tank's status: Normal, Watch, At risk, Critical (or Empty). Keys: `ok`, `watch`, `risk`, `critical`, `empty`. |
| **Pattern** | The named combination of signals ("Pattern matches a bacterial outbreak"). |
| **Decision** | A recommended action waiting for the manager: approve, dismiss, or undo. |

Users: the **tech** at the microscope, who logs checks and fixes calls, and the **manager**, who
watches the Floor and decides. Localhost has no login: the user shown in the sidebar comes from the
seed file ("Dana Ortiz, Hatchery manager") and is recorded as `decided_by`.

Loop: drain the tank → photograph the sample → review and correct → add water readings → save →
rules run → the Floor updates → the manager decides.

---

## 4. Screens

Designed screens are in `design/screens/` (PNG) and `design/html/` (open in a browser to inspect
exact CSS). `design/README.md` has the tokens and component rules. **Floor** and **Photo library**
are designed pixel-for-pixel. The other screens below reuse the same shell and components.

### 4.0 App shell (design: every screen)
- **Sidebar** (216 px, on the tinted canvas): workspace button ("Northwind Shellfish / Hatchery
  Autopilot"; it has no menu in the MVP).
  - Nav: Floor, Tanks, Checks, Decisions (with a black count badge of pending decisions) and
    Photo library. **Hide Reports** for the MVP.
  - "Rooms": only rooms that have tanks. Each has a swatch for its worst tank level and its tank
    count, and filters the Floor. **Leave out the Algae room** (it is still drawn on the plan).
  - User card at the bottom.
- **Main panel**: a white inset panel (radius 12, border `#E2E8EC`) with a 52 px header:
  - breadcrumb, then an **"Example data"** badge whenever example rows exist
  - local date and time ("Sat, Oct 31 · 9:12 AM")
  - the **New check** button (black)
  - Hide the ⌘K button unless §14 phase 7 has spare time.

### 4.1 Floor `/` (design: `home.png`, `home-t04-selected.png`, `home-table-view.png`, `home-phone.png`)
Build it exactly as designed, from live data (`GET /api/floor`). The PNG is the target for
layout, styling and components. Some things come from the seed and the rules, so they differ
slightly from the mock, and the computed values win:
- the numbers
- which history cells are coloured
- the Next check value
- a few condition rows

Do not hardcode the mock's numbers.

The Floor contains:
- **Headline**: "{n} tanks need attention now" (n = Critical + At risk; "1 tank needs…"). If n = 0,
  use "{m} tanks on watch", or "All tanks tracking normally".
- **Summary paragraph** from the template in §7.6.
- **Act now** row (Critical, then At risk) and **Monitor** row (Watch). Each has chips of the form
  "T-03 · Critical · Bacterial pattern". Clicking a chip selects the tank.
- **Metrics**:
  - Larvae in hatchery: the sum of `live_est` over active batches, as "135.6M"
  - Tanks running: "10 of 12"
  - Average survival: the mean over active batches
  - Decisions waiting
  - Next check: the active batch with the oldest last check. Due = last check + 48 h. Show the time
    if it is due today, "Overdue" in watch colour if it is past due, otherwise the day.
- **Floor plan** card with a legend and a Plan | Table toggle:
  - Plan: SVG, viewBox 800×470. Copy the static parts (walls, room labels, pipes, algae
    cultures, bench) from `design/source/Main.dc.html`. Tanks are drawn from data.
  - Seawater line cards show the latest Ω and pH read on that line. A line with an active line
    alert (§7.6) is orange.
  - Tank outline colour and width encode the level. Empty tanks are dashed.
  - Hover shows a tooltip: tank, batch, level, reason, survival, last check, water line.
  - Clicking a tank selects it. Hovering a line card highlights its pipe.
- **Last 14 days** grid: one row per tank, one cell per day, coloured by the level from that day's
  most recent check (§7.8). Each cell has a tooltip; clicking a row selects the tank.
- **Inspector** (right column, `flex: 1 1 376px; max-width: 400px`) for the selected tank. Default
  selection: the worst tank. It contains:
  - header: tank, level pill, "Day 9 · Early umbo", and "Larval room A · Batch NW-1021 · Line 1"
  - **Latest check**: the photo with outlines (drawn from detections, not baked in), count chips,
    "{n} larvae · {µm/px} µm/px", and a "Review outlines" link to `/checks/:id`
  - **Risk forecast**: a 4-step meter, "Rules-based" tag, pattern title and forecast sentence (§7.4)
  - **Condition** table (§7.5)
  - **Survival since spawn** chart
  - **Recommended actions** (§7.7): numbered rows with the action's CTA, Dismiss, and Undo after
    deciding
  - "Open T-03 →" link to the tank page
- Responsive:
  - below 1200 px the inspector moves under the plan
  - below 900 px the sidebar becomes a top bar with a menu button
  - below 660 px the plan becomes the list (container query, as in the design), and the inspector
    opens as a full-screen sheet

### 4.2 New check `/checks/new?tank=T-03` (not designed: build in the same style)
Same shell. Breadcrumb "Northwind Shellfish / New check". The panel body has two columns:
- **Left**: the photo workspace (flex 1)
- **Right**: a 380 px form column, with the same section styling as the Floor inspector (13 px
  section titles, `#EEF2F4` dividers)

**Before a photo**
- Tank select. It lists only tanks with an active batch, as "T-03 · Day 9 · Early umbo", and is
  prefilled from `?tank` or the Floor selection.
- "Sampled at" (datetime-local, default now).
- Drop zone: white, `1.5px dashed #C7CFD4`, radius 12. It reads "Drop microscope photos here, or
  choose files" with "JPG or PNG · one photo per field of view", and has a ghost button **Use a
  sample slide**. That button opens a menu of `fixtures/slides` and `fixtures/demo` photos,
  each labelled "Synthetic".
- A dropped or chosen file whose SHA-256 matches a file in those folders is marked
  `synthetic = true`, with its `source_name`, exactly like a sample slide. So dragging in
  `t03-today.jpg` still shows the "Synthetic sample" badge.
- Two muted tips:
  - "Concentrate the sample so each photo holds about 20–50 larvae."
  - "Keep the counting-slide grid in view so sizes calibrate automatically."

**Analysing**: an inline spinner with "Finding larvae…" (target ≤ 1 s). No skeleton screens.

**Review** (the core of the demo)
- **Image viewer**: the photo with an SVG overlay in image coordinates. Outlines use the class
  colours: live `#2E8B57`, abnormal `#C2620E`, dead `#C2362B`, at 2 px with
  `vector-effect: non-scaling-stroke`.
  - **Unsure** objects: dashed outline plus a small "?" badge.
  - **Clumps**: a "×3" pill at the centroid.
  - "Not a larva" objects are hidden unless the "Ignored" chip is on, then shown in `#AEB9C0`
    dotted.
  - Hover fills the object at 8% opacity. The selected object gets a 3 px outline with a white halo.
- **Toolbar** above the image:
  - segmented control **Select | Add larva**
  - filter chips with counts: Live 44 · Abnormal 5 · Dead 14 · Unsure 4 · Ignored 31
  - zoom −, +, Fit (mouse wheel zooms, drag pans)
  - photo tabs when there are several ("Photo 1 · Photo 2 · + Add photo")
- **Correct**: clicking an object opens a small popover: "Larva 12 · 131 µm", then Live (1),
  Abnormal (2), Dead (3), Not a larva (0); manual objects also get Delete. Keys 1/2/3/0 work on the
  selected object, and Tab moves to the next unsure one. A change sets `source = corrected` when it
  differs from `auto_cls`. Counts and the summary update instantly (`POST /api/summarize`,
  debounced 100 ms).
- **Add larva** mode: clicking empty space adds a manual live larva (a circle at the median
  length) and opens its popover.
- **Caption** under the image: "63 larvae · 1.60 µm/px · grid calibration · 0.0049 mL in view".
  Without calibration, show a link "Add a scale" that lets the user draw a line and type its µm.

Right column, top to bottom:
1. **Counts**: Live, Abnormal, Dead rows with % of counted (the layout of the photo-library
   preview stats). Under them, "4 to check" with a **Review** button (steps through the unsure ones,
   zooming to each) and **Ask Claude** (§8.1; hidden when Claude is off).
2. **Size**: mean ± SD (µm), CV, stage chip, and a 10 µm-bin histogram (bars `#A7B3BA`, previous
   check's histogram as a `#0F1A20` outline).
3. **Gut fullness**: the value, with "beta" in muted text.
4. **Estimate for the tank**:
   - Inputs: Bucket volume (L), default 20, and "Sample concentrated ×", default 50 (both from
     settings).
   - Result: "≈ 3.9M live larvae (39% of 10.0M stocked)".
   - Warning (watch colour) if the result is above 1.1 × stocked: "More than were stocked. Check
     the concentration."
5. **Water readings (optional)**, collapsible: Temperature °C, Salinity ppt, pH, Ω aragonite and
   Oxygen mg/L. Above the inputs: "Line 1 · last reading Ω 2.9 · pH 7.96 · today 8:40 AM", with a
   **Use these** link.
6. **Notes** (textarea).
7. **Save check** (black, full width) and Cancel (ghost). Save is disabled until there is a tank
   and a reviewed photo.

**After save**:
- Go to `/` with the tank selected.
- Show a toast: "Check saved. T-03 is now Critical. 3 decisions waiting." The toast is a white card
  (border `#E2E8EC`, shadow `0 8px 24px rgba(15,26,32,.10)`) with a status dot, and auto-hides after
  6 s.

### 4.3 Check detail `/checks/:id`
The same review layout, read-only, with **Edit outlines** (re-enables correction, then Save
changes → `PATCH`, §10). It shows the saved water readings and estimate, the risk snapshot taken
at save time, and a "Synthetic sample" badge when the photo came from `fixtures/`.

### 4.4 Tank page `/tanks/:id`
- **Header**: "T-03" (Geist Mono 24/600), level pill, and "Day 9 · Early umbo · Larval room A ·
  Batch NW-1021 · Line 1". Buttons:
  - **New check** (black)
  - **Close batch** (ghost; dialog: outcome Moved to setting / Harvested / Crashed / Discarded,
    plus date and note)
  - For an empty tank, **Start batch** (dialog: batch code, spawn date, number stocked)
- **Left column**:
  - **Trends** card with a segmented control: Survival | Shell length | Dead & abnormal | Water.
    - One 260 px chart; x = day since spawn.
    - Ink line 1.5 px with 3 px points. The last point uses the level colour.
    - Threshold and expected-growth lines are dashed `#C7CFD4` with small labels.
  - **Checks** table: When, Day, Larvae (est.), Survival, Length, Growth, Dead, Abnormal, Gut, Ω,
    pH, Temp, Photos.
    - Values at watch or worse use that severity's text colour.
    - A row click opens `/checks/:id`.
- **Right column (400 px)**: the inspector blocks from 4.1, then **Explain** (§8.2), then
  **Decision history** for this tank: approved and dismissed decisions with who, when and note.

### 4.5 Decisions `/decisions`
Header "Decisions" and a segmented filter: Waiting (n) | Decided | All. Rows are grouped by target
("T-03 · Critical · Pattern matches a bacterial outbreak", "Line 2 · corrosive water"). Each row
reuses the inspector's action component. Decided rows show the done text, "Dana Ortiz · Today,
9:20 AM", the note, and Undo.

### 4.6 Photo library `/photos` (design: `photo-library.png`)
Build it as designed, with four columns:
- Rooms (photo counts)
- Tanks ("Day 9 · 24% dead")
- Checks (time, then "24% dead · 128 µm")
- Preview: photo with outlines, the stats list, and **Review outlines**

Hide the Filter button and the "Unsorted" row for the MVP.

### 4.7 Tanks `/tanks` and Checks `/checks`
- **Tanks**: the Floor's table view as its own page, with a room filter and **Start batch** on
  empty tanks.
- **Checks**: a table of all checks, newest first (When, Tank, Batch, Larvae counted, Dead,
  Abnormal, Length, Level after check, Photos). Rooms are filter chips, and a row click opens
  `/checks/:id`.

---

## 5. Image analysis engine (`backend/app/analysis`, pure functions)

A prototype of exactly this pipeline was checked against the provided fixtures. Results:

| Measure | Result |
|---|---|
| Counts per synthetic slide | within ±2.1% |
| Dead larvae | precision 1.00, recall 0.97 |
| Abnormal larvae | precision ≈ 0.88, recall ≈ 0.9 |
| Shell length | MAE 2.4 µm |
| Grid scale | found on every gridded slide, no false grids |
| Speed | about 0.25 s per photo |
| Real J006 photos | exact count on 22 of 30, with a cruder size rule than below |

Follow the steps and starting values below. They are expected to work, but tune if a test fails.

### 5.1 Interface
```python
Cls = Literal["live", "abnormal", "dead", "ignore"]

class Detection(BaseModel):
    id: int
    cx: float; cy: float                    # ORIGINAL image px
    contour: list[tuple[float, float]]      # original px, simplified to <= 48 points
    length_px: float                        # shell length, original px
    length_um: float | None
    area_px: float                          # original px^2
    solidity: float; defect: float; hollowness: float
    gut: float | None                       # 0..1, live/abnormal only
    interior: float                         # median background-minus-gray inside (negative = brighter)
    cls: Cls; auto_cls: Cls
    unsure: bool; unsure_reason: str | None # "between live and dead", "shape borderline", "clump count"
    clump_n: int = 1
    touches_edge: bool
    source: Literal["auto", "corrected", "manual"] = "auto"

class AnalysisResult(BaseModel):
    width: int; height: int                 # original size
    um_per_px: float | None
    calibration: Literal["grid", "preset", "manual", "none"]
    grid_spacing_px: float | None           # original px
    photo_volume_ml: float | None
    detections: list[Detection]
    engine_version: str                     # "cv-0.1"
    ms: int

def analyze(img_bgr: np.ndarray, *, um_per_px: float | None = None,
            params: EngineParams = DEFAULT_ENGINE) -> AnalysisResult
def summarize(dets: list[Detection], um_per_px: float | None, settings: Settings) -> Summary
```
`summarize` is separate so corrections recompute the summary without re-running segmentation.

### 5.2 Pipeline
1. If the long side is > 1600 px, resize to 1600 with `INTER_AREA`. Call the factor `s` and map
   all geometry back to original px at the end.
2. `gray = 0.25 R + 0.45 G + 0.30 B` (float32). Brown larvae absorb blue, so blue gets a little
   weight.
3. **Background**:
   - Downsample `gray` ×4 (`INTER_AREA`).
   - `MORPH_CLOSE` with an elliptical kernel of odd size `k = 0.2 × long side / 4` (81 at 1600 px),
     border `REFLECT`. Closing removes dark objects up to about a fifth of the image.
   - `GaussianBlur` with σ = k/6.
   - Upsample back (`INTER_LINEAR`).
4. `d = bg − gray`, then `d −= median(d)`. Noise `σ = 1.4826 × median(|d|)`. `diff = max(d, 0)`.
5. **Grid** (§5.4). For each detected grid line, replace `diff` across the band
   `[start − 3, end + 3]` by linear interpolation between the band's two edges, so larvae that
   cross a line stay whole.
6. **Threshold**: `T = max(4σ, 0.5 × Otsu(diff values > 3σ, clipped to 0–255))`. `mask = diff > T`.
   Dead shells are faint inside, but their rim is dark and closed.
7. `MORPH_CLOSE` 3×3 ×2. **Fill holes**: holes are the background components, 4-connected, that
   don't touch the border. Then `MORPH_OPEN` 3×3 ×1.
8. Label 8-connected components (`connectedComponentsWithStats`) and drop those with area < 40 px.
9. **Open-rim repair**. Let `A_med` be the median area of the components ≥ 300 px. Any component
   whose convex-hull area is > 0.3 `A_med` and whose area / hull area is < 0.5 is an empty shell
   with a broken rim (typically along a grid line). Fill its convex hull and relabel.
10. **Features** per object:
    - **Contour**: `findContours` on the object's ROI (`CHAIN_APPROX_NONE`); store
      `approxPolyDP(ε = 0.6 px)`, at most 48 points.
    - **Length**: max Feret diameter = max distance between hull points, + 1 px, − **3 px** edge
      correction (the threshold widens edges). Converted with µm/px.
    - **Aspect**: long side / short side of `minAreaRect`.
    - **Shape on an opened mask**: open the object's mask with an ellipse of odd size
      `max(3, 0.14 × Feret)`, padding first. This strips attached algae, debris spikes and grid
      residue. If the opened mask keeps > 50% of the area, compute on it:
      - `solidity = contour area / hull area`
      - `defect` = deepest convexity defect (`depth / 256`) / Feret. OpenCV 5 returns defects as
        N×4, so use `reshape(-1, 4)`.

      Otherwise compute both on the raw mask.
    - **Hollowness**: distance transform (`DIST_L2`, 5) inside the object, with
      `rEq = √(area/π)`. `inner = d[dist ≥ 0.35 rEq]` and `ring = d[0 < dist < 0.2 rEq]`.
      `hollowness = mean(inner) / mean(ring)`. Live ≈ 1.3–1.9, abnormal ≈ 0.9–1.6, dead ≈ 0.18–0.37.
    - **Gut**: `core = d[dist ≥ 0.25 rEq]`, then
      `gut = clip(0.94 × (P95(core) − median(core)) / median(ring), 0, 1)`. It correlates 0.97 with
      truth on the synthetic slides. Show it as "beta".
    - **Interior** = `median(inner)`. Negative means brighter than the background, i.e. an air
      bubble.
    - **touches_edge**: the bounding box touches the image border.
11. **Classification**, first match wins. `A_ref` is the median area of round candidates (area ≥ 300,
    solidity ≥ 0.9, aspect ≤ 1.6, interior ≥ −3σ).
    - **ignore** if any of these holds:
      - area < 60 px
      - aspect > 2.6
      - interior < −3σ (bubble)
      - when calibrated: length < 45 µm or > 420 µm
      - when not calibrated: area < 0.35 `A_ref`, or area > 4 `A_ref` with solidity ≥ 0.93
    - **clump**: area > 1.35 `A_ref` and (solidity < 0.93 or defect > 0.12). Set
      `clump_n = max(2, round(area / A_ref))`, class `live`, `unsure = true` ("clump count").
    - **dead**: hollowness < 0.6.
    - **abnormal**: solidity < 0.955.
    - **live**: everything else.
    - **unsure** when hollowness is in [0.45, 0.8), or the object is live or abnormal with
      solidity in [0.945, 0.965).

All numbers above live in `EngineParams` in `config.py`.

### 5.3 Summary (`Summary`)
- `n_live` (clumps add `clump_n`), `n_abnormal`, `n_dead`, `n_unsure`, `n_ignored`.
- `pct_dead = 100 × dead / (live + abnormal + dead)`; `pct_abnormal` likewise.
- **Sizes**, from live and abnormal singles that don't touch the edge, and only when calibrated:
  `mean_len_um`, `sd_len_um` (sample SD, `ddof=1`), `cv = sd/mean`, and a histogram of 10 µm bins
  from 40 to 420.
- `stage` from the mean (§6). `gut` = mean gut of the live singles.
- `count_for_estimate` = live + abnormal, with edge-touching objects counted as 0.5 and clumps as
  `clump_n`.

### 5.4 Calibration (µm per px)
1. **Grid (Sedgewick-Rafter, 1 mm squares)**. For each axis:
   - Take the per-column (or per-row) median of `diff`.
   - Find peaks above `max(median + 8·MAD, 4σ)`, skipping 4 px at the borders.
   - Group contiguous indices (gap ≤ 2) and keep groups ≤ 15 px wide. The line centre is the
     group's argmax.

   An axis is valid when it has ≥ 2 lines, spacing CV < 5% and spacing ≥ 100 px. If both axes are
   valid they must agree within 5% (average them). Then `um_per_px = 1000 / spacing`, converted to
   original px. Works when the grid is within about 1° of the image axes.
2. **Preset**: `settings.microscope_presets` (name → µm/px).
3. **Manual**: the user draws a line over a known distance.
4. **None**: sizes stay in px, and stage and growth are not computed for that check.

**Photo volume** = width × height × (µm/px)² / 10⁶ (mm²) × chamber depth (1 mm) / 1000 (mL). A
1600×1200 photo at 1.6 µm/px holds 0.004915 mL.

### 5.5 Upgrade path (after YC, not now)
Keep `analyze()` as the seam. A trained segmenter (YOLO-seg or Cellpose, fine-tuned on corrected
detections) later returns the same `Detection` list. Every correction is a training label, so
store them all.

---

## 6. Tank math (`rules/series.py`)

- `live_est` (photo check) = `count_for_estimate / (Σ photo_volume_ml × concentration) × bucket_l ×
  1000`. With several photos, sum the counts and the volumes. A manual check stores `live_est`
  directly.
- `survival = live_est / stocked`.
- **Day N**: a check's day = its local date − spawn date. A tank's current day (Floor, tank page)
  = today − spawn date.
- **Baseline for rates** = the most recent earlier check of the batch at least 0.5 days older. If
  there is none, loss uses stocking at spawn (spawn date 12:00) and growth is not computed.
- **Loss rate** `k = −ln(live_est / baseline_live) / Δdays`, where Δdays is fractional.
- **Growth** = `(mean_len − baseline_mean_len) / Δdays` in µm/day. It is skipped in setting tanks
  and when the baseline mean is ≥ 260 µm, because eyed larvae stop growing before they set.
- **Previous check** (used for the "+ points" rules and the "at last check" texts) = the
  immediately previous check.
- **Stage** (Pacific oyster): D-stage < 120 µm, Early umbo 120–180, Late umbo 180–260, Eyed ≥ 260.
  Tanks in a setting room show "Setting".

---

## 7. Rules engine (`backend/app/rules`, pure functions)

`assess(checks, batch, tank_kind, cfg, upto=None) -> Assessment` uses only `checks[:upto+1]`, so
history can be replayed exactly. A test appends a future crash and asserts the earlier result
doesn't change. The `Assessment` has: level, pattern, signals (key, severity, value, previous
value, kind), growth, loss rate, survival, stage, `rules_version = "rules-0.1"`.

### 7.1 Signals (defaults live in `config.py`)
| Key | Kind | Measure | Watch | Risk | Critical |
|---|---|---|---|---|---|
| `dead` | larvae | % dead | ≥ 10, or +8 points vs previous check | ≥ 15 | ≥ 20 |
| `abnormal` | larvae | % abnormal | ≥ 12, or +8 points | ≥ 20 | ≥ 30 |
| `growth` | larvae | growth ÷ expected (9 µm/day) | < 0.50 | < 0.35 | < 0.20 |
| `gut` | larvae | gut index | < 0.35 | < 0.25 | – |
| `spread` | larvae | CV of length | ≥ 0.18, or +0.06 vs previous | ≥ 0.26 | – |
| `loss` | count | loss rate k per day | > 0.10 | > 0.15 | – |
| `omega` | water | Ω aragonite | < 2.0 | < 1.5 | – |
| `ph` | water | pH | < 7.8 | < 7.65 | – |
| `temp` | water | \|T − 25 °C\| | > 2 | > 3.5 | – |
| `oxygen` | water | DO mg/L | < 6 | < 5 | – |

Missing data means the signal is skipped: no row, and no effect on the level. In §7.2 and §7.3,
"OK" means "not at watch or worse", so a missing reading counts as OK there.

### 7.2 Level ladder (first match)
1. **Critical**: any larvae signal is critical, or (dead ≥ risk and loss ≥ risk).
2. **At risk**: any one of these holds:
   - any larvae signal ≥ risk
   - a water signal ≥ risk and any larvae signal ≥ watch (the water is hurting the larvae)
   - loss ≥ risk and any larvae signal ≥ watch
3. **Watch**: any signal ≥ watch. Water alone, or loss alone, never goes above Watch.
4. **Normal** otherwise.

### 7.3 Patterns (first match; only when level ≠ Normal)
| Key | When | Title (inspector) | Chip |
|---|---|---|---|
| `bacterial` | (dead or loss ≥ watch) and (gut or growth ≥ watch) and neither Ω nor pH ≥ watch (missing counts as OK) | Pattern matches a bacterial outbreak | Bacterial pattern |
| `corrosive` | (Ω or pH ≥ watch) and (abnormal, growth or dead ≥ watch) | Pattern matches corrosive water | Corrosive water |
| `corrosive_early` | Ω or pH ≥ watch, no larvae signal | Water is corrosive; larvae not affected yet | "On line 2" when the line alert is on, else "Corrosive water" |
| `underfed` | (gut or growth ≥ watch) and dead and loss OK | Growing slower than expected | Slow growth |
| `splitting` | spread ≥ watch | Batch is splitting into fast and slow growers | Size spread widening |
| `temperature` | temp ≥ watch | Water temperature is off target | Temperature off |
| `oxygen` | oxygen ≥ watch | Oxygen is low | Low oxygen |
| `unexplained_loss` | loss ≥ watch and no larvae signal | Fewer larvae than expected | Unexplained loss |
| `early_warning` | anything else | An early warning sign | Early warning |

For a Normal tank the title is "Tracking normally". It is "Ready to set" for eyed larvae and
"Setting" in a setting room.

### 7.4 Forecast sentence (inspector, under the title)
- Normal: "No warning signs at the last check."
- Watch: "An early warning sign. Re-check at the next drain."
- At risk: "Elevated chance of a crash in the next 1–3 days."
- Critical: "High chance this batch crashes in the next 1–3 days if nothing changes."
- Empty: "No batch in this tank."

### 7.5 Condition table (inspector "Condition": Now | Compared with)
Rows, in this order:
1. **Signals at watch or worse**, except loss. Order by severity, then dead, growth, gut, abnormal,
   spread, omega, ph, temp, oxygen. The dot and the "Now" text use the severity colour.
2. **Context rows** with a grey dot:
   - for `bacterial`: Ω aragonite, "target ≥ 2" (shows the water is fine)
   - for `corrosive_early`: Abnormal shells, "normal range"
3. **Live larvae (est.)**, always. The dot follows the loss severity. Compared with: "{prev} at
   last check" when loss ≥ watch, else "of {stocked} stocked".
4. **Shell length**, always. Compared with: "{prev} µm at last check" when growth is a row,
   otherwise "growing {g} µm/day", or "first check".

Labels:

| Signal | Label |
|---|---|
| dead | Dead larvae |
| growth | Growth |
| gut | Gut fullness |
| abnormal | Abnormal shells |
| spread | Size spread (CV) |
| omega | Ω aragonite |
| ph | pH |
| temp | Water temperature |
| oxygen | Oxygen |

"Compared with" text:

| Signals | Text |
|---|---|
| dead, abnormal, gut, spread | "{prev} at last check" |
| growth | "9 µm/day expected" |
| omega | "target ≥ 2" |
| ph | "target ≥ 7.8" |
| temp | "target 25 °C" |
| oxygen | "target ≥ 6 mg/L" |

Number formats: % as integers, CV with 2 decimals, growth with 1 decimal (the expected growth
without a trailing ".0", so "9"), Ω with 1 decimal, pH with
2 decimals, counts like "4.1M" or "850k".

### 7.6 Texts on the Floor
**Reason** (one sentence or two; used in tooltips, the table and chips): the first two signals by
severity, then in the order dead, loss, omega, ph, growth, abnormal, gut, spread, temp, oxygen. Use
pH only if Ω wasn't used.

| Signal | Template |
|---|---|
| dead | "Dead larvae {v}%, up from {p}% at the last check." (or "Dead larvae {v}%.") |
| loss | "Survival fell from {p}% to {v}% since the last check." |
| omega / ph | "Line {n} water is corrosive (Ω {v})." when the line alert is on, else "Water is corrosive (Ω {v})." |
| growth | critical: "Growth has stalled.", else "Growth is {g} µm a day, below the {e} expected." |
| abnormal | "Abnormal shells are up to {v}%." |
| gut | risk: "Guts are nearly empty.", watch: "Guts look light." |
| spread | "Size spread is widening: CV {v}, up from {p} at the last check." |
| temp | "Water is {t} °C, {d} °C off target." |
| oxygen | "Oxygen is low ({v} mg/L)." |

Special cases:
- `corrosive_early` with a line alert: "On line {n} (Ω {v}). Larvae look normal so far."
- Normal, by case:
  - first check: "First check done. Tracking normally."
  - eyed: "Eyed larvae. Ready to move to setting in 1–2 days."
  - setting room: "Setting on cultch."
  - otherwise: "Tracking normally."
- Empty tank: "Empty. Being cleaned." (status cleaning), or "Empty."

**Line alert**: ≥ 2 active tanks on the same line whose latest check (within 3 days) has Ω or
pH ≥ watch. **Since** = the first alerting check of the current run, shown as "today",
"yesterday", a weekday within 7 days, or "Oct 24".

**Summary paragraph**:
1. For each line alert: "Line {n} water has been corrosive since {since}. It now affects
   {tanks at At risk/Critical, joined 'T-04 and T-05'}, and {other active tanks on the line} {is/are}
   on the same line."
2. Then, for each Critical or At risk tank not on an alerting line: "{Separately, }{T-03} shows a
   pattern that matches {noun}." Add "Separately, " only after a line sentence.

   | Pattern | Noun |
   |---|---|
   | bacterial | a bacterial outbreak |
   | corrosive | corrosive water |
   | underfed | underfeeding |
   | splitting | a splitting batch |
   | temperature | a temperature problem |
   | oxygen | low oxygen |
   | unexplained_loss | unexplained losses |
   | early_warning | an early warning |
3. If nothing is At risk or worse: "{m} tanks are on watch. Nothing needs action right now.", or
   "All tanks are tracking normally."

With the full example data this must produce exactly: *"Line 2 water has been corrosive since
yesterday. It now affects T-04 and T-05, and T-06 is on the same line. Separately, T-03 shows a
pattern that matches a bacterial outbreak."*

### 7.7 Decisions
**Catalog** (`rules/actions.py`):

| Action | Title | CTA | Done text |
|---|---|---|---|
| `isolate` | Isolate {T}. Use separate screens, buckets and hoses. | Approve isolation | Isolation approved |
| `sample_vibrio` | Plate a water and larvae sample to check for Vibrio | Request sampling | Sampling requested |
| `restock` | Drain, clean and restock in fresh water today | Approve drain and restock | Drain and restock approved |
| `discard` | Discard this batch to protect the other tanks | Approve discard | Discard approved |
| `buffer_line` | Buffer line {n} water to bring Ω aragonite to 3 or higher | Approve buffering | Buffering approved |
| `hold_spawn` | Hold the next spawn until line {n} water recovers | Hold next spawn | Next spawn on hold |
| `buffer_tank` | Buffer this tank's water to bring Ω aragonite to 3 or higher | Approve buffering | Buffering approved |
| `screen` | Screen at the next drain and cull the slowest growers | Schedule screening | Screening scheduled |
| `feed_check` | Check the algae ration and culture health | Request feed check | Feed check requested |
| `recount` | Take a second sample now to confirm the count | Request recount | Recount requested |
| `temp_check` | Check the heater or chiller setpoint | Request check | Check requested |
| `aerate` | Increase aeration in this tank | Approve | Aeration increased |

**Pattern → actions**:

| Pattern | Actions |
|---|---|
| bacterial | isolate, sample_vibrio, restock (+ discard if dead ≥ 40%) |
| corrosive, corrosive_early | `buffer_line` (line scope), plus `hold_spawn` (line scope) when the line alert is on. A tank with no line gets `buffer_tank` |
| underfed | feed_check |
| splitting | screen |
| temperature | temp_check |
| oxygen | aerate |
| unexplained_loss, early_warning | recount |

**When a check is saved**:
1. Run `assess` for it.
2. Recompute the line alerts.
3. Create every decision whose (scope, target, action) isn't already pending.
4. Return the new decisions.

**Deciding**:
- Approve and dismiss record `decided_by`, `decided_at` and an optional note. Undo returns the
  decision to pending.
- Line-scoped decisions show in the inspector of every tank on that line, and count once in the
  badge.
- Nothing ever acts on equipment.

### 7.8 History grid (Last 14 days)
For each tank and each day from today−13 to today:
- If a batch was active that day, the cell shows the level of its most recent check on or before
  the end of that day (Normal if it hasn't been checked yet).
- Otherwise the cell is empty, with a dashed border; its tooltip says "No batch in this tank" or
  "Tank emptied".

Each check stores its level when saved. The seed computes it by replay.

---

## 8. Claude features (optional; `services/claude.py`)

Use the `anthropic` Python SDK on the backend only:
- `services/claude.py` is the only module that reads `ANTHROPIC_API_KEY`, as a `SecretStr`.
  `GET /api/claude/status` returns only `enabled`, `model`, `used_today` and `limit`.
- Model comes from `CLAUDE_MODEL` (default `claude-sonnet-5-5`; `claude-haiku-5-5` is cheaper).
- Structured output: `client.messages.parse(model=…, max_tokens=…, system=…, messages=[…],
  output_format=PydanticModel)` → `.parsed_output`. If the installed SDK lacks `parse`, use
  `messages.create(…, output_config={"format": {"type": "json_schema", "schema": …}})` and
  `json.loads` the text block.
- If there is no key, every Claude button is hidden and `GET /api/claude/status` returns
  `enabled: false`.

### 8.1 Second opinion on unsure larvae
Called by `POST /api/claude/second-opinion {photo, detection_ids}`, with at most 12 per call.

**Request**:
- One image block per object: a crop with 30% padding, at most 256 px, JPEG quality 85, with the
  automatic outline drawn 1 px in its class colour.
- Before each image, a text line: "Object {n}: automatic call {cls} ({unsure_reason}), length {L} µm".
- System prompt: "You help a shellfish hatchery technician review a microscope photo of Pacific
  oyster larvae on a counting slide. Each numbered crop is one object an automatic counter was
  unsure about. Classify each: live (shell filled with brown tissue, smooth D or umbo outline),
  abnormal (misshapen, indented or asymmetric shell, or tissue shrunk but still brown), dead
  (empty or nearly empty pale shell, only the outline dark), not_larva (bubble, algae, debris,
  grid line). Give a reason of at most 12 words. If you can't tell, say so with low confidence."

**Schema**: `{opinions: [{object: int, cls: "live"|"abnormal"|"dead"|"not_larva",
confidence: "low"|"medium"|"high", reason: str}]}`.

**UI**: each unsure object shows "Claude: Dead · empty shell, outline only", with **Accept** and
**Keep**, plus **Accept all**. Accepting sets `source = corrected` and stores the opinion on the
detection (`claude` JSON). The button shows a 1-line note: "Sends {n} small crops to Claude."

### 8.2 Explain this tank
Called by `POST /api/claude/explain {tank_id}`, and only when the user clicks **Explain**.

**Input**: the assessment JSON, plus the last 3 checks' key numbers and the recommended actions.

**Instruction**: "Write 3 short sentences for a hatchery manager: what changed since the last check,
why the numbers match this pattern, and what the recommended actions do. Use only numbers from the
data. Say 'pattern matches', never 'diagnosis'."

**Display**: under Risk forecast, with the caption "Written by Claude from the numbers above".
Cache it by `(check_id, rules_version)`.

### 8.3 Budget guard
- Every call is logged in `claude_calls` (kind, input hash, model, input and output tokens,
  created_at, result or error).
- **Cache**: an identical input hash returns the stored result, with no API call.
- **Daily cap**: `CLAUDE_DAILY_LIMIT` calls (default 100). Over the cap, return 429 and show "Daily
  Claude limit reached".
- `max_tokens`: 1500 for opinions, 400 for explanations. Never log the key or full prompts.

---

## 9. Data model (SQLModel on SQLite)

```
Hatchery(id=1, name, species, user_name, user_initials, user_role, settings JSON, is_example)
Room(id "A", name, kind "larval"|"setting", label_xy JSON, caption)
Line(id "L1", name, card_xy JSON)
Tank(id "T-01", room_id, line_id, shape "circle"|"rect", geom JSON {cx,cy,r}|{x,y,w,h},
     volume_l, status "active"|"cleaning"|"empty", is_example)
Batch(id, code, tank_id, species, spawn_date, stocked, status "active"|"closed",
      outcome "moved_to_setting"|"harvested"|"crashed"|"discarded"|None, closed_on, is_example)
Check(id, batch_id, tank_id, sampled_at, source "photo"|"manual",
      n_live, n_abnormal, n_dead, n_unsure, pct_dead, pct_abnormal,
      mean_len_um, sd_len_um, cv, gut, stage, hist JSON, live_est,
      bucket_l, concentration, photo_volume_ml,
      temp_c, salinity_ppt, ph, omega_arag, do_mgl, notes,
      level, pattern, signals JSON, growth_um_day, loss_per_day, survival,   -- snapshot at save time
      engine_version, rules_version, created_by, is_example)
Photo(id, check_id, path, width, height, um_per_px, calibration, grid_spacing_px, volume_ml,
      engine_version, synthetic bool, source_name)
Detection(id, photo_id, cx, cy, contour JSON, length_px, length_um, area_px, solidity, defect,
          hollowness, gut, interior, cls, auto_cls, unsure, unsure_reason, clump_n, touches_edge,
          source "auto"|"corrected"|"manual", claude JSON)
Decision(id, scope "tank"|"line", tank_id, line_id, check_id, action, status
         "pending"|"approved"|"dismissed", created_at, decided_at, decided_by, note, is_example)
ClaudeCall(id, kind, input_hash, model, input_tokens, output_tokens, created_at, result JSON, error)
```
Titles and CTAs come from the catalog, not the DB. The risk snapshot on `Check` matters: it proves
later what the system said *before* a crash. Photos live at `data/photos/{check_id}/{photo_id}.jpg`.
Uploads waiting to be saved go to `data/uploads/` and are deleted after 24 h.

---

## 10. API (JSON; all under `/api`)

| Method & path | Purpose |
|---|---|
| `GET /health` | `{ok: true}` |
| `GET /floor` | Everything the Floor needs, in one response:<br>• hatchery, user, now, example flag<br>• headline, summary, metrics<br>• act_now and monitor chips<br>• tanks (geometry, level, pattern, reason, chip, stage, day, live, survival, last check, line)<br>• lines (latest Ω/pH, alert)<br>• rooms and the history grid |
| `GET /tanks`, `GET /tanks/{id}` | List, or one tank: batch, assessment, condition rows, actions with decision ids, chart series, checks, decision history |
| `POST /batches`, `POST /batches/{id}/close` | Start or close a batch |
| `POST /analyze` (multipart `file`) | Save the upload and analyze it → `{token, width, height, um_per_px, calibration, photo_volume_ml, detections, summary}` |
| `GET /samples`, `POST /samples/{name}/analyze` | List and analyze the synthetic photos in `fixtures/slides` and `fixtures/demo` |
| `POST /summarize` | `{detections, um_per_px, photo_volume_ml, sample}` → summary and estimate (used live while correcting) |
| `POST /checks` | `{tank_id, sampled_at, photos:[{token, detections}], sample:{bucket_l, concentration}, water, notes}` → `{check_id, level, pattern, new_decisions}` |
| `GET /checks`, `GET /checks/{id}` | List (filters: tank, room); one check with photos, detections and snapshot |
| `PATCH /checks/{id}/photos/{pid}/detections` | Save corrections, then recompute the summary and re-assess this check and later ones in the batch |
| `GET /decisions?status=` | List |
| `POST /decisions/{id}/approve`, `/dismiss`, `/undo` | `{note?}` |
| `GET /photos/tree` | Rooms → tanks → checks, for the Photo library |
| `GET /files/...` | Static photos from `data/` |
| `GET /claude/status`, `POST /claude/second-opinion`, `POST /claude/explain` | §8 |

---

## 11. Design system (details in `design/README.md`)

- **Fonts**: Geist and Geist Mono (tank ids and keyboard hints). Base size 14 px, sentence case
  everywhere.
- **Canvas** `#EDF1F3`. **Panel** white, radius 12, border `#E2E8EC`. **Dividers** `#EEF2F4`.
- **Ink** `#0F1A20`, secondary `#3E4B53`, muted `#5F6C74` / `#66737B`.
- **Brand** `#13557A`: logo, active nav icon, focus ring and links only.
- **Primary button**: black `#0F1A20`, hover `#26333A`. Ghost buttons: white with a border.
- **Status colours are only for problems**:

  | Level | Colour | Text | Pill |
  |---|---|---|---|
  | Critical | `#D93A2F` | `#B42318` | `#FEF3F2` |
  | At risk | `#E0702A` | `#B54708` | `#FFF6ED` |
  | Watch | `#C98A0B` | `#8E6206` | `#FEF9EC` |

  Normal is grey (ring `#A7B3BA`, swatch `#DCE3E7`). Empty is a dashed `#C7CFD4`. Approved is the
  only green (`#2E7D57` on `#EEF7F1`).
- **Outline colours on photos**: live `#2E8B57`, abnormal `#C2620E`, dead `#C2362B`.
- **Never**: gradients, glows, coloured shadows, neon, emoji, illustrations, or colour as the only
  carrier of meaning (always pair it with text).
- **Accessibility**: a visible focus ring (2 px `#13557A`), aria labels on icon buttons and chart
  summaries, keyboard access to the plan and the photo editor, and 44 px tap targets on phones.

---

## 12. Example data, photos and honesty

**Seed**: `npm run seed` loads `seed/example_hatchery.json`. It is relative to the current day,
verified against §7, and every row is `is_example = true`.
- The default (**demo mode**) skips the rows marked `demo_live` (T-03's check today and its 3
  decisions), so T-03 starts at Watch. The live demo upload then makes it Critical.
- `npm run seed:full` loads everything and reproduces the designed Floor's state: levels,
  patterns, decisions, headline and summary.
- `--reset` deletes all rows and saved photos and recreates the tables. Stop `npm run dev` before
  seeding.

**Seeding rules**:
1. **Photos and stats.** For each seeded check:
   - Render its photo with `make_slide(name, out, seed=…, stage=…, grid=…, clumps=0, counts=…,
     mean_len_um=…, sd_len_um=…, gut=…)` from `tools/gen_slides.py`.
   - Create detections from the truth JSON (`poly` → contour, plus `cls`, `len_um`, `gut`) with
     `source = auto`.
   - Compute the check's stats with `summarize`. They match the file's numbers.
   - If `make_slide` raises "no room" (a different numpy), retry with `seed + 1000`.
2. **Estimates.** Seeded checks keep the file's `live_est`. It stands for a full count; the photo
   only illustrates it. Don't recompute it from the photo.
3. **Decisions.** Insert exactly the file's `decisions` list. Never run the save flow's decision
   creation while seeding. Each check's risk snapshot comes from replaying `assess` in time order.
4. **Speed.** Rendering about 50 photos takes about 40 s.
   - Cache rendered photos in `data/cache/seed-photos/`, keyed by the photo parameters, so
     re-seeding takes seconds.
   - Tests seed once per session into a temp data folder (`HATCHERY_DATA_DIR`) and reuse a shared
     cache.

T-03's demo-live check uses seed 2031, which is byte-identical to `fixtures/demo/t03-today.jpg`.

**Photos**:

| Folder | What | Where it can be used |
|---|---|---|
| `fixtures/slides`, `fixtures/demo` | Synthetic, with ground truth | Tests and the demo. Show a "Synthetic sample" badge |
| `fixtures/real/j006` | 30 real microscope photos with no license | Tests only. Never in the UI, the video or git |
| `fixtures/sources/README.md` | Openly licensed photos and how to fetch them | Optional; not needed for the MVP |

**Honesty rules**: never present example or synthetic numbers as real hatchery results in the app,
the video or the YC application. The UI keeps the "Example data" badge visible while example rows
exist.

---

## 13. Acceptance tests

**Engine** (`tests/test_analysis.py`, on `fixtures/slides` + `fixtures/demo`). A truth larva counts
as found when its (x, y) is inside a detection's contour (`pointPolygonTest ≥ 0`).
- [ ] Total count within ±5% of truth on every slide
- [ ] Dead larvae (pooled): precision ≥ 0.9 and recall ≥ 0.9
- [ ] Abnormal larvae (pooled): precision ≥ 0.75 and recall ≥ 0.75
- [ ] Shell length MAE ≤ 4 µm (calibrated slides, singles not touching the edge)
- [ ] Grid spacing within 1% of 625 px on gridded slides; no grid found on the others
- [ ] ≤ 1.0 s per slide
- [ ] The test prints a table: slide, count error, dead P/R, abnormal P/R, length MAE, ms

**Real photos** (`tests/test_j006.py`, skipped if the folder is missing):
- [ ] The non-ignored count equals `labels.json` `larvae_whole` on ≥ 20 of 30 images. The labels
      were counted by eye, so if this still fails after the tuning time box, report the score and
      move on.

**Rules** (`tests/test_rules.py`):
- [ ] Every signal at, just under and just over each threshold
- [ ] Every rung of the ladder and every pattern
- [ ] `assess` ignores checks after `upto`
- [ ] The exact reason texts for the full seed:

  | Tank | Reason |
  |---|---|
  | T-02 | "Size spread is widening: CV 0.21, up from 0.14 at the last check." |
  | T-03 | "Dead larvae 24%, up from 9% at the last check. Growth has stalled." |
  | T-04 | "Line 2 water is corrosive (Ω 1.4). Abnormal shells are up to 19%." |
  | T-05 | "Line 2 water is corrosive (Ω 1.4). Abnormal shells are up to 13%." |
  | T-06 | "On line 2 (Ω 1.4). Larvae look normal so far." |
  | T-10 | "Growth is 4.1 µm a day, below the 9 expected. Guts look light." |

**Seed story** (`tests/test_seed_story.py`):
- [ ] Demo and full modes match `expected` in the seed file: levels, patterns, pending decisions
      and headline
- [ ] Full mode: Larvae in hatchery "135.6M", average survival 65%, 7 decisions waiting, and the
      exact summary paragraph from §7.6

**API** (`tests/test_api.py`), on a demo-seeded temp DB:
- [ ] No API response ever contains `sk-ant` (run with a fake key set)
- [ ] Analyze `t03-today.jpg`, then save the check to T-03 with line 1's last water readings.
      T-03 becomes critical, its pattern is
      bacterial, and it has 3 new pending decisions (isolate, sample_vibrio, restock)
- [ ] Approve, then undo, works
- [ ] Saving the same check twice doesn't duplicate decisions

**Manual (before recording)**:
- [ ] Run the §1 demo end to end in under 2 minutes, with no console errors
- [ ] On `seed:full`, the Floor's layout, styling and components match
      `design/screens/home.png` side by side at 1440 px wide (numbers may differ, §4.1)
- [ ] It works at 390 px wide with no horizontal scroll
- [ ] With no API key, there are no Claude buttons and nothing breaks

---

## 14. Build plan (deadline: YC application, Mon Nov 2, 8 pm PT; code freeze Mon 2 pm PT)

| # | Phase | Time box | Done when |
|---|---|---|---|
| 0 | Scaffold: backend (uv, FastAPI, SQLModel, health), frontend (Vite, React, TS, Tailwind tokens, fonts, app shell from the design), root scripts | 45 min | `npm run dev` shows the empty shell; `/api/health` is ok |
| 1 | Analysis engine + tests (§5, §13 engine and J006) | 2.5 h | Engine tests pass; the metrics table is printed |
| 2 | Data model, tank math, rules, decisions, seed + tests (§6, §7, §9, §12, §13 rules and seed) | 2.5 h | `npm run seed:full`, then all seed tests pass |
| 3 | Floor, exactly as designed, on live data (§4.0, §4.1) | 3 h | Matches `home.png` side by side; approve, dismiss and undo work |
| 4 | New check: upload, review, correct, estimate, water, save (§4.2, §4.3, §10) | 3.5 h | The demo steps 2–5 work; API tests pass |
| 5 | Claude: second opinion + explain + budget guard (§8) | 1 h | Works with a key; hidden without one |
| 6 | Tank page, Decisions, Photo library, Tanks, Checks (§4.4–4.7) | 3 h | Every nav item works |
| 7 | Polish: phone width, empty states, demo rehearsal, record the video | 2 h | Manual checklist done |

**If behind, cut in this order**:
1. Tanks and Checks list pages (point their nav items at the Floor table)
2. Photo library (show a simple grid instead)
3. Explain
4. Tank charts beyond Survival and Shell length
5. Zoom/pan (keep Fit plus click-to-enlarge)
6. Phone polish

**Never cut**: the T-03 demo flow, corrections, the Floor's fidelity, or the example-data labels.

### Prompts to paste into Claude Code (one per phase)

**Phase 0**
> Read SPEC.md and CLAUDE.md fully. Do phase 0 from §14: scaffold `backend/` with uv (Python
> 3.12; FastAPI, uvicorn, opencv-python-headless, numpy, pillow, sqlmodel, python-multipart,
> python-dotenv, anthropic; dev: pytest, httpx, ruff) and `frontend/` with Vite + React + TS +
> Tailwind v4 + React Router + TanStack Query + Geist fonts. Add the root package.json scripts
> from §2 exactly. Put the design tokens from design/README.md in `frontend/src/styles/tokens.css`
> and build the app shell (sidebar + main panel header) from design/html/home.html with static
> placeholder content. Add `concurrently` (root) and `@playwright/test` (frontend) as dev
> dependencies, run `npx playwright install chromium`, and make `npm run setup` work on a fresh
> clone. Add backend/tests/conftest.py that blanks ANTHROPIC_API_KEY and points
> HATCHERY_DATA_DIR at a temp folder. Stop when `npm run dev` shows the shell at localhost:5173
> and `/api/health` returns ok. Commit.

**Phase 1**
> Do phase 1: implement `backend/app/analysis` exactly as SPEC §5 (pure functions, every number
> in `EngineParams` in config.py). Write tests/test_analysis.py and tests/test_j006.py per §13
> using fixtures/slides, fixtures/demo and fixtures/real/j006. Run them, print the metrics
> table, and tune only parameters (not the tests) until they pass. Time-box tuning to 60 minutes:
> if a target still fails, stop and show me the table. Write any debug images only under data/
> (never next to fixtures/real). Commit.

**Phase 2**
> Do phase 2: SQLModel tables (§9), `rules/` (§6, §7: series, signals, ladder, patterns, texts,
> actions, line alerts, history grid) as pure functions with tests/test_rules.py, the decision
> service, and `app/seed.py` that loads seed/example_hatchery.json per §12 (demo mode by
> default, --full, --reset; photos via tools/gen_slides.make_slide). Write
> tests/test_seed_story.py against the file's `expected` block and the exact summary sentence in
> §7.6. Follow the seeding rules in §12 exactly: keep the file's live_est, insert only the
> file's decisions, snapshot risk by replaying assess, and cache rendered photos. Make all tests
> pass. Commit.

**Phase 3**
> Do phase 3: `GET /api/floor` and the Floor screen (§4.0, §4.1), matching
> design/screens/home.png and design/html/home.html exactly: summary, Act now/Monitor chips,
> metrics, floor plan (static parts from design/source/Main.dc.html, tanks from data), table
> view, Last 14 days grid, inspector with photo outlines from detections, condition table,
> survival chart and decisions with approve/dismiss/undo. Run `npm run seed:full`, screenshot
> the page at 1440px (Playwright) and compare it with home.png; fix differences. Commit.

**Phase 4**
> Do phase 4: the New check flow (§4.2), check detail (§4.3) and their endpoints (§10): upload or
> sample slide → analyze → SVG overlay → popover corrections with keys → live summary →
> estimate → water readings with "Use these" → save → rules → decisions → redirect to the Floor
> with a toast. Write tests/test_api.py (§13; the save posts line 1's last water readings).
> Then run the demo steps 2–5 from §1 yourself on
> a demo seed and fix anything awkward. Commit.

**Phase 5**
> Do phase 5: Claude features per §8 with the anthropic SDK (structured output via
> messages.parse), caching, the daily cap, the call log, and UI for Ask Claude and Explain.
> Everything hides when ANTHROPIC_API_KEY is missing. Only services/claude.py reads the key (as
> SecretStr). Never read or print .env. Test once with my key on t03-today.jpg and tell me the
> token counts. Commit.

**Phase 6**
> Do phase 6: tank page, Decisions, Photo library (match design/screens/photo-library.png),
> Tanks and Checks pages (§4.4–4.7). Commit.

**Phase 7**
> Do phase 7: responsive pass at 390 px and 900 px, empty and error states, focus states, then
> run the full §13 manual checklist and list anything still off. Commit.

---

## 15. After YC (not now)
A trained segmenter fed by corrected detections, multiple users and login, a hosted pilot, probe
CSV import, a backtest of the rules on real hatchery logs, an offline capture queue, seed counting,
and the "Autopilot" dosing integration.
