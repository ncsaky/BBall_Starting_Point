# Trade AI step 1: how AI teams value their own players (2026-11-19)

_Claude (Opus agent), branch `worktree-agent-a2151937196b0334c`. Step 1 of `docs/agents/TRADE_AI_DIRECTION.md`;
follows the review in `docs/agents/tasks/trade-review-2026-11-19.md`._

## TL;DR
- **AI teams now price their own players as what they would lose**: the minutes he really plays for them, plus a small,
  documented attachment, years with the team, and recent investment (draft slot, trading up, trade cost, contract),
  scaled down when the team has its own reason to sell. Every save now keeps a memory of tenure and investment.
- **The problems from the review mostly disappear** (94-input ratings, same seed): players traded twice or more 31 -> 4
  (three times or more 3 -> 0), rebuilding teams taking on 30+ veterans with big multi-year deals 8 -> 0, star-for-star
  swaps 4 -> 0, young players (23 or younger) moved 11 -> 2. Both scorecards are unchanged (they don't use AI trades).
- **Cost: trade volume falls by 40%** (89 -> 53 over two seasons; deadline week 24-25 -> 9 a season, real NBA ~23), and
  the deadline search evaluates about twice as many packages (~13% more CPU time). No volume hack was added: step 2's
  target-driven search is the planned fix, because today's package builder still aims at the market price, not the
  seller's asking price.

## What was wrong (mechanics, before)

Every AI evaluation prices a trade from one team's side: what it receives minus what it gives up
(`package_value_components` in `transactions.py`). Three things made a team's own players look cheaper to it than to
the team receiving them:

1. **His role on his own team was guessed, not read.** A player's value is scaled by the minutes he would play. For an
   incoming player the team ranks him against its roster by on-court value and expects that rank's minutes (35 for the
   best player down to ~8 for the ninth). The same guess was used for the team's *own* player, even though the team
   knows exactly how much he plays. On-court rank and real minutes often disagree, so a 33-minute starter could be
   priced as a fringe player: on the old aged save, the median own-team minutes weight was 0.55 (about 21 minutes)
   while the best five other teams averaged 0.64 for the same players, and in a quarter of cases the team's own weight
   was the floor of 0.12 (8 minutes or less). Example: Toronto's Immanuel Quickley played 33.5 minutes but Toronto
   priced him at 12 against 66 for the five most interested teams.
2. **His own presence counted as a surplus.** Needs and surpluses by position are counted with him on the roster, so a
   team's seventh guard read as "guard surplus" (a fit penalty) even though losing him removes the surplus, and losing
   a team's fourth guard never showed the hole it leaves.
3. **One context bonus counted only on the way in.** A contender gets +5.5 for receiving a playoff-level player, but
   lost nothing for sending one away, so two contenders swapping playoff players both "gained".

And there was no memory: no attachment to one's own players, no years-with-the-team, no record of what a team paid
(draft slot, trading up, trade cost, contract). Only a 60-day "recently traded" block and a small premium for
players acquired 60-180 days earlier.

Measured on the aged league after two seasons (every AI-team player worth 25+, his own team's price vs the five
other teams that value him most): those buyers valued him at a median **1.22x** his own team's price (quartiles 1.03 /
1.22 / 2.01). That is the "every team is a willing seller" effect.

## What changed (all "context"; no ratings, no game simulation, no draft code)

New module `src/nba_gm_data/trade_ownership.py` plus small hooks in `transactions.py`, `save.py` and `play.py`.
None of it applies to the human team: the user's own valuations are unchanged (tested).

### 1. Own-player correction (`transactions.py`)
- **Actual role:** when an AI team prices its own player, his minutes weight is at least the one for the minutes he
  actually plays (injured players use their usual minutes). `destination_role_multipliers`.
- **Departure, not presence:** position needs and surpluses for its own departing players are counted on the roster
  *without* them (`own_departure_state`): his own slot no longer reads as a surplus, and the hole he leaves counts as
  a need. Skill needs (shooting, rim protection, ...) are unchanged.
- **Symmetric contender bonus:** a contender sending out a playoff-level player gives up the same +5.5 it would get
  for receiving one (`strategic_fit_adjustment`).

### 2. Attachment (loss aversion)
4% of the player's value to his team, plus up to 4% more for reasons to keep him: in the team's core plan (+3),
25 or younger playing 24+ minutes (+2), 30+ minutes (+1).

### 3. Tenure
1.2% per year with the team (up to 8 years) for rotation-quality players (scaled from market value 35 to 70), plus 2%
if he is homegrown (drafted and kept, 2+ years). Fades to zero between ages 32 and 35; halved for a rebuilding team.

### 4. Investment
Recent costs, full for about three months, then fading linearly to zero at two seasons:
- **Draft:** pick 1-3 10%, 4-10 8%, 11-20 5%, 21-30 3.5%, second round 1%; **+4% if the team traded up** for that pick.
- **Trade:** 7% scaled by what the team gave up for him relative to his value (0.3x to 1.5x).
- **Signing or extension:** 5% scaled by salary relative to $30M a year (up to 1.5x); contracts under $5M ignored.
Investment is capped at 15%, the whole premium at 30%.

### 5. Context can override (the team's own reasons to move him)
The premium is scaled down by the strongest reason the team has to move the player (the existing trade-block
reasons): GM listing or stalled contract talks x0.3, rebuilding team with a 29+ veteran x0.35 (x0.8 for a team that
is only "developing"), retool candidate or bad contract x0.5, expensive non-contributor on a contender or veteran
surplus x0.6, position surplus (still over-full after he leaves), blocked prospect or health risk x0.75. Roster-shape
reasons never apply to a core player.

### Why these sizes
- **Small attachment:** lab studies find owners ask about twice what buyers offer (Kahneman, Knetsch & Thaler 1990),
  but experienced professional traders show little of it (List 2003, *QJE*). Front offices are professionals, so 4-8%.
- **Investment memory is real in the NBA:** teams give more minutes and longer stays to higher draft picks than their
  play explains, i.e. they escalate commitment to sunk costs (Staw & Hoang 1995; Camerer & Weber 1999). The user's
  framework asks for this to fade over one to two seasons; it does.
- **The Clifford check:** Sacramento traded a protected first to move up to #24 for Nique Clifford (2025), then sold
  him 17 months later for two seconds while 1-9, at the back of the rotation, saving tax. In the game at the start of
  2026-27 his draft investment is still on (pick 24 + traded up, 39% left after 16 months), but he is a back-of-rotation
  player on a rebuilding team, so Sacramento's premium on him is about 1.4 points on a 21-point own value: the investment
  raises reluctance a little and context still lets the sale happen, as it did in real life.
- **Franchise players:** Jokić (11 years, homegrown) carries about +21 on Denver's 153 (14%); Shai Gilgeous-Alexander
  +26 on 185; Wembanyama +17; Booker on rebuilding Phoenix only +4 (the rebuild overrides 11 years of tenure).

At the opening of a new 94-input save, the premium is a median 7% of a player's own value (10th-90th percentile
3.6% to 15%), 3 points (0.3 to 14).

### Tenure and investment ledger (`save["player_tenure"]`)
- **Starting league** (`seed_player_tenure`): consecutive seasons with his current team from the ESPN season-by-team
  rows in `data/research/player_career_stats.json` (counting back from his latest season, so an injured 2025-26 doesn't
  reset Haliburton); homegrown = drafted and every NBA season with this team; trades from June 2025 on from
  `data/research/real_trades/trades_2025_2027.json` (date known, cost assumed fair); 2026 offseason arrivals with no
  recorded trade = free-agent signings with their contract as the investment; real draft-night trade-ups (Clifford,
  Karaban, Tarris Reed Jr., Stirtz, Okorie, Carr) from the same file. Fantasy-draft saves start empty.
- **Going forward** (`fold_transaction_logs`): when the save is written, every new transaction log is folded in before
  old logs are archived: trades (date, the value the team gave up, split across the players it got by their value),
  draft selections (pick number, and "traded up" when the team acquired that pick in a trade in the 40 days before),
  free-agent signings, re-signings and extensions (date, salary), waiver claims, and releases. Readers
  (`canonical_with_save`) see the ledger plus any logs not yet folded, so a trade made earlier the same day already
  counts. The fold is idempotent and gives the same result whether logs are folded one at a time or all at once.
- Size: about 200 KB per save (one small record per player; a mature save is ~14 MB).

### Explanations
- Evaluation notes now end with an "Own-player price" sentence, e.g. *"Austin Reaves valued 110.0 in his 34-minute
  role (attachment +4.1, tenure +4.1 (6.8 yrs) (scaled x0.50: planned core retool not full teardown))"*.
- The value breakdown has `attachment`, `tenure` and `investment` pieces and per-player components, an
  `own_player_view` per own player (role minutes, keep and move reasons, years, homegrown, how he arrived, live
  investments), and new `from_team_sends` / `to_team_sends` sections with each team's own price for what it gives up.
  The GUI chart (receiving-team values) is unchanged.

### One related fix
When an AI team loses a free-agent target in the summer, the game looks for a trade instead
(`free_agency_fallback_trade_candidates`). That search used the user's trade finder, which marks the searching team
as human, so the AI team skipped its own checks (own-player price, roster plan, premium-player rules). In the first
after-run this let Washington send AJ Dybantsa (21, 35 minutes) and a 20-year-old 2027 draftee for 31-year-old Lauri
Markkanen's expiring deal. The finder now takes `ai_buyer=True` for that path.

## Before / after (two-season probe, seed 17, GSW hands-off, 2026-10-20 to 2028-11-01)

Same seed and actions; "base" = current `main` (`d8bacda`), "after" = this branch. Computed by
`scripts/trade_probe_metrics.py` from each run's final save and progress log.

| Measure | 94 inputs: base | 94 inputs: after | Older ratings: base | Older ratings: after |
|---|---:|---:|---:|---:|
| Trades (2026-27 / 2027-28 / 2028-29 to Nov 1) | 89 (36 / 43 / 10) | **53** (18 / 25 / 10) | 90 (36 / 41 / 13) | **57** (20 / 31 / 6) |
| ... deadline week, per season | 24 / 25 | 9 / 9 | 24 / 24 | 10 / 13 |
| ... draft night, per draft | 5 / 5 | 5 / 5 | 5 / 5 | 5 / 5 |
| ... offseason (July to Oct 19), 2027 / 2028 | 8 / 9 | 9 / 10 | 7 / 12 | 8 / 6 |
| ... rest of the season, per season | 7 / 5 | 4 / 2 | 7 / 5 | 5 / 5 |
| Three-team trades | 0 | 0 | 0 | 0 |
| Players traded 2+ times / 3+ times | 31 / 3 | **4 / 0** | 29 / 5 | **10 / 1** |
| Players 23 or younger moved (25 or younger) | 11 (26) | **2 (14)** | 9 (30) | 3 (15) |
| Rebuilding team takes a 30+ player on $15M+ for 2+ years | 8 | **0** | 7 | 5 |
| Star-for-star swaps (both send a 68+ player, or a $35M+ player 33 or younger) | 4 | **0** | 3 | 1 |
| Trades where both teams net more than +5 | 18 of 89 | 15 of 53 | 28 of 90 | 16 of 57 |
| Receiver's value / giver's own value, executed trades (median; quartiles) | 1.12 (1.00-1.43) | 1.09 (1.01-1.32) | 1.15 (1.04-1.46) | 1.12 (1.00-1.39) |
| ... assets only, without the receiver's context bonuses | 1.00 (0.99-1.22) | 1.00 (0.96-1.18) | 1.05 (1.00-1.27) | 1.00 (0.98-1.18) |
| **League-wide: five most interested teams' value / own team's price** (median; quartiles; every AI player worth 25+, final save) | **1.22** (1.03-2.01) | **0.84** (0.50-0.96) | | |
| Trade-search evaluations, whole run | 45,654 | 104,137 | 39,903 | 87,330 |
| ... steps covering deadline week 2027 (Jan 21-Feb 5): evaluations, CPU s | 19,058, 95 | 37,530, 108 | 19,015, 100 | 33,496, 100 |
| ... steps covering deadline week 2028 (Jan 2-Feb 5): evaluations, CPU s | 15,859, 135 | 29,818, 153 | 14,513, 118 | 25,782, 130 |
| CPU seconds, whole two-season run | 1,200 | 1,357 (+13%) | 1,065 | 1,129 (+6%) |

How to read it:
- **The league-wide row is the review's main finding, measured directly.** Before, the five teams most interested in a
  player valued him 22% above his own team (a quarter of players at twice or more), so almost everyone was for sale.
  Now his own team values him 16% above them at the median: a team sells when a buyer has a bigger role for him or the
  team has its own reason to move him.
- **The executed-trades ratio barely moves, and it is not the right gauge.** Trades only happen where the receiver
  values the assets more (a selection effect), and most of the gap in that row is the receiver's context bonuses, not
  asset values: a rebuilder gets a flat +7 for every pick it receives, contenders a bonus for playoff players, plus
  wants and roster-plan credits. On assets alone the median is 1.00 in all four runs.
- The four remaining two-time movers on the 94 inputs are role players a season apart (Marcus Smart, Donte DiVincenzo,
  Julian Champagnie, Herbert Jones). The older-rating run keeps five rebuilding-team veteran buys (e.g. Memphis taking
  38-year-old James Harden on two years); step 2's targets should own "a rebuilder doesn't want this".
- CPU times were measured with up to three probes running at once on a 10-core machine; compare columns, not
  absolute values. The first after-run (before the summer-fallback fix below) gave 55 trades, 11 players moved twice,
  0 rebuilding veteran buys and 2 star swaps.

## Ten biggest player trades of the after-run, read like a person

Draft-night deals (10 in each run, pick-for-pick trade-ups and trade-downs) are left out: they are bigger by value but
are decided by the draft code (see "Other findings"). "Textbook" = roughly fair value and a reason on both sides.

| # | Date | Trade | Each side's reason | Textbook? |
|---|---|---|---|---|
| 1 | Jul 2028 | **Lakers** (entering) send Austin Reaves (30, $48M x5, 38 min) to **Miami** (exiting) for Quadir Copeland and a top-10-protected 2029 first | LAL: a 30-year-old on a five-year deal for a young team in its planned retool; own price 100 (attachment and 6.8 years' tenure halved by the retool). MIA: a guard upgrade for a first | **Borderline**: LAL's net was +1.6 with +5.2 of personality noise and a weaker roster; a real team would ask for more |
| 2 | Jul 2028 | **76ers** (entering) send Joel Embiid (34, $67M expiring) to **Dallas** (exiting) for P.J. Washington and a 2032 first | PHI: an aging star off the team's timeline becomes a rotation forward and a first. DAL: a last push with an expiring star | **Yes** |
| 3 | Dec 2026 | **Houston** (13-8) sends Kevin Durant (38) to **San Antonio** (18-4, peak) for Keldon Johnson, Julian Champagnie, a 2029 first and a second | SAS: a contender adds a star scorer for depth and a pick. HOU: a young team turns a 38-year-old into two rotation players and a first | **Yes** |
| 4 | Feb 2028 | **Orlando** (rebuilding) sends Desmond Bane (29.6, $42M x5) to **New Orleans** (rebuilding, 11-42) for Dejounte Murray (expiring) and second-round terms | ORL: clears five years of a 29-year-old for an expiring deal. NOP: a backcourt upgrade | **No for New Orleans**: an 11-42 rebuilder taking on five years of a 29-year-old (just under the metric's 30+ line) |
| 5 | Jul 2028 | **Milwaukee** (rebuilding) sends Tyler Herro (28, $27M x2) to **Houston** (entering) for a 2029 first | MIL: rebuild sells a starter for a first. HOU: needs a scorer | **Yes** |
| 6 | Jul 2027 | **Phoenix** (rebuilding) sends Devin Booker (30.7, $61M, long deal) to **Indiana** (exiting) for Pascal Siakam (33, expiring) and seconds | PHX: rebuild moves a long max deal for an expiring one; 11.8 years of homegrown tenure counted, but a rebuild with a 30-year-old scales it to x0.35. IND: one more push | **Yes for Phoenix, questionable for Indiana** (an "exiting" team taking a long Booker deal) |
| 7 | Jul 2027 | **Sacramento** (exiting) sends Precious Achiuwa, Emanuel Sharp and a 2030 first to the **Lakers** for Quentin Grimes (27, 36 min) | SAC: buys a starting guard with a first and filler. LAL: values Grimes at 92 in his 36-minute role and takes a first for him | **Yes** |
| 8 | Feb 2028 | **Atlanta** (rebuilding, 19-33) sends Lonzo Ball (30, $11M x3) to **Houston** for Julian Champagnie and two seconds | ATL: rebuild sells a 30-year-old for a younger wing and picks. HOU: guard depth | **Yes** |
| 9 | Jul 2027 | **Detroit** (entering) sends John Collins (29.8, $17M x5, 28 min) to **Cleveland** (exiting) for Sam Merrill (31) and 2033/2034 seconds | DET: its +17.8 context comes mostly from the flat +7 per pick a developing team gets, even for two far-future seconds. CLE: a starter for a role player | **No**: driven by the pick bonus, not Detroit's own price (Collins valued 78 in his role) |
| 10 | Nov 2026 | **Minnesota** (11-4) sends Donte DiVincenzo (29.8, expiring) to **San Antonio** (12-2) for Tobias Harris (34) and a 2028 first swap | SAS: a contender upgrades a rotation wing and pays a swap. MIN: a pick return for an expiring guard, keeps a rotation forward | **Yes** (SAS accepted by bounded negotiation, net -3.8) |

Six textbook, two borderline on one side, two not. None of the review's failure types (hot potatoes, rebuilders buying
expensive 30+ veterans, value-only star swaps, young starters for seconds) appears in the top ten; the two misses come
from context terms this step did not touch (below).

## Other findings (not changed here)
- **The flat pick bonus is now the largest one-sided term.** A rebuilding or developing team adds +7 for every pick it
  receives (+2.7 per swap) on top of the pick's value, whatever the pick (a 2034 second gets the same +7), and pays
  nothing extra for picks it sends. It drove trade 9 above and most "both teams win big" cases. It is pick valuation,
  not own-player value, so it was left alone; suggested fix: scale the bonus by the pick's value and make it symmetric.
- **Every draft-night trade is executed with one side's own evaluation rejecting it** (10 of 10 in both runs, nets
  around -14 to -25). The draft code decides these trades from its own draft grades (`draft.find_draft_trade`) and
  never asks for both teams' acceptance. Draft code was out of scope here.
- **Fixed here:** the summer "missed free-agent target" trade search treated the AI team as the user (see "One related
  fix").
- **Still no three-team trades** (0 in all four runs), as in the review.

## Open questions
1. **Volume.** 53 trades in two seasons (about 22 a full season vs real ~55-60), deadline week ~9 vs real ~23. Accept
   the drop until step 2 (targets and sellers' asking prices), or soften attachment a little now? This branch does
   not soften it; the sizes are argued above, not tuned to volume.
2. **Search cost.** With fewer willing sellers the brute-force search tries about twice as many packages before giving
   up (deadline ~13% more CPU). Step 2 should use the own-player price (`trade_ownership.own_player_premium` and the
   breakdown's `own_player_view`) as the seller's asking price, so the builder stops offering packages the seller will
   refuse.
3. **Pick bonus** (above): fix in step 2 or as a small separate task?
4. **"Developing" teams and veterans.** The game's phase labels call some playoff teams "developing" (Denver with
   Jokić at the start). This branch counts "older than the team's timeline" fully only for rebuilding teams (x0.8
   otherwise); the phase labels themselves may need a look.
5. **Player wants out.** The game has no trade-request concept; stalled extension talks stand in for it (x0.3).
6. **Starting-league investment** is approximate: trades from June 2025 assume a fair price; earlier arrivals are
   "joined" with tenure but no recorded cost; 2026 re-signings with the same team are not known.

## Files
- Code: `src/nba_gm_data/trade_ownership.py` (new), `transactions.py` (own-player correction, premium hook,
  breakdown, notes, `ai_buyer`), `save.py` (seed, fold on write, ledger in the active league), `play.py` (fallback
  search as an AI buyer).
- Tests: `tests/test_trade_ownership.py` (19 tests: tenure and investment never lower the premium, draft slot and
  trade-up order, human team untouched, move reasons scale it down, ledger seeding (Jokić homegrown, Clifford traded
  up, Haliburton's injured season, Giannis by trade, fantasy draft empty), fold idempotent and order-independent, own
  role at least the minutes played, breakdown explains the price). Also passing: all 29 `trade|market|contract`
  modules (260 tests), `test_foundation`, `test_deadline_speed_exact`, `test_fantasy_draft`, and
  `scripts/run_core_tests.sh` (337 tests, 2 skips). Scorecards: `calibration_report.py` (60 games, both rating sets)
  and `validate-season-probabilities` (60 games x 20 runs) give byte-identical output before and after.
- Measurement: `scripts/two_season_league_probe.py` now records CPU seconds and trade-search evaluations per step;
  `scripts/trade_probe_metrics.py` (new) computes the table above from a probe run.
- Local outputs (not committed): `output/probe/results/trade_metrics_<run>.json`, `trades_<run>.{json,md}`.
