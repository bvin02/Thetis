# Thetis demo script

Two parts, about 4 minutes. Every click is listed.

1. **Photo to count:** a tech uploads a microscope photo and Thetis counts and classifies every larva.
2. **What to do about it:** Thetis reads all the data, says what could crash and how to head it off, and finds where
   to raise yield.

## Before each take

1. **Reboot first if your Mac has been up more than 49 days.** Check with `uptime`. A macOS bug stops closed connections
   from ever clearing after 49.7 days, so pages hang at random, and only a reboot fixes it. See
   [If something goes wrong](#if-something-goes-wrong).
2. Stop the app if it's running (Ctrl+C), then:
   ```bash
   npm run seed
   npm run dev
   ```
3. Open http://localhost:5173 in a window about 1440 px wide.
4. **Re-seed on the day you record.** The example data is relative to the day it was seeded, so "Today" and
   "Day 9" drift otherwise.
5. **Record after 8:40 AM.** The example checks are timed 7:55–8:15 AM today. Earlier than that, they show times
   that haven't happened yet. After 2:00 PM, the Next check metric reads "S-01 · Overdue", which is correct but
   worth knowing about.
6. **Rehearse once on the day.** Claude's answers are stored by the data they were given, so a rehearsal makes the real
   take instant and free. See [Live or stored](#live-or-stored).

Say out loud that this is example data and a synthetic slide. The app labels both ("Example data", "Synthetic
sample"). Don't present these numbers as real hatchery results in the video or the YC application.

---

# Part 1: Photo to count

## 1. The Floor

You see **"2 tanks need attention now"**.

- Read the paragraph: "Line 2 water has been corrosive since yesterday. It now affects T-04 and T-05, and T-06 is on
  the same line."
- Read the line under it: **"Do next: Buffer line 2 water to bring Ω aragonite to 3 or higher."**
- Point at the three rows: **Act now**, **Monitor**, and **Raise yield**.
- Hover **T-04** on the floor plan to show the tooltip and the orange line 2 pipe.

## 2. New check for T-03

1. In the **Monitor** row, click the chip **T-03 Watch Slow growth**. The panel on the right switches to T-03.
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
- The **Do next** line now reads "Isolate T-03. Use separate screens, buckets and hoses."
- In the panel on the right, point at **Pattern matches a bacterial outbreak** and the "Rules-based" tag.
- Under **Recommended actions**, each step says how: the first one, to clean shared gear with sodium hypochlorite.
  Click **Approve isolation**. It turns to a green "Isolation approved". Say: a person decides, nothing acts on
  equipment.

That's the first job done: photo in, counts out, the tank's status updated.

---

# Part 2: What to do about it

## 6. Today's brief

Click **Advisor** in the sidebar.

- The headline says it all: **"3 risks could turn into a crash. 3 ways to raise yield."** Under it: larvae in tanks at
  risk, and how many are on course to reach the eyed stage against how many could.
- **Today's brief**, labelled "Written by Claude". If this data hasn't been read before, it says "Claude is reading 44
  checks across 10 running tanks, 1 past batch and the decision log", shows which tanks it's looking at, and writes
  the brief in about 30 seconds. The rest of the page is already there, because the rules don't need Claude.
- Read the headline and **Do these first**. Say: this is Claude reading every check in the hatchery, and every number it
  cites comes from your records.

## 7. Crash risks, and how to head them off

**T-03** is open at the top of **Crash risks**.

- Three small charts: dead larvae, growth and gut fullness, each with its target dashed.
- "High chance this batch crashes in the next 1–3 days if nothing changes", and why, in plain words.

Scroll to **Line 2 water is corrosive** and click it open. **This is the example that matters most:**

- 56.9M larvae at stake, and at today's rates none of these tanks reach the eyed stage within 21 days.
- Under **What to do**, the dose: **16 g of sodium carbonate per 1,000 L, 96 g across T-04, T-05 and T-06**, taking Ω from
  1.4 to 3.0 and pH from 7.62 to 7.94. Calculated from the water chemistry, not guessed, with a note to try it in a jar
  first.
- Change the dropdown from sodium carbonate to **sodium hydroxide**. The dose becomes **6 g per 1,000 L**, with a caustic
  warning. Say: whatever your plant uses. Change it back.
- Click **Approve buffering**.

Then the cards tagged **Found by Claude**: things no rule was written to catch. Claude's wording changes between runs,
but it has found **"T-10 looks like T-03 did before it crashed"** each time on this data. Click it open: the readings
behind it are listed, each checked against the records. Say: T-03 just crashed, and this is the next one, caught early.

## 8. Raise yield

- **Move T-07's largest larvae to setting**, open at the top: how to grade it, how much S-02 can take, and what waiting
  costs. Click **Schedule grading**.
- Click **T-02 is losing larvae 2.1× as fast as T-01** to open it: same water, so the gap is worth 1.8M eyed larvae.
- **Split T-08**: stocked at 31,000 per L against FAO's 15,000 to 20,000.
- Look for **Found by Claude** here too: on this data it spots that setting space runs out in about 3 days.
- Scroll to **Forecast to the eyed stage**: dark is on course, grey is what's possible. Line 2's tanks have no dark bar
  at all. That's the cost of doing nothing, in larvae. Say that it's a rough, rules-based estimate.

## 9. Ask Thetis

Scroll back up. On the right, click **What could crash next, and why?**, or type your own question:

- "How do I keep T-03 from spreading to other tanks?"
- "Why is T-02 losing more larvae than our best batch?"
- "What should I check first on line 2?"

Answers arrive in a few seconds, and tank names link to their pages.

## Optional: the tank page

Click any tank's name. Trends opens on **Survival**. Click **Shell length**: the dashed line is the expected 9 µm/day.
Click **Explain** for three plain sentences from Claude.

---

## Live or stored

Claude's answers are stored by the data they were given, so the same data gives the same answer, instantly and free.

| To show... | Do this | Cost |
|---|---|---|
| The brief being written live | Click **Run again** on Today's brief. It takes about 30–40 seconds | About $0.13 |
| A stored brief, with no wait | Rehearse the same clicks once first. Corrections change the numbers, so follow the script exactly | Free |
| A live chat answer | Ask something new | About $0.02–0.05 |

Re-seeding keeps the stored answers. New data, like a saved check, marks the old brief "Written before the latest
changes", and opening the Advisor runs a new one.

## If something goes wrong

| What you see | What to do |
|---|---|
| Pages hang on a spinner at random, or other apps can't connect, while Thetis isn't using any CPU | **Reboot the Mac.** If `uptime` is over 49 days, this is the macOS bug. `netstat -an \| grep -c TIME_WAIT` shows thousands of connections that never clear |
| No **Today's brief**, **Ask Thetis**, **Ask Claude** or **Explain** | The key in `.env` wasn't found. Check the line, then restart `npm run dev`. Everything else works without it, including every risk, dose and suggestion |
| "Daily Claude limit reached" | Raise `CLAUDE_DAILY_LIMIT` in `.env` and restart, or wait until tomorrow. The last brief stays on screen |
| "Can't reach the Thetis server" | `npm run dev` isn't running |
| T-03 is already Critical at the start | You didn't re-seed. Stop the app and run `npm run seed` |
| You changed a chemical and forgot | Re-seeding sets it back to sodium carbonate |
