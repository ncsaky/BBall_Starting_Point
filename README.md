# NBA GM Sandbox

A local NBA front-office simulator with starting rosters and pick rights updated through **October 13, 2026**. New saves begin in the 2026 offseason with the 2026-27 league universe. The Python engine powers both the detailed CLI and the browser GUI: roster building, staff decisions, trades, free agency, draft scouting, injuries, development, morale, social reaction, multiplayer leagues, fantasy drafts, and sandbox season simulation.

Current status: **private friends-and-family beta candidate**. Self-contained Mac downloads are available for private testing and bug reports. This is not a broad public release yet.

**Private Mac download:** self-contained betas are built with
`./scripts/build_macos_beta.sh --version 0.1.0-beta.10 --arch arm64` or `--arch x86_64` and written to `dist/macos/`. Both beta.10 ZIPs passed isolated packaged acceptance; Intel execution was tested under Rosetta. Friends extract
the versioned ZIP and double-click `NBA GM Sandbox.app`; Python, Git, Terminal,
and this repository are not required. Choose Apple Silicon (arm64) or Intel
(x86_64); both target macOS 11.0 or later. See [Mac beta packaging and verification](docs/MACOS_BETA.md)
and [friend launch instructions](packaging/macos/START%20HERE.txt).

**Windows packaging:** a separate native x64 launcher, portable ZIP recipe and
manual acceptance workflow are now in place. **No Windows executable has been
built or verified yet.** Build from the complete working tree on Windows, then
run the extracted-artifact checks before sharing. See [Windows beta](docs/WINDOWS_BETA.md).

## Should You Play This Build?

Yes, if you want to run a deep NBA GM sandbox and you are okay with a few rough edges. The core loop is now playable:

- Create a save, pick or randomize a team, and sim through multiple seasons.
- Manage trades, extensions, free agency, staff, rotations, and a visual Starting 5.
- Watch injuries, morale, social media, press conferences, league events, playoffs, lottery, draft night, rookies, and offseason rollover.
- Use the full ASCII loading-screen animation if optional assets are installed.

The game is best described as a **friends-and-family beta**: ready for focused playtesting, with balance and clean-machine compatibility still needing feedback before a broad public release.

## Local GUI

The browser GUI runs on top of the same Python engine and save format as the CLI. It includes the command dashboard, immersive journey view, phase-specific draft/playoff/free-agency rooms, trade builder/finder, team and league views, and save management.

After installing with `python -m pip install -e .`, run:

```bash
nba-gm-data-gui --root . --open
```

If the browser does not open automatically, go to `http://127.0.0.1:8765`.

The downloadable beta keeps this ordinary launch on loopback. Its API validates
Host/Origin, obtains a fresh browser-protection token at runtime, limits JSON and
backup uploads, and contains GUI save paths within the configured save directory.
See [local API security and compatibility](docs/LOCAL_API_SECURITY.md) for HTTP
client requirements and explicit network-test boundaries.

### Multiplayer Alpha

The GUI now supports one authoritative shared league for **2–30 human GMs**:

- Create a lobby and share its six-character join code.
- Every manager claims a different team; AI controls unclaimed teams.
- Configure weekly or monthly action windows and a 1–20 season dynasty.
- Mark ready to advance early, or let the shared clock advance everyone together.
- Human actions use revision checks and idempotency keys, so stale browsers cannot overwrite newer league state.
- Human-to-human trades wait for explicit approval from the other GM and are revalidated against the live save before execution.
- Draft, free agency, and playoff windows use coordinated league clocks.
- Fantasy-draft leagues use a per-pick clock and stop automatically on each human manager's turn.
- The final dynasty table ranks championships first, then regular-season wins.

For a same-network test, the host runs:

```bash
nba-gm-data-gui --root . --host 0.0.0.0 --port 8765 --public-multiplayer-only
```

Friends on that network open `http://HOST-LAN-IP:8765`. Do not expose this development server directly to the public internet without HTTPS and the deployment protections described in [docs/MULTIPLAYER_ARCHITECTURE.md](docs/MULTIPLAYER_ARCHITECTURE.md) and [docs/HOSTING.md](docs/HOSTING.md).

For a temporary internet test with friends, install Cloudflare's tunnel client once:

```bash
brew install cloudflared
```

Then run:

```bash
./scripts/run_public_multiplayer_test.sh
```

Share the temporary `trycloudflare.com` URL printed in Terminal. This mode intentionally hides local saves and blocks direct single-player API actions. It is for short tests, not permanent hosting.

### Fantasy Draft

Choose **Fantasy Draft** when creating a solo save or multiplayer lobby:

- The 30-team order is randomized from the save seed.
- Teams select 15 players apiece in a 450-pick snake draft.
- Every player keeps the contract, age, health, traits, and development state already modeled by the game.
- AI boards blend the reviewed league-wide OVR prior, current engine impact, contract surplus and term, age, health, playoff translation, and roster fit.
- Position and skill redundancy matter as rosters form, so a team with multiple creator guards begins prioritizing wings, size, defense, spacing, or rebounding.
- When the draft finishes, each franchise has exactly 15 unique players.
- Prior real-world pick trades and conditions are cleared; every franchise begins with one own R1 and R2 in each modeled draft year.
- Multiplayer fantasy drafts pause on human turns, auto-run intervening AI picks, and support one clock extension per pick.

## Easiest Setup For Friends

If you are testing for the first time, do these steps in order.

1. Install **Git**.
2. Install **Python 3.11 or newer**.
3. Open Terminal or PowerShell.
4. Clone the repo.
5. Create the Python environment.
6. Install the game.
7. Install optional loading assets.
8. Run `nba-gm-data play --root .`

Detailed commands are below.

## Setup From Zero

You run this game from a terminal. On macOS that app is called **Terminal**. On Windows, use **PowerShell** or **Windows Terminal**.

Before cloning the repo, install:

- **Git**: needed to download the game from GitHub.
- **Python 3.11 or newer**: needed to run the game.
- **ffmpeg**: optional, only needed if you want to build or rebuild the ASCII loading-screen animation cache from local video files.

### macOS Setup

Open **Terminal** and run:

```bash
git --version
python3 --version
```

If `git` is missing, install Apple's command line tools:

```bash
xcode-select --install
```

If `python3 --version` is older than Python 3.11, install the latest Python 3 release from [python.org](https://www.python.org/downloads/), then close and reopen Terminal.

Optional, for rebuilding loading animations:

```bash
brew install ffmpeg
```

If `brew` is missing, install Homebrew from [brew.sh](https://brew.sh/) first.

Choose where the game should live, then clone it:

```bash
cd ~/Documents
git clone https://github.com/ncsaky/BBall_Starting_Point.git
cd BBall_Starting_Point
```

Create the local Python environment and install the game:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Install the prebuilt loading-screen assets:

```bash
nba-gm-data install-assets --root .
```

If that download fails because the repo is private, open the GitHub Releases page in your browser, download `loading-assets-v1.zip`, then run:

```bash
nba-gm-data install-assets --root . --zip ~/Downloads/loading-assets-v1.zip
```

Start the game:

```bash
nba-gm-data play --root .
```

If you get stuck, take a screenshot of the terminal and send it with the last command you ran.

### Windows Setup

Install:

- Git for Windows from [git-scm.com](https://git-scm.com/download/win)
- Python 3.11+ from [python.org](https://www.python.org/downloads/windows/)

During Python installation, check **Add python.exe to PATH**.

Open **PowerShell** and check:

```powershell
git --version
py --version
```

Choose where the game should live, then clone it:

```powershell
cd $HOME\Documents
git clone https://github.com/ncsaky/BBall_Starting_Point.git
cd BBall_Starting_Point
```

Create the local Python environment and install the game:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Install the prebuilt loading-screen assets:

```powershell
nba-gm-data install-assets --root .
```

If that download fails because the repo is private, open the GitHub Releases page in your browser, download `loading-assets-v1.zip`, then run:

```powershell
nba-gm-data install-assets --root . --zip "$HOME\Downloads\loading-assets-v1.zip"
```

Start the game:

```powershell
nba-gm-data play --root .
```

If `nba-gm-data` is not found, make sure the virtual environment is active. You should see `(.venv)` at the start of the terminal prompt.

If PowerShell blocks activation with a script policy warning, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then close PowerShell, reopen it, return to the repo folder, and run:

```powershell
.venv\Scripts\activate
```

## Quick Start For Returning Testers

Open a terminal in this folder.

### macOS

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
nba-gm-data play --root .
```

If `python3 --version` is older than Python 3.11, install Python 3.11+ from [python.org](https://www.python.org/downloads/) and rerun the commands.

### Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
nba-gm-data play --root .
```

If the `py -3.11` command is missing, install Python 3.11+ from [python.org](https://www.python.org/downloads/) and check “Add Python to PATH” during installation.

## Loading-Screen Assets

The game can run without loading-screen assets, but testers will get the intended full ASCII highlight loading screens after installing `loading-assets-v1.zip`.

The easiest command is:

```bash
nba-gm-data install-assets --root .
```

If GitHub asks you to sign in, download `loading-assets-v1.zip` from the repo's Releases page in your browser and install it from your Downloads folder:

```bash
nba-gm-data install-assets --root . --zip ~/Downloads/loading-assets-v1.zip
```

On Windows PowerShell:

```powershell
nba-gm-data install-assets --root . --zip "$HOME\Downloads\loading-assets-v1.zip"
```

The asset zip installs pre-rendered loading-screen frames into `.cache/`, so testers do not need `ffmpeg` or the original video file.

## Optional Local LLM Narrative

The game can run without any AI writing tools. New saves try to use local AI writing by default, but social media and press conferences automatically fall back to built-in writing if Ollama is not running or the selected model is unavailable.

For richer local social posts and press-conference questions, optionally install **Ollama** from [ollama.com](https://ollama.com/) and pull a local model:

```bash
ollama pull llama3.1
```

Then launch the game and open **Narrative settings** from the main menu if you need to change the model, test the connection, or adjust the wait time. The game talks to Ollama at `http://localhost:11434` by default. If you already have a different local model installed, run `ollama list` and set the in-game model name to one of those installed models.

You can also configure it from the terminal:

```bash
nba-gm-data narrative-settings --root . --save saves/YOUR_SAVE.json --enable --provider ollama --model llama3.1 --test
```

This feature is optional and sandboxed. The model receives only the current sim context that the game provides, and the game falls back to built-in writing if Ollama is not running, times out, or returns malformed text.

## Optional Custom Loading-Screen Videos

Large video files are intentionally not stored in normal Git history because GitHub blocks large repository files. To use custom ASCII loading screens, create this folder after cloning:

```bash
mkdir -p "Animation Videos"
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "Animation Videos"
```

Put your local `.mp4` files inside `Animation Videos/`. The game automatically prefers the largest MP4 in that folder for loading-screen animation caches.

To rebuild the loading animation cache from your local videos:

```bash
nba-gm-data animation-cache --root . --segments 8
```

That command requires `ffmpeg`. The generated cache lives in `.cache/` and is ignored by Git.

## Maintainer: Publish Loading Assets

After rebuilding local loading-screen caches, package them for GitHub Releases:

```bash
python scripts/package_loading_assets.py --root .
```

That writes `dist/loading-assets-v1.zip`. Upload that zip to the GitHub Release tagged `loading-assets-v1`.

With GitHub CLI installed and authenticated, the release command is:

```bash
gh release create loading-assets-v1 dist/loading-assets-v1.zip --title "Loading assets v1" --notes "Pre-rendered ASCII loading-screen cache."
```

Without GitHub CLI, go to the repo on GitHub, open **Releases**, draft a release for tag `loading-assets-v1`, attach `dist/loading-assets-v1.zip`, and publish it.

## Starting A Save

The interactive launcher lets you pick an existing save, delete a save, or create a new one. When creating a save, choose:

- Team
- Save file path
- AI difficulty: `easy`, `normal`, or `hard`

`Random team` is the default team option when creating a save. If you do not pass a seed, new random saves use fresh randomness. If you pass `--seed`, the same seed stays deterministic for reproducible testing.

Example direct launch:

```bash
nba-gm-data play --root . --team LAC --save saves/lac_test.json --seed 7
```

Saves live in `saves/` and are intentionally ignored by Git.

## How To Playtest

Good first test run:

1. Create a save with any team.
2. Open the team dashboard and inspect rotation stats, ratings, contracts, cap room, staff, morale, development, and Starting 5.
3. Sim a week or month.
4. Try the trade finder and manual trade builder.
5. Reach the trade deadline.
6. Finish the regular season.
7. Watch the playoffs, lottery, draft, and free agency.
8. Advance into the next season and check whether rosters, rookies, stats, morale, and contracts changed.
9. Review AI trade offers from the main menu when they appear.

The game is still rough. Please report bugs with:

- Save file name
- Team and date shown at the top of the screen
- Menu path taken
- What happened
- What you expected
- Any traceback text

## Useful Commands

Run the game:

```bash
nba-gm-data play --root .
```

Build deterministic canonical exports:

```bash
nba-gm-data build --root . --out data/canonical
```

The October roster and pick audit is documented in `docs/starting_data_audit_2026_10_13.md`. Existing saves use their archived July baseline; only new saves receive the refreshed roster, salary, and pick inputs. The offseason start date remains July 28.

Refresh the official roster snapshot and compile the reviewed RealGM pick snapshot before rebuilding:

```bash
PYTHONPATH=src python3 scripts/refresh_2026_rosters.py
PYTHONPATH=src python3 scripts/normalize_realgm_pick_snapshot.py
```

See [docs/2026_OFFSEASON_UPDATE.md](docs/2026_OFFSEASON_UPDATE.md) for source
provenance, audit counts, rating-preservation policy, and known boundaries.

Run tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Inspect a player or team:

```bash
nba-gm-data player "Stephen Curry" --traits --root .
nba-gm-data team OKC --staff --root .
```

Inspect or configure optional local narrative:

```bash
nba-gm-data narrative-settings --root . --save saves/YOUR_SAVE.json
nba-gm-data narrative-settings --root . --save saves/YOUR_SAVE.json --enable --test
```

## What Is In The Game

- Canonical July 28, 2026 NBA universe with current rosters, completed 2026 draft results, 2026-27 contracts, 2027-2033 picks, traits, health, staff context, and source provenance.
- Persistent local saves that advance through seasons.
- Sandbox game simulation with saved box scores, standings, leaders, injuries, fatigue, rust, and monthly development.
- AI trade, extension, free-agency, draft, draft-night trade, and staff-decision systems.
- Draft lottery, draft room, rookie signing, rookie onboarding, free-agency market, playoffs, and offseason rollover.
- Staff management for head coach, coordinators, development, scouting, and performance.
- Morale, social posts, league events, contextual press conferences after major events, and optional Ollama-backed narrative writing.
- Protected picks and same-year same-round pick swaps.
- Display-scale player ratings plus a ratings guide, while the engine keeps its internal calibrated values.
- Optional ASCII highlight loading screens.



## Data Notes

Raw folders such as `Player Stats/`, `NBA Schedule/`, `Pre-Season manifestos/`, `HTML Pages with Stats AND Writing/`, `Even more stats/`, and `Computed Stats From Previous Project/` are ingestion sources, not canonical truth. The canonical layer can be rebuilt from source data and caches.

Research caches live under `data/research/`. Manual overrides live under `data/overrides/`. Canonical exports live under `data/canonical/` when generated.
