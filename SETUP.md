# Setup: exact steps

You need **no new logins and no more photos**. Everything the build needs is in this pack. The
only secret is the Anthropic API key you already have.

## 1. Install the tools (once, about 5 minutes)
| Tool | Mac | Windows (PowerShell) | Check |
|---|---|---|---|
| **uv** (installs Python for you) | `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `uv --version` |
| **Node.js 22 or newer** | `brew install node` or the LTS installer from nodejs.org | LTS installer from nodejs.org | `node -v` |
| git, Claude Code | you have these | | `claude --version` |

Open a new terminal after installing, so the commands are found.

## 2. Put the pack in your repo
Unzip `hatchery-starter.zip`, then copy everything **including hidden files** (`.gitignore`,
`.env.example`, `.claude/`) into the root of your repo:
```bash
cd ~/Downloads && unzip hatchery-starter.zip          # creates ~/Downloads/hatchery-starter/
cp -R ~/Downloads/hatchery-starter/. ~/path/to/your-repo/
cd ~/path/to/your-repo
```
On Windows: right-click the zip, choose **Extract All**, then copy everything inside
`hatchery-starter` into your repo folder. Files starting with a dot show normally on Windows.

If your repo already had a `.gitignore`, this replaces it. The new one covers `.env`, Python,
Node, `data/` and the unlicensed photos.

## 3. Check your API key is safe (2 minutes)
1. Open `.env` in your editor. The line must be named exactly `ANTHROPIC_API_KEY=sk-ant-...`.
   Then copy the other two lines from `.env.example` into it (`CLAUDE_MODEL`,
   `CLAUDE_DAILY_LIMIT`).
2. `git check-ignore .env` must print `.env`.
3. `git log --all --oneline -- .env` must print **nothing**.
   - If it prints any commit, the key is in your git history. In the Claude Console, create a new
     key, delete the old one, and put the new one in `.env`.
4. In the Claude Console, go to **Billing** (platform.claude.com/settings/billing), then
   **Spend limits**, and set a low monthly limit such as $25.
5. Don't `export` or `source` the key in the terminal where you run `claude`. If Claude Code ever
   asks whether to use an API key, answer **No**, so it keeps using your Max plan.

## 4. Commit the starter files
```bash
git add -A
git status        # .env and fixtures/real/ must NOT be in the list
git commit -m "Add spec, design, seed data and test fixtures"
```

## 5. Build with Claude Code, one phase at a time
```bash
claude
```
1. Paste the **Phase 0** prompt from `SPEC.md` §14.
2. When it stops, run `npm run dev` and open http://localhost:5173 to look.
3. Then paste the next phase's prompt.

After each phase:
- run `npm test`
- look at the app
- ask Claude Code to commit

If a phase runs over its time box, use the cut list in §14.

Suggested schedule (the YC deadline is Mon 8 pm PT = 11 pm ET; code freeze Mon 2 pm PT = 5 pm ET):
- **Tonight:** phases 0 and 1 (scaffold and photo analysis)
- **Sunday:** phases 2–5 (rules and seed, Floor, New check, Claude)
- **Monday morning:** phases 6–7, then record the demo
- **Monday afternoon:** write the application

## 6. Record the demo
Stop `npm run dev` first (Ctrl+C), then:
```bash
npm run seed       # T-03 starts at Watch; your upload in the video makes it Critical
npm run dev
```
Follow the demo script in `SPEC.md` §1.
- Upload `fixtures/demo/t03-today.jpg`, or use **Use a sample slide**. It is a labelled synthetic
  slide; say so in the video.
- `npm run seed:full` instead shows the finished designed state (T-03 already Critical).

## What's in the pack
| Path | What |
|---|---|
| `SPEC.md` | What to build, phase by phase, with the prompts to paste |
| `CLAUDE.md` | Rules Claude Code follows in every session |
| `design/` | Final UI: screenshots, static HTML with exact CSS, design source, tokens |
| `seed/example_hatchery.json` | The example hatchery (12 tanks, 50 checks), already checked against the rules |
| `tools/gen_slides.py` | Makes synthetic microscope photos with known answers |
| `fixtures/slides/`, `fixtures/demo/` | Synthetic test photos plus their answer files |
| `fixtures/real/j006/` | 30 real photos for tests only. **No license: never commit, show or post them** (gitignored) |
| `fixtures/sources/` | Optional: where more real photos come from, their licenses, and a fetch script. Not needed |
| `.claude/settings.json` | Stops Claude Code from reading `.env` |

## If something goes wrong
- **`uv` or `node` not found**: open a new terminal window, then check again.
- **Fresh clone on another computer**: run `npm run setup` once (it exists after phase 0).
- **Port 5173 or 8000 busy**: close the old `npm run dev` (Ctrl+C), or restart the terminal.
- **Claude features don't show**: check the key name in `.env` and restart `npm run dev`.
- **Want more real photos** (optional): `bash fixtures/sources/fetch_sources.sh`. The ZooCAMNet
  part needs a free Hugging Face account.
