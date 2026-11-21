# NBA GM Sandbox

NBA GM Sandbox is a local basketball management game. Pick an NBA team, take over
its roster just before the 2026–27 regular season, and see what you can build over
several years. You make the front-office decisions while the game runs the rest of
the league. The browser interface and the text menus use the same Python engine
and save format.

## What you can do

**Run a team for several seasons.** Set a rotation, manage staff, sign and trade
players, and follow the standings, box scores, play-in and playoffs. Players
develop and age, and new draft classes enter the league each year.

### Get through the offseason

The summer has four main stops. The lottery runs in the background during the
playoffs, and draft night gets its own screen during the first stop.

1. **Decide who to keep.** Review your own free agents, team and player options,
   and qualifying offers in one checklist. A contract option lets the player or
   team decide whether to keep the last year of a deal. A qualifying offer is a
   one-year offer that makes an eligible young player a restricted free agent.
2. **Make offers.** Bid for free agents and see how you can legally pay each
   player before sending an offer.
3. **Signing day.** Review who signed, where departing players went, and which
   decisions are still open.
4. **Set the roster.** Make your final cuts to 15 players before opening night.
   Rookie extensions and rookie contract options have their own deadlines.

Bird rights let you re-sign eligible players over the salary cap. A cap hold
counts against your cap room while your free agent is unsigned. You can preview
how much room you would gain by giving up the hold and the rights that go with it.
The offer builder shows minimum and maximum salaries, yearly raises, and how much
you can spend through exceptions such as the mid-level and bi-annual. It also
shows when using an exception creates a hard cap, a payroll ceiling for the
rest of the season. Computer-run teams use the same signing rules and prioritize
keeping their stars.

### Make trades and scout the draft

**Work the trade market.** Other front offices have their own patience, urgency,
loyalty and opinions about players and picks. Where there is evidence, those
tendencies draw on real front-office reputations. Talks can stretch over several
days, including in the summer. Teams can send counters or make a take-it-or-leave-it
offer, and a team shopping a player can draw rival bids. The **Trade Market**
board shows who is available, which teams are interested, and how far talks have
gone. Your assistant GM texts you about notable players on the market and gets
a clearer read on other front offices as you deal with them. Open **Front
Office** on any other team's page to see that read.

**Build your draft board.** Compare the league consensus with your scouts’
board, which updates monthly, and check how a prospect fits your team. Prospect
cards give you your scouts’ estimate of a player’s upside. Other teams start
with their own scouting and weigh roster needs and team direction when they pick.
The draft screen gives a reason for each computer-run team’s pick.

### Manage minutes, health and player development

**Set playing-time targets.** Your coach decides actual minutes. Matchups, foul
trouble and blowouts can change the rotation, and the coach finds replacements
when someone is out. Fatigue builds from minutes played and eases on days off.
You can rest a player yourself or let your coach make rest decisions.

**Plan around injuries.** New careers use the real 2026–27 opening-night injury
report for players in the game. Injuries can happen during games. Players can
come back rusty and on a minutes limit, and the player card shows availability
and recovery information.

**See what players do well.** New saves use 94 inputs covering 64 basketball
skills, 12 groups of physical tools and 18 groups of tendencies. The player card
shows ratings derived from the same inputs the engine uses. It separates what a
player can do, what they tend to do and how the coach uses them. Ratings draw
on game and tracking data, combine measurements, Basketball Index metrics and
attributed scouting from analysts such as Nerd Sesh. Credible scouting leads
when it disagrees with the numbers, and the build gives more weight to measures
that hold up from season to season.

### Look back on the season

Awards are decided after the Finals. The game names a Finals MVP, Sixth Man,
Most Improved Player and three All-NBA teams, along with the other season awards.
The 65-game eligibility rule applies to awards such as regular-season MVP and
All-NBA. In the browser, the year-end recap and preseason outlook show what
happened and how teams are shaping up. Reopen either slideshow from Settings.
The browser also has sortable standings, minutes and development tables, plus
icons to help you find open windows.

## Install and play

If you have a private Mac beta ZIP, extract it and open **NBA GM Sandbox.app**.
The app includes its own Python runtime.

To play from source, get a checkout of this repository and install Python 3.11
or newer. Set up the game from the repository folder on macOS or Linux.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

For Windows setup, open PowerShell in the repository folder.

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

From the same folder, choose the browser game or the text menus.

```bash
nba-gm-data-gui --root . --open
nba-gm-data play --root .
```

On Windows, run the corresponding executable from the virtual environment.

```powershell
.venv\Scripts\nba-gm-data-gui.exe --root . --open
.venv\Scripts\nba-gm-data.exe play --root .
```

Choose **New Save** to try the current game. Source installs keep their local
saves in `saves/` by default.

## Run tests

Run the test scripts from the repository folder on macOS or Linux, with the
`.venv` created above.

```bash
./scripts/run_core_tests.sh
.venv/bin/python scripts/run_tests_parallel.py --all
```

The core suite covers saves, game and box-score results, the calendar,
transactions and app actions. The parallel runner can take test module names or
`--match` to narrow a run. Add `--js` to include browser-interface tests with
Node.js, or `--calibration` to include the real-stat scorecard.

For a simulation change, check both scorecards.

```bash
nba-gm-data validate-season-probabilities --root . --runs 100
python scripts/calibration_report.py --games 1230
```

- **Betting-odds scorecard.** Replays real 2025–26 games with the minutes players
  actually played and that season’s head coaches. It uses Brier score and log
  loss to compare the simulator’s win probabilities and the betting market’s
  probabilities against actual results, after removing the bookmaker’s margin
  from market odds. It also checks spreads, totals and available player props.
- **Real-stat scorecard.** Compares league and player stats with 2025–26 NBA
  targets. It uses simulated rotations by default. Add
  `--mode replay-real-minutes` to compare with real availability and minutes.

## Where things live

- `src/nba_gm_data/` is the Python game. `save.py` advances careers, `sim.py`
  runs games, and `transactions.py`, `trade_market.py`, `cap_ledger.py` and
  `draft.py` handle roster moves. The player model and ratings modules build
  player inputs and turn them into game ratings.
- `src/nba_gm_data/gui/` holds the browser interface. `app_server.py` serves
  it, `app_actions.py` connects it to the engine, and `cli.py` and `play.py`
  handle the terminal commands and menus. The experimental possession engine
  is off by default.
- `data/` holds the league data the game reads, reviewed overrides, research
  material and calibration targets. `tests/` holds automated tests and
  `scripts/` holds test, data and build tools.
- [AGENTS.md](AGENTS.md) explains the project’s engineering and coordination
  rules. The [coordination board](docs/agents/BOARD.md) tracks work in
  progress, and [task reports](docs/agents/tasks/) record what changed and how
  it was checked.

## Beta status

This is a **private friends-and-family beta**. Mac ZIPs for Apple Silicon and
Intel are built with `scripts/build_macos_beta.sh`. See the
[Mac beta build guide](docs/MACOS_BETA.md) for build and verification steps.

A simulated month takes about 30–37 seconds in the playtest guide. The top stars
still tend to play a few more games than their real counterparts. Restricted free
agents currently negotiate with their own team, and too many take the one-year
qualifying offer. Outside offer sheets and matching, two-way contracts, Exhibit
10 camp deals and sign-and-trades are still on the list. Some screens have only
been checked in desktop Chrome. [Playtest guide](docs/PLAYTEST_GUIDE_2026_11_20.md)

If something feels off, report the team, the in-game date, what you did and what
you expected to happen. A screenshot helps.

## Data and privacy

Keep paid Basketball Index exports and captures local and out of Git. Some older
extracts were committed before that policy. The beta ships with the game’s
built ratings and excludes the private research capture folders. Build from a
clean checkout to keep other local research files out of the ZIP. You can play
without a subscription. Local saves are ignored by Git.
