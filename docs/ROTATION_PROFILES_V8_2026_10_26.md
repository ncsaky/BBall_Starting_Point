# Demonstrated Rotation Profiles V8

Published starting baseline: `2026-10-26-rotation-profiles-v8`.

## Problem And Scope

V7 was a narrow skill cleanup, not a full solution to the imported-roster gap.
The next pass found two repeatable input issues:

1. A low-ranked subjective ratings prior could outweigh substantial NBA
   evidence across an entire offensive package. Ryan Nembhard's imported
   passing input was 95.1 before that prior, 34.82 afterward, and only 44.82
   after V7's bounded correction. His available NBA season contained 60 games
   and 5.3 assists per game. This does not prove the original 95.1 was correct;
   it demonstrates a source conflict that should not be treated as certainty.
2. Conditioning used league percentiles of playing time, including last year's
   total minutes. A returning NBA rotation player could have stamina in the
   teens despite sustaining an NBA workload. V6 repaired an arithmetic error
   but deliberately skipped previously calibrated traits, leaving this problem.

The candidate changes 199 numeric traits across 66 players:

- 127 offensive/fit-trait adjustments across 17 conflicting imported profiles.
- 59 conditioning adjustments; these overlap the profile group.
- Five reviewed traits for Coffey and eight for Ayton.

This is not 66 complete manual reratings. The automatic corrections affect
64 players; most receive conditioning changes only. The full numerical change
list and before/after profiles are in `output/rotation-profiles-v8-2026-10-26/candidate-review.json`.

No prospect generation, development, opportunity, injury-generation rules,
retirement rules, overall formula, identities, contracts, picks, initial medical
state, player ability/potential metadata or current-rookie traits are changed.

## Correction Rules

`src/nba_gm_data/rotation_profile_calibration.py` runs after the earlier rating
passes and medical construction, before derived markets/valuations.

### Contradictory Ranking Prior

Eligibility requires a completed latest NBA season with 40 games, 15 MPG and
1,000 weighted minutes across the last two seasons. Identity and finite source
values use V7's NBA-only evidence checks. Current 2026 draftees and manually
reviewed/imported-rookie profiles are protected.

At least eight reconciled historical calibration records must come from ranks
250 or lower in the subjective prior, with average suppression of at least
eight raw points. The historical final value must match the actually preserved
baseline value; refreshed metadata alone is not sufficient.

For supported offensive/fit inputs, retain 35% of the historical prior's
adjustment rather than its full effect. Restoration is capped at 20 raw points
per trait, cannot move past the original statistical input, and retains later
corrections. A prior that inflated a weak skill can be reduced too.

Eligible keys are release, range, shot versatility, rim pressure, handling,
passing, portability and playoff translation. At least half the source
components, or four play types, must be present. NBA minutes do **not** justify
upgrading defense, lateral quickness, rim protection or rebounding. These remain
unchanged automatically, even where their original proxies look questionable.

These weights and bounds are modeling judgments, not measured skill ratings.
They were frozen before the comparison, not optimized against its results.

### Conditioning

For the same demonstrated NBA rotation cohort with existing stamina below 40,
use a workload prior of `45 + 0.7 * latest MPG`, reduced for age over 30 and
bounded to 40-73. Blend 65% of the positive gap, capped at 30 raw points. Do
not reduce already adequate stamina or use an injury-only historical sample.

This changes full-health conditioning, not availability or durability. Initial
medical profiles and injury records are byte-for-byte unchanged. Future fatigue
and injuries can differ as a natural consequence; they are not claimed identical
between treatment and control.

### Reviewed Specialists

- Coffey: retain complementary wing shooting and a functional set-shot release
  without granting lead creation or elite defense. His later role decline is
  counterevidence against restoring a peak starter profile.
- Ayton: recognize assisted interior scoring and some paint touch while reducing
  the near-maximum rim-protection/rebounding inputs. His lack of range and
  limited passing/defensive versatility remain weaknesses.

The numerical choices are explicitly modeled scouting judgments in
`data/overrides/trait_overrides.json`, not numbers assigned by the cited writers.
Coffey's categorical imported role tag remains suspect; it was not rewritten
as part of this trait-only correction, and this pass does not certify all role
labels or spatial behavior.

## Research Cross-Checks

Sources were restricted to information available before the July 28, 2026 game
start when making rating judgments. Cached NBA season totals drive the automatic
checks; the following independently inform interpretation:

- [Mavericks signing announcement](https://www.nba.com/mavs/news/mavs-sign-rookie-point-guard-ryan-nembhard-to-multi-year-contract): Dallas rewarded Nembhard with a multiyear contract.
- [NBA G League announcement](https://gleague.nba.com/news/the-dallas-mavericks-sign-guard-ryan-nembhard-to-a-multi-year-contract): records his NBA starts, passing production and shooting sample.
- [Suns profile](https://www.nba.com/suns/news/collin-gillespie-is-surprising-the-nba-but-his-teammates-always-knew): describes Gillespie's breakout and competitive qualities.
- [NBA offseason report](https://www.nba.com/news/suns-resign-collin-gillespie-jordan-goodwin): reports his 80-game season and 40.1% three-point shooting.
- [Robert Flom's Coffey review](https://213hoops.com/2025-clippers-exit-interviews-amir-coffey/): useful bench spacing and competent defense, but limited breadth and no playoff role. This supports a specialist correction, not a star upgrade.
- [Milwaukee role-decline analysis](https://behindthebuckpass.com/bucks-amir-coffey-forgot-essential-trait-los-angeles): counterevidence on his diminished shooting role.
- [Nicole Ganglani's Ayton review](https://www.silverscreenandroll.com/lakers-analysis/118891/lakers-season-review-deandre-ayton-jj-redick): useful interior production, variable engagement and matchup-dependent playoff results.
- [Ayton pick-and-roll film analysis](https://www.silverscreenandroll.com/lakers-analysis/112482/austin-reaves-lakers-film-breakdown-wizards-deandre-ayton-lebron-james): efficient assisted short-roll finishing, distinct from lead creation.
- [NBC Sports on Ayton's role](https://www.nbcsports.com/nba/news/lakers-deandre-ayton-still-finding-role-with-lakers-im-not-no-clint-capela): his offensive role and limitations remained contentious.

## Starting Profiles

Fixed-24-minute display ratings, without current health adjustments:

| Player | V7 | Candidate |
| --- | ---: | ---: |
| Ryan Nembhard | 49.4 | 62.0 |
| Collin Gillespie | 66.3 | 77.3 |
| Tre Jones | 66.3 | 73.5 |
| Dru Smith | 56.4 | 64.5 |
| Quenton Jackson | 56.6 | 66.3 |
| Jamal Shead | 69.7 | 73.8 |
| Amir Coffey | 56.4 | 63.3 |
| Deandre Ayton | 63.7 | 65.9 |

The point is not to make every rotation player a 75. Strong one-skill profiles
can remain low overall; the correction must also improve or rebalance the
underlying simulation inputs, not just the displayed headline.

## Experiment

Exactly four disposable careers: V7 and candidate, seeds 29 and 913, two full
seasons each, ending October 1, 2028. One shared frozen runtime, separate starting
canonical inputs and saves. No changes to the actual engine or prospect rules
between arms, and no further parameter changes while running.

The shared policy uses hands-off GSW, automatic drafting, no discretionary user
bids/trades/extensions, explicit phase confirmations, legal low-role roster
cutdowns and the existing staff-retention policy. Different AI transactions and
different policy-selected cutdowns are consequences of changed inputs, not
forced identical individual decisions.

Monthly/phase observations retain fixed-context ratings, age, origin, actual
minutes/games, health, salary and development coverage. Completed seasons must
contain 1,230 games and 82 games for every team. All drafted players, including
those who never play, remain available for entry-cohort analysis.

The initial stored 2027 class is shared across paired seeds. Two seeds do not
constitute independent samples of that class or proof of long-run equilibrium.

### Test Setup Recovery

The candidate stopped at the first draft because a nested AI trade loaded the
default canonical and could not find the unpublished candidate in the frozen
registry. Draft-board initialization had been saved, but the draft index was
zero, no picks/trades were applied, and no rookies were onboarded.

Registered the identical candidate archive inside the disposable runtime only,
preserved the initialized board and failed-action marker as evidence, and
explicitly resumed. No rating, engine or draft-generation code was changed.
`archive-setup-repair.json` and the original manifest document this configuration
repair. Preparation now registers unpublished candidates up front, with tests
for nested baseline lookup. This is not a gameplay-balance finding.

## Completed Results

All four careers completed both full seasons and real rollovers to October 1,
2028: 196 committed app actions, 9,840 regular-season games, plus playoffs,
drafts, free agency and training camp. All eight completed league seasons had
30 teams playing 82 games. Each career observed 27 development-month checkpoints,
including the initial summer. No played-player metadata or end-rating coverage
gaps were found in the completed-season summaries.

Bottom-decile fixed-context ratings among rostered players:

| Seed | V7 Start / End | V8 Start / End | V7 Rise | V8 Rise | Ending Rosters, V7 / V8 |
| --- | --- | --- | ---: | ---: | --- |
| 29 | 66.89 / 68.57 | 67.39 / 68.40 | 1.68 | 1.01 | 438 / 445 |
| 913 | 66.89 / 68.60 | 67.38 / 68.86 | 1.71 | 1.48 | 444 / 444 |

The rise slowed in both seeds; the endpoint floors remain similar and are not
stationary. Roster size/composition differs, so this is not proof that the
correction alone explains every difference or that eight-year balance is fixed.

Retention of corrected players rostered initially in **both** arms:

| Seed | Shared Initial Cohort | V7 Retained | V8 Retained |
| --- | ---: | ---: | ---: |
| 29 | 61 | 27 | 29 |
| 913 | 60 | 24 | 32 |

Year-two qualifying rotation roles (20 games and 16 MPG):

| Seed | Corrected Incumbents, V7 / V8 | Generated Players, V7 / V8 | Second-Rounders, V7 / V8 |
| --- | --- | --- | --- |
| 29 | 15 / 20 | 21 / 20 | 8 / 5 |
| 913 | 16 / 25 | 20 / 16 | 5 / 4 |

Useful incumbents compete better; ordinary rookies do not get guaranteed
opportunity. This is an expected tradeoff, not justification to force more
minutes for every prospect. One seed-29 treatment top-three pick played 15.53
MPG, narrowly missing the reporting cutoff; rotation-count changes should not
be interpreted without actual minutes and health context.

The 90+ rostered count stayed 24 to 24 in both seed-29 arms and 24 to 23 in
both seed-913 arms. There is no short-window star-count inflation here, but
the generated classes have not had time to establish mature star replacement.

Mean-rating increases also fell: 1.2513 to 0.9531 for seed 29, and 1.2276 to
1.0712 for seed 913. The review separates continuing-player rating changes from
the composition residual, including entry/exit mix and roster-size changes.
That exact mean identity does not causally decompose the bottom-decile change.

### Regression And Compatibility

The complete focused rerun passed **82 tests**. Additional real-action replay
checks covered **624 games**: daily versus bulk advancement under both seeds
across October 28-November 11, plus a V7 career loaded through old and new
starting-data entry points. Normalized durable business states matched exactly.
These short checks explicitly position the starting date and complement, not
replace, the full chronological careers.

Existing saves, earlier baseline archives, initial medicals, contracts, picks,
player ability/potential metadata and prospect inputs were preserved. All
protected pre-existing save/archive file hashes remained unchanged. New careers
use V8; existing careers retain their original version and earned development.
No release ZIP/application was packaged and no user server was interrupted.

Evidence:

- `output/rotation-profiles-v8-2026-10-26/candidate-review.json`
- `output/rotation-profiles-v8-2026-10-26/two-season-review.json`
- `output/rotation-profiles-v8-2026-10-26/smoke-verification.json`
- `output/rotation-profiles-v8-2026-10-26/publication.json`
- Frozen careers and setup-recovery evidence under `~/.cache/nba-gm-audits/rotation-profiles-v8-2026-10-26/`.

This is focused verification, not a claim that the complete historical test
suite is clean or that all contract/transaction realism has been validated.

## Limits And Follow-Up

The correction does not certify every specialist's box-score output. In the
seed-29 candidate, Gillespie produced 15.9 PPG in 31.4 MPG in year one, then
14.0 in 27.8 in year two. Shead's assist rate and Ayton's scoring rate remain
worth a controlled role/lineup comparison. Different simulated teammates,
minutes, injuries and usage prevent declaring a box-score allocation bug from
these comparisons alone. Do not raise unrelated skills to force a desired PPG.

Initial medical priors were preserved, not independently recalibrated. Legacy
defensive/physical proxies and categorical role labels also remain audit areas.
Do not interpret this as clearance of all starting-roster inputs.

There is a small performance opportunity in the draft path: the caller already
has canonical context, but a nested trade application reloads the default
canonical when it is not passed through. The test-setup failure exposed that
path. It was not optimized during this experiment, preserving an identical
engine between arms; any follow-up should prove draft/transaction parity from
the retained checkpoints before changing it.
