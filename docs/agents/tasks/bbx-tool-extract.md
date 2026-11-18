# Basketball Index saved tool extraction

The three captures with inline player data yielded 139,812 historical talent rows, 173,290 forward forecasts, 6,945 player absence records, and the 2026–27 minutes and roster talent tables.  
The two Role Lab captures contain zero player rows. Each page calls for four separate data files. The defensive page does include seven height coefficients.  
The exports reproduced byte for byte from the five local captures. The largest file is 4.58 MB.

## Reproduce the exports

Run `.venv/bin/python scripts/bbi_extract_tools.py` from the repository root. The script reads `data/research/bbi/captures/tools/` and writes `data/research/bbi/tools/`. The capture receipt is dated 2026-11-17 04:53:56 UTC. Use `--output` to verify against a fresh directory. `--captures` and `--canonical` override the source directory and player index. The extractor uses Python's standard library and reads data literals without executing the source JavaScript. All inputs were local.

The manifest `inventory.json` contains 35 entries, with filenames, row counts, and match numerators and denominators for tables with top-level player IDs. Counts are for complete embedded tables, including rows filtered out by the page's default view. JSON uses `null` for missing values, and CSV uses blank cells. Source `NaN` also becomes missing. The gzip files omit timestamps.

## Player identifiers and match coverage

`player` is the name as recorded by Basketball Index. `player_id` is the matching ID from `data/canonical/universe_2026_27_offseason.json`. Matching requires a unique exact name after folding case, accents, spaces and punctuation, or an established alias. The alias pairs come from the existing leaderboard importer and league trait imports. Source teams are retained where available and can differ from our roster. The match counts use distinct source names in each file, so repeated seasons or injuries do not increase the denominator. Injury records also carry the source's `player_key`. The minutes and talent pages identify players by name and team. Growth Curve generally uses names alone, with team codes on coach-season and roster tables.

| Dataset | Names matched |
|---|---:|
| Growth Curve history, forecasts, roles and development | 551 / 1,505 (36.6%) |
| Growth Curve current projection grid and composite baselines | 507 / 516 (98.3%) |
| Growth Curve coach detail | 437 / 854 (51.2%) |
| Growth Curve team-view inputs | 550 / 571 (96.3%) |
| Injury Tracker player panel, seasons and durability/availability | 547 / 589 (92.9%) |
| Injury Tracker detailed absence history | 455 / 479 (95.0%) |
| Injury Tracker body-part risk | 540 / 582 (92.8%) |
| Injury Tracker examples | 319 / 788 (40.5%) |
| Injury Tracker team cores | 266 / 270 (98.5%) |
| Minutes players | 546 / 559 (97.7%) |
| Talent grid players | 327 / 328 (99.7%) |

The current universe has limited coverage of retired players in the historical tables. Unmatched names retain their original spelling and a missing game ID.

## Growth Curve data

The skills are Basketball Index composite scores in their original units. The three broader scores use the page's offensive, defensive and overall talent scales. `growth_model_reference.json` maps the 22 skill codes to the page's display names. All ages are in years, `minutes` are season minutes and `possessions` are source counts for the applicable composite. Roles are Basketball Index role labels.

| File | Rows | Fields and units |
|---|---:|---|
| `growth_history.csv.gz` | 139,812 | Player, game ID, season, age, minutes or possessions, role, metric, actual, actual copied into the forecast sample, one-year projection, actual minus projection, and lower/upper 50/80/90% bounds in the metric's units. |
| `growth_forward.csv.gz` | 173,290 | Player, game ID, reference season, age and minutes, target season and age, forecast horizon (1–5 years), metric, forecast, and lower/upper 50/80/90% bounds. Target seasons are calculated from the latest observed season for that player. |
| `growth_history_extra.json` | 5,848 | Player, game ID, season and six additional numeric slots in the offensive history arrays. The saved code does not assign metric names to slots 7 and 13–17 (zero-based, after age/season/minutes). |
| `growth_player_roles.json` | 6,310 | Player, game ID, season and historical offensive role. Defensive roles are in the historical skill rows. |
| `growth_development.json` | 1,505 | Player, game ID, count of evaluated seasons, minutes, source low-minutes flags, overall/offense/defense skill deltas, a delta for each skill and the broader talent deltas where present. Overall talent delta is the sum of offensive and defensive talent deltas when both exist. |
| `growth_coach_development.json` | 56 | Coach, counts of team seasons and player seasons, minutes, mean skill deltas by side and overall, per-skill deltas, and broader talent deltas. |
| `growth_coach_teams.json` | 231 | Coach, season, team, minutes, player count, and the source's minute-weighted actual, forecast and delta by skill. |
| `growth_coach_players.json` | 2,099 | Coach, season, team, player, game ID, age, minutes, and actual, forecast and actual-minus-forecast by skill. The browser coach detail table computes the reverse subtraction for its displayed delta. |
| `growth_projection_grid.json` | 2,580 | Player, game ID, target season and horizon, reference age and minutes, offensive role, advanced position, rotation role, low-minutes flag and 22 skill forecasts. The grid covers 516 players per year from 2026–27 through 2030–31. |
| `growth_composite_baselines.json` | 1,548 | Player, game ID, composite metric, baseline, role and possessions. The forward CSV carries the accompanying forecasts, including the dedicated overall talent series. |
| `growth_team_view_roster.json` | 571 | Player, game ID, default team and source minutes weight. The team view combines these inputs with the projection grid, and coverage differs between team and minutes lookups. |
| `growth_model_reference.json` | 1 object | Metric labels, 22 sorted empirical score distributions (3,957 values each), interval half-widths, root mean squared error and coverage by horizon. Also includes error breakdowns for six age bands, twelve offensive roles and six defensive roles, role and overall percentile lookup values, composite coefficients, the minutes threshold and the team list. Coverage is a fraction. |
| `growth_methodology.txt` | 1 text | Complete methodology tab wording, with HTML entities decoded and paragraph line breaks retained. |

The historical file joins on player and target season. The capture labels the retrospective forecasts as one-year forecasts. For 132 player-season forecast records in each skill family, the prior calendar season has no separate history row. The source forecasts remain present for those records. `forecast_sample_actual` preserves the second copy of the outcome as supplied by the forecast arrays. Some offensive values differ from the history arrays, so the output keeps both. The composite histories supply possessions in place of minutes.

The intervals use forecast ± source half-width. Defense skills use the minutes-adjusted interval from the page's newer defensive player table. Historical bounds use the minutes at the previous age when available. Forward bounds use the reference season minutes. The older defensive view's unadjusted widths are in the model reference. The CSVs retain more precision than the displayed tables.

## Injury Tracker data

The time-out estimates reproduce the page's default six-year half-life for weighting older cases. Days count basketball time and exclude offseason time. Unlogged returns are treated as censored, so their observed durations are lower bounds. A missing percentile means the estimated return curve never reached that percentile.

| File | Rows | Fields and units |
|---|---:|---|
| `injury_time_out.json` | 249 | 209 diagnoses, 30 body parts and 10 regions. Level, bucket, absence category, surgery share, observation IDs, case/return/censor counts, return share, weighted effective sample size, and 25th/50th/75th/90th return-day percentiles. |
| `injury_observations.json` | 21,216 | Capture-local zero-based observation index, days out, return-logged flag, years since the observation and start year. These rows carry no player identifier. |
| `injury_examples.json` | 1,953 | Level and bucket, player and game ID, start month, days out, reported diagnosis and optional source qualifier. A case can appear in more than one bucket. |
| `injury_long_term.json` | 191 | Level/bucket and optional region or tier, treated count, missed-whole-season and return rates, peer survival, matching diagnostics, one- and two-year impact changes and interval bounds, and next-year possession change. Impact uses the source's adjusted plus-minus scale. Possession change is a percent. |
| `injury_short_term.json` | 6 | Absence-length bracket and counts, median games missed, minutes before/after, percent change in minutes and bounds, true shooting before/after change and bounds (fractions), and `curve` triples of game offset, percent of prior minutes and sample count. |
| `injury_recurrence.json` | 27 | Level, bucket, body part, season horizon, index cases, rates of playing and reinjury, matched comparison risks, excess in percentage points, and risk ratios. |
| `injury_risk_validation.json` | 16 | Body part, sample count, base and top-decile rates, discrimination statistic (`auc`), lift ratio and source trust flag. |
| `injury_players.json` | 589 | Player and both IDs, position, height in inches, team codes by season, experience in years, injury totals and recovery rating. Recovery has a 1–5 score, label, number of spells, trust flag and raw/shrunk percent difference in time out versus the same diagnoses. |
| `injury_player_history.json` | 6,945 | Player and both IDs, dates, season, team, diagnosis, category, body part, region, side, days, approximate games, status, surgery and censor flags, source specificity code (`spec`), flags and note. Includes 5,629 injury spells and 1,316 other logged absences. |
| `injury_player_seasons.json` | 3,144 | Player and both IDs, season, games played/missed (`gp`/`gm`), possessions, adjusted plus-minus (`rapm`), spell count, days out and body parts. |
| `injury_player_risk.json` | 9,312 | Player and both IDs, body part, predicted next-season probability and comparable-player probability (`risk`/`peer`), lift ratio, and career/recent case counts. |
| `injury_player_projections.json` | 589 | Player and both IDs, profile-page version of availability and injury-only forecasts, role and workload, age, source/model/season fields, recent and career missed time, 10th/90th percentile limits, durability and confidence. |
| `injury_durability_projections.json` | 589 | Durability-table version, with `team25`, `team27`, and recovery band, score, percent, spell count and trust fields. Both versions retain the embedded values. Games and game limits are counts on an 82-game schedule, `p_available*` and share/rate fields are fractions, `*_pct` fields are percentages, `hist_inj_rate82` and `missed_to_injury` are injury games per 82, and durability/recovery scores are 1–5. Unconditional games projections include the chance of no roster spot. The `if_plays` pair and its limits condition on playing in the league. |
| `injury_teams.json` | 30 | Team, roster and coverage counts, core age and possessions, roster/core injury games per 82, total projected core games lost, fragile/chronic counts and unprojected count. Includes the most fragile regular and nine core players per team with names, game IDs, injury games per 82, scores and possessions where supplied. |
| `injury_model_reference.json` | 1 object | Date, source totals, eras and day milestones, aging/experience/severity/workload tables, recovery validation and band cuts, short-term placebo results and game window, durability validation and calibration including five injury bands and four role summaries, team aggregate settings and roster coverage metadata. Rate fields keep the page's original scale. |

## 2026–27 Minutes and Talent data

| File | Rows | Fields and units |
|---|---:|---|
| `minutes_players.json` | 559 | Player, game ID, team, rotation role, draft pick, projected injury games missed, health-only games available, games played and 10th/90th percentile games. Includes projected, healthy, previous-season and unconstrained minutes per game, the coach adjustment in minutes per game and seasons under that coach. Season-minute fields include the projection and its 10th/90th limits, own role, minutes lost to own absences and signed changes from teammates' injuries and garbage time or games skipped. Also includes the durability label. |
| `minutes_teams.json` | 30 | Team, injury games missed, teammate-injury, garbage-time and bench minutes, and top-eight share of minutes (0–100). The fields `fs` and `m` retain their source names and values. The rendered table does not define their meaning or units. |
| `talent_grid_players.json` | 328 | Player, game ID, team, age, position group and draft pick. Overall/offense/defense talent, 0–100 role percentiles, projected roles and percentage-mix strings, 2025–26 roles and talent in those roles, and talent source. Team slot, league ranks (`profile_pool_league_rank`, `full_pool_league_rank`), slot profile, rank within profile, tier (1 low, 2 mid, 3 high) and slot delta (profile minus team slot) are ranks, tiers or differences in ranks. Includes season minutes, average and healthy minutes per game, and rotation role. The extra numeric source field `dep` is retained under its embedded name. |
| `talent_grid_teams.json` | 30 | Team code/name, sum of player slot deltas overall and across slots 1–5 and 6–11, top-eight talent sum, weighted talent and counts of higher/lower talent slots and players. The extra aggregate `tal12` keeps its source key and talent units. |
| `talent_grid_reference.json` | 1 object | `edges` contains the 11 talent thresholds, in the overall talent scale. `ns` is the slot count and `n` the number of players. |

These role mixes and talent scores are the Minutes/Talent tool's chosen-role projections. A player line can reflect the draft-slot or veteran fallback described in the source page. The minutes capture uses its September 18, 2026 roster snapshot, and the injury panel contains a later roster snapshot. Source teams are preserved for each.

## Role Lab captures

`role_lab_capture_status.json` has two rows with capture filename, embedded player-row count and the missing part basenames. Each page renders the player, role-change, team and coach tables after joining four separate files. The offensive page needs `orl-v1-data-0.txt` through `orl-v1-data-3.txt`. The defensive page needs `drl-v8-data-0.txt` through `drl-v8-data-3.txt`. The local captures did not include those files or rendered player tables.

`defensive_role_height_coefficients.json` has seven rows with the role name, its inline height coefficient per standard deviation of height in the source talent model's units, and a unitless t-statistic. The body-envelope bounds displayed beside these coefficients come from the missing defensive model data.

## Verification and handoff

- Compared 128,656 historical offensive and defensive skill rows with the source's actual and retrospective arrays. Checked unique player/season/metric keys and verified the current projection grid cells against the forward skill export.
- Compared all 249 injury bucket counts and return-day percentiles with the saved page's local JavaScript formula. Compared the 6,945 detailed absence records and both aftermath/recurrence tables with the source payload.
- Checked methodology text against the source tab, all JSON for valid finite values, and every file against the 5 MB size cap. Ran the extractor in two directories and compared the outputs byte for byte.
- BBX is ready for coordinator review. Only the parser, report, board row and research exports changed. No commit was made.
