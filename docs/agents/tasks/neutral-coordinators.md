# NEUTRAL-COORDINATORS: new saves start every coordinator at neutral ratings

Owner: Claude (Opus agent), worktree branch `worktree-agent-a3766f8925744f861`. Status: **review** (committed on the
branch; not pushed or merged). User decision 2026-11-21: "We don't need real offensive or defensive coordinators."

## TL;DR

1. Every team's starting offensive and defensive coordinator now has neutral ratings (no edge either way), in new saves and in the betting test's replay of 2025-26. Head coaches are unchanged.
2. The betting test improves on both seeds: Brier 0.2060 -> 0.2041 and 0.1992 -> 0.1972; log loss 0.6021 -> 0.5975 and 0.5852 -> 0.5808. Totals error improves on both; spread error improves on one seed and is a hair worse on the other.
3. The real-stat scorecard stays 18/18. Staff screens show the neutral ratings the engine uses.

## 1. What changed

**The starting coordinators.** A new save's coordinators came from made-up per-team ratings, worth from about -0.9 to
+1.3 points per 100 possessions on one end (Utah's defensive coordinator +1.29, the Lakers' offensive coordinator
+1.14, Detroit's two coordinators -0.71 and -0.90). ODDS-COACH found that these pushed real teams' results against both
the betting market and real results. Now:

- `staff.neutral_starting_coordinator` sets a starting coordinator's skill ratings to **60**, the staff model's
  no-effect point (60 becomes 3 stars, and 3 stars means league average, so no effect on either end). It covers shot
  quality, spacing design and creator usage for offense, and coverage, matchup scheming and discipline for defense.
- `staff.initialize_save_staff_slots`, which builds every new save's staff, applies it to both coordinator slots.
- `sim.replay_staff_stints`, which builds the betting test's 2025-26 coaches, applies the same helper. So the replay
  starts coordinators exactly as a new save does.
- The fouls effect from defensive discipline is now neutral (1.0) for every starting coordinator.

**What stays:**

- Name, archetype, style tags, personality and age (age is drawn from the person, not the rating).
- Contracts still exist and still come from the same rule, but the rule reads the neutral rating. Pay now matches the
  rating: starting coordinator salaries are $3.3-4.3M (mean $3.70M), down from $3.2-7.75M (mean $4.41M). Job security and
  starting reputation follow the same way.
- Head coaches keep their evidence-based reputation ratings. Their effect is unchanged on every team.
- Development lead, scouting lead and performance lead are untouched.
- Coordinators hired from the market still range from about 2.5 to 3.4 stars, and later development still moves
  ratings up or down. That's the game.

**Display (rule 4).** The coordinator's effect rows on the staff screens (shot quality, spacing design, creator usage;
coverage, matchup scheming, discipline) already showed the ratings the engine uses, so a starting coordinator now shows
60 on each. The coordinator's **"Coach stars"** row used to be his overall staff grade divided by 20. That grade includes
personality, which the game sim never uses for a coordinator. It is now the average of his three effect ratings, so a
starting coordinator shows exactly 3.0 stars. The same applies to market coordinators (their row now matches what the
sim uses too). The head coach's row is unchanged.

**Seed file.** `data/overrides/gameplay_staff_seed.json` only holds name and archetype pools. The made-up ratings are
generated during data build (`ingest.py`, outside this task), so neutralizing happens where a save and the replay read
the slots.

## 2. Betting-odds test (20 runs a game, 1,231 games, 1,018 with market lines)

| | Seed 1001 before | after | Seed 2001 before | after |
|---|---|---|---|---|
| Brier score | 0.2060 | **0.2041** | 0.1992 | **0.1972** |
| Log loss | 0.6021 | **0.5975** | 0.5852 | **0.5808** |
| Spread error vs market (points) | 4.249 | **4.097** | 3.899 | 3.923 |
| Totals error vs market (points) | 5.681 | **5.513** | 5.839 | **5.545** |

Market: 0.1962 Brier, 0.574 log loss.

- "Before" is this branch's starting commit (`26d4db4`). Seed 1001 reproduces ODDS-COACH's after-numbers exactly.
  Seed 2001 is 0.1992, not ODDS-COACH's 0.1986, because of merges since then.
- **Size of the change.** Brier improves by about 0.002 on both seeds. That is about twice ODDS-COACH's +0.001 change,
  which was within noise, and the change has the same sign on both seeds. Log loss improves by about 0.0045 on both. The
  sim is now 0.0010-0.0079 Brier from the market, down from 0.0030-0.0098.
- Nothing else was tuned.

## 3. Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`)

- **18/18 before and after.** Every league metric moves by 0.1 z or less.
- Fouls per 100: 19.19 -> 19.26 (target 19.37). The made-up discipline ratings had been trimming fouls a little.
- Player per-36 average misses are about the same (points mean absolute 1.238 -> 1.241, rebounds 0.572 -> 0.566,
  turnovers 0.292 -> 0.301).

## 4. Tests

- New `tests/test_neutral_coordinators.py` (8 tests):
  - every starting coordinator in a new save is neutral (60 on each rating);
  - name, personality and status stay, and contract and age exist;
  - head coaches are unchanged;
  - coordinator effect terms are zero and fouls are neutral, while head coaches still differ;
  - staff screen rows show 60 and 3.0 stars;
  - market coordinators still vary;
  - other slots pass through untouched;
  - the 2025-26 replay's coordinators are neutral.
- `tests/test_odds_coach.py`: "same ratings a new save gives" now neutralizes the coordinators the same way.
- `tests/test_foundation.py`, `test_staff_queue_keeps_live_strategy_from_raising_budget`:
  - **What it checks:** an AI team can't hire using the raised "live" budget, only its original staff budget.
  - **Why it broke:** the test built an unaffordable hire by adding a fixed $1M to another Brooklyn staffer's pay. With
    cheaper neutral coordinators, Brooklyn had enough room left, so the hire went through. The test checked a real
    rule, but its setup leaned on the old pay level.
  - **Fix:** the setup now adds exactly enough to leave Brooklyn $1M short of the candidate's ask (never less than the
    old $1M). The rule under test is unchanged, and the test passes.
- **Core suite** (`scripts/run_core_tests.sh`): **338 OK** (2 skipped).
- **Focused run** (`run_tests_parallel.py --workers 2 --match "staff|coach|odds|game_context|foundation" --js`):
  - Python: 640 tests. The only failure was the foundation test above, now fixed (rerun alone: OK).
  - Browser: `startup_video.test.cjs` failed only because the git-ignored startup movie isn't in a fresh worktree. With
    the movie linked in, it passes 10/10. It is unrelated to this change.

## 5. Notes for the coordinator

1. **Overall staff grade still varies a little.** The big grade number on a coordinator's staff card is the overall staff
   grade. It feeds pay, job security and AI hiring and firing, and it includes communication and adaptability. Starting
   coordinators read 59.7-66.6 (mean 62.7) even though their engine effect is identical. A coordinator with all-60
   ratings and all-60 personality grades 62.3 on that scale. I left the grade formula alone because it also drives AI
   staff decisions. If the user wants the card number to equal engine impact for coordinators, that is a small follow-up
   (one formula in `staff.staff_grade` for coordinator slots), and it would shift AI retention thresholds a little.
2. **More coordinator turnover at the first contract ends is likely.** AI teams keep a coordinator at expiry only if his
   grade is at least 68 ("stable fit") or 76. Starting coordinators are now all below 68, so most will be replaced from
   the market when their first 2-5 year deals end. I didn't measure this over a multi-season run.
3. Scratch: `output/neutral-coordinators/` keeps `odds_summaries.json`, the scorecard text and JSON, and the scripts.
   The full betting-run files and the base-commit source copy were deleted.
