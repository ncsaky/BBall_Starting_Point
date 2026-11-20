# Trade deadline and counter-offers (TRADE-DEADLINE)

_Claude (Opus agent), branch `worktree-agent-aeffeb94cdbe260e6` (from main at 7cef425). Status: **review**
(committed on the branch, not pushed or merged)._

## TL;DR
- **AI teams now negotiate instead of only saying yes or no**: a team that is a little short asks for one change
  (a player it wants, a pick, keeping a piece of its own), back and forth for up to 4 rounds, and you get the same
  counters in the trade window with Accept, Edit and answer, and Decline. About 1 trade in 9 now closes after a counter.
- **The deadline did not get busier: 16 and 15 deadline-week trades against 17 and 15 before (real 23-28).** The
  deals are more like real ones (salary matched with unwanted contracts, fewer pure salary dumps), but the two
  sides' prices still rarely meet; the evidence and the next decision are in "What's left".

## Objective
- Deadline week toward about 23 trades a season (real 23-28); two-season total toward 100-110 (was about 80).
- AI teams counter near-miss offers (each other's and the user's), the textbook way: one or two rounds, legal, close
  to the asking side's price, explained in plain words.

## Boundaries
- Files: `trade_targets.py`, `transactions.py` (target search, package builder), new `trade_counters.py`,
  `save.py` (late deadline pass only), `app_actions.py` (evaluate_trade counter), `gui/app.js` +
  `trade-workspace.css` (trade response area only), scripts, tests.
- Not step 5 (front-office personality). Experimental engine untouched. Scorecards must not move.

## What changed

### 1. Salary a buyer would rather move (`trade_targets.salary_filler`, `transactions.buyer_offer_packages_for_value`)
- Each AI team keeps a short "salary I'd move" list (at most 3): players outside its rotation (under 18 minutes)
  with a reason to go (overpaid, out of the rotation, over the tax, an older bench veteran, on the trade block),
  players out injured for 30+ more days, and expiring bench contracts. Never a core player, a young player the team
  builds around or a recent draft pick.
- When a buyer builds an offer, these players are always available to match salary, with a small preference over
  rotation players. The talent screens that stop a buyer from overpaying are skipped for them: they are there for
  their salary. The seller still prices every player it takes with its own check.
- **Why it mattered**: on a fresh 2027 deadline day, 79 of 125 pairings for players paid $5M or more got **no legal
  package at all**: the builder only tried cheap bench players, which cannot match a $10-30M salary for a team over
  the tax. With the filler that fell to 40, and the deals that close now look like real deadline deals (Dosunmu for
  Tre Mann and Tre Johnson; Murray for Grant Williams and a first; Eason and Adams for Josh Green and picks, with
  the Clippers taking salary).

### 2. The quick price screen allows what the full check allows (`trade_targets.quick_capital_limit`)
- The cheap screen before the full check limited picks for a non-starter to 8 points plus depth. The full check also
  allows the rotation-role allowance (17-24 minutes), $5M+ of salary shed, tax saved and young upside. The screen now
  includes those cheap terms, so it stops dropping packages the full check would accept. The acceptance check itself
  is unchanged.

### 3. Counter-offers between AI teams (trade step 3, new `trade_counters.py`)
- **When**: one side accepted and the other refused while at most 20 points short (about one second-round pick),
  with no hard-rule refusal (premium return, core commitment). It covers the closest package of a pairing that met
  neither price in the quick screen, and packages the full check refused.
- **What the short side asks for**, in order: a player on the other team who matches one of its own trade targets
  (added, or in place of a piece it was getting); otherwise, by phase: rebuilding and retooling teams ask for a pick
  (one, or two seconds), then a young player, then to leave a salary out; teams competing now ask to keep a piece of
  their own out of the deal, then a pick, then a young player. A competing seller refusing because it loses a rotation
  player asks for a rotation player back. A buyer refusing to spend a pick offers one of its own bench players
  instead ("Fontecchio instead of the second").
- **Fairness**: the ask must bring the asking side to its price and at most 15 points past it (one second's worth);
  the closest such ask wins. The other side must stay inside the existing bounded AI negotiation, and then decides
  with its own unchanged full check. A player for nothing back is allowed only when the other side saves luxury tax.
- **Rounds (user feedback, 2026-11-20)**: real back-and-forth. Either side may counter again, but every counter must
  bring the two sides closer (their combined shortfall below their own prices must drop by at least half a point; a
  refusal on a rule counts as 5 points apart) and no package may come back. The deal dies when the short side has no
  ask that narrows the gap within its tolerance, or after **4 rounds**. Why 4: each round costs up to 3 full checks
  (about 0.05 s each), so a 4-round negotiation costs at most 12; with at most 40 negotiations and 80 counter checks
  per deadline-week day, counters stay under about a tenth of a deadline day's checks. In the probes no deal needed
  more than 2 rounds, so a higher cap would buy nothing.
- **The chain is recorded on the trade** (`trade_reasons.counter.steps`): for each round the asking and answering
  team, what was asked, the full offer (each side's assets), each team's distance from its price, the answer
  (refused or agreed) and the plain-words reason. The trade's reason text ends with the whole chain.
- **Explanations**, e.g. "MIN asked for Tre Johnson (a rotation player back) instead of Deandre Ayton; WAS agreed:
  Tre Johnson was a young player blocked from minutes."
- **Budget**: at most 12 negotiations (24 counter checks) on a normal market day and 40 (80 checks) on a
  deadline-week day.

### 4. Counters to the user's offers (`app_actions` evaluate_trade, `gui/app.js`, `trade-workspace.css`)
- When you evaluate an offer in the trade window and the AI partner refuses while a little short, the response area
  shows its counter in plain words ("MIN asked for a 2030 second-round pick as well."), the full package each side
  would send, and **Accept counter**, **Edit and answer**, **Decline**. The partner asks for its own targets on your
  roster first, then a pick. Your own evaluation is never used or changed; the AI only proposes.
- **Multi-round in the trade window**: Edit and answer loads the counter into the builder; you change it and evaluate
  again. The window sends the negotiation so far with each evaluation, so the partner never repeats a package (yours
  or its own) and each new counter must ask for less than its last one (a real concession). Earlier counters are
  listed as "Round 1: ...". After 4 counters it says it will not counter again. Decline ends the negotiation.
- **What you see is what executes**: the counter shown is the evaluated deal itself, and Accept sends exactly that
  deal through the normal apply path. Checked on a real save: GSW offered De'Anthony Melton for Jonathan Kuminga; MIN
  refused and countered for GSW's 2030 second; accepting executed exactly Melton + the 2030 second for Kuminga.
  Offering the same package again drew no second counter (MIN had no smaller ask), as intended.
- Not checked visually in the running app (node tests of the markup, and the save-level checks above).

### 5. A late deadline-day pass (`save.late_deadline_trade_pass`, `save.late_deadline_user_offers`)
- After the deadline day's first deals are applied, the market runs once more for the slots left that day, looking
  only at pairings that involve a team that traded that day (new needs, new filler, new room).
- **Your team (user feedback)**: if your team traded that day, AI teams may send you up to 2 new offers that fit your
  new roster, into your normal incoming offers, each with its reason plus "... made this offer late on deadline day,
  after GSW's trade earlier today changed its roster." Nothing is ever executed for you. (Not exercised in the probe:
  the probe's Golden State is hands-off and makes no trades; covered by a unit test.)

### 6. Fit with the current core (`trade_roster.system_fit_discount`; user feedback on the Kuminga trade)
- **The Kuminga trade**: no probe ever traded Kuminga. The Kuminga-to-Golden State deal came from my own check of the
  counter feature: my script picked offers for the user's team by trade value (Melton for a player worth a little
  more), and Minnesota's AI answered. Golden State is your team, so its own evaluation never decides anything.
- **But the question stands**, so I measured how an AI Golden State would price him (2027 deadline save):
  - The fit credit in a player's price comes only from the team's phase, listed needs and position depth. It never
    looks at the players already there or how the team plays. Kuminga got **+9.6**, the largest of the players tested.
  - The engine already projects the team's rotation after a trade with its own team model (the same features the
    game simulation uses: spacing, creation, defense, rebounding and rim protection of the players who would play),
    but only in the full check and with a small weight. It says Golden State's rotation gets **0.26 worse** with
    Kuminga (Sam Hauser: 0.68 better; Jaylin Williams: 0.80 better). The team model has no separate coach-system
    input; the system shows only through the players who would play.
  - In the 94-input ratings Kuminga is a poor shooter (40.8) and creator (54.7) with strong rim pressure (74.1), but
    his defense summary is about average (63.1), so the ratings do not call him a weak team defender. Per the
    ratings-first rule I did not touch ratings; if Basketball Index evidence disagrees, that is a ratings-track item.
- **The change**: when the engine's projection says the rotation gets worse, the generic fit credit for the incoming
  players is taken back in proportion, all of it at a projected loss of 0.5. It never adds value, it only runs on
  deals that reach the full check (the projection is already cached there), and rebuilding teams keep their generic
  credit (they are picking a new identity). The evaluation notes say so in plain words.
- **Before and after** (Golden State's roster term in the full check, Melton going out):

| Incoming | Generic fit credit | Projected rotation change | Roster term before | after |
|---|---:|---:|---:|---:|
| Jonathan Kuminga | +9.6 | -0.26 | -1.1 | **-6.1** |
| Ayo Dosunmu | +3.0 | -0.35 | -1.4 | -3.5 |
| Kenrich Williams | +3.0 | -0.13 | -0.5 | -1.3 |
| Sam Hauser | +3.0 | +0.68 | +2.7 | +2.7 |
| Jaylin Williams | -0.2 | +0.80 | +3.2 | +3.2 |

  It also cost volume: the run before it made 96 trades, the run with it 86 (marginal deals for players who make the
  buyer's rotation worse no longer close).

### 7. Guards added after reading the new trades
- **Recent first-round picks** (first three seasons) stay off the market unless the team has its own reason (a
  listing, a blocked prospect, stalled talks). Runs had rising Utah give Darryn Peterson (2026 No. 2) to Boston for
  Neemias Queta and a second; contending Oklahoma City give Bennett Stirtz (No. 16, traded up for) and a second for
  Jericho Sims; rising Orlando give Cameron Williams (21, 24 minutes) for a bench big. The first version covered
  lottery picks only; it was widened to all first-rounders after the final probe (see "Results").
- **Young starter-quality players** (25 or younger, on-court value 65+, about the top 5% of young players) count as
  pieces a team builds around even when their projected minutes are lower (rising Portland traded Donovan Clingan, 23,
  for Mitchell Robinson and a first).
- **A team stops chasing a target it filled in the last 60 days** (collecting young players excepted). Indiana bought
  three bigs in three days for the same "successor to Siakam" target; the base run had 5 such repeats, the final 2
  (both young-player collecting).
- **No quick re-sale**: a player acquired by trade in the last six months is not shopped as a target, except a
  veteran (28+) a rebuilding team took on as salary and flips to a contender. One run had Sam Hauser traded three
  times in eight months.

## Results

Two-season probe: seed 17, Golden State hands-off, 94-input ratings, 2026-10-20 to 2028-11-01. "Base" is main at
7cef425; "final" is the branch at 88e38db (everything above except the widening of the first-round guard, which came
after reading this run; on the fresh 2027 deadline day it did not change the 17 deals).

| Window | Base | Final | Real |
|---|---:|---:|---:|
| Draft (June), 2027 / 2028 | 7 / 8 | 8 / 7 | 8-11 on draft night |
| July, 2027 / 2028 | 6 / 9 | 6 / 11 | 16 (2025), 8 (2026) |
| August-September, 2027 / 2028 | 4 / 4 | 4 / 5 | 3, 5 |
| October to January (in season), two seasons | 13 | 12 | ~1 a season |
| **Deadline week, 2027 / 2028** | **17 / 15** | **16 / 15** | **23-28** |
| ... of which deadline day | 6 / 4 | 5 / 2 | 18 |
| **Total** | **83** | **86** | ~110-140 |

The intermediate runs show how much the deadline swings with the path: 84 trades (deadline weeks 18 / 9), 96 (20 /
17), 96 (20 / 13), then 86 (16 / 15). No lever moved the deadline reliably.

The step 1-4 measures:

| Measure | Base | Final |
|---|---:|---:|
| Trades with every team's reason stated | 82 of 83 | **86 of 86** |
| Three-team trades | 10 | 11 |
| Two-team salary dumps | 18 | 8 (tax relief now often rides inside target deals with filler) |
| Players traded twice / three times | 17 / 1 | 19 / 2 |
| Re-traded within six months | 3 | 3 |
| Young starters (25 or younger, 24+ minutes) moved | 0 | 1 (Cameron Williams; guarded since) |
| Players rated 68+ moved | 1 | 0 |
| Rebuilding team buying a 30+ veteran on $15M+ for 2+ years | 0 | 0 |
| Star-for-star swaps | 0 | 0 |
| Same team, same target within 60 days | 5 | 2 |
| Taxpayers at season end, 2027 / 2028 (real 6-8) | 10 / 10 | 10 / 10 |
| Most trades by one team in two seasons | DEN 13 | MEM 12 |

**Counter measures (final run)**:
- 10 of 86 trades (12%) include a counter-asked piece: 5 picks, 3 target players, 2 "leave a salary out", 1
  player-for-pick swap.
- Rounds: 9 closed after one counter, 1 after two; none needed three or four. Longest chain: 2 rounds; shortest: 1.
- Sellers ended up with a player matching one of their own targets in 7 trades (counter or not).
- How far the asking team ended above its own price in the full check: median 7.5, middle half 5.9-9.2 (one
  second-round pick is worth about 12-20): fair asks, not gouges.
- On a fresh 2027 deadline day with no slot limit, the market finds 17 deals with the branch (12 from targets,
  2 of them after counters, 1 three-team, 4 dumps) against 11 on main.

Example chains:
1. **Deadline 2027, New Orleans and Charlotte (2 rounds)**. Charlotte (rising) targets Dejounte Murray from
   rebuilding New Orleans. Round 1: Charlotte asks for a 2033 second as well (New Orleans would send Murray and the
   second for Sion James, Grant Williams and a 2027 first); New Orleans refuses, 0.4 short. Round 2: New Orleans asks
   to leave Sion James out; Charlotte agrees. Final: Murray and a second for Grant Williams (expiring) and a first.
2. **Deadline 2027, Minnesota and Washington (1 round)**. Washington (retooling) targets Ayo Dosunmu, whom Minnesota
   moves to get under the tax. Minnesota asks for Tre Johnson (a rotation player back) instead of Deandre Ayton;
   Washington agrees because Johnson was blocked from minutes.
3. **November 2026, Cleveland and Dallas (1 round)**. Dallas (rebuilding) targets Tyrese Proctor; it will not spend a
   2027 second on him and offers Dwight Powell instead; Cleveland agrees.

**Hand-read deadline trades** (12 read; five here):
1. **Good**: New Orleans (rebuilding) sends Dejounte Murray (30, $32.8M x2) and a second to rising Charlotte for
   Grant Williams (expiring $14.3M) and a 2027 first: a textbook rebuild sale, salary matched with an expiring deal.
2. **Good**: rebuilding Phoenix sends Collin Gillespie (28) to rising Detroit for David Jones Garcia, KJ Lewis, Kevin
   Huerter (salary) and a 2028 first: a buyer paying in youth, a first and an unwanted contract.
3. **Good**: rebuilding Memphis sends Zach Collins (expiring) to the contending Lakers for Jaden Hardy, Marvin Bagley
   and a second: a contender buys a proven big from a seller with bench salary.
4. **Borderline**: rising Minnesota sends Ayo Dosunmu ($19.3M x5) to Washington for Tre Mann, Tre Johnson and two
   seconds. Minnesota sheds a long deal under the tax; Washington gives up the 2025 No. 6 pick after a season and a
   half because he was listed as blocked, which the guard allows.
5. **Bad**: contending Oklahoma City gives Bennett Stirtz (2026 No. 16, it had traded up for him) and a second to
   Milwaukee for Jericho Sims, after Milwaukee's counter asked for the second. Same shape as the Nique Clifford sale.
   Fixed afterwards: recent first-round picks are now off the market without the team's own reason.

Others read: Gafford for Vukcevic (good); Jarrett Allen and a protected first for Santi Aldama (borderline: a
tax-driven downgrade by contending Cleveland); Cameron Williams for Johann Grunloh (bad; fixed by the same guard).

**Speed** (CPU seconds; the machine was shared with other agents' probes and tests during the later runs, so the
probe numbers are noisy):
- Whole two-season run: 1,351 -> 1,398 (+3.5%).
- 2027 deadline step: 76.5 -> 80.5 (+5%). 2028 deadline steps: 92.9 -> 107.5 (+16%, inside the 20% budget).
- One deadline day's market search, run back to back on the same save: 8.8 -> 9.6 s (+9%).

**Scorecards**: trades do not change game results. Real-stat scorecard
(`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**. No odds run (not needed).

## Tests
- New `tests/test_trade_counters.py` (23 tests): filler choice (never core, young or recent picks; injured and
  expiring bench included), quick screen matches the full check's allowances, counter choice (targets first, tiers by
  phase, closest ask, overshoot cap, AI bound), plain-words text, short-side rules, multi-round chains (each round
  narrows the gap, no repeated package, round cap), the user counter is the evaluated deal, recent first-round picks
  and quick re-sales kept off the market, filled targets, the system-fit discount, the late deadline pass and the late
  offers to the user (offers only, never executed).
- New `tests/trade_counter_offer.test.cjs` (3 tests): the counter block, its full packages and buttons, earlier rounds
  and the closed negotiation.
- Trade modules (`test_trade*`, `test_multi_team*`, `test_keep_stars`): 307 OK, 1 skipped.
- `bash scripts/run_core_tests.sh`: 337 OK, 2 skipped.
- `for f in tests/*.test.cjs`: all pass except `startup_video.test.cjs` (needs the ignored movie file, as on main).
- Determinism: no new random draws. Counters re-use the existing per-proposal personality draw of each evaluated
  package; outcomes change because more and different deals close.

## What's left
- **The deadline is still about half of real.** What limits it is acceptance, not search:
  - On a fresh 2027 deadline day the branch builds packages for far more salaried targets than main (filler), sends
    134 to the full check and 105 are refused: buyers refuse to spend picks on non-starters (the draft-spending rule)
    and competing sellers refuse to lose rotation players (the roster-plan rule).
  - Counters can only move value from one side to the other; they close deals where one side has room to give. Most
    refusals have both sides short.
  - The week shares one pool of deals: whatever earlier days use up, deadline day lacks (deadline day 5 and 2 against
    a real 18).
  - Moving the rotation-role pick allowance to start at 12 minutes instead of 16 changed nothing on the fresh deadline
    day (tested, not kept).
  - **Decision for the user**: the next lever is the acceptance check itself, e.g. how much draft capital a contender
    may spend on a 15-20 minute player, or letting a competing seller move a rotation player for a younger one plus a
    pick. Both change how teams value deals, so they need the user's say.
- The late deadline-day pass and late offers to the user rarely fire: they need open slots and a team that traded that
  day.
- The user counter's multi-round path is unit-tested and checked on a save; a full multi-round negotiation was not
  walked through in the running app.
- Kuminga's 94-input defense (63, about average) does not match the user's read of him as a weak team defender; worth
  a ratings-track look with Basketball Index evidence.
- Front-office personality (step 5) not started, as agreed.
- The last guard change (all recent first-round picks) was checked with unit tests and the fresh deadline day, not a
  new two-season probe.

## Resume state
- Probes: `output/trade-deadline/{base,after1,final,final2,final3}-src/output/probe` (final3 is "final" above).
  Metrics: `output/trade-deadline/results/trade_metrics_<label>.json`, trade lists `trades_<label>.json`.
- Scratch scripts (git-ignored, `output/trade-deadline/`): `diag_packages.py` (one market day, every package and why
  it failed; `--no-filler`, `--no-counters`, `--backup-minutes`), `diag_builder.py`, `diag_issues.py`,
  `debug_counters.py`, `fit_probe.py`, `chains.py`, `show_*.py`, `read_trades.py`, `extra_metrics.py`, `windows.py`,
  `repeat_targets.py`, `retrade_detail.py`, `advance_copy.py`, `explore_user_counter.py`, `verify_user_counter.py`,
  `user_chain.py`.
