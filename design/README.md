# Design: final UI for Hatchery Autopilot

The UI is approved. Build it to match these files. Screens that aren't drawn here (New check, Tank
page, Decisions, Tanks, Checks) reuse the same tokens and components.

## Files
| File | Use it for |
|---|---|
| `screens/home.png` | Floor at 1440 px wide, full example data, T-03 selected |
| `screens/home-t04-selected.png` | Floor with T-04 selected (line alert, line-scoped decisions) |
| `screens/home-table-view.png` | Floor with the Plan / Table toggle on Table |
| `screens/home-phone.png` | Floor at 390 px wide (plan becomes a list) |
| `screens/photo-library.png` | Photo library column browser |
| `html/home.html`, `html/photo-library.html` | The same screens as static HTML with every exact CSS value. Open them in a browser and use dev tools to inspect. Hover the floor plan and the 14-day grid to see tooltips |
| `source/Main.dc.html`, `source/FileBrowser.dc.html` | Design source: markup with `{{ holes }}` and a `class Component` with the example data and interaction logic (selection, approve/dismiss/undo, plan/table toggle). Copy the floor-plan SVG (walls, labels, pipes, algae room, bench) from here |
| `source/assets/` | The photos used in the design. In the `.dc.html` files they appear as `/_blob/<id>` (map below) |

Blob map:

| Blob id | File |
|---|---|
| `c24f4a48989afd34200503c13a7b22b0` | `c-vibrio.jpg` |
| `8c64a39999e7e910aeffed4192cd3073` | `c-healthy.jpg` |
| `2d1e4e432dff2d4ae82a68dec400a1d2` | `c-omega.jpg` |
| `aa09a49851a8c00d5dc7211ff3472a11` | `c-dstage.jpg` |
| `8363ae7fd21cdba30a96f07ebf684c84` | `c-eyed.jpg` |
| `4d40417b0163cdf1b2f2d62ff8c76d99` | `t03-check.jpg` |
| `a4b1b4459a322e6889fee3acde035221` | `t03-full.jpg` |

In the app, outlines are drawn as an SVG overlay from detections; they are **not** baked into the
image the way they are in these design crops.

## Tokens (put these in `frontend/src/styles/tokens.css`)
```css
@import "tailwindcss";
@import "@fontsource-variable/geist";
@import "@fontsource-variable/geist-mono";

@theme {
  --font-sans: "Geist Variable", "Geist", ui-sans-serif, system-ui, -apple-system, sans-serif;
  --font-mono: "Geist Mono Variable", "Geist Mono", ui-monospace, monospace;

  --color-canvas: #EDF1F3;      /* page background behind the panel */
  --color-panel: #FFFFFF;
  --color-line: #E2E8EC;        /* panel and card borders */
  --color-divider: #EEF2F4;     /* rows and sections inside a card */
  --color-subtle: #F6F8F9;      /* hover and selected rows */
  --color-muted-bg: #F1F4F6;    /* segmented control track, neutral pills */
  --color-ink: #0F1A20;
  --color-ink-2: #3E4B53;
  --color-ink-3: #5F6C74;
  --color-ink-4: #66737B;
  --color-faint: #AEB9C0;       /* separators "/", disabled */
  --color-border-strong: #CCD5DB;
  --color-brand: #13557A;       /* logo, active nav icon, focus ring, links */

  --color-critical: #D93A2F;  --color-critical-text: #B42318;  --color-critical-bg: #FEF3F2;  --color-critical-border: #F2C4BF;
  --color-risk: #E0702A;      --color-risk-text: #B54708;      --color-risk-bg: #FFF6ED;      --color-risk-border: #F3D0B4;
  --color-watch: #C98A0B;     --color-watch-text: #8E6206;     --color-watch-bg: #FEF9EC;
  --color-normal-ring: #A7B3BA; --color-normal-swatch: #DCE3E7;
  --color-empty: #C7CFD4;       /* dashed */
  --color-approved: #2E7D57;  --color-approved-bg: #EEF7F1;   --color-approved-border: #A9D3B8;

  --color-larva-live: #2E8B57;
  --color-larva-abnormal: #C2620E;
  --color-larva-dead: #C2362B;

  --radius-panel: 12px;   /* main panel */
  --radius-card: 10px;    /* cards, tooltips */
  --radius-control: 8px;  /* buttons, nav items, chips, inputs */
  --radius-small: 6px;    /* badges, segmented buttons */

  --shadow-panel: 0 1px 2px rgba(15, 26, 32, 0.04);
  --shadow-nav-active: 0 1px 2px rgba(15, 26, 32, 0.06), 0 0 0 1px #E2E8EC;
  --shadow-seg-active: 0 1px 2px rgba(15, 26, 32, 0.08);
  --shadow-pop: 0 8px 24px rgba(15, 26, 32, 0.10);   /* tooltips, popovers, toasts */
}
```

## Type
| Use | Size / weight | Notes |
|---|---|---|
| Page headline ("3 tanks need attention now") | 28 / 600 | line-height 1.15, letter-spacing −0.025em, `text-wrap: balance` |
| Metric values | 20 / 600 | −0.015em, tabular numbers; unit in 13 / 400 `ink-4` |
| Section titles, inspector header text | 14–15 / 600 | |
| Body | 14 / 400 | Base size of the app |
| Secondary text, table cells, buttons | 13 / 400–500 | |
| Labels, captions, tags | 12 / 500 | `ink-4` |
| Badges | 11 / 500–600 | |
| Floor-plan labels (SVG) | 10–10.5, room titles 10 / 600 with letter-spacing 0.8 in uppercase | The only uppercase in the app |
| Tank ids | Geist Mono 13 / 600 (plan), 24 / 600 (tank page header) | |

Use tabular numbers (`font-variant-numeric: tabular-nums`) for every number that updates.

## Components (measured from the design)
- **Sidebar**: 216 px max width on the canvas, padding 16/12.
  - **Nav items**: 32 px tall, padding 0 10, radius 8, 14 px text `ink-2`, 16 px stroke icons
    (1.75). The **active** item is white with `shadow-nav-active`, `ink` text, and a `brand` icon.
    Hover is `rgba(255,255,255,.72)`.
  - **Decisions badge**: black pill, 20 px tall, 11/600 white text.
- **Main panel**: white, `margin: 8px 8px 8px 0`, border `line`, radius 12, `shadow-panel`.
  - **Header**: min 52 px tall, padding 8/28, bottom border `divider`. It holds the breadcrumb
    (13 px; parent in `ink-4`, "/" in `faint`, current page 500) and the "Example data" badge
    (11/500, `ink-4`, 1 px `line` border, radius 6, padding 2/6).
- **Buttons**:
  - **Solid**: 32 px tall, padding 0 12, radius 8, background `ink`, white 13/500 text, hover
    `#26333A`.
  - **Ghost**: white, 1 px `line` border, hover `subtle` background and `border-strong`.
  - **Link**: `brand` colour, underlined, offset 2 px.
- **Chips** (Act now / Monitor): 32 px tall, padding 0 12, radius 8, 13 px text.
  - Critical: `critical-bg` with `critical-border`. At risk: `risk-bg` with `risk-border`.
    Watch: white with `line` border.
  - Content: a status dot, the tank id in mono, the level in status text colour, then the short
    reason in `ink-3`.
  - Selected chips get `0 0 0 1.5px #0F1A20`.
- **Status pill**: tinted background with a 6 px dot and the label in status text colour. Normal
  uses `muted-bg` and `ink-2`.
- **Segmented control**: a `muted-bg` track with 2 px padding and radius 8. Buttons are 28 px tall,
  padding 0 12, radius 6, 12/500. The active button is white with `shadow-seg-active`.
- **Tooltip / popover / toast**: white, 1 px `line` border, radius 10 (8 for small ones), padding
  12, `shadow-pop`.
- **Tables**: rows at least 40 px tall, padding 6/16, 13 px text, top border `divider`. The header
  is 12/500 `ink-4`. Selected or hovered rows use `subtle`.
- **Inspector sections**: padding 16, top border `divider`, title 13–14 / 600. The right-aligned
  tag ("Rules-based") is 11/500 with a `line` border and radius 6.
- **Risk meter**: four bars labelled Normal / Watch / At risk / Critical. The current bar uses its
  status colour and the others `#E3E9EC`. The current label is 600 in status text colour.
- **Condition rows**: an 8 px severity dot, label, "Now" value (status text colour when risk or
  critical), and "Compared with" in 12 px `ink-4`, right-aligned, max width 108 px, line-height
  1.35.
- **Action rows**: a numbered 22 px circle badge (1 px `border-strong`), the title, then the CTA
  (solid, small) and Dismiss (ghost).
  - Pending: the CTA shows a spinner and is disabled until the request returns.
  - Approved: the badge becomes a check on `approved-bg` with `approved-border`, and the done text
    is `approved` green. This is the only green in the app.
  - Dismissed: a grey ×, the text "Dismissed", and Undo.
- **Floor-plan tanks**: the outline stroke encodes the level.

  | Level | Stroke colour | Width | Fill |
  |---|---|---|---|
  | Critical | `critical` | 2.75 | `critical-bg` |
  | At risk | `risk` | 2.25 | `risk-bg` |
  | Watch | `watch` | 2 | white |
  | Normal | `normal-ring` | 1.25 | white |
  | Empty | `empty` | 1.25, dashed 3 3 | white |

  Problem tanks get a 5 px dot at the top right. The selected tank gets a ring of `ink` 1.75 px at
  r + 7. Line 2's pipe and line card turn orange (`risk`) when the line alert is on.
- **14-day grid**: cells are swatches. Normal is `normal-swatch` with a `normal-ring` border;
  problems are solid status colours; empty is a dashed `empty` border. Today has a ring
  `0 0 0 1.5px #fff, 0 0 0 3px #66737B`.

## Rules
- Colour only for problems. Normal is grey. Green appears only for "approved" and for live-larva
  outlines on photos.
- Never use gradients, glows, coloured shadows, neon, emoji, illustrations or stock icons with fills.
- Every colour has a text partner: no meaning carried by colour alone.
- Focus: 2 px `brand` outline, offset 2.
- Copy: sentence case, plain words, numbers with units ("128 µm", "1.2 µm/day", "4.1M").
  - Times: "Today, 8:40 AM", "Yesterday, 4:10 PM", "Oct 29, 2:00 PM".
  - Say "pattern matches", never "diagnosis".
- Phones (≤ 660 px): the plan turns into a list (see `home-phone.png`) and tap targets are 44 px.
