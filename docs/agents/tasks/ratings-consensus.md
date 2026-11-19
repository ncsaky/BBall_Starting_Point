# RATINGS-CONSENSUS: analyst baseline for the 94-input ratings

Owner: Claude (Opus agent), worktree branch `worktree-agent-a1d66c99cf9218da0`. Status: **review** (committed on the
branch; not pushed or merged). User notes that started it: `docs/agents/tasks/ratings-review-notes-2026-11-19.md`.

## TL;DR

1. Analysts and Basketball Index's impact numbers both agree with you that Jokić, Wembanyama and Gilgeous-Alexander are
   a near-tied top three. The game gets Jokić and Gilgeous-Alexander right but undervalues Wembanyama: its value formula
   averages all 14 defensive skills, so it cannot give elite rim protection its full worth (Holmgren, Adebayo, Gobert,
   Mobley suffer the same way). Edwards is different: analysts rank him ~7th, his impact numbers ~45th; the game sits at 15th.
2. Fixed with real data (separate commit): dunk ratings now come from real dunk counts (Curry, Dončić, Jokić drop far;
   athletic dunkers rise); pull-up, movement and deep-three ratings no longer trust a handful of attempts (Ausar Thompson's
   pull-up three 50 -> 30); and a unit bug that scrambled every free-throw rating is gone (Amen Thompson 42 -> 75%).
3. The card now shows the game's own value on a straight line, so gaps are real gaps. That makes Wembanyama and Edwards
   look further from the top until the value formula is fixed (a job for the value-model owner). Both scorecards held
   (18/18 real-stat targets; betting-odds accuracy slightly better).

## Resume state (done)
- [x] Worktree symlinks; public rankings (ESPN, Ringer) and Nerd Sesh lists parsed (raw files in `output/ratings-consensus/raw/`).
- [x] Consensus script `scripts/research/ratings_consensus.py` -> `output/ratings-consensus/consensus.json`.
- [x] Diagnosis, claim check (`output/ratings-consensus/claim_contradictions.md`), data gaps, card change, scorecards.
- Coordinator: copy `output/ratings-consensus/` from this worktree into the main checkout's `output/` before removing
  the worktree (the consensus script reads the raw ranking files from there; ESPN/Ringer lists are not committed).

## 1. The consensus baseline

Sources, recorded per player in `output/ratings-consensus/consensus.json`:
- **ESPN NBA Rank 2026** (top 100, panel of 7, 2026-09-24, espn.com/story/_/id/50015167; ranks 50-11 from the ABC7
  syndicated copy, matching TSN).
- **The Ringer Top 100** (snapshot 2026-10-14, theringer.com/nba-ranked/top-100).
- **Nerd Sesh**: the 48-pick redraft of current players (2026-07-31) and the five position top-10 lists (Aug-Sep 2026),
  parsed from the extractions in `docs/ratings-evidence-2026-10-29/` (raw transcripts checked where the extraction was
  ambiguous; two extraction-doc errors found: the point-guard order of Haliburton/Maxey and swapped lists in the centers doc).
- **Basketball Index impact** (local only): the six-metric impact consensus already used by the ratings audit (LEBRON,
  DPM, DRIP, RAPTOR and two RAPM versions, three seasons, 1,000+ minutes), plus multi-year LEBRON itself, which is the
  exact number the game's value formula is fitted to.
- No public 2026-27 tier list from Basketball Index, Taylor Metrics or Nerd Sesh exists beyond the above (a 2024
  Basketball Index mid-season list by Taylor Wyman was found but is two seasons old).

Consensus rank = order of the mean of the ranks each player has among ESPN, Ringer, the Nerd Sesh redraft and the
Basketball Index impact rank (missing from a top-100 list counts as 110; not drafted or not enough minutes = no entry).
It is a diagnostic only: no rating was moved toward it.

Columns: Cons = consensus rank; NS pos = Nerd Sesh position and average rank in that position; BBI impact = rank in
the six-metric impact consensus; Real LEBRON = rank by multi-year LEBRON (what the game's value formula tries to
predict); Engine fit = rank by the game's predicted value; Game = the game's order (card, tables and AI all use it);
Card OVR = the new straight-line card; Tables = the number tables show; Gap = game rank minus consensus rank (+ = game
lower than consensus). After this branch's input changes.

| Cons | Player | ESPN | Ringer | NS redraft | NS pos | BBI impact | Real LEBRON | Engine fit | Game | Card OVR | Tables | Gap |
|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Nikola Jokić | 1 | 2 | 2 | C 2 | 1 | 1 | 1 | 1 | 97.8 | 77.9 | +0 |
| 2 | Victor Wembanyama | 2 | 1 | 1 | C 1 | 5 | 2 | 6 | 6 | 83.7 | 73.5 | +4 |
| 3 | Shai Gilgeous-Alexander | 3 | 3 | 3 | PG 1 | 3 | 3 | 2 | 2 | 93.7 | 76.2 | -1 |
| 4 | Giannis Antetokounmpo | 5 | 5 | 4 | PF 1 | 2 | 5 | 4 | 4 | 84.5 | 73.7 | +0 |
| 5 | Luka Dončić | 4 | 4 | 5 | PG 2 | 6 | 4 | 3 | 3 | 92.1 | 74.2 | -2 |
| 6 | Kawhi Leonard | 15 | 8 | 7 | SF 1 | 4 | 6 | 5 | 5 | 83.9 | 73.6 | -1 |
| 7 | Jayson Tatum | 9 | 10 | 10 | PF 2 |  | 9 | 12 | 11 | 75.7 | 71.9 | +4 |
| 8 | Stephen Curry | 12 | 11 | 6 | PG 3.5 | 17 | 24 | 11 | 12 | 76.7 | 71.9 | +4 |
| 9 | Cade Cunningham | 8 | 9 | 8 | PG 3.5 | 38 | 8 | 8 | 8 | 79.4 | 73.1 | -1 |
| 10 | Scottie Barnes | 17 | 18 | 9 | PF 3 | 24 | 31 | 24 | 24 | 71.1 | 68.8 | +14 |
| 11 | Donovan Mitchell | 10 | 12 | 40 | SG 2 | 9 | 11 | 10 | 10 | 78.6 | 72.5 | -1 |
| 12 | Karl-Anthony Towns | 16 | 13 | 12 | C 3 | 32 | 20 | 36 | 35 | 68.6 | 67.5 | +23 |
| 13 | Tyrese Haliburton | 19 | 17 | 21 | PG 7 |  |  | 9 | 9 | 79.2 | 72.7 | -4 |
| 14 | Chet Holmgren | 24 | 28 | 16 | C 6 | 8 | 7 | 23 | 23 | 71.3 | 69.0 | +9 |
| 15 | Anthony Edwards | 7 | 7 | 14 | SG 1 | 50 | 43 | 15 | 15 | 73.3 | 71.2 | +0 |
| 16 | Kevin Durant | 13 | 15 | 11 | SF 2 | 40 | 49 | 16 | 16 | 73.1 | 70.3 | +0 |
| 17 | Evan Mobley | 26 | 24 | 19 | PF 4.5 | 20 | 12 | 34 | 34 | 68.8 | 67.5 | +17 |
| 18 | Devin Booker | 20 | 19 | 15 | SG 3 | 35 | 37 | 50 | 51 | 65.8 | 66.2 | +33 |
| 19 | LeBron James | 18 | 21 | 26 | PF 4.5 | 26 | 26 | 7 | 7 | 79.5 | 73.4 | -12 |
| 20 | Jalen Brunson | 6 | 6 | 22 | PG 5 | 58 | 29 | 55 | 55 | 64.6 | 65.8 | +35 |
| 21 | Bam Adebayo | 28 | 26 | 25 | C 6 | 19 | 13 | 69 | 69 | 62.5 | 64.7 | +48 |
| 22 | Jalen Williams | 25 | 25 | 27 | SF 5 |  | 40 | 19 | 19 | 72.8 | 69.4 | -3 |
| 23 | OG Anunoby | 34 | 20 | 13 | PF 7 | 36 | 47 | 59 | 58 | 64.1 | 65.6 | +35 |
| 24 | Derrick White | 47 | 43 | 18 | SG 4 | 11 | 10 | 14 | 14 | 74.4 | 71.5 | -10 |
| 25 | Tyrese Maxey | 11 | 14 | 24 | PG 6.5 | 71 | 30 | 25 | 26 | 71.0 | 68.6 | +1 |
| 26 | Pascal Siakam | 29 | 30 | 28 | PF 6 | 34 | 61 | 65 | 66 | 63.0 | 64.9 | +40 |
| 27 | Joel Embiid | 41 | 39 | 20 | C 4.5 | 22 | 18 | 13 | 13 | 74.8 | 71.7 | -14 |
| 28 | Amen Thompson | 31 | 40 |  | SF 9 | 23 | 51 | 32 | 32 | 69.4 | 67.8 | +4 |
| 29 | LaMelo Ball | 35 | 33 | 17 | PG 9 | 44 | 16 | 40 | 40 | 68.0 | 67.1 | +11 |
| 30 | Rudy Gobert | 42 | 45 | 31 | C 7.5 | 13 | 39 | 86 | 87 | 61.1 | 62.3 | +57 |
| 31 | James Harden | 32 | 37 | 37 |  | 28 | 15 | 47 | 47 | 66.3 | 66.4 | +16 |
| 32 | Franz Wagner | 45 | 42 | 35 | SF 6.5 | 15 | 36 | 60 | 61 | 63.8 | 65.5 | +29 |
| 33 | Jaylen Brown | 14 | 16 | 32 | SF 3 | 87 | 46 | 33 | 33 | 69.1 | 67.6 | +0 |
| 34 | Jalen Duren | 33 | 46 | 30 | C 9.5 | 45 | 14 | 46 | 46 | 66.6 | 66.5 | +12 |
| 35 | Anthony Davis | 40 | 38 |  | C 6 |  | 27 | 21 | 22 | 71.6 | 69.3 | -13 |
| 36 | Kyrie Irving | 39 | 41 |  |  |  |  | 30 | 29 | 69.7 | 68.0 | -7 |
| 37 | Jamal Murray | 21 | 23 |  |  | 80 | 45 | 35 | 36 | 68.6 | 67.3 | -1 |
| 38 | Ausar Thompson | 59 | 61 |  |  | 14 | 44 | 51 | 50 | 65.6 | 66.2 | +12 |
| 39 | Austin Reaves | 37 | 36 |  | SG 5 | 63 | 56 | 26 | 25 | 70.7 | 68.6 | -14 |
| 40 | De'Aaron Fox | 43 | 56 |  |  | 39 | 33 | 20 | 21 | 72.6 | 69.3 | -19 |
| 41 | Lauri Markkanen | 49 | 34 | 46 | SF 7 | 56 | 71 | 31 | 31 | 69.6 | 67.9 | -10 |
| 42 | Deni Avdija | 27 | 27 |  | SF 7 | 86 | 38 | 97 | 99 | 60.2 | 61.2 | +57 |
| 43 | Paul George | 67 | 65 | 38 |  | 21 | 53 | 18 | 18 | 72.8 | 69.8 | -25 |
| 44 | Aaron Gordon | 64 | 52 | 23 |  | 52 | 115 | 66 | 65 | 63.0 | 64.9 | +21 |
| 45 | Jalen Johnson | 22 | 22 |  | PF 10 | 109 | 50 | 53 | 52 | 64.9 | 66.1 | +7 |
| 46 | Desmond Bane | 52 | 49 | 41 | SG 6.5 | 65 | 70 | 80 | 80 | 61.7 | 63.2 | +34 |
| 47 | Alex Caruso | 84 | 68 | 48 | SG 7 | 10 | 66 | 43 | 43 | 66.9 | 66.8 | -4 |
| 48 | Jarrett Allen | 63 | 70 |  |  | 25 | 28 | 42 | 42 | 66.9 | 66.8 | -6 |
| 49 | Alperen Sengun | 30 | 35 |  |  | 94 | 58 | 37 | 37 | 68.5 | 67.3 | -12 |
| 50 | Dylan Harper | 50 | 47 | 34 | PG 8 | 83 | 148 | 58 | 59 | 64.2 | 65.6 | +9 |
| 51 | Isaiah Hartenstein | 74 | 75 |  |  | 12 | 22 | 28 | 28 | 70.2 | 68.4 | -23 |
| 52 | Jaren Jackson Jr. | 53 | 44 | 33 | PF 8 | 85 | 76 | 41 | 41 | 67.8 | 66.9 | -11 |
| 53 | Trae Young | 44 | 64 |  |  |  | 81 | 167 | 165 | 56.1 | 57.9 | +112 |
| 54 | Kon Knueppel | 48 | 48 | 36 | SG 9 | 100 | 156 | 90 | 89 | 60.6 | 62.1 | +35 |
| 55 | Domantas Sabonis | 58 | 60 |  |  |  | 41 | 88 | 88 | 60.9 | 62.3 | +33 |
| 56 | Ivica Zubac | 66 | 55 |  | C 9.5 | 59 | 85 | 74 | 74 | 62.1 | 64.2 | +18 |
| 57 | Cason Wallace | 75 | 73 |  | SG 8 | 37 | 55 | 148 | 147 | 57.3 | 58.9 | +90 |
| 58 | Ajay Mitchell | 79 | 74 |  | SG 6 | 33 | 54 | 123 | 123 | 58.8 | 60.0 | +65 |
| 59 | Cooper Flagg | 23 | 31 | 29 | SF 4 | 169 | 259 | 110 | 110 | 59.2 | 60.7 | +51 |
| 60 | Jrue Holiday | 82 | 79 | 47 |  | 48 | 91 | 63 | 64 | 63.3 | 65.3 | +4 |
| 61 | Stephon Castle | 38 | 29 | 43 | PG 9 | 148 | 104 | 82 | 82 | 61.6 | 62.8 | +21 |
| 62 | Payton Pritchard | 70 | 71 |  |  | 54 | 42 | 56 | 57 | 64.6 | 65.7 | -5 |
| 63 | Mikal Bridges | 61 | 67 |  | SF 10 | 69 | 77 | 93 | 92 | 60.4 | 62.0 | +29 |
| 64 | Jaden McDaniels | 56 | 50 | 44 | SF 9 | 113 | 343 | 79 | 79 | 61.8 | 63.3 | +15 |
| 65 | Damian Lillard | 69 | 66 |  |  |  |  | 29 | 30 | 70.0 | 68.0 | -35 |
| 66 | Jimmy Butler III | 92 |  |  | SF 8 | 7 | 25 | 27 | 27 | 70.5 | 68.5 | -39 |
| 67 | Donovan Clingan | 95 | 85 |  |  | 29 | 21 | 38 | 39 | 68.3 | 67.2 | -28 |
| 68 | Zion Williamson | 51 | 54 |  | PF 9.5 | 104 | 60 | 44 | 45 | 66.8 | 66.7 | -23 |
| 69 | Jalen Suggs | 98 | 87 |  |  | 30 | 57 | 22 | 20 | 71.5 | 69.3 | -49 |
| 70 | Dyson Daniels |  | 89 |  |  | 18 | 35 | 118 | 117 | 58.9 | 60.2 | +47 |
| 71 | Draymond Green | 93 |  | 42 |  | 49 | 178 | 111 | 114 | 59.1 | 60.4 | +43 |
| 72 | Paolo Banchero | 36 | 32 |  |  | 154 | 62 | 153 | 153 | 56.8 | 58.3 | +81 |
| 73 | Darius Garland | 62 | 59 |  | PG 10 | 102 | 78 | 142 | 142 | 57.6 | 59.2 | +69 |
| 74 | Trey Murphy III | 57 | 53 |  | SF 10 | 114 | 103 | 92 | 94 | 60.4 | 61.9 | +20 |
| 75 | Josh Hart | 89 | 76 |  |  | 66 | 68 | 113 | 115 | 59.1 | 60.4 | +40 |

- Top 80 by consensus: rank correlation with game order 0.693; median absolute rank gap 16
- Consensus vs real multi-year LEBRON order: 0.585 (n=76); game order vs engine fit order identical: False

## 2. Biggest mismatches and their causes

Three causes show up. (a) an input lacks evidence or is wrong; (b) the card's display formula; (c) the engine's value
formula (`impact_value.py`: a straight-line fit from the ratings to Basketball Index multi-year LEBRON, cross-validated
correlation 0.88; it then orders every player for the AI). Numbers are impact per 100 possessions (LEBRON units).

**Game too low**

| Player | Consensus | Game | Real LEBRON (rank) | Game's predicted value | Cause |
|---|---:|---:|---|---:|---|
| Victor Wembanyama | 2 | 6 | +7.66 (2nd) | +5.53 | (c) Defense predicted +2.37 vs real +4.19. The value formula reads defense as the average of 14 defensive skills; Wembanyama is 100th percentile on interior positioning, contests, rotations and help, but average on screen navigation and steals, so the average hides him. Rim deterrence carries only a small separate weight. |
| Bam Adebayo | 21 | 70 | +4.59 (13th) | +2.53 | (c) same defense compression (real +2.49, predicted +1.57) and offense under (+2.10 real vs +0.92). Also a claim mismatch: analysts call him a creator, his passing-read inputs are bottom-10%. |
| Chet Holmgren | 14 | 24 | +5.73 (7th) | +3.74 | (c) defense +3.83 real vs +2.27 predicted. |
| Rudy Gobert, Evan Mobley | 30 / 17 | 87 / 34 | +3.3 / +4.6 | +2.3 / +3.5 | (c) Among the 12 most interior-skilled players, 8 are under-predicted on defense (by +0.4 to +1.8); the miss grows with how far a player's interior skills sit above his own defensive average (correlation 0.19, 101 players). Clingan and Hartenstein are under-predicted the same way, though the game still ranks them above the analysts. |
| Jalen Brunson | 20 | 55 | +3.94 (29th) | +2.83 | (c) offense predicted +4.0 vs real +5.0; plus analysts (ESPN/Ringer 6th) rate him far above his impact numbers. |
| Deni Avdija, Paolo Banchero | 42 / 72 | 96 / 152 | +3.31 / +2.76 | +2.21 / +1.73 | (c) offense under-predicted by ~1 point each. Analysts (ESPN 27 / 36) are higher than impact data too. |
| Cason Wallace, Dyson Daniels | 57 / 70 | 148 / 117 | +2.93 / +3.54 | +1.77 / +2.03 | (c) guard defense under-predicted (Wallace +2.67 real vs +1.92); offense also under. |
| Karl-Anthony Towns, Scottie Barnes, Pascal Siakam, OG Anunoby, Devin Booker | 12 / 10 / 26 / 23 / 18 | 36 / 25 / 65 / 58 / 51 | +4.3 / +3.8 / +2.8 / +3.2 / +3.4 | +3.4 / +3.8 / +2.6 / +2.7 / +3.0 | Mostly analysts above the impact data (Barnes, Siakam, Booker), with modest (c) under-prediction for Towns and Anunoby. |
| Trae Young, Michael Porter Jr., Nickeil Alexander-Walker, Cooper Flagg, Jaylen Brown | 53 / 77 / 76 / 59 / 33 | 169 / 164 / 156 / 109 / 36 | 81st / 140th / 118th / 259th / 46th | | Analysts vs data: the impact numbers agree with the game, not the analysts (Flagg is a 19-year-old projection). Young is also under-predicted by 0.8 (c). Human taste needed. |

**Game too high**

| Player | Consensus | Game | Real LEBRON (rank) | Game's predicted value | Cause |
|---|---:|---:|---|---:|---|
| Jalen Suggs, Paul George, Austin Reaves, De'Aaron Fox | 69 / 43 / 39 / 40 | 21 / 19 / 26 / 20 | +2.9 / +3.0 / +2.9 / +3.6 | +3.8 / +4.0 / +3.7 / +4.0 | (c) the value formula over-predicts by about one point each. Not traced to a single input. |
| LeBron James | 19 | 9 | +4.04 (26th) | +4.86 | (c) over-predicted by 0.8; analysts also discount age 41. |
| Jimmy Butler, Damian Lillard, Isaiah Hartenstein, Joel Embiid | 66 / 65 / 51 / 27 | 27 / 29 / 28 / 13 | 25th / none / 22nd / 18th | | Data agrees with the game; analysts discount age, injury and availability (Butler 37, Lillard's Achilles, Embiid's knees). The ratings measure ability when playing; availability is the injury model's job. |

**Where the user's four notes land**
- *Top tier spacing (Jokić 97.8, SGA 92.8, Wembanyama 87.2).* Two causes. (b) The old card turned the AI's number into
  a league rank and then into 50 + 15z, so places 1, 2 and 3 always showed about 97.8, 92.9 and 90.3 however close they
  were. (c) Wembanyama really is ranked 5th-7th by the engine, ~2 points of impact below his real value (defense).
- *Edwards 80.1 too low.* Not an input or card error: his impact numbers rank him ~45th (multi-year LEBRON +3.25), the
  engine predicts +4.03 (15th). Analysts (ESPN and Ringer 7th, Nerd Sesh SG #1) rank him much higher. Human taste question.
- *Shooting sub-skills.* Fixed for the evidence part (section 4). Jokić's movement three stays high (75.6, was 80.4):
  there is no movement-three measurement for anyone, and his catch-and-shoot accuracy is genuinely good (38%, 45% and 40% over the last three seasons, per Basketball Index).
- *Dunks.* Fixed with real dunk data (section 4).
- *Giannis drive-and-kick.* His drive passing quality is above average (drive-assist per pass 61st-66th percentile)
  but he kicks out less often per drive than most (22nd-25th percentile); "does a lot of it" comes from how often he
  drives (85th-87th percentile drives). The rating (34th percentile) is pulled down by the shared all-passing measures.
  Left unchanged: it is a judgement about which passing measures should count, not missing data. Listed for the user.

## 3. Analyst claims vs ratings

About 110 specific skill claims from the Nerd Sesh episodes were checked against the matching inputs; about 65 agree.
The full table (28 rows, with episode and timestamp) is `output/ratings-consensus/claim_contradictions.md`; it was built
before the free-throw fix (Amen Thompson's free throws are now 75%, matching the claim). The cross-video index and the
dossiers hold almost no skill claims (team context, contracts, injuries). The strongest contradictions:

1. **Alperen Şengün**: called a major defensive problem; every defensive skill is top-quarter on data (rotation reading 100th percentile).
2. **Kawhi Leonard**: called a secure ball handler; handle security is 18th percentile. Cause found: ball security is
   measured as turnovers per touch, which penalizes isolation scorers whose touches are mostly dribble attacks.
3. **Franz Wagner**: called an elite handler and finisher; his handle is a pure guess at the 10th percentile, contact finishing 23rd.
4. **Bam Adebayo / Giannis / Embiid / Siakam / Butler / Zion**: called good passers or creators; passing-read inputs
   are below average for all. Biggest cluster: the passing-read measures favour guards who make many shot-creating passes.
5. **Jaylen Brown**: called a below-average passer; four passing reads sit at the 88th-91st percentile (the opposite).
6. **Tyrese Maxey and Cade Cunningham**: called limited finishers (Cunningham's pull-up also called a limiter); their
   finishing and pull-up inputs are top-quarter or better.
7. **Donovan Mitchell**: "tunnel vision, declining passing"; passing reads 97th-99th percentile (may belong in pass willingness, a tendency).
8. **Jalen Duren**: praised as a screener; screen execution 17th percentile.
9. **Rookies (Boozer, Peterson, Dybantsa)**: "elite" shooting/athleticism claims against inputs that are almost all guesses.

None of these were changed: each needs a measurement decision (which data should define the skill), not a hand edit.

## 4. Data added and who moved (commit 1)

All through the existing pipeline (`scripts/build_player_inputs.py`), each with its own evidence entry and confidence.

**a. Dunks (new).** Basketball-Reference season shooting and totals pages for 2023-24 to 2025-26 (public; fetched once
with curl, raw pages in `output/ratings-consensus/raw/`, compact table committed as
`data/research/bref_shooting_2024_2026.json`, parser `scripts/research/bref_shooting.py`). New module
`src/nba_gm_data/public_shot_evidence.py`: dunk attempts per attempt within 3 feet, compared with the players closest
in height, wingspan and weight (the approved model defines dunk execution as skill *when a dunk is available*; size
belongs to the physical layer), blended with the old estimate by sample size. 553 players measured.
Players moved by more than half a point: 537. The ones you named and other stars: Stephen Curry 49 -> 24, Luka Dončić 63 -> 15, Nikola Jokić 64 -> 15, Shai Gilgeous-Alexander 57 -> 25, Giannis Antetokounmpo 63 -> 58, Victor Wembanyama 69 -> 50, Anthony Edwards 59 -> 70, Ausar Thompson 53 -> 78, Rudy Gobert 62 -> 71, Amen Thompson 55 -> 81.
Biggest drops among rotation players: Nikola Jokić 64 -> 15, Luka Dončić 63 -> 15, James Harden 60 -> 13, Joel Embiid 68 -> 22, Desmond Bane 54 -> 13, Jalen Brunson 53 -> 12, Josh Giddey 57 -> 17, Pascal Siakam 57 -> 18, Karl-Anthony Towns 63 -> 25, LaMelo Ball 56 -> 20.
Biggest rises: VJ Edgecombe 50 -> 78, Amen Thompson 55 -> 81, Cason Wallace 46 -> 72, Ausar Thompson 53 -> 78, OG Anunoby 52 -> 77, Trey Murphy III 53 -> 76, Devin Vassell 49 -> 71, Brandon Miller 51 -> 70, Ja Morant 54 -> 69, Jalen Duren 60 -> 74.
Limitation recorded on each record: vertical leap has no measurement in the model, so this score still carries some
leaping ability (the jump input was left alone; it needs its own evidence).

**b. Shot-type threes and midrange: sample size.** Basketball Index's pull-up, off-screen and deep shooting measures were
weighted by minutes only, so a pull-up percentage on a dozen attempts (or one shrunk to the league average) counted as
much as one on 400. Now each such measure is weighted by attempts of that type (attempts / (attempts + 40); deep
threes + 80), and the player's overall three-point or jump-shot talent stays as the fallback. Catch-and-shoot threes
(the main mode) are unchanged. The movement-three rating also lost a measure that counted layups and dunks on assisted
shots (that is why lob-finishing bigs and Giannis looked like movement shooters) and now uses catch-and-shoot and
overall three-point accuracy, plus off-screen scoring weighted by off-screen volume.
- Pull-up three: 488 players moved; down: Ausar Thompson 50 -> 30, Collin Murray-Boyles 60 -> 42, Domantas Sabonis 55 -> 42, Isaiah Hartenstein 34 -> 22, Jalen Duren 30 -> 19, Draymond Green 50 -> 40; up: Karl-Anthony Towns 44 -> 51, Nickeil Alexander-Walker 37 -> 44, Lauri Markkanen 41 -> 47, Dylan Harper 22 -> 29, Jaren Jackson Jr. 31 -> 37, OG Anunoby 36 -> 42.
- Movement three: 509 players moved; down: Alperen Sengun 44 -> 23, Jalen Duren 52 -> 31, Evan Mobley 56 -> 37, RJ Barrett 53 -> 37, Josh Hart 58 -> 42, Giannis Antetokounmpo 50 -> 35; up: OG Anunoby 35 -> 60, Ryan Rollins 52 -> 70, VJ Edgecombe 33 -> 51, Paul George 52 -> 68, Karl-Anthony Towns 56 -> 71, Toumani Camara 32 -> 46.
- Deep range: 496 players moved; down: Ausar Thompson 52 -> 38, Jarrett Allen 41 -> 30, Isaiah Hartenstein 31 -> 25, Dylan Harper 64 -> 59, Amen Thompson 36 -> 32, Ayo Dosunmu 69 -> 66; up: Nickeil Alexander-Walker 36 -> 43, Zion Williamson 29 -> 35, OG Anunoby 37 -> 42, Ajay Mitchell 24 -> 28, Giannis Antetokounmpo 26 -> 30, De'Aaron Fox 30 -> 34.
- Pull-up midrange: 493 players moved; down: Ivica Zubac 67 -> 47, Jarrett Allen 53 -> 40, Collin Murray-Boyles 53 -> 40, Zion Williamson 77 -> 65, Onyeka Okongwu 55 -> 46, Jalen Duren 56 -> 50; up: Draymond Green 19 -> 31, Rudy Gobert 15 -> 23, Cason Wallace 30 -> 36, Aaron Gordon 37 -> 43, OG Anunoby 21 -> 25, Chet Holmgren 55 -> 58.
- Movement midrange: 521 players moved; down: Rudy Gobert 41 -> 19, Evan Mobley 57 -> 36, Collin Murray-Boyles 48 -> 31, Jarrett Allen 41 -> 26, Giannis Antetokounmpo 50 -> 37, Donovan Clingan 42 -> 29; up: Scottie Barnes 28 -> 52, Jalen Williams 46 -> 65, Paul George 42 -> 61, Ryan Rollins 38 -> 55, VJ Edgecombe 34 -> 49, Mikal Bridges 51 -> 66.
- Players from your notes (catch-and-shoot / pull-up / movement three): Ausar Thompson 21/50/34 -> 21/30/20; Giannis Antetokounmpo 40/25/50 -> 40/27/35; Nikola Jokić 80/65/80 -> 80/66/76; Victor Wembanyama 56/47/62 -> 56/49/51; Stephen Curry 87/90/86 -> 87/89/84; AJ Green 88/84/70 -> 88/84/80.
- Poor catch-and-shoot shooters (below 35, 104 players): pull-up three minus catch-and-shoot three averaged +6.6 before, +1.7 after.

**c. Free throws (bug fix).** The free-throw input is stored as a real free-throw percentage, but the Basketball Index
overlay blended a 0-100 percentile grade into it, so every value was a mix of two units (Amen Thompson, a 78% shooter
last season, showed 42; Giannis 24; Gobert 19). Now the overlay skips it and the value is the recency-weighted,
sample-shrunk real percentage.
All 548 measured players changed (mean change 14.9). Examples (shown value, now a real FT%): Amen Thompson 42 -> 75, Giannis Antetokounmpo 24 -> 65, Rudy Gobert 19 -> 61, Luka Dončić 55 -> 78, Nikola Jokić 69 -> 81, Stephen Curry 95 -> 90, Shai Gilgeous-Alexander 90 -> 88.

**d. Also in the rebuild:** listed height and weight for 11 deep-bench players that were filled into the universe
earlier (missing-measurements task) but never rebuilt into the inputs (e.g. Carson Cooper, Christoph Tilly).

**Effect on the game's order:** small. The value formula reads group averages of skills, so most players moved a few
places; the largest moves within the top 120 are listed below. Agreement of the game's order with the six-metric
impact consensus: 0.817 before and after. Note: the value formula was fitted when dunks were guesses and free throws
were scrambled; refitting it (value-model owner) would let these corrected inputs count properly.
Largest order changes (game rank before -> after): VJ Edgecombe 132 -> 108, Ryan Rollins 126 -> 111, Desmond Bane 68 -> 80, Stephon Castle 94 -> 82, Aaron Gordon 76 -> 65, Josh Hart 104 -> 115, Deni Avdija 89 -> 99, Dyson Daniels 127 -> 117, LaMelo Ball 31 -> 40, OG Anunoby 65 -> 58, Amen Thompson 38 -> 32, Jalen Johnson 58 -> 52, Franz Wagner 56 -> 61, Alex Caruso 48 -> 43. The top 10 holds the same players; Wembanyama 5 -> 6 (his predicted value moved 0.08 and Kawhi Leonard passed him by 0.05), LeBron 9 -> 7, Cunningham 7 -> 8.

## 5. The card's overall number (commit 2)

What the card showed: not the 94-input composite its old docstring described, but the AI's own overall
(`save.player_attribute_summary`), which is already the fitted value mapped by league rank onto the old summary scale,
then mapped by league rank again onto 50 + 15z. Two rank steps: real value gaps were thrown away twice, and the
top three always read about 97.8 / 92.9 / 90.3 whatever the evidence. The tables show the first step's number
(Jokić 77.9), which is the same order on a different scale.

Options considered:
1. Keep the rank display. Can never show a near-tie at the top.
2. Plain 50 + 15z of the value. Jokić would show about 126: the stars are 4-5 standard deviations above a typical player.
3. **Chosen: a straight line through the engine's own value** (`player_profile._ImpactLine`): league median player = 50,
   league best = the same ~97.8 the rank display gave the best, everything else on the line, nothing capped (a player who
   improves past the best keeps rising). Grounded in the value the AI actually uses (impact per 100 possessions fitted to
   Basketball Index LEBRON), not tuned to any ranking; same order as before, so card and AI still agree (rule 4).
   OFF and DEF use the offensive and defensive halves of the same value.
4. A composite of the 94 inputs. Rejected: the engine never reads it, so it would show a number the AI doesn't use.

What the user now sees (before -> after): 

| Game rank | Player | Card OVR before -> after | OFF / DEF after | Tables (unchanged scale) |
|---:|---|---|---|---:|
| 1 | Nikola Jokić | 97.8 -> 97.8 | 96.1 / 69.3 | 77.9 |
| 2 | Shai Gilgeous-Alexander | 92.8 -> 93.7 | 94.8 / 60.8 | 76.2 |
| 3 | Luka Dončić | 90.3 -> 92.1 | 97.8 / 48.4 | 74.2 |
| 4 | Giannis Antetokounmpo | 88.6 -> 84.5 | 82.3 / 67.2 | 73.7 |
| 5 | Kawhi Leonard | 86.2 -> 83.9 | 80.4 / 70.5 | 73.6 |
| 6 | Victor Wembanyama | 87.2 -> 83.7 | 73.0 / 89.3 | 73.5 |
| 7 | LeBron James | 84.1 -> 79.5 | 79.1 / 60.8 | 73.4 |
| 8 | Cade Cunningham | 85.2 -> 79.4 | 79.5 / 59.6 | 73.1 |
| 9 | Tyrese Haliburton | 84.1 -> 79.2 | 89.0 / 34.0 | 72.7 |
| 10 | Donovan Mitchell | 83.1 -> 78.6 | 82.8 / 48.6 | 72.5 |
| 11 | Jayson Tatum | 81.7 -> 75.7 | 79.6 / 48.5 | 71.9 |
| 12 | Stephen Curry | 82.5 -> 76.7 | 82.4 / 43.9 | 71.9 |
| 15 | Anthony Edwards | 80.1 -> 73.3 | 76.7 / 49.1 | 71.2 |
| 14 | Derrick White | 80.7 -> 74.4 | 67.6 / 76.7 | 71.5 |
| 50 | Ausar Thompson | 72.0 -> 65.6 | 49.9 / 97.8 | 66.2 |
| 87 | Rudy Gobert | 67.3 -> 61.1 | 47.2 / 91.8 | 62.3 |
| 43 | Alex Caruso | 72.4 -> 66.9 | 55.2 / 87.3 | 66.8 |
| 55 | Jalen Brunson | 71.7 -> 64.6 | 79.6 / 16.0 | 65.8 |

Bench players also compress toward the middle (the worst player shows about 25 instead of 2), because in value terms
they really are closer to the median than the stars are.

If the value formula's defense is fixed, Wembanyama (real +7.66 vs Jokić +7.72) would sit within about a point of
Jokić on this card; the rank display could never show that. The table number (77.9 for Jokić) is unchanged and is
still a different scale for the same order; unifying it means changing the summary in `save.py` (not this task).

**What I'd change in the value formula (not done; `impact_value.py` belongs to another agent):**
- Split the defense predictor into interior (contact, interior positioning, contests, rotations, off-ball coverage),
  perimeter (containment, screen navigation, closeouts, steals) and help/team groups, so a specialist's elite skills
  are not averaged away; or let rim deterrence enter non-linearly. Expected effect: Wembanyama, Holmgren, Adebayo,
  Gobert, Mobley, Clingan up 0.5-2 points of value.
- Refit after this branch's input corrections (dunks and free throws changed meaning).
- Look at the over-predicted group (Suggs, George, Reaves, Fox, LeBron: about +1 each); a likely cause is involvement x
  skill terms that reward high usage with good technique grades more than their real impact.

## 6. Scorecards and tests

**Betting odds** (`validate-season-probabilities --runs 100`, new ratings, 1,231 games, 1,018 with market odds). The
"before" row is main's published number for this commit (not re-run here):

| | Brier | Log loss | Spread error | Totals error |
|---|---:|---:|---:|---:|
| Main (before) | 0.1941 | 0.5744 | 4.546 | 5.465 |
| This branch | **0.1937** | **0.5734** | **4.500** | **5.441** |
| Market | 0.1962 | 0.5740 | | |

All four improved slightly (the ratings audit measured seed-to-seed noise near 0.0001 Brier, so this is small but real).

**Real-stat targets** (`calibration_report.py --games 1230 --mode replay-real-minutes`, new ratings; before re-run in
this worktree): 18/18 league metrics within band both before and after. Per-36 player bias barely moved (points
-0.50 -> -0.51, shots -0.52 -> -0.56, turnovers +0.10 -> +0.11, true shooting +0.004 -> +0.005; mean absolute errors
within 0.04). Largest single misses are the same names (AJ Green's shooting, Wembanyama's blocks 2.58 -> 2.38 per 36
vs 3.79 real, Ausar Thompson's steals, Draymond Green's turnovers). Older ratings: nothing here touches them (the
changed inputs and card only apply to the 94-input ratings).

Other checks: agreement of the game's order with the six-metric Basketball Index impact consensus 0.817 before and
after; top-80 rank correlation with the analyst consensus 0.697 -> 0.693 (median gap 18 -> 16 places).

**Tests:** core suite (`scripts/run_core_tests.sh`) 337 OK (2 skipped); focused player-profile, inputs build, Basketball Index overlay, dunk evidence, input estimator, ratings model and value model tests 114 OK (2 skipped). Full suite not run (no save or engine code changed).
New tests: `tests/test_public_shot_evidence.py` (dunk size-peer comparison, open scale, missing-file guard, attempt
weighting, free-throw unit guard, data file shape) and a card test in `tests/test_player_profile.py` (header is a
straight line through the engine's value: median 50, best equals the old top value, equal gaps).

## 7. Questions for the user (casual-fan quick answers)

1. **Edwards:** analysts rank him top 7; his on-court impact numbers rank him about 45th. Should the game follow the
   analysts or the impact numbers for players like him (also Brunson, Maxey, Jaylen Brown, Flagg)?
2. **Dunk rating meaning:** it now means "dunks more than players his size" (Giannis about 58, Wembanyama about 50,
   Amen and Ausar Thompson about 80). Or should it mean "how often he dunks", which mostly rewards height?
3. **Jokić's movement three (about 76):** nobody's movement threes are measured; his catch-and-shoot is genuinely good.
   Should a slow center's movement shooting sit well below his standing shooting by default?
4. **Giannis drive-and-kick:** he kicks out of drives less often than most, but his kick-outs become assists at an
   above-average rate. Should the passing rating reward how often, or only how well?
5. **Alperen Şengün:** analysts call his defense a big problem; the defensive data rates his reads and positioning highly. Who's right?
6. **Kawhi Leonard:** is he a secure ball handler (analysts) or turnover-prone per touch (data)? We think the data is
   unfair to isolation scorers; OK to measure ball security per dribble attack instead?
7. **Bam Adebayo, Giannis, Embiid, Siakam, Butler:** analysts call them good passers; the passing reads rate them below average. Agree with the analysts?
8. **Jaylen Brown:** analysts call him a below-average passer; the data rates his reads top 10%. Agree with the analysts?
9. **The new card scale:** do you prefer gaps that match the game's value (current), even though bench players bunch up in the 30s-50s?
