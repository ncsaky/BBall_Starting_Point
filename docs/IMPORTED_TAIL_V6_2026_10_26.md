# Imported Tail Correction V6

## Published Boundary

Starting-data version: `2026-10-26-imported-tail-v6`.
Previous version: `2026-10-23-forward-tuning-v5`.

This correction changes 123 numeric trait values across 97 existing player
profiles. Three researched players receive 29 explicit trait corrections; the
other 94 players change only in stamina through reconcilable, unreviewed
arithmetic. The automatic intermediate repair report includes values subsequently
superseded by final manual overrides; the verification's numeric diff is the
authoritative final scope.

No prospect inputs, development coefficients, hidden-upside rules, bust draws,
playing-time policy, retirement rules or rating formulas change. Initial medical
profiles, health states, injury records, identities, contracts and pick terms
are identical to V5. Existing manual corrections outside these three profiles
retain their numeric values.

## Stamina Arithmetic

The default raw-trait builder now computes the available workload mean plus a
role bonus. Missing workload remains unknown, rather than treating a bonus as
evidence of conditioning. Values stay bounded to the trait scale.

The released roster-refresh pipeline deliberately retains its legacy arithmetic
as an explicit upstream reference. Recomputing its percentile calibration before
the preservation layer otherwise changes additional uncertain inputs and generic
durability. V6 does not silently rebase those distributions. Instead, after
alignment and initial health construction, `repair_preserved_stamina` corrects
only preserved values that still reconcile to the old formula.

Already manual-, league-, rookie-prior- or roster-aligned stamina values are
excluded. The correction records its old value, component percentiles, role
bonus, corrected value and source ID; repeated application is a no-op. Explicit
post-alignment scouting corrections remain the final authority.

This fixes a defined arithmetic problem. It does **not** establish that playing
time percentiles are an ideal physiological stamina model or correct every
unsupported input. A general raw-input rebase remains outside this release.
For new V6 careers, future fatigue and stamina-dependent injury probabilities
can change under the existing formulas. Initial injuries/durability are not
erased, and neither the injury model nor aging model is modified.

## Researched Profiles

All headlines below are evaluated at fixed 24-minute workload. Exact trait
numbers are conservative game-model judgments, not ratings assigned by the NBA.
The overrides retain citations and .62 confidence rather than pretending these
are directly measured hidden skills. Sources used for calibration predate the
game's July 28, 2026 start, apart from same-day reporting of already completed
2025-26 play. Later previews and October transactions were not used to alter
the starting roster or ratings.

| Player | V5 OVR | V6 OVR | Calibration Decision |
| --- | ---: | ---: | --- |
| Spencer Jones | 45.6 | 67.3 | Replace an obsolete near-non-NBA profile with limited complementary wing utility; preserve weak initiation and interior deterrence. |
| Isaac Okoro | 60.9 | 70.0 | Restore perimeter recognition/action defense and ordinary conditioning; preserve offensive creation and shooting limitations. |
| Dorian Finney-Smith | 62.5 | 66.9 | Modest veteran recognition, connective passing and conditioning correction; no restoration of peak mobility or primary creation. |
| Jordan Hawkins | 61.8 | 61.8 | Reviewed, not boosted. A low headline alone does not justify removing real limitations. |

### Evidence Notes

- [Denver's February contract release](https://www.nba.com/nuggets/news/nuggets-sign-spencer-jones-to-nba-contract): 46 appearances, 34 starts and 23.6 minutes per game support revisiting Jones' obsolete input profile.
- [NBA's July Jones reporting](https://www.nba.com/news/spencer-jones-free-agency-2026): the completed regular season and subsequent retention provide additional evidence of an established complementary role.
- [Official Denver–Brooklyn box score](https://statsdmz.nba.com/pdfs/20260104/20260104_DENBKN.pdf): Jones' 26:49 workload also illustrates modest scoring and playmaking; minutes do not establish star-level creation.
- [Cleveland's Okoro role analysis](https://www.nba.com/cavaliers/news/features-isaac-okoro-230627): perimeter assignments coexist with restricted offensive opportunities.
- [NBA's Okoro re-signing report](https://www.nba.com/news/cavaliers-re-sign-isaac-okoro): defensive specialist recognition supports a role-specific correction, not an across-the-board increase.
- [Chicago's acquisition release](https://www.nba.com/bulls/news/chicago-bulls-acquire-isaac-okoro-from-cleveland-cavaliers/): his multi-season role adds context beyond one low input sample.
- [Donovan interview reporting](https://www.nba.com/news/the-athletic-bulls-isaac-okoro-excited-for-new-start-can-he-help-build-their-defensive-identity): physicality matters, but one perimeter defender cannot carry an entire scheme.
- [Rockets signing report](https://www.nba.com/news/rockets-sign-dorian-finney-smith-lakers-2025-free-agency): complementary shooting and defense motivated the acquisition.
- [Finney-Smith injury reporting](https://www.nba.com/news/rockets-dorian-finney-smith-expected-to-miss-start-of-season): ankle recovery is counterevidence to automatically restoring peak physical ability.
- [July Finney-Smith trade report](https://www.nba.com/news/dorian-finney-smith-hornets-trade): his disappointing recent output and declining roster value argue against a major rejuvenation.
- [Hawkins' season-specific NBA statistics](https://www.nba.com/stats/player/1641722/traditional?Season=2025-26&SeasonType=Regular%20Season): recent efficiency and role provide no basis for broadly lifting the current profile.

Source-derived facts motivate the direction. They do not directly determine
the exact raw-trait values or an OVR target. No six-game playoff shooting sample
is extrapolated into permanent elite ability.

## Distribution And Limits

For the same 449 original preseason roster identities, mean fixed-minute OVR
moves from 76.415 to 76.584. The median moves from 76.2 to 76.3; the 10th
percentile moves from 66.3 to 66.9; the 95th percentile and maximum are unchanged.
The weakest 45 profiles after reordering average 63.104 versus 62.2 before.
This narrows one part of the input problem; it does not force the tail to the
incoming-rookie mean or remove legitimate weak players.

Irving, Lively, Murray-Boyles, George, Gordon and Randle retain their prior
reviewed headline ratings. Broad veteran buffs, extra prospect busts and
guaranteed developmental minutes were deliberately not added.

The change affects on-court features and derived markets, not only labels.
However, no new long-run league batch was launched, and the previous eight-
season evidence is not presented as validation of this new starting baseline.

## Verification And Save Compatibility

`scripts/verify_imported_tail.py` verifies exact numeric scope, preserved
manual values, unchanged identity/medical/financial records, deterministic
rebuilds, protected file hashes and the final archive. Its candidate and
verification report are in `output/imported-tail-v6-2026-10-26/`.

A disposable V5 save was advanced from November 14 to November 21 through real
app actions using both V5 and the V6 entry point. Hydrated meaningful save state
matched exactly, excluding the existing incidental path/revision/timestamp
normalization. A separate test also preserves an earned development total,
traded roster assignment and contract override through V6 entry/reload. Fresh
V6 saves use the corrected traits. Seeded full-game replays are identical on
repeat, with positive scores; focused fatigue tests confirm the expected
direction without resetting injury state.

The focused regression work completed 128 distinct passing tests: the 75-test
combined run, two additional V6 baseline/saved-growth tests (the resulting
seven-test V6 module passed), and 51 lifecycle, retention, generated-upside and
development-coverage tests. This is not a claim that the whole repository suite
is green.

The immutable V5 archive remains registered. V6 receives its own archive and
registry entry; old playable saves and previous archives retain their hashes.
There is no automatic historical save migration and no release packaging.

Historical V5 forward-tuning tests now explicitly use the published V5 archive.
The earlier alignment test still checks that its V2 correction left Beal alone,
then separately checks that current V6 changes only his proven stamina input.
This avoids confusing a later versioned arithmetic repair with a regression in
the original alignment. No assertion was replaced with a generic tolerance.
