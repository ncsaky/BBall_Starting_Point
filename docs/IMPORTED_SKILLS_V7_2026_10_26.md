# Imported Skill Evidence V7

Published starting baseline: `2026-10-26-imported-skills-v7`.

## Scope And Finding

The pass examined all 691 imported player profiles. It changed 24 underlying
traits across 20 players, beyond V6's three reviewed profiles and stamina repair:

- 12 shooting-range corrections.
- Nine passing-read corrections.
- Three sparse-proxy corrections, all for Georges Niang: defensive effort,
  screen navigation and portability.

Combined with V6, the difference from V5 is 147 numeric traits across 113
players. This is not 113 comprehensive player reratings: many changes remain
stamina-only. No prospect generation, development, opportunity, retirement or
headline overall formula was modified.

The importer uses league-relative statistical percentiles and a subjective
full-health ranking prior. Those are not direct measurements of absolute skill.
An extreme or missing input is a review flag, not proof that every low-rated
player deserves a raise. This pass only corrects conflicts that can be checked
against sampled NBA production, or modestly regularizes an unreviewed, sparse
proxy. It does not set an overall floor or change players merely to match a
replacement cohort's average.

## Method

`src/nba_gm_data/imported_skill_calibration.py` runs after medical construction
and final manual profile overrides, before rating-derived markets are rebuilt.
It returns new trait records without modifying its inputs.

Career evidence comes from `data/research/player_career_stats.json`. Identity
must match the ESPN athlete ID and NBA endpoint. Only the two completed seasons
preceding the canonical 2026-27 season qualify. Future seasons, nonfinite counts,
invalid minutes, missing required fields and impossible three-point makes are
excluded. Missing statistics are never converted into zero production.

The latest calendar season has weight 1 and the preceding season weight 0.5.
An absent latest season does not promote the previous season to full weight.
This retains some injury-interrupted history without assuming permanent decline.

### Observable Skill Conflicts

- At least 1,000 weighted NBA minutes are required.
- Shooting requires at least 80 weighted attempts, 1.5 attempts per 36 minutes,
  and observed accuracy of at least 34%. Accuracy is shrunk with an 80-attempt,
  35% prior; volume and accuracy inform a bounded modeled range target.
- Passing uses assists per 36 minutes and a shrunk assist/turnover ratio. Very
  low-assist profiles are not promoted simply for having NBA minutes.
- Only existing trait values at or below 65, with a target at least 12 points
  higher, qualify. The sample-dependent adjustment is capped at 10 raw points.
- These are conservative weak-input corrections, not a replacement for elite
  shooting/scouting models. Box scores do not establish defensive IQ or the
  speed of a shooting release; neither is inferred from these production checks.

The mapping, thresholds and priors are modeling judgments, not NBA-assigned skill
ratings. The unmodified observed totals, sources and correction details remain
in per-trait provenance and the verification report.

### Sparse Proxy Uncertainty

For effort, scheme IQ, screen navigation and portability, a partial proxy with
at most half its inputs available can be moved modestly toward the importer's
existing neutral missing-data prior of 50. This requires 500 weighted NBA minutes,
excludes existing human-prior and earlier-alignment calibrations, and caps the
adjustment at eight raw points. The rule can shrink either extreme; it is not
evidence that the player is a good defender. Only Niang qualified in this build.

Any manually reviewed or imported-rookie profile is protected as a whole.
Current 2026 draftees are excluded. Known nonshooters and poor observed shooters
are not given shooting skills. No trait outside the six eligible keys changes.
The provenance marker makes reapplication idempotent.

## Independent Cross-Checks

These are qualitative checks on the data interpretation, not sources for our
numerical skill targets:

- [NBA: Coffey signing](https://www.nba.com/news/bucks-sign-amir-coffey): his 2024-25 three-point percentage was 40.9%.
- [Raptors game notes](https://www.nba.com/gamenotes/raptors.pdf): identify Shead's bench-assist production.
- [NBA statistical glossary](https://www.nba.com/stats/help/glossary): distinguishes assists, blocks and other observable events from broader impact concepts.

The build itself uses frozen pre-start career records, not live pages that may
later contain future seasons. Existing V6 research and manual decisions remain
unchanged.

## Results

Selected fixed-24-minute displayed overall changes relative to V6:

| Player | Before | After | Main correction |
| --- | ---: | ---: | --- |
| Ryan Nembhard | 47.5 | 49.4 | Shooting and passing |
| Jamal Shead | 68.7 | 69.7 | Passing |
| Scotty Pippen Jr. | 67.9 | 69.0 | Shooting and passing |
| Tre Jones | 65.5 | 66.3 | Passing |
| Amir Coffey | 55.7 | 56.4 | Shooting |
| Georges Niang | 63.5 | 64.3 | Sparse proxies |

All-import mean overall: V5 72.439, V6 72.575, V7 72.597. V6/V7 p10 remains
62.7 and the maximum remains 95.1. These populations include free agents and
fringe players; they are not the earlier 449-player preseason roster cohort.
The small change is intentional. Some individual profiles remain questionable;
the pass does not certify their entire skill package or NBA role.

## Gameplay Verification

`output/imported-skills-v7-2026-10-26/verification.json` contains full evidence.
The publication script, `scripts/verify_imported_skills.py --publish`, and
follow-up checks verified the following:

- Fresh disposable V5 and V7 careers for seeds 17 and 29, with the same user
  team and no discretionary roster actions, advanced from October 28 through
  November 11. Each arm played 104 league games: 416 before/after games total.
  The starting date was positioned explicitly to bound this regular-season
  integration test; it is not a replay of the entire preceding offseason.
- All game minute totals matched between teams and represented 240 minutes
  plus valid overtime. Box-score scoring identities and unique history IDs held.
  Fatigue remained within bounds. Contracts, transactions, injuries, development
  and rotation state were carried by the real app-action path.
- Team-game scoring: seed 17, 118.221 to 118.245; seed 29, 118.077 to 117.692.
  These are descriptive short-window checks, not estimates of season balance.
- The V7 seed-17 daily/reloaded replay exactly matched its bulk advance across
  the full normalized durable business state, including games, transactions,
  contracts, development, rosters and health. Incidental timestamps/paths and
  save revisions are excluded by the existing comparison helper.
- A V6 career advanced for the same 14 days through V6 and V7 entry points.
  Both produced identical normalized durable state. This adds two 104-game
  preservation runs. Including the V7 daily replay, 728 games were checked.
- Fresh bulk windows took 12.3-14.8 seconds each; the daily replay took 24.9
  seconds. There was no new multiseason batch.
- All 24 protected playable-save/archive files retained their hashes. The
  active JSON and SQLite baseline versions match; SQLite integrity is `ok`.

The focused regression run passed 65 tests; the added direct simulation-feature
test also passed, for 66 distinct checks. These cover baseline pinning, skills
reaching simulation features, protected manual profiles, known weaknesses,
invalid/missing/future evidence, deterministic rebuilding, idempotency, prior
rating passes, talent balance, development coverage and user rotations. This
does not represent a clean full-suite run or resolution of previously reported
unrelated failures.

## Save Compatibility And Limits

The new archive and registry entry apply to new careers only. Existing saves
retain their original baseline, earned development, medical state, rotations,
contracts and roster decisions. Initial medicals, player ability/potential
metadata, identities, contracts, picks and prospect traits are unchanged.

The league-floor issue is **not proven resolved**. These corrections are too
small to explain or eliminate the entire eight-year distribution shift.
Production data cannot settle every defensive, physical or role-specific
scouting discrepancy. A later bounded/multiseason comparison may measure the
remaining effect, but no new overnight batch was started without approval.
