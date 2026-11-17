# Rare Upside Supply and Draft Information

## What Was Missing

The previous learning calibration improved strong prospects without raising the
ordinary prospect floor. Its actual-entry controlled samples still produced few
late stars. This follow-up distinguishes **consensus rank**, **actual selection
slot**, latent talent, and realized career outcomes.

Two bottlenecks appeared:

1. Across 100 generated classes, just 21 of 3,000 consensus second-round
   prospects had potential >=80, before realization, opportunity or injury
   losses. The rank-decaying upper-tail probability left very little latent
   supply outside the lottery.
2. Generated-draft AI directly evaluated true potential, ceiling and rookie
   value. Widening the tail alone promoted most of the new hidden talent into
   the lottery. In 24 paired draft screens, 27 of 29 altered profiles went in
   the lottery and none reached round two. A low consensus rank in a controlled
   development probe was therefore not evidence of a genuinely late selection.

The initial aptitude hypothesis was not used to justify another learning boost.
Raw examples already had strong aptitudes and generous capacity in their better
skills, with genuine limitations elsewhere. Learning rates, skill aptitude,
capacity formulas, injury effects and aging remain unchanged in this follow-up.

## Implemented Boundary

Only newly generated talent-model-V2 classes receive the additional rare tail.
Its rank-independent component changes from .004 to .012 + .012 * class quality;
the existing rank-sensitive component and upper-tail value draw remain. These
are calibrated latent-upside probabilities, **not empirical star probabilities**.
There is no minimum number of gems per class and no guaranteed star outcome.

For a prospect whose true upside changes, the record additionally stores a
`scouting_prior`: the potential, ceiling and rookie-value estimates from the
original tail. They are persisted, not recalculated from developed abilities.
The same independent random stream and ceiling-room draw preserve the original
estimates without consuming any extra class RNG draws. Identities, class
strengths, ages, physicals, medicals, skill values and minutes projections remain
unchanged. True increased potential still enters the rookie's career capacities.

Generated BPA grades, team timeline fit, cap-value grades, board grades, pick
reasons and noisy scouting reports use these draft-day estimates. The added
latent upside cannot leak back into selection through the ceiling or rookie
value. Existing profiles with no prior retain their original evaluations.
This is a narrow information boundary for the additional tail, not a complete
new scouting model: legacy known-upside profiles still have the old behavior.
No player is forced into a later slot; normal team boards and selection logic
choose them. The prior also does not predict the seeded realization outcome.

Stored classes and already signed player profiles are not rewritten. Existing
V2 careers get the change only when generating future, not-yet-stored classes.
Earlier non-V2 careers retain the old generator. There is no baseline archive
replacement or historical save migration. No playable saves were edited.

## Controlled Evidence

Two disjoint generation screens use 100 classes each: year 2038/seeds 100-199
and year 2043/seeds 200-299. All **12,000** entry records are compared. Every
current skill and fixed-minute entry rating matches; **11,821** complete
prospect/capacity profiles remain unchanged. Only 179 profiles receive additional
upside. Realization draws and all trait aptitudes remain unchanged.

Controlled development uses healthy players, neutral staff and 120 monthly
steps. Only altered profiles and one unchanged control per class are developed;
this is not a census of population career peaks. Headlines are always evaluated
at 24 minutes, irrespective of developmental opportunity.

| Screen | Altered Profiles | Additional Consensus-Rank-15+ 90+ Peaks |
| --- | ---: | ---: |
| 2038 classes, 24 MPG | 81 | 5 |
| 2043 held-out classes, 24 MPG | 98 | 13 |
| 2038 classes, 8 MPG/fringe | 81 | 0 |

All unchanged sampled trajectories match exactly. In the 24-minute screens,
55 altered profiles have disappointed (.55/.80) realizations; none reaches 90.
This does not mean every disappointing career is bad, or that the game's
realization labels are empirical NBA bust classifications. The low-minute
screen does produce two lottery-ranked 90+ peaks; it does **not** show that
playing time has become irrelevant, or that all eight-minute careers fail.

### Actual Draft Selections

Twenty-four paired drafts use the real generated-draft lottery/order, team-fit,
BPA, medical and selection logic on a frozen baseline-team environment. After
the information boundary, the 29 altered profiles are selected as follows:

| Actual Selection | Tail Alone (Rejected) | Tail With Scouting Prior |
| --- | ---: | ---: |
| 1-3 | 10 | 1 |
| 4-14 | 17 | 4 |
| 15-30 | 2 | 10 |
| 31+ | 0 | 14 |

The 29 profiles retain the same selection slots and teams as their pre-change
counterparts when the prior is used. Development then uses those real selected
teams, slots and resulting player IDs, rather than consensus rank or a synthetic
single-team identity. Under healthy, fixed 24-minute opportunity:

- Among the 10 altered picks 15-30, 90+ peaks change from zero to three.
- Among the 14 altered second-round selections, 90+ peaks change from zero to
  one. Henrik Halvorsen, pick 51, moves from a 77.7 peak to 92.0, first reaching
  90 around age 25.6. His starting ratings are unchanged.
- The other late-selected 90+ examples first cross that line around ages 26.1,
  26.6 and 30.6, rather than every prospect arriving as a polished star.

These are **altered-profile comparisons**, not all second-round players, and
not an estimate of full-league star frequency. Changes to roster competition,
opportunity, financial decisions, injuries and retirement remain unmeasured.
Increasing late-star supply can itself affect the rostered floor through
competition; a fixed entry floor does not guarantee a fixed roster histogram.

## Verification and Cost

`scripts/probe_hidden_upside.py` performs the paired generation/learning screens.
`scripts/screen_hidden_upside_drafts.py` checks real selection slots; its
`--develop-report` option develops the altered profiles using the saved actual
selection identities. Both refuse to overwrite evidence. Artifacts are under
`output/hidden-upside-2026-10-26/`; the `scouting-prior*` files are the final
candidate. Earlier files retain the rejected tail-only investigation.

Each 100-class learning screen took about 15-20 seconds. Twenty-four pairs of
real drafts took about 64 seconds, and their altered-profile development screen
took about four seconds. These timings exclude full seasons and are not claims
that full league simulations now run faster. No new long career batch was
started. The old final-season repair control separately finished 10/10 seasons;
it uses old learning and is not validation of this tuning.

The focused regression modules cover 120 distinct passing tests: hidden/generated
upside, talent conversion, learning, development coverage and consistency,
lifecycle/retention, prospect-rating parity, draft slots, duplicate applications
and draft-year gates. The final combined run passed 119 tests; one additional
scouting-report regression was added and the six-test hidden-upside module then
passed. No whole-repository green claim is made.

One early probe serialized temporary player indexes, breaking their shared
object references and falsely changing the headline minutes context on reload.
The harness now serializes persistent inputs and rebuilds indexes, as the game's
canonical rebuild does. The corrected reload comparisons pass. No production
save/reload bug was inferred from that harness failure.

## Research and Next Gate

The [NBA's official 2026 draft notes](https://cdn-uat.nba.com/news/2026-nba-draft-news-notes)
list 22 second-round All-Stars and 11 second-round All-NBA players since 1989.
That supports preserving rare late-star pathways, not equating 90 OVR with an
All-Star selection or fitting a probability directly to an incomplete cohort.

The next gate is a bounded actual-league comparison using the combined learning
and supply changes, tracking all picks (including cuts), playing time, veteran
displacement, star formation, salaries, age groups and roster percentiles. Do
not increase the coefficients further based only on these healthy probes.
