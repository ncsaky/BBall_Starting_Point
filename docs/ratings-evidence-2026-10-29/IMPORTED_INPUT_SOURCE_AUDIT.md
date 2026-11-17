# Imported player-input source completeness audit — 2026-11-03

## Scope and finding

Read-only audit of the retained skill-input artifact, retained ESPN regular-season career-stat snapshot, canonical universe metadata, and import/trait construction order. No runtime probe, save, external request, rating edit, or test was performed.

The import is usable as a mixed, evidence-bearing input set, but it is **not a single-date complete skill-stat snapshot**. Its current-season regular-season box statistics were generated during the season, while other fields and later canonical calibrations come from different windows or modeled fallbacks. Strict-pass success and high aggregate coverage are not evidence that every field is observed or season-complete. Exact per-player cutoff/provider query for the `crafted_strict` source is not retained; where a partial-season claim cannot be proven, it remains unknown.

## Retained sources and dates

| Artifact | What it supports | Date/window evidence | Important limit |
|---|---|---|---|
| `Player Stats/player_skill_input_2025_26.json` | 526 player input rows; per-game box stats, GP/MP, role/advanced fields and augment metadata | `generatedAt=2026-03-11T22:36:29.668610Z`; `season=2025-26`; 524 BDL augmentation records have `pulledAt=2026-03-05T04:37:43.751293Z`; 2 manual supplements are dated March 5 | All 526 top-level rows say `crafted_strict+augment_public`, but per-row strict-source provider, query, and games-through date are absent. `sampleCount=1` means one augmentation record, not one game. |
| `data/research/player_career_stats.json` | Later regular-season season totals and per-game rates | `retrieved_at=2026-10-14T05:42:54.067559+00:00`; ESPN athlete career-stats endpoint with `seasontype=2` | 679 matched ESPN profiles of 691 game players; 572 have NBA seasons, 12 profile matches are missing; it is a retained comparison snapshot, not proof of what each March input row queried. |
| `data/canonical/universe_2026_27_offseason.json` | Actual canonical output and transformation reports | canonical start `2026-07-28`; roster snapshot `2026-10-13`; data version `2026-10-30-contract-separation-v10` | Combines the July 28 preserved baseline with later roster and regular-season-stat-derived adjustments; it is not purely a July or October player-skill snapshot. |

The ESPN row query template retained in player career stats is `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/stats?seasontype=2`. The canonical source registry records the March skill input, but no separate `player_career_stats` source-registry record with retrieval date was found. Row-level source URLs and the artifact-level retrieval date should therefore travel together in any future refresh.

## Season completeness: do not classify by GP alone

Of the 526 input rows, 509 have a GP value and 17 do not. The later career-stat snapshot has 547 players with a positive 2025–26 regular-season row. Normalized exact-name matching yields 515 comparable skill-input/final-season pairs:

- 457 March GP values are below the October final-season GP.
- 58 March GP values equal October final GP. For **all 58**, the available per-game box-score fields also match the final-season rates within rounding. This is consistent with an early-season player who did not play again and an already-final line; it is not evidence of incomplete extraction. Their exact upstream query date still is not provable.
- No matched March GP exceeds final GP.
- MP differences are generally consistent with whole-minute rounding for 47 same-GP rows (within one minute). Two notable exceptions are David Jones Garcia (raw MP 0 vs ESPN 68.2) and Kyshawn George (1369 vs 1392.0); retain these as source anomalies, not silently corrected values.

Examples of demonstrably lower counts versus the retained final row include Cedric Coward (49→62 GP), Luka Dončić (49→64), and Tyler Herro (17→33). These are clear differences from the October final snapshot, but the March artifact does not expose the exact cutoff day for each. The 11 nonmatched input rows with no final row/name match also must not be interpreted as zero performance or as a known injury/absence. The 17 null-GP rows include players whose cause is not established by this artifact; do not infer why an individual row lacks GP.

## Prioritized rookie cohort and reviewed players

The March file has 70 rows with `Rookie=True`; **all 70 lack both `touches` and `BBallIQ`**. For example, Coward has GP49, MP1263, 13.3 PPG, 6.1 RPG, 2.9 APG and minutes projection 26.1; Dylan Harper has GP50, MP1081, 11.2 PPG, 3.3 RPG, 3.7 APG and minutes projection 22.1. Both are explicitly missing those two fields. These box rates should be understood as the March extract's observed window, not final-season values. They are not independently corroborated by the later canonical traits, which are modeled and share source lineage.

Other reviewed-player examples show mixed windows:

- Luka: raw March GP49/MP1698, 32.4 PPG, 8.6 APG, 7.7 RPG; later ESPN final row is 64 games and 2291.2 minutes.
- Stephon Castle: raw GP51/MP1486 versus final 68 games/2040 minutes; current projected `minutes=29.7` is separate from raw cumulative MP.
- Lillard: current GP is null and MP is zero, while `minutes=2093` and `2025minutes=2093` refer to prior-season minutes; missing current-season box fields should not be populated from this prior-year total.

The input's box fields such as PTS/REB/AST are per-game; GP and MP are counts/totals. `minutes` is a role/minutes input and in `build_players` is converted to a projection if over 80; `2025minutes` is handled as prior minutes. For null-GP rows, a numeric `minutes`/`2025minutes` therefore does not establish a current-season sample.

## Missing values, defaults, and confidence

Across 526 March rows, missing-critical-field counts include touches 248, BBallIQ 82, boxCreationEst 38, passerRating 38, offensiveLoad 38, TS% 24, USG% 18, and 18 each for the listed per-75 fields (points, assists, turnovers, rebounds, steals, blocks, FGA, 3PA, FTA). CraftedOPM and CraftedDPM are missing on 6 rows each. The differing rookie and all-row counts reflect the wider cohort and field-level missingness.

The 691-player canonical universe records fallbacks on 422 players. Across it are 553 neutral-default field values; role/minutes proxies for touches on 413 players and age/role proxies for BBallIQ on 247. Other documented fallback families include neutral values for TS%, USG%, box creation, offensive load and passer rating; aliases for crafted offense/defense; and per-75 estimates derived from per-game values/minutes. Those fallback records make the imputation auditable; they do not make it observed evidence. The canonical report's coverage score (487/526 skill rows at or above .9) is an aggregate and can coexist with important missing fields.

Trait calculation separately assigns component percentiles and confidence. When a component is unavailable it can use neutral 50 with confidence capped at .2; other traits derive confidence from their own field coverage. Do not conflate the player-field fallback ledger with trait-level proxy/default logic, and do not raise confidence simply because a row has a GP count.

## Transformation order and date mixing

Inspection of `src/nba_gm_data/ingest.py`, `roster_alignment.py`, `traits.py` and the canonical reports supports this order:

1. Load March 2026 skill rows with official roster/draft data and overrides; build players and initial traits.
2. Apply prior data to returning players and preserve returning trait values from the July 28 baseline (the report says 622 players/9330 traits preserved); new players receive generated traits and rookie conversion where applicable.
3. Align players using retained ESPN 2025–26 full-season career statistics (alignment cutoff 2026-07-01; report says 247 players/1679 traits adjusted).
4. Apply stamina-role repair and overrides.
5. Apply imported-skill calibration (v7 report: 19 players/23 traits) and rotation-profile calibration (v8: 64 players/186 traits), both informed by later full-season career stats; then model profiles and persist reports.

So the canonical universe is a versioned composite: July baseline traits are intentionally preserved for many returning players, while later final-season career stats adjust a bounded subset, and October roster/status information is used for the universe. It would be inaccurate to describe every canonical trait as recalculated from complete October inputs. Rookie conversion is a separate modeled path and is not a license to infer missing rookie tracking data.

## Source-refresh candidate (not implemented)

A narrowly scoped candidate is justified: create a versioned, diff-only refresh of **observed 2025–26 regular-season aggregate and per-game fields** for matched NBA players using the retained ESPN `seasontype=2` full-season rows, with artifact retrieval date and row-level athlete URL attached. Preserve field/provider/season/split, GP, MP, totals and per-game rates; when a last-game date is unavailable, record that it is unknown. Do not replace any row with zero merely because a profile or season row is absent. Keep prior `2025minutes` separate from current season GP/MP. Do not fabricate tracking/advanced fields or replace neutral/proxy fallbacks with guessed observations.

For any subsequently approved recalculation, rebuild only metrics explicitly supported by those final rows, from totals and a consistent cohort/window. Retain missing/proxy provenance and field-specific confidence. Compare the proposed output against the July baseline in a review artifact; do not silently overwrite preserved traits or migrate an existing career. Prospect growth/potential and OVR formula are out of scope.

Suggested regression cases for a future implementation review (not executed here): (1) partial GP versus final GP is detected using source window/row provenance, not a GP threshold; (2) same-GP complete lines remain valid even at low GP; (3) missing profile/season rows are not zeros; (4) prior `2025minutes` cannot become current MP; (5) unsupported tracking metrics remain missing/proxy with documented confidence; (6) player-season joins use stable ID plus provider/source; (7) cohort percentile calculations use one declared source window; (8) overrides and calibration apply once; (9) repeated new-universe import is idempotent; (10) existing-career state remains unchanged absent a separately authorized migration.

## Open limits

Exact upstream `crafted_strict` per-player source query/cut date is not in retained files. The 58 same-GP lines are validated against later totals but their original retrieval timing remains unknown. The ESPN file covers regular-season stats only. The retained tracking registry is a list of dashboard/source categories, not player-level full-season tracking records. No conclusion here settles the user's October 20 start snapshot policy beyond reporting the distinct source dates; later regular-season data is used only for this completeness comparison and is not silently backdated into July-start evidence.
