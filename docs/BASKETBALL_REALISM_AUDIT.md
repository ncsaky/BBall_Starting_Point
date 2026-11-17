# Basketball Accounting And Career Audit

Started 2026-10-03; completed 2026-10-04. Private macOS beta.6 follow-up.

Update: beta.7 addresses the schedule finding and a rare overtime-minute rounding edge case. See [Schedule Integrity Follow-Up](SCHEDULE_INTEGRITY.md). The beta.6 measurements and remaining calibration concerns below are retained as historical evidence.

## Scope

Three fixed-roster regular-season simulations (seeds 7, 19 and 31), plus a disposable Warriors career (seed 20261003) through playoffs, draft, re-signing, free agency, training camp and rollover. Fixed-roster runs deliberately exclude evolving injuries, development and trades; the career run exercises those systems through app actions. This is not a claim that all basketball balance, all franchises, or ten years of careers are verified. No real user saves were changed.

## Fixed

- `sim.py:shooting_line` could generate points inconsistent with made shots, and two-point makes greater than two-point attempts. Shooting reconstruction now respects the assigned point budget and parity. When that budget caps sampled threes, their attempt volume is reduced too, rather than introducing systematic additional misses. The existing random draws are retained.
- Overtime added player points without corresponding team shooting totals or extra playing time. `resolve_overtime_if_tied`, `add_overtime_points` and `add_overtime_minutes` now reconcile shot totals, offensive efficiency and 25 additional team-minutes. Zero-minute players stay at zero. Score generation and winner selection are unchanged. Regulation and overtime timing/scoring checks follow [NBA Rule 5](https://official.nba.com/rule-no-5-scoring-and-timing/).
- The existing career soak driver tried to skip the required re-signing phase. It now uses the same open-market action as the game. This was a verifier defect, not evidence that the game could not finish its offseason.
- Soak snapshots previously copied only JSON, omitting archived history SQLite data. They now use the existing complete export/restore path and remain readable independently after rollover.

These fixes apply to newly simulated games. Existing historical box scores are not rewritten or retroactively recalibrated.

## Evidence

`output/realism-2026-10-03/accounting-before.json` records 3,705 games before the repair:

| Accounting failure | Count |
| --- | ---: |
| Shooting points disagree with made shots | 31,575 player/team lines |
| Impossible shooting attempts | 1,323 lines |
| Team/player field totals disagree | 360 field comparisons |
| Incorrect team-minute totals | 180 team-games |

`accounting-release.json` checks the same 3,705 games with zero accounting failures. Every game score and winner exactly matches the pre-fix run. It records the simulation source SHA-256, per-seed scores and full aggregate box statistics. There were 90 overtime games. Checks cover integer/nonnegative counts, legal two/three/free-throw attempts, player/team totals, final scores, no tied finals and regulation/overtime minute limits.

Across seeds, scoring remains 117.47-117.78 points per team-game. The corrected box environment is approximately 42.2% FG, 31.8% three-point shooting and 75.5% FT, with 96.3 FGA, 34.8 three-point attempts and 33.5 FTA per team-game. **These are measured model outputs, not an assertion of current NBA realism.** Repairing impossible box scores necessarily changes shooting statistics even though points and winners stay identical. Further shot-volume and percentage calibration remains worthwhile.

The final-source career completed in four minutes with zero hard invariant failures, 12 trades, 60 generated rookies and a successful 2027-28 rollover. Its champion was Oklahoma City. `release-career/soak_audit.{json,md}` contains the full career report. `career-accounting-release.json` independently checks all 1,326 archived games after rollover, and all four self-contained phase snapshots, with zero box-score errors. Those snapshots share the same games; their counts are not additional independent samples. Development averaged +0.47 for players 22 and younger, +0.33 at 23-27, -0.09 at 28-31 and -0.47 at 32+. This is one seed, not a balance guarantee.

Focused regressions passed: 20 basketball/soak/lineup/history/minutes/replay Python tests, 26 save-persistence/static-media Python tests and 102 JavaScript tests. No full-repository green test claim is made. Both beta.6 build manifests contain the same simulation source SHA-256 as the accepted fixed-roster audit.

Both extracted beta.6 ZIPs passed the complete packaging smoke harness, including offline startup video and fallback, first game, backup/restore, restart, duplicate launch and byte-identical stored data after app replacement. Reports: `dist/macos/verification-0.1.0-beta.6-{arm64,x86_64}.json`. The packaged first-game box scores were also read back and audited independently. Intel testing is through Rosetta, not physical Intel hardware; these remain ad-hoc signed and unnotarized private builds.

Earlier candidate reports (`accounting-after.json`, `accounting-final.json`, `accounting-volume-corrected.json`) are retained as diagnostic evidence, not final acceptance results. An intermediate reconstruction depressed free-throw percentages; the final regression includes profile guardrails as well as arithmetic properties. Intermediate career runs and unverified ZIPs are likewise not release evidence.

## Open Findings

1. **Schedule integrity is the next priority.** The schedule template has 1,235 games marked regular, and `save.py:generate_future_schedule` propagates it. CHI, DAL, DEN, GSW, MEM, MIA, MIL, MIN, NYK and SAS each receive 83 games; the other teams receive 82. The December 16 SAS-NYK entry (`401809839`) is included as regular. Removing that alone would not repair the remaining imbalance. The existing rollover test explicitly expects 1,235 games. Repair the source/generator with explicit phase handling and a test asserting 82 games for every team, while preserving already-played save results.
2. **Injury burden needs an audit of semantics before tuning rates.** The career report's expected missed-games estimate and recorded missed-games counter differ substantially. These measures may count differently; no conclusion about correct injury frequency is established here.
3. **Contracts and roster calibration remain limited.** The career harness flags zero extensions against its old 20-35 band and an 18-player Phoenix roster at its regular-season checkpoint. Eligibility changes, baseline contract dates and cutdown timing need investigation before changing those systems. A warning is not proof of an engine bug.
4. **Long-term balance is unverified.** One rollover does not establish talent, retirement, generated-player or cap stability over ten seasons. Overtime secondary statistics and multiple-overtime modeling were not redesigned.

## Repeat

Use the existing build Python or an equivalent configured environment:

```sh
PYTHONPATH=src python -B scripts/audit_basketball_accounting.py --output /tmp/accounting-new.json --compare output/realism-2026-10-03/accounting-before.json
PYTHONPATH=src python -B scripts/ten_season_soak.py --output-dir /tmp/career-new --seasons 1 --seed 20261003 --team GSW --save-name career_new
PYTHONPATH=src python -B scripts/audit_basketball_accounting.py --output /tmp/career-accounting-new.json --save /tmp/career-new/saves/career_new.json
```

The accounting tool refuses to overwrite existing evidence. Saved-career mode reads archived box scores without simulating or editing the save. Use new isolated paths, not a friend's live save directory. The new tests cover 4,860 shooting edge cases, internal shooting-profile guardrails, overtime point remainders, 50 overtime seeds, minute rounding, unchanged non-tied games, required re-signing actions and self-contained snapshot replacement.
