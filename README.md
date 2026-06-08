# NBA GM Sandbox

A local, CLI-first NBA front-office simulator built around the 2025-26 preseason universe. The goal is a deeper, more basketball-aware version of classic GM modes: roster building, staff decisions, trades, free agency, draft scouting, injuries, development, morale, press conferences, social reaction, and sandbox season simulation.

Current status: **playable pre-alpha / internal alpha candidate**. It is ready for private testing by patient testers, not public beta.

## Quick Start For Testers

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
