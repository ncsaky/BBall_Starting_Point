# ODDS-COACH: betting test uses the saves' staff model with the real 2025-26 staffs

Owner: Claude worker (worktree branch `worktree-agent-af94ae6dd58dea634`). Status: **review**.

## TL;DR
- The betting test and real-stat report now replay 2025-26 with that season's real head coaches (including the two in-season changes), rated by the same staff model a save uses. Saves are byte-for-byte unchanged.
- The betting score is about the same: Brier +0.001 on both seeds, which is within noise, and a dice-free check is slightly better. The real-stat report stays at 18/18.
- Finding: a new save's coordinators are made-up starting ratings, and on real teams they point the wrong way. The real head coaches' effect is real but small.

## 1. The gap (before this change)
- **Formula.** Saves install `save.save_coach_ratings` (save.py:6779, installed at save.py:2254 and 4286). It gives one star value per staff rating, and `sim.coach_effect` then takes the staff branch (sim.py `staff_coach_effect`, the "Save staff (coaching overhaul 2026-11-18)" section). The replay built `coach_by_team` from `sim.coach_ratings` (sim.py:490 before; index at sim.py:204). That uses the old nine reputation stars (`COACH_DEFAULTS` and `COACH_REPUTATION_OVERRIDES`, sim.py:49-73, with only 11 coaches listed), so the old branch of `coach_effect` ran.
- **Effects the save path has that the replay lacked:**
  - offensive coordinator: shot quality, spacing design scaled by the roster's shooters, creator usage scaled by its main creator;
  - defensive coordinator: coverage, matchup scheming, discipline;
  - head coach: player relations and game management on both ends;
  - playoff edge from game management and matchup scheming;
  - discipline also lowers personal fouls (`foul_rate_multiplier`, which had been neutral in replays).
  - Rotation management (matchup minutes, return ramp) and star workload apply only to generated minutes, so they do nothing in replay-real-minutes either way.
- **Old formula's size.** It multiplied coach effects by a roster "fit" factor of 0.35 to 1.0 (`scaled_coach_effect`, old branch). That is part of why coach effects measured about half-strength.
- **Wrong season's staff.** `coach_ratings` read the head coaches from the 2026-27 universe's `staff_profiles`. So 2025-26 games used Sean Sweeney for Orlando, Taylor Jenkins for Milwaukee, Dusty May for Dallas, Tiago Splitter for Chicago, Micah Nori for Portland and Jamahl Mosley for New Orleans. The real coaches were Mosley, Rivers, Kidd, Donovan, Billups then Splitter, and Green then Borrego. (The repo's `universe_2025_26_preseason.json` has the same contamination for Milwaukee and New Orleans, so it was not used.)

## 2. The staffs file: `data/research/staffs_2025_26.json`
- **Opening-night coaches:** all 30 from CBS Sports' 2025-26 coach tiers (Sam Quinn, 2025-10-13).
- **In-season changes:**
  - Portland: Billups was arrested 2025-10-23, the morning after the opener. Splitter was interim from the next game, 2025-10-24 (CBS Sports, 2025-10-23).
  - New Orleans: Green was dismissed 2025-11-15 at 2-10, and Borrego was interim from then (NBA.com, 2025-11-15).
  - Rivers, Kidd, Donovan and Mosley coached their full seasons (Hoops Rumors, AP/KSL, NBA.com's 2026-27 new-coaches piece, Last Word On Sports). Every source has its URL and date in the file.
- **Ratings:** the game's own rule for a real head coach in a new save. The team's starting head-coach slot is calibrated once to his reputation grade (`staff.HEAD_COACH_REPUTATION_GRADES`, via `apply_head_coach_reputation`). Every 2025-26 coach is in that table except James Borrego.
- **Borrego:** no 2025-26 ranking includes him. He is rated at grade 60, the game's neutral point (three stars on each head-coach rating), the same grade the table gives the season's other interim, Splitter. Reason recorded in the file. It was not looked at against either scorecard.
- **Coordinators:** each team's starting offensive and defensive coordinator slots, exactly as a new save starts them. Teams don't publish coordinator titles consistently, and the game has no evidence-based assistant ratings. Named lead assistants are recorded for reference only (Cleveland Bryant, Dallas Triano, Indiana Pierce, Clippers Van Gundy, Sacramento Woodson, San Antonio Sweeney, New Orleans Borrego).

## 3. Code
- `sim.replay_staff_stints(canonical, root)`: each team's 2025-26 coaches in order, with first game dates. Each one gets the team's starting slots, the save calibration and `save.save_coach_ratings`, so it is the same code path a save uses.
- `sim.replay_coach_indices`: `coach_by_team` (the opening-night coach) plus `coach_changes_by_team`.
- `sim.coaches_on_date`: the coach in charge on a game's date. Used by `sim_game_with_context` and `explain_game_probability`.
- Only `load_sim_context(root)` with no canonical, meaning the save-less tools, attaches the replay staff. Saves always pass their own canonical. That path is unchanged and still overwritten with the save's staff.
- `staff.apply_head_coach_reputation(slot, name, grade=None)`: the optional `grade` rates a coach the table lacks. Saves never pass it.
- Tests: `tests/test_odds_coach.py` (6). They cover:
  - every team has its 2025-26 coach, not the 2026-27 hire;
  - Portland and New Orleans switch on the right dates;
  - the ratings equal what a new save gives that coach on that team's slots;
  - every coach is graded or documented, with a listed source;
  - the explicit grade matches the table rule;
  - a save context gets no replay staff and keeps the old index.

## 4. Save-identity proof
Script: `output/odds-coach/save_identity.py`. It runs a fresh Boston save (seed 55) through the GUI's own actions, `create_save` then eight `advance_save` days (2026-10-20 to 10-28). The base commit `0215bec` engine and this branch's engine ran the same script, and the saves were compared field by field.
- **Identical:** all 163,482 fields of the saved league, including 48 game results (10 full box scores of 2,916 fields each, the rest summaries), and every action response.

## 5. Betting-odds test (20 runs a game, 1,231 games, 1,018 with market lines)

| | Seed 1001 before | after | Seed 2001 before | after |
|---|---|---|---|---|
| Brier score | 0.2049 | 0.2060 | 0.1977 | 0.1986 |
| Log loss | 0.5997 | 0.6021 | 0.5825 | 0.5842 |
| Spread error vs market | 4.147 | 4.249 | 3.960 | 4.007 |
| Totals error vs market | 5.657 | 5.681 | 5.634 | 5.771 |

Market: 0.1962 Brier, 0.574 log loss.
- **Seed noise:** at 20 runs the two seeds differ by 0.007 Brier, while the change is about +0.001 on both.
- **Dice-free check:** the engine's expected margins on the 1,017 games with lines, through a normal curve, no random draws. Brier 0.1987 before, 0.1982 after: slightly better, not worse.
- **Takeaway:** the change is within noise on Brier, and slightly worse on spread and totals error.

## 6. Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`)
- **18/18 before and after.** Every league metric moves by 0.1 z or less.
- Fouls per 100 go from 19.26 to 19.18: coordinator discipline now acts in replays.
- Player per-36 average absolute misses are about the same (points 1.262 to 1.235).

## 7. Coach effect sizes (findings only; nothing was refit)
Method: each game's expected home margin was split into terms (`output/odds-coach/terms.py`, the overnight-margins decomposition with the coach split into a head-coach part and a coordinator part). Then the market's spread and the real margins were regressed on the terms, on the 1,017 games with lines. Output: `output/odds-coach/terms_analysis.txt`, `offline_brier.txt`.

| Coach part | Spread across games (points of margin) | Market weight | Real-results weight | Dice-free Brier without it |
|---|---|---|---|---|
| Old replay formula (reputation stars) | 1.57 | 0.35 (se 0.06) | 0.08 (se 0.29) | 0.1987 -> 0.1969 |
| New: coordinators (save's starting ratings) | 0.95 | **-0.83 (se 0.10)** | **-1.48 (se 0.48)** | 0.1982 -> 0.1969 |
| New: real head coaches | 0.34 | 2.2 (se 0.29) | 1.2 (se 1.4) | no change (0.1969 either way) |

What the numbers say:
1. **The coordinator part points the wrong way on real teams.** A new save's starting coordinators are generated per team, not scouted (for example, Golden State's starting defensive coordinator is worth about +1.1 points per 100 and Utah's about +1.3). On real 2025-26 teams their effect runs against both the market and real results. In gameplay that means every new save hands real teams made-up coordinator edges of up to about 1.3 points per 100 on one end. This is a rating question (rule 1), not an effect-size question. The options are to start coordinators neutral or rate them from evidence. That touches save creation (`staff.py` and `save.py`), which is outside this task.
2. **The real head coaches' part is real but small.** The market weights it about 2.2 times what the engine gives it (player relations 0.25 and game management 0.2 points per 100 per star, each end). The caveat: reputation rankings partly reflect team quality, so the weight may absorb strength the player ratings miss. Real results can't tell (se 1.4), and scaling it up does not move win-picks (dice-free 0.1969 to 0.1971 at double). Not changed.
3. The old formula also measured near zero against real results (0.08). Coach effects have so far not been shown to help win-picks in either form.

## What's left
1. Decide how a new save's starting coordinators are rated: neutral, or evidence-based for real staff. That would be its own task touching `staff.py` and save creation. After it, rerun this test.
2. Evidence-based ratings for coordinators and lead assistants would need a per-assistant source (team defense or offense under each coordinator, adjusted for roster). The named lead assistants in the staffs file are a starting point.
3. The head-coach effect size could be revisited with more seasons. One season can't separate coach quality from team strength.
4. Disk was nearly full during this task (as low as 117 MB free at one point; about 19 GB free after the crash and cleanup).

## Tests
- Focused (odds coach, coaching effects, staff lifecycle, game-context margins, win-pick shooters, box score reconciliation, box star stats, box variation, forward tuning, game minutes, foundation, plus-minus, narrative simulation): **312 OK** (14 skipped).
- Core suite (`scripts/run_core_tests.sh`): **338 OK** (2 skipped).
- Scratch kept small: `output/odds-coach/` holds the four odds summaries (`odds_summaries.json`), the term analyses, the identity check and the scripts. The full run files were deleted.
