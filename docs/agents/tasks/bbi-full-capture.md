# BBI-ALL: capture everything the Basketball Index membership exposes

User request (2026-11-18): "find a way to get ALL data from Bball index". Subscription renews Dec 16 (user's call).
Rules: signed-in browser pane only (the user signs in); each tool's own data requests or export controls; personal use,
never shared; polite pacing (one tool at a time, small batches, back off on server errors). Terms (checked 2026-11-18,
last updated Feb 9 2026) contain no restriction on downloading or exporting.

Method that works on fanspo-hosted tools: read the page's own `/api/...` data request, fetch it in the page, gzip in the
page (CompressionStream) and save as a download; if the download lands as a hidden
`~/Downloads/.Q6L2SF6YDW.com.anthropic.claudefordesktop.*` temp file, copy it (size-check) — it is complete.
Raw captures go to `data/research/bbi/captures/` (git-ignored); tidy extracts go to `data/research/bbi/tools/`.

## Inventory (site menu, 2026-11-18) and status

| Tool | Host | Status |
|---|---|---|
| Leaderboards Tool (664 metrics, 2013-14..2025-26, Values) | shinyapps | done (2026-11-17). Percentile/grade/Value+ views skipped (derivable) |
| Team Leaderboards | shinyapps | TODO |
| NBA LEBRON Dashboard / LEBRON history 2010-2026 | fanspo | done |
| LEBRON Player Trends | fanspo role-explorer | TODO (check vs value trends) |
| LEBRON Trends Dashboard (value trends) | fanspo | done |
| Daily LEBRON (game LEBRON) | fanspo | done |
| Shooting talent projections | fanspo | done (2/3 of players) |
| Stable Lineup Data | shinyapps lineup-free / fanspo bbi-lineups explorer | done via Lineup Explorer (61,037 lineups) |
| Rotation Minutes | minutes-app | TODO |
| Custom Lineup Creator / 5th Man / Roster Optimizer | fanspo bbi-lineups | scenario tools: underlying data only (lineup explorer + progression) |
| Player Skills Tool | shinyapps | TODO (check overlap with Leaderboards) |
| Play Style Similarity | ? | TODO |
| Playoff Talent Grades | fanspo bbi-pbp-tool | done (4,344 player-windows x 386) |
| Defensive / Offensive Role Lab | static html + 4 data files each | done: `captures/tools/role_labs/bbi_role_labs.json.gz` (5,589 offensive, 5,813 defensive player entries + model coefficients) |
| Talent Age Growth Curve | static html | done (extracted by Codex BBX) |
| Minutes Projections & Talent Grid | static html | done (BBX) |
| Injuries Tool | static html | done (BBX) |
| xPoints Analyzer | fanspo bbi-pbp-tool | TODO |
| xPoints Game Database (1,230 games, play-by-play) | fanspo bbi-pbp-tool | TODO |
| xPoints WOWY Combos | fanspo bbi-pbp-tool | TODO (base tables only) |
| xPoints Standings | fanspo bbi-pbp-tool | TODO |
| xPoints Team Trends | fanspo bbi-pbp-tool | TODO |
| xPoints Lineups | fanspo bbi-pbp-tool | done: `captures/fanspo_tools/xpoints/bbi_xpoints_lineups_2025_26.json.gz` (30 teams, exact possessions, expected points) |
| xPoints Referee Trends | fanspo bbi-pbp-tool | TODO |
| Shot Charts | ? | TODO |
| Headshots & Scatter Plots | shinyapps | skip (re-plots captured metrics) |
| Career Trends | shinyapps | check for fields not in Leaderboards |
| Player Progression Analysis | fanspo bbi-lineups | done: `captures/fanspo_tools/progression/bbi_progression_all.json.gz` (1,706 players, 6,942 player-seasons, 164 measures incl. EPM/RAPM/DRIP/DPM/RAPTOR/BPM + league distributions) |
| Player Profiles | site | TODO (check for unique fields) |
| Skill Badges | site | TODO |
| Glossary | google sheet | TODO (definitions) |
| NCAA section | site | TODO: check membership coverage (prospect evidence) |
| WNBA section | site | low priority |

## Resume state
Next: xPoints lineups (tab-1, window.__xl) then xPoints games/standings/trends/referees/WOWY, Team Leaderboards, Skills/Similarity/Career Trends overlap check, Shot Charts, Player Profiles, Skill Badges, Glossary, NCAA coverage check, Rotation Minutes.
