# 2025–26 injury history

## TL;DR

- Rebuilt 5,512 missed-game stretches across all 1,322 completed games, with evidence for 561 of the game's 691 real players.
- Matched 419 Basketball Index entries and found 1,159 additional injury stretches and 140 additional illness stretches. The regular-season comparison rose from 18.3 to 66.6 entries per 1,000 games played.
- The comparison comes to 55.4 after setting aside newly found injury-management-only stretches and stretches already underway at team openers. That is close to the tracker's 50.2–55.3 in the previous two seasons.

## Coverage

The [data file](../../../data/research/injury_history_2025_26.json) covers 1,230 regular-season games, the NBA Cup final, six play-in games and 85 playoff games. The builder uses the repo box scores, checks final status and Eastern game dates against ESPN's schedule, drops four postponed listings and fills 18 missing or empty final-game boxes. One of those games uses the NBA box score because ESPN's summary returned 404. Every team has 82 regular-season games. [NBA postseason schedule](https://www.nba.com/news/2026-nba-playoffs-schedule) · [NBA box-score fallback](https://www.nba.com/game/nyk-vs-cle-0042500303/box-score)

The build found 547 real-pool players with a regular-season appearance and 543 with at least one missed game in any phase. The file lists the 130 players for whom the inputs show no 2025–26 NBA roster evidence. This includes players who entered the pool after the season.

| Reported reason | Stretches | Games missed |
|---|---:|---:|
| Injury | 1,542 | 7,509 |
| Illness | 176 | 262 |
| Coach's decision | 2,479 | 4,771 |
| G League | 645 | 2,901 |
| Rest | 87 | 97 |
| Personal | 51 | 75 |
| Suspension | 16 | 56 |
| Not with team | 52 | 211 |
| Trade pending | 29 | 33 |
| Reconditioning without a named injury | 11 | 24 |
| Unknown | 424 | 907 |
| **Total** | **5,512** | **16,846** |

Each stretch gives the historical team, first and last missed dates, actual games missed and the regular-season subtotal. Its game-by-game sources retain the injury report's status and wording, any box-score reason, and how roster membership was established. Playing in the box score ends a stretch. Consecutive misses with the same category and injury site and side form one stretch even when the report changes the diagnosis wording. A different team, category, site or side starts a new stretch. For a report with multiple conditions, the first listed injury site drives grouping and the source preserves the full reason.

A late snapshot was found for all 212 game dates. The NBA switched from hourly filenames on December 22. Two snapshots had no player rows dated for that day's game. Those were Cleveland–New York on May 21 and 23, for which the box scores supply participation. In all, 2,599 of 2,644 team-game slots had at least one player in the selected report. The reason came from the NBA report for 7,762 of the 7,771 injury or illness misses, and from the box score for the other nine. [May 21 report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-05-21_09_30PM.pdf) · [May 23 report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-05-23_09_30PM.pdf)

## Comparison with Basketball Index

The match uses the player, team, injury or illness category, reported site and side when known, and the date. It accepts an overlapping date range or close starts, with a three-day margin for the same known site and one day when a site is missing. Of 481 tracker entries for players in the game's pool, 476 were injury or illness. The public stretches matched 419 of those, including 256 of the 279 tracker records that reported missed games and 163 that had zero in the tracker. The 1,299 additions had no such match to the 2025–26 tracker rows. Of those additions, 1,269 include a regular-season miss, with 1,134 injury and 135 illness stretches.

| Count | Entries | Entries per 1,000 games played |
|---|---:|---:|
| 2023–24 tracker, full tracker pool | 1,086 | 50.2 |
| 2024–25 tracker, full tracker pool | 1,343 | 55.3 |
| 2025–26 tracker, full tracker pool | 492 | 18.7 |
| 2025–26 tracker, game pool | 481 | 18.3 |
| Game-pool tracker plus all regular-season additions | 1,750 | 66.6 |
| Same count, excluding 239 new injury-management-only stretches | 1,511 | 57.5 |
| Same count, also excluding 56 new stretches beginning at team openers | 1,455 | 55.4 |

The game-pool rows divide by 26,269 actual regular-season player appearances. The historical rows use the tracker's own exposure. The tracker already counts records that cost zero games. The public file only sees absences. Injury management can cost a game without representing a fresh injury, and an opener absence can carry over from the previous season. The last two rows show what those choices do to the count. They leave the underlying stretches in the data. Across all phases, the tracker plus public additions totals 1,780 entries.

## Examples

| Player | Tracker entries in 2025–26 | Public injury or illness stretches | Regular-season games out for injury or illness |
|---|---:|---:|---:|
| Stephen Curry | 1 | 7 | 39 |
| Nikola Jokić | 0 | 2 | 17 |
| Jayson Tatum | 1 | 5 | 66 |
| Tyrese Haliburton | 0 | 1 | 82 |

- Curry's seven include three games with illness in November, five with a left quadriceps contusion, and 27 with right kneecap pain in February through April. Jokić's record includes 16 straight games out with a left knee injury. [Curry's February report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-02-03_09_30PM.pdf) · [Jokić's January report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-01-15_09_30PM.pdf)
- Tatum's 62 games out before his March 6 debut are one Achilles recovery stretch. Haliburton missed all 82 games in one Achilles recovery. The March 23 report lists Haliburton's injury as a right ACL tear. The file retains that listing and cites Indiana's medical update for the correction. [Tatum's return](https://www.nba.com/celtics/news/gamerecap-keys-20260306-dalbos) · [Haliburton's medical update](https://www.nba.com/pacers/news/indiana-pacers-medical-update-tyrese-haliburton-250623) · [Indiana season review](https://www.nba.com/news/2026-27-season-preview-ind)

## Gaps

- A box-score scratch with no specific reason can end up as a coach's decision or unknown. The 907 unknown misses include 830 in inferred roster windows. Dated transactions and same-team sightings bound those windows, but there can still be unrecorded contract gaps, especially for two-way players. Postseason misses require a box-score or report sighting on the day.
- Some source labels are broad, and illnesses or secondary conditions can appear alongside an injury in one report. The published wording remains in the source. Six medical stretches have no mapped body part. Unknown absences carry no assumed medical reason. An injury at the last observed game also gives no return date.
- A continuous injury that crosses a trade can appear in two team stretches. A carry-in can also match a tracker event filed under an earlier season. The 1,299 additions count newly documented stretches, and those two cases need a second check before treating them as new injuries in the model.

## Builder handoff

1. Read the JSON in `scripts/build_injury_model.py` when constructing the per-player `recent` history. Use the canonical `player_id`. For the first pass, use injury stretches with a supported model body part and at least one regular-season missed game. The current recent-history builder excludes illness. The new file has illness available for a later illness-specific change.
2. Match existing history by player, site, side where available, and dates. Keep the existing onset when a same-condition stretch continues from the previous season or through a trade. For an unmatched injury with evidence of a new spell, the first missed date is a usable proxy for onset. If the existing history format needs tracker-style days, use twice the demonstrated regular-season games missed. Use the game count directly when measuring recovery and treat season-end or roster-end stretches as incomplete until a return is established.
3. Review injury-management-only episodes and opener carry-ins before counting them as new events. Leave rest, other nonmedical reasons and unknown absences out of recent injury history. This first integration can feed the startup history independently of the rate fit and recovery pools.
4. Rebuild the private per-player evidence from a checkout with its own output file when the coordinator takes over. The local tracker comparison here reads the tracker files and prints aggregate results. The committed public dataset is built independently of those files.

## Rebuild and verification

```sh
.venv/bin/python scripts/research/injury_history_2025_26.py --write
.venv/bin/python scripts/research/injury_history_2025_26.py --cache-only --compare-tracker
PYTHONPATH=src .venv/bin/python -m unittest tests.test_injuries_2
```

The builder uses the shared `output/injuries-2/nba_pdf` and `espn` caches. The existing PDF parser now preserves compressed pages ending with a carriage-return byte and keeps the first player aligned with the date and team on page breaks. All 11 focused tests passed. The cached rebuild reproduces the committed data. The accounting check verifies unique player dates, box-score participation, stretch totals, source URLs, and the opening Achilles stretches for Tatum and Haliburton.

## Resume state

The data, builder and parser update are ready for coordinator review on `codex/injury-history-2025-26`. The commit contains research data from public sources. The gameplay model and private per-player evidence remain as they were.
