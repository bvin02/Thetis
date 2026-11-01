# Setup: exact steps

You need **no new logins and no more photos**. The only secret is the Anthropic API key you already
have, and the app works without it (Claude features hide).

## 1. Install the tools (once, about 5 minutes)
| Tool | Mac | Windows (PowerShell) | Check |
|---|---|---|---|
| **uv** (installs Python for you) | `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `uv --version` |
| **Node.js 22 or newer** | `brew install node` or the LTS installer from nodejs.org | LTS installer from nodejs.org | `node -v` |
| git, Claude Code | you have these | | `claude --version` |

Open a new terminal after installing, so the commands are found.

## 2. Get the code

The repo already has everything: the app, the example data, the test photos. On a fresh clone, run:
```bash
npm run setup
```

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

## 4. Run it

```bash
npm run seed    # loads the example hatchery (first run renders photos, about 15 s)
npm run dev     # then open http://localhost:5173
```

| Command | What it does |
|---|---|
| `npm run seed` | Demo state: T-03 at Watch, ready for the live upload. Stop `npm run dev` first |
| `npm run seed:full` | The designed state: T-03 already Critical |
| `npm test` | Backend tests |

`DEMO.md` is the click-by-click demo script.

## What's in the repo
| Path | What |
|---|---|
| `backend/`, `frontend/` | The app |
| `PROGRESS.md` | What was built, test results and decisions |
| `DEMO.md` | Click-by-click demo script |
| `SPEC.md` | The build spec |
| `CLAUDE.md` | Rules Claude Code follows in every session |
| `design/` | Final UI: screenshots, static HTML with exact CSS, design source, tokens |
| `seed/example_hatchery.json` | The example hatchery (12 tanks, 50 checks), already checked against the rules |
| `tools/gen_slides.py` | Makes synthetic microscope photos with known answers |
| `fixtures/slides/`, `fixtures/demo/` | Synthetic test photos plus their answer files |
| `fixtures/real/j006/` | 30 real photos for tests only. **No license: never show or post them.** A copy is committed at the owner's request |
| `fixtures/sources/` | Optional: where more real photos come from, their licenses, and a fetch script. Not needed |
| `.claude/settings.json` | Stops Claude Code from reading `.env` |

## If something goes wrong
- **`uv` or `node` not found**: open a new terminal window, then check again.
- **Fresh clone on another computer**: run `npm run setup` once.
- **Port 5173 or 8000 busy**: close the old `npm run dev` (Ctrl+C), or restart the terminal.
- **Claude features don't show**: check the key name in `.env` and restart `npm run dev`.
- **Pages hang at random on a Mac that's been up over 49 days** (check with `uptime`): reboot. It's a macOS bug, and closed
  connections never clear until you do.
- **Want more real photos** (optional): `bash fixtures/sources/fetch_sources.sh`. The ZooCAMNet
  part needs a free Hugging Face account.
