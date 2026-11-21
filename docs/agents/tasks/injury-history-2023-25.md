# 2023–25 injury history

## TL;DR

- Rebuilt 2023–24 and 2024–25 from all 2,640 completed games and official NBA injury reports for all 422 game dates.
- Found 350 and 447 injury or illness stretches without a Basketball Index match, including 347 and 441 with a regular-season miss.
- After setting aside injury-management-only stretches and absences already underway at team openers, the public records show 48.4 and 55.7 injury or illness stretches per 1,000 regular-season player appearances. The same 2025–26 measure is 50.3.

## Coverage

| | 2023–24 | 2024–25 | 2025–26 |
|---|---:|---:|---:|
| Completed games | 1,319 | 1,321 | 1,322 |
| Regular season / Cup final / play-in / playoffs | 1,230 / 1 / 6 / 82 | 1,230 / 1 / 6 / 84 | 1,230 / 1 / 6 / 85 |
| Game dates with player rows in a same-day report | 208 / 208 | 214 / 214 | 210 / 212 |
| Team games with player rows in the report | 2,583 / 2,638 | 2,601 / 2,642 | 2,599 / 2,644 |
| Players with roster evidence | 597 | 587 | 561 |
| Players who appeared in the regular season | 572 | 569 | 547 |
| Regular-season player appearances | 26,401 | 26,306 | 26,269 |
| All missed-game stretches / games missed | 5,866 / 17,694 | 5,873 / 17,795 | 5,512 / 16,846 |
| Missed games with an unknown reason | 1,291 | 668 | 907 |
| Injury stretches / games missed for injury, all phases | 1,212 / 6,319 | 1,497 / 7,212 | 1,542 / 7,509 |
| Illness stretches / games missed for illness, all phases | 182 / 318 | 216 / 320 | 176 / 262 |

Every team has 82 regular-season games in each file. The older seasons use ESPN's team schedules, scoreboards, game summaries and transactions. The NBA's `_11PM.pdf` filename contains the 11:30 p.m. Eastern report in both older seasons. The existing parser reproduced the player-status row count from an independent PDF extraction on 40 reports per season. The NBA's regular-season stats independently list 572 and 569 players, the same totals as the two ESPN box-score builds. [2023–24 NBA stats](https://www.nba.com/stats/players/traditional?Season=2023-24&SeasonType=Regular+Season) · [2024–25 NBA stats](https://www.nba.com/stats/players/traditional?PerMode=Totals&Season=2024-25&SeasonType=Regular+Season&dir=-1) · [2023–24 NBA playoffs](https://www.nba.com/news/2024-nba-playoffs-schedule) · [2024–25 NBA playoffs](https://www.nba.com/news/2025-nba-playoffs-schedule)

The new files have the same stretch format and reason categories as 2025–26. They keep both the NBA report's wording and any box-score reason. An appearance ends a stretch. A change in team, reason category, injury site or side starts a new stretch. The older files include 209 and 114 players outside the game's current player pool. They use the game's player ID when available, then ESPN's player ID or a name from the NBA report. ESPN roster placeholders with no minutes and no scratch flag do not count as appearances. [2023–24 data](../../../data/research/injury_history_2023_24.json) · [2024–25 data](../../../data/research/injury_history_2024_25.json) · [2025–26 report](injury-history-2025-26.md)

## Basketball Index comparison

| Entry or stretch count | 2023–24 | 2024–25 | 2025–26 |
|---|---:|---:|---:|
| All tracker entries | 1,086 | 1,343 | 492 |
| Tracker entries linked to the build's player pool | 1,080 | 1,339 | 481 |
| Tracker injury or illness entries matched to a public stretch | 1,045 | 1,269 | 419 |
| Of those matches, tracker entries with a game missed | 846 | 996 | 256 |
| Distinct public stretches with a tracker match | 1,044 | 1,266 | 419 |
| Additional public injury / illness stretches, all phases | 294 / 56 | 398 / 49 | 1,159 / 140 |
| Of those additions, stretches with a regular-season miss | 347 | 441 | 1,269 |
| Of those regular-season additions, injury management only | 3 | 75 | 239 |
| Of those regular-season additions, at the opener after setting aside injury management | 15 | 25 | 56 |

The date and injury-site match is the same as in 2025–26. It uses player, team, reason category, site and side when known, and overlapping dates or starts a few days apart. Several tracker entries can match the same public stretch. The tracker reports zero games missed on some matched entries. The public file includes the game dates observed in the box scores and injury reports.

| Entries or stretches per 1,000 regular-season player appearances | 2023–24 | 2024–25 | 2025–26 |
|---|---:|---:|---:|
| All tracker entries, using the tracker's own appearances | 50.2 | 55.3 | 18.7 |
| Tracker injury or illness entries with a game missed, using its own appearances | 40.3 | 42.9 | 10.7 |
| Same game-costing tracker entries, using box-score appearances | 33.0 | 39.6 | 10.7 |
| Tracker entries linked to the build's pool, using box-score appearances | 40.9 | 50.9 | 18.3 |
| Linked tracker entries plus all public regular-season additions | 54.1 | 67.7 | 66.6 |
| Same, setting aside new injury-management-only stretches | 53.9 | 64.8 | 57.5 |
| Same, also setting aside new opener stretches | 53.4 | 63.9 | 55.4 |
| **Public injury or illness stretches costing a regular-season game** | **51.7** | **64.1** | **64.1** |
| Public, setting aside injury-management-only stretches | 50.1 | 57.6 | 52.8 |
| Public, setting aside opener stretches only | 50.0 | 62.2 | 61.6 |
| **Public, setting aside both** | **48.4** | **55.7** | **50.3** |
| Public injuries alone, including management and openers | 44.8 | 56.0 | 57.6 |
| **Public injuries alone, setting aside both** | **41.8** | **47.6** | **43.9** |

The combined tracker rows keep tracker entries with zero games missed so they can be compared with the previous write-up. The public rows use all game-costing stretches observed in the public files. The opener filter sets aside every stretch that starts at a team's first game. It covers prior-season carryovers as well as offseason and preseason injuries. The injury management filter uses the existing dataset flag, which looks for the word “management” in every listed diagnosis.

## Examples

- **2023–24.** Ja Morant's 25-game suspension and 47-game shoulder injury are separate. Vlatko Čančar's knee surgery stretch covers all 82 regular-season games and 12 playoff games, even though he never appeared in a box score that season. [Morant's shoulder report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2024-01-07_11PM.pdf) · [Denver opener report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2023-10-24_11PM.pdf)
- **2024–25.** Victor Wembanyama's last 30 games are one stretch for a blood clot in his right shoulder. Luka Dončić's left calf strain appears as 19 Dallas games and three Lakers games on either side of the trade. [Wembanyama's injury update](https://www.nba.com/news/victor-wembanyama-shoulder-out-for-season) · [Dallas report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2024-12-27_11PM.pdf) · [Lakers report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2025-02-04_11PM.pdf)
- **2025–26.** Tyrese Haliburton missed all 82 games recovering from his Achilles tear. A published report mislabeled the injury once. The file keeps the published wording and the correction with Indiana's source. [Indiana's medical update](https://www.nba.com/pacers/news/indiana-pacers-medical-update-tyrese-haliburton-250623)

## Gaps and handoff

- The NBA report supplies the reason for 6,626 of 6,637 injury or illness misses in 2023–24 and 7,524 of 7,532 in 2024–25. ESPN supplies the rest. A blank reason stays unknown. Two-way players and short contracts can still leave uncertain roster dates between sightings. Where dated releases established a contract gap, the build removes those games. [Portland's Taze Moore signings](https://www.nba.com/blazers/news/trail-blazers-sign-taze-moore-to-two-way-contract) · [Sacramento preseason roster moves](https://www.nba.com/kings/news/kings-announce-roster-moves-2) · [Atlanta's Kevon Harris release](https://www.nba.com/game/0022400884)
- Official reports sometimes give a broad reason without an identifiable body part. That occurs in 31 injury stretches in 2023–24 and 37 in 2024–25. Stretches can end at the last game while the player is still out. Team changes can split a single injury across two entries, as in Dončić's case.
- Both new files and the shared builder are ready for the coordinator. The three-season comparison uses only aggregate figures from the local Basketball Index data.

## Rebuild and verification

```sh
for season in 2023-24 2024-25 2025-26; do
  .venv/bin/python scripts/research/injury_history_2025_26.py --season "$season" --cache-only --compare-tracker --write
done
PYTHONPATH=src .venv/bin/python -m unittest tests.test_injuries_2
```

Omit `--cache-only` to populate a new cache. ESPN responses and NBA PDFs for the older seasons are under `output/injury-history-2023-25/`. The 2025–26 builder still uses `output/injuries-2/`. Successful responses are saved as they arrive and reused after interruption.

All 11 focused tests passed. Cache-only rebuilds reproduced all three files, including the original 2025–26 file byte for byte. The accounting check verified game dates, player appearances, unique missed days, game-by-game sources and stretch totals.

## Resume state

Ready for review on `codex/injury-history-2023-25`. The cache and tracker inputs are local to this setup.
