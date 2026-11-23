# INPUT-DATA-FIXES: fix the evidence bugs the input data audit found

Progress: 9/9 - done; report written, board row set to review

Owner: Claude (Opus agent), worktree branch `worktree-agent-a05cb62ef5f68df45`. Status: **review** (committed on the
branch; not pushed, not merged). Source: `docs/agents/tasks/input-data-audit.md` (ranked findings).

## TL;DR

1. Five evidence bugs fixed at the source, each re-checked against the raw capture first: two "paint shooting"
   columns that were copies of pull-up shooting, a movement-distance column that is zero for 94% of players, two
   pairs of near-identical columns that each voted twice, a handful of impossible rebound rates (125%, 200%), and two
   players whose play-type shares were stored in percent. The repeatability check now gives tied values a shared rank.
2. The ratings that actually change: floater / short-paint touch (pull-up shooters such as Bub Carrington and AJ Green
   drop 9-10 points; non-shooting drivers such as Ryan Dunn and Amen Thompson rise 9-11), rim-contest technique (up to
   +/-2.7), dribble persistence and the offense share of effort (small). No player's overall moves by 1.0; three
   players' defense moves by 1.0-1.2 (knock-on, explained below). Highest grade anywhere 92.4; nothing at 100.
3. Both scorecards are flat: 18/18 real-stat targets before and after; betting test Brier unchanged on both seeds
   (.2047, .1978), log loss within .0002, spread within .01 point, total points one seed .03 better, one .004 worse.

## What was wrong and what changed

The foul-drawing and ball-security findings (audit ranks 1, 2, 7, 8) were already handled by RATINGS-FT-TOV
(commits `e457e809`, `d7262108`, merge `3799bd85`): both inputs are measured per chance in `foul_security_evidence.py`
and the Basketball Index overlay skips them; the all-zero shooting-fouls column was removed from contact seeking; the
overlay ignores constant columns. Verified in the code and mapping; not redone. The remaining findings, in order:

| Audit rank | Re-checked against the capture (2023-24 / 2024-25 / 2025-26) | Fix |
|---|---|---|
| 3. Paint columns copy pull-up | "Paint Shooting Talent" = "Pull-Up Shooting Talent" on 570 / 567 / 578 of 570 / 567 / 578 rows; "Paint Shot Making Efficiency" = the pull-up version on 554 / 552 / 566 of 554 / 552 / 566. Paint Shot Quality and Shot Creation are copies too; Paint Shot Making (r .75) and Openness (r .45) are not. | Both copied columns removed from floater / short-paint touch (listed under `excluded` with the reason). There is no verified non-rim paint per-shot column to replace them; the floater measures and short-midrange percentage remain. |
| 4. Movement Distance Rating zeros | Zero for 524 / 525 / 544 players (259 / 261 / 272 of the 266 / 270 / 278 with 1,000+ minutes). No other offensive distance column exists (only defensive miles). | Removed from effort allocation (its only offensive vote); the offense share keeps the estimate. |
| Repeatability ties | Tied values got distinct ranks in sort order, so Movement Distance read 0.94 repeatable; with shared (average) ranks it is 0.44. | Ties share their average rank. Re-screened all 173 mapped measures: 18 weights move by 0.005+, mostly up slightly (count stats with many zeros, e.g. pick-sixes .54 -> .63, goaltends .87 -> .96); post-up impact .20 -> .15. `data/research/input_data_fixes.json`. |
| 5. Rim percentages vote twice | "Stable Defensive FG% at Rim" vs "Stable Rim dFG% vs. Expected": r .990 / .993 / .992. The unstabilised rim rate is a different signal (r .43), left alone. | The pair shares one vote (new `vote_group` in the mapping), weighted like its stronger member. |
| 6. Dribbles and seconds per touch | r .979 / .985 / .984. | Same: one shared vote in dribble persistence. |
| 9. Impossible rebound rates | 8 player-seasons, all under 150 minutes: defensive success up to 125% (six in 2023-24), offensive success 125% (Mo Bamba, 44 minutes, 2025-26), offensive contested share 200% (2023-24). Units are percentage points. | New `valid_range` [0, 100] on the four rates: an impossible value is not read for that season (the rating itself is never capped). |
| 10. Crafted impact text | In the March snapshot, impact cells are text with a percentile ("-1.4 27%"), which the number reader rejects; the reader then fell back to the separate numeric columns. The numeric offense column matches the text's number (497 of 499) and the April values (mean gap .13). The numeric defense column agrees with April (gap .17) while the text's defensive number does not (.67). | The verified numeric columns are now read first and the text is never parsed (made explicit, test added). No player changes: every player with March data also has April data with minutes, and April is preferred. |
| 11. March play-type shares above 1 | Two rows (Killian Hayes, Zyon Pullin) store all ten shares in percent (22.0 for 22%); a 1% roll-man share was read as 100%. The April file has none. | A row with any share above 1 has all its shares divided by 100 when the snapshots are loaded. |

Files: `src/nba_gm_data/bbi_evidence.py` (shared-rank repeatability, `vote_group`, `valid_range`; overlay version
v5), `src/nba_gm_data/input_estimator.py` (play-type units, impact column order), `data/research/bbi/bbi_input_mapping.json`
(v7), `scripts/research/input_data_fixes.py` + `data/research/input_data_fixes.json` (the checks above),
`tests/test_input_data_fixes.py` (11 tests), rebuilt `data/canonical/player_inputs_2026_27.json.gz`,
`data/canonical/tendency_scale_map.json`, and the builder's generated tables in `e2-input-estimator.md`.

## Which players moved and why

Rebuild: `PYTHONPATH=src .venv/bin/python scripts/build_player_inputs.py` (run on the Azure pool). A rebuild of the
last commit reproduced the committed inputs file byte for byte, so every difference below comes from this task.

**Floater / short-paint touch** (half the league moves 1+ point, 122 players 3+): it had been partly grading pull-up
shooting. Down: Bub Carrington 40.5 -> 30.3, AJ Green 48.1 -> 38.8, Rui Hachimura -8.7, Miles McBride -8.4, Giannis
-7.6, Khris Middleton -7.4, Jamal Murray -7.2, Cade Cunningham -7.1. Up: Ryan Dunn 51.6 -> 63.0, Amen Thompson 62.5 ->
71.9, De'Anthony Melton +8.3, Myles Turner +8.0, Paolo Banchero +7.4.
**Rim-contest technique** (110 players move 1+, none 3+): the two rim percentages no longer outvote rim deterrence and
block rate. Up: Harden, Thybulle +2.7, Royce O'Neale +2.5, Caldwell-Pope +2.2; down: Wendell Carter Jr. -2.1, Paul
George -2.0.
**Dribble persistence** (tendency): Jokic .44 -> .56, Lonzo Ball .55 -> .44. **Offense share of effort**: back to the
estimate (Horford, Keon Ellis, Hauser, Dyson Daniels about -.06; Doncic, Embiid +.04).
**Hayes and Pullin**: their play-type driven priors fall (Hayes post sealing -2.3, Pullin lob finishing -2.1 and
cutting routes -2.0, small physical moves).
**Everything else**: other technique grades move by a median .04 (95% under .3), the knock-on of the league-wide value
tables and the opening-day level step re-placing players on their targets.

**Overall / offense / defense (as a new save shows them):** 132 players move overall by 0.1+, **none by 1.0+** (largest:
Brandon Clarke 73.9 -> 74.8, Jamarion Sharp 73.7 -> 73.0). Offense: none by 1.0+. **Defense by 1.0+: Jamarion Sharp
76.4 -> 75.2, Andre Drummond 80.9 -> 79.9, Jake Stephens 76.6 -> 75.6.** None of the three moved on his own evidence
(Sharp and Stephens have no NBA minutes; Drummond's rim-contest grade changed by .4). They are placed by the
opening-day level step, which aims each at a target value; in the old file they sat above their targets (Drummond
+.14, Sharp +.19), in the new one they land on them. Across the 637 placed players the largest miss from target fell
from .26 to .14 points per 100. Top three unchanged (Jokic 95.2, SGA 94.8, Wembanyama 93.5).

**No clipping:** highest grade in the file 92.4 (was 92.5); no grade at or above 99.5.

## Gates (last commit `f7aaa327` -> this branch)

**Real-stat scorecard** (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18 -> 18/18.**
Player misses per 36: points 1.206 -> 1.204, shot attempts .891 -> .897, threes .271 -> .273, free throws .570 ->
.577, rebounds .549 -> .544, assists .453 -> .465, turnovers .281 -> .279, steals .184 -> .183, blocks .189 -> .191,
true shooting .021 -> .022. Mixed and small; league levels essentially unchanged (offensive rating 113.4 -> 113.3).

**Betting test** (`validate-season-probabilities --runs 20`, 1,231 games, 1,018 with market odds):

| | Seed 1001 before | after | Seed 2001 before | after |
|---|---:|---:|---:|---:|
| Brier (market .1962) | .2047 | .2047 | .1978 | .1978 |
| Log loss (market .5740) | .5992 | .5991 | .5827 | .5829 |
| Spread miss vs market | 4.115 | 4.116 | 3.944 | 3.953 |
| Total miss vs market | 5.721 | 5.725 | 5.875 | 5.844 |

Player props: the output carries props only for its 20 sample games, so they were not scored separately.

**Tests:** core suite 341 tests pass (one module first errored on a git-ignored reference file from the main checkout's
`output/`; linked and rerun: OK). Focused: `test_input_data_fixes`, `test_bbi_evidence`, `test_foul_security_evidence`,
`test_input_estimator`, `test_public_shot_evidence`, `test_rating_scale_consistency`: 115 pass (same reference-file
link needed for one).

## Notes for the coordinator

- Not fixed, outside the audit's list: "spotup_pct" and "transition_pct" in the March snapshot correlate above .98
  (audit, duplicate list); the help-defense talent / activity pair is a near-copy, but only one of them is mapped.
- The level step leaves a few players up to .14 off their target; more iterations would close it (not touched here).

## Resume state (done)

- Worktree links (git-ignored): `.venv`, BBI `normalized.json` and the contents of `normalized/ raw/ tools/`,
  `captures/{fanspo_*,leaderboard,tools,bbi_metric_catalog*}`, injury evidence v2-v4, barttorvik raw,
  `output/azure_*`, two `output/` test reference folders. `values_recent.json.gz` copied.
- Logs: `output/azure-idf-{before,after}-{cal,odds1001,odds2001}.log`, `output/azure-idf-build.log`; snapshots and
  helper scripts in the worktree's `output/input-data-fixes/`.
