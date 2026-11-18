# Player growth and aging vs Basketball Index

- **The game starts aging players too late.** Basketball Index shows the strongest gains at 19–22, a broad peak around 23–26, and a clear drop by 27–30. Both rating sets in the game are still flat or improving at 27–30. The typical game player first loses overall rating at 31.
- **The game gives players very similar development years.** For a rotation player, changing the seed barely moves the annual rating around its healthy forecast. Basketball Index sees much wider swings around its forecasts. Some of that gap is season-to-season measurement noise, changing roles and health.
- **Better staff help young players, but the effect gets small fast.** The strongest versus weakest current staff changes a young rotation player's overall growth by about 0.31 points in legacy ratings or 0.14 in the 94-input model, on average. Basketball Index's coach differences include roster and system effects, so I would keep the current coach settings for the first tuning pass.

## 1. When players improve, peak and decline

The table uses players with at least 500 starting-season minutes. Each row shows the median changes in **offense / defense / overall**. Basketball Index and the game use their own units. The full age-by-minutes tables are below.

| Starting age | Basketball Index actual | Basketball Index 2026–27 forecast | Game legacy ratings | Game 94-input ratings |
| --- | --- | --- | --- | --- |
| 19–22 | +0.30 / +0.09 / +0.40 | +0.33 / +0.10 / +0.46 | +1.10 / +0.90 / +1.00 | +0.50 / +0.50 / +0.55 |
| 23–26 | +0.01 / −0.04 / +0.03 | 0.00 / +0.01 / +0.01 | +0.30 / +0.20 / +0.20 | +0.10 / +0.10 / +0.10 |
| 27–30 | −0.14 / −0.06 / −0.15 | −0.16 / −0.04 / −0.16 | +0.10 / 0.00 / +0.10 | +0.10 / +0.10 / +0.10 |
| 31–33 | −0.17 / −0.07 / −0.16 | −0.28 / −0.15 / −0.43 | −0.50 / −0.90 / −0.60 | −0.20 / −0.30 / −0.40 |
| 34–36 | −0.18 / −0.09 / −0.30 | −0.51 / −0.20 / −0.70 | −0.70 / −1.10 / −0.90 | −0.40 / −0.60 / −0.40 |

- **Peak and decline start.** Among players starting with 1,500+ minutes, the observed median offensive change turns negative at 24 and stays negative through 36. Overall is still slightly positive at 25 and turns negative at 26. Defense is near flat at 23–24, then generally negative with a few rebounds in small older samples. The exact peak depends on minutes and which part of the game we measure. The game has a plateau around 30 and a sharp break at 31–32. The result also holds when comparing players in the middle half of the starting-level distribution within each minutes band. At 27–30, their median overall change is −0.16 in Basketball Index and +0.10 in both game modes.
- **Early growth.** Relative to the spread of starting talent, Basketball Index shows much bigger gains for young players, especially on offense. In the 1,500+ band at 19–22, the overall median gain is 26% of the distance between the 25th and 75th percentiles of starting talent. The game gives 10% in legacy and 6% in inputs. At 0–499 minutes, Basketball Index early gains are smaller and less consistent, so the rotation result favors an increase tied to opportunity and existing room to improve.
- **Decline speed.** In that same high-minute band at 34–36, observed overall loss is 19% of the starting spread per year, versus 7% legacy and 3% inputs. The 2026–27 Basketball Index forecasts are steeper still at 39%, from 12 players with 500+ minutes and fewer in this band. Use this as a sensitivity check. Historically, offense declines more than defense relative to its starting spread. In the game, defense often loses more raw card points, and at 34–36 the two sides lose a similar share of their starting spread. The −0.12 monthly floor also compresses late physical losses.
- **Role checks.** Keeping transitions with the same recorded role leaves the broad pattern intact. Median overall changes are +0.39 at 19–22, +0.02 at 23–26, −0.12 at 27–30, −0.11 at 31–33 and −0.35 at 34–36. Restricting the offense series to the same player-seasons that have overall data still gives +0.33 at 19–22, −0.11 at 27–30 and −0.33 at 34–36.

### How the comparison works

- **Basketball Index.** Start with each player's actual score. Subtract it from the following season's actual or retrospective forecast for the same metric. Keep consecutive seasons with an age increase of one. Use starting-season minutes from the 3-point talent history for all three metrics, so the composite possession counts never stand in for minutes. The source scores are expected offensive and defensive LEBRON, Basketball Index's impact-based talent scores, and its dedicated overall talent series. Defense and overall have substantially thinner historical coverage than offense. Ages 19–36 contain 4,166 offense transitions and 2,091 each for defense and overall. The forward check uses the captured 2025–26 projection baselines and one-year forecasts. Across the five age groups in the main table, the historical retrospective model predicts overall changes of +0.65, +0.18, −0.21, −0.32 and −0.48.
- **Game.** Run `expected_rating_changes` for 12 months on the canonical 2026–27 roster, starting in October 2026 with seed 1, current team staff and healthy players. There are 671 rostered players ages 19–36, with 167 / 219 / 285 in the three minutes bands. Use projected minutes per game × 82 to approximate the same opportunity bands. Apply the returned changes to the underlying ratings and recalculate the offense, defense and overall card scores at fixed minutes. In inputs mode this routes through the 94 inputs and re-derives traits, using the baseline impact mapping. Overall matched `expected_overall_change` for every player in both modes. This helper increments age by a month on each step and applies the input routing at the end. The monthly live path uses the save's season age, a minimum change threshold and month-by-month routing, which can yield different values.
- **Similar players.** The main comparison groups players by opening workload, and the starting-level check keeps the 25th–75th percentile of each side's starting talent within each workload and dataset. It matches relative level. The starting-spread percentages above divide each dataset's median change by its own starting interquartile range in that band across ages 19–36. This is a scale check, with no assumption that one card point equals a fixed amount of NBA impact. The legacy defense ratings in the 0–499 band have a zero starting interquartile range, so that band has no defensible ratio.
- **Coverage.** Each historical transition counts once. Basketball Index's methodology says its skill models were trained with a 500-minute minimum, so treat the lower band as descriptive. Players who leave the league or have no following score are absent. The oldest cells are small and survivor-heavy. Current engine ages and prospective minutes may differ from Basketball Index's season ages and realized minutes. The ages refer to broad peak windows, with no single peak age inferred from this sample.

## 2. How much players vary

These are central bands around each source's forecast. Basketball Index uses actual minus its one-year retrospective forecast. The game uses a seeded monthly replay minus the same player's replay with random shocks turned off. The main comparison uses 500+ minutes. The 50%, 80% and 90% bands are the 25th–75th, 10th–90th and 5th–95th percentile ranges.

| Source | Side | N | Median | Middle 50% | Middle 80% | Middle 90% |
| --- | --- | ---: | ---: | --- | --- | --- |
| Basketball Index | Offense | 3,246 | +0.01 | −0.40 to +0.40 | −0.77 to +0.79 | −1.05 to +1.05 |
| Basketball Index | Defense | 1,796 | −0.12 | −0.40 to +0.17 | −0.68 to +0.43 | −0.86 to +0.58 |
| Basketball Index | Overall | 1,796 | −0.09 | −0.62 to +0.38 | −1.11 to +0.84 | −1.47 to +1.14 |
| Game legacy | Offense | 1,632 | 0.00 | 0.00 to 0.00 | 0.00 to +0.10 | −0.10 to +0.10 |
| Game legacy | Defense | 1,632 | 0.00 | 0.00 to 0.00 | 0.00 to +0.10 | −0.10 to +0.10 |
| Game legacy | Overall | 1,632 | 0.00 | 0.00 to 0.00 | 0.00 to +0.10 | 0.00 to +0.10 |
| Game 94 inputs | Offense | 1,632 | 0.00 | 0.00 to 0.00 | 0.00 to 0.00 | 0.00 to +0.10 |
| Game 94 inputs | Defense | 1,632 | 0.00 | 0.00 to 0.00 | 0.00 to 0.00 | 0.00 to +0.10 |
| Game 94 inputs | Overall | 1,632 | 0.00 | 0.00 to 0.00 | 0.00 to 0.00 | 0.00 to +0.10 |

The source's published overall forecast intervals are 1.02, 2.00 and 2.68 units wide at 50%, 80% and 90%. The observed errors are almost as wide at 1.00, 1.95 and 2.61. Actual overall changes, before subtracting the forecast, have a median of +0.06 and ranges of −0.56 to +0.68, −1.13 to +1.28 and −1.51 to +1.59. In the game, pooled actual overall changes have a wider middle 80% than the seed effects, at −0.80 to +1.40 legacy and −0.40 to +0.70 inputs. That total spread mixes different ages and different starting players.

Even when comparing just 1,500+ minute players, the middle 80% of the overall forecast error spans 98% of Basketball Index's starting talent spread. The game spans about 0.8% of its starting spread in legacy, and both displayed endpoints round to zero in inputs. The game has month-to-month randomness in each hidden rating (a standard deviation of `0.012 + 0.012 × focus`), but the mostly independent draws average out across months and traits. The 0.015 event threshold and tenth-point card display also affect what shows up in these bands. Basketball Index's wider bands include model error, changing opportunities, health and performance measurement. Copying the whole spread into permanent skill would likely overstate true development.

The replays used 12 seeds, each with a paired no-noise run on the same 182 players, 136 of them at 500+ minutes. The sample takes up to four players per age and minutes cell. It holds season age, team, minutes and health fixed, and uses `advance_development` plus the normal monthly rating writeback, including eligibility, the event threshold and caps. The count in the table is player-seed pairs for the game and real transitions for Basketball Index. As a check on the difference between the two game methods, the monthly no-noise runs also have a median overall change of 0.00 in both modes at 27–30.

## 3. How much coaches and staff matter

Basketball Index groups players' actual minus predicted talent by head coach. The middle 80% gives the range from the lower tenth of coaches to the upper tenth. The main comparison requires at least three team seasons per coach. All 56 are included in the source file.

| Basketball Index coach sample | Coaches | Side | Median | Middle 80% | Lowest to highest |
| --- | ---: | --- | ---: | --- | --- |
| All | 56 | Offense | −0.08 | −0.22 to +0.12 | −0.38 to +0.24 |
| All | 56 | Defense | −0.09 | −0.32 to +0.13 | −0.48 to +0.27 |
| All | 56 | Overall | −0.18 | −0.50 to +0.23 | −0.60 to +0.69 |
| 3+ team seasons | 37 | Offense | −0.07 | −0.16 to +0.08 | −0.25 to +0.19 |
| 3+ team seasons | 37 | Defense | −0.06 | −0.23 to +0.08 | −0.35 to +0.20 |
| 3+ team seasons | 37 | Overall | −0.12 | −0.40 to +0.20 | −0.51 to +0.30 |
| 5+ team seasons | 19 | Overall | −0.10 | −0.28 to +0.19 | −0.39 to +0.25 |

In the 3+ sample, the lowest and highest overall results are Brett Brown (−0.508, four seasons) and Monty Williams (+0.297, three seasons). With five seasons minimum they are Tom Thibodeau (−0.385, seven seasons) and Mike Budenholzer (+0.251, seven seasons). These are results under each coach's system. Team composition, role changes, substitutions, health and forecast bias can all affect the totals. The negative median is one reason to use the spread around the cohort median when looking at differences across coaches.

The game counterfactual holds each player's ratings, seed, minutes and team context fixed. Swap in the weakest or strongest current development staff settings and compare against neutral staff at 60 and a 3.0 head coach. The combined growth multiplier runs from 0.904 to 1.255 across those two staff profiles. For the coach-only column, keep staff neutral and compare the actual head coach grade endpoints of 3.0 and 4.8. The head coach coefficient is 0.08 per grade point, so the endpoints change the growth multiplier by 14.4 percentage points before any limits.

| Starting age, 500+ minutes | Legacy weak / strong staff vs neutral | 94-input weak / strong staff vs neutral | Legacy coach-only span | 94-input coach-only span |
| --- | --- | --- | ---: | ---: |
| 19–22 | −0.09 / +0.22 | −0.04 / +0.10 | +0.13 | +0.06 |
| 23–26 | −0.02 / +0.07 | −0.01 / +0.04 | +0.04 | +0.03 |
| 27–36 | <0.01 / +0.01 | <0.01 / <0.01 | +0.01 | <0.01 |

These are mean differences in annual overall card points, so the table picks up effects that would round to zero for a typical player. At 19–22, the weak-to-strong comparison moves the mean hidden rating by about 0.33 points in both rating sets. On the card, the average offense / defense spans are 0.36 / 0.27 points in legacy and 0.13 / 0.16 in inputs. The smaller inputs effect on the card comes after the underlying development step. The game scales the growth part of the formula, so staff have very little effect on the late-career aging penalties.

**Is it realistic?** The game is conservative. The full staff span for young rotation players is about 1–2% of a typical high-minute starting overall rating spread. The 3+ season Basketball Index coach band spans about 30% of the high-minute starting overall talent spread. Those scales put the observed association in context, but the samples and interventions differ. The Basketball Index number gives room for a larger effect. It cannot tell us how much of that effect a coaching hire should produce. I would keep the current coefficients for now, including the 0.08 head coach coefficient, and check staff again once the underlying growth curve is stronger.

## 4. Parameter changes to try

I ran two separate in-memory trials. The age trial reran healthy forecasts for every player with at least 500 projected minutes. The variability trial used the same 136 sampled rotation players with six seeds, over a single July–June cycle. Neither trial changed game files.

| Area | Change to try | Expected effect |
| --- | --- | --- |
| Young growth in `monthly_trait_delta` | Raise the base growth coefficient from **0.20 to 0.30** through age 22. Taper linearly to **0.20** at 24. Apply the higher coefficient to the existing growth term and keep the current minutes, focus, upside and ceiling rules. | At 19–22, median overall growth moves from **+1.00 to +1.40** in legacy and **+0.55 to +0.70** in inputs in the age trial. Median inputs offense rises **+0.50 to +0.70**. This closes part of the youth gap without raising starting ratings. |
| Onset and slope of decline | Replace the physical cliff at 31 with monthly loss of **0.014 × years past 27 + 0.009 × years past 32**, capped at **0.16**. For release, range, shot versatility, handle and offensive rebounding, use **0.011 × years past 25.5** with the existing **0.09** cap. For other ratings that already take the general age penalty, ramp that penalty from **30.25** at **0.013 per year**, with the same 0.09 cap. Keep passing reads, scheme knowledge and portability exempt from the general penalty. Allow losses down to **−0.18 per month** instead of −0.12. | The 27–30 median overall changes from **+0.10 to −0.20** legacy and **+0.10 to −0.10** inputs. At 34–36 it goes from **−0.90 to −1.20** legacy and **−0.40 to −0.50** inputs. The older inputs effect remains small. Check the underlying athletic ratings and what the engine actually reads before increasing late-career penalties further. |
| Make earlier decline reach low-minute veterans | Allow an aging event for players ages 27–30 regardless of minutes or rotation priority. Today the 16-minute rule and priority exception skip **49 of 148** players ages 27–30, including **28** in the 500+ projected minutes sample. Let those players receive the proposed aging component. | An earlier age curve can reach fringe veterans as well as regulars. The age forecast already evaluates everyone. This eligibility change needs a live-month check before applying the forecast estimates to those players. |
| Player-to-player variation | Keep the monthly per-trait noise. Add a player-season draw shared across ratings, keyed by save seed, player and season. Start with a standard-normal draw limited to **±2**, contributing **0.075 rating points per month per developable rating** before existing floors and ceilings. Keep the draw out of the expected forecast. | In the isolated variability trial, the middle 80% of overall deviations widened to **−0.85 to +1.00** legacy and **−0.50 to +0.60** inputs. The median stayed **0.00** in both modes. This gives players noticeably different years while staying well inside the relative spread of measured NBA performance. |
| Head coach and staff | Keep the **0.08** coach coefficient, staff coefficients **0.006 / 0.003 / 0.004**, and multiplier limits for this pass. | An earlier aging curve and faster young growth already change where staff are most visible. Recheck the staff swap after implementing the growth curve before assigning a larger causal effect to a hire. |

The pilots are separate, so the report gives no combined-effect estimate. Before enabling a change, run healthy and normal-injury seeded careers, check young-player growth and veteran decline by minutes and starting level over multiple seasons, and verify that the outlook and monthly writeback tell the same story. Check both repository scorecards on aged rosters, since an opening-day replay cannot detect changes that only accumulate after development runs.

## 5. Full age-by-minutes tables

Each cell is **median [25th, 75th percentile] (count)**. A single observation shows just the change and count. **—** means zero observations. Treat small cells, especially counts below 10, as examples. Ages are the starting ages, so age 19 is the change from 19 to 20.

### Basketball Index actual one-year changes

The units are Basketball Index talent points. Each count is a consecutive player-season transition with both actual scores available.

### 0–499 starting-season minutes

| Starting age | Offense | Defense | Overall |
| --- | --- | --- | --- |
| 19 | -0.16 [-0.48, +0.19] (27) | -0.08 [-0.58, +0.23] (10) | -0.26 [-0.75, +0.28] (10) |
| 20 | +0.08 [-0.27, +0.60] (81) | +0.23 [+0.05, +0.72] (40) | +0.63 [-0.04, +1.02] (40) |
| 21 | -0.04 [-0.44, +0.41] (96) | +0.20 [-0.09, +0.45] (34) | +0.22 [-0.21, +0.84] (34) |
| 22 | +0.04 [-0.41, +0.44] (121) | +0.14 [-0.17, +0.45] (31) | +0.43 [-0.02, +1.06] (31) |
| 23 | +0.08 [-0.32, +0.59] (148) | +0.03 [-0.10, +0.31] (50) | +0.28 [-0.49, +1.12] (50) |
| 24 | +0.12 [-0.28, +0.58] (132) | +0.04 [-0.26, +0.19] (48) | +0.04 [-0.40, +0.60] (48) |
| 25 | +0.03 [-0.35, +0.39] (83) | -0.12 [-0.51, +0.41] (26) | +0.18 [-0.20, +0.57] (26) |
| 26 | +0.00 [-0.47, +0.31] (53) | +0.01 [-0.29, +0.37] (21) | +0.22 [-0.03, +0.54] (21) |
| 27 | +0.21 [-0.37, +0.67] (31) | +0.14 [-0.42, +0.43] (12) | -0.18 [-0.41, +0.51] (12) |
| 28 | +0.07 [-0.20, +0.41] (29) | -0.10 [-0.29, +0.00] (6) | +0.06 [-0.29, +0.56] (6) |
| 29 | +0.02 [-0.40, +0.56] (31) | -0.17 [-0.31, -0.09] (3) | +0.00 [-0.08, +0.23] (3) |
| 30 | -0.16 [-0.38, +0.21] (17) | +0.06 [-0.21, +0.33] (5) | -0.42 [-0.72, +0.29] (5) |
| 31 | +0.23 [+0.12, +0.63] (7) | -0.26 [-0.26, -0.25] (2) | +2.31 [+1.44, +3.17] (2) |
| 32 | -0.32 [-0.65, +0.05] (15) | -0.38 [-0.51, -0.24] (2) | -0.90 [-1.16, -0.64] (2) |
| 33 | +0.18 [-0.30, +0.35] (12) | +0.14 [-0.18, +0.47] (2) | +0.44 [+0.14, +0.74] (2) |
| 34 | +0.62 [+0.20, +0.78] (7) | — | — |
| 35 | +0.32 [-0.10, +0.50] (10) | +0.64 (1) | +0.40 (1) |
| 36 | -0.03 [-0.13, +0.35] (6) | -0.15 [-0.36, +0.05] (2) | +0.18 [+0.15, +0.22] (2) |

### 500–1,499 starting-season minutes

| Starting age | Offense | Defense | Overall |
| --- | --- | --- | --- |
| 19 | +0.33 [-0.18, +0.61] (42) | +0.17 [-0.14, +0.38] (27) | +0.46 [-0.31, +1.04] (27) |
| 20 | +0.37 [-0.15, +0.67] (85) | +0.06 [-0.26, +0.31] (56) | +0.38 [-0.23, +0.93] (56) |
| 21 | +0.25 [-0.29, +0.61] (126) | +0.03 [-0.28, +0.29] (79) | +0.16 [-0.34, +0.73] (79) |
| 22 | +0.17 [-0.36, +0.55] (145) | +0.05 [-0.38, +0.37] (89) | +0.08 [-0.45, +0.72] (89) |
| 23 | +0.02 [-0.44, +0.46] (148) | +0.01 [-0.47, +0.29] (83) | -0.06 [-0.75, +0.48] (83) |
| 24 | +0.11 [-0.32, +0.54] (152) | +0.00 [-0.18, +0.31] (76) | +0.38 [-0.21, +0.86] (76) |
| 25 | +0.02 [-0.39, +0.48] (142) | +0.00 [-0.40, +0.32] (61) | +0.10 [-0.42, +0.65] (61) |
| 26 | +0.09 [-0.33, +0.56] (113) | -0.12 [-0.40, +0.10] (41) | -0.09 [-0.44, +0.42] (41) |
| 27 | -0.13 [-0.41, +0.41] (112) | -0.04 [-0.33, +0.20] (41) | +0.01 [-0.48, +0.55] (41) |
| 28 | +0.00 [-0.47, +0.50] (102) | -0.14 [-0.39, +0.30] (39) | +0.33 [-0.44, +0.77] (39) |
| 29 | +0.00 [-0.58, +0.53] (81) | -0.13 [-0.43, +0.34] (26) | -0.24 [-0.98, +0.43] (26) |
| 30 | -0.24 [-0.54, +0.13] (70) | -0.25 [-0.66, +0.10] (17) | -0.10 [-1.33, +0.00] (17) |
| 31 | +0.04 [-0.41, +0.38] (67) | -0.20 [-0.47, +0.20] (19) | +0.05 [-0.64, +0.23] (19) |
| 32 | -0.11 [-0.58, +0.42] (54) | -0.07 [-0.19, +0.10] (17) | -0.29 [-0.52, +0.30] (17) |
| 33 | -0.29 [-0.89, +0.25] (41) | -0.23 [-0.37, -0.02] (12) | -0.32 [-0.58, +0.43] (12) |
| 34 | -0.15 [-0.69, +0.29] (29) | +0.29 [-0.67, +0.45] (7) | +0.53 [+0.16, +0.99] (7) |
| 35 | -0.12 [-0.62, +0.49] (21) | -0.13 [-0.28, -0.10] (3) | -0.40 [-0.85, +0.07] (3) |
| 36 | +0.15 [-0.49, +0.43] (11) | -0.07 [-0.07, -0.03] (5) | -0.41 [-0.99, +0.36] (5) |

### 1,500+ starting-season minutes

| Starting age | Offense | Defense | Overall |
| --- | --- | --- | --- |
| 19 | +0.59 [+0.23, +0.88] (30) | +0.13 [+0.03, +0.32] (23) | +0.96 [+0.25, +1.20] (23) |
| 20 | +0.44 [-0.05, +0.99] (74) | +0.17 [-0.23, +0.44] (61) | +0.67 [+0.22, +1.08] (61) |
| 21 | +0.43 [-0.07, +0.89] (98) | +0.15 [-0.20, +0.41] (83) | +0.64 [+0.10, +1.07] (83) |
| 22 | +0.17 [-0.27, +0.76] (115) | +0.03 [-0.27, +0.37] (98) | +0.29 [-0.36, +0.86] (98) |
| 23 | +0.04 [-0.43, +0.44] (150) | -0.01 [-0.27, +0.25] (113) | +0.04 [-0.51, +0.71] (113) |
| 24 | -0.06 [-0.51, +0.51] (155) | +0.00 [-0.34, +0.31] (112) | +0.05 [-0.61, +0.69] (112) |
| 25 | -0.06 [-0.47, +0.44] (158) | -0.08 [-0.30, +0.23] (111) | +0.08 [-0.49, +0.51] (111) |
| 26 | -0.11 [-0.55, +0.38] (164) | -0.06 [-0.42, +0.23] (99) | -0.15 [-0.71, +0.38] (99) |
| 27 | -0.09 [-0.59, +0.27] (155) | -0.05 [-0.29, +0.29] (86) | -0.09 [-0.70, +0.52] (86) |
| 28 | -0.11 [-0.63, +0.45] (131) | -0.06 [-0.32, +0.17] (71) | -0.19 [-0.86, +0.29] (71) |
| 29 | -0.29 [-0.79, +0.30] (119) | -0.11 [-0.34, +0.14] (63) | -0.37 [-0.83, +0.06] (63) |
| 30 | -0.23 [-0.65, +0.28] (108) | -0.01 [-0.34, +0.25] (50) | -0.29 [-0.75, +0.55] (50) |
| 31 | -0.33 [-0.72, +0.20] (84) | -0.12 [-0.35, +0.25] (37) | -0.24 [-1.05, +0.38] (37) |
| 32 | -0.10 [-0.89, +0.29] (61) | -0.01 [-0.30, +0.19] (29) | -0.10 [-0.91, +0.45] (29) |
| 33 | -0.46 [-0.76, -0.07] (41) | +0.19 [-0.24, +0.43] (19) | -0.12 [-0.93, +0.38] (19) |
| 34 | -0.54 [-0.81, -0.10] (33) | -0.21 [-0.61, +0.02] (19) | -0.85 [-1.24, -0.27] (19) |
| 35 | -0.18 [-0.71, +0.13] (27) | +0.09 [-0.38, +0.18] (15) | +0.01 [-0.26, +0.19] (15) |
| 36 | -0.35 [-0.72, -0.09] (16) | -0.14 [-0.40, +0.00] (9) | -0.81 [-1.01, -0.22] (9) |

### Game expected 12-month changes

The units are game card points. Each count is a current roster player projected for 12 months with no monthly noise. Legacy is the default set. The inputs columns use the 94-input set.

### 0–499 projected season minutes

| Starting age | Legacy offense | Legacy defense | Legacy overall | Inputs offense | Inputs defense | Inputs overall |
| --- | --- | --- | --- | --- | --- | --- |
| 19 | +0.20 (1) | +0.10 (1) | +0.20 (1) | +0.30 (1) | +0.00 (1) | +0.30 (1) |
| 20 | +0.10 [+0.10, +0.15] (3) | +0.20 [+0.15, +0.20] (3) | +0.10 [+0.10, +0.10] (3) | +0.10 [+0.05, +0.15] (3) | +0.10 [+0.05, +0.15] (3) | +0.20 [+0.15, +0.30] (3) |
| 21 | +0.10 [+0.10, +0.15] (7) | +0.10 [+0.10, +0.15] (7) | +0.10 [+0.10, +0.20] (7) | +0.20 [+0.15, +0.45] (7) | +0.30 [+0.15, +0.50] (7) | +0.30 [+0.15, +0.55] (7) |
| 22 | +0.15 [+0.10, +0.20] (20) | +0.10 [+0.10, +0.10] (20) | +0.10 [+0.10, +0.20] (20) | +0.20 [+0.10, +0.30] (20) | +0.25 [+0.10, +0.53] (20) | +0.25 [+0.07, +0.33] (20) |
| 23 | +0.10 [+0.00, +0.10] (39) | +0.00 [+0.00, +0.10] (39) | +0.10 [+0.00, +0.10] (39) | +0.20 [+0.00, +0.30] (39) | +0.20 [+0.05, +0.45] (39) | +0.20 [+0.10, +0.40] (39) |
| 24 | +0.10 [+0.00, +0.10] (32) | +0.00 [+0.00, +0.10] (32) | +0.00 [+0.00, +0.10] (32) | +0.10 [+0.00, +0.30] (32) | +0.20 [+0.10, +0.30] (32) | +0.15 [+0.10, +0.30] (32) |
| 25 | +0.10 [+0.00, +0.10] (24) | +0.00 [+0.00, +0.03] (24) | +0.10 [+0.00, +0.10] (24) | +0.20 [+0.00, +0.30] (24) | +0.20 [+0.10, +0.30] (24) | +0.15 [+0.10, +0.42] (24) |
| 26 | +0.00 [+0.00, +0.00] (16) | +0.00 [+0.00, +0.00] (16) | +0.00 [+0.00, +0.00] (16) | +0.10 [+0.00, +0.10] (16) | +0.10 [+0.00, +0.20] (16) | +0.00 [+0.00, +0.25] (16) |
| 27 | +0.00 [+0.00, +0.00] (9) | +0.00 [+0.00, +0.00] (9) | +0.00 [+0.00, +0.00] (9) | +0.10 [+0.00, +0.40] (9) | +0.10 [+0.00, +0.20] (9) | +0.10 [+0.10, +0.50] (9) |
| 28 | +0.00 [+0.00, +0.00] (4) | +0.00 [+0.00, +0.00] (4) | +0.00 [+0.00, +0.00] (4) | +0.20 [+0.15, +0.27] (4) | +0.15 [+0.00, +0.35] (4) | +0.20 [+0.00, +0.40] (4) |
| 29 | +0.00 [+0.00, +0.00] (2) | +0.00 [+0.00, +0.00] (2) | +0.00 [+0.00, +0.00] (2) | +0.20 [+0.15, +0.25] (2) | +0.20 [+0.10, +0.30] (2) | +0.15 [+0.07, +0.22] (2) |
| 30 | +0.00 [+0.00, +0.00] (6) | -0.05 [-0.10, +0.00] (6) | +0.00 [+0.00, +0.00] (6) | +0.00 [+0.00, +0.00] (6) | -0.10 [-0.10, -0.03] (6) | +0.00 [-0.08, +0.00] (6) |
| 31 | -0.20 (1) | -0.40 (1) | -0.30 (1) | -0.40 (1) | -0.30 (1) | -0.40 (1) |
| 32 | -0.50 (1) | -0.90 (1) | -0.70 (1) | +0.00 (1) | -0.80 (1) | -0.50 (1) |
| 33 | -0.60 [-0.60, -0.60] (2) | -1.00 [-1.00, -1.00] (2) | -0.75 [-0.78, -0.73] (2) | -1.10 [-1.55, -0.65] (2) | -0.30 [-0.35, -0.25] (2) | -1.20 [-1.70, -0.70] (2) |
| 34 | — | — | — | — | — | — |
| 35 | — | — | — | — | — | — |
| 36 | — | — | — | — | — | — |

### 500–1,499 projected season minutes

| Starting age | Legacy offense | Legacy defense | Legacy overall | Inputs offense | Inputs defense | Inputs overall |
| --- | --- | --- | --- | --- | --- | --- |
| 19 | +1.90 [+1.20, +2.00] (9) | +1.40 [+1.00, +2.20] (9) | +1.70 [+1.10, +2.00] (9) | +0.70 [+0.40, +1.10] (9) | +0.70 [+0.60, +1.30] (9) | +0.80 [+0.70, +1.20] (9) |
| 20 | +1.00 [+0.65, +1.50] (15) | +0.90 [+0.40, +1.55] (15) | +0.90 [+0.45, +1.45] (15) | +0.40 [+0.20, +0.65] (15) | +0.40 [+0.25, +0.65] (15) | +0.50 [+0.25, +1.15] (15) |
| 21 | +0.70 [+0.60, +1.10] (15) | +0.60 [+0.50, +0.90] (15) | +0.60 [+0.55, +0.95] (15) | +0.50 [+0.25, +0.75] (15) | +0.30 [+0.20, +0.55] (15) | +0.30 [+0.20, +0.60] (15) |
| 22 | +0.70 [+0.30, +0.80] (21) | +0.60 [+0.20, +0.80] (21) | +0.70 [+0.20, +0.80] (21) | +0.30 [+0.20, +0.50] (21) | +0.30 [+0.20, +0.40] (21) | +0.30 [+0.20, +0.50] (21) |
| 23 | +0.30 [+0.20, +0.40] (22) | +0.25 [+0.20, +0.40] (22) | +0.30 [+0.20, +0.40] (22) | +0.20 [+0.10, +0.40] (22) | +0.20 [+0.10, +0.40] (22) | +0.10 [+0.10, +0.27] (22) |
| 24 | +0.20 [+0.10, +0.30] (27) | +0.20 [+0.10, +0.30] (27) | +0.20 [+0.10, +0.30] (27) | +0.10 [+0.05, +0.20] (27) | +0.20 [+0.10, +0.30] (27) | +0.10 [+0.05, +0.30] (27) |
| 25 | +0.20 [+0.10, +0.30] (26) | +0.20 [+0.20, +0.30] (26) | +0.20 [+0.12, +0.30] (26) | +0.10 [+0.10, +0.27] (26) | +0.10 [+0.10, +0.20] (26) | +0.10 [+0.10, +0.27] (26) |
| 26 | +0.00 [+0.00, +0.10] (22) | +0.05 [+0.00, +0.10] (22) | +0.00 [+0.00, +0.00] (22) | +0.10 [+0.00, +0.10] (22) | +0.00 [+0.00, +0.10] (22) | +0.05 [+0.00, +0.10] (22) |
| 27 | +0.00 [+0.00, +0.05] (11) | +0.00 [+0.00, +0.10] (11) | +0.00 [+0.00, +0.10] (11) | +0.00 [+0.00, +0.25] (11) | +0.00 [+0.00, +0.10] (11) | +0.10 [+0.05, +0.10] (11) |
| 28 | +0.00 [+0.00, +0.10] (8) | +0.10 [+0.00, +0.10] (8) | +0.00 [+0.00, +0.03] (8) | +0.10 [+0.10, +0.20] (8) | +0.10 [+0.10, +0.18] (8) | +0.05 [+0.00, +0.13] (8) |
| 29 | +0.00 [+0.00, +0.05] (11) | +0.00 [+0.00, +0.10] (11) | +0.10 [+0.00, +0.10] (11) | +0.10 [+0.00, +0.10] (11) | +0.00 [+0.00, +0.10] (11) | +0.00 [+0.00, +0.10] (11) |
| 30 | +0.00 [+0.00, +0.00] (8) | +0.00 [+0.00, +0.00] (8) | +0.00 [+0.00, +0.00] (8) | +0.00 [+0.00, +0.10] (8) | +0.00 [+0.00, +0.00] (8) | +0.00 [+0.00, +0.00] (8) |
| 31 | -0.15 [-0.20, -0.10] (6) | -0.40 [-0.40, -0.40] (6) | -0.30 [-0.30, -0.22] (6) | -0.10 [-0.10, -0.03] (6) | -0.20 [-0.27, -0.05] (6) | -0.10 [-0.17, -0.10] (6) |
| 32 | -0.50 (1) | -0.80 (1) | -0.60 (1) | -0.10 (1) | -1.80 (1) | -0.40 (1) |
| 33 | -0.60 [-0.60, -0.60] (9) | -1.00 [-1.00, -0.90] (9) | -0.70 [-0.70, -0.70] (9) | -0.40 [-0.70, -0.30] (9) | -0.50 [-0.70, -0.40] (9) | -0.40 [-0.70, -0.30] (9) |
| 34 | -0.60 [-0.60, -0.60] (5) | -1.10 [-1.10, -1.10] (5) | -0.80 [-0.80, -0.80] (5) | -0.80 [-0.80, -0.50] (5) | -0.60 [-1.10, -0.50] (5) | -0.60 [-0.90, -0.40] (5) |
| 35 | -0.70 [-0.70, -0.70] (3) | -1.10 [-1.15, -1.10] (3) | -1.00 [-1.00, -0.95] (3) | -0.40 [-0.95, -0.35] (3) | -0.20 [-0.45, -0.20] (3) | -0.30 [-0.35, -0.25] (3) |
| 36 | — | — | — | — | — | — |

### 1,500+ projected season minutes

| Starting age | Legacy offense | Legacy defense | Legacy overall | Inputs offense | Inputs defense | Inputs overall |
| --- | --- | --- | --- | --- | --- | --- |
| 19 | +2.55 [+2.28, +2.83] (6) | +2.60 [+2.28, +2.85] (6) | +2.40 [+2.23, +2.58] (6) | +0.95 [+0.75, +1.15] (6) | +1.50 [+1.20, +1.65] (6) | +1.50 [+0.90, +1.80] (6) |
| 20 | +1.70 [+1.50, +1.80] (7) | +1.50 [+1.30, +1.55] (7) | +1.50 [+1.45, +1.60] (7) | +0.70 [+0.50, +1.00] (7) | +0.90 [+0.50, +1.25] (7) | +0.90 [+0.75, +1.25] (7) |
| 21 | +1.35 [+1.10, +1.47] (14) | +0.95 [+0.73, +1.10] (14) | +1.15 [+1.00, +1.40] (14) | +0.60 [+0.33, +0.80] (14) | +0.50 [+0.30, +0.60] (14) | +0.75 [+0.50, +0.98] (14) |
| 22 | +1.10 [+1.00, +1.40] (19) | +0.90 [+0.55, +1.10] (19) | +1.00 [+0.90, +1.25] (19) | +0.50 [+0.25, +0.75] (19) | +0.60 [+0.35, +0.80] (19) | +0.60 [+0.30, +0.70] (19) |
| 23 | +0.50 [+0.40, +0.70] (21) | +0.40 [+0.30, +0.50] (21) | +0.50 [+0.40, +0.50] (21) | +0.10 [+0.10, +0.30] (21) | +0.30 [+0.20, +0.40] (21) | +0.20 [+0.10, +0.50] (21) |
| 24 | +0.35 [+0.30, +0.50] (24) | +0.30 [+0.20, +0.40] (24) | +0.35 [+0.30, +0.50] (24) | +0.20 [+0.10, +0.30] (24) | +0.20 [+0.10, +0.45] (24) | +0.20 [+0.10, +0.30] (24) |
| 25 | +0.40 [+0.30, +0.50] (30) | +0.30 [+0.20, +0.40] (30) | +0.35 [+0.20, +0.40] (30) | +0.20 [+0.02, +0.30] (30) | +0.10 [+0.10, +0.27] (30) | +0.20 [+0.20, +0.40] (30) |
| 26 | +0.10 [+0.10, +0.10] (25) | +0.10 [+0.00, +0.10] (25) | +0.10 [+0.00, +0.10] (25) | +0.10 [+0.00, +0.20] (25) | +0.10 [+0.00, +0.20] (25) | +0.10 [+0.00, +0.10] (25) |
| 27 | +0.10 [+0.10, +0.10] (25) | +0.10 [+0.00, +0.10] (25) | +0.10 [+0.00, +0.10] (25) | +0.10 [+0.00, +0.10] (25) | +0.10 [+0.00, +0.20] (25) | +0.20 [+0.10, +0.20] (25) |
| 28 | +0.10 [+0.00, +0.10] (31) | +0.10 [+0.00, +0.10] (31) | +0.10 [+0.10, +0.10] (31) | +0.10 [+0.00, +0.10] (31) | +0.10 [+0.00, +0.10] (31) | +0.10 [+0.00, +0.10] (31) |
| 29 | +0.10 [+0.10, +0.10] (18) | +0.10 [+0.00, +0.10] (18) | +0.10 [+0.10, +0.10] (18) | +0.10 [+0.00, +0.10] (18) | +0.10 [+0.00, +0.10] (18) | +0.10 [+0.00, +0.10] (18) |
| 30 | +0.00 [+0.00, +0.00] (15) | +0.00 [+0.00, +0.00] (15) | +0.00 [+0.00, +0.00] (15) | +0.00 [+0.00, +0.10] (15) | +0.10 [+0.00, +0.10] (15) | +0.00 [+0.00, +0.15] (15) |
| 31 | -0.20 [-0.20, -0.20] (13) | -0.30 [-0.40, -0.30] (13) | -0.30 [-0.30, -0.20] (13) | -0.10 [-0.10, -0.10] (13) | -0.20 [-0.30, -0.10] (13) | -0.20 [-0.30, -0.10] (13) |
| 32 | -0.50 [-0.53, -0.50] (12) | -0.90 [-0.90, -0.80] (12) | -0.65 [-0.70, -0.60] (12) | -0.30 [-0.43, -0.20] (12) | -0.30 [-0.50, -0.20] (12) | -0.45 [-0.75, -0.30] (12) |
| 33 | -0.60 [-0.60, -0.60] (10) | -0.95 [-1.00, -0.90] (10) | -0.70 [-0.70, -0.70] (10) | -0.30 [-0.47, -0.20] (10) | -0.55 [-0.80, -0.40] (10) | -0.50 [-0.75, -0.32] (10) |
| 34 | -0.70 [-0.70, -0.70] (6) | -1.00 [-1.00, -1.00] (6) | -0.80 [-0.80, -0.80] (6) | -0.35 [-0.55, -0.23] (6) | -0.60 [-0.75, -0.45] (6) | -0.30 [-0.37, -0.15] (6) |
| 35 | -0.75 [-0.80, -0.70] (4) | -1.10 [-1.12, -1.08] (4) | -0.90 [-0.90, -0.90] (4) | -0.30 [-0.38, -0.25] (4) | -0.30 [-0.60, -0.10] (4) | -0.50 [-0.65, -0.35] (4) |
| 36 | -0.90 [-0.90, -0.80] (5) | -1.20 [-1.30, -1.20] (5) | -1.00 [-1.00, -1.00] (5) | -0.50 [-0.80, -0.30] (5) | -0.60 [-0.90, -0.30] (5) | -0.30 [-0.50, -0.30] (5) |

## Reproduce and review

Run these commands from the repository root.

```bash
PYTHONPATH=src .venv/bin/python output/dev-growth-vs-bbi/analyze.py
PYTHONPATH=src .venv/bin/python output/dev-growth-vs-bbi/tables.py
PYTHONPATH=src .venv/bin/python output/dev-growth-vs-bbi/pilot.py legacy
PYTHONPATH=src .venv/bin/python output/dev-growth-vs-bbi/pilot.py inputs
```

The local research files are `data/research/bbi/tools/growth_history.csv.gz`, `growth_forward.csv.gz`, `growth_composite_baselines.json`, `growth_coach_development.json` and `growth_methodology.txt`. The extraction handoff is [Basketball Index saved tool extraction](bbx-tool-extract.md). The analysis scripts and row-level comparison outputs are in the ignored `output/dev-growth-vs-bbi/` directory. The age-by-minutes results for the middle half of starting level are in `level_matched_by_age.csv` there, including the retrospective forecast and actual-minus-forecast bands. The installed 94-input file matched the tracked compressed copy byte for byte after decompression.

The 15 focused development outlook and rating model tests passed. Implementation is pending coordinator review. This task changed the report and board only, with local research outputs in the ignored directory.

## DEV-TUNE results

Young rotation players improve faster in both rating sets. The broad peak is around ages 23–26. By 27–30, offense has started to slip while defense holds closer to flat. Decline accelerates in the thirties. Players can have meaningfully different years, with most of the spread coming from a draw that lasts the season.

### Healthy age curve

These are median annual changes for players with 500+ minutes. Each cell gives offense / defense / overall. Basketball Index columns use its own talent points. The game columns use rating points. Both game runs started from identical card ratings and used the same coaches and staff.

| Starting age | Basketball Index | Legacy before | Legacy after | 94 inputs before | 94 inputs after |
| --- | --- | --- | --- | --- | --- |
| 19–22 | +0.30 / +0.09 / +0.40 | +1.10 / +0.90 / +1.00 | +1.95 / +1.45 / +1.65 | +0.50 / +0.50 / +0.60 | +0.80 / +0.80 / +0.90 |
| 23–26 | +0.01 / -0.04 / +0.03 | +0.30 / +0.20 / +0.20 | +0.30 / +0.20 / +0.20 | +0.10 / +0.10 / +0.10 | +0.10 / +0.10 / +0.10 |
| 27–30 | -0.14 / -0.06 / -0.15 | +0.10 / +0.00 / +0.10 | -0.80 / +0.00 / -0.50 | +0.10 / +0.10 / +0.10 | -0.40 / -0.10 / -0.30 |
| 31–33 | -0.17 / -0.07 / -0.16 | -0.50 / -0.90 / -0.60 | -2.20 / -1.00 / -1.70 | -0.20 / -0.30 / -0.40 | -1.00 / -0.60 / -1.00 |
| 34–36 | -0.18 / -0.09 / -0.30 | -0.70 / -1.10 / -0.90 | -3.50 / -2.30 / -3.20 | -0.40 / -0.60 / -0.40 | -1.30 / -1.10 / -1.50 |

The matched 500+ minute sample also shows the earlier downturn when the game applies each month in order. These replays use the normal event eligibility and minimum change threshold, with random rating changes off.

| Starting age | Legacy before | Legacy after | 94 inputs before | 94 inputs after |
| --- | --- | --- | --- | --- |
| 19–22 | +1.30 / +1.10 / +1.20 | +2.20 / +1.75 / +2.00 | +0.50 / +0.60 / +0.50 | +0.80 / +1.00 / +1.00 |
| 23–26 | +0.30 / +0.30 / +0.30 | +0.30 / +0.40 / +0.30 | +0.20 / +0.10 / +0.20 | +0.20 / +0.10 / +0.20 |
| 27–30 | +0.00 / +0.00 / +0.00 | -0.40 / +0.00 / -0.20 | +0.00 / +0.00 / +0.00 | -0.15 / +0.00 / -0.10 |
| 31–33 | -0.40 / -0.70 / -0.50 | -1.90 / -0.70 / -1.40 | -0.20 / -0.30 / -0.20 | -1.00 / -0.50 / -0.90 |
| 34–36 | -0.70 / -1.00 / -0.80 | -3.30 / -2.30 / -2.90 | -0.40 / -0.60 / -0.30 | -1.20 / -1.20 / -1.30 |

Low-minute players ages 27–30 can still be skipped by the existing eligibility rules. The detailed tables include separate 0–499, 500–1,499 and 1,500+ minute cohorts and single-year age cells. See `output/dev-growth-vs-bbi/after/comparison.md` and the age tables in each run folder.

### Variation around each player's expected year

The original comparison replays 12 seeded years for the same 182 players, including 136 with 500+ projected minutes. Each player's realized yearly change is measured against their own replay with the random rating changes turned off. The last column divides the endpoints by the distance between the 25th and 75th percentiles of starting overall ratings within the same group.

| Source | Side | N | Median | Middle 50% | Middle 80% | Middle 90% | Starting spread | Middle 80% relative to start |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Basketball Index | overall | 1796 | -0.09 | -0.62 to +0.38 | -1.11 to +0.84 | -1.47 to +1.14 | 1.81 | -61% to +46% |
| legacy before | overall | 1632 | +0.00 | +0.00 to +0.00 | +0.00 to +0.10 | +0.00 to +0.10 | 12.90 | +0% to +1% |
| legacy after | overall | 1632 | +0.00 | -2.10 to +1.90 | -4.60 to +4.10 | -6.45 to +5.70 | 12.90 | -36% to +32% |
| inputs before | overall | 1632 | +0.00 | +0.00 to +0.00 | +0.00 to +0.10 | +0.00 to +0.10 | 11.02 | +0% to +1% |
| inputs after | overall | 1632 | +0.00 | -1.20 to +1.10 | -2.80 to +2.80 | -4.10 to +3.85 | 11.02 | -25% to +25% |

Among 1,500+ minute players, the original replay's middle 80% moved from **0% to +1%** of starting spread to **−42% to +37%** in legacy and from **0% to 0%** to **−29% to +28%** in inputs. Basketball Index's reference is **−54% to +44%** in that group. This replay runs from November through October and crosses a season boundary.


Across complete July–June seasons, the same draw applies to all 12 monthly updates. The higher-minute groups are close to the Basketball Index overall band on the relative scale, with legacy somewhat wider and the 94-input set somewhat narrower.

| Minutes | Source | Overall middle 80%, before | Overall middle 80%, after | After as share of starting spread |
| --- | --- | --- | --- | --- |
| 500+ | Basketball Index reference | — | −1.11 to +0.84 | −61% to +46% |
| 500+ | Legacy | 0.00 to +0.10 | −7.00 to +6.30 | −54% to +49% |
| 500+ | 94 inputs | 0.00 to +0.09 | −4.60 to +4.00 | −42% to +36% |
| 1,500+ | Basketball Index reference | — | −1.07 to +0.86 | −54% to +44% |
| 1,500+ | Legacy | 0.00 to +0.10 | −8.50 to +7.67 | −65% to +59% |
| 1,500+ | 94 inputs | 0.00 to 0.00 | −5.30 to +4.90 | −45% to +42% |

In the original November–October replay with season draws on, median overall movement at ages 27–30 was **−0.65 legacy** and **−0.20 inputs** for the 1,500+ minute sample. The pooled 500+ minute sample was flat in both, reflecting the eligibility gap and the spread around the healthy forecast. The historical Basketball Index scores also reflect role, health and measurement changes.

### What changed in the game

- The learning boost is strongest through age 22 and tapers by age 24. Prospects with recorded skill ceilings keep their separate learning runway.
- Aging phases in for offensive execution after 25½, athletic ratings mostly after 28½ and other defensive ratings after 29½. The decline steepens after 32. Passing reads and scheme knowledge retain their age protection.
- One draw per player and July–June season affects several ratings together. It has less influence on conditioning, certain reads, weaker roles and prospects with defined skill ceilings. The effects of previous draws fade over two seasons to contain long-term drift. The monthly noise is smaller for players without defined skill ceilings. The healthy outlook uses the same aging and learning curves and excludes both sources of random change.
- Gains taper as a hidden rating approaches the upper end. Starting card scores matched for all 671 players in both rating sets. A three-year fixed-roster replay reproduced the same final traits and scores in both modes, and the 94-input development deltas also matched. Across the 182-player test, no final trait or input grade newly ended at 100.
- A fixed-roster health replay through the current injury model produced similar age medians to the healthy replay at seed 17. It held roles and minutes fixed.

### Validation

- The 1,230-game real-stat scorecard, run with starting ratings and real minutes, was byte-for-byte identical before and after in each rating set. Both met 18 of 18 league targets. Ratings can already differ by opening night in a live save if offseason development ran.
- Core suite passed with 330 tests run and 2 skipped. The separate ratings model, outlook and coverage check passed all 20 tests.
- The requested three development modules ran 15 tests. One prospect assertion still expects the old −0.12 monthly loss floor. It passes on the baseline. A separate check of all 75 combinations in that test preserved the staff, injury and minutes ordering with the tuned model.
- The additional prospect learning and talent balance check ran 14 tests. The old monthly loss floor and eight exact outputs from the old development formula failed. Both affected learning tests passed when replayed with the baseline formula.
- Event generation plus rating writeback on the full roster took a median of 0.25 → 0.33 seconds in legacy and 0.82 → 0.86 seconds in inputs. This measures the monthly development step.

**Resume state.** Waiting on the full suite and the frozen-rating betting-odds check. Comparison detail, replay scripts and logs are in `output/dev-growth-vs-bbi/`. The paired scripts substitute only the old monthly formula in the same process to keep concurrent staff and simulation work out of the comparison.

## Coordinator review (Claude, 2026-11-19)

- **Accepted.** The aging curve, youth learning boost, top-of-scale taper and fading season draw are all accepted.
- **Process slip (Claude's).** The health.py part of this work was swept into Claude's coaching commit 5b6812c
  (23:18, Nov 17) while it was still in progress, so it reached main before review. Reviewed now; nothing lost.
- **User decision: about two-thirds of Basketball Index's year-to-year spread.** Part of the real spread is
  measurement noise and role change, not ability. The season draw is now 0.47 for the 94-input ratings and 0.36 for
  the older trait set. The older set needs a smaller draw because the 94-input route compresses changes when it
  re-derives traits.
- **Measured** with one July–June season, draw on vs off, 182-player sample, 6 seeds. The middle 80% of the draw's
  effect on overall, as a share of the starting spread:

  | Minutes | Target (two-thirds of Basketball Index) | Older ratings (0.36) | 94-input ratings (0.47) |
  | --- | --- | --- | --- |
  | 500+ | −41% to +31% | −35% to +32% | −34% to +29% |
  | 1,500+ | −36% to +29% | −37% to +33% | −41% to +34% |

- **Bug found and fixed in review.** Simulating a playoff round in one call and day by day gave slightly different
  development. Cause: the head-coach reputation calibration (`staff.apply_head_coach_reputation`) re-ran on every
  save load and kept nudging the coach's ratings. Development now reads the save's head coach (coaching overhaul),
  so that drift mattered. It now calibrates once.
- **Stale tests updated.**
  - The old 0.12 monthly cap was replaced by aging-curve and draw bounds in test_foundation,
    test_prospect_development and test_prospect_learning.
  - The pinned monthly references were recaptured from the new formula.
