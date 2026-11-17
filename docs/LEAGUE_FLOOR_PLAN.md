# Why the League Floor Rises

## Current Status

The historical plan below predates the V4-V8 changes; its mechanism descriptions
and unimplemented-work statements are not a current code inventory. The latest
completed step is the [V8 rotation-profile comparison](ROTATION_PROFILES_V8_2026_10_26.md):
four disposable two-season careers, with prospect/development rules frozen.
Better incumbent retention and smaller bottom-decile increases appeared in both
paired seeds, but long-run equilibrium remains unproven. Consult that report
before repeating experiments or treating this older plan as pending work.

The subsequent [specialist-impact audit](SPECIALIST_IMPACT_AUDIT_2026_10_27.md)
reuses those careers and fast controlled games. It identifies shot-profile,
bench-scoring, post/roll separation and passing-feature issues; no additional
live ratings or career-development rules were changed. These mechanisms should
be tested before interpreting low veteran box scores as more evidence for
prospect nerfs or broad imported-rating increases.

[V9 offensive roles](OFFENSIVE_ROLES_V9_2026_10_27.md) now repairs shot profiles
and distinguishes post creation, assisted finishing, screening and offensive
rebounding in OFF, simulation and valuation. Overall, prospect/development and
minute-suppression formulas remain unchanged. Existing careers stay pinned.

## Verified Accounting

`scripts/audit_roster_floor.py` uses saved censuses, not another simulation. Every grade uses a fixed 24-minute context and the same fixed display transform. Incumbent development is separated from roster entry/exit. The two contributions reconcile exactly even when roster counts differ. This is endpoint accounting, not a causal experiment: entrants can develop before the endpoint, and intermediate exits/returns are not visible.

The aligned V2 careers start at a 74.95 mean. At October 1, 2028:

| Seed | Mean Increase | Continuing-Player Contribution | Turnover Contribution | Below 70, Start / End |
| --- | ---: | ---: | ---: | ---: |
| 17 | 2.467 | 0.401 | 2.066 | 129 / 58 |
| 29 | 1.887 | 0.371 | 1.515 | 129 / 81 |

Turnover accounts for approximately 84% / 80% of the average increase. Departing players averaged 67.52 / 67.37 at the start; entrants averaged 75.03 / 72.76 at the endpoint. Only three continuing players crossed upward through 70 in each career. Of the below-70 count reduction, most is departures, not mass individual improvement.

The older, unaligned ten-year careers have the same accounting pattern: turnover contributes 5.115 / 5.054 of the 5.311 / 5.203 mean increase. These are not ten-year V2 forecasts. The model/input versions differ and must not be pooled as independent current-version runs.

Rostered generated newcomers in V2 number 111 / 113 out of 120 selections across two drafts at the endpoint. The most recent class has not played its first regular season, so this is not a two-year survival rate for all 120 players. In the older class, 51 / 55 of 60 are rostered after one NBA season. Future analysis must distinguish guaranteed-contract bench retention, actual rotation success, eventual league exits and retirement, rather than force a predetermined number of cuts.

## Mechanisms to Test

1. **Generated weaknesses are too mild.** `draft.py:nba_trait_values_from_prospect` blends many inputs toward shared anchors; `rookie_trait_records` clamps each resulting trait to 25-95. The prior audit observed no converted trait below 31.91 across 900 generated players, versus 343 sub-25 traits among the original starting roster's 6,750 values. Some imported lows are bad data, now partly repaired; some are legitimate specialist limitations. Merely matching the global mean misses both problems. Potential also enters current `ability_anchor` and playoff translation; promise can leak into immediate readiness. These are code mechanisms, not yet measured causal effect sizes.
2. **Broad profiles are rewarded by overall.** `save.py:player_attribute_summary` assigns the same shooting/creation weights across positions and adds a projected-minutes term. It does not directly reward rebounding in overall. A lob center can have valuable simulation features and an unflattering overall; a generic balanced rookie can win the headline comparison. AI has other consumers, including `sim.py:player_impact_score`, asset valuations and retention. Changing display alone cannot establish gameplay balance.
3. **Weak development realization is not a plateau.** `health.py` already has age curves, focus, health drag and outcome variance. But low realization still supplies a positive growth multiplier, role has a positive minimum, and every focus multiplier is positive. For young players, short-injury penalties are capped to avoid reversing growth. These sensible safeguards together warrant testing whether too many marginal skills inevitably improve. The present endpoint results do not justify calling this the dominant cause.
4. **Turnover may favor cheaper generalists too strongly.** Selection, rookie contracts and role-insensitive grades can replace flawed veterans with broadly competent rookies. Some replacement is realistic; an inexhaustible cheap supply of complete rotation players is not. Need same-position, same-role, same-age comparisons and actual rotation/salary outcomes before changing AI retention.

## Recommended Order

### First: More Real Weaknesses, Not Weaker Stars

Run a paired generator/conversion experiment with the top-end potential tail and development rules held fixed. Keep good initial grades for exceptional ready prospects, but vary late-first/second-round readiness more and retain archetype-specific holes: nonshooting centers, scoring guards who cannot defend, defenders who cannot create, skilled players who struggle physically. Test removing potential's contribution to current playoff/readiness traits. Preserve correlated strengths, rather than add independent random noise to every skill.

Match generated and imported cohorts by age, role and selection band, using both skill distributions and simulation features. Preserve rare gems and disappointing high picks. No blanket draft-class nerf, enforced star quota or universal talent minimum.

### Second: Role Value and Trait-Specific Career Arcs

Design a separately versioned role/impact summary, checking every AI consumer before changing it. Do not inflate a center's shooting merely to improve the headline. Then test player/trait-specific saturation and plateau timing, with scarce opportunity, coaching fit and health affecting which skills actually improve. Existing bust/late-breakout variance should be evaluated before adding more random failure.

Review aging/serious-injury recovery separately against age-year performance and participation data. Allow skill retention alongside physical decline. Do not injure or retire productive veterans solely to make a histogram stationary, and do not use catastrophes as a substitute for a realistic replacement-level supply.

### Third: Validate the League, Not Just the Mean

Use matched paired seeds and full-career draft tracking, including waived and never-signed players. Compare years 0/5/10/15/20, not only the initially misaligned transition. Track fixed-context and rotation-weighted performance, age-year counts, bottom/median/top quantiles, role weaknesses, salary/minutes, three-to-five-year draft outcomes and free-agent quality. The goal is plausible turnover and scarcity, not an identical annual count above 90.

Historical draft analysis such as [Berkeley's second-round study](https://sportsanalytics.studentorg.berkeley.edu/articles/trash-or-treasure.html) emphasizes that outcomes depend heavily on the success definition and the observation window. Do not equate getting a roster spot with becoming a rotation player or a star, or convert one study's success rate directly into our bust probability.

## What the Game Loses Otherwise

When too many cheap newcomers have few weaknesses, lineup fit becomes less important, veteran specialists lose value, second-round hits stop feeling rare, and every rebuild starts to resemble buying generic upgrades. The star supply can still be too low at the same time. Flattening the whole distribution downward would make that problem worse. Neither cosmetic reranking nor raising all imported players to the strongest class's mean solves it.

No league-wide generation, development, retirement or retention change is implemented in this pass. The evidence prioritizes the next experiment without mixing it into the four-player correction.
