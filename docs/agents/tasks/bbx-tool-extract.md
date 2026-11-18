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

## BBX-2

All five captures are now in reusable research tables. They cover 6,942 player-seasons, 4,344 playoff player-windows, 61,037 historical lineups, and 12,481 lineups with exact possession counts and expected points.

The later Role Lab capture supplies 11,402 player-season entries and the model settings behind the saved pages.
The tables keep every source row, including players without a verified game ID. The largest file is 4.55 MB.

### Reproduce the tables

From the repository root, run `.venv/bin/python scripts/bbi_extract_captures.py`. It reads the five gzip captures listed in `data/research/bbi/tools/bbx2_inventory.json` and uses the existing canonical player index and two saved NBA roster snapshots. It writes alongside the original BBX extracts. Use `--output` to build in a fresh directory. Use `--captures`, `--canonical` or `--rosters` to override the inputs. The inventory records the capture paths, retrieval times, file sizes, row counts and player match rates.

CSV blanks represent missing values. JSON uses `null` for missing values and preserves absent optional source fields. Files whose uncompressed representation is at least 5 MB are gzipped with a fixed timestamp. The Lineup Explorer uses two files with identical headers so each compressed file stays under 5 MB.

### Player matches

`nba_player_id` is the NBA ID. `player_id` is the simulator's ID. The link uses the July 28 and October 13, 2026 NBA.com roster snapshots. A player must have the same normalized name and birthdate in the official roster and canonical index. Name normalization folds accents, case, spaces and punctuation and uses the three existing reviewed aliases. The resulting link must be unique in both directions. No team or similarity fallback is used.

Role Lab rows first recover the NBA ID from a unique normalized name and season in Progression and Lineup Explorer. Three defensive entries, for Nigel Hayes and Ruben Nembhard Jr., lack a verified NBA ID under that rule. Both IDs remain blank for those entries. The historical data span many players outside the current universe, and the roster bridge can also miss players in the current universe when official identity details are absent or disagree.

| Dataset | Distinct NBA IDs matched to the game | Player references matched to the game |
|---|---:|---:|
| Progression | 534 / 1,706 (31.3%) | 2,758 / 6,942 (39.7%) |
| Playoff Talent | 378 / 961 (39.3%) | 1,809 / 4,344 (41.6%) |
| Lineup Explorer | 515 / 1,606 (32.1%) | 150,858 / 305,185 (49.4%) |
| xPoints Lineups | 509 / 576 (88.4%) | 59,881 / 62,405 (96.0%) |
| Offensive Role Lab | 502 / 1,347 (37.3%) | 2,568 / 5,589 (45.9%) |
| Defensive Role Lab | 520 / 1,481 (35.1%) | 2,637 / 5,813 (45.4%) |

A reference is one player-season, one player-window or one lineup slot. The distinct-ID denominator includes resolved NBA IDs even when they lack a game ID. The reference denominator includes all entries, including the three Role Lab rows without resolved NBA IDs.

### Progression, playoffs and lineups

| File | Rows | Fields and units |
|---|---:|---|
| `progression_player_seasons.csv.gz` | 6,942 | One row per NBA ID and season, 2013–14 through 2025–26. Includes team, age in years, season minutes, position, advanced position, offensive/defensive/rotation roles and all 164 reported values in their source units. Includes impact measures such as EPM, RAPM, DRIP, DPM, RAPTOR and BPM, plus talent and usage measures. |
| `progression_percentiles.csv.gz`, `progression_ranks.csv` | 6,942 each | Source percentiles on a 0–100 scale and integer ranks. Join on NBA ID and season. Missing values stay blank. |
| `progression_players.json`, `progression_metrics.json` | 1,706 players, 164 metric definitions | Player names, IDs, headshot URLs, seasons, active filters and peer population sizes. The metric file defines each column's display name and category. |
| `progression_league_distributions.json` | 8 season blocks | Source arrays keyed by season and measure code, in source order and units. Contains 2013–14 through 2019–20 and 2021–22. Empty arrays and seasons absent from the capture are preserved as supplied. |
| `playoff_talent_windows.csv.gz`, `playoff_talent_reference.json` | 4,344 windows plus reference | One row per NBA ID and three-season playoff window, from 2013–14 to 2015–16 through 2023–24 to 2025–26. The 386 source fields include 381 numeric columns and five identity, window and role fields. The reference preserves display labels, percentage/integer flags, tabs and scatterplot groups. Values remain in the source scale. CSV renames `Season` to `window`, `player_name` to `player`, and source `player_id` to `nba_player_id`. |
| `lineup_explorer_2013_2019.csv.gz`, `lineup_explorer_2019_2026.csv.gz` | 27,483 and 33,554 | One row per season, team and set of five players, split at 2019–20. Slots 1–5 preserve the input order and carry the source name and both IDs. Includes minutes, offensive/defensive/net ratings per 100 possessions, source league-relative ratings, 55 `role_*` lineup counts and 24 `grade_*` talent columns in their original scale. Counts overlap across role, position, rotation and handedness categories. |
| `lineup_explorer_reference.json` | 13 season blocks | Source league-average offensive and defensive ratings. |
| `xpoints_lineups.csv`, `xpoints_lineups_reference.json` | 12,481 lineups, 30 teams | The 2025–26 request uses a zero-minute minimum and includes garbage time. Player slots preserve the capture order. `possessions` and `def_possessions` are exact offensive and defensive counts, and `possessions_total` is their sum. `pts_for`/`pts_against` and `xpts_for`/`xpts_against` are actual and expected point totals. Ratings are per 100 possessions, percentages use 0–100, and minutes can be fractional. The reference gives row counts by team and request group. Every row is from `select`. The `opponent` groups were empty. |

### Role Labs field guide

The player-season files are `role_lab_offensive_player_seasons.json.gz` (5,589 rows, 2014–15 through 2025–26) and `role_lab_defensive_player_seasons.json.gz` (5,813 rows, 2015–16 through 2025–26). The matching `role_lab_*_reference.json` files retain the source coefficient values and the keys needed to interpret the arrays. Definitions come from the saved pages `captures/tools/bbi_tool_offensive_role_lab.html` and `captures/tools/bbi_tool_defensive_role_lab.html`.

| Fields | Meaning |
|---|---|
| `n`, `s`, `t`, `tm`, `m`, `a`, `h`, `w`, `r`, `lo` | Source name, season, team label, teams in that season, minutes, age in years, height in inches, weight in pounds, observed role and flag for the source's low-minutes band below 500. `player` repeats `n` for joins. |
| `p`, `pc`/`rk`, `pf`/`rf`, `vo` | One value per reference `roles` entry. Projected talent in each role, percentile/rank against players who held the role, percentile/rank against its eligible rotation pool, and projected talent minus the 25th-percentile incumbent. Percentiles use 0–100. |
| `sh` | Optional history-blended version of the supplied scores and inputs. On offense it is embedded in each row. The defensive page reads it by row index from a parallel array, which is attached to each exported row. `sh.w` is the history blend weight. |
| `t27`, `mv`, `qtm`, `qag` | Source 2026–27 team and moved flag, plus projection team and age where supplied. Projection fields sit on the 2025–26 input row. |
| Offense `ol`, `lb`, `dl`, `u`, `dr` | Observed Offensive Talent, overall and defensive LEBRON, usage percent and defensive role. |
| Offense `ev`, `op`, `bf`, `cp`, `sw`, `pp` | Per-role envelope, opportunity, body-fit and ceiling adjustments in talent units, size warning index into `swlab`, and role precedent probability as a fraction. |
| Offense `im`, `tv`, `t3` | Play-type impact inputs and play-type talent inputs in `plays` order. `t3` orders the source shooting talent inputs as three-point, midrange and finishing. |
| Offense `qol`, `qd`, `q*` | The projected 2026–27 base and growth-model change. The role arrays `q/qc/qf/qv/qr/qrf` mirror `p/pc/pf/vo/rk/rf`. The remaining `qev/qop/qbf/qcp/qsw` store projected adjustments and size warning. |
| Defense `dt`, `np_`, `gp`, `im` | Observed Defensive Talent, body-implied position and average position guarded on a guard-to-center scale, plus the per-role exposure-weighted talent score. `gp` refers to guarded position. |
| Defense `dc`, `pe`, `ob`, `obd`, `fl`, `ex`, `md`, `sw`, `pr` | Per-role skill-transfer, size, on-ball and foul-risk terms plus the size and precedent fields. The page moves `obd` from `dc` to `ob` for display. `ex` is the maximum envelope breach and `md` lists the four possible breaches in order (too short, too light, too heavy, too tall), in position units. `sw` is a size warning index and `pr` a precedent probability. |
| Defense `skz`, `fz`, `obz`, `cf` | The 12 standardized inputs ordered by `skills`, the standard-deviation scores for fouling and on-ball skill, and the deployment matrix. The deployment matrix uses `roles` for rows and `keys` for columns. The observed-role row is the baseline shown by the page. The other rows are projected deployment in each role. |
| Defense `qol`, `qdc`, `qob`, `qfl`, `qz` | Projected defensive talent base, skill-transfer, on-ball and foul-risk adjustments, and standardized projected skill ratings. The page uses these with the existing size term to build the projected ladder. The capture also contains `qth`, `qsh`, `qsf` and `cfl` under their original names. The page's player view does not define them. |

The reference files retain the following model components:

- **Offense.** `theta` gives role effects. The player view subtracts the current role effect from the proposed one, then adds the four stored adjustments to the talent base. `base` and `coef` describe the talent breakdown, with one coefficient per entry in `plays`. `pcoef[play]` aligns with `pterms` and predicts play possessions per 75 using role indicators, shooting inputs and their interactions. `amean` gives role-specific typical values for the play contributions. `ceil` carries 95th-percentile and maximum talent, `env` carries height/weight bounds, and `body` carries penalty parameters. `prop` carries the precedent model's centers, scales, classes, intercepts and weights. `pools`, `nfit`, `span` and `target` describe comparison pools and borrowing across seasons.
- **Defense.** `theta` gives role effects. `W`, `LO` and `HI` carry skill weights and transfer bounds in `skills` order for each role. `wW`, `wbase`, `wmu` and `wrsd` support the grade breakdown and its league or role-centered views. `xW`, `xLO`, `xHI`, `xRAT` and `lamo` are the more precise transfer and opportunity parameters used by that breakdown. `exp[role]` holds the volume, stakes and combined exposure multipliers. `env` holds median, 10th and 90th percentiles of body-implied position. `body` carries the height/weight envelopes, penalties and natural-position equation, and `prop` carries the precedent model's standardization and fit. `fe` supplies tracked-stat role shifts, `lg` supplies league means and standard deviations, and `surv` and `pairs` describe retained skill opportunities when roles change. The seven inline height coefficients remain in the original BBX file `defensive_role_height_coefficients.json`.
- **Both.** The reference files preserve the source's team, coach, role-pool, fit and lineup-optimization data as supplied, including ancillary names. Matched IDs belong to the separate player-season tables. These role-change projections are observational estimates. The saved pages mark moves with limited precedent and distinguish model assumptions from measured history.

### Verification and handoff

Compared the exported values with all five raw captures, including the lineup member order, both sides of the xPoints possession totals, the Role Lab vectors and the defensive history-blend alignment. Checked unique row keys and consistent one-to-one player joins. A second extraction reproduced all 18 files byte for byte. BBX-2 is ready for coordinator review. No commit was made.
