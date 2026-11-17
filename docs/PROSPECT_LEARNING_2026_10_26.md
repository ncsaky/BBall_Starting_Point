# Selective Prospect Learning Calibration

## Diagnosis From The Expensive Careers

The three completed ten-season careers lose top-end supply while their lower
rating percentiles rise. Increasing busts across all ordinary prospects would
attack the wrong population: many late picks already never establish a rotation
role, while roster departures account for most of the mean rating rise.

The unused-headroom check uses the actual 2027-2030 draftees, original player IDs,
entry traits, per-skill capacity records and save seeds. Among 27 successful
high-potential profiles, 25 have a mechanical all-developable-skills-at-capacity
rating of at least 90, but only five reached a sampled neutral 90 in the actual
careers. That all-skills capacity is an optimistic diagnostic, not a promised
future rating or an instruction to remove weaknesses.

The old learning process compresses the usable runway: the age multiplier falls
at 24, then drops again at 27, while sparse minutes and a fringe role multiply
learning down further. Raw prospects also hit the upside-rate cap despite being
much farther from their individual skill ceilings than polished prospects.

## Implemented Change

Only `health.monthly_trait_delta` changes in the game model. The calibration uses
the existing version-2 career-capacity records; it does not regenerate prospects,
change current ratings, change potential, or add a player-name/draft-slot bonus.

- Successful high-potential skills receive extra learning runway through age 29.
  Support depends continuously on potential, existing seeded fulfillment and
  the trait's aptitude, which already incorporates profile/motor/feel inputs.
- Exceptionally raw high-upside players can additionally learn toward their
  own remaining skill capacity. The extra component requires potential above
  75, a potential/entry-ability gap above 30, a successful career realization,
  and aptitude above .35. It does not target a headline OVR.
- Practice support prevents the low-minutes catch-22 from eliminating every
  promising fringe player. That floor is capped at .55 of the normal role
  factor, below the 1.0 factor at 24 minutes. Minutes, staff and health still
  matter. Permanently giving everyone eight minutes produces no 90+ players
  in the mature controlled sample, before or after the change.
- Each trait's capacity is unchanged. Low-aptitude holes retain the old learning
  behavior; sparse trait focus remains. The ordinary .24/.36 monthly limits
  remain except for raw catch-up, whose selective cap is .36 plus at most .45.
  The negative bound remains -.12.
- Low/moderate-potential profiles (potential <=70), disappointed realizations
  (.55/.80), and age-30+ behavior are unchanged. Imported players and legacy
  profiles without a version-2 career-capacity record keep their old behavior.
- There are no new random draws or rerolls, annual star quotas, forced
  retirements, extra injuries, or universal player-rating floors.

Existing version-2 careers adopt the rate adjustment only for future evaluated
months. Previously saved traits, development events, games, draft classes and
contracts are not recalculated. This is a forward runtime calibration, not a
historical save migration or a newly published baseline archive.

## Paired Mechanism Evidence

All probes use actual entry records, retain failures as well as survivors,
compare identical IDs/seeds, keep staff neutral and players healthy, and run
120 monthly development steps. Headlines are always evaluated at 24 minutes,
even in the eight-minute opportunity test. No games, financial decisions,
injuries, cuts or retirements are simulated in these probes.

| Paired Sample | 90+ Before | 90+ After | Unchanged Control Careers |
| --- | ---: | ---: | ---: |
| 714 entries, 2027-2030, 24 MPG opportunity | 6 | 16 | 648 |
| Same 714, only 8 MPG/fringe opportunity | 0 | 0 | 648 |
| Same 714, 32 MPG opportunity sensitivity check | 13 | 20 | 648 |
| Held-out 531 entries, 2031-2033, 24 MPG opportunity | 7 | 15 | 478 |

Every control career's annual checkpoints match exactly. Every initial rating
matches. The 10th percentile, 25th percentile and median sampled peak ratings
are unchanged in all four comparisons. The mature-sample mean peak changes
from 75.033 to 75.176; this is an upper-tail adjustment, not a general rookie
boost. Only 63 of the 714 mature sampled peaks change.

The held-out classes were not used to choose the coefficients, but they still
share the game's model and canonical environment. These are not independent
real-world observations or a new estimate of league equilibrium. The completed
careers motivated the mechanism; the coefficients remain game calibration,
not directly estimated NBA probabilities.

Two raw late-pick examples illustrate the intended effect: Milan Hayes (pick 27)
and Julian Keita (pick 39) enter at neutral 68.7 and 67.1. With constant healthy
24-minute opportunity their sampled peaks move from 83.1/83.0 to 88.7/88.6.
With only eight minutes, their new peaks are 80.6/80.5, versus 73.6/73.2 before.
Those are useful development paths without turning either into a guaranteed star.

The mature sample's late-pick 85+ count rises from 8 to 12, but **late-pick 90+
counts remain 0 to 0**. In the held-out sample, late-pick 90+ stays 1 to 1; that
existing pathway improves rather than a new star being manufactured. The
second-round star-supply problem is not presented as solved. A small number of
lower picks reaching the upper 80s is progress, not a substitute for validating
rare star outcomes under real opportunity and survival.

The 32-minute sensitivity check also leaves mature late-pick 90+ at zero. This
check was run after choosing the final coefficients, without changing them to
force a particular player across 90. A remaining hypothesis is that too few
late picks combine high latent upside with learnable role-critical skills:
trait aptitude is partly inferred from entry polish. That deserves a separate
generation/latent-aptitude investigation, rather than ever-larger global growth
bonuses or a guaranteed second-round star per class.

Each final controlled screen took about 22-30 seconds on this machine. This is
how to isolate development mechanisms without repeating a 13-hour league batch;
it is not a speedup claim for full game simulation.

## Research And Limits

[Vaci et al.'s NBA aging analysis](https://link.springer.com/article/10.3758/s13428-018-1183-8)
supports heterogeneous development and a peak around the late twenties, rather
than treating age 24 as the end of meaningful learning for everyone. NBA records
also show why late-selected players need a viable pathway: [Butler's fourth-year
Most Improved season](https://pr.nba.com/jimmy-butler-2014-15-kia-most-improved-player-chicago-bulls/)
and [Jokic's second-round selection and MVP](https://cdn-uat.nba.com/news/nikola-jokic-wins-2020-21-kia-nba-most-valuable-player-award)
are concrete counterexamples to eliminating late development. These examples do
not establish an exact gem rate or justify guaranteeing a star in every class.

Full-league star counts, veteran retention, salaries and the rostered rating
floor after this tuning still require a bounded overnight comparison. No new
multi-season careers were launched for this change. The already-running final
season of seed 17 remains frozen to the old learning settings plus the identity
crash repair, so its eventual success cannot be claimed as tuning validation.

## Reproduction And Regression Coverage

`scripts/probe_league_health_tuning.py` prepares the entry datasets and runs the
paired probes. Its reference mode executes the exact old monthly function and
first verifies that all other local health helper functions match the frozen
runtime AST. `compare` checks identical datasets, initial ratings, control
trajectories, capacity bounds and unchanged lower percentiles, then writes
`output/league-health-tuning-2026-10-26/verification.json`.

`tests/test_prospect_learning.py` covers frozen pre-change monthly reference
values, legacy profiles, failed realizations, low-aptitude skills, veteran
decline, gain bounds, injuries, staff, workload, ceilings, draft-slot neutrality,
serialized reloads and real monthly batch-versus-split processing. The related
development, talent, lifecycle, rotation-retention and simulation-consistency
tests are also run. No whole-suite green claim is made from that focused set.
The final focused run completed **81 tests with zero failures or errors**.

The subsequent [rare-upside supply pass](RARE_UPSIDE_SUPPLY_2026_10_26.md)
leaves these learning coefficients unchanged. It separately tests future-class
latent supply and the generated-draft information boundary, using actual
selection slots rather than treating consensus ranks as picks.
