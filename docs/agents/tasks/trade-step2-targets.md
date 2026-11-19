# Trade AI step 2: targets, willing sellers, offers at the seller's price (2026-11-19)

_Claude (Opus agent), branch `worktree-agent-a27f380f5f89a462b`. Step 3 of the order of work in
`docs/agents/TRADE_AI_DIRECTION.md`; follows `trade-step1-own-value.md`._

## TL;DR
- **AI teams now trade from targets.** Each front office picks two or three targets that fit its situation, every
  team lists who it would move and why, and offers are built toward the seller's own price. 44 of 47 trades in the
  two-season test state both teams' reasons in plain words; draft-night trades now need both teams to agree.
- **The trade deadline is much cheaper**: trade evaluations over two seasons fell from about 99,000 to 4,700 (-95%);
  the first deadline week costs 42 CPU seconds instead of 114, the second 98 instead of 142. The whole two-season
  run costs about the same (other work dominates).
- **Volume is still low and the cause is the acceptance check, not the search**: 47 trades in two seasons (53 before,
  real about 110), deadline week 3 and 13 (real ~23). The search now finds most deals the check would accept; the
  check rarely agrees because a team values a veteran by the minutes he plays for it, even when rebuilding, and it
  gives no value to tax savings. Two decisions for you below.

## What was built

### 1. Targets per team per trade window (`trade_targets.team_trade_targets`)
Each AI team sets up to three targets from its situation (contending, on the rise, retooling, rebuilding: the
league-relative window the game already computes). Targets are profiles; the search finds the players who fit, the
best fit is the specific target and the next ones are the alternatives. Each has a label and a reason in plain words.

| Situation | Targets (first is tried first) | Grounding in the real 2025-27 trades |
|---|---|---|
| Contending | a player for its top six at its thinnest position (must beat its 6th-best player); a rotation player who adds the skill it lacks most relative to the league (shooting, rim protection, perimeter defense, shot creation, playmaking, rebounding, rim pressure); with 2+ firsts or high owner pressure, a playoff-level starter from a team with a reason to sell | Contenders bought rotation players at a need or to cover injuries (Clifford, Alvarado, Porzingis, Vucevic, Kennard, Dosunmu, McCain, Huerter) and a few stars (Harden, Giannis, LaMelo Ball, Jaylen Brown, Kawhi), paying with picks, expiring money and young non-core players |
| Rebuilding | a young player (23 or younger) who would play for it, only from teams competing now; a young starter (25 or younger) at its thinnest position. No bad contracts | Rebuilders took young players that competing teams had no room for (Dillingham, Kuminga, Mathurin, Hendricks, Ware, Jakucionis, Risacher) and picks; veterans only as expiring salary paid for with a pick or as absorbed salary for seconds |
| On the rise | a player for its top six at its thinnest position (30 or younger, 4 years or less); the skill it lacks; a young starter | Middle teams made fit moves (a scoring guard for Charlotte, a center for Indiana, shooting for Portland) and young-starter moves (Morant, Risacher) |
| Retooling | a younger successor (27 or younger) for its oldest core player at his position; the skill it lacks (29 or younger); a young player who would play | The retooling pattern in the list (Clippers, Bucks, Celtics pivots) turned older players into younger pieces |

A target only counts a player who would take a real role on the buyer (the acceptance check values an incoming
player by the minutes he would play there), at a salary the buyer can match.

### 2. Willing sellers (`trade_targets.team_sell_reasons`, `trade_ownership.move_reasons`)
Each team lists who it would move and why: step 1's reasons (rebuilding team with a veteran, bad contract, retool
candidate, position surplus, blocked prospect, contract talks stalled, GM listing) plus three new ones: **over the
luxury tax** (non-core player paid $5M+; the own-player premium is scaled x0.75), **expiring veteran on a team not
contending** (28+, last contract year; x0.6), and **out of the rotation** (search order only). Real sellers cited
tax savings in 12 of the 43 trades.

Players a team has no reason to move are still reachable, at that team's full own price (step 1's premium, not
scaled down). Young players a team builds around are off the market unless it has its own reason: every player 25
or younger on a rebuilding or retooling team, and young starters anywhere. (The first full run without this rule had
rebuilders selling 21-year-old starters such as Knueppel, Acuff and Flemings for veterans.)

### 3. Offers built to the seller's asking price
- **Asking price** (`asking_price`): what the seller loses (step 1's own value, premium scaled by its reasons), plus
  its acceptance margin and the contender's playoff-player term: the same numbers the acceptance check uses.
- **Is there a deal at all?** A pairing is pursued only if the buyer's value of the player, plus how much more the
  seller values the buyer's two best spare assets than the buyer does (a bench player who would start for the
  seller, a pick a rebuilder prizes), comes within 4 points of the ask.
- **Packages** (`buyer_offer_packages_for_value(..., seller_view_outgoing=...)`): the existing builder, now aimed at
  the ask in the seller's own values, trying first the buyer's players the seller values most above the buyer.
- **Quick screen** (`ranked_packages`, `package_fits_rules`): each package is priced from both sides and checked
  against the acceptance check's hard rules (a premium player needs a comparable return; a team competing now does
  not lose a rotation player without a like-for-like player back; no more than a couple of seconds spent on a player
  who would not play starter minutes). Only the best 3 (6 at the deadline) go to the real check.

### 4. Target search replaces brute force for AI-to-AI trades
`transactions.simulate_ai_trades` now runs `target_driven_ai_trades` for every AI-to-AI market (in-season days,
the deadline, summer trades). Up to 5 alternatives per target at the deadline (3 otherwise), interleaved so every
team's first target is tried before anyone's second. The unchanged `evaluate_trade_decision` plus
`ai_trade_candidate_accepted` remain the judge for both teams. The search stops at the day's trade slots plus three
spares. The search for offers to the human team keeps the old listed-player search (unchanged), as does the user's
own trade finder. The three-team salary-repair path still runs off the failed pairings.

### 5. Pick bonus fixed (`transactions.rebuilder_draft_bonus`)
A rebuilding or developing team's extra value for a pick is now 14% of that pick's value (a typical future first,
about 50 to a rebuilder, keeps roughly the old +7; a far second now adds about 1-3 instead of 7), and it applies both
ways: sending a pick costs what receiving it adds. Same for pick swaps. Config key `rebuilder_pick_bonus_rate`.

### 6. Draft-night trades accepted by both teams (`play.best_ai_draft_trade_candidate`)
Before, every draft-night trade went through with the buyer's own evaluation rejecting it. Now the seller's own
evaluation must accept, and the buyer's net plus what its target is worth to it must clear its threshold. That worth
is half the gap between the slot value of the prospect's place on the buyer's own board and this pick's slot value
(half, because every team has prospects it ranks well above where the league takes them). The target is now the
prospect the buyer would actually take with the pick (the same choice the draft makes), and a team trades up at
most once per draft. The first test run without those two fixes had New York trading up four times for a prospect
it never drafted, paying four future firsts.

### 7. Explanations
Each trade from the target search or the draft stores `trade_reasons` on the trade and its log, for example:
*"SAS (contending) targeted a wing for its top six: its wing rotation is the thinnest part of a contending roster, and
chose Trey Murphy III; NOP (rebuilding) had no plan to move him but took an offer at its own price."* The probe trade
list (`scripts/inputs_readiness_report.py`) prints it under each trade.

## Before / after (two-season probe, seed 17, GSW hands-off, 2026-10-20 to 2028-11-01)
"HEAD" = current main with step 1, rerun in this session alongside the step-2 run (paired CPU). Older-ratings
"step 1" = the numbers recorded in `trade-step1-own-value.md` (no paired rerun after the machine crash).

| Measure | 94 inputs: HEAD | 94 inputs: step 2 | Older: step 1 | Older: step 2 | Real |
|---|---:|---:|---:|---:|---:|
| Trades (2026-27 / 2027-28 / 2028-29 to Nov 1) | 53 (18/25/10) | **47** (11/27/9) | 57 (20/31/6) | **44** (12/23/9) | ~55-60 a season |
| ... deadline week, per season | 9 / 10 | 3 / 13 | 10 / 13 | 4 / 9 | ~23 |
| ... draft night, per draft | 5 / 5 | 1 / 1 | 5 / 5 | 1 / 1 | ~5 |
| ... offseason (July to Oct 19), 2027 / 2028 | 8 / 9 | 8 / 9 | 8 / 6 | 8 / 9 | |
| ... rest of the season | 4 / 2 (+1) | **7 / 5** | 5 / 5 | 7 / 5 | |
| Three-team trades | 0 | **2** | 0 | **1** | ~10-15% |
| Players traded 2+ / 3+ times | 8 / 1 | 6 / 1 | 10 / 1 | 8 / 0 | rare |
| Players 23 or younger moved (25 or younger) | 3 (11) | 16 (28) | 3 (15) | 18 (29) | many |
| Rebuilding team takes a 30+ player on $15M+ for 2+ years | 2 | 1 | 5 | 1 | ~0 unless paid |
| Star-for-star swaps | 1 | 0 | 1 | 0 | rare |
| Trades where both teams net more than +5 | 11 of 53 | 7 of 47 | 16 of 57 | 16 of 44 | |
| Trades with both teams' reasons stated | 0 | **44 of 47** | 0 | 40 of 44 | |
| Draft-night trades both teams' own evaluations accept | 0 of 10 | **2 of 2** | 0 of 10 | 2 of 2 | |
| Trade-search evaluations, whole run | 98,890 | **4,739** | 87,330 | **6,710** | |
| ... deadline week 2027: evaluations, CPU s | 37,530, 114 | **748, 42** | 33,496, 100 | **848, 39** | |
| ... deadline weeks 2028 (2 steps): evaluations, CPU s | 27,294, 142 | **938, 98** | 25,782, 130 | **3,380, 82** | |
| CPU seconds, whole two-season run | 1,376 | 1,390 | 1,129 | 1,158 | |

How to read it:
- **Young players moved went up (3 -> 16)**: that is mostly the realistic pattern now (bench prospects from teams
  competing now going to rebuilders: Cameron Carr, Tyrese Proctor, Meleek Thomas, Thomas Sorber, Obinna Ekezie Jr.)
  plus contenders paying with young non-core players (San Antonio's Carter Bryant and Dylan Harper). Step 1's 3 was
  low because young players were rarely listed at all; real rebuild deals move many young players.
- **The three trades with no stated reason**: one summer "lost a free-agent target" trade (separate path) and the two
  three-team salary repairs (both routed salary through Philadelphia for second-round picks).
- **Speed**: the deadline weeks are 25-63% cheaper; whole-run CPU is flat (+1% / +3%, within machine noise) because
  the deadline search was only about 15% of the run and the target search adds a small daily setup cost. Note the
  2028 deadline also includes a full month of games.

## The ten biggest player trades (94 inputs), read like a person

| # | Date | Trade | Reasons (stored) | Textbook? |
|---|---|---|---|---|
| 1 | Oct 2028 | **SAS** (contending) gets Jaden McDaniels (28) from **MIN** (on the rise) for Andrew Wiggins (33.7, 4 yrs), Dylan Harper (22.6) and a 2030 first | SAS: a wing for its top six. MIN: no plan to sell, took its price | **Borderline**: sound for SAS; MIN takes four years of a 34-year-old but gets a young guard and a first |
| 2 | Jul 2027 | **POR** (retooling) gets Jalen Suggs (26) from **ORL** (rebuilding) for Robert Williams III, Saliou Niang, a 2028 first and a second | POR: a successor for 37-year-old Lillard. ORL: no plan to sell, took its price | **Yes** |
| 3 | Jul 2027 | **PHX** (rebuilding) gets VJ Edgecombe (21.9) from **PHI** (on the rise) for Cameron Williams (21) and Mark Williams | PHX: a young player who would play. PHI: getting under the tax | **Borderline**: a rising team moving its young guard mainly for tax |
| 4 | Nov 2027 | **PHX** (retooling) gets Stephon Castle (23, 34 mpg) from **SAS** for Ryan Dunn, Oso Ighodaro and a 2028 first | PHX: younger playmaking. SAS: getting under the tax | **No for SAS**: a contender sells a young starter for tax savings (the tax reason bypasses the young-player rule; see below) |
| 5 | Jul 2027 | **IND** (retooling) gets Santi Aldama (26.5, expiring) from **DAL** (rebuilding) for Obi Toppin and three seconds | IND: a younger big to succeed Siakam. DAL: no plan, took its price | **Yes** |
| 6 | Jul 2028 | **IND** gets Jalen Johnson (26.5) from **ATL** (rebuilding) for T.J. McConnell and two firsts | IND: successor for Siakam. ATL: retooling around a younger core | **Yes** |
| 7 | Dec 2027 | **SAS** (20-5) gets Sam Hauser (30) from **MIA** for Julian Champagnie and two seconds | SAS: a big for its top six. MIA: a veteran older than its timeline | **Yes** |
| 8 | Nov 2026 | **SAS** (12-2) gets Trey Murphy III (26.4) from **NOP** (2-13, rebuilding) for Luke Kornet, Carter Bryant, Tarris Reed Jr. and a first | SAS: a wing for its top six. NOP: took its price | **Yes**: contender pays young players and a first, rebuilder sells |
| 9 | Feb 2028 | **POR** gets Tyler Herro (28) from **MIL** ("rebuilding" at 29-18) for Toumani Camara, Eric Gordon and two seconds | POR: successor for Lillard. MIL: took its price | **Borderline**: the deal is fine; Milwaukee's "rebuilding" label at 29-18 is not |
| 10 | Feb 2028 | **PHI** ("on the rise" at 15-34) gets Tre Jones (28, expiring) from **CHI** for Cameron Williams, Adem Bona, Justin Edwards and a second | PHI: a guard for its top six. CHI: took its price | **Borderline**: a 15-34 team buying a veteran at the deadline (phase label again) |

Six textbook or nearly, three borderline, one wrong. Every one states a target and a reason on both sides. Compared
with step 1's ten, the review's failure types are gone from the top ten; the remaining misses come from phase labels
(a 29-18 "rebuilding" team, a 15-34 "rising" team) and the tax reason.

Draft night (1 per draft): in 2027 Indiana moved up to Memphis's pick 24 for Abdou Toure (13th on its board),
giving its own later first and a second; in 2028 the Lakers moved up to pick 23 for Bruce Branch III (7th on its
board), giving their own later first and a second. Both are the small real-world kind of trade-up, both teams'
evaluations accept, and the reason is stored.

## Tests and checks
- New `tests/test_trade_targets.py` (20): targets by situation (contender rotation and skill targets, star target
  only with picks or pressure, rebuilder young-only targets from competing teams, retooling successor), young players
  kept without a reason, tax and expiring-veteran reasons, plain-words reasons, pick bonus scales with value and is
  symmetric, asking price equals the seller's own value plus margin, packages screened from both sides, the human team
  never in the target search, draft-night both-sides rule and premium, trade reasons kept in the log.
- Adapted: `tests/test_trade_calendar.py` and one `tests/test_multi_team_trades.py` search test now call the
  listed-player search explicitly (still used for offers to the user); the multi-team settlement fixture's
  departing player is slightly weaker, because its deal relied on the old flat +7 for a 2029 second.
- `test_foundation`'s mid-first draft-market test required a pick-11 trade that the buyer's own evaluation rejected;
  in that fresh league no mid-first buyer now clears its bar, so it checks instead that every deal found is legal,
  accepted by both teams, explained, and paid with a first. (Flagged for review: it no longer requires a deal.)
- Results: 30 trade/market/contract modules + `test_foundation` + `test_deadline_speed_exact` (489 tests) OK after
  that change (15 skips); `scripts/run_core_tests.sh` 337 OK (2 skips). Scorecards (94 inputs):
  `calibration_report.py` (60 games) and `validate-season-probabilities` (60 games x 20 runs) give byte-identical
  output to HEAD.

## What is still wrong
1. **Volume is set by the acceptance check.** Diagnosing a deadline day: the search builds and screens ~500
   packages and the check rejects most survivors on its roster rules ("too much draft capital for the rotation
   gain", "weakens a competing rotation"). The deeper cause is valuation: every team prices a player by the minutes he
   plays for it, so a rebuilding team values its 31-year-old starter like a contender would, and contenders (deeper
   rosters) value him less than his own team does. Rebuild sales of veterans, the most common real trade, rarely
   clear. Step 1's flat pick bonus used to paper over part of this.
2. **No value for tax savings.** 12 of 43 real trades were tax moves; the acceptance check has no term for money
   saved, so salary dumps with picks attached (Saric, Finney-Smith, LeVert) cannot happen. The new tax reason only
   makes the seller less attached.
3. **The tax reason can expose young starters** (Castle). It should not override "young players a team builds
   around" unless the player is paid a lot.
4. **Phase labels**: "rebuilding" at 29-18 and "on the rise" at 15-34 produce odd buyers and sellers.
5. **Draft night**: 1 trade per draft (real ~5). The draft offer builder asks for two future firsts for a mid first
   (its slot values make a #14 pick worth about 1.7 future firsts), which the buyer's half-board premium rarely
   covers.
6. **Prospects are valued by current minutes**, so a blocked teenager is cheap to both sides.
7. Counter-targets (step 3), real three-team assembly (step 4) and personality (step 5) are not built.

## Decisions for the user
1. **Rebuilding teams and veterans' minutes**: should a rebuilding team value a veteran's current production less
   (for example x0.75 at 29+, both when selling and buying)? This is the main lever for realistic rebuild sales and
   volume. It is a valuation change, so it was not made here.
2. **Tax savings in the acceptance check**: add the luxury-tax money saved as value for teams over the line (and so
   allow salary dumps paid with picks)? Recommended as its own small task.
3. Smaller: keep young starters off the market even for tax reasons (one-line fix); review phase labels; re-price
   draft-night trade-ups.

## Files
- Code: `src/nba_gm_data/trade_targets.py` (new); `transactions.py` (target search, seller-view package builder,
  pick bonus, reasons in the trade log); `trade_ownership.py` (tax and expiring-veteran reasons); `play.py`
  (draft-night both-sides acceptance, target = actual pick, one trade-up per team); `save.py` (search limit = slots +
  3); `trade_wants.py`; `data/overrides/transaction_model_config.json`.
- Measurement: `scripts/trade_probe_metrics.py` (reasons, targets, both-sides acceptance),
  `scripts/inputs_readiness_report.py` (prints the reasons).
- Local outputs (not committed): `output/probe3/results/` (step 2), `output/probe2/results/*head*` (HEAD baseline).

## Resume state
Done: code, tests, both probes (94 inputs and older ratings) on the final code, paired HEAD baseline, metrics,
report, board row (review), commit. Nothing remaining on this branch.
