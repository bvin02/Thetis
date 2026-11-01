# Thetis demo script

Follows the six steps in SPEC §1. About 2 minutes. Every click is listed.

## Before each take

1. Stop the app if it's running (Ctrl+C), then:
   ```bash
   npm run seed
   npm run dev
   ```
2. Open http://localhost:5173 in a window about 1440 px wide.
3. **Re-seed on the day you record.** The example data is relative to the day it was seeded, so "Today" and
   "Day 9" drift otherwise.
4. **Record after 8:40 AM.** The example checks are timed 7:55–8:15 AM today. Earlier than that, they show times
   that haven't happened yet. After 2:00 PM, the Next check metric reads "S-01 · Overdue", which is correct but
   worth knowing about.

Say out loud that this is example data and a synthetic slide. The app labels both ("Example data", "Synthetic
sample"). Don't present these numbers as real hatchery results in the video or the YC application.

## 1. The Floor

You see **"2 tanks need attention now"**.

- Read the paragraph: "Line 2 water has been corrosive since yesterday. It now affects T-04 and T-05, and T-06 is
  on the same line."
- Point at **Act now**: T-04 and T-05, At risk, Corrosive water.
- Hover **T-04** on the floor plan to show the tooltip and the orange line 2 pipe.

## 2. New check for T-03

1. In the **Monitor** row, click the chip **T-03 Watch Slow growth**. The inspector on the right switches to T-03.
2. Click **New check** (black button, top right). The Tank field already says T-03.
3. Click **Use a sample slide**, then **T-03 today**.
   (Or drag `fixtures/demo/t03-today.jpg` from Finder onto the drop zone. It's labelled the same way.)

In under a second every larva is outlined: green live, orange abnormal, red dead. Three carry a **?**: those are
the ones the counter is unsure about. Counts read Live 43, Abnormal 5, Dead 14.

## 3. Fix a wrong call, then ask Claude

**Fix the missed shell:**

1. Find the faint, empty shell with no outline: upper right of the photo, sitting on the right-hand vertical grid
   line, about 40% of the way down.
2. Click **Add larva** (top left of the photo), then click that shell. A popover opens.
3. Press **3** on the keyboard (or click **Dead**). Dead goes from 14 to **15**, and 23% to **24%**.
4. Press **Esc**.

**Ask Claude:**

1. In the right column, under Counts, the note reads "Sends 3 small crops to Claude." Click **Ask Claude**.
2. Three opinions appear, each with a one-line reason. Click **Accept all**.
3. The right column now says "Nothing left to check."

## 4. Water and save

1. Under **Water readings**, click **Use these**. The line's last readings fill in (Ω 2.9, pH 7.96).
2. Click **Save check**.

## 5. Back on the Floor

- Toast: **"Check saved. T-03 is now Critical. 3 decisions waiting."**
- Headline: **"3 tanks need attention now"**.
- New last sentence in the paragraph: "Separately, T-03 shows a pattern that matches a bacterial outbreak."
- In the inspector, point at: **Pattern matches a bacterial outbreak**, the "Rules-based" tag, and the **Condition**
  table (dead larvae up from 9%, growth far below 9 µm/day, water fine at Ω 2.9).
- Scroll to **Recommended actions** and click **Approve isolation**. It turns to a green "Isolation approved". Say:
  a person decides, nothing acts on equipment.

## 6. The tank page

1. Scroll to the bottom of the inspector and click **Open T-03**.
2. Trends opens on **Survival**. Click **Shell length**: the dashed line is the expected 9 µm/day.
3. Point at the **Checks** table: the red and orange values are the warning signs.
4. Click **Explain**, under Risk forecast. Three plain sentences appear, captioned "Written by Claude from the
   numbers above".

## If something goes wrong

| What you see | What to do |
|---|---|
| No **Ask Claude** or **Explain** button | The key in `.env` wasn't found. Check the line, then restart `npm run dev`. The rest of the demo works without it |
| "Daily Claude limit reached" | Raise `CLAUDE_DAILY_LIMIT` in `.env` and restart, or wait until tomorrow |
| "Can't reach the Thetis server" | `npm run dev` isn't running |
| T-03 is already Critical at the start | You didn't re-seed. Stop the app and run `npm run seed` |

The Ask Claude answer for this slide is stored, and re-seeding keeps it. Repeat takes get it instantly and free.
Explain makes one small paid call per check the first time you click it.
