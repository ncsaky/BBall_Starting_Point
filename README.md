# NBA GM Sandbox

A local, CLI-first NBA front-office simulator built around the 2025-26 preseason universe. The goal is a deeper, more basketball-aware version of classic GM modes: roster building, staff decisions, trades, free agency, draft scouting, injuries, development, morale, press conferences, social reaction, and sandbox season simulation.

Current status: **playable pre-alpha / internal alpha candidate**. It is ready for private testing by patient testers, not public beta.

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

Example direct launch:

```bash
nba-gm-data play --root . --team LAC --save saves/lac_test.json --seed 7
```

Saves live in `saves/` and are intentionally ignored by Git.

## How To Playtest

Good first test run:

1. Create a save with any team.
2. Open the team dashboard and inspect rotation stats, ratings, contracts, staff, morale, and development.
3. Sim a week or month.
4. Try the trade finder and manual trade builder.
5. Reach the trade deadline.
6. Finish the regular season.
7. Watch the playoffs, lottery, draft, and free agency.
8. Advance into the next season and check whether rosters, rookies, stats, morale, and contracts changed.

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

Run tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Inspect a player or team:

```bash
nba-gm-data player "Stephen Curry" --traits --root .
nba-gm-data team OKC --staff --root .
```

## What Is In The Game

- Canonical 2025-26 preseason NBA universe with players, teams, staff context, contracts, picks, traits, health, and sources.
- Persistent local saves that advance through seasons.
- Sandbox game simulation with saved box scores, standings, leaders, injuries, fatigue, and monthly development.
- AI trade, extension, free-agency, draft, and staff-decision scaffolds.
- Draft lottery, draft room, rookie signing, free-agency market, playoffs, and offseason rollover.
- Staff management for head coach, coordinators, development, scouting, and performance.
- Morale, social posts, and mandatory contextual press conferences after major events.

## Known Pre-Alpha Caveats

- The CLI is improving quickly, but some screens are still dense.
- CBA rules are practical approximations, not full NBA legal modeling.
- The roster model uses a save baseline for current broad preseason data, then forces cutdowns when transactions add overflow.
- AI GMs are intentionally bounded but still need more playtest tuning.
- Some ratings and player stat outputs still need named-player calibration.
- Setup is currently command-line based; a one-click launcher is a future packaging pass.

## Data Notes

Raw folders such as `Player Stats/`, `NBA Schedule/`, `Pre-Season manifestos/`, `HTML Pages with Stats AND Writing/`, `Even more stats/`, and `Computed Stats From Previous Project/` are ingestion sources, not canonical truth. The canonical layer can be rebuilt from source data and caches.

Research caches live under `data/research/`. Manual overrides live under `data/overrides/`. Canonical exports live under `data/canonical/` when generated.

## GitHub Hygiene

Before pushing publicly, keep the repo private and avoid committing:

- `saves/`
- virtual environments
- caches
- local logs
- generated SQLite/database files
- OS/editor metadata

The current target is private roommate testing, then installer/onboarding polish, then broader alpha.
