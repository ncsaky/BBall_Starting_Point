# Gordon and Randle Calibration

## Scope

New-game version: `2026-10-23-forward-tuning-v5`. Only these two players' 15 underlying traits change, through the established post-alignment override path. The display transform, overall weights, simulation formulas, development and draft generation are unchanged. All earlier corrections remain exact. Health and availability are separate from healthy skill, with their original records preserved.

These are researched model judgments, not measured skill integers or proof of a universal player ranking. Gordon's stronger complementary two-way profile should have greater healthy on-court value; Randle remains the superior self-creator and direct passer. Team context, availability and contracts can produce a different asset or roster preference. No current-season team changes or results after the July 2026 game start are imported.

## Evidence

[ESPN regular-season statistics for Gordon](https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3064290/stats?seasontype=2), checked October 23, 2026: 2024-25, 14.7 points and 3.2 assists, 43.6% from three on 3.4 attempts; 2025-26, 16.2 points and 2.7 assists, 38.9% on 4.4 attempts. His limited availability (51 and 36 games) remains a real disadvantage. These are complementary shooting samples, not evidence of elite pull-up creation or directly measured release speed.

[ESPN postseason statistics for Gordon](https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3064290/stats?seasontype=3): 2025, 16.2 points, 7.6 rebounds (3.6 offensive), 37.3 minutes across 14 games. The three-game 2026 sample is too small to define permanent skill. [Denver's film breakdown](https://www.nba.com/nuggets/news/the-leap-aaron-gordon-advancement-post-up-player) supports seals, screening and interior matchup scoring. [NBA Finals reporting](https://www.nba.com/news/aaron-gordon-game-4-breakout) supports difficult defensive assignments. [2025 playoff coverage](https://www.nba.com/news/nuggets-westbrook-gordon-x-factors-playoffs) supports rebounding, hustle and complementary postseason value.

[ESPN regular-season statistics for Randle](https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3064514/stats?seasontype=2): 2024-25, 18.7 points, 7.1 rebounds and 4.7 assists, 34.4% from three; 2025-26, 21.1 points, 6.7 rebounds and 5.0 assists, 31.5% from three. His 79 appearances at 33.0 minutes in 2025-26 argue against penalizing conditioning or pretending Gordon has the same availability.

[ESPN postseason statistics for Randle](https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3064514/stats?seasontype=3): 2025, 21.7 points and 4.9 assists with 50.2% field-goal shooting; 2026, 16.0 points and 2.8 assists at 39.0%. [NBA's May 2025 analysis](https://www.nba.com/news/starting-5-may-19-2025) credits his playmaking and defensive contributions. [Mike Conley's explanation of the 2026 Spurs series](https://roundtable.io/sports/nba/timberwolves/news/mike-conley-explains-how-the-spurs-shutdown-julius-randle) identifies how Wembanyama's doubling length complicated Randle's passing reads. The accompanying reporting describes inconsistent defensive engagement. This supports matchup-sensitive execution, not deleting his good 2025 run or his genuine passing strengths.

## Changes and Tradeoffs

- Gordon: stronger finishing/cutting pressure, defensive engagement and recognition, complementary spacing and playoff fit. Reduce exaggerated handling, direct passing, offensive rebounding and center-like rim protection. Healthy conditioning is distinct from injury risk.
- Randle: reduce overgenerous release/range, pressure handling, lateral/screen defense, rim protection and complementary fit. Preserve strong passing, improve usable shot repertoire, paint pressure, conditioning and physical rebounding. Playoff translation reflects both successful and unsuccessful series.
- `scheme_iq` contributes to simulated passing as well as defense. Check actual passing features, not only the visible passing trait: Randle still leads Gordon in both.
- Canonical projected-minute overall: Gordon 82.4 -> 85.3; Randle 85.0 -> 80.9. The gap also persists at equal 24-minute workloads. Exact decimals are model outputs, not external expert grades.
- Generated prospects, existing career growth and league-wide rating distributions are outside this correction. No long-term league-balance claim is made from three seeded game checks.

## Verification

Run `PYTHONPATH=src:tests:scripts python -B -m unittest test_forward_tuning test_player_tuning test_talent_balance test_lineup_performance -v`. Run `PYTHONPATH=src:scripts python -B scripts/verify_forward_tuning.py` for the deterministic data/preservation report; add `--publish` only after tests pass. Tests use temporary careers. Existing saves and old compressed baselines are fingerprinted before and after publication. This is a new-game baseline, not a migration of playable careers.
