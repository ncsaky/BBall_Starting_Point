# FA-REAL slice 4: two-ways, camp deals, the cutdown, sign-and-trades

_Claude (Opus agent), branch `worktree-agent-a705af51286ad1e81` (from main at d93e80d). Status: **review** (slice 4).
Committed on the branch only; not pushed or merged._

## TL;DR
- Teams finish rosters the real way: three **two-way** spots for young players (outside the 15 and the salary cap, at most 50 games), one-season **camp tryouts**, a **cut to 15** before opening night, and **sign-and-trades** (re-sign a leaving free agent, trade him at once).
- Replays hit the real counts for camp deals (~7 a team), cuts, claims and sign-and-trades (8 and 3; real 3-11), with no team over its payroll ceiling at opening; two-way promotions run low (15-20, real 26-32).
- You get an Opening Roster window (guarantees, waiver dates, two-way spots, Submit roster), two-way and camp buttons and a sign-and-trade panel; the game never signs anyone onto your roster.

## What was built

### Two-way contracts (`two_way.py`, new)
- **Three places of their own**, kept off the 15-player standard roster entirely (`save["two_way"]`): two-way players
  are not in payroll, trades or roster counts. Pay is half the rookie minimum ($678,882 in 2026-27), prorated after
  opening night, **outside the salary cap**.
- **Eligibility** (CBA Art. II §11): fewer than four years of service in every season the deal covers; at most three
  seasons on two-ways with the same team; one or two seasons; no new two-way after March 4.
- **The 50-game limit**: on each game day the coach calls a two-way up when the team has fewer than 12 healthy standard
  players, or when he is better than the team's 8th best healthy standard player (a real rotation option, the
  Spencer Jones case). Each call-up is one active game; at his limit he stays with the affiliate (news item). A later
  signing gets a prorated limit. Called-up players play real minutes in the simulation (capped at a backup's 10, or
  an end-of-bench 4 when he only fills a short bench); his box-score lines are kept.
- **Conversion** to a standard minimum contract (prorated in season) before the team's last regular-season game: needs
  a standard spot (in the offseason, the 21-player limit) and must fit any hard cap the team triggered.
- **Two-way qualifying offers**: when a two-way deal ends (the June 17 switch) his team keeps his rights until the
  June 29 deadline. AI teams tender their two best young two-ways; the user decides in the stop-1 checklist ("Two-way
  qualifying offer: Send offer / No offer"). A tendered player re-signs a one-year two-way when talks open (June 30);
  the rest join the free-agent pool.
- **New careers** open with each team's **real 2026-27 opening-night two-ways** (83 players from Codex's evidence file,
  the NBA's released lists), instead of sending them to the free-agent pool.
- **AI** (`RULES`, each number with its evidence): late second-round picks (No. 41 on) go to two-ways first (10-14 of
  28-30 second-rounders opened on one; the fit chose picks 40-43); places fill through the summer (one by July 6, two
  by August 1, three by September 20, most trios completed in September-October); on September 20 about half the
  teams with a two-way-eligible camp deal keep the last place for him; about one club in eight leaves a place open at
  opening; in season an empty place is refilled a week later until March 4. **Promotions** happen on Mondays: from
  February 1 when a teammate is out injured and the two-way is good enough to play (76 of 87 promotions came from
  February on; 79 of 82 had an injured teammate), whenever a playing two-way is within four games of his limit, and
  ten days before the last game for playoff eligibility. Always with an open standard spot and a minimum that fits
  any hard cap. No random draws: fixed rules and hashes.

### Exhibit 10 camp deals (`camp.py`, new)
- **One-click camp invite** from the free-agency room: one season at his minimum, not guaranteed (guarantee date
  January 10), at most six at a time, within the 21-player offseason maximum (two-ways count toward the 21), from
  July 1 to opening night. It counts on the payroll and respects a hard cap.
- **Conversion to a two-way** before opening day (the opening-roster window's "Two-way" choice; the team's own summer
  draft pick can be moved to a two-way the same way).
- **Affiliate bonus**: a camp deal waived before opening who clears waivers joins the team's G League affiliate and the
  bonus written into his deal (about $94,000 in 2027-28, the CBA's figure grown with the cap) is recorded, outside the
  cap (modelled simply: no 60-day check). He stays a free agent for NBA teams.
- **AI**: invites in four waves (July 16, August 15, September 15, September 28), teams taking turns one player at a
  time; the August and September waves first send the weakest camp deal to the affiliate (the churn behind the real
  seven or eight deals a team). Invites favour young players with NBA experience (camp signees were about 24-25).

### The 21-to-15 cutdown
- Teams carry up to 21 players through camp. From the roster deadline (the day before opening night) the limit is 15
  standard players plus three two-ways (`two_way.in_season_limits`, `save.refresh_roster_cutdowns`).
- **AI cutdown** two days before the deadline, so the cuts clear waivers (48 hours) the day before opening night and no
  non-guaranteed money is owed: first the best two-way-eligible camp deal moves into an open two-way place, then camp
  deals are waived unless he is one of the team's seven best players, then anyone else over 15 by the roster-retention
  score (which already weighs guaranteed money). The evidence's rule: "keep everyone except players on a known
  Exhibit 10 deal".
- **Waivers**: the existing 48-hour claims (worst record first, paid through `cap_ledger` room, the minimum or an
  exception) stay. Summer camp releases are affiliate assignments that AI teams don't claim (all six real camp claims
  in 2023-2026 came in October); in October a camp player is looked at only by teams with an open spot that he would
  improve (better than their eighth best player), so the batch of ~100 camp cuts clears quickly.
- **The user's window** (Opening Roster, open all preseason, and "Roster & Two-Way Places" in season): standard players
  with their contract, **guarantee in words** ("Fully guaranteed", "Not guaranteed until 2028-01-10", "Guaranteed
  (assumed)" for imported contracts with no public record), what waiving costs and the **day he clears waivers**, a
  "Camp deal" tag, Keep / Waive / Buy out / **Two-way** choices, the **three two-way places** (games used of 50,
  pay, Make standard / Release, open places), counts (standard x/15, two-ways x/3, camp total x/21), the deadline and
  the last day to cut so a player clears before opening night, and **Submit roster** (a legal roster is submitted for
  you on the deadline if you don't; games still wait for a legal roster).
- **Nobody is signed onto the user's roster without the user's say-so**: roster repair and late "strategic" signings
  skip human teams. Below 14 players the game warns; 13 is allowed for two weeks, fewer stops games, and the window
  offers "Fill with minimum contracts" (the assistant signs the best available at the minimum, one click).
- **Roster repair respects hard caps**: a hard-capped team that can't add a minimum plays short (its two-ways come up)
  until it sheds salary; noted once a season in the news.

### Sign-and-trades (`sign_and_trade.py`, new)
- **Legality** (`quote`), every rule explained in plain words: the sending team holds his rights (he finished last
  season there, not renounced); between June 30 and opening night; three or four seasons; first year fully guaranteed;
  raises at most 5%; salary within the sender's Bird limit and his max; the receiving team under the first apron
  before and after; cap room after the trade or salary going back under the 2023 CBA matching table (200% + $250K /
  +$7.5M / 125% + $250K, scaled with the cap); the sender's own matching when it takes players back; roster room on
  both sides; players and picks that are really the receiver's. **Base-year compensation**: when the sender is over
  the cap and his raise is over 20% with full or Early Bird rights, he counts the greater of his old salary and half
  the new one going out (the receiver counts the full salary).
- **Execution**: the contract is written once (year by year, first year guaranteed, tradable again on the normal
  date), he moves to the receiver, players and picks go back, the receiver is **hard-capped at the first apron**
  (`cap_ledger.trigger_hard_cap`), the transaction log shows a trade (with both teams' reasons), and the news says
  "Sign-and-trade: ...".
- **AI** (`ai_pass`, market days 2-5 and August 1): a rotation free agent (18+ minutes, asking $6M+) whose old team
  isn't bidding to keep him; one of his likely suitors over the cap with no room or exception big enough to sign him
  outright, under the first apron after the trade, with room left under that hard cap to fill its roster to 15 at the
  minimum, and whose owner accepts the payroll; bench players (under 20 minutes, not core) for salary matching; the
  sender gets the receiver's own future second-round pick (or cash). Agreed on a fixed hash rate (`agree_rate`) set on
  the 2027 replay. The reasons are recorded ("wanted X but had no room or exception big enough to sign him outright" /
  "wasn't keeping him and got a second-round pick instead of losing him for nothing").
- **The user**, in the free-agency room's offer builder ("Other Ways To Add Him"): for your own free agent, **Find a
  partner** lists the teams he'd join at his ask with each one's legality (and the salary/picks coming back); Propose
  makes the deal after a confirmation. For another team's free agent, **Ask [team]**: tick the bench players to send
  and the pick, **Check the rules** shows every problem or note, **Make the deal**.

### The late market
- **Overseas**: on August 1 and September 15 unsigned veterans aged 24-33 with limited NBA roles (under 14 projected
  minutes) leave for a named club abroad (Real Madrid, Panathinaikos, Hapoel Tel Aviv, Melbourne United...) with a
  reason ("a guaranteed contract and a starting role, which no NBA team offered", ...), in the news and the league
  exit records.
- The rollover's existing archive of fringe free agents is unchanged.

### Trade-file change (minimal, marked)
- `transactions.salary_matching_issue`: a trade can't add salary past a hard cap the team **triggered** this season
  (mid-level, bi-annual, receiving a sign-and-trade), read from `cap_ledger` through `save.canonical_with_save`
  (`triggered_hard_caps`, read-only). Five lines, marked "FA-REAL slice 4 (minimal hook)". No change to
  `trade_market.py`. The sign-and-trade itself runs outside the trade code (`sign_and_trade.execute`), so no other
  trade-file change was needed; its contract's `trade_eligible_date` is read by the existing
  `recently_signed_player_ids`.

## Measures: two seasons from a fresh save, main against this branch
Seed 17, Golden State hands-off, `output/fa-real-slice4/lean_probe.py` (slice 3's harness plus a copy on opening night,
after the cutdown), main at d93e80d (`base`) against this branch at d1e66fa (`run`). Scripts: `edge_metrics.py` (this
slice's measures), `offseason_metrics.py` (slice 3's, now counting a camp deal as "unsigned", not as a destination),
`stars.py`. Real figures: `roster-edge-evidence.md` (2023-2026) and the plan.

| Measure | 2027 main | 2027 branch | 2028 main | 2028 branch | Real |
|---|---:|---:|---:|---:|---:|
| Teams opening with three two-ways (two-way players) | 0 (0) | **29 (87)** | 0 (0) | **16 (73)** | 23-28 of 30 |
| Camp deals signed (median per team, range) | 0 | **196 (7, 0-10)** | 0 | **170 (6, 0-11)** | 190-253 (7-8, 0-12) |
| ... still on the opening standard roster on the same deal | - | **1** | - | **1** | 0-1 |
| ... converted to two-ways before opening | - | 3 | - | 1 | 8-14 |
| ... signees on any opening roster | - | 18 | - | 4 | 11-16 |
| Affiliate bonuses recorded (camp cuts who joined the G League team) | - | 191 ($18.0M) | - | 168 ($16.4M) | 161-200 |
| Waivers from camp (camp deals / others) | 13 (all on October 1) | 191 / 4 | 32 (October 1) | 168 / 16 | 134-159 / 23-28 |
| Waiver claims in camp | 0 | **0** | 0 | **0** | 0-2 |
| Sign-and-trades | 0 | **8** | 0 | **3** | 3-11 |
| Teams over a triggered hard cap on opening night | 1 (MIN) | **0** | 2 (MIA, ORL) | **0** | 0 |
| Standard roster sizes at opening (12 / 13 / 14 / 15) | 0/0/21/9 | 1/1/19/9 | 0/0/14/16 | 1/0/14/15 | about half below 15 |
| Overseas departures (named club and reason) | 0 | **33** | 0 | **24** | 22-47 |
| Return to own team (all / AI teams) | 61% / 66% | **57% / 60%** | 69% / 74% | 65% / 70% | 45-55% |
| Teams using a mid-level | 18 | 15 | 22 | 18 | 18-23 |
| Offer sheets (one-year qualifying offers taken) | 3 (2) | 0 (3) | 1 (1) | 0 (3) | 0-3 (0-2) |
| User stops in the offseason (automated GM actions) | 13 | 13 | 13 | 13 | |

| In season | 2026-27 main | 2026-27 branch | 2027-28 main | 2027-28 branch | Real |
|---|---:|---:|---:|---:|---:|
| Two-ways converted to standard deals (months) | 0 | **15** (Feb 12, Mar 3) | 0 | **20** (Jan 3, Feb 13, Mar 1, Apr 3) | 26-32, 76 of 87 from February |
| Two-ways reaching the 50-game limit | 0 | **25** | 0 | **13** | at least 5 / 13 / 14 (incomplete lists) |
| Two-way signings after opening | 0 | 12 | 0 | 8 (+ refills) | 55-59 contract moves |

How to read it:
- **Two-ways**: the real 2026-27 opening trios start the career (83 players, 30 teams). In the first summer almost every
  team refilled all three places (29, a little above the real 23-28); in the second only 16 did, because the pool of
  young, eligible free agents thins out after the first rollover archives the startup overflow (an undrafted rookie
  class was built for this, then switched off for speed: see "What's left").
- **Camp deals** match the real volume and shape: about seven a team in four waves, almost all cut before opening, most
  joining the affiliate with the bonus; only one a summer stays on the same deal (real 0-1). Too few become two-ways
  (3 and 1, real 8-14): AI teams fill their places with free agents before the camp competition is decided.
- **Promotions** come for the evidence's reasons (11 of 15 and 14 of 20: "a teammate is out injured and he is good
  enough to play"; the rest near the 50-game limit), mostly in February, but below the real count: most AI rosters sit
  at 14-15 and a full team doesn't make room. The 50-game count is in range in the second season (13) and high in the
  first (25): the real 2026-27 two-ways that open a new career include several rotation-level players.
- **Sign-and-trades**: 8 and 3 a summer with the evidence's reasons, e.g. "LAL wanted Cameron Johnson (28 minutes) but
  had no room or exception big enough to sign him outright" / "DEN wasn't keeping him and got a second-round pick and
  salary that matched instead of losing him for nothing". Base-year compensation applied in four of the 2027 deals.
  Every receiver was hard-capped at the first apron and stayed under it.
- **Hard caps**: no breach at opening in either summer (main: MIN in 2027; MIA and ORL in 2028). The two hard-capped
  teams that could not add a minimum contract (HOU at 12, DET at 13) played short, with two-ways called up, instead of
  being filled past their ceiling. Roster repair never signed a player onto Golden State (the hands-off GM used the
  one-click fill when short).
- **Return share** is at or a little below main (57% vs 61%, 65% vs 69%), closer to the real 45-55%: sign-and-trades
  send some departing regulars to new teams instead of losing them for nothing.
- **Mid-level use** is a little lower (15 and 18, real 18-23): some over-the-cap teams got their player by
  sign-and-trade instead of the mid-level.
- **Stars**: every top-60 expiring player whose AI team held his rights stayed (`stars_run_*.txt`); the movers are the
  same as main's (Golden State's own, hands-off; Anthony Davis retired; Paul Reed signed a camp deal with Philadelphia,
  where main's left him unsigned).

### Trades and seasons still flow
`scripts/two_season_league_probe.py --model inputs_v1 --seed 17` on this branch (`trades_probe17/`): two full seasons to
2028-11-01, no stops, **112 trades** (2026-27: deadline week 22, draft 10, in season 7; 2027-28: deadline week 20, draft
12, in season 5, summer 20; summer 2028: 15), of which 11 are sign-and-trades. Without them, 101 ordinary trades against
96 in slice 3's probe on the earlier main (deadline weeks 22/20 vs 23/22, draft nights 10/12 vs 9/11).

## Screens (`output/fa-real-slice4/screens/`)
- `1440-opening-roster-cutdown.jpg`: preseason, 18 standard players (3 on camp deals): "Set The Opening Roster", the
  deadline (October 20, the day before opening night) and the last day to cut so a player clears before it; the
  counter (15 / 15 after three Waive choices, 3/3 two-ways, 21/21 in camp, 3 camp deals); "Camp deal" tags,
  guarantees in words, what each waiver costs and the day it clears; "Apply 3 moves" and "Submit roster".
- `1440-opening-roster-two-way-places.png`: the three two-way places (games used of 50, pay outside the cap, Make
  standard / Release).
- `1440-set-the-roster-checklist.jpg`: stop 4's checklist with the opening-roster and two-way-places rows and "Roster
  view".
- `1440-free-agency-two-way.jpg`, `1440-builder-two-way-camp.png`: the offer builder's "Other Ways To Add Him" (two-way:
  $0.70M this season outside the cap, 1 or 2 seasons; camp invite with the affiliate bonus); signed in the app.
- `1440-sign-and-trade-partners.jpg`: your free agent (Cam Thomas): the teams he'd join with each one's legality
  (Orlando must send back salary, Sacramento's salary is too big for Golden State to take back, Boston is over the
  first apron) and Propose; the deal was then made in the app (Philadelphia, a second-round pick and Dean Wade back).
- `1440-sign-and-trade-acquire.jpg`, `1024-sign-and-trade-acquire.jpg`: another team's free agent (Lonzo Ball, Denver's
  rights): pick the players to send and the pick, "Legal, and everyone agrees" with the salary by year, the matching
  and "GSW becomes hard-capped at the first apron".
- `1024-opening-roster-cutdown.jpg`: the opening-roster window at 1024 wide (fits; the board keeps its window
  positions, as before).
- No console errors from the new code (the only errors were the server restarts' dropped sockets).

## Speed
- **Same-conditions profiles** (`prof_*.py`, one copy, both codes back to back): a regular-season stretch (15 days) is
  about 10% slower (53 s vs 48 s profiled: call-ups, Monday rating refresh, promotions); three market days are within
  a few percent of main's once the undrafted class is off (60/67/76 s vs 56/58/106 s profiled).
- **The replays** ran on a laptop shared with two other agents' jobs (load 12-18): every step was slower, including
  untouched ones (the draft sim 66 s vs 44 s, 101 s vs 61 s), so the raw totals overstate the cost: regular seasons
  1,102 s vs 719 s, offseasons 666 s / 549 s vs 257 s / 412 s. Beyond the load, the real extra cost is in late summer
  and camp of the first summer (the large startup pool of camp candidates and about 190 camp waivers: 125 s and 175 s
  vs 33 s and 32 s); the second summer's are within the load factor (75 s and 65 s vs 47 s and 42 s). Two fixes went
  in for this: summer camp releases skip AI claim checks (affiliate assignments), and an October camp claim is looked
  at only by teams with an open spot that he would improve.
- Determinism: same seeds give the same results. New streams: none (fixed rules and hashes). Outcomes change where
  rosters now include two-ways, camp deals, sign-and-trades and the new cutdown timing.

## Trade-file changes
- `transactions.salary_matching_issue` (marked "FA-REAL slice 4 (minimal hook)", five lines): a trade can't add
  salary past a hard cap the team triggered this season. The caps come from `cap_ledger` through
  `save.canonical_with_save` (`triggered_hard_caps`, read-only). Nothing in `trade_market.py` or any other `trade_*.py`.

## Tests and checks
- New `tests/test_roster_edge.py` (17): two-way eligibility (service, three seasons with a team, March 4), the three
  places, pay outside the cap and off the standard roster, prorated pay and games, call-ups (short bench, rotation
  option, the limit), conversion (a spot, the hard cap), two-way qualifying offers (rights kept until decided, tender,
  re-sign); camp deals (six at once within 21, not guaranteed until January 10, conversion before opening only, the
  affiliate bonus after clearing, nothing owed when cut before opening), guarantee words; sign-and-trade rules (3-4
  years, matching, base-year compensation, 5% raises, hard cap at the first apron, a receiver over the first apron
  refused, no rights no deal, the matching table); roster repair under a hard cap and never onto a human team; the
  user's roster-minimum gate (13 for two weeks).
- New `tests/test_roster_edge_league.py` (2, a real new career): the 83 real opening two-ways, off the 15 and out of the
  free-agent pool; the opening-roster window's answer; the user's camp invite, camp-to-two-way, a full two-way place
  refused, Submit roster, all through the app's action boundary.
- New `tests/roster_edge_ui.test.cjs` (4): a two-way move counts toward the cut, the two-way places panel, the
  builder's other-ways section, the two-way qualifying-offer buttons.
- Updated: `scripts/ten_season_soak.py` (the hands-off GM takes the one-click minimum fill when its roster is short: the
  game no longer fills it).
- `tests/test_foundation.py`: one test updated because a rule changed (says so in a comment): after a hands-off
  rollover the user's 9-player roster is no longer filled by the game, so the test takes the one-click fill before
  advancing into games.
- `bash scripts/run_core_tests.sh`: **338 tests OK** (2 skipped).
- `scripts/run_tests_parallel.py --workers 2 --match "free_agen|offseason|cap_ledger|qualifying|offer_sheet|waiver|roster|
  two_way|keep_stars|extension|trade|market_health|foundation" --js`: 135 modules, **1,554 tests**: one error (the
  `test_foundation` rollover test above), updated and rerun OK. Browser tests: all pass except `startup_video.test.cjs`
  (needs the ignored movie file, as on main).
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18** league metrics in
  band. The game simulation (`sim.py`) is untouched; a called-up two-way joins his team's game like any roster player.
  The betting-odds check was not rerun (it replays real 2025-26 games without a save, so two-ways can't enter it).

## What's left
- **In-season promotions** run below real (15-20 a season, real 26-32): most AI teams carry 14-15 standard players
  and a full team doesn't waive someone to promote a two-way. Next: let a contender waive its weakest non-guaranteed
  player to promote a playing two-way.
- **Camp deals into two-ways** (3 and 1, real 8-14): teams fill their places before the cutdown; more of them should
  keep the last place for the camp competition.
- **The second summer's two-way fill** (16 of 30 teams with three, real 23-28): the young free-agent pool thins after
  the first rollover. An undrafted-rookie class (60 generated players a summer) fixed the supply but made every
  league view slower (about 50% on market days) and is switched off (`camp.RULES["undrafted_class_size"] = 0`). A
  cheaper fix: keep two-way-eligible young players out of the rollover's archive of fringe free agents.
- **Hard-capped short rosters**: a team that can't add a minimum contract plays the season short (Houston at 12 in
  2027-28), calling up two-ways; it should look to trade salary away (the trade AI doesn't know to).
- **Offer sheets**: none in the branch's two summers (main's run had 3 and 1; real 0-3), and three one-year qualifying
  offers taken each summer (real 0-2). Sign-and-trades now take some of the over-the-cap bidders. Worth a look with
  more replayed summers.
- **Camp speed** in a first summer with a big free-agent pool (see Speed).
- Not modelled: two-way waivers and claims (a released two-way goes straight to the market), the team-wide 90 two-way
  active slots in short-handed games, Exhibit 9 (camp injury protection), the 60-day affiliate service check for the
  bonus, a player's veto on a sign-and-trade, the traded-player exception as a way to receive one, Exhibit 10 deals that
  carry a partial guarantee.
- Multiplayer: the new mutations are registered (`multiplayer.py`); not exercised with two humans.

## Resume state
- Done: engine, AI, GUI, actions, tests, two-season replays (main and branch), the two-season probe, screenshots, this
  report; board row set to review. Branch commits only.
- Outputs (git-ignored, `output/fa-real-slice4/`): `base` and `run` (lean replays: copies, progress, metrics),
  `runcode/output/probe17` and `trades_probe17/`, code copies `maincode`/`runcode`, scripts `lean_probe.py`,
  `edge_metrics.py`, `offseason_metrics.py`, `stars.py`, `make_gui_saves.py`, `prof_*.py`, `codecopy.sh`, screens.
