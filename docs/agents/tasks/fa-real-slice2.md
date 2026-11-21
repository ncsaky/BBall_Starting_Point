# FA-REAL slice 2: the calendar and the four stops, options and qualifying offers

_Claude (Opus agent), branch `worktree-agent-a246e3c04237da68c` (from main at eab27ac; rules from
OFFSEASON-DECISIONS-EVIDENCE, main c19849b). Status: **review** (slice 2). Committed on the branch only; not pushed._

## TL;DR
- The summer now runs in the real order with four stops: decide who to keep (from June 17, the draft in the middle),
  make offers (June 30), signing day, and set the roster (October). The draft lottery happens in May, in the background.
- Players decide their own options (an option is a final contract year one side may keep or drop); teams send young
  players a qualifying offer (a one-year offer that lets the team keep him), and for now such a player re-signs only there.
- AI teams now keep about half their free agents (54% and 59%, real 45-55%; main 32% and 49%), and stars stay.

## The new offseason calendar and the stops
All dates live in `offseason_calendar.py` and are computed for each season (2026 shown; 2027 and 2028 in tests).

| Date | What happens | Stop? |
|---|---|---|
| Sunday May 8-14 (May 10, 2026) | Draft lottery, during the playoffs, drawn with the career's seed; a news item names the winner | no |
| Finals end (game: June 10-16) | Season recap | yes (as before) |
| **June 17** | **Stop 1, "Decide who to keep"** opens: options decided, qualifying offers due, talks with your own free agents. **The one contract-season switch**: from this day rosters, payrolls, cap holds, signings, extensions and trades all count next season (before: June 22 for some parts, the phase name for others, the October rollover for the label) | yes |
| first Tuesday on/after June 22 (June 23-24, 2026) | The draft, its own screen | yes |
| the day after the draft | Back to stop 1 | yes |
| June 29 | Last day for options and qualifying offers (undecided ones take their default when you open free agency, after a confirmation that lists them) | - |
| June 30 | **Stop 2, "Make offers"**: talks with other teams' free agents; deals official as soon as both sides agree | yes |
| July 1 | New league year: empty-roster cap charges start | - |
| July 4 (after five market days) | **Stop 3, "Signing day"**: who you signed, who left you and where, what is still open | yes |
| July 13 | Last day to pull a qualifying offer and keep the player's Bird rights | - |
| August 1 | Late summer in the background: trades, and restricted free agents settle with their teams | no |
| October 1 | Last day to accept a qualifying offer: an unsigned restricted free agent takes it | no |
| October 1 to the day before opening night (October 20; real 2026: October 19 with an October 20 opener) | **Stop 4, "Set the roster"**: cut to 15, rookie-scale extensions (their own deadline now, the day before opening night; other extensions keep the January window) | yes |
| October 31 or the next weekday (November 2, 2026) | Rookie-scale options: AI teams decide; the calendar stops here only if you still have one to decide (advancing again lets it lapse) | only if yours is open |

- Phases keep their names (`re_signing` is stop 1, `free_agency` stops 2-3, `offseason` late summer); the
  `draft_lottery` stop is gone. The text room (`play.py`) follows the same path.
- **Slice 3 hooks:** the restricted rule is in one place (`offseason_decisions.blocked_for_team`,
  `restricted_player_ids`, `restricted_market_day`, `restricted_summer_pass`); signing day has a "Still open" box
  for offer sheets to match; qualifying-offer records carry the team, amount and status a match needs; `cap_ledger`'s
  reserve/commit/release already holds offer money.

## Options and qualifying offers (`offseason_decisions.py`)
- **Where options come from:** the Basketball-Reference contract table already in the save (matched by season and
  salary) and the game's own rookie deals. They are written onto the contracts the whole game reads (screens, cap,
  waivers, trades: rule 4). Options for 2026-27 and earlier were decided in real life and count as kept.
- **Rules** (one labeled block, `RULES`, fitted by OFFSEASON-DECISIONS-EVIDENCE on three summers and tested on the
  fourth):
  - Player options: he opts out when his market price is at least 0.95 of the option (0.85 at 30 and older); a close
    call with full Bird rights goes to opting out and re-signing longer (Kyrie Irving 2025); an injury into next season
    keeps him in. Each decision states its reason.
  - Veteran team options: kept when he is worth at least 1.2 times the option, or when the year is minimum-level
    (cheap to keep and cut later); you decide your own.
  - Rookie-scale options: the third year is kept; the fourth is declined only for a player under about 850 minutes last
    season worth less than the option (the evidence: 700-1,000 minutes and replacement level).
  - Qualifying offers (AI): sent to players with about 1,000 minutes last season, or to an injured rotation player.
- **Qualifying-offer amounts** (CBA Art. XI): a first-rounder after year four gets his fourth-year salary plus 30%
  (No. 1 pick) to 50% (No. 30), with the starter criteria (41 starts or 2,000 minutes: a pick outside the top nine
  who meets them gets the No. 9 offer; a top-14 pick who misses gets the lesser of his and the No. 15 offer); others
  get 135% of salary or the minimum plus $200,000 (second-rounders meeting the criteria: at least the No. 21 offer);
  the optional maximum qualifying offer (five years at the max) is a button for you. A restricted player's cap hold is
  the larger of his hold and his offer; a declined rookie option caps what his team may pay him.
- **The interim restricted rule** (until offer sheets, slice 3): a player sent a qualifying offer talks only to his own
  team. In June he signs only if he does not hold out for more; each market day, on August 1 and at the October 1
  deadline his team offers his price (stepping down to what its owner will pay, never below the offer) and he gives a
  little more ground each time; on October 1 he takes a multi-year deal worth 75% of his price, else the one-year offer.
  A tendered regular gets KEEP-STARS' franchise budget. Withdrawing through July 13 keeps Bird rights; later it also
  renounces them. This replaces the old "keep good young players automatically" proxy.

## The market fix (`payroll_plan.py`, `play.py`)
The owner's payroll rule refused most AI bids (slice 1). Day-one pairs on the slice-1 save: 86 bids possible, 502
refused by "keep room below the tax line"; after the fix 128 and 360. What changed, for reasons rather than targets:
- A team keeps its regulars (18+ minutes) with Bird rights up to the line; only the tax bill against the owner's
  budget decides. Fringe re-signings still keep room.
- A mid-level signing for a rotation player (a need) goes up to the line; only rebuilding teams keep trade room.
- Front-office habits (TRADE-MARKET traits): an office known to avoid the tax stays $3M under the line and accepts half
  the tax; one known to pay it accepts 1.6 times as much; urgency scales a contender's or rising team's budget by up
  to 40%.
- Front offices look at more of the market each day (30 players the first day, then 10 more; was 26 and 8), and a
  rotation player draws an offer from the first day.

Two summers from a fresh save (seed 17, Golden State hands-off), main (eab27ac) against this branch (e4ad64d),
`output/fa-real-slice2/lean_probe.py`:

| Measure | 2027 main | 2027 branch | 2028 main | 2028 branch | Real |
|---|---:|---:|---:|---:|---:|
| Expiring contracts (incl. opt-outs) | 150 | 178 | 171 | 173 | |
| Return to own team (all / AI teams) | 32% / 35% | **54% / 59%** | 49% / 53% | **59% / 63%** | 45-55% |
| Teams using a mid-level | 19 | 15 | 22 | 22 | 18-23 |
| Day-one AI bids | 21 | 22 | 25 | 31 | |
| Qualifying offers sent (of eligible) | - | 13 of 32 | - | 11 of 26 | 10-13 of ~25 |
| ... signed with his team / took the one-year offer | - | 8 / 5 | - | 7 / 4 | most / 0-2 |
| Player options (opted out) | - | 34 (15) | - | 16 (7) | ~50% out |
| Veteran team options (declined) | - | 26 (6) | - | 14 (6) | ~52% declined |
| Rookie options, autumn before (declined) | - | 46 (5) | - | 47 (4) | 59 (11, autumn 2026) |
| Teams over the tax / first apron, opening | 13 / 7 | 15 / 8 | 7 / 4 | 9 / 5 | 7-14 |
| Unsigned expiring players on opening day | 50 | 48 | 37 | 27 | |
| Offseason actions by the automated GM | 14 | 13 | 14 | 13 | |
| Offseason seconds (Finals to Oct 1) | 228 | 296 | 327 | 368 | |

How to read it:
- **Teams keep their players for real reasons now**: options, qualifying offers and Bird re-signings of regulars. The
  return share sits at the top of the real range (54%, 59%); it includes restricted players re-signed with their
  teams. Mid-level use is in range in 2028 and slightly below it in 2027 (more players re-sign, fewer move).
- **Qualifying offers**: the sending rule lands in the real range; 5 and 4 players took the one-year offer (real 0-2):
  mostly players whose teams' owners wouldn't pay their price over the tax (2027: Jarace Walker, Scoot Henderson,
  Bilal Coulibaly; 2028: Stephon Castle, Zach Edey), plus low-salary players whose offer is only the minimum plus
  $200,000 (Devin Carter, Rocco Zikarsky). Logged under "What's left".
- **Stars stay (KEEP-STARS holds)**: Nikola Jokic opted out in 2027 and re-signed in Denver ($59.8M x 3), Luka Doncic
  (Lakers, $59.3M x 4), Jalen Brunson (Knicks), Kyrie Irving (Dallas) and Derrick White (Boston) opted out and
  re-signed; Brandon Miller and Donovan Clingan re-signed as restricted free agents; every top-30 player whose AI team
  held his rights stayed. The only movers were Golden State's (hands-off) and Paul Reed (44th).
- **Trades still flow**: 102 trades against 103 on main (deadline weeks 20 and 29 against 21 and 26; draft nights 9
  and 9 against 9 and 8; summers 10 and 12 against 10 and 17).
- **Speed**: the offseason took about 20% longer in these runs (664 s against 555 s over two summers) on a busy shared
  laptop; most of it is the June decisions (market values for options and offers) and the restricted talks.

## Screen = save (rule 4)
- The checklist reads the same records the engine writes (option and offer records, holds from `cap_ledger`); an
  accepted qualifying offer writes exactly the recorded amount (all nine in the branch run, e.g. Bilal Coulibaly
  $12,394,361 offered and saved); option years shown on contracts are the ones the cap, waivers and trades use.

## Screenshots (`output/fa-real-slice2/screens/`)
- `1440-stop1-decide-who-to-keep.jpg`: the checklist beside the offer builder (sorted by deadline: qualifying offer for
  Brandin Podziemski with amount and why, the player-option results, your free agents with Bird rights, holds and
  Renounce), the four stops with their dates, "Go To Draft Night (Jun 22)".
- `1024-stop1-checklist.jpg`, `1024-draft-night-june22.jpg` (straight into the draft; lottery already drawn in May),
  `1440-stop1-after-draft.jpg` ("Open Free Agency (Jun 30)").
- `1440-stop2-market-june30.jpg`, `1440-stop2-market-restricted-labels.jpg` ("Restricted · OKC" in the bids column).
- `1440-stop3-signing-day.jpg`: who you signed, who left and where, what is still open.
- `1440-stop4-set-the-roster.jpg`, `1024-stop4-after-keeping-option.jpg`: roster count, the rookie-scale option
  due November 1 with Keep him / Decline.
- At 1024 the board keeps its window positions (as before); the windows read correctly.

## Tests and checks
- New: `tests/test_offseason_calendar.py` (dates, phases, stops, the one switch date, hold window),
  `tests/test_offseason_decisions.py` (options from data, decisions, rookie kinds and deadlines, qualifying-offer
  amounts and eligibility, the interim rule, holds, withdrawal), `tests/test_offseason_market.py` (market fix, office
  habits, stop names, stop-1 defaults, the June 29 deadline), `tests/offseason_checklist.test.cjs`.
- Updated because the rules changed (each says so): `test_postseason_calendar`, `test_simulation_consistency` (new
  dates), `test_keep_stars` (a regular's Bird re-signing no longer keeps room), `free_agency_room.test.cjs` (a fourth
  window; new stop commands).
- `bash scripts/run_core_tests.sh`: 338 tests; one failure (a calendar test with the old draft dates) updated, then OK.
- 59 more modules touching free agency, the calendar, phases, draft, waivers, extensions, trades and saves (list in
  `output/fa-real-slice2/run_modules.txt`, including `test_foundation`): 794 tests; 3 modules had old-calendar
  expectations (`test_draft_year_gate`, `test_foundation` x2, `test_fitted_free_agent_salary` relied on the phase
  name for the signing season); updated and rerun OK. The audit runner `scripts/league_health_audit.py` follows the
  new dates.
- Node: all pass except `startup_video.test.cjs` (needs the ignored movie file, as on main).
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18** league metrics in
  band. Game simulation is untouched, so the betting-odds check was not rerun.

## What's left
- Qualifying-offer acceptances run high (4-5 a summer, real 0-2) for over-tax rebuilding teams; offer sheets (slice 3)
  and the owner budget for young players are the natural places to fix it.
- Rookie-scale extensions keep the game's existing AI choice; the evidence's rule (a strong prior season, about 1.0
  value over replacement; some teams wait for cap room) is not wired in yet.
- Market prices for stars under contract can be odd (Giannis valued at $16.8M for his option decision): the room's
  ask model for players who aren't free agents. Decisions came out right (he opted in), but the reasons show the number.
- Two-way qualifying offers, Exhibit 10, sign-and-trades: slice 4. The 21-to-15 cutdown keeps the existing screen.
- The text room shows the stop-1 flow but not the checklist's option and offer buttons (GUI only).
- `trade_calendar.free_agency_trade_slots` still keys on July; market day 1 is now June 30, so day-one AI trades
  start on July 1 (not changed: trade file).

## Resume state
- Done: code, tests, probes (main and branch), screenshots, this report. Board row set to review.
- Outputs (git-ignored): `output/fa-real-slice2/` (code copies `basecode`/`branchcode`, runs `base` and `run3`,
  metrics JSON, trade metrics, screenshots, scripts `lean_probe.py`, `offseason_metrics.py`, `stars.py`,
  `tax_teams.py`, `bid_funnel.py`, `codecopy.sh`, `run_modules.sh`).
