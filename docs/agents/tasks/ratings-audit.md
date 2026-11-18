# Ratings audit: rim protection and players the game rates differently from the evidence

Owner: Claude (overnight worker session, 2026-11-18), branch `claude/ratings-audit`. Status: **review**.

## TL;DR

- **Rim protection no longer flattens at the top, and blocks go to real shot-blockers.** The top 25 rim protectors used to sit within 1–1.6 points of each other on the card; now they spread like the real evidence (Wembanyama +17.0, Holmgren +15.1, Gobert +14.7, about +11 for the 25th). Sim blocks: Jokić 2.33 → 0.66 per 36 (real 0.84), Huff 1.13 → 2.91 (real 3.20); average miss 0.32 → 0.21.
- **Player values track real impact better.** Usage now pays off only with the skill behind it, and one input (attack recognition) dropped a misleading shot-location measure, so stars' offense is no longer under-credited (Brunson 102nd → 42nd overall among 278 compared players; the evidence says 60th). No input was moved to hit a target; the 30 biggest remaining disagreements are mostly rookies, role players the impact metrics disagree on, and three energy bigs the value model cannot read (listed, left alone).
- **Scorecards (final, combined with box-star-stats):** real-stat targets 18/18 in band for both rating sets, blocks much better; betting odds better than before this branch (Brier 0.1955 → 0.1942, log loss 0.5786 → 0.5745, spread error 5.04 → 4.65) except totals (5.51 → 5.63). An interim odds regression was diagnosed and fixed; see "Follow-up after coordinator review". The "Scorecards" section below is the interim state before that fix.

## Task 1: rim protection saturated at the top

### What was wrong (three stacked causes)

1. **The response curve flattened the top.** `defense.rim_response` turns the rim_deterrence rating into the engine's
   effective rim protection. Its shoulder reached 99 near rating 92 and ended with almost no slope, so every big above
   ~90 landed between 95 and 99. Among the 25 best rim protectors by evidence, the card's "Inside 8 feet" suppression
   spanned only 1.0 points (legacy ratings) or 1.6 points (new ratings). With the rim term flat, the small scheme-IQ
   term decided who looked best (Barnes and Ausar Thompson out-rated Gobert on the new-ratings card).
2. **The rating scale itself was clipped at 100.** Seven players share rim_deterrence 100.0 in the legacy data
   (Wembanyama, Lopez, Turner, Huff, Stewart, Capela and one more). The new ratings are placed onto that same
   scale by league rank, so the top ~1% of the new ratings also tied at exactly 100.
3. **The new-ratings recipe for rim deterrence used the wrong inputs.** It averaged league percentiles of generic
   defensive grades with jump height (P10, where guards out-jump centers) and foul control. Gilgeous-Alexander (94.4),
   Cunningham (97.2) and Jalen Williams (96.7) rated above Kessler (82.8) and Huff (80.3), and Jokić got 90.8.
   This is also why blocks went to wings: Jokić 2.33 blocks per 36 in the sim (real 0.84), Anunoby 2.26 (0.78),
   LeBron 2.07 (0.63), while Huff got 1.13 (real 3.20).

### What changed (no player's inputs were changed for this task)

- **Evidence-shaped response** (`defense.rim_response`, knots in `data/canonical/rim_response_fit.json`, built by
  `scripts/fit_rim_protection.py`). Up to the 75th league percentile of the rating (rating ~66) nothing changes: the
  old response already matched the real spread there. Above it, the rating's league rank is mapped onto the real
  distribution of opponents' rim FG% against expectation (Basketball Index "Stable Rim dFG% vs. Expected", the
  sample-size-shrunk version), at the same exchange rate the old curve used between the 25th and 75th percentiles
  (4.95 response points per percentage point). Result: league 85th percentile 81.5 → 76.2, 90th 89.1 → 82.1,
  95th 97.5 → 91.7, 98th 98.6 → 106.5, 99th 99 → 111.4, best ~123. Good-not-elite bigs come down a little, elite
  ones go up, nobody is clipped. Why this measure: it is the direct real counterpart of the card's rim number, and in
  the middle of the league the engine already matched it (median rotation player +1.6 on the card vs +1.1 real).
- **No clipped plateau** (`trait_adapter.uncensor_top`). When a legacy table has several values tied at 100, they
  are treated as censored and replaced by the table's own upper tail extended on the normal-quantile scale
  (rim_deterrence's seven 100s become 100.4–106.6 in the new ratings' table). Also applies to the other two clipped traits:
  shooting range (top value 100 → 102.1) and offensive rebounding (100, 100 → 102.1, 104.3). The legacy rating set keeps its own ties (its data are not changed).
- **Rim recipe fitted to evidence** (`trait_adapter.ADAPTER_SPEC["rim_deterrence"]`). Target: the mean z-score of six
  Basketball Index rim measures (Rim Points Saved per 75, Stable Rim dFG% vs. Expected, Rim Deterrence, Rim
  Protection, Rim Contests per 75, Block Rate on Contests), 2023-24..2025-26, minutes-weighted. Non-negative ridge
  over defensive technique and size inputs, 491 players, out-of-fold r 0.90. Recipe: contest technique 0.52,
  interior positioning 0.23, height 0.14, rotation recognition 0.07, wingspan 0.04. Jump height and foul control
  dropped out on their own. Jokić 90.8 → 71.7, Gilgeous-Alexander 94.4 → 78.0, Kessler 82.8 → 96.0.
- **Blocks from a fitted rate** (`defense.block_rate_per36`, `scripts/fit_block_rate.py`). Each player's box blocks
  are one Poisson draw (same single random number as before) from a per-36 rate fitted to real 2025-26 blocks
  (377 players): rim protection, plus in the new ratings the contest-jump tendency (T16: does he leave his feet).
  Blocks are skill times choice, so Jokić (stays down) blocks few shots and Huff (jumps at everything) many. The old
  power-2 team rescale is gone; box variation adds only the remaining team-level spread (real team-game sd 2.46).
- Smaller pieces: zone suppression/contest and fatigue-adjusted rim features no longer clip at 99; the help-defense
  league mean was re-measured (59.0 → 56.2); the player-value fit was refitted for the new rim recipe.

### Top 25 rim protectors by evidence: card "Inside 8 feet" suppression and rank among 108 rotation bigs

Evidence = mean z-score of the six rim measures above (higher is better). Card = suppression in percentage points.

| Evidence rank | Player | Rim evidence (z) | Legacy before: card / rank | Legacy after: card / rank | New before: card / rank | New after: card / rank |
|---:|---|---:|---|---|---|---|
| 1 | Victor Wembanyama | 2.85 | +11.7 / 2 | +14.0 / 1 | +11.8 / 1 | +17.0 / 1 |
| 2 | Chet Holmgren | 2.45 | +11.5 / 4 | +13.2 / 3 | +11.2 / 5 | +15.1 / 2 |
| 3 | Donovan Clingan | 2.34 | +10.9 / 19 | +12.1 / 16 | +10.8 / 11 | +14.3 / 4 |
| 4 | Walker Kessler | 2.27 | +11.2 / 12 | +11.4 / 24 | +8.0 / 58 | +9.2 / 33 |
| 5 | Dylan Cardwell | 2.11 | +3.2 / 88 | +3.2 / 88 | +8.7 / 49 | +11.4 / 21 |
| 6 | Daniel Gafford | 2.08 | +10.7 / 26 | +11.4 / 25 | +9.6 / 37 | +10.9 / 25 |
| 7 | Rudy Gobert | 1.98 | +11.7 / 1 | +13.5 / 2 | +10.8 / 12 | +14.7 / 3 |
| 8 | Robert Williams III | 1.85 | +10.3 / 34 | +9.2 / 34 | +10.6 / 17 | +11.1 / 22 |
| 9 | Kristaps Porziņģis | 1.84 | +11.0 / 15 | +11.9 / 17 | +11.2 / 4 | +13.1 / 9 |
| 10 | Luke Kornet | 1.83 | +9.8 / 39 | +8.2 / 41 | +10.6 / 18 | +12.4 / 12 |
| 11 | Ryan Kalkbrenner | 1.80 | +9.7 / 44 | +8.1 / 44 | +10.7 / 16 | +13.5 / 5 |
| 12 | Ivica Zubac | 1.73 | +11.2 / 11 | +12.8 / 9 | +10.4 / 19 | +13.1 / 8 |
| 13 | Brook Lopez | 1.65 | +10.4 / 32 | +12.6 / 12 | +10.2 / 27 | +13.5 / 6 |
| 14 | Alex Sarr | 1.65 | +10.7 / 24 | +12.6 / 13 | +8.9 / 47 | +7.3 / 54 |
| 15 | Zach Edey | 1.64 | +10.2 / 36 | +8.9 / 37 | +10.4 / 20 | +12.7 / 11 |
| 16 | Evan Mobley | 1.64 | +11.4 / 6 | +11.8 / 18 | +10.7 / 14 | +12.0 / 13 |
| 17 | Anthony Davis | 1.62 | +11.6 / 3 | +12.8 / 8 | +10.9 / 8 | +12.8 / 10 |
| 18 | Clint Capela | 1.58 | +10.8 / 23 | +13.1 / 5 | +10.3 / 21 | +11.6 / 20 |
| 19 | Dereck Lively II | 1.57 | +7.6 / 60 | +6.5 / 61 | +10.1 / 28 | +11.1 / 23 |
| 20 | Isaiah Stewart | 1.55 | +10.8 / 22 | +13.1 / 4 | +9.5 / 42 | +10.5 / 28 |
| 21 | Jay Huff | 1.54 | +10.5 / 28 | +12.8 / 10 | +7.2 / 65 | +8.2 / 45 |
| 22 | Jaren Jackson Jr. | 1.54 | +11.2 / 10 | +10.3 / 28 | +10.2 / 23 | +11.9 / 15 |
| 23 | Neemias Queta | 1.50 | +10.7 / 25 | +12.3 / 14 | +10.2 / 26 | +12.0 / 14 |
| 24 | Myles Turner | 1.49 | +10.0 / 37 | +12.3 / 15 | +10.2 / 25 | +11.6 / 18 |
| 25 | Isaiah Hartenstein | 1.49 | +11.3 / 8 | +12.9 / 7 | +11.3 / 2 | +13.3 / 7 |

| Rank agreement with the rim evidence (rank correlation) | Legacy before | Legacy after | New before | New after |
|---|---:|---:|---:|---:|
| All 394 rotation players | 0.67 | 0.67 | 0.86 | **0.94** |
| 108 rotation bigs | 0.64 | 0.67 | 0.70 | **0.87** |
| Top 25 bigs only | 0.15 | -0.04 | 0.23 | 0.34 |
| Card spread across the top 25 bigs | 1.0 pp | 2.6 pp | 1.6 pp | **6.1 pp** |

Notes and open items:
- Legacy ratings: the seven players tied at 100 stay tied (now +12.3 to +14.0 instead of +10.0 to +11.7), so the
  top-25 order inside legacy cannot follow the evidence (that is the legacy data, not the engine). Fixing it would
  mean changing legacy ratings, which needs its own evidence. The new ratings are where the order is fixed.
- New ratings, still low for their evidence: Kessler (#4 by evidence, #33 on the card), Alex Sarr (#14, #54) and
  Huff (#21, #45). Their interior-positioning grade (S36, from on/off rim deterrence and screener rim defense) and
  rotation-recognition grade (S38) are low; the contest-technique grade carries them. These are input values with
  their own Basketball Index evidence, left alone.
- Tested and not adopted: using the rim response (instead of the raw rating) in the defensive value fit, and a rim x
  defensive-technique term: +0.003 to +0.005 out-of-fold, not worth the extra moving part.

### Blocks per 36 (real-minutes replay, 1,230 games; "after" = final state of the branch)

| Player | Real | New ratings before | after | Legacy before | after |
|---|---:|---:|---:|---:|---:|
| Nikola Jokić | 0.84 | 2.33 | 0.66 | 0.70 | 0.55 |
| OG Anunoby | 0.78 | 2.26 | 0.99 | 0.99 | 1.26 |
| LeBron James | 0.63 | 2.07 | 0.59 | 0.98 | 0.98 |
| Draymond Green | 0.81 | 2.18 | 0.78 | 0.74 | 0.60 |
| Nikola Vučević | 0.81 | 2.18 | 1.09 | 2.32 | 1.17 |
| Bam Adebayo | 0.75 | 1.65 | 1.02 | 2.14 | 1.45 |
| Jay Huff | 3.20 | 1.13 | 2.91 | 2.41 | 2.43 |
| Matas Buzelis | 1.86 | 0.43 | 1.11 | 0.77 | 0.72 |
| Victor Wembanyama | 3.79 | 2.58 | 2.56 | 2.55 | 2.44 |
| Chet Holmgren | 2.37 | 2.04 | 2.75 | 2.39 | 2.08 |
| Rudy Gobert | 1.88 | 2.53 | 2.25 | 2.53 | 2.30 |
| Evan Mobley | 1.96 | 2.41 | 1.93 | 2.38 | 1.72 |
| **All 150 compared players: average miss** | | 0.320 | **0.213** | 0.280 | **0.271** |
| **Correlation with real** | | 0.68 | **0.87** | 0.77 | **0.79** |

Wembanyama is still short (2.56 vs 3.79): his block rate on contests (35%) is far beyond what rim protection and
jump choice predict. Matas Buzelis too (1.11 vs 1.86).

## Task 2: players the game rates very differently from the evidence

### How the comparison works

- **Consensus** (`scripts/research/consensus_impact_audit.py`): six real-impact measures from Basketball Index, each
  split into offense and defense: LEBRON, DPM, DRIP, RAPTOR, luck-adjusted RAPM and time-decay luck-adjusted RAPM.
  Each is a z-score among that season's 500+ minute players, averaged across measures, then blended over 2023-24 to
  2025-26 (season weights 1.0 / 0.6 / 0.35 times minutes). Overall = offense + defense. 278 players with 1,000+
  minutes in 2025-26.
- **Game**: the card's overall, offense and defense under each rating set. The game's scale is rank-based, so gaps are
  measured in league-percentile points (+ means the game rates him higher than the evidence).
- For diagnosis the consensus is also split into a **box-score family** (LEBRON, DPM, DRIP, RAPTOR) and an **on/off
  family** (the two RAPMs). When those two disagree, the evidence itself is unsettled.
- The consensus is never a fitting target. The new-ratings value model is fitted to multi-year LEBRON only (as before).

| Agreement with the consensus (rank correlation, 278 players) | Overall | Offense | Defense | Average gap |
|---|---:|---:|---:|---:|
| Legacy ratings | 0.52 | 0.62 | 0.54 | 22.5 pts |
| New ratings, before this branch | 0.794 | 0.778 | 0.844 | 13.9 pts |
| New ratings, after this branch | **0.807** | **0.787** | 0.843 | **13.3 pts** |

### What was found and changed

1. **(a) Mapping: usage was credited the same whether or not skill came with it.** The new ratings' value model
   (`impact_value.py`) is a linear fit, and its biggest offensive term is involvement (how much of the offense a player
   takes on). Every heavy-usage player got the same credit for it, so it under-predicted the stars' offense
   (Brunson's multi-year O-LEBRON +4.97 predicted +3.14; Gilgeous-Alexander +6.06 → +4.98) and over-credited
   heavy-usage scorers whose real impact is modest. Fix: four involvement x skill terms (shooting, creation,
   finishing, two-point efficiency), built so a better skill can never lower a player's value. Fitted to the same
   LEBRON target, the out-of-fold fit improved (offense r 0.886 → 0.902, overall 0.859 → 0.870). Against the
   consensus, which the fit never saw, agreement also improved.
2. **(b) Input evidence: attack recognition (S20) came from a shot-location measure.** Its only Basketball Index
   input was "PnR Ball Handler Shot Quality", the expected value of the handler's own shot locations and contests,
   not his decisions. It ranked rim-heavy handlers at the top (Westbrook and Edwards 99th percentile, Coby White 98th)
   and elite pull-up shot-makers at the bottom (DeRozan 3rd, Cunningham 45th, Brunson 55th), and it pulled five of
   the nine players with reviewed scouting ranges (`docs/ratings-evidence-2026-10-29`, creation/passing packet)
   below the bottom of their range: Brunson 51.6 (range 78–93), Cunningham 50.5 (75–91), Barnes 48.9 (80–94),
   Dončić 63.2 (85–97), Garland 68.7 (77–92). The same flaw got "Half Court Shot Quality" removed on 2026-11-17.
   Fix: the metric is removed from the mapping (`bbi_input_mapping.json`, with the reason recorded in its gap note),
   so S20 now comes from the estimator's prior, which includes the expert ranges where they exist. Only S20 changed
   (483 player records; `scripts/research/transplant_inputs.py` copied S20 from a fresh build so unrelated drift in
   the local evidence did not ride along). Now: Brunson 78.3, Cunningham 78.4, Dončić 80.6, Garland 76.9, Barnes
   73.7 (still below his range), DeRozan 35.9 → 64.0, Westbrook 80.4 → 70.8. The value fit (refitted on the new
   inputs) improved slightly on its own target (offense r 0.900 → 0.902), an independent sign the fix is right.
3. **Jalen Brunson** (the known example): among the 278 compared players his card overall goes 102nd → 42nd (consensus 60th: 15 points too low before, 6.5 too high now). Among all 365 rotation players: overall 122nd → 50th, offense 20th → 10th,
   playoff translation 65th → 54th. His real playoff record is strong; the playoff recipe is fitted to playoff
   box production and playoff talent grades, and still ranks him 54th (see open questions).

### The 30 biggest disagreements after the changes (new ratings, sorted by overall gap)

Class: **a** = engine/mapping problem, **b** = an input with weak or wrong evidence, **c** = the evidence is noisy or
role-driven and the game is defensible. "Open" = a real problem with no supported fix found tonight.

| # | Player | Min 25-26 | Consensus rank (box / on-off) | Game rank, new ratings: before -> after | Legacy rank | Gap new O / D / OVR | Class | Diagnosis |
|---:|---|---:|---|---|---:|---|---|---|
| 1 | Moussa Diabaté | 1899 | 31 (43 / 22) | 222 -> 209 | 230 | -67 / -15 / -64 | a, open | Energy big: low involvement and no jumper outweigh offensive rebounding and finishing in the value model. The model misses him against its own target too (real offense +0.65 vs predicted about -0.4). Tested extra offensive-rebounding, screening, cutting and lob-finishing terms: at most +0.004 out-of-fold, no supported fix. |
| 2 | Cedric Coward | 1598 | 204 (176 / 231) | 72 -> 63 | 162 | +39 / +23 / +51 | c | Rookie (44 inputs still priors); his first season grades well on technique, poorly on impact (box #176, on/off #231). No independent evidence to move an input. |
| 3 | Daniss Jenkins | 1455 | 130 (174 / 85) | 242 -> 255 | 276 | -26 / -43 / -45 | c | One real season (1,455 min, 48 of 94 inputs still priors). On/off #85, box #174. |
| 4 | AJ Green | 2270 | 150 (212 / 67) | 274 -> 274 | 232 | -51 / -34 / -45 | c | Low-usage spot-up shooter; on/off rates him (#67), box-score metrics do not (#212). The game follows the box view. |
| 5 | Gui Santos | 1395 | 90 (111 / 69) | 192 -> 206 | 185 | -17 / -40 / -42 | c | Small samples (192 / 762 / 1,395 min). His Basketball Index help and foul-control grades are near the bottom; his on/off is good. |
| 6 | Josh Okogie | 1354 | 69 (104 / 27) | 186 -> 182 | 213 | -47 / +1 / -41 | c | Low-usage wing defender; on/off #27, box #104. Role-driven. |
| 7 | Brandon Miller | 1968 | 156 (123 / 210) | 43 -> 44 | 42 | +19 / +24 / +40 | c | Strong shooting and creation grades over three seasons; impact middling (box #123, on/off #210). The involvement x skill change did not move him much: his skills are real. |
| 8 | Pelle Larsson | 1849 | 123 (159 / 87) | 225 -> 234 | 223 | -27 / -31 / -40 | c | Second season; on/off #87, box #159. |
| 9 | Jordan Goodwin | 1572 | 71 (86 / 49) | 172 -> 180 | 244 | -36 / -16 / -39 | c | Low-usage role guard on short samples (543 min in 2024-25); on/off #49, box #86. |
| 10 | Brandon Ingram | 2604 | 207 (153 / 253) | 93 -> 98 | 44 | +20 / +13 / +39 | c, watch | High-usage tough-shot scorer; every impact metric is lukewarm (box #153, on/off #253). The game credits his shot-making grades. Moved 93rd -> 98th by the involvement x skill change. |
| 11 | Landry Shamet | 1171 | 132 (195 / 56) | 239 -> 240 | 257 | -34 / -25 / -39 | c | On/off-driven (#56 vs box #195). |
| 12 | Quentin Grimes | 2206 | 224 (224 / 222) | 112 -> 117 | 85 | +6 / +40 / +38 | c | Defense: his Basketball Index technique grades are good (screen navigation 98th pct, steal technique 88th) while every impact metric calls him a poor defender. The card shows technique; the layers disagree. |
| 13 | Hugo González | 1084 | 88 (129 / 43) | 224 -> 194 | 240 | -11 / -6 / -38 | c | Rookie, age 20, 1,084 min, 49 inputs still priors. |
| 14 | Sion James | 1843 | 147 (198 / 91) | 261 -> 250 | 227 | -12 / -16 / -37 | c | Rookie, 45 inputs still priors. |
| 15 | John Collins | 1871 | 155 (146 / 169) | 45 -> 52 | 123 | +19 / +33 / +37 | c | Defense: rotation-recognition 96th pct and rim protection 84 from technique evidence; impact average. |
| 16 | Santi Aldama | 1198 | 171 (154 / 188) | 75 -> 69 | 137 | +10 / +32 / +37 | c | Defense: technique grades above his impact numbers. |
| 17 | Peyton Watson | 1598 | 250 (219 / 271) | 168 -> 151 | 116 | +12 / +40 / +36 | c | Defense: athletic shot-blocking wing (rim 80); impact metrics poor. |
| 18 | Quinten Post | 1159 | 202 (186 / 206) | 113 -> 104 | 190 | +35 / +20 / +35 | c | Second season, stretch big; rim evidence is genuinely good (+1.0 z), impact middling. |
| 19 | Nikola Vučević | 1818 | 170 (177 / 160) | 62 -> 73 | 68 | +24 / +17 / +35 | c, watch | Age 35; post scoring, rebounding and size carry his value; both impact families rate him about 170th. |
| 20 | Neemias Queta | 1926 | 16 (20 / 14) | 110 -> 110 | 107 | -50 / -4 / -34 | a, open | Same pattern as Diabaté: both the box-score family (#20) and on/off (#14) rate him highly; the game sees a low-usage non-shooter. Rim protection now rates elite (98.6); the gap is on offense. |
| 21 | Will Richard | 1377 | 135 (147 / 137) | 218 -> 229 | 256 | -8 / -22 / -34 | c | Rookie, 49 inputs still priors. |
| 22 | Tyler Herro | 1033 | 153 (121 / 209) | 77 -> 59 | 17 | +6 / -1 / +34 | c | Injury-shortened season (1,033 min); box #121 vs on/off #209. |
| 23 | Nique Clifford | 1882 | 160 (229 / 62) | 256 -> 254 | 236 | -8 / -36 / -34 | c | Rookie; on/off #62 vs box #229. |
| 24 | Luke Kornet | 1430 | 41 (51 / 29) | 140 -> 135 | 154 | -53 / +0 / -34 | a, open | Same pattern (screening and rim-running big). Rim protection now 12th among bigs on the card (was 39th, legacy). |
| 25 | Miles Bridges | 2387 | 183 (144 / 224) | 103 -> 90 | 103 | +9 / +19 / +34 | c | Volume wing; box #144 vs on/off #224. |
| 26 | Naji Marshall | 2184 | 201 (188 / 202) | 104 -> 109 | 134 | +22 / +14 / +33 | c | Box #188, on/off #202; game rates his finishing and post grades. |
| 27 | Miles McBride | 1080 | 92 (137 / 36) | 183 -> 184 | 140 | -30 / -18 / -33 | c | On/off-driven (#36 vs box #137), 1,080 min. |
| 28 | Ayo Dosunmu | 1881 | 232 (216 / 245) | 124 -> 142 | 176 | +15 / +22 / +32 | c | Box #216, on/off #245. |
| 29 | Jamal Shead | 1852 | 174 (191 / 141) | 266 -> 263 | 197 | -12 / -41 / -32 | c | Small point-of-attack guard; the value model leans on size for defense. Both families rate him below average overall (#191 box, #141 on/off). |
| 30 | Bobby Portis | 1619 | 245 (217 / 260) | 141 -> 157 | 178 | +39 / +6 / +32 | c | Bench scorer; box #217, on/off #260. Scheme IQ 22 already marks his weakness. |

**Reading the list.** Fifteen of the 30 are rookies, second-year players or short samples, or players the two
evidence families disagree on (usually on/off loves a low-usage role player the box-score metrics call average).
The game follows the box-score view there, as its value model is fitted to LEBRON. Twelve are volume scorers or
technique-strong defenders whose skills grade well while every impact measure is lukewarm. That is the four-layer
model working as designed (technique is shown separately from outcomes), but Ingram and Vučević are worth a second
look. The three energy bigs (Diabaté, Queta, Kornet) are the one real mapping gap left: both evidence families rate
them highly and the value model cannot express why.

## Scorecards

### Real-stat targets (`scripts/calibration_report.py --games 1230 --mode replay-real-minutes`)

League metrics: **18/18 in band** before and after, both rating sets.

| Per-36 average miss, 150 players | New before | New after | Legacy before | Legacy after |
|---|---:|---:|---:|---:|
| Points per game (league, real 115.6) | 115.95 | 115.90 | 114.19 | 114.51 |
| Points | 2.595 | **2.566** | 2.653 | 2.665 |
| Field-goal attempts | 1.922 | **1.889** | 1.864 | 1.897 |
| Threes attempted | 0.403 | **0.396** | 0.400 | 0.396 |
| Free throws attempted | 1.145 | 1.146 | 1.222 | 1.216 |
| Rebounds | 1.160 | 1.164 | 1.134 | 1.129 |
| Assists | 0.697 | **0.687** | 1.091 | 1.099 |
| Turnovers | 0.583 | 0.591 | 0.602 | 0.605 |
| Steals | 0.280 | 0.294 | 0.313 | 0.309 |
| **Blocks** | 0.320 | **0.213** | 0.280 | **0.271** |
| True shooting | 0.025 | 0.026 | 0.025 | 0.025 |

The new ratings' scoring offset (`sim.INPUTS_OFFENSE_CALIBRATION`, same for both teams, so margins are unaffected)
was re-centred 2.45 → 1.60 per 100 possessions: the rim changes lowered league rim protection (guards no longer count
as rim protectors and good-not-elite bigs came down a little), which had raised replay scoring to 116.8 per team.
Legacy scoring rose 0.3 per team and needed no change (it is still below the real level). Steals and turnovers moved
by about 0.01 per 36 (rotation and score changes, not their allocation code, which another agent owns).

### Betting-odds test (`validate-season-probabilities --runs 100`, new ratings) — interim, superseded by the follow-up

| | Brier | Log loss | Spread error vs market | Totals error vs market |
|---|---:|---:|---:|---:|
| Before (base commit bba9a83, re-run tonight; matches the coordinator's numbers exactly) | 0.1955 | 0.5786 | 5.04 | 5.51 |
| After Task 1 only (no scoring re-centre) | 0.1964 | 0.5801 | 4.77 | 5.91 |
| After both tasks (final) | 0.1968 | 0.5808 | **4.74** | 5.70 |
| Market | 0.1962 | 0.5740 | | |

**Read this before merging: the probability scorecard got slightly worse.** Brier 0.1955 → 0.1968 (+0.0013) and
log loss 0.5786 → 0.5808 (+0.0022): the sim went from slightly beating the market's Brier (0.1962) to slightly
trailing it. At the same time the predicted margins moved clearly closer to the market's spreads (average spread
error 5.04 → 4.74), and totals error rose 5.51 → 5.70 (it was 5.91 before the scoring re-centre). Most of the change
came with Task 1 (Brier 0.1964 after Task 1 alone); the attack-recognition fix added the rest. The bucket view is
mixed rather than one-directional: heavy favorites are less overconfident (0.889 → 0.881 vs 0.841 actual) and away
favorites closer (0.282 → 0.299 vs 0.328), while plain home favorites moved away (0.716 → 0.706 vs 0.728). The
league-wide spread of team rim protection actually narrowed (team standard deviation 6.6 → 5.6), because guard-heavy
teams lost rim protection they never had, so this is not "rim effects got too big". The test only keeps 20 game
reports, so the change could not be traced game by game tonight, and the three-run budget for this test is used up.
The coordinator should decide whether the rim realism, the much better blocks and the closer spreads are worth
+0.0013 Brier, or ask for a follow-up that re-tunes the team-level rim coefficients in `sim.py` (shot-diet rim
suppression, shot-quality term, defensive anchor), which were set on the old, compressed scale.

## Tests

- New/updated: `tests/test_defensive_alignment.py` (response is monotone and never clipped, the low/mid part is
  unchanged, the evidence tail joins without a jump, the old shoulder's flatness is documented, block rate rises with
  rim protection and with choosing to jump, one-draw Poisson count), `tests/test_trait_adapter.py` (clipped plateau
  rescaled, rim recipe is technique and size, not jump height), `tests/test_impact_value.py` (better skill never
  lowers value at any involvement level; involvement pays off more for a skilled player), `tests/test_box_variation.py`
  (team blocks spread near the real 2.46 instead of "variance grows 25%", because blocks now arrive already varied).
- Focused modules: defensive alignment, trait adapter, impact value, ratings model, Basketball Index evidence and
  import, build player inputs, court influence, spatial, shot chart, box stat tiebreak, box variation, box score
  reconciliation, team block: all pass.
- Core suite (`scripts/run_core_tests.sh`, local python path): 320 run, all pass except `test_settlement_materialization`, which cannot load its fixture in a fresh worktree (`output/settlement-materialization-pass/` is git-ignored and absent), a missing file unrelated to these changes. (The final scoring-offset commit landed while the suite ran; its test module, `test_box_stat_tiebreak`, was re-run and passes.)
- Not run: the full ~37-minute suite and the browser JS tests.

## Files

- Engine: `src/nba_gm_data/defense.py`, `trait_adapter.py`, `sim.py` (block line, contest-jump feature, blocks left
  out of the power rescale, scoring offset, fatigue clamp), `spatial.py` (no top clip on zone suppression/contest),
  `box_variation.py` (block spread), `court_influence.py` (rim mean), `impact_value.py` (involvement x skill terms).
- Data (derived numbers only): `data/canonical/rim_response_fit.json`, `data/canonical/impact_value_fit.json`,
  `data/canonical/player_inputs_2026_27.json.gz` (S20 only), `data/research/bbi/bbi_input_mapping.json` (S20 entry).
- Scripts: `scripts/fit_rim_protection.py`, `scripts/fit_block_rate.py`, `scripts/fit_impact_value.py` (version),
  `scripts/research/consensus_impact_audit.py`, `scripts/research/transplant_inputs.py`.
- Output (git-ignored): `output/ratings-audit/consensus_vs_game.json` (full 278-player comparison).

## Follow-up after coordinator review (2026-11-18, later the same night)

**TL;DR.** The betting-odds regression was real, and it came from the sim's hand-made player-impact blend losing
its hidden "general defense" signal once rim deterrence became a true rim rating. The sim's impact now reads the
evidence-fitted value the card already shows. Combined branch: Brier **0.1942**, log loss **0.5745**, spread error
**4.65** (all better than before this branch); totals error **5.63** is still above 5.51 (target 5.55); that is the
remaining cost.

### 1. Diagnosis

- **Not noise.** Re-running both the base and the branch with a second seed gave the same numbers to 0.0001
  (base 0.1955 / 0.5787, branch 0.1969 / 0.5811). The game probabilities are smooth enough that the season mean barely
  moves between seeds. (A first estimate from per-game spreads suggested noise of ±0.0012; the seed test shows that
  was far too pessimistic.)
- **What got worse was the order of teams, not the spread of probabilities.** Sim vs market win-probability
  correlation 0.898 → 0.893; the sim actually got less overconfident (calibration slope 0.764 → 0.789; 1 is perfect).
- **Which teams moved and why.** With every game report kept (local change only), each team's average margin shift
  tracked the change in its rim deterrence (r 0.78) and in the sim's player impact (r 0.77); shot creation 0.28,
  usage 0.02. The sim's impact (`sim.player_impact_score`) is a hand blend of nine skills that includes rim
  deterrence. While the rim rating mixed in general defensive grades, it also carried perimeter and help defense.
  Fitted to real rim evidence, it no longer does, so the biggest sim-impact losers were elite non-rim defenders:
  Anunoby −3.6, Achiuwa −3.5, Draymond Green −3.5, Eason −3.3, Adebayo −3.1, Gordon −2.7.
- **The team-level rim coefficients were not the problem.** The new team rim value matches real team rim evidence
  better (minutes-weighted team rim vs Basketball Index rim points saved, 2025-26: r 0.51 → 0.65). The engine's
  overall rim sensitivity (0.21 points per 100 per rim point, measured by shifting everyone's rim protection +10) is
  of the same order as the evidence slope (0.15 per 100 from rim points saved alone, which leaves out deterrence).
  Re-fitting them would not have touched the cause. The scoring offset only moves both teams equally, so margins
  are unaffected.
- **Totals.** The average totals error grew because team scoring environments moved (teams that lost "guard rim
  protection" allow more; teams with elite bigs allow less). Against the real 2025-26 team results in the
  real-minutes replay, team totals actually matched better after Task 1 (team-total correlation 0.51 → 0.56). The
  per-game gap to the market's totals grew, though: the average miss after removing each run's overall bias went
  from 5.37 to 5.61.

### 2. Fix (evidence-based, nothing fitted to the odds test)

In new-ratings mode the sim's player impact feature is the fitted value: Basketball Index multi-year O+D LEBRON
predicted from the hidden ratings and grouped inputs (`impact_value.sim_impact`, the same model the card shows). It is
placed by league rank onto the blend's own distribution, so every team-strength formula keeps its scale. Usage
projections keep the blend. This also makes the engine match what the user sees (rule 4). Examples (blend → fitted):
Gobert 61.1 → 68.6, Diabaté 50.4 → 56.4, Gilgeous-Alexander 84.3 → 80.0, Draymond Green 69.1 → 64.9, Jokić 81.1 → 82.1.

| Betting odds, new ratings, 100 runs | Brier | Log loss | Spread error | Totals error | Sim vs market corr |
|---|---:|---:|---:|---:|---:|
| Base (main before this branch) | 0.1955 | 0.5786 | 5.04 | 5.51 | 0.898 |
| This branch before the fix | 0.1968 | 0.5808 | 4.74 | 5.70 | 0.893 |
| box-star-stats alone (its own report) | 0.1949 | 0.5772 | 4.93 | n/a | n/a |
| Combined, without the fix | 0.1957 | 0.5778 | 4.68 | 5.64 | 0.893 |
| **Combined, with the fix (final)** | **0.1942** | **0.5745** | **4.65** | 5.63 | **0.903** |
| Coordinator's targets | ≤ 0.1958 | ≤ 0.5792 | ≤ 5.04 | ≤ 5.55 | |

Totals stay 0.12 above the base. I found no principled lever for them: the remaining gap is the market's view of team
scoring environments. Pulling the sim's average toward the market's totals would be fitting to the test. Holding
league scoring at the real level (115.55 per team in the replay vs real 115.6) is the principled anchor.

### 3. Card ratings above 99 (rules 3 and 4)

The attribute summary keeps the engine's value (rim deterrence, range, offensive rebounding, block, rebounding,
defense skill and team rim protection no longer cap at 99). `save.presentation_rating_value` shows everything at or
below 99 unchanged; above 99 it approaches 100 smoothly and keeps rising (100 → 99.3, 102.1 → 99.6, 104.3 → 99.8,
106.6 → 99.9), so elite players stay distinguishable. `defensive_components.skill` no longer clips at 99 either.

### 4. Merge with box-star-stats

Merged `claude/box-star-stats`. The conflict in `normalize_secondary_box_score_totals` and the box-line block was
resolved by keeping its Poisson assists/turnovers/steals, input-driven rates and team levels, plus this branch's block
rate, contest-jump feature and blocks-out-of-the-rescale. Both helper styles remain (`poisson_quantile` there,
`defense.poisson_count` here; they could be unified later).

| Real-minutes replay, 1,230 games | Before this branch (new) | Combined final (new) | Before (legacy) | Combined final (legacy) |
|---|---:|---:|---:|---:|
| League metrics in band | 18/18 | 18/18 | 18/18 | 18/18 |
| Points per game (real 115.6) | 115.95 | 115.55 | 114.19 | 114.51 |
| Points per 36, average miss | 2.595 | **1.260** | 2.653 | 2.665 |
| Field-goal attempts | 1.922 | **1.114** | 1.864 | 1.875 |
| Threes attempted | 0.403 | **0.367** | 0.400 | **0.338** |
| Free throws attempted | 1.145 | **0.576** | 1.222 | **1.172** |
| Rebounds | 1.160 | 1.206 | 1.134 | 1.131 |
| Assists | 0.697 | **0.465** | 1.091 | 1.105 |
| Turnovers | 0.583 | **0.339** | 0.602 | **0.436** |
| Steals | 0.280 | **0.189** | 0.313 | 0.295 |
| Blocks | 0.320 | **0.218** | 0.280 | **0.264** |

Most of the points, attempts, assists, turnovers and steals gain is box-star-stats' work; blocks are this branch's.
Rebounds moved +0.05 per 36 in the new ratings (rotation shifts from the impact change; rebound allocation is
untouched).

Tests: `tests.test_box_star_stats`, box variation, defensive alignment, box stat tiebreak, basketball accounting, box
score reconciliation, trait adapter, impact value, ratings model, fantasy draft: all pass. Core suite: 320 run, all pass except `test_settlement_materialization` (its fixture is missing in this worktree, as before).

## Open questions for the user

Left for you (coordinator: not done tonight on purpose):
1. **Legacy ties at 100.** Seven legacy players share rim_deterrence 100 (clipped when the legacy set was built), so
   the legacy card cannot order its top rim protectors. Leave legacy as it is (it is being replaced), or rebuild that
   one legacy trait unclipped from its stored components?
2. **Energy bigs** (Diabaté, Queta, Kornet): both families of impact metrics rate them top-50, the game 110th–210th.
   Nothing tested (offensive-rebounding, screening, cutting, lob-finishing terms) helped the fit. Look at how the sim
   credits screening and offensive rebounding, or accept?
3. **Blocks use the contest-jump tendency (T16).** It explains blocks well (0.87 correlation with real), but its own
   evidence is weak (role prior plus rim-contest volume). Should Basketball Index "Block Rate on Contests" feed T16
   directly, or is that mixing skill into a choice?
4. **Attack recognition (S20) has no Basketball Index measure now.** It rests on the estimator prior and nine expert
   scouting ranges. Accept, or look for a decision-quality measure (turnovers per touch, quick-decision rates)?
5. **Totals error** stays 5.63 vs 5.51 before. Accept, or should someone study how the sim sets each team's scoring
   environment (a separate task)?
6. **Ingram and Vučević** rate far above every impact measure on the card. Keep (skills shown, impact separate), or
   lean the value model harder on impact?
