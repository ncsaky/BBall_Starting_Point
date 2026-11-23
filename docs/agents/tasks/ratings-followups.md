# RATINGS-FOLLOWUPS: the five follow-ups from the Golden State ratings audit, plus rookie involvement

Progress: 9/9 - report written, board row set to review

_Status: **review**. Claude Opus agent, worktree branch `worktree-agent-a7aab1745f3a463f5`, 2026-11-22._

**TL;DR**
- **Done and measured:** fringe players with little NBA evidence now sit where such players really play (most were
  rated too low, a few far too high: Javon Small 66th -> 214th, LJ Cryer 153rd -> 378th); 17 players coming back from
  Achilles or knee-ligament tears lose what real returning players lose (about 0.65 points per 100 possessions in the
  first season back); rookies' "how much they want the ball" now matches veterans who use the same share of plays, so
  role-player rookies stop over-scoring; and the two scorecards that replay last season now judge last season's ratings.
- **Checked and left alone, with evidence:** the value formula does not shortchange high-usage scorers (it misses them
  no more than anyone else when checked against real impact); most of the Brunson gap is that real impact numbers and
  Nerd Sesh rate them lower than ESPN and The Ringer. Physical tools: real data shows almost no extra athletic decline in
  one season, so nothing moved.
- **Gates:** real-stat scorecard 18/18 (player misses better on 7 of 9 stats); betting test slightly better at picking
  winners and spreads on both seeds, total points a little worse (section 8); core suite passes.

## 1. Thin-sample players (follow-up 1)

**What changed.** 139 veterans with 1-999 NBA minutes over the last three seasons. Before, the part of their rating their
few minutes could not settle came from the average established player in their listed role. Now their level is a
forecast measured on real history: the level such players really show the next season, plus their own measured impact
(Basketball Index LEBRON) counted by how many minutes it rests on: m / (m + 350). A player with 100 minutes keeps about a
fifth of his own number; one with 900 keeps about 70%. Each player's own age is applied on top (a 39-year-old is not
given a 24-year-old's improvement). His skill shape (which skills are strengths) is kept; physical tools, tendencies and
coach usage never move.

**The user's point about veterans who rarely play.** Tested directly, three ways (years in the league 1-2 / 3-4 / 5+,
age, years x draft round), on 733 real cases 2011-2026:
- Veterans who rarely play mostly **leave the league**: of players with 5+ years and under 1,000 minutes over three
  seasons, only 13% get 250 minutes the next season (40% of young players do).
- But the ones who do play **show the same level** as young players with the same thin record: about -1.0 points per
  100 possessions in both groups (-1.03 for 5+ years, -1.09 for 1-2 years). Splitting by years forecast no better than one
  group (checked on held-out seasons), so one group is used; the split levels are recorded in the evidence file.
- In the game, a rarely-used veteran still ends low: Garrett Temple (39, 589 minutes) 600th of 691; the extra low rank
  comes from his own numbers and his age, not from his years.

| | |
|---|---|
| Players moved | 139 (94 up, 43 down by 0.1+ overall; 109 by 1.0+) |
| Largest moves | Javon Small 80.0 -> 75.2 (66th -> 214th; 830 minutes, real impact +0.2 / -0.6); Garrett Temple 65.1 -> 71.4 (691st -> 600th) |
| Average | +0.9 overall: the game had most of them lower than their own real numbers say |
| LJ Cryer | 76.9 -> 73.5 (153rd -> 378th); value +1.83 / -0.04 -> +0.32 / +0.34 |
| Charles Bassey | 73.9 -> 74.8 (355th -> 248th) |
| Forecast check | held-out error 1.42 against 1.63 using only his own number and 1.87 using only the group |

Evidence: `data/research/thin_sample_level_2026_27.json` (method, cross-validation, group levels, who plays next season).

## 2. Coming back from an Achilles or knee-ligament tear (follow-up 2)

**Real cases.** 52 Achilles ruptures and ACL tears 2010-2026 (named in the repo's Basketball Index injury tracker
capture, plus widely reported cases of the same years, each checked against Basketball Reference minutes). For the 43
who got back to a 250-minute season, the first season back against what their level before and their age predicted:

| Group | Back | Cost in the first season back (offense / defense, points per 100 possessions) |
|---|---:|---|
| Achilles, under 30 | 11 of 11 | -0.59 / +0.07 (total -0.52 ± 0.34) |
| Achilles, 30+ | 6 of 6 | -0.34 / -0.46 (total -0.81 ± 0.26) |
| ACL, under 30 | 23 of 25 | -0.37 / -0.29 (total -0.67 ± 0.32) |
| ACL, 30+ | 3 of 3 | -0.70 / +0.08 (total -0.62 ± 0.41) |
| **Used for all** | 43 | **-0.45 / -0.20 (total -0.65)** |

The four groups differ by less than chance would give, so the pooled cost is used for everyone; age in the 30s is not
measurably worse in these cases (the age step already takes off the normal decline). Basketball Index's own matched
estimate agrees in size: ACL -0.54, Achilles -1.12 before its shrinkage. Survivors only, so if anything the cost is
understated. A player who has already played seasons since the injury carries only the share of his measured seasons
that came before it (Tatum 85%, Melton 33%).

| Player (injury, age then) | Overall before -> after | League rank |
|---|---|---|
| Jimmy Butler (ACL, 36) | 83.1 -> 81.6 | 29 -> 42 |
| Damian Lillard (Achilles, 34) | 82.1 -> 80.7 | 38 -> 58 |
| Kyrie Irving (ACL, 32) | 81.3 -> 79.9 | 48 -> 64 |
| Fred VanVleet (ACL, 30) | 78.1 -> 76.7 | 113 -> 145 |
| Tyrese Haliburton (Achilles, 24) | 88.1 -> 86.6 | 7 -> 9 |
| Jayson Tatum (Achilles, 26; 522 minutes back) | 86.7 -> 85.5 | 10 -> 12 |
| Donte DiVincenzo (Achilles, 28) | 78.2 -> 76.8 | 109 -> 142 |

17 players moved (all down; largest -1.5). It is part of the opening-day projection, so replays of last season undo it.
Evidence: `data/research/major_injury_return_2026_27.json`. The in-game injury model already applies a lasting loss
for tears that happen during a save; this covers the real ones from before the save starts.

## 3. High-usage scorers' value (follow-up 3): checked, no formula change

Checked against real impact (Basketball Index multi-year LEBRON, offense and defense separately) on the 408 players the
value formula is fitted on:
- **No bias against high usage.** By fifths of usage, creation, shooting or finishing skill, the formula misses real
  offense by at most 0.15 points per 100 possessions and real defense by at most 0.23, in both directions. High-usage
  players as a group are not under-valued.
- **Defense does not weigh too much.** Elite rim protectors are valued *below* their real defense (Wembanyama 3.5 vs
  4.2, Holmgren 3.1 vs 3.8, Gobert 2.9 vs 3.3); Jarrett Allen is the one clearly above (3.0 vs 2.1).
- **Where the gap comes from.** Among the 94 analyst-ranked veterans in the fit:

  | Player | ESPN / Ringer | Real impact (multi-year) | The game | Nerd Sesh redraft |
  |---|---:|---:|---:|---:|
  | Jalen Brunson | 6 | 26 | 36 | 22nd pick |
  | Jaylen Brown | 16 | 41 | 42 | 32nd pick |
  | Trae Young | 49 | 64 | 80 | not picked |
  | Paolo Banchero | 32 | 54 | 81 | not picked |
  | Alperen Sengun | 29 | 51 | 62 | not picked |
  | Donovan Clingan | 78 | 19 | 26 | - |

  Most of the distance to ESPN and The Ringer is real impact data itself, which the value formula follows by design
  (60% analysts, 40% impact), and the analysts closest to the user's taste (Nerd Sesh) sit near the game. The rest is
  individual: Banchero and Young sit below even their real impact because their own skill grades (shooting, handle) are
  low, which is a question about those players' ratings, not the formula.
- **Tested fixes, none justified.** Removing usage from the defensive value, splitting the analysts' gap by each
  player's own profile instead of the league's, and three ridge strengths: none moves Brunson more than 5 places, and
  the one that moves most (no usage on defense) makes the defensive fit to real impact worse (0.903 -> 0.885).
- One real fix: the value fit script now fits on 2025-26-level ratings (the opening-day projection undone, like the
  scorecards), since its targets are 2025-26 impact. The fit file itself was not refitted (it predates the projection,
  so it already matches).

Before/after against the 104 analyst-ranked players: rank agreement 0.727 -> 0.746 (mostly from the injury step);
Brunson 39th -> 37th. Lendeborg is not affected by this step.

## 4. Aging and physical tools (follow-up 4): checked, nothing moved

Real data on athletic decline within players who keep playing (`data/research/physical_aging_2026_27.json`):
- Basketball Index tracked movement speed (2013-14 to 2025-26): **no decline with age**; young players slow down as
  their roles grow, older players hold.
- Dunk share of close shots (2023-24 to 2025-26): no age pattern beyond noise.
- Blocks per minute -3% a season at 27-32; rebounds per minute -4% a season from 33; steals flat (all partly role).

Translated onto the game's physical tools, one season of that is under half a grade point, smaller than anything the
card shows. The cards already show the age gap: players 35+ sit about 3 grade points (0.7-0.9 of the league spread)
below players 23 and under in first step, speed and lateral mobility. So the age step's change stays on technique,
where the evidence puts it, and nothing physical moved.

## 5. Replays judge last season's ratings (follow-up 5)

Each opening-day step now records, on every input it moves, the value before the step. The betting test and the
real-stat scorecard (and the value fit) restore those values, so they replay 2025-26 with 2025-26-level ratings; steps
that describe a player's level (thin samples, no NBA track record) stay. A diagnostic switch undoes every step.

Checked before steps 1-4 existed, then again with all steps undone:

| | Pre-audit | Audit (projection kept) | Projection undone | Every step undone |
|---|---:|---:|---:|---:|
| Seed 1001 Brier / log loss | .2043 / .5985 | .2053 / .6001 | .2044 / .5986 | .2043 / .5985 |
| Seed 1001 spread / total miss | 4.164 / 5.626 | 4.129 / 5.670 | 4.150 / 5.687 | 4.164 / 5.624 |
| Seed 2001 Brier / log loss | .1972 / .5813 | .1985 / .5836 | .1974 / .5817 | .1972 / .5813 |
| Seed 2001 spread / total miss | 3.998 / 5.758 | 3.972 / 5.753 | 3.969 / 5.841 | 3.997 / 5.756 |
| Real-stat 18/18; points per 36 miss | 1.232 | 1.216 | 1.260 | 1.232 |

With every step undone the scorecards return to the pre-audit values (identical to the third decimal). With only the
projection undone, every player who appears in the replay has exactly his pre-audit inputs; the small remaining
difference (mostly the total miss) comes from the 68 no-track-record players and the rookies, who never play in the
replay but sit in the league-wide tables the ratings are scaled against.

## 6. Rookies' involvement on the veterans' usage scale (coordinator's step, after the shot fix merge)

**The problem.** The builder set rookies' involvement from a prospect prior that sat far above veterans (about 0.5 for
guards) lightly moved by college usage, so at 16-20% real usage rookies had 0.32 against veterans' 0.26.

**Now.** A rookie's involvement is what a veteran at his expected usage has:
1. Veterans' line: involvement against real usage, 278 veterans (correlation 0.89).
2. Expected rookie usage from college usage and draft pick, fitted on 328 real rookies 2015-16 to 2025-26 (usage =
   15.5 + 0.33 x college usage - 2.0 x log pick; error 3.5 points). Three international draftees use the average
   draftee's college usage and their own pick.
3. This season's real usage joins the forecast by how precise each is (the forecast's error against the counting noise
   of a usage share over his minutes): about 0.85-0.90 weight at 300-600 minutes, so a 2-minute 0% does nothing.

| Real usage this season | Rookies before | Rookies after | Veterans |
|---|---:|---:|---:|
| under 16% | 0.30 | 0.24 | 0.21 |
| 16-20% | 0.32 | 0.26 | 0.26 |
| 20-24% | 0.36 | 0.29 | 0.32 |
| 24-28% | 0.39 | 0.33 | 0.38 |

(These use the college forecast only; this season's usage, added in point 3, lifts the high-usage rookies further.)
The builder's level step then put every rookie back on his day-one target (largest miss 0.017 points per 100): rookies
moved -1.0 overall on average, undoing the shot fix's +0.9. Sergio de Larrea (no college line, not leveled) fell most,
74.8 -> 70.2: his old involvement (0.48) was the prior's.

**Rookie class against real classes** (`rookie_season_probe.py`, seeds 17 and 18, first season; real = 11 classes):

| | ROOKIE-SEASON after shot fix | Now | Real |
|---|---:|---:|---:|
| Points per 36 (500+ min): bottom tenth / middle / top tenth | 14.6 / 18.3 / 22.1 | 13.5 / 15.8 / 20.3 | 9.6 / 13.7 / 19.0 |
| 15+ points a game per class | 7, 6 | 4, 5 | 2.5 (range 0-4) |
| Share 10+ a game | 30% | 19% | 14% |
| Points a game, middle / top tenth | 6.1 / 15.8 | 4.9 / 14.1 | 4.2 / 12.1 |

Top rookies, points per 36 early this season (simulated vs real): Acuff 22.0 vs 24.8 (was 21.4), Wilson 19.5 vs 22.1
(19.3), Lendeborg 19.9 vs 22.4 (18.1), Peterson 18.2 vs 19.6 (22.0), Boozer 19.5 vs 19.3 (18.5). Most of the overshoot
is gone and the stars hold; the class is still about 2 points per 36 hot in the middle and 4 at the bottom, which is
no longer involvement (low-usage rookies now have veterans' involvement) and is left for the engine side.

## 7. The Warriors, gaps in real terms

Overall (league rank of 691, percentile); value per 100 possessions; the same value put in real-impact terms (the line
that links veterans' real impact to the game's value); last season's real impact; this season's box plus-minus.

| Player | Age | Overall (rank, percentile) | Value off / def | In real-impact terms | Last season real | This season box +/- |
|---|---:|---|---|---|---|---|
| Porziņģis | 31 | 85.6 (11, 98th) | +3.08 / +1.62 | +2.8 / +1.3 | +2.2 / +0.5 | out |
| Curry | 38 | 84.8 (16, 98th) | +4.36 / +0.09 | +4.4 / -0.9 | +4.3 / -1.2 | +12.3 / +1.5 |
| Butler | 37 | 83.1 -> 81.6 (29 -> 42, 94th) | +2.54 / +0.83 | +2.1 / +0.1 | +2.9 / +0.3 | out |
| Podziemski | 23 | 79.3 (81, 88th) | +1.74 / +0.85 | +1.1 / +0.2 | -0.6 / +0.8 | +1.1 / -0.1 |
| Moody | 24 | 79.2 (82, 88th) | +1.25 / +1.32 | +0.5 / +0.8 | -0.3 / +0.7 | out |
| Payton II | 33 | 78.3 (102, 85th) | +0.74 / +1.52 | -0.2 / +1.1 | +1.3 / +0.4 | -5.0 / +0.1 |
| Horford | 40 | 77.4 (128, 81st) | -0.00 / +1.98 | -1.1 / +1.8 | -0.2 / +1.1 | -3.2 / +1.8 |
| Melton | 28 | 76.8 -> 76.3 (162, 76th) | +0.81 / +0.78 | -0.1 / +0.1 | -0.2 / +0.8 | -1.5 / +1.3 |
| Green | 36 | 76.0 (173, 75th) | -0.52 / +2.02 | -1.8 / +1.9 | -2.0 / +1.3 | -2.5 / +2.5 |
| **Lendeborg** | 24 | **75.8 (185, 73rd)** | +0.54 / +0.88 | **-0.4 / +0.2** | rookie (day-one forecast -0.5 / +0.1) | +1.2 / -0.6 |
| Santos | 24 | 75.7 (188, 72nd) | +0.53 / +0.86 | -0.4 / +0.2 | -0.7 / +0.8 | -3.7 / -0.9 |
| Cryer | 25 | 76.9 -> 73.5 (153 -> 378, 45th) | +0.32 / +0.34 | -0.7 / -0.6 | -0.1 / -1.1 | +2.8 / -2.7 |

**How big the gaps really are.** The middle of the league is crowded: half the league sits between 72.7 and 75.9
overall, and 110 players are within one overall point of Lendeborg.
- **Green:** 0.2 overall and 12 places ahead; in real terms 0.3 points per 100 possessions. Lendeborg is better on
  offense by about 1.4 points per 100; Green's defense (+1.9) closes it. On real numbers they are equal, which is the
  user's read.
- **Horford:** 1.6 overall, 57 places; 0.9 per 100. Lendeborg is better on offense by 0.7, Horford's defense carries him.
- **Payton II:** 2.5 overall, 83 places; 1.1 per 100 (offense about even, Payton's defense).
- **Podziemski:** 3.5 overall, 104 places; 1.5 per 100 (the game likes Podziemski more than his real numbers do).
So a gap that reads as 50-100 league places is often under one point per 100 possessions: "about the same player" in
analysts' language. None of these steps moved Lendeborg (the value step changed nothing; his involvement rose with his
real usage, and the level step held his day-one target).

**Display suggestion (not built).** League rank exaggerates small gaps in the crowded middle. Show a percentile or a
tier instead (for example: star, starter, rotation, bench, fringe), or the value gap in plain terms ("about 0.3 points
per 100 possessions behind Green"), and keep league rank for the top 50, where gaps are wide.

## 8. Gates

- **Real-stat scorecard** (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**. Player per-36
  misses, last commit -> now: points 1.220 -> 1.206, shot attempts 0.881 -> 0.891, threes 0.275 -> 0.271, free throws
  0.578 -> 0.570, rebounds 0.570 -> 0.549, assists 0.452 -> 0.453, turnovers 0.307 -> 0.281, steals 0.190 -> 0.184,
  blocks 0.196 -> 0.189 (better on 7 of 9).
- **Betting test** (20 runs a game, 1,231 games, 1,018 with market odds; last commit = this branch's base with the
  merged shot fix, same code, last commit's inputs):

  | | Seed 1001 last commit | now | Seed 2001 last commit | now |
  |---|---:|---:|---:|---:|
  | Brier (market .1962) | .2055 | .2047 | .1987 | .1978 |
  | Log loss (market .5740) | .6007 | .5992 | .5842 | .5827 |
  | Spread miss vs market (points) | 4.155 | 4.115 | 3.986 | 3.944 |
  | Total miss vs market (points) | 5.713 | 5.721 | 5.795 | 5.875 |

  Better at picking winners and spreads on both seeds (mostly from undoing the opening-day projection in the replay);
  the total-points miss is a little worse (+0.01 and +0.08), which traces to the league-wide tables (see section 5:
  the same shift appears with only the projection undone, and vanishes when every step is undone).

- **Core suite** and **focused tests**: CORE_TESTS
- No grade clipped at 100 (all technique grades strictly between 0 and 100; checked in tests).
- All runs were on the laptop (each scorecard run about 4 minutes; the rookie probes about 4 minutes each), so Azure
  was not needed.

## 9. Decisions for the user
1. **Banchero and Trae Young** sit below even their real impact because of their own skill grades (shooting, handle).
   A ratings check of those two (not the formula) would be the next step if the gap bothers you.
2. **Display:** percentiles or tiers instead of league rank in the middle of the league (section 7).
3. **Rookie class still runs about 2 points per 36 hot in the middle.** Involvement is now on the veterans' scale, so
   this is engine-side (how low-usage players turn touches into points); worth an engine task if you want it closer.
4. Other fit scripts that fit 2025-26 data (`fit_court_influence.py`, `fit_offensive_rebounding.py`,
   `fit_playoff_translation.py`) should also pass `replay_last_season=True` the next time they are refitted.

## 10. Files
- `scripts/build_player_inputs.py`: thin-sample step, return-from-injury step, replay-undo notes on every shifted input,
  rookie involvement on the veterans' scale, name matching that ignores a same-named father.
- `src/nba_gm_data/ratings_model.py`: `replay_last_season_inputs`, `install_inputs_model(..., replay_last_season=True)`;
  `src/nba_gm_data/sim.py`: the replay branch uses it; `scripts/fit_impact_value.py`: fits on 2025-26-level ratings.
- `src/nba_gm_data/input_estimator.py`: rookie involvement evidence text.
- Evidence: `data/research/thin_sample_level_2026_27.json`, `major_injury_return_2026_27.json`,
  `physical_aging_2026_27.json`, `rookie_involvement_2026.json`. Research: `scripts/research/ratings_followups.py`.
- Rebuilt `data/canonical/player_inputs_2026_27.json.gz`. Tests: `tests/test_ratings_followups.py`.

## Resume state (done)
- Worktree links (git-ignored, never commit): `.venv`, BBI files under `data/research/bbi/`, `data/research/barttorvik`,
  `output/ratings-consensus/raw`, `output/ratings-audit-gsw/bbref`.
- Outputs in `output/ratings-followups/` (`run_gates.sh <tag>`, `summ.py <tag>`; snapshots, probes, gate logs).
