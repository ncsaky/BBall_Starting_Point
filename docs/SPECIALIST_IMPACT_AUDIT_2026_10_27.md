# Specialist Impact Audit

## Verdict

The nonspacing-center concern is partly right, but a blanket center rating buff
would obscure several different problems. Existing V4 role-aware overall and
impact calculations already reward interior defense and rebounding. Edey's low
OFF headline coexists with a useful overall and plausible starting-minute scoring
volume. The stronger findings are incorrect shot profiles, nonlinear suppression
of bench scoring, missing separation of post/roll/screen skills, and a passing
feature that blends away some specialists' strengths.

This pass changes no live ratings, simulation rules, prospect development,
playable saves, GUI files or preview server. It adds a reproducible audit and
integrity tests. Findings below describe V8 inputs and the current engine,
not a newly tuned candidate. No further seasons were simulated.

## Method And Artifacts

- Baseline: `2026-10-26-rotation-profiles-v8`.
- Read all four completed V7/V8 careers, seeds 29 and 913, two archived seasons
  each. No save was advanced or rewritten.
- Run 31 controlled cases with 256 trials each: ten centers, five guards,
  six single-trait interventions, two feeder interventions, eight minute probes.
- Same fixed 240-minute rotation; target normally plays 30 minutes. Compare
  allocation at 114 team points/100 possessions separately from real
  `simulate_team_line` team offense and opponent offense.
- All probe players are age 27, healthy, without fatigue/rust, coaches,
  manifestos or a home-court advantage. Common teammates, common opponent and
  paired random seeds. Center minute probes transfer minutes only to/from the
  backup center, preserving the rest of the rotation.
- These are fixed full-game rotations, not possession-level five-man lineup
  experiments. They identify mechanisms, not a causal NBA player-impact estimate.
- Read cached ESPN NBA season totals for 2024-25 and 2025-26, checking identity
  and source URLs. Tiny samples remain visible, not promoted to reliable priors.
- Source files, engine modules and all four input saves were hashed before and
  after; all unchanged. Runtime: 48.7 seconds on this machine.

Code: `scripts/audit_specialist_impact.py`.
Full result: `output/specialist-impact-2026-10-27/audit.json`.
Tests: `tests/test_specialist_impact_audit.py`.

Run from the repository root:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/audit_specialist_impact.py --output output/specialist-impact-2026-10-27/audit.json
```

## 1. Post Skill Really Is Missing As A Distinct Mechanism

`traits.py` has no post scoring, roll finishing, hands or screen-setting skill.
`PostPPP` and `PnrrPPP` appear in the percentile field list but are never directly
consumed by trait inference or simulation. `Post%` contributes to versatility
breadth, not to demonstrated post efficiency. The input already contains these
fields for some players, but has no play-type possession counts and sometimes
missing PPP; this is not a ready-to-use comprehensive scouting database.

`sim.py:shot_creation_value` generally returns shot versatility alone. Its
scoring allocation grants a modest individual rim-pressure finishing bonus and
several creation/usage bonuses or penalties, without a distinct post scorer or
roll-man mechanism. `scoring_weight` receives no teammate features. Improving a
feeder can improve team offense, but cannot directly increase the finisher's
scoring weight; changes in the finisher's fixed-total share come through the
denominator. In the feeder probe, Edey's weight stayed exactly 21.3538 while
team offensive rating rose from 119.42 to 121.10.

There is indirect interior value: rim pressure, spatial rim efficiency,
rebounding, team shot quality and role-aware impact. It would be wrong to say
the simulation contains no interior scoring whatsoever. It cannot, however,
cleanly distinguish two equally broad trait profiles with different post touch,
rolling or screening skills.

This distinction is basketball-grounded: [Synergy's definitions](https://support.synergysports.com/support/solutions/articles/77000572558-glossary)
separate post-up bigs, rim-finishing bigs and stretch bigs, and define roll-man
possessions separately from post-ups. Michael Pina's [Edey film analysis](https://www.theringer.com/2025/04/15/nba/nba-play-in-preview-playoffs-warriors-grizzlies)
describes how increased screening and changes in spacing supported Memphis's
creators. Screening value is not synonymous with self-created post scoring.

## 2. The Shot Generator Gives Nonshooters Too Many Threes

`sim.py:shooting_line` starts three-point volume at
`minutes * (0.048 + spacing / 980 + ...) + random * 1.35`.
Even near-zero spacing therefore produces routine attempts. Earlier subjective
priors also elevated several nonshooters' range inputs: Gobert's pre-prior raw
range 5.19 became 36.74, and Zubac's 10.97 became about 44.26. These are raw
engine values, not displayed grades. Both input calibration and the behavior
mapping warrant correction; reducing the input alone cannot remove the attempt
floor.

With the same teammates and 30 minutes, fixed 114-point probes yield:

| Player | Points | 3PA | Aggregate FG% |
| --- | ---: | ---: | ---: |
| Edey | 12.7 | 2.9 | 42.2% |
| Ayton | 14.1 | 2.3 | 43.9% |
| Allen | 13.2 | 3.4 | 42.3% |
| Gobert | 13.1 | 3.3 | 42.3% |
| Zubac | 13.5 | 3.5 | 42.9% |

Exact rates are in the JSON, calculated as total makes / total attempts, not
averaged per-game percentages. These are isolated current-model outcomes, not
NBA predictions. Cached NBA 2025-26 totals have zero 3PA for Ayton and Zubac,
about 0.08 attempts per 36 for Gobert, and 0.24 for Allen. Edey's 2024-25 sample
has 1.32 attempts per 36; his 11-game 2025-26 sample has 0.63.

This also appears in the expensive saved careers: candidate seed 29 Edey took
195 threes in 79 games in 2026-27. Allen, Gobert and Zubac repeatedly attempted
roughly 3.7-4.2 threes per 36 in archived seasons. It is not just a tooltip error.

Overall FG% is reconstructed from assigned points and a broad scalar FG%
formula rather than separate rim/post/midrange/three attempts and efficiencies.
The model's low FG% for finishers cannot be repaired solely by changing the
headline OFF grade, nor does removing made threes alone automatically repair
the overall FG% denominator.

## 3. Bench Scoring Is Suppressed More Than Once By Minutes

`scoring_weight` already multiplies by minutes, then multiplies by
`(minutes / 32) ** 0.8`, bounded to 0.45-1.08. Projected scoring usage also
depends on projected minutes. Several low-usage/creation penalties compound
this. Some role dependence is legitimate, but the combined effect is very large.

Same traits and teammates; center minutes are exchanged with the backup center:

| Target MPG | Edey Points Per 36 | Ayton Points Per 36 |
| --- | ---: | ---: |
| 12 | 5.50 | 6.26 |
| 18 | 8.58 | 9.81 |
| 24 | 11.99 | 13.56 |
| 30 | 15.26 | 16.97 |
| 36 | 17.74 | 19.28 |

Thus low Ayton season production is not independent proof that his restored
finishing rating remains too low. At 30 minutes he scores at a plausible rate;
the saved careers mostly play him much less. This minute intervention changes
the other center's role as well, so it is not a pure algebraic scaling test, but
the explicit extra minute multiplier is directly visible in code.

Do not require exactly flat per-minute production across roles. Do test against
realistic ranges and avoid applying multiple implicit role penalties on top of
playing time without independent evidence. Treat this as a separate calibration
issue from rookie talent or career development.

## 4. Passing Specialists Lose Their Identity Before Assist Allocation

`sim.py:player_feature_vector` sets passing to the mean of passing reads and
scheme IQ. Scheme IQ itself mixes basketball IQ, passing evidence and defensive
impact. Assist generation subsequently uses steep thresholds on this blended
value. It is not simply using the displayed passing rating.

Shead: raw passing reads 77.44, scheme IQ 47.71, final passing feature 62.575.
His displayed passing is 93.2, while the fixed 30-minute probe generates 3.3
assists (about 3.9 per 36). Cached NBA samples have about 7.7 and 8.6 assists per
36. Candidate archived seasons also show roughly 3.1-4.1 assists per 36.

Holding his passing reads fixed while changing only scheme IQ from 20 to 80
moves assists from 2.88 to 4.80 per 30 minutes. This is a mechanism experiment,
not a recommendation to assign scheme IQ 80. Conversely, Gobert's high scheme
IQ raises his passing feature, and the saved careers give him roughly four
assists per 36 compared with about 1.9 in both cached NBA seasons.

Separating offensive reading/passing from general defensive scheme knowledge
is preferable to simply giving every guard more assists. Recheck elite passing
bigs, secondary creators, low-usage connectors and team assist totals together.

## 5. OFF Is Incomplete, But AI Does Not Just Use OFF

The common derived OFF formula is 35% shooting, 32% creation, 18% passing and
15% rim pressure. Creation itself already includes passing, versatility and rim
pressure. Offensive rebounding and screening are absent. Some app table paths
instead use a 30/30/20/20 formula, so a shared label is not even a single formula
everywhere. No UI formula was changed here.

An Edey offensive-rebounding intervention from raw 20 to 80 changes displayed
overall from 74.9 to 79.0 and team offensive rating from 121.06 to 121.58, but
OFF stays 61.5. The label omits a real modeled offensive contribution.

However, `save.py:player_attribute_summary` and `sim.py:player_impact_score`
already use role-aware value in talent model 2. Retention uses overall plus
role/age/contract factors. `transactions.py:build_player_asset_valuations` uses
raw on-court impact, portability, contract, health, upside and scarcity rather
than the displayed OFF number.

At fixed 30 minutes, displayed overall is about 80 for Edey, 86 for Allen,
88 for Gobert and 87 for Zubac. In original-roster AI valuation, Edey has
on-court value 61.26 and asset value 78.84 on the engine's raw scale; these must
not be compared numerically to his displayed OFF 61.5 as if they were the same
quantity. Existing V4 tests demonstrate role-aware big-man value reaches trade
and retention consumers.

The common-opponent probe retains meaningful differences: Edey is about 1.6
net-rating points below Allen, Jokic about 6.1 above Allen. These isolated model
differences do not prove either gap is correctly calibrated. They do disprove
the stronger suggestion that all centers are reduced to the same OFF value.

## Recommended Next Implementation

1. Correct shot-profile behavior and input contradictions first, with separate
   attempt/efficiency channels and explicit support for true nonshooters. Use
   measured attempt rates where supported and trait/archetype fallbacks for
   generated players. Do not make missing data mean zero ability.
2. Narrowly remove redundant minute-based scoring suppression, preserving
   legitimate differences in role/usage and the existing team-point totals.
   Validate stars, starters and bench players, not just centers.
3. Add distinct internal post-creation, assisted-finishing and screening
   mechanisms, with teammate feeding and spacing effects. Use sample-aware
   play-type evidence; do not equate unshrunk PPP with skill or make every
   large center a post creator. Generated prospects need plausible corresponding
   weaknesses and developmental ceilings, without retuning their talent supply.
4. Repair the passing-feature coupling, then consolidate OFF consumers to a
   shared, explicitly scoped offensive-contribution measure. UI exposure of
   additional skills can follow separately.

Implement these as bounded, separately testable changes rather than one broad
ratings bump. Respect existing career/model compatibility. Regression checks
should cover low/zero-spacing centers versus stretch bigs, post scorers versus
rollers, creator/finisher pairings, one versus two nonshooters, 12/24/36-minute
roles, passing guards and passing bigs, deterministic replay, shot/point
identities, team assist totals, and unchanged user rotation targets. Reuse the
saved careers for context; use fast controlled games before another season run.

## Limits

- No new multi-season equilibrium or veteran-retention causal claim. Retention
  uses ratings, not a direct PPG threshold; poor box scores alone are not proof
  that this is why an AI team waived someone.
- No assertion that a 61 OFF grade should become any particular higher grade.
- Post/roll frequency, efficiency and screening are different constructs;
  source coverage is incomplete and Edey's latest sample is tiny.
- The source play-type snapshot and cached career totals are evidence inputs,
  not guaranteed perfectly reconciled databases. No rating was assigned from
  either automatically during this audit.
- 42 focused tests passed, including seven new audit-integrity tests. The full
  repository suite was not rerun or certified clean.
