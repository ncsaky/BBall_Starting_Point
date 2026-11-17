# Schedule Integrity Follow-Up

2026-10-04, private macOS beta.7.

## Root Cause

The raw 2025-26 ESPN schedule contains 1,235 entries marked regular. The old sandbox generator copied all of them: ten teams received 83 games, while twenty received 82. Five entries account for the excess, rather than five legitimate regular-season games selected for deletion.

| Excluded template ID | Entry | Kept makeup ID |
| --- | --- | --- |
| 401809839 | Dec. 16 SAS-NYK Cup championship | None |
| 401810384 | Jan. 8 MIA-CHI postponed original | 401850920 |
| 401810499 | Jan. 24 GSW-MIN postponed original | 401857824 |
| 401810507 | Jan. 25 DAL-MIL postponed original | 401858694 |
| 401810506 | Jan. 25 DEN-MEM postponed original | 401858693 |

The Cup final is outside regular-season statistics. [NBA Cup rules](https://www.nba.com/news/nba-cup-101)

Miami-Chicago moved from January 8 to January 29. [NBA announcement](https://pr.nba.com/heat-bulls-schedule-adjustments/)

Golden State-Minnesota moved to January 25. [Timberwolves announcement](https://www.nba.com/timberwolves/news/wolves-vs-warriors-postponed-to-jan-25-at-430-p-m-cst)

Dallas-Milwaukee moved to March 31; Denver-Memphis to March 18. [NBA schedule adjustments](https://www.nba.com/news/nba-schedule-adjustments-weather-2026)

Dates and teams identify the corresponding local ESPN entries. All four makeup entries already exist in the raw file. Cup quarterfinals and semifinals remain in the regular template; the correction does not implement a new Cup competition.

## Implementation

`data/overrides/schedule_template_corrections.json` records exact IDs, expected dates/teams, makeup IDs and source URLs. `save.py:regular_schedule_template` validates these identities and replacements before excluding the superseded entries. The raw research file is unchanged, including its original metadata and checksum, so replay/research inputs remain intact.

The generator validates both its corrected input and randomized output: 1,230 games, 82 for each of the fixed 30 ESPN team IDs, unique game IDs, no self-matchups, valid dates and no same-day double booking. A missing/mismatched correction or invalid schedule fails explicitly rather than silently trimming games. The correction file is a bundled runtime input; gameplay does not fetch these source websites.

Existing per-season schedules are not regenerated or modified on read. Existing scores, standings and history retain their original meaning. **An existing 83-game season stays that way until its next rollover; new franchises and newly generated future seasons get the corrected schedule.** The rollover regression verifies an old 1,235-game schedule and its played result survive unchanged while the next season has 1,230 games.

New schedule matchups remain deterministic, using the existing within-date away-team shuffling. Removing obsolete slots changes some new-season matchups and therefore can change new-season results. This is not a promise of identical seasons across beta.6 and beta.7. Conference/division matchup frequencies, travel realism, neutral-site metadata, an actual 2026-27 real-world schedule and a dynamically simulated Cup are outside this repair.

## Additional Defect Found

An independent archived-career audit found one overtime player line with 53.01 minutes. Regulation-minute rounding produced a 239.99-minute team rotation; rounding the proportional overtime shares assigned a capped player 5.01 extra minutes. `sim.py:add_overtime_minutes` now redistributes excess hundredths to participants with room. Team overtime minutes and random draws stay unchanged. The captured rotation is a regression fixture, and a 3,690-game comparison confirms identical scores and winners before/after this small follow-up.

## Verification

- Eleven deterministic generated seasons, 2026-27 through 2036-37, have 82 games for every team and pass date/identity/booking checks.
- Three fixed-roster seasons (seeds 7, 19, 31): 3,690 games, zero accounting errors, unchanged scores after the overtime rounding repair. Evidence: `output/schedule-2026-10-04/accounting-final.json`.
- 28 focused schedule/accounting/soak/lineup/history/rollover Python tests passed, plus 27 fresh-save/persistence/static-media Python tests and 102 JavaScript tests. The eight schedule tests cover exact removals, retained makeup/Cup games, deterministic generation, malformed schedules, missing replacements, identity drift, unchanged existing schedules, old-season rollover and the existing resource-root fallback. No full-repository green test claim is made.
- The first career and its independent archive report are retained under `output/schedule-2026-10-04/career/` and `career-accounting.json`. Their single overtime rounding violation is diagnostic evidence, not final accounting acceptance.
- The final Miami career completed a full season and offseason through rollover with zero hard invariant failures. Every team finished with 82 regular-season games; the next season also has 1,230 games and 82 per team. All 1,312 archived games pass independent accounting checks across self-contained phase snapshots. Evidence: `output/schedule-2026-10-04/final-career/soak_audit.md` and `career-accounting-final.json`. Extension-volume calibration and injury-burden interpretation remain unresolved; this is not a claim of calibrated NBA realism.
- Both final extracted beta.7 architecture ZIPs passed the complete packaging smoke harness, including offline startup video/fallback, full calendar schedules, first game, backup/restore, relaunch, duplicate launch and byte-for-byte data preservation after app replacement. Reports: `dist/macos/verification-0.1.0-beta.7-{arm64,x86_64}.json`, both with `checks.complete: true`. Bundled simulation, generator and correction-file hashes match the accepted source.
- An initial Apple Silicon browser smoke stopped at an image-readiness assertion. The runner now waits up to 30 seconds for visible local images to become ready, still fails with detailed missing-image evidence, and explicitly decodes the affected asset. No source art or game UI was changed. Its incomplete report is retained with `-first-attempt` in the name.

Older packages are retained. Intermediate schedule-only beta.7 packages and their smoke reports are under `dist/macos/superseded-beta.7-overtime-rounding/`; use only the final verified top-level ZIPs.

## Repeat

```sh
PYTHONPATH=src:tests python -B -m unittest test_schedule_integrity test_basketball_accounting
PYTHONPATH=src python -B scripts/audit_basketball_accounting.py --output /tmp/schedule-accounting-new.json
PYTHONPATH=src python -B scripts/ten_season_soak.py --output-dir /tmp/schedule-career-new --seasons 1 --seed 20261004 --team MIA --save-name schedule_new
PYTHONPATH=src python -B scripts/audit_basketball_accounting.py --output /tmp/schedule-career-accounting-new.json --save /tmp/schedule-career-new/saves/schedule_new.json
```

Use fresh disposable paths; do not run the career driver against a live user's directory. The accounting tool refuses to overwrite existing evidence. Intel packaging tests use Rosetta on this Apple Silicon Mac, not physical Intel hardware. Clean-machine installation, older macOS and longer-term balance remain separate checks.
