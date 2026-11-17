# Historical shooting data QA — November 13, 2026

**Diagnosis confirmed for the main defect: missing source-field alias, not FGM-as-2PM or a demonstrated cross-player join.** The imported historical cache has FGM=0 and FGA=0 in every one of34,325 player rows.16,050 rows have made threes, so all16,050 necessarily violate3PM≤FGM. The intended total-FG field exists in the retained team statistics and in representative authoritative ESPN player responses; the parser does not read its long player key and converts missing input to zero.

No raw source file, production parser/importer, canonical data, save or generated box score was modified. Research-only diagnostics and derived evidence are under [milestone2 diagnostics](diagnostics/milestone2_20261113/historical_shooting_qa_results.json). Source samples were bounded to four requests: three successes and one404; the failed request was not retried. Rerunning the diagnostic now uses retained samples offline unless explicit `--fetch-samples` is supplied.

## Source and transformation trace

`data/research/game_boxscores_2025_26.json` is an imported ESPN-summary cache, not the output of the game simulator. Its refresh reports413 existing preserved games plus896 attempted missing schedule games and a playoff pass; games are merged by external game ID. The single aggregate fetched-at timestamp is not a per-game acquisition timestamp.

Read-only `research.py` inspection finds:

* Summary parsing pairs the source `keys` with the athlete `stats` array and attaches athlete ID/team. The relevant authoritative key is **`fieldGoalsMade-fieldGoalsAttempted`**.
* `parse_boxscore_stat_row` reads total FG only from **`fg` or `FG`**, while its three-point/free-throw paths already accept their long ESPN keys.
* `parse_made_attempt` maps an absent/invalid value to zero makes/attempts. The missing alias therefore creates apparently numeric zero FG values rather than missing data.

The bug is reproducible from the key contract without changing production code. This explains why points,3PT and FT can remain populated while FGM/FGA are zero. Reinterpreting stored FGM as2PM, adding3PM to zero or clamping3PM≤FGM would preserve/fabricate wrong totals and would not recover attempts.

## Exact retained coverage

| Audit | Result |
|---|---:|
| Games / player rows |1310 /34325|
| Positive-minute player rows |28191|
| Positive FGM / positive FGA rows |0 /0|
|3PM>FGM rows |16050|
| Regular / playoff tagged games |1235 /75|
| Final / postponed / scheduled statuses |1304 /4 /2|
| Duplicate game/team/player keys found |0|
| Retained team groups |2620|
| Team groups where reconstructed total FGM reconciles |2601|
| Team groups where player3PM /3PA sums match team |2606 /2601|
| Team groups where playerFTM /FTA sums match team |2607 /2605|

A populated cache is not a completed-game-only dataset: four postponed and two scheduled records must be excluded from historical outcome calibration. In particular, the scheduled May24 record returned404 from the current public endpoint. That is an availability/provenance gap for that record, not the cause of the all-season FG alias error or proof that every retained playoff record is invalid.

## Authoritative sample checks

| Game | Scope / source season | Successful keyed shooting rows |
|---|---|---:|
|[401809243](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401809243)|2025-10-21; source season2026,type2|20|
|[401810557](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401810557)|2026-02-01; source season2026,type2|24|
|[401869187](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401869187)|2026-04-18; source season2026,type3|26|

Across70 usable source rows, all70 contain the long FG key without an old `fg`/`FG` alias. All70 match retained3PM/3PA/FTM/FTA/points by athlete ID and team; all70 also match the algebraically reconstructed total FGM. Source header IDs and calendar dates agree with these three retained game records. Season2026 here means the **2025–26 ending-year convention**, with type2 regular and type3 postseason; these samples do not show a cross-season merge or a shifted stat-array join.

Concrete examples: Kevin Durant on Oct21 has sourceFG9–16,3PT0–4,FT5–6,23 points; retained FG is0–0 while the other scoring components agree. Jabari Smith Jr. has sourceFG7–15,3PT2–6,FT0–0,16 points; those are7 total field goals, including2 threes, not7 twos. Its point identity is2×7+2=16. Source raw responses and hashes are preserved, not replaced by a normalized interpretation.

These checks identify the primary cause and validate a minimal alias normalization. They are representative samples, **not an authoritative refetch of all1310 games**. No claim that every unrelated field or residual team mismatch is now verified.

## Minimal normalization and conditional recovery

**Future production correction proposal, not implemented:** recognize the long total-FG key before/followed by explicitly supported legacy aliases; parse it as total makes/attempts. Treat missing/invalid source values as missing with a reason. Keep source-key/version provenance so repeated normalization is idempotent and already normalized rows are not transformed again. Do not use player names, dates or desired totals to select a fix.

The three retained authoritative samples provide **70 directly normalized shooting rows**, including FGA, in the diagnostic result. For the larger cache, total FGM has a limited algebraic recovery:

`points = 2 × total_FGM + three_point_makes + free_throw_makes`

Thus `total_FGM = (points − three_point_makes − free_throw_makes) / 2`.

The research-derived view requires integer/nonnegative results, total_FGM≥3PM, final-game status and independent reconciliation to the retained team FG makes. **34,216 player records** pass those conditional checks. They are explicitly **reconstructed**, not newly observed player FGM, and not a production replacement. FGA is **null**, not zero or an estimate, outside the directly checked samples. Shot attempts cannot be recovered from points.

The [derived view](diagnostics/milestone2_20261113/historical_total_fgm_derived.json) preserves original zero fields, reconstructed eligibility and method. It supports arithmetic/source QA and limited checked historical calculations; it is not a gold-standard full-season calibration dataset. Team reconciliation is necessary but cannot rule out compensating individual errors.

## Residual exceptions and quarantine

There are19 failing/missing retained team groups:12 belong to the six nonfinal postponed/scheduled events; **seven final-game team groups** also fail the FGM sum check. Those final groups occur in games401810150,401810372,401810547,401810560,401810577,401810633 and401810760. Their player algebra is not sufficient to reconcile the independent team figures. The exact residual cause—scoring correction, missing attribution or another field discrepancy—was not resolved in this bounded pass. Do not distribute the difference among players.

[Exception records](diagnostics/milestone2_20261113/retained_team_reconciliation_exceptions.json) preserve the team strings, derived sums and status context.84 final-game player rows fail the team-level recovery gate;25 retained player rows belong to a postponed record. Together these account for109 unrecovered rows. Nonfinal records with no player rows remain excluded at game level.

| Field/use | Usable rule |
|---|---|
| Raw cached FGM/FGA |Quarantine all as missing-by-parser, including zeros that happen to match a genuine zero. Do not identify valid zeros without source evidence.|
| Direct normalized sample FGM/FGA |Usable with source IDs/keys/season preserved and row invariants checked;70 rows only.|
| Reconstructed total FGM |Conditional research-only recovery for eligible final-team groups; retain derived label and all checks.|
| Full-season FG%,2PA,2P%,effective FG% requiring FGA, or possession estimates requiring FGA |Not usable from this cache until actual total attempts are recovered/verified. No denominator imputation or clamping.|
|3PT/FT/points |Potentially usable independently after row and relevant team reconciliation, final status and source checks. Do not certify all rows from the70-row sample; retain per-field flags.|
| Minutes, rebounds, assists, steals, blocks, fouls |Not logically invalidated by the missing FG alias. Use field-specific completeness/source reconciliation; incomplete/nonfinal rows and tactical/context issues remain.|
| Schedule/scores |Separate from player shooting, but filter final status and validate event/phase identity. Scheduled404 record is not a played outcome.|
| ESPN career-season snapshot |Different parser/source path; its importer recognizes the long FG key. Do not blanket-quarantine it from this game-cache finding or assume it is automatically perfect.|

## Imported history versus generated boxes

Read-only generation code constructs totalFGM as FG2M+FG3M and totalFGA coherently; the plus-minus builder also checks `points == 2*fgm + fg3m + ftm`. This diagnosis concerns the imported research cache/parser. It is **not evidence of the same defect in newly simulated game boxes**, and no game was run to make that claim. Consumers using this cache for historical comparisons must honor the quarantine; offense priors using the separate season-career snapshot should be audited by their own lineage rather than assumed contaminated.

Future regression cases for an authorized importer correction: long keys; legacy aliases; genuine0–N; missing/invalid values; DNP; made threes within totalFG; multi-team player IDs; regular/postseason ending-year semantics; nonfinal records; team/point reconciliation; repeated normalization. Research has not installed that fix or changed existing expected outputs.

Reproduce offline with `python3 docs/ratings-evidence-2026-10-29/diagnostics/milestone2_20261113/historical_shooting_qa.py`. The raw cache, original records and source hashes remain unchanged. No human answer or paid access is needed for this diagnosis; the seven residual final-team discrepancies remain explicit scoped gaps.


## Bounded residual follow-up — November 13

One Chicago game (401810150, November29,2025) was checked against one retained authoritative response. Nine identified playing rows sum to38FGM/99points; source team statistics list39FGM and components imply101points. Two DNP rows and one unidentified zero-stat row do not establish twelve successful player joins. Identified scoring rows preserve prior points/3PM/FTM. Cause and attribution remain unknown; do not allocate the residual. The other six exceptions were not rechecked. [Coverage correction](diagnostics/milestone3_20261113/residual_coverage_correction.json) supersedes any broader reading of the preliminary matched_CHI_rows inventory. No production source/cache repair was performed by research; backend owns that work.
