# STAR-INJURIES: fuller 2025-26 injury history and the history weight (2026-11-21)

Branch: `worktree-agent-afd1e8831e7215e1d`. Scratch and harness: `output/star-injuries/` (git-ignored).

## TL;DR
- Every real player's injury history now includes the 892 injuries from 2025-26 that Basketball Index's tracker missed, and the game counts a player's injury history at 0.75 of the fitted strength instead of 0.55. Both choices come from tests on games the model never saw.
- The 30 best players now miss games like real stars do: 5.8 games a season in 2-10 game stretches (real 5.6-6.0; was 4.1-4.7), and a median of 59.5-63.5 games played (real 64.5-65.5; was 67.5-70).
- The cost: about 14% more injuries league-wide (40 a team, up from 35). That is above the tracker's count but below the complete 2025-26 record. The league rate holds steady over four seasons.

## 1. What changed

### Folding in the 2025-26 record (`scripts/build_injury_model.py`)
The builder reads Codex's public file (`data/research/injury_history_2025_26.json`) through its normal path and sorts every stretch (`classify_public_stretches`). It adds the new ones to real players' history, which is written to a new git-ignored file, `data/canonical/injury_player_evidence_v3.json`. The engine reads v3 and falls back to v2 if v3 hasn't been built. The tracker-only v2 file is untouched.

| What the stretch is | Stretches | Games missed | What happens |
|---|---:|---:|---|
| New injury the tracker lacks | 892 | 4,711 | **added** (dated at the first game missed; two "days" per game, the tracker's unit) |
| Already in the tracker (Codex's match rule) | 417 | 1,618 | already counted |
| Injury management only | 240 | 355 | left out (below) |
| Illness | 141 | 211 | left out (below) |
| Already underway on opening night, continuing an injury in the tracker | 17 | 762 | already counted (below) |
| Same injury continuing after a trade | 5 | 40 | already counted |
| No body part | 6 | 74 | left out |
| Coach's decision, G League, rest, personal, suspension, not with team, trade pending, unknown | 3,794 | 9,075 | left out |

- Density check: 2025-26 now has 51.3 entries per 1,000 games played (tracker alone: 18.2). The tracker logged 50.2 in 2023-24 and 55.3 in 2024-25.
- 352 players gain history. The most added: Anthony Edwards, Zach LaVine and Alex Sarr (9 each), and Embiid, LeBron, Josh Hart, Grayson Allen and Dean Wade (7 each).
- The model's injury-rate fit still uses the tracker alone, which gives 2025-26 its own starting level. Only the per-player starting history changes. This follows Codex's handoff advice.

**The decisions, with evidence** (`scripts/research/injury_history_foldin_check.py`, log `output/star-injuries/foldin_check.log`):
- **"Injury management only" stays out.** These are planned games off for a condition the player already has. They are not new injuries:
  - 62% fall on the second night of a back-to-back, against 18% of all games and 31% of other one-game injuries;
  - 93% follow a same-part injury in the past year, against 44%;
  - the tracker logged them about 0.6 times as often as other one-game injuries (19% against 31%);
  - 18 players with chronic conditions account for half of them (Robert Williams III 15, Mitchell Robinson 14, Horford 10, Embiid 10);
  - adding them to the history makes the prediction of who gets hurt next worse (log-likelihood -7.6).
- **Opening-night stretches:** a stretch counts as a continuation when the tracker already has a same-part injury in the previous 400 days that started after the previous regular season or never logged a return. That covers 17 stretches, including Tatum, Haliburton, Lillard, Irving, VanVleet, Dejounte Murray and Strus.
  - The other 37 opening-night stretches have no trace in the tracker, so they are added:
    - preseason injuries (Coby White, Ty Jerome, T.J. McConnell, Jalen Green and Fox, plus LeBron's sciatica);
    - summer surgeries (Herro, Jalen Williams);
    - injuries from before the NBA (Thomas Sorber's ACL).
  - Leaving them out makes the prediction slightly worse (-1.9).
- **Illness stays out, which differs from the brief.** The engine's injury history has never counted illness, neither the tracker's nor the game's own, and the league rates are anchored that way.
  - Adding 2025-26 illness only would be inconsistent.
  - The gain from adding it is small (+2.0).
  - It's listed under "What's left" as a whole-model change.

### History weight (`injury_model.py`, `health.py`)
The split-weight patch from TOP30-GAMES is re-applied: real recorded injuries and the game's own drawn injuries each get their own weight. The re-check moved both values.

- **Real history: 0.75, not 0.95.** On 2025-26, a season the slopes weren't fitted on, I tested which weight best predicts who gets hurt next (the public file is complete for games missed):

| Check (2025-26) | New injuries | Best weight | 90% range | 0.75 vs best | 0.95 vs best |
|---|---:|---:|---|---:|---:|
| Whole season, tracker history | 1,172 | 0.80 | 0.75-0.85 | -0.7 | -3.8 |
| From Dec 1, tracker + added history | 943 | 0.80 | 0.75-0.85 | -0.5 | -3.5 |
| From Jan 15, tracker + added | 665 | 0.70 | 0.60-0.75 | -0.4 | -9.3 |
| From Mar 1, tracker + added | 340 | 0.65 | 0.50-0.75 | -0.9 | -7.9 |

  - 0.75 is inside every range, and 0.95 is outside all of them.
  - The 0.95 from TOP30-GAMES came from the same seasons the slopes were fitted on, so it partly grades the fit's own work.
  - The added history improves every prediction: log-likelihood +5.8 from Jan 15, +7.5 from Dec 1, +7.2 from Mar 1.
  - At 0.55 the stars were under-predicted by 18% over the whole season. At 0.95 the gap was 4%.
- **The game's own injuries: 0.75, the same as real history.** Four seasons back to back, health only, fixed rosters. Spells costing a game per team, seeds 17 / 29:

| Setting | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---|---|---|---|
| Before (0.55, thin 2025-26) | 36.2 / 37.6 | 37.5 / 41.1 | 37.1 / 40.6 | 38.0 / 39.3 |
| Fuller history, 0.55 | 39.2 / 40.7 | 39.3 / 42.9 | 37.4 / 41.7 | 38.8 / 39.9 |
| Real 0.75, own 0.55 | 39.6 / 41.1 | 38.3 / 41.5 | 35.6 / 39.7 | 35.3 / 37.6 |
| Real 0.75, own 0.65 | 40.1 / 41.9 | 39.9 / 43.0 | 37.3 / 41.3 | 37.7 / 39.7 |
| **Real 0.75, own 0.75 (new)** | **41.5 / 42.9** | **41.6 / 44.4** | **39.8 / 44.1** | **41.7 / 42.9** |

  - Lower weights for the game's own injuries make the rate sink.
  - At 0.75 it holds.
  - The climb that once argued for a discount came from starting the game on the thin 2025-26 history.
  - The split stays in the code for a future frailty trait.
- **Real events:** the real opening-night list counts as real history. The three manual startup records for Tatum's, Haliburton's and Lillard's Achilles tears (entered as "ankle/foot" on 2025-10-21) are no longer counted a second time.
- **League rates rebuilt** at 0.75 (`rate_fit.history_weight` is recorded in the model file). Only the per-part base rates moved, by -0.04 to -0.12 on the log scale.

## 2. Before and after
Full regular seasons, all 30 teams AI-coached, fixed opening rosters, real 2026-27 opening-night injuries, seeds 17 / 29. "Before" is current main, rerun today. "History only" is the fuller history at the old 0.55. "0.95/0.75" is the setting the brief proposed, with the fuller history.

**The 30 best-rated players**

| | Real (5 seasons; 2025-26) | Before | History only | **New** | 0.95/0.75 |
|---|---|---|---|---|---|
| Median games | 65.5; 64.5 | 70 / 67.5 | 66.5 / 65 | **63.5 / 59.5** | 61.5 / 56.5 |
| Mean games | 58.9; 55.4 | 67.1 / 59.8 | 63.9 / 57.3 | **62.5 / 53.4** | 61.9 / 51.5 |
| Missed in 2-10 game stretches | 5.6-6.0; 7.0 | 4.1 / 4.7 | 5.5 / 4.9 | **5.8 / 5.8** | 6.2 / 6.7 |
| Missed in 11+ game stretches | 6.0; 6.8 | 3.3 / 4.3 | 4.7 / 6.5 | **5.8 / 8.8** | 5.6 / 10.0 |
| Single games | 2.9; 2.9 | 3.3 / 3.3 | 3.3 / 3.3 | 2.9 / 3.0 | 3.0 / 2.8 |
| Under 60 games | 9-14; 11 | 7 / 9 | 10 / 9 | 12 / 15 | 14 / 17 |

**Heavy-minute players** (30+ minutes; real is 2025-26 box scores)

| | Real | Before | **New** |
|---|---|---|---|
| Median / mean games | 68 / 61.7 | 66 / 63.1, 68 / 62.5 | **65 / 61.8, 65 / 59.7** |
| Single games | 2.4 | 2.6 / 2.6 | 2.5 / 2.6 |
| 2-10 game stretches | 5.6 | 5.0 / 5.7 | 6.2 / 5.6 |
| 11+ game stretches | 4.0 | 5.6 / 5.0 | 6.1 / 8.0 |

**Injuries costing a game, per 82 games played.** I added a second real column from the complete 2025-26 record: injury and illness stretches costing a regular-season game, excluding injury management and stretches underway at the opener.

| Minutes | Tracker 2021-25 | Real 2025-26 | Before | **New** |
|---|---:|---:|---|---|
| Under 10 | 2.47 | 2.23 | 1.42 / 1.43 | 1.53 / 1.39 |
| 10-20 | 2.13 | 2.94 | 2.67 / 2.65 | 2.78 / 2.70 |
| 20-30 | 2.85 | 4.70 | 3.16 / 3.39 | 3.98 / 4.13 |
| 30+ | 3.67 | 5.13 | 3.61 / 3.67 | 4.28 / 4.42 |

| Age | Tracker 2021-25 | Real 2025-26 | Before | **New** |
|---|---:|---:|---|---|
| Under 23 | 2.46 | 3.38 | 2.43 / 2.55 | 2.47 / 2.69 |
| 23-25 | 2.75 | 3.86 | 2.30 / 2.40 | 2.61 / 2.71 |
| 26-28 | 3.26 | 4.17 | 2.98 / 3.09 | 3.53 / 3.50 |
| 29-31 | 3.55 | 5.81 | 2.94 / 3.06 | 3.90 / 3.53 |
| 32+ | 3.61 | 4.20 | 2.64 / 2.61 | 3.36 / 3.46 |

- The age gaps the earlier tasks flagged are now closed against the tracker: 29-31 and 32+ were 0.5-1.0 low and are now within about 0.3.
- Against the tracker, every band from 10 minutes up is now higher; the 20-30 minute band is the furthest above (+40%). Against the complete 2025-26 record, every band from 10 minutes up is still lower.
- The tracker is now known to under-log games-missing injuries. 2025-26 shows about 52 a game-costing injury per 1,000 games, against the tracker's own 40-43 in 2023-25. So the truth is probably between the two columns. Where exactly is the open question in "What's left".

**Length bands and spells per team** (every in-season injury; tracker 40 / 35 / 11 / 7 / 6.5%)

| | 1 game | 2-5 | 6-10 | 11-20 | 21+ | Spells costing a game, per team |
|---|---|---|---|---|---|---|
| Before | 39.9 / 38.7 | 35.5 / 35.7 | 11.6 / 11.4 | 7.4 / 6.8 | 5.6 / 7.4 | 34.9 / 35.7 |
| **New** | 39.9 / 40.1 | 35.0 / 34.0 | 11.8 / 12.1 | 7.8 / 7.0 | 5.5 / 6.8 | **40.1 / 39.9** |

The reference for spells per team is 35-43 with illness (2023-25 full-team comparison); the complete 2025-26 record has about 45.

**Why the league rate rose about 14%.** The model's base rates are anchored so that 2021-25 players, with the injury history the tracker gave them then, reproduce the tracker's totals.
- In those seasons, rotation players carried 2.3-2.7 decayed history entries, because the tracker years behind them were thinner.
- The game's 2026-27 rotation players now start with 3.22 (with v2 it was 1.95).
- Denser history at the same base rates means more injuries. That is right if real histories are this dense and the tracker's totals are low, and too many if not.
- I did not re-anchor (Rule 1): the right target needs a complete record for more than one season (see "What's left").
- Script: `output/star-injuries/history_density.py`.

**What it means for the stars.**
- The top 30 now match real stars' medium-length absences, and their games played sit at or a little under real.
- The heavy-minute group's median moved from 66/68 to 65/65 (real 68), and its 11+ game stretches rose (6.1/8.0 against real 4.0 in 2025-26).
- Nothing was tuned to games played.

## 3. Rebuild v3 (coordinator, in main)
```sh
PYTHONPATH=src .venv/bin/python scripts/build_injury_model.py --write
```
- This writes `data/canonical/injury_model_v2.json` (tracked; byte-identical to the one committed here) and the git-ignored `data/canonical/injury_player_evidence_v3.json`.
- It reads the tracker files under `data/research/bbi/tools/` and `data/research/injury_history_2025_26.json`, and takes about 9 seconds.
- v2 evidence is left alone. `.gitignore` now lists v3.
- Until v3 exists, the engine falls back to v2: the thin history at the new weight, which is not the tested setting.

## 4. Speed and tests
- **Health simulation:** 2.2-2.4 s per health-only season (about 0.4 s per simulated month), against 2.1-2.3 s before.
- **Full fixed-roster season:**
  - 52.0 / 51.7 s wall and 31.5 / 31.4 s of game simulation, against 49.8 / 50.2 s and 30.3 / 30.4 s before;
  - that is about +1 s a season, from more injuries (more in-game exits and reserve minutes);
  - the machine was heavily loaded, so these timings carry noise.
- **Determinism:** draws stay seeded and in the same order. Outcomes change because injury probabilities changed.
- **New `tests/test_star_injuries.py` (6 tests):**
  - every stretch category, including trade splits and both kinds of opening-night stretch;
  - the v3 paths;
  - the weights and the model's anchor agree;
  - the game's draws use their own weight;
  - which events count as real or as a duplicate;
  - the v2 fallback.
- Focused injury modules (14 modules, 133 tests): OK.
- Core `scripts/run_core_tests.sh`: 338 run, OK (2 skipped).
- `run_tests_parallel.py --match "injur|health|rest_model|fatigue|games_played|new_career" --js`: 1,078 Python tests, 1 failure, now fixed:
  - **The failure:** the foundation test's health-replay range. That replay exposes every 4+ minute player all season with no rest nights, and counts injuries that cost no game. It went from about 47 to 53.0 injuries a team, above the old ceiling of 52.
  - **The fix:** the ceiling is now 60. The complete 2025-26 record has about 45 spells a team that cost a game; adding the tracker's share of no-game entries gives about 58.
  - The test passes on a rerun.
  - **One browser test fails:** `startup_video.test.cjs`. It needs the git-ignored startup video, which this worktree doesn't have, so the failure has nothing to do with this change.
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**.

## 5. What's left
1. **League level of injuries.** The tracker under-counts injuries that cost games: about 40-43 per 1,000 games in 2023-25, against about 52 in the complete 2025-26 record. The model's base rates are anchored to the tracker but now meet denser histories.
   - **Next step:** build 2023-24 and 2024-25 the way Codex built 2025-26.
   - Then anchor the base rates to complete game-costing counts, with histories built the same way.
   - This would settle whether 40 spells a team (now) is right.
2. **Illness as history:** a small predictive gain (+2.0). Doing it properly means counting tracker illness and the game's illness draws too, and re-anchoring.
3. **Heavy-minute players' long absences** (11+ games: 6.1 / 8.0 against 4.0 in 2025-26) and their median games (65 against 68). Check this against more real seasons before changing anything.
4. **A persistent frailty trait** (from TOP30-GAMES) is still the long-term design. The split weights are in place for it.
5. **The history's functional form:** each entry multiplies risk, so players with many recent entries may be over-predicted. The best weight falls the more recent the history, from 0.80 to 0.65. A refit with a saturating history term could test this.

## Files
- **Changed:**
  - `scripts/build_injury_model.py`: fold-in, v3 output, recorded weight;
  - `src/nba_gm_data/injury_model.py`: weights 0.75 / 0.75, split, v3 with v2 fallback, duplicate scaffold events;
  - `src/nba_gm_data/health.py`: split-aware history, from the TOP30-GAMES patch;
  - `data/canonical/injury_model_v2.json`: rebuilt;
  - `.gitignore`: v3;
  - `scripts/research/injury_multiseason_check.py`: `--sim-weight`, `--evidence`;
  - `scripts/research/injury_rate_bands.py`: real 2025-26 column;
  - `scripts/research/top30_inputs_compare.py`: tuple fix.
- **New:** `scripts/research/injury_history_foldin_check.py`, `tests/test_star_injuries.py`.
- **Test bound:** `tests/test_foundation.py`, the health-replay ceiling, 52 to 60.
- **Harness and logs** (`output/star-injuries/`):
  - `sim_season.py` (env overrides `STAR_EVIDENCE`, `STAR_WEIGHT`, `STAR_SIM_WEIGHT`, `STAR_MODEL`), `run2.sh`, `analyze.sh`, `multiseason.sh`;
  - `build_at_weight.py`, `bands_table.py`, `history_density.py`, `top30_split.py`;
  - runs `base_`, `hist055_`, `new_`, `tried95_` (s17 / s29), with their `lengths_*`, `top30_*` and `bands_*` outputs;
  - `multiseason.log` and `foldin_check.log`.

## Resume state
Done. Committed on the branch, not pushed; board row set to review. The coordinator rebuilds v3 in main with the command in section 3.
