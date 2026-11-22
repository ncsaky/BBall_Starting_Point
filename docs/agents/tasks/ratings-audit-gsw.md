# RATINGS-AUDIT-GSW: is Lendeborg underrated, and what does it say about the league's ratings?

_Status: **review**. Claude Opus agent, worktree branch `worktree-agent-ae9d0da15fccdd0ec`, 2026-11-22._

**TL;DR**
- **Lendeborg's own rating holds up; what was wrong is the league around him.** Every veteran started the season at
  the level he showed over the last three seasons, never carried forward a year, so old players (Horford 40, Green 36,
  Curry 38, Butler 37) started too high and young ones too low. That is now fixed for 500 veterans, from real aging
  evidence. Separately, 68 fringe players who have never played NBA minutes had been rated like established
  rotation guards; they now sit at the level such players really show.
- **Golden State after the fix:** Horford drops from 90th in the league to 131st, Green from 139th to 188th, Payton
  from 85th to 105th; Podziemski rises from 102nd to 81st. Lendeborg is unchanged at 75.4 (243rd → 225th). Scouts,
  his first 16 games and both impact measures agree he is a good, well-rounded forward without a standout skill,
  which is roughly where the game has him. Analysts rank him the best rookie, but they rank rookies, not
  rookies against veterans.
- **His 31.6 real minutes come mostly from injuries, not from the ratings.** Curry, Butler, Moody and Porziņģis are all
  out in real life. In the simulated season Curry and Porziņģis are healthy, and Lendeborg plays about 16-18 minutes
  before and after the fix. Real-stat scorecard 18/18; the betting test, which replays last season, is a hair worse
  at picking winners (expected when ratings move toward this season) and a hair better on spreads.

## 1. Golden State

### How the game rates them, and how they are really used (2026-27, through 2026-11-21)

Overall = the card number; league rank of 691; value = the game's impact per 100 possessions (offense / defense).
Real = Basketball Reference (games / starts, minutes a game, usage, true shooting, box plus-minus with its
offense / defense split). Last season's impact = Basketball Index LEBRON for 2025-26 (offense / defense).

| Player | Age | Overall (rank) before → after | Value before → after | Real 2026-27 | Box +/- (off / def) | 2025-26 impact |
|---|---:|---|---|---|---|---|
| Kristaps Porziņģis | 31 | 86.3 (11) → 85.7 (12) | +3.25/+1.67 → +3.07/+1.65 | not with team (illness) | | +2.7 (+2.2/+0.5) |
| Stephen Curry | 38 | 86.3 (12) → 84.8 (16) | +4.73/+0.20 → +4.35/+0.09 | 10/10, 26.3 min, usage 34%, TS 72% | +13.8 (+12.3/+1.5) | +3.1 (+4.3/-1.2) |
| Jimmy Butler | 37 | 84.4 (22) → 83.0 (29) | +3.25/+1.07 → +2.88/+0.97 | out (knee ligament repair) | | +3.1 (+2.9/+0.3) |
| Brandin Podziemski | 23 | 78.6 (102) → 79.3 (81) | +1.56/+0.81 → +1.75/+0.85 | 14/14, 31.9 min, 20%, 58% | +0.9 (+1.1/-0.1) | +0.2 (-0.6/+0.8) |
| Moses Moody | 24 | 78.8 (95) → 79.3 (82) | +1.12/+1.31 → +1.26/+1.33 | out (knee tendon repair) | | +0.3 (-0.3/+0.7) |
| Gary Payton II | 33 | 79.1 (85) → 78.3 (105) | +1.00/+1.55 → +0.74/+1.52 | 14/0, 13.8 min, 15%, 55% | -4.9 (-5.0/+0.1) | +1.7 (+1.3/+0.4) |
| Al Horford | 40 | 79.0 (90) → 77.5 (131) | +0.43/+2.08 → +0.00/+1.98 | 13/2, 16.9 min, 13%, 43% | -1.5 (-3.2/+1.8) | +1.0 (-0.2/+1.1) |
| De'Anthony Melton | 28 | 76.9 (148) → 76.8 (150) | +0.97/+0.84 → +0.93/+0.82 | 16/4, 22.0 min, 19%, 55% | -0.2 (-1.5/+1.3) | +0.6 (-0.2/+0.8) |
| LJ Cryer | 25 | 76.3 (185) → 76.7 (160) | +1.63/-0.05 → +1.76/-0.04 | 13/2, 11.3 min, 24%, 55% | +0.1 (+2.8/-2.7) | -1.3 (-0.1/-1.2), 292 min |
| Draymond Green | 36 | 77.2 (139) → 75.9 (188) | -0.18/+2.07 → -0.53/+2.00 | 13/13, 25.5 min, 10%, 47% | +0.0 (-2.5/+2.5) | -0.8 (-2.0/+1.3) |
| Gui Santos | 24 | 75.2 (254) → 75.7 (202) | +0.39/+0.84 → +0.53/+0.86 | 13/7, 18.9 min, 17%, 49% | -4.6 (-3.7/-0.9) | +0.1 (-0.7/+0.8) |
| **Yaxel Lendeborg** | 24 | **75.4 (243) → 75.4 (225)** | +0.49/+0.81 → +0.48/+0.81 | **16/16, 31.6 min, 27%, 57%** | **+0.6 (+1.2/-0.6)** | rookie |
| Brandon Williams | 26 | 75.0 (272) → 75.1 (239) | +1.36/-0.21 → +1.40/-0.21 | 10/1, 16.1 min, 29%, 54% | -0.9 (-0.7/-0.2) | +1.0 (+1.1/-0.1) |
| Will Richard | 23 | 73.6 (372) → 74.3 (292) | -0.27/+0.98 → -0.09/+1.01 | 15/4, 19.9 min, 15%, 64% | -1.4 (-0.8/-0.6) | -0.7 (-1.5/+0.8) |
| Charles Bassey | 25 | 73.2 (394) → 73.9 (320) | -0.36/+0.94 → -0.16/+0.97 | 14/3, 14.9 min, 20%, 71% | +0.0 (-0.3/+0.3) | -0.8 (-0.3/-0.4) |
| Seth Curry | 35 | 73.2 (390) → 71.1 (570) | +0.30/+0.28 → -0.32/+0.19 | has not played | | -0.6 (-0.3/-0.3) |
| Georges Niang | 33 | 69.5 (642) → 67.8 (673) | -0.25/-0.42 → -0.74/-0.49 | 16/2, 18.9 min, 18%, 52% | -4.3 (-2.7/-1.6) | |

Others (Ike, Toohey, Burton, Terry, Leons) moved 0-0.8 points and stay below Lendeborg.

### What the reporting says (plain paraphrase, dated)
- **Lendeborg.** Pre-draft (Jonathan Wasserman, Bleacher Report, 2026-04-07): a versatile glue forward; at Michigan
  he scored well in almost every play type, improved into a good shooter (about 42% on spot-up threes), and can guard
  both forward spots; weaknesses are limited burst and little one-on-one creation; compared with Aaron Gordon, a
  role-player outcome. Training camp (Danny Emerman, The San Francisco Standard, 2026-10-01): Steve Kerr calls him a
  connector and a really good passer who can guard bigs and wings and will play a lot. In season: No. 1 on the NBA.com
  Kia Rookie Ladder (2026-11-18), NBC Sports Bay Area and Sports Illustrated rookie rankings; 20.8 points, 39% from three
  through 14 games, but a slump of 10-for-36 in two games without Curry (NBC Sports Bay Area, 2026-11-18). Nobody
  compares him with the Warriors' veterans directly.
- **Veterans.** Curry: no decline when healthy, now out with a torn oblique (out at least two weeks). Butler and Moody:
  out after knee surgeries. Porziņģis: out indefinitely with an illness. Green: writers describe a defensive decline
  last season and an offensive liability. Horford: at 40, minutes-limited, no back-to-backs. Payton II: a
  turnover-hunter, rarely durable. Podziemski: the team's "X factor", described as an average NBA player so far.

### Verdict on Lendeborg
- **His own level is about right.** The rookie fit (ROOKIE-FIT-2) already blends his college record, scouts' board
  rank, readiness notes and a quarter weight on his first 16 games. His box plus-minus so far (+0.6) is about 1.3
  points better than the game's value of him predicts, over only 506 minutes; a quarter weight on that is
  appropriate. Scouting claims added this time (both strengths and weaknesses, six claims) leave his value unchanged:
  better passing and shooting are offset by less burst and one-on-one creation.
- **Players above him who were overrated:** the older ones. Horford, Green, Payton II, Curry and Butler all came down
  (see section 2). Green now sits only 0.5 above Lendeborg; Horford about 2 above.
- **Still above him and worth watching:** LJ Cryer. He has 292 NBA minutes; his ratings rest on a role average plus a
  tiny measured sample (his one-on-one creation sits in the top 5% of the league). Fixing that properly means
  shrinking every thin-sample player toward the level of his group, which moves about 180 players in both directions;
  left as a decision below. In the simulation the coach plays Cryer only 3 minutes anyway.
- **Coach versus ability.** Kerr starting him is a coaching view, and partly forced by injuries. The ratings should not
  chase it.

## 2. The league sweep

Sources: ESPN NBA Rank 2026 (preseason) and The Ringer Top 100 (October 2026) for 104 ranked players; Basketball Index
LEBRON (2025-26 and history back to 2010); this season's Basketball Reference box numbers (298 players with 150+
minutes; small samples, weighted by minutes).

### Pattern 1 (fixed): veterans were never carried forward a year
- Analysts' preseason rankings put young players above the game and older players below it, steadily by age:
  game rank minus analyst rank was +14 places for ages 19-21, +8 at 22-24, -8 at 31-33 and -14 at 34+.
- The cause: a veteran's inputs measure what he showed over 2023-24 to 2025-26 (most weight on the last season), and a
  new career starts on opening day with no development first. So everyone starts at a level about a season and a half
  old.
- Real evidence: Basketball Index LEBRON 2010-2026 with Basketball Reference ages (1,000+ minute seasons; checked
  three ways: a three-season blend of LEBRON, a three-season blend of box plus-minus, and Basketball Index's own
  multi-year LEBRON). From that blend to the next season's opening day, players gain about +0.5 points per 100
  possessions at 20-21 and +0.3 at 23, hold at 26-28, and lose about -0.3 at 32, -0.5 at 35 and -0.6 at 37-40 (most of
  it on offense). Half a season of change is taken off because the game's own development runs from opening day.
  Players who missed a whole season also get that season's change. Survivors only: 13-22% of older players drop out of
  the league each year, so the true decline is if anything larger.
- After: the age pattern against analysts shrinks to +5 / +2 / -2 / -5 places; overall agreement with the analysts'
  order improves slightly (rank correlation 0.716 → 0.727, average gap 16.6 → 16.3 places).
- This season's box plus-minus (small, and only players still getting minutes) does not show the old pattern clearly
  either way; after the change the 34+ group outplays its new value by about 0.7 points, driven by Curry's 263
  minutes at +13.8. Reported, not tuned.

### Pattern 2 (fixed): players with no NBA track record were rated like established rotation players
- 70 rostered veterans had no NBA minutes in the last three seasons (two-way signings, players back from Europe).
  Their skills sat at the average of established players in their listed role, so their average value (+0.81) was
  above the league median and above every group of measured bench players. A "primary ball handler" with no NBA
  minutes ranked about 150th in the league.
- Real evidence: such players, in the seasons they did reach 250 minutes (542 player-seasons 2011-2026, first-round
  picks left out), averaged -1.15 offense / -0.28 defense (LEBRON), about 1.4 points per 100 possessions below
  established players. That is an upper bound (most never got the minutes).
- After: 68 players placed at that level (their skill shape kept); they now rank around 350-440 (overall about 73).

### The biggest remaining disagreements (after the fix)
Game rates higher than analysts:
- **Rim-protecting bigs:** Clingan (game 20th of the 104 vs analysts 87th), Hartenstein (27 vs 73), Allen (31 vs 67),
  Kessler, Okongwu. The impact measures side with the game (Clingan +3.4, Hartenstein +3.6 LEBRON last season).
  Left alone; this is where Basketball Index and Nerd Sesh-style analysis disagree with the mainstream lists.
- **Older stars coming back from major injuries:** Butler (28 vs 96; knee ligament), Lillard (36 vs 68; Achilles,
  missed last season), George, Embiid. Age is now handled; the injury itself is not (see decisions).
- **Suggs** (30 vs 89): strong impact numbers, weak start this season (-4.3 in 207 minutes).

Game rates lower than analysts:
- **High-usage creators and scorers:** Brunson (39 vs 6), Jaylen Brown (51 vs 16), Trae Young (91 vs 54), Randle,
  Banchero (84 vs 34), Sengun (60 vs 31), Keyonte George, Michael Porter Jr. Their impact numbers are also below the
  analysts' view, and the game's value formula already leans 60% on analysts. Closing this needs the value formula,
  not individual ratings (see decisions).
- **Young risers:** Flagg (61 vs 28; +6.4 box plus-minus this season), Avdija (69 vs 29; +6.6), Castle. The age fix
  moved them up (Flagg 107th → 76th in the league) but not all the way.
- **Defense-first wings:** Anunoby, Brooks, McDaniels, Alexander-Walker: analysts like them more than the impact
  measures do; the game follows the measures.

## 3. What changed (files)
- `scripts/build_player_inputs.py`: new last step `project_veterans` (age projection + no-track-record level), using
  the rookies' mechanism (the game's value scale via the veteran real-impact line; one log-odds shift per side of the
  ball on technique; physical tools, tendencies and coach usage never move). Flag `--no-age-projection` skips it.
  Basketball Reference name matching now ignores Jr./II/III (it had silently skipped Butler).
- Evidence files: `data/research/age_projection_2026_27.json`, `data/research/no_track_record_level_2026_27.json`.
- `data/research/analyst_claims_2026.json`: six attributed Lendeborg claims (Wasserman, Bleacher Report; Emerman,
  The San Francisco Standard), strengths and weaknesses.
- Rebuilt `data/canonical/player_inputs_2026_27.json.gz`.
- Research script `scripts/research/ratings_audit_gsw.py` (team table, league comparison, age curve, track-record
  level, before/after, simulation minutes). Tests `tests/test_veteran_levels.py` (13).
- **How many players moved:** 568 had inputs moved (500 by age, 68 by track record); 542 of 691 cards moved by
  0.1+, 142 by 1.0+, largest 4.0 (the no-track-record guards). Rookies' inputs unchanged. No grade clipped (all
  grades stay strictly between 0 and 100). Solver: average miss 0.009 points of value; three track-record bigs
  (Dia, Aidoo, Stephens) stopped 0.2-0.4 short of their target after 12 rounds.

## 4. Short simulation (seed 17, opening day to 2026-12-20, Golden State on autopilot)

Minutes a game, same seed, committed ratings vs new ratings:

| Player | Before | After |
|---|---:|---:|
| Podziemski | 25.2 | 25.2 |
| Curry | 24.8 | 24.8 |
| Porziņģis | 23.0 | 22.7 |
| Melton | 21.4 | 21.5 |
| Green | 21.9 | 21.2 |
| Horford (17 games) | 20.6 | 21.3 |
| Payton II | 21.4 | 19.7 |
| Will Richard | 17.8 | 18.9 |
| Brandon Williams | 18.1 | 18.5 |
| Santos | 15.7 | 17.7 |
| **Lendeborg** | **17.7** | **16.2** |
| Bassey | 13.0 | 14.2 |
| Niang | 12.0 | 10.4 |
| Cryer | 3.4 | 3.4 |

The minutes barely depend on these rating changes. The simulated Warriors have Curry and Porziņģis healthy
(real: both out), and the coach spreads minutes across about eleven players. Lendeborg's real 31.6 minutes come
from a depleted roster and Kerr's choice; matching that is the coach and rotation model's job (ROOKIE-SEASON), not the
ratings'. Not tuned.

## 5. Gates

Both scorecards replay **last season (2025-26)**. The age step deliberately moves ratings toward 2026-27, so a small
cost on a 2025-26 replay is expected by construction (players who appear in that replay all have 2025-26 minutes, so
the track-record step and the Lendeborg claims do not touch it; the whole difference comes from the age step).

- **Real-stat scorecard** (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18** (before 18/18).
  Player per-36 misses, average absolute, before → after: points 1.232 → 1.216, shot attempts 0.885 → 0.883,
  threes 0.280 → 0.273, free throws 0.572 → 0.583, rebounds 0.553 → 0.559, assists 0.428 → 0.459, turnovers
  0.284 → 0.292, steals 0.192 → 0.189, blocks 0.203 → 0.197. Mixed, all small.
- **Betting test** (20 runs a game, 1,231 games, 1,018 with market odds). Last commit re-run here for seed 1001 and
  identical to the ROOKIE-FIT-2 runs on the same inputs, so those are used for seed 2001.

  | | Seed 1001 last commit | this branch | Seed 2001 last commit | this branch |
  |---|---:|---:|---:|---:|
  | Brier (market .1962) | .2043 | .2053 | .1972 | .1985 |
  | Log loss (market .5740) | .5985 | .6001 | .5813 | .5836 |
  | Spread miss vs market (points) | 4.164 | 4.129 | 3.998 | 3.972 |
  | Total miss vs market (points) | 5.626 | 5.670 | 5.758 | 5.753 |

  Spreads move slightly closer to the market; picking winners gets slightly worse (Brier +.001, log loss +.002).
  This is the expected cost of rating players for 2026-27 while replaying 2025-26 (see decision 5).
- **Core tests** (`run_core_tests.sh`) and **focused tests** (`run_tests_parallel.py --workers 2 --match
  "rating|input|estimator|analyst|evidence|rookie"`): see below.

## 6. Decisions for you
1. **Thin-sample players (Cryer's case).** Pull every player with under about 1,000 NBA minutes toward the real level
   of players with that much evidence, by how much he has played. About 180 players would move, in both directions
   (on average, measured low-minute players already sit a little below what such players show when they do play,
   so most would not fall). Worth doing?
2. **Coming back from major injuries.** Butler, Lillard, VanVleet, Irving, Haliburton and Tatum start from their
   pre-injury level (plus aging). Research says Achilles and knee-ligament tears in a player's 30s cost real ability
   beyond age. Add a measured return-from-injury step?
3. **High-usage scorers (Brunson 39th vs analysts' 6th).** The fix belongs in the value formula (how creation and
   scoring load are credited), which this task did not touch. Queue a value-model task?
4. **Aging is applied to skills, not athleticism.** The age step moves technique grades, as the rookies' step does.
   Real decline is partly physical (burst, speed). Splitting it between skills and physical tools would follow how
   the development model ages players; worth doing if you want the card's physical numbers to show age.
5. **Scorecards replay last season.** With ratings now meant for 2026-27, the betting test loses about .001 Brier on
   its 2025-26 replay. Options: accept it (recommended: the ratings should describe the season being played), or have
   the replay scorecards undo the recorded age step (each moved input carries its shift), which is validation-code
   work outside this task.

## Resume state (done)
- Worktree links (git-ignored, never commit): `.venv`, BBI `normalized*`, `raw/`, `tools/`, `captures/*`,
  `output/ratings-consensus/raw`.
- Outputs in `output/ratings-audit-gsw/` (snapshots `snapshot_before|age|v2.json`, `league_rows_*.json`, builds,
  `sim_before|sim_after`, gate logs).
