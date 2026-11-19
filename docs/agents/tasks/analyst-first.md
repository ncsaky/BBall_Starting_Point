# ANALYST-FIRST: analysts lead where they and the data disagree

Owner: Claude (Opus agent), worktree branch `worktree-agent-ae8eaf08bf6a4e1dc`. Status: **review** (committed on the
branch; not pushed or merged). Started from the ratings consensus check (`docs/agents/tasks/ratings-consensus.md`) and
the user's evidence priority (2026-11-19): analysts first, impact numbers second, read in their context.

## TL;DR

1. Two measuring mistakes are fixed for everyone: ball security now counts turnovers per play a player uses or creates
   (it counted per touch, which punished isolation scorers like Kawhi Leonard), and every Basketball Index measure now
   counts only as much as it repeats from one season to the next (noisy ones such as help-defense effectiveness used to
   decide whole ratings).
2. The Nerd Sesh hosts' skill claims (337 claims, 104 players, each with episode, date and time stamp) are now an
   explicit evidence source that leads when it disagrees with the data. Şengün's defense, the bigs' passing, Brown's
   passing, Maxey's and Cunningham's finishing now follow the analysts.
3. The game's order agrees better with the analysts in the top 50 (correlation 0.61 -> 0.68). Real stats hold 18/18;
   betting-odds accuracy is worse (Brier 0.1937 -> 0.1959, still a hair better than the market): following analysts
   moves ratings away from what the market prices, and the noise weighting costs the same-season replay. For the
   value-formula owner: Trae Young falls to about 290th (his inputs look right; the formula barely pays for elite
   passing), and its fitting target should blend analyst rankings with impact numbers.

## Resume state (done)
- [x] Worktree symlinks; baseline scorecards (18/18; Brier 0.1937 / log loss 0.5734, identical to main).
- [x] Measurement fixes (`bbi_evidence.py`, mapping v3), analyst evidence (`analyst_evidence.py`, claims file),
      rebuild, comparison, scorecards, consensus rerun, report, board row.
- Local working files (git-ignored): `output/analyst-first/` (inputs before / measures-only / after, consensus
  before / measures-only / after, a repeatability-only variant, the scorecard logs, team-margin checks, the list of every analyst-driven change). Worktree symlinks removed.

## 1. How the new evidence works

**Order of evidence** in `scripts/build_player_inputs.py`: estimator prior -> Basketball Index measures -> real dunk
data -> **analyst claims (new, last)**. Option `--no-analysts` skips the last step.

**Analyst claims** (`data/research/analyst_claims_2026.json`, read by `src/nba_gm_data/analyst_evidence.py`).
- Source: the Nerd Sesh extractions in `docs/ratings-evidence-2026-10-29/` (point guards 2026-08-05, shooting guards
  08-14, small forwards 08-19, power forwards 08-28, centers 09-02, the redraft 07-31 and opening week 10-23). Each
  claim records show, episode, video ID, date, the time range, a paraphrase in plain words (no long quotes), the inputs
  it informs, a level (elite / strong / above average / below average / weak / very weak), whether both hosts said it,
  one host, or the other host disputed it, and whether it was about the playoffs or a one-game sample.
- 15 claims are recorded but not applied, with the reason stated (vague, about team fit, or framed against the
  player's own ceiling, such as "Edwards' midrange is his growth area"). Claims about tendencies (what a player chooses
  to do, for example Mitchell's playoff "tunnel vision") and about measured body size or free-throw percentage are
  recorded only, so the four layers stay separate. Jump height is stored as a measurement prior, so "athletic" claims do
  not touch it either.
- Weights (documented in the module): both hosts 1.0, one host 0.6, disputed 0.35; playoff-only claims x0.5 (a claim
  about elite playoff defenses is only half about the season skill); one-game or opening-week claims x0.25; generic
  "bad defender" claims x0.5; a claim naming many inputs is spread across them. A general "good passer" claim informs
  the four general passing reads together.
- Each level is a one-sided band of league percentiles (praise is a floor, criticism a ceiling: "solid rim protector"
  does not say "not elite"). If the claims that agree with the current value carry at least half the weight, nothing
  changes. Otherwise the value moves toward the claim's level: analyst share = analyst weight / (analyst weight + 0.6
  for a measured input, or 0.2 for a guess). One both-hosts claim against measured data leads (63%), one host splits
  evenly. The move happens on the league's own distribution of that input, so no clipping and no value outside the
  league's existing range. No number is typed by hand.
- Result: 875 player-input pairs claimed; 555 already agreed; **306 changed (85 players; 150 up, 156 down)**.

## 2. Each contradiction: cause and fix

League percentiles among all 691 rostered players, before -> after.

| Case | What the analysts said | Cause of the disagreement | Kind | Fix and result |
|---|---|---|---|---|
| **Kawhi Leonard, ball security** | secure handler (small forwards ep., 01:32) | Turnovers were divided by touches. Isolation scorers hold the ball long and touch it rarely, so each touch looks risky. Per play he uses or creates (shots, turnovers, shot-creating passes), Kawhi is 70th-91st percentile. | measurement definition | Ball security now uses plays used or created for every player. Kawhi 18th -> 77th. Also: Gilgeous-Alexander 68 -> 99, Dončić 57 -> 96, Curry 41 -> 91, Mitchell 54 -> 95, Booker 16 -> 90. Low-usage bigs who fumble catches drop (Gobert 30 -> 2, Lively 55 -> 7). |
| **Isolation turnover rate** (main ball-security measure) | | It repeats from season to season at only 0.18 (rank correlation) and its 2025-26 column is on a different scale. | small-sample noise | Now weighted by repeatability (section 3), so it no longer decides the rating. |
| **Alperen Şengün, defense** | defense a major problem; lacks rim protection (centers ep., 00:10:48-00:16:59, critical host) | Two things. (1) His top-of-league "rotation recognition" came from help-defense effectiveness, which barely repeats (0.20): Sabonis swings from 2nd to 99th percentile between seasons on it. (2) Even among centers, Basketball Index's other measures still like him, so the rest is a real disagreement. | noise + genuine | Repeatability weighting first (rotation 100 -> 99), then the analyst claims, split into specific ones (generic defense; rim protection; processing; touch; free throws). Interior positioning 97 -> 65, contests 85 -> 50, on-ball 75 -> 41, rotation 100 -> 87 (the generic, one-host claim moves it least). |
| **Bigs as passers** (Adebayo, Giannis, Embiid, Siakam, Butler, Mobley) | good passers / creators | The passing-read measures are per-pass quality measures that depend on role and teammates: the value of the shots a player's passes create depends on who shoots them, and handoff-heavy bigs make many low-value passes. Basketball Index's own playmaking grade rates all of them above average. | context + genuine | Analyst claims now lead on the general passing reads. Adebayo connector read 8 -> 41, short-roll 4 -> 35, drive-and-kick 8 -> 41; Giannis connector 10 -> 51, pick-and-roll feed 27 -> 62, drive-and-kick 35 -> 65; Embiid post passing 32 -> 71; Butler connector 27 -> 53; Mobley reads 13-19 -> 52-56; Siakam drive-and-kick 24 -> 41. |
| **Jaylen Brown, passing** | below-average passer and decision-maker (small forwards ep., 01:21:58, one host) | His per-pass numbers are excellent (top 10%), partly because he plays beside elite shooters (teammate offense 94th-97th percentile), which raises the value of every pass. | context | Analyst claim leads: connector 65 -> 50, pick-and-roll feed 90 -> 72, drive-and-kick 88 -> 68, skip 90 -> 74, attack decisions 86 -> 53. His turnover rate stays below average (1 -> 37), as the analysts say. |
| **Tyrese Maxey, finishing** | limited at the rim over size, 52% on twos (point guards ep., 00:59:02) | And-one conversion ("contact finish rate") drove contact finishing; it repeats at only 0.11. | noise + genuine | Contact finishing 91 -> 73, layups 87 -> 62. His ball security rose (94 -> 97), as the analysts also said. |
| **Cade Cunningham, finishing and pull-up** | poor finishing inside, inconsistent pull-up (point guards ep., 01:16:54-01:25:46, both hosts) | Pull-up three percentages repeat poorly (0.27-0.29); a good pull-up season counted fully. | noise + genuine | Layups 66 -> 29, pull-up three 94 -> 61. Contact finishing rose (78 -> 94) after the and-one noise was removed: his free-throw drawing is real. |
| **Franz Wagner, handle** | elite handle and change of pace (small forwards ep., 00:51:23) | The handle input had almost no data (a guess at the 10th percentile). | missing data | Analyst claim leads (guess -> measured claim): dribble manipulation 10 -> 67; contact finishing 24 -> 74 (noise removal). |
| **Donovan Mitchell, passing** | playoff tunnel vision | It is about willingness, not seeing the play. | layer | Recorded as a tendency claim; skill unchanged (99th). |
| **Jalen Duren, screening** | good screener (centers ep., 00:17:18; redraft) | Screening has little data. | missing data | Screen execution 17 -> 56. |
| **Rookies** (Boozer, Peterson, Dybantsa) | polished / elite shooting / freak athlete | Inputs were guesses. | missing data | Analyst claims lead on guesses (weight 0.2 for the guess): Peterson pull-up and movement threes 63 -> 88; Boozer layups 37 -> 72, decisions 45 -> 79; Dybantsa driving 41 -> 92. |
| **Others moved by claims** | | | | LaMelo Ball driving 97 -> 48; Tyler Herro driving 97 -> 58; Harden attention on defense 82 -> 40; Dončić rotations 76 -> 36; Garland on-ball defense 71 -> 33; Haliburton release mechanics 94 -> 52; Tatum rotations 10 -> 48 and connector read 45 -> 81; Durant strength 89 -> 49; Avdija decisions 89 -> 49 and pull-up midrange 84 -> 47; Banchero decisions 84 -> 46. Full list: `output/analyst-first/analyst_changes.json`. |

## 3. Measures weighted by how well they repeat (applies to every player)

Each Basketball Index measure's weight is now multiplied by its season-to-season rank correlation (players with 1,000+
minutes in both seasons) divided by 0.6, capped at 1. 74 of 189 mapped measures were scaled down; the worst:
isolation free-throw drawing rate (negative, a broken column; now ignored), and-one rate 0.11, post-up impact 0.12,
off-screen points per play 0.15, isolation turnover rate 0.18, corner three percentage 0.19, help-defense effectiveness
0.20, floater percentage 0.24, drive assists per pass 0.25, cut points per play 0.26, pull-up three percentage 0.27.
Inputs known only through noisy measures now lean more on the estimate and on the analysts.
Effect of sections 2a and 3 alone (before analyst claims): 13,751 input values moved by more than half a point across
567 players; the game's order already agreed better with the analysts (top 80: 0.693 -> 0.709).

## 4. The named players: where their impact numbers come from

Impact = Basketball Index multi-year LEBRON (what the value formula is fitted to); per-season figures from the
local Basketball Index tables.

| Player | Analysts | Impact rank | Where the gap comes from | Do the inputs show what analysts credit? |
|---|---:|---:|---|---|
| **Anthony Edwards** | ESPN 7, Ringer 7, NS 14 | 43rd | Offense is elite on every measure (offensive LEBRON 96th percentile). The whole gap is defense, and mostly one season: 2025-26 defensive LEBRON 12th percentile and defensive plus-minus 4th, after average seasons before. Analysts weigh shot-making load, athleticism and playoffs; they call the defense "not the projected plus", which matches. | Yes: catch-and-shoot, pull-up three, driving, separation and free-throw drawing at the 97th-99th percentile. Game rank 15 -> 14. |
| **Jalen Brunson** | 6, 6, 22 | 29th | Offense 99th percentile; defense 3rd-6th percentile while guarding the easiest assignments (matchup difficulty 4th-6th). Impact metrics charge every point of that. Analysts value his clutch scoring and offensive engine more. | Yes: pull-up midrange 100th, driving 100th, ball security 98th, pull-up three 98th; defense low (as analysts say). The game still ranks him 57th: the value formula, not the inputs (section 6). |
| **Tyrese Maxey** | 11, 14, 24 | 30th | Offense 97th; defense 2nd-11th percentile in two of three seasons. Team context hurts his on-court numbers: teammates' offense 15th-24th percentile, and offensive luck adjustment -0.85 last season (unlucky). | Yes: speed 98th, driving 99th, pull-up midrange 97th, ball security 97th; passing low (analysts: "mediocre"). Game 26 -> 27. |
| **Jaylen Brown** | 14, 16, 32 | 46th | Box-score impact is strong (97th last season) but plus-minus models swing wildly (offense 29th one season, 91st the year before): stars beside other stars (teammate offense 94th-97th) share credit in on/off data. Turnovers cost him (12th percentile turnover impact). | Mostly: pull-up midrange 95th, finishing 90th, first step 96th; passing now average and turnovers below average, as the analysts say. Game 33 -> 36. |
| **Michael Porter Jr.** | ESPN ~61 avg | 140th | 2025-26 in Brooklyn beside the league's worst teammates (teammate offense 0th percentile), usage jumped from 43rd to 84th percentile, defense 5th-12th percentile. In Denver his numbers rode beside Jokić. | Yes for shot-making: catch-and-shoot 97th, finishing 98th; defense low. No Nerd Sesh skill claims about him. Game 162 -> 145. |
| **Cooper Flagg** | 23, 31, 29 | 259th | One season at 19 on a poor team (teammates 10th percentile, on-court net -3.8); analysts rank his projection. | Partly: athletic tools (priors) high, jumper poor (2nd percentile, analysts agree), creation middling. Game 110 -> 96. |
| **Trae Young** | 44, 64 | 81st | Only 384 minutes in 2025-26 (injury); in 2024-25 offense 98th, defense 2nd percentile. | Yes: passing reads 97th-99th, pull-up three 92nd; finishing 2nd, defense 13th, and now (analysts) turnovers 54th, driving 72nd, inside scoring 60th. **The game ranks him 292nd (was 165th)**: the value formula averages all passing reads into one group with little weight and multiplies creation skills by his very high usage, so the analysts' criticisms of his creation cost him a lot while his elite passing earns little. Inputs follow the analysts; the value formula is the problem. |

## 5. Who moved in the game's order (top 80 by analyst consensus)

Game rank before -> after (card OVR): Scottie Barnes 24 -> 15 (71.1 -> 74.8), Devin Booker 51 -> 37, Bam Adebayo
69 -> 54, OG Anunoby 58 -> 42, Pascal Siakam 66 -> 56, Franz Wagner 61 -> 40, Jimmy Butler 27 -> 19, Zion Williamson
45 -> 31, Stephon Castle 82 -> 63, Darius Garland 142 -> 111, Trey Murphy 94 -> 74, Cooper Flagg 110 -> 96, Michael
Porter Jr. 162 -> 145; down: Trae Young 165 -> 292, Alperen Şengün 37 -> 66, Domantas Sabonis 88 -> 120, Ivica Zubac
74 -> 109 and Rudy Gobert 87 -> 101 (both from the ball-security change: bigs who lose catches), Deni Avdija 99 -> 112,
Jalen Duren 46 -> 55, Jamal Murray 36 -> 44, Austin Reaves 25 -> 33, Jarrett Allen 42 -> 52. The top six are unchanged
(Jokić, Gilgeous-Alexander, Dončić, Giannis, Kawhi, Wembanyama); Edwards 15 -> 14, Mitchell 10 -> 7.

**Agreement with the analyst consensus** (`scripts/research/ratings_consensus.py`, now with `--out`):

| | Before | Measurement fixes only | After |
|---|---:|---:|---:|
| Top 50: correlation / rank correlation / median gap | 0.607 / 0.671 / 10 | 0.648 / 0.715 / 9 | **0.676 / 0.757 / 8** |
| Top 80: correlation / rank correlation / median gap | 0.693 / 0.732 / 16 | 0.709 / 0.747 / 14 | 0.618 / **0.743 / 14** |

The top-80 straight correlation drops only because of Trae Young's fall (one 240-place miss); the rank correlation
and the median gap improve at every depth.

## 6. Recommendation for the value-formula refit (not done here: `impact_value.py` belongs to another agent)

- **Blend the target.** Fit to a blend of multi-year LEBRON and the analyst consensus placed on the LEBRON scale
  (analyst order -> the LEBRON value at that rank). The user's priority suggests analysts at 50-65%. Before using the
  analyst side: remove age and injury discounts from it (analysts drop Butler, Lillard, Embiid for availability, which
  the injury model already handles; the ratings measure ability when playing), and treat rookies' projection rankings
  separately (Flagg). Keep LEBRON alone for players no analyst ranks.
- **Estimated effect** (blended-target rank; the formula tracks its target at about 0.88 correlation, so the game rank
  should land near it):

  | Player | Impact rank | Blend 50/50 | Blend 65% analysts | Game now |
  |---|---:|---:|---:|---:|
  | Anthony Edwards | 43 | 12 | 9 | 14 |
  | Jalen Brunson | 29 | 14 | 13 | 57 |
  | Tyrese Maxey | 30 | 17 | 15 | 27 |
  | Jaylen Brown | 46 | 27 | 22 | 36 |
  | Michael Porter Jr. | 140 | 76 | 70 | 145 |
  | Cooper Flagg | 259 | 67 | 51 | 96 |
  | Trae Young | 81 | 54 | 54 | 292 |
- **Credit passing properly.** Passing reads enter as one averaged group; elite passers (Young, Haliburton,
  Harden) get little for it. Give the passing group an involvement interaction like shooting and creation have.
- **Refit after this branch:** ball security and passing reads changed meaning for many players (Gobert and Zubac lost
  value through ball security; a refit would decide how much ball security is worth for a big).

## 7. Scorecards and tests

**Real-stat targets** (`calibration_report.py --games 1230 --mode replay-real-minutes`): 18/18 before and after.
Player per-36 errors improved: turnovers bias +0.11 -> -0.04 (mean miss 0.35 -> 0.31), shots -0.56 -> -0.49, true
shooting mean miss 0.028 -> 0.026, rebounds -0.14 -> -0.09. League turnovers per 100 fell 13.72 -> 13.18 (target
14.13; still in band, z -0.4 -> -1.0): ball handlers who use most possessions now rate as more secure. Jokić,
Westbrook and Giddey are now under-predicted on turnovers (shot-creating passes count in the denominator); Wembanyama's
turnover miss is gone.

**Betting odds** (`validate-season-probabilities --runs 100`, 1,231 games, 1,018 with market odds). Each step was
run separately to find the cause:

| | Brier | Log loss | Spread error | Totals error |
|---|---:|---:|---:|---:|
| Before (= main) | 0.1937 | 0.5734 | 4.500 | 5.441 |
| + repeatability weighting only | 0.1950 | 0.5763 | 4.495 | 5.438 |
| + ball security per play (both measurement fixes) | 0.1950 | 0.5760 | 4.533 | 5.498 |
| + analyst claims (this branch) | **0.1959** | **0.5786** | 4.566 | 5.472 |
| Market | 0.1962 | 0.5740 | | |

**This is a setback, stated with its causes.** Brier worsens by 0.0022 (seed-to-seed noise is about 0.0001); the game
is still slightly better than the market on Brier, now worse on log loss.
- Repeatability weighting: +0.0013 Brier. The odds test replays the 2025-26 season, the same season most of the
  Basketball Index measures come from. A measure that does not repeat from year to year still describes that one
  season (including its context and luck), so trusting it less makes the replay of that same season slightly worse,
  even though it should make next season's ratings sturdier. The test cannot reward that.
- Ball security per play: no Brier change; totals error 5.44 -> 5.50, because league turnovers fell (13.7 -> 13.2
  per 100) and scoring rose a little.
- Analyst claims: +0.0009 Brier. The market prices what the impact data says; moving ratings toward the analysts
  moves them away from the market. This is the trade the user chose; the size is now known.
- If this is too much: the repeatability weighting is one constant (`RELIABILITY_REF` 0.6 in `bbi_evidence.py`;
  lower means milder) and the analyst weights are three (`SUPPORT`, `DATA_WEIGHT`). I did not tune either to the
  scorecard.

**Team strength check** (every 2025-26 game replayed three times with real minutes; average margin per team vs the
real margin): miss 2.47 points before, 2.48 with the measurement fixes, 2.60 after the analyst claims. The claims moved
Cleveland and Minnesota further above their real margin and Indiana and Charlotte further from theirs; Houston
(Şengün) dropped from 0.6 above its real margin to 0.7 below.

**Tests:** core suite (`scripts/run_core_tests.sh`) 337 OK (2 skipped); focused player-profile, dunk evidence, input
estimator, Basketball Index overlay, analyst evidence, inputs build and ratings-model tests 118 OK (2 skipped); value
model and adapter 17 OK. New tests: `tests/test_analyst_evidence.py` (claim leads but keeps the scale, agreeing claim
changes nothing, weights by support/context/specificity, guesses move further than measured values, tendency and
free-throw claims recorded only, playmaking claims spread over the passing reads, claims file attributed and
paraphrased); in `tests/test_bbi_evidence.py` ball security per play, repeatability weighting and the mapping check.
Full suite not run (no save or engine code changed).

## Files

- `src/nba_gm_data/analyst_evidence.py` (new), `data/research/analyst_claims_2026.json` (new),
  `tests/test_analyst_evidence.py` (new).
- `src/nba_gm_data/bbi_evidence.py` (repeatability weighting; summed exposure), `data/research/bbi/bbi_input_mapping.json`
  (ball security per play used or created), `tests/test_bbi_evidence.py`.
- `scripts/build_player_inputs.py` (analyst step, `--no-analysts`), `scripts/research/ratings_consensus.py` (`--out`),
  `scripts/research/prospect_input_audit.py` (shared exposure helper).
- Rebuilt `data/canonical/player_inputs_2026_27.json.gz`, `data/canonical/tendency_scale_map.json` and the generated
  tables in `docs/agents/tasks/e2-input-estimator.md`.
