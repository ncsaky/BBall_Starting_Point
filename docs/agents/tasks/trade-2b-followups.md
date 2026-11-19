# Trade 2b: rebuild sales, tax savings, young starters, phase labels, draft-night prices (2026-11-19)

_Claude (Opus agent), branch `worktree-agent-a3655cd6755db5f27`. The five fixes the user approved after trade step 2
(`trade-step2-targets.md`, "Decisions for you"), plus two older test failures the coordinator asked for._

## TL;DR
- **Trades went from 49 to 68 in two seasons** (real: about 110). Draft night now has 5 trades per draft (real: about 5,
  was 1). Deadline week has 15 and 12 (was 4 and 10; real: about 23). Teams over the luxury tax now shed salary to
  teams with room: 19 such moves, 28% of all trades, the same share as the real tax moves (12 of 43).
- **The textbook model held up.** Players traded twice: 9 to 7. Both teams state their reasons in 66 of 68 trades.
  No young starter was sold for tax savings. One rebuilding team took on an expensive veteran (it was paid to).
- **The deadline is still at half the real volume.** The market offers about 25 trade slots in deadline week, and the
  search fills about half of them. Speed: whole run +7% CPU, the first deadline +22%. Decisions for the user are at
  the end.

## What changed

### 1. Rebuilding teams value veterans' current minutes less (`transactions.veteran_present_factor`)
Every team priced a player by the minutes he plays for it now. So a rebuilding team valued its 31-year-old starter
above what a deeper contender would pay, and rebuild sales rarely went through. Now a team far from contending values
a veteran's current production less. This applies on both sides: when it sells him and when it would buy him.
- **Distance from contending** (new `contend_distance` on each team's strategy, `team_planning.py`): 0 within a point
  of the 4th-best team's strength, rising to 1 at six points or more below it. Contenders are always 0. It is a
  smooth scale, not a cliff.
- **Age**: what counts is how old the player will be when the team expects to be good. A deep rebuild is about three
  years away, so a 29-year-old counts as a 32-year-old. The discount ramps in between ages 29 and 33 at that future
  age.
- **Size**: at most 30%. A deep rebuilder values a 29-year-old at x0.78 and a 30-year-old or older at x0.70; a
  mid-table team (distance about 0.4) values a 31-year-old at about x0.90. The step-2 suggestion was about x0.75 at
  29+.
- **Grounding**: the game's own aging (about 0.65 points of decline a year after 29); the real 2025-27 rebuild sales
  (Dosunmu, Vucevic, Conley, Middleton, Kawhi, LaMelo, Giannis went to competing teams for younger players and picks,
  not for equal current production); and the real rebuilders' veteran buys, which were all expiring salary paid for
  with picks.
- The trade-value breakdown shows the same number (a "rebuild timeline" line). The human team's view is unchanged.
- **Measured on a late-2028 league**: the median gap between a rebuilder's asking price for a 28+ starter and the best
  contender's value for him fell from -20 to -14.5 points. That is still a gap; most of it is contenders valuing a
  player by the bench minutes he would get on their deeper roster.

### 2. Luxury-tax savings count as value (`trade_tax.py`, new)
The game had a tax line and a hard cap, but no tax bill. The new module adds:
- **The bill**: the real NBA rates. $1.50 per dollar over the line, then $1.75, $2.50, $3.25, then 50 cents more per
  bracket. A bracket is about 3.33% of the tax line.
  - The tax is charged on the payroll at season's end, using full salaries, so a deadline deal saves a full year of
    tax.
  - Seasons counted: the current one until the regular season ends, plus the next season at half weight.
  - **Repeater rates are not used**: the save keeps no payroll history, so the game cannot tell which teams are
    repeaters (see decisions).
- **Value**: 3 points per $1M of tax saved or added. This is scaled by the owner's spending appetite (financial
  discipline, x0.7 to x1.4) and the team's phase (contender x0.75, rebuilder x1.25). It saturates at 40 points, so a
  team deep in the tax does not give away good players for nothing.
  - **Calibration**: a future second-round pick is worth about 15 to 20 points in this game. Real teams pay one to
    three seconds to shed $5-15M of salary that saves them about $8-25M in tax. That works out to roughly 2 to 4 points
    per $1M.
  - Only AI teams get this term. It enters the acceptance check, the target search's quick price and the seller's
    asking price.
  - Taking on salary that pushes a team over the line now costs it, too. So contenders over the tax now match salary
    instead of adding it.
- **Salary dumps** (`trade_targets.salary_dump_offers`): a new seller-driven search that runs after the target search.
  - Each team over the tax lists up to three players it can spare. These are age 24 or older, paid $3M or more, not in
    its core plan, and not young starters. They are ranked by tax saved minus what the team loses on the court.
  - Each player is offered to the three AI teams with room under the tax that value him most. A team with a full
    roster sends back a minimum-salary player.
  - The cheapest package is tried first: the player alone, then with one, two or three of the seller's cheapest
    seconds, then with its cheapest first (only when the tax saving is large).
  - At most one dump per team per day, and at most a third of the day's trade slots.
  - The reasons are stated in plain words: "DEN (retooling) moved Marvin Bagley III ($10.0M) to cut its luxury tax by
    about $22.9M; ATL (rebuilding) had room under the tax and took him as a rotation player."
- Three-team salary routing uses the same evaluation, so it sees the tax too. No three-team trade happened in these
  runs (see "still wrong").

### 3. Young starters are not sold for tax savings
There is no blanket rule. Young starters (25 or younger, 24+ minutes) and young players in a team's core plan now:
- **Stay off the market when the only reason is money.** The tax and the "expiring veteran" reasons no longer put
  them in reach of the target search (`trade_targets.exposing_reasons`). A team's own reasons still do: a trade-block
  listing, stalled contract talks, a blocked prospect, a position surplus, a bad contract.
- **Carry more attachment.** Their keep-reason premium is up to 8% of their value (it was 4%), and money reasons never
  scale it down (`trade_ownership.py`).
- **Never move for the tax term.** When a team sends one out, the tax term can cost the team but never pays it
  (`trade_tax.young_piece_outgoing`).

They can still be traded for fair value. In the final run one was: Javon Small (25.1, 26 mpg) went from Houston to
Portland as Damian Lillard's successor, at Houston's full own price. No Castle-type tax sale happened.

### 4. Phase labels follow the season (`team_planning.window_assessments`)
Before, a team's strength was its roster rating plus at most 3 points for its record. That is why a 29-18 Milwaukee
was "rebuilding" and a 15-34 Philadelphia was "on the rise". Now:
- **The record is blended in.** Point margin (60%) and winning percentage (40%), as league z-scores, are mapped onto
  the roster-strength scale. The record's weight is 0.85 x games / (games + 15): 0.42 after 15 games, 0.69 at the
  deadline. From July to September, last season's record counts for at most 0.3.
- **A standings guard** applies after 25 games. A team with a top-third record is never "rebuilding". A team with a
  bottom-third record is never "contending" or "on the rise"; it is rebuilding, or retooling if its core is aging.
- **Stability**: a team keeps its previous label unless the new one still holds with its strength moved a point (and
  its trend 0.3) back toward the old label. Labels change at the monthly plan review, not week to week.
- The first test run used a lighter record weight. It still had Charlotte "rebuilding" at 35-17, because the game's
  roster rating predicts its own results only loosely. That led to the heavier weight and the guard.

### 5. Draft-night trade-ups priced like real draft nights (`play.draft_trade_mid_first_offer`)
- **Old pricing**: after the top 10, the offer builder asked for the pick's value plus 8%, and always added a future
  first for picks 11-18 or slides of five spots or more.
- **Real prices** (June 2026, `data/research/real_trades`):
  - #17 to #16 for two seconds
  - #21 to #17 for three seconds
  - #34 to #29 for a future second
  - #35 to #26 for two seconds
  - #25 to #24 for cash
  - a future first for #24 outright (Clifford, 2025)
- The game's slot values already price those slides at one to two seconds. So the offer is now the lower pick plus the
  cheapest seconds that cover the pick's value plus 4% (so the seller clears its own bar). A future first is added
  only when seconds cannot cover the gap, and then it is the cheapest first that does.
- Picks 26-30 can now be traded too.
- A team trades up only for a prospect it ranks above the pick. In one test run a team moved up to 15 for its
  29th-ranked prospect.
- Top-10 picks keep the old, stricter rules.

### Also fixed (coordinator request)
- `tests.test_team_planning`: the trade-block reasons now read a partial valuation record as neutral instead of
  failing (`trade_ownership.VALUATION_DEFAULTS`).
- `tests.test_salary_search_stage_b`, two failures:
  - **Memo parity**: the frozen "stage A" copy of the team evaluation used by the memo test lacked the own-player
    note from step 1 (and now the tax term). It now has both, so the test again checks only that the memo and the
    full path agree.
  - **Repair seeds**: the salary-repair test calls the listed-player search explicitly (since step 2, AI-to-AI markets
    use the target search).
- `test_foundation`'s draft trade-up test now checks the new pricing: the package covers the pick's value plus the
  seller's margin.
- The multi-team test league's team A payroll moved from $205M to $199M, so its three-team leg stays under the tax
  line it used to be tested below.

## Before and after against real
Two-season probe: seed 17, GSW hands-off, 94-input ratings, 2026-10-20 to 2028-11-01. "Before" is main at 14eae80
(injuries and rest, smart minutes, 94-input default). "After" is this branch merged with that main. Both runs are on
the same base.

| Measure | Before | After | Real |
|---|---:|---:|---:|
| Trades, whole run (2026-27 / 2027-28 / summer 2028) | 49 (12/26/11) | **68** (27/29/12) | ~110 |
| ... deadline week, per season | 4 / 10 | **15 / 12** | ~23 |
| ... draft night, per draft | 1 / 1 | **5 / 5** | ~5 |
| ... offseason (July to Oct 19), 2027 / 2028 | 10 / 10 | 7 / 11 | |
| Rebuild sales (rebuilding or retooling seller, player 28+, to a contending or rising team) | 7 | **13** | the most common real trade |
| Salary dumps (a tax team sheds salary to a team with room) | 0 | **19** (28%) | 12 of 43 real were tax moves (28%) |
| Trades where tax money entered a team's decision | 5 | 35 | |
| Three-team trades | 0 | 0 | ~10-15% |
| Players traded 2+ / 3+ times (hot potatoes) | 9 / 1 | **7 / 0** | rare |
| Rebuilding team takes a 30+ player on $15M+ for 2+ years | 0 | 1 (paid to: see below) | ~0 unless paid |
| Young starters moved (25 or younger, 24+ mpg) | 1 | 1 (fair-value successor deal) | |
| Star-for-star swaps | 0 | 0 | rare |
| Both teams net more than +5 | 15 of 49 (31%) | 23 of 68 (34%) | |
| Both teams' reasons stated | 44 of 49 | **66 of 68** | |
| Draft-night trades both teams' evaluations accept | 2 of 2 | 10 of 10 | |
| Odd labels at the deadline (rebuilding with a .550+ record, contending/rising at .400 or worse), 2027 / 2028 | 1 / 1 (Charlotte 33-19, Miami 33-19 "rebuilding") | 1 / 0 (Phoenix 30-22 "rebuilding") | |
| ... the old rule on the after run's league states | | 2 / 0 | |
| Trade-search evaluations, whole run | 8,533 | 6,286 | |
| CPU seconds, whole run | 1,258 | 1,343 (+7%) | |
| ... deadline 2027 (1 step) / 2028 (2 steps), CPU s | 46.8 / 94.6 | 57.1 (+22%) / 99.3 (+5%) | |

The same pair on the branch's original base (2b3cade, before main's injury and minutes work) gave 41 trades before
and 66 after. Deadline weeks went from 4/10 to 11/13, draft nights from 0/0 to 5/5, salary dumps from 0 to 18, odd
deadline labels from 1/1 to 0/0. So the effect does not depend on the base.

Scorecards: see "Tests and checks".

## The ten biggest player trades, read like a person
Draft-night pick swaps are left out; they are listed after the table.

| # | Date | Trade | Textbook? |
|---|---|---|---|
| 1 | Jan 2028 | **DAL** (retooling, 22-27) gets Jalen Suggs (26.7) from **ORL** (rebuilding, 21-25) for Sergio de Larrea (22), Zaccharie Risacher (22.8, expiring), Morez Johnson Jr. (22) and DAL's 2028 first (subject to an Oklahoma City swap right) | **Yes**: a successor for 35-year-old Kyrie Irving; Orlando turns a 26-year-old into three young players and a first |
| 2 | Jul 2027 | **SAS** (contending) gets Santi Aldama (26.5, expiring) from **DAL** (rebuilding) for Devin Vassell (26.9, 2 years) and two seconds | **Yes**: San Antonio needed a big |
| 3 | Jul 2028 | **IND** (retooling) gets Jalen Johnson (26.5) from **ATL** (rebuilding) for T.J. McConnell (36), Quenton Jackson, a protected 2030 first and a second | **Yes**: a successor for 40-year-old Kevin Durant |
| 4 | Nov 2026 | **SAS** (11-3) gets Trey Murphy III (26.4) from **NOP** (5-10) for Luke Kornet, Carter Bryant (21), Tarris Reed Jr. and a first | **Yes**: a contender pays young players and a first; a rebuilder sells |
| 5 | Feb 2028 | **DAL** (retooling) gets Onyeka Okongwu (27.1, expiring) from **ATL** (rebuilding) for Derrick Jones Jr. (31), Caleb Martin (32, expiring), a 2029 first and a second | **Borderline**: Atlanta takes Jones's three years at 31, but is paid a first for it |
| 6 | Feb 2027 | **NYK** (retooling) gets Cam Spencer (26.8, cheap for 6 years) from **MEM** (rebuilding) for Tyler Kolek, Ochai Agbaji, Landry Shamet and NYK's 2028 first | **Yes** in shape; **rich** in price: a first and three players for a $2.4M guard |
| 7 | Feb 2028 | **BOS** (34-15) gets Isaiah Hartenstein (29.7) from **OKC** (39-11) for Bub Carrington, Hugo González, Mitchell Robinson and a protected first | **Borderline**: two contenders, and OKC sends its starting center; OKC saves tax and gets two young players and a first |
| 8 | Feb 2028 | **DET** (28-21) gets Quentin Grimes (27.7) from **LAL** (31-18) for Ronald Holland II (22.6), two seconds and a swap | **Borderline**: a contender-to-contender swap; LAL nets +7.8 |
| 9 | Feb 2028 | **DAL** gets Cam Spencer again, from **NYK**, for Kyle Filipowski and a 2031 first | **No**: Spencer traded twice in a year (MEM to NYK to DAL) |
| 10 | Dec 2027 | **TOR** (11-15, on the rise) gets Donte DiVincenzo (30.9) from **MEM** (rebuilding) for Jakob Poeltl (32.2, $27.3M x3), two bench players and a second | **Half**: a good rebuild sale (veteran to a rising team), but Memphis takes back an older, longer contract to match salary. This is the one "rebuilder takes a 30+ veteran" case. |

Six are textbook or nearly; three are borderline; one is a repeat. All ten state both teams' reasons. Compared with
step 2's ten, the phase-label problems (the 29-18 "rebuilding" seller and the 15-34 "rising" buyer) are gone, and
there is no young starter sold for tax.

**Draft night** (5 per draft). Each trade is a lottery or mid-first move-up for a prospect ranked 2nd to 15th on the
buyer's board. The prices:
- **With a lower first to send**: that pick plus one or two seconds (for example, Denver from 18 to 13 for its own
  first and two seconds).
- **Without one**: a far-future first plus seconds (Cleveland: a 2034 first and two seconds for #11).

Both teams' evaluations accept every one of them.

**Salary dumps** (19). These are bench and rotation players earning $3-15M, moved by tax teams to teams with room
(Boston four times, Denver three, Minnesota, San Antonio and Oklahoma City twice each). Only 2 carried a pick (see "still wrong").

## What is still wrong
1. **Deadline volume is still about half of real** (15 and 12 vs ~23). The market offers 24 and 27 trade slots in
   these deadline weeks, and the search fills about half. The remaining limit is the acceptance check's roster rules
   ("weakens a competing rotation", "too much draft capital for the rotation gain"). Contenders over the tax now also
   pay for any salary they add. Counter-targets (the seller asking for players it wants) and three-team assembly are
   the planned next steps.
2. **Salary dumps rarely carry picks.** Teams with room value bench role players positively, so they take them for
   free. Real dumps usually carried one to three seconds, and they moved bigger contracts ($13-30M). Big negative
   contracts still do not move: their own team's value for the player's minutes exceeds the tax saved.
3. **Three-team trades: still none** in these runs (step 2 had 2, by luck). The tax term makes salary routing
   rational now, but the facilitator path only starts from failed two-team pairings.
4. **Salary matching can undo a rebuild sale**: Memphis sold DiVincenzo (31) but took back Poeltl (32, three years).
   The package builder does not yet prefer expiring salary when the buyer is rebuilding.
5. **The roster rating predicts game results only loosely** (Charlotte 35-17 was rated 15th). The phase fix works
   around it with the record. The contention rating itself could be refit against simulated results; that is a
   separate task.
6. **Repeater tax is not modeled** (no payroll history in the save).
7. **Phoenix was "rebuilding" at 30-22** at the 2027 deadline. It was just outside the top third of the standings,
   where the guard does not apply.
8. **Cheap young guards draw rich prices**: Cam Spencer went for a first and three players, then for a first again a year later. This is step 2's "still
   wrong #6", prospects and cheap players valued by current minutes.

## Decisions for the user
1. **Should teams with room charge to absorb salary?** For example, each roster spot used for a dumped player could
   cost about a second's worth. Real dumps came with seconds attached; ours mostly do not.
2. **Repeater tax**: should seasons record each team's final payroll, so repeat taxpayers pay the higher rates? That
   is a small change in `save.py`'s season history, which is another agent's area.
3. **Tax weight**: 3 points per $1M saved, capped at 40. It gives realistic dump volume. A higher weight would push
   contenders to dump more rotation players.
4. **Next volume lever**: counter-targets (the seller asks for players it wants) or three-team assembly. Both are in
   the plan; counter-targets is probably the larger deadline gain.

## Tests and checks
- New `tests/test_trade_2b.py` (24 tests): veteran discount by distance and age, both sides, breakdown matches,
  human view unchanged; tax bill brackets, open seasons, savings and costs, human team excluded, acceptance note,
  young starters never paid for tax, salary-dump offers and reasons; young starters not exposed by money reasons and
  premium not scaled; phase labels follow the record, standings guard, summer weight, stability band, distance;
  draft-night offers in seconds and the cheapest covering first.
- On the branch merged with main: the trade, market, contract, multi-team, salary, settlement, pick and team-planning
  modules (38 modules) plus `test_foundation` and `test_deadline_speed_exact`: **565 tests OK** (15 skips).
  `scripts/run_core_tests.sh`: **337 OK** (2 skips). The two older failures the coordinator flagged now pass.
  `tests.test_rating_scale_consistency` (not in my files) still has one error, which happens on main as well.
- Scorecards (94 inputs), main vs this branch: `calibration_report.py --games 60` (both modes) and
  `validate-season-probabilities --runs 20 --limit 60` give **identical output** (only the timing line differs).
  This is expected: nothing here touches the game simulation.

## Files
- Code: `src/nba_gm_data/trade_tax.py` (new); `transactions.py` (veteran factor, tax term in the evaluation, salary-dump
  loop, breakdown); `trade_targets.py` (dump search, tax in the asking price and quick price, young pieces);
  `trade_ownership.py` (young-starter attachment, partial valuations); `team_planning.py` (record blend, standings
  guard, stability, distance); `play.py` (draft-night pricing); `schema.py` (one field: `contend_distance`).
- Measurement: `scripts/trade_probe_metrics.py` (rebuild sales, tax moves, salary dumps, young starters, odd labels);
  `scripts/two_season_league_probe.py` (each team's label against its record at the deadline, plus the old rule's
  label on the same league).
- Local outputs (not committed): `output/trade2b/results/` (metrics and trade lists for every run),
  `output/trade2b/{mainbase,merged,base,after,after2}_inputs_v1/` (probe runs). Step 2's results moved to
  `/Users/noahtyler/Documents/BBall_data/BBall_Starting_Point/output/trade-step2-probe/results/`.

## Resume state
Done: code, tests, both pairs of probes, metrics, ten-trade read, report, board row (review), tests and scorecards on
the merged branch, final commit. Nothing remaining on this branch. Not pushed or merged into main.
