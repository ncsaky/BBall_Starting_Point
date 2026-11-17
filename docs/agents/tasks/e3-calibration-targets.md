# E3: Real-NBA calibration targets

What was built
- `data/calibration/nba_2025_26_targets.json` (made by `scripts/build_calibration_targets.py`, deterministic).
- `src/nba_gm_data/calibration_targets.py`: `load_targets`, `compare`, `aggregate_from_results`, `format_report`.
- `scripts/calibration_report.py`: runs N regular-season games on the live engine (sandbox-sim) and prints the comparison. About 14 seconds for 1,230 games.
- Tests: `PYTHONPATH=src .venv/bin/python -m unittest tests.test_calibration_targets`.

League targets (2025-26 regular season, from team box stats in `game_boxscores_2025_26.json`)
- Pace, offensive rating, points per game, FGA/3PA/FTA per 100, 3PA rate, FT rate, eFG%, TS%, turnovers (per 100 and %), ORB%, assists (per 100 and per FGM), steals, blocks, fouls per 100.
- Possessions = FGA + 0.44*FTA - ORB + TOV. Mean is the league total; spread is the std of the season value across the 30 teams. Acceptance band = target +/- 1.5 std.
- The box-score cache has zero FGM/FGA in its player rows (known parser bug), so only team-level stats are used. Team stats check out (points reconcile from FG/3P/FT).
- Nothing was left null. Caveat: team spread is season-long; a short sim run is noisier than that, so use many games (500+) before trusting a band miss.

Player targets
- Source: ESPN 2025-26 season totals in `player_career_stats.json`. Eligible = 500+ minutes, or 20+ games at 15+ mpg. Per-game and per-36 for points, FGA, 3PA, FTA, rebounds, assists, turnovers, steals, blocks, plus TS%.
- Usage, ORB% and DRB% are copied from Crafted's `player_stats.json` (not recomputed, and not used by `compare`).
- Keyed by universe player id via ESPN id (name fallback). Match rate and any unmatched names are in the file under `player_match`.
- `compare` looks at the top 150 players by real minutes. Misses are scored as z against the spread of that stat across real rotation players.

Limits
- Rebounds are not split into offensive and defensive per player (ESPN totals only).
- Real players are keyed to the 2026-27 universe, so a sim player's team may differ from the 2025-26 team; per-36 rates are team-independent so this is fine.
