# UNUSED-RATINGS: which of the 94 ratings the game actually uses, and wiring in the ones that matter

_Claude (Opus agent), 2026-11-19, branch `worktree-agent-a54069f3bec04132d`. Rules 1, 2, 4, 7 and 9 apply. No player's ratings were changed._

**TL;DR**
- Of the 94 player ratings, 9 had no effect at all on the game (screen setting, the screen/roll/pop habit, strength, jumping, shooting-mode habit, pace habit, cutting habit, rebound pursuit habit, steal gambling) and 3 more (the defensive-rebounding skills) only nudged the player-value number: the rebounds a player got ignored them.
- Now wired in, each fitted to real data: screening skill and habits drive a new screen-assists stat (matches real screen assists, correlation 0.84) and the "Screening" rating shown on the player page; the rebounding skills drive each player's rebounds (correlation with real 0.85 -> 0.94); shot-difficulty tolerance decides how much of a team's hot or cold shooting night lands on a player, which brings tough-shot scorers back toward their real efficiency (Ingram true shooting .628 -> .591, real .573).
- Both scorecards hold: real stats 18/18 (player rebound error 1.14 -> 0.70 per 36, true-shooting error .026 -> .025); betting odds Brier 0.1958 / log loss 0.5782 (main 0.1959 / 0.5786; market 0.1962 / 0.574). Speed unchanged (the full 1,230-game replay takes 16.4 s, was 16.6 s).

## Resume state

Done; ready for review. One commit on this branch (code, tests, scripts, this report, board row); not pushed or merged. Scratch scripts and outputs: `output/unused-ratings/` (git-ignored): `sensitivity.py` (the sweep), `sensitivity_before.json/.txt`, `sensitivity_after.json/.txt`, `calib_before/after.json/.txt`, `split_check.py`, `ts_residuals.py`, `ts_regress.py`, `miss_stages*.py`, `screen_check.py`, `screen_facet_scale.py`, `usage_table.py` (builds the table below), `odds_after.txt`. Worktree data symlinks (`.venv`, Barttorvik, sqlite, injury evidence, Basketball Index files, settlement folder) are untracked and were removed before the commit.

## How the audit was done

- **Code tracing.** The 94 ratings reach the game four ways: (1) the 15 older "blended" ratings the engine still runs on, each a weighted mix of inputs (`trait_adapter.ADAPTER_SPEC`); (2) box-score rates read straight from the inputs (`box_rates.py`: points share, turnovers, assists, steals, free throws; `defense.contest_jump_share`: blocks); (3) the fitted player-value model (`impact_value.py`), which reads grouped skill averages and involvement and sets each player's weight in team strength as well as his overall rating and trade value; (4) display only (the player card).
- **Sensitivity sweep** (`output/unused-ratings/sensitivity.py`). For 120 rotation players (every other player in the minutes ranking, so no team is bumped wholesale) each input was raised by 15 grade points (habits: x1.3; habit mixes: +10 points of share for each option in turn; body sizes: +5%), their blended ratings were re-derived exactly as development does, and the same 400 games were replayed with real minutes. Recorded: the change in each team's points per game, how many of the 400 winners flipped, and the bumped players' box-score rates. Same seed, so any change is caused by the bump (the unbumped run reproduces exactly).
- **Categories:** (a) read directly by the game; (b) reaches the game only through a blended rating or the player-value model, with its share; (c) valuation or display only; (d) unused.

Note on development: growth and aging move only inputs that feed a blended rating (plus involvement). Inputs outside the blend never change over a career: before this task that was screen setting, the three defensive-rebounding skills, steal technique (on-ball and passing-lane), foul control, strength and jumping, and every habit except involvement. See "Remaining gaps".

## The 94 inputs: what reaches the game

Columns: the blended ratings an input feeds (its share of each); what reads it directly; category before -> after; sweep result (average change in a team's points per game / winners flipped out of 400 / biggest change in the bumped players' per-36 box rates).

| Input | Blended ratings it feeds (share of that rating) | Read directly | Category before -> after | Sweep before: team pts / winner flips / biggest box change | Sweep after |
|---|---|---|---|---|---|
| P01 Height | rim protection 14%, playoff translation 2% | NEW: rebounds | b -> a | 0.99 / 10 / points 0.06 | 1.06 / 11 / rebounds 0.34 |
| P02 Wingspan | rim protection 4%, offensive rebounding 4%, playoff translation 2% | NEW: rebounds | b -> a | 0.27 / 4 / fga 0.05 | 0.23 / 5 / rebounds 0.07 |
| P03 Standing reach | playoff translation 2% | - | b -> b | 0.03 / 0 / no box change | 0.01 / 0 / fga 0.01 |
| P04 Body mass | playoff translation 2% | NEW: screen assists, screening rating | b -> a | 0.00 / 0 / no box change | 0.04 / 0 / screen_assists 0.24 |
| P05 Acceleration / first step | rim pressure 5%, foot speed 25%, screen navigation 15% | - | b -> b | 0.48 / 6 / fga 0.03 | 0.43 / 5 / ftm 0.03 |
| P06 Straight-line speed | foot speed 15% | - | b -> b | 0.28 / 4 / fga 0.03 | 0.32 / 3 / ftm 0.02 |
| P07 Lateral mobility / change of direction | foot speed 45%, screen navigation 15% | - | b -> b | 0.99 / 8 / rebounds 0.05 | 0.95 / 8 / rebounds 0.05 |
| P08 Functional strength | - | - | d -> d | 0.00 / 0 / no box change | 0.00 / 0 / no box change |
| P09 Physical balance / stability | handle 5% | - | b -> b | 0.03 / 0 / assists 0.01 | 0.02 / 0 / fga 0.01 |
| P10 Vertical / jump capacity | - | - | d -> d | 0.00 / 0 / no box change | 0.00 / 0 / no box change |
| P11 Conditioning | stamina 60% | - | b -> b | 0.34 / 1 / fga 0.03 | 0.32 / 1 / points 0.03 |
| P12 Recovery between efforts | stamina 40% | - | b -> b | 0.20 / 0 / fga 0.03 | 0.17 / 0 / assists 0.01 |
| S01 Catch-and-shoot three-point execution | shot release 10%, three-point range/volume 10%, shot versatility 5%, portability 20%; player value (shooting group) | - | b -> b | 2.53 / 34 / fg3a 0.33 | 2.50 / 34 / fg3a 0.33 |
| S02 Pull-up three-point execution | shot release 10%, three-point range/volume 10%, shot versatility 15%; player value (shooting group) | - | b -> b | 2.85 / 38 / fg3a 0.39 | 2.75 / 38 / fg3a 0.39 |
| S03 Movement three-point execution | shot release 10%, three-point range/volume 5%, shot versatility 5%; player value (shooting group) | - | b -> b | 1.91 / 27 / fg3a 0.23 | 1.89 / 27 / fg3a 0.23 |
| S04 Catch-and-shoot midrange execution | shot versatility 5%; player value (shooting group) | - | b -> b | 0.17 / 1 / points 0.02 | 0.14 / 1 / points 0.02 |
| S05 Pull-up midrange execution | shot versatility 15%; player value (shooting group) | - | b -> b | 0.35 / 2 / points 0.03 | 0.28 / 2 / points 0.03 |
| S06 Movement midrange execution | shot versatility 5%; player value (shooting group) | - | b -> b | 0.13 / 1 / assists 0.02 | 0.13 / 1 / points 0.02 |
| S07 Free-throw execution | three-point range/volume 5%; player value (shooting group) | - | b -> b | 2.21 / 34 / fg3a 0.31 | 2.20 / 33 / fg3a 0.31 |
| S08 Release / preparation technique | shot release 30%; player value (shooting group) | - | b -> b | 1.65 / 27 / fg3a 0.22 | 1.59 / 26 / fg3a 0.21 |
| S09 Distance-extension technique | three-point range/volume 15%; player value (shooting group) | - | b -> b | 2.90 / 44 / fg3a 0.45 | 2.85 / 44 / fg3a 0.45 |
| S10 Layup / close-touch execution | shot versatility 5%, rim pressure 5%, playoff translation 5%; player value (finishing group) | points share | a -> a | 1.28 / 11 / points 0.66 | 1.20 / 10 / points 0.65 |
| S11 Floater / short-paint touch | shot versatility 10%, playoff translation 5%; player value (finishing group) | - | b -> b | 0.30 / 2 / fga 0.02 | 0.22 / 1 / rebounds 0.02 |
| S12 Dunk execution | rim pressure 5%, playoff translation 5%; player value (finishing group) | - | b -> b | 0.28 / 1 / rebounds 0.02 | 0.22 / 1 / rebounds 0.03 |
| S13 Aerial catch-to-finish execution | rim pressure 5%, playoff translation 5%; player value (finishing group) | - | b -> b | 0.66 / 5 / fga 0.05 | 0.60 / 5 / points 0.05 |
| S14 Receiving / catch control | portability 10%, playoff translation 5%; player value (finishing group) | - | b -> b | 0.08 / 0 / fga 0.02 | 0.03 / 0 / fga 0.01 |
| S15 Contact finishing technique | rim pressure 5%, playoff translation 5%; player value (finishing group) | - | b -> b | 0.34 / 1 / points 0.03 | 0.33 / 1 / points 0.02 |
| S16 Dribble manipulation | handle 20%, playoff translation 5%; player value (creation group) | turnovers | a -> a | 0.56 / 5 / turnovers 0.16 | 0.54 / 6 / turnovers 0.16 |
| S17 Handle security | handle 25%, playoff translation 5%; player value (creation group) | turnovers | a -> a | 0.42 / 2 / turnovers 0.34 | 0.32 / 1 / turnovers 0.34 |
| S18 Perimeter separation craft | handle 10%, playoff translation 5%; player value (creation group) | - | b -> b | 0.22 / 0 / points 0.02 | 0.18 / 0 / points 0.02 |
| S19 Driving craft | rim pressure 10%, playoff translation 5%; player value (creation group) | - | b -> b | 0.83 / 6 / points 0.06 | 0.74 / 5 / points 0.05 |
| S20 Attack recognition | handle 10%, passing 10%, basketball IQ 15%, playoff translation 5%; player value (creation group) | - | b -> b | 0.52 / 2 / points 0.04 | 0.44 / 2 / points 0.04 |
| S21 Post establishment / sealing | playoff translation 5%; player value (post group) | - | b -> b | 0.09 / 0 / points 0.01 | 0.06 / 0 / points 0.01 |
| S22 Post moves / counters | playoff translation 5%; player value (post group) | - | b -> b | 0.15 / 1 / points 0.02 | 0.08 / 0 / points 0.01 |
| S23 Post-specific finish execution | playoff translation 5%; player value (post group) | - | b -> b | 0.13 / 1 / assists 0.01 | 0.08 / 0 / points 0.01 |
| S24 Foul-drawing craft | rim pressure 15%, playoff translation 5%; player value (creation group) | free throws | a -> a | 1.01 / 8 / fta 0.52 | 0.95 / 8 / fta 0.51 |
| S25 Cutting-route execution | portability 10% | - | b -> b | 0.04 / 0 / turnovers 0.01 | 0.02 / 0 / fga 0.01 |
| S26 Relocation / shooting-route execution | portability 10% | - | b -> b | 0.04 / 0 / turnovers 0.01 | 0.02 / 0 / no box change |
| S27 Screen execution | - | NEW: screen assists, screening rating, team offence | d -> a | 0.00 / 0 / no box change | 0.05 / 0 / screen_assists 0.30 |
| S28 Screen-action recognition | passing 5%, basketball IQ 10% | NEW: screen assists, screening rating, team offence | b -> a | 0.63 / 4 / fga 0.06 | 0.62 / 4 / screen_assists 0.61 |
| S29 Offensive rebound reading / pursuit technique | offensive rebounding 32%; player value (rebounding group) | - | b -> b | 0.59 / 4 / rebounds 0.25 | 0.45 / 2 / fga 0.06 |
| S30 Defensive rebound reading / positioning | -; player value (rebounding group) | NEW: rebounds | b (value only) -> a | 0.04 / 0 / turnovers 0.01 | 0.03 / 0 / rebounds 0.29 |
| S31 Box-out technique | -; player value (rebounding group) | NEW: rebounds | b (value only) -> a | 0.04 / 0 / turnovers 0.01 | 0.03 / 0 / rebounds 0.59 |
| S32 Rebound control | -; player value (rebounding group) | NEW: rebounds | b (value only) -> a | 0.04 / 0 / turnovers 0.01 | 0.03 / 0 / rebounds 0.28 |
| S33 On-ball containment technique | foot speed 15%, portability 15%; player value (defence group) | - | b -> b | 0.19 / 3 / assists 0.02 | 0.17 / 3 / ftm 0.02 |
| S34 Contact resistance / leverage technique | screen navigation 15%; player value (defence group) | - | b -> b | 0.24 / 4 / assists 0.02 | 0.15 / 3 / ftm 0.01 |
| S35 Screen-navigation technique | screen navigation 55%, portability 10%; player value (defence group) | - | b -> b | 0.54 / 7 / fga 0.03 | 0.45 / 6 / ftm 0.03 |
| S36 Interior positioning | rim protection 23%; player value (defence group) | - | b -> b | 1.36 / 12 / points 0.07 | 1.30 / 11 / points 0.07 |
| S37 Contest technique | rim protection 52%, playoff translation 1%; player value (defence group) | - | b -> b | 1.85 / 15 / points 0.14 | 1.91 / 17 / points 0.14 |
| S38 Rotation recognition | basketball IQ 15%, rim protection 7%; player value (defence group) | - | b -> b | 0.37 / 4 / blocks 0.02 | 0.30 / 4 / rebounds 0.03 |
| S39 Off-ball coverage positioning | basketball IQ 12%, portability 10%; player value (defence group) | - | b -> b | 0.25 / 1 / points 0.02 | 0.18 / 0 / fga 0.02 |
| S40 Closeout / arrival control | defensive effort 15%, playoff translation 1%; player value (defence group) | - | b -> b | 0.26 / 3 / points 0.02 | 0.30 / 3 / ftm 0.03 |
| S41 Defensive anticipation | defensive effort 10%; player value (defence group) | - | b -> b | 0.20 / 4 / assists 0.02 | 0.23 / 4 / ftm 0.02 |
| S42 On-ball steal technique | -; player value (defence group) | steals | a -> a | 0.07 / 0 / steals 0.10 | 0.04 / 0 / steals 0.10 |
| S43 Passing-lane interception technique | playoff translation 1%; player value (defence group) | steals | a -> a | 0.08 / 0 / steals 0.19 | 0.04 / 0 / steals 0.18 |
| S44 Attention / responsibility execution | defensive effort 25%, basketball IQ 12%, playoff translation 1%; player value (defence group) | - | b -> b | 0.64 / 5 / assists 0.05 | 0.61 / 5 / rebounds 0.04 |
| S45 Foul-control technique | playoff translation 1%; player value (defence group) | - | b -> b | 0.08 / 0 / fga 0.02 | 0.04 / 0 / steals 0.01 |
| S46 Defensive communication | defensive effort 10%, basketball IQ 11%, playoff translation 1%; player value (defence group) | - | b -> b | 0.19 / 2 / assists 0.01 | 0.16 / 1 / fga 0.02 |
| F01.recognition Connector / swing / reversal — recognition | passing 4%, basketball IQ 3%, playoff translation 1%; player value (pass-reading group) | - | b -> b | 0.27 / 1 / fga 0.02 | 0.15 / 0 / assists 0.02 |
| F01.execution Connector / swing / reversal — execution | passing 2%, portability 15% | assists (passing delivery) | a -> a | 0.17 / 1 / assists 0.18 | 0.10 / 1 / assists 0.17 |
| F02.recognition Post entry — recognition | passing 4%, basketball IQ 3%, playoff translation 1%; player value (pass-reading group) | - | b -> b | 0.23 / 1 / fga 0.02 | 0.13 / 0 / assists 0.02 |
| F02.execution Post entry — execution | passing 2% | assists (passing delivery) | a -> a | 0.05 / 0 / assists 0.16 | 0.03 / 0 / assists 0.15 |
| F03.recognition Pocket / roll feed — recognition | passing 4%, basketball IQ 3%, playoff translation 1%; player value (pass-reading group) | - | b -> b | 0.23 / 1 / fga 0.02 | 0.13 / 0 / assists 0.02 |
| F03.execution Pocket / roll feed — execution | passing 2% | assists (passing delivery) | a -> a | 0.08 / 0 / assists 0.17 | 0.05 / 0 / assists 0.15 |
| F04.recognition Lob — recognition | passing 4%, basketball IQ 3%, playoff translation 1%; player value (pass-reading group) | - | b -> b | 0.23 / 1 / fga 0.02 | 0.13 / 0 / assists 0.02 |
| F04.execution Lob — execution | passing 2% | assists (passing delivery) | a -> a | 0.05 / 0 / assists 0.16 | 0.03 / 0 / assists 0.15 |
| F05.recognition Short-roll playmaking — recognition | passing 4%, basketball IQ 3%, playoff translation 1%; player value (pass-reading group) | - | b -> b | 0.23 / 1 / fga 0.02 | 0.13 / 0 / assists 0.02 |
| F05.execution Short-roll playmaking — execution | passing 2% | assists (passing delivery) | a -> a | 0.08 / 0 / assists 0.17 | 0.04 / 0 / assists 0.15 |
| F06.recognition Drive-and-kick — recognition | passing 4%, basketball IQ 3%, playoff translation 1%; player value (pass-reading group) | - | b -> b | 0.23 / 1 / fga 0.02 | 0.13 / 0 / assists 0.02 |
| F06.execution Drive-and-kick — execution | passing 2% | assists (passing delivery) | a -> a | 0.08 / 0 / assists 0.17 | 0.05 / 0 / assists 0.15 |
| F07.recognition Skip / cross-court — recognition | passing 4%, basketball IQ 3%, playoff translation 1%; player value (pass-reading group) | - | b -> b | 0.23 / 1 / fga 0.02 | 0.13 / 0 / assists 0.02 |
| F07.execution Skip / cross-court — execution | passing 2% | assists (passing delivery) | a -> a | 0.05 / 0 / assists 0.16 | 0.03 / 0 / assists 0.15 |
| F08.recognition Post playmaking — recognition | passing 4%, basketball IQ 3%, playoff translation 1%; player value (pass-reading group) | - | b -> b | 0.23 / 1 / fga 0.02 | 0.13 / 0 / assists 0.02 |
| F08.execution Post playmaking — execution | passing 2% | assists (passing delivery) | a -> a | 0.09 / 0 / assists 0.17 | 0.04 / 0 / assists 0.15 |
| F09.recognition Transition / outlet / advance — recognition | passing 4%, basketball IQ 3%, playoff translation 1%; player value (pass-reading group) | - | b -> b | 0.23 / 1 / fga 0.02 | 0.13 / 0 / assists 0.02 |
| F09.execution Transition / outlet / advance — execution | passing 2% | assists (passing delivery) | a -> a | 0.13 / 1 / assists 0.17 | 0.10 / 1 / assists 0.17 |
| T01 Shoot / drive / pass / post / reset choices | rim pressure 15%, passing 15% | points share (shoot/pass), assists (pass/post) | a -> a | 2.76 / 36 / points 1.98 | 2.76 / 37 / points 1.98 |
| T02 Shot-location preferences | shot release 25%, three-point range/volume 55%, rim pressure 20% | - | b -> b | 3.86 / 52 / fg3a 0.65 | 3.86 / 51 / fg3a 0.65 |
| T03 Shooting-mode preferences | - | - | d -> d | 0.00 / 0 / no box change | 0.00 / 0 / no box change |
| T04 Shot difficulty tolerance | shot versatility 10% | NEW: how much of the team's hot or cold shooting lands on him (efficiency) | b -> a | 0.29 / 1 / assists 0.03 | 0.24 / 1 / fga 0.15 |
| T05 Pace / early-attack preference | - | - | d -> d | 0.00 / 0 / no box change | 0.00 / 0 / no box change |
| T06 Dribble / possession persistence | handle 10% | - | b -> b | 0.07 / 1 / assists 0.01 | 0.03 / 0 / fga 0.01 |
| T07 Passing risk appetite | - | turnovers, assists (box score only) | a -> a | 0.00 / 0 / turnovers 0.57 | 0.00 / 0 / turnovers 0.57 |
| T08 Offensive involvement preference | shot versatility 25%, rim pressure 15%, handle 20%, passing 15% | points share, turnovers, assists, free throws; player value | a -> a | 3.33 / 39 / points 2.64 | 3.24 / 39 / points 2.63 |
| T09 Cutting frequency | - | - | d -> d | 0.00 / 0 / no box change | 0.00 / 0 / no box change |
| T10 Relocation / off-ball movement frequency | shot release 15% | - | b -> b | 1.04 / 12 / fg3a 0.15 | 1.01 / 12 / fg3a 0.14 |
| T11 Screen / roll / pop / slip preferences | - | NEW: screen assists, screening rating, team offence (screen and roll shares) | d -> a | 0.00 / 0 / no box change | 0.04 / 0 / screen_assists 0.18 |
| T12 Offensive crash versus retreat | offensive rebounding 64% | NEW: rebounds | b -> a | 0.87 / 4 / rebounds 0.43 | 0.82 / 5 / rebounds 0.57 |
| T13 Defensive pursuit versus box-out emphasis | - | NEW: rebounds (pursue share) | d -> a | 0.00 / 0 / no box change | 0.00 / 0 / rebounds 0.03 |
| T14 Steal / disruption gamble frequency | - | - | d -> d | 0.00 / 0 / no box change | 0.00 / 0 / no box change |
| T15 Help commitment | defensive effort 15% | - | b -> b | 0.46 / 5 / fga 0.03 | 0.40 / 4 / rebounds 0.04 |
| T16 Contest commitment / stay-down preference | - | blocks (jump share; box score only) | a -> a | 0.00 / 0 / blocks 0.38 | 0.00 / 0 / blocks 0.38 |
| T17 Effort allocation | defensive effort 25% | - | b -> b | 0.71 / 9 / fga 0.04 | 0.65 / 8 / points 0.04 |
| T18 Contact-seeking preference | - | points share, free throws | a -> a | 0.91 / 10 / fta 3.26 | 0.89 / 10 / fta 3.25 |

**Plain-language summary of the table**
- **Unused before (no effect at all):** screen setting, the screen/roll/pop/slip habit, strength, jumping, catch vs pull-up vs movement shooting habit, pace habit, cutting habit, rebound pursuit vs box-out habit, steal gambling.
- **Box score only (never moves a score):** passing risk appetite (assists and turnovers), contest style (blocks).
- **Barely used:** defensive-rebounding positioning, box-out and rebound control (only through the player-value model's rebounding average; rebounds themselves ignored them); standing reach and body mass (2% of playoff translation); cutting and relocation routes (10% of portability each); foul control (only the value model's defence average; fouls ignore it); receiving.
- **Heavily used:** three-point shooting skills and the three-point share of shots (they set three-point volume), involvement, shoot/pass choices, contact seeking, interior defence and contest technique, lateral speed.
- Free-throw execution moves three-point volume (through the range rating), not free-throw percentage: real players' free-throw percentage comes from their own recent record, which is right for them, but it means a drafted player's free-throw grade does not set his free-throw percentage.

## What was wired in, and the evidence

### 1. Screening (screen setting, screen reads, the screen/roll habit, body mass)

- **Before:** the "Screening" rating on the player page and in team offence was 45% body size, 35% general basketball IQ, 20% stamina. The screen-setting grade the card shows (built from Basketball Index's screening grade, correlation 0.96) had no effect anywhere; the screen/roll/pop/slip habit was unused.
- **Evidence:** Basketball Index screen assists per 75 possessions (screens that directly lead to a teammate's basket), 2023-24 to 2025-26 weighted 1 / .5 / .25, 471 players with 500+ minutes. Log-linear fit like the other box-score rates (`scripts/fit_screen_assists.py`): screen setting (+1.5% per grade point), screen reads (+2.7% per point), how often he is the screener and the roller (the habit mix), body mass (+3.5% per kg). Out-of-fold correlation **0.85**. A +15 screen-setting grade means about +26% screen assists. How often a player screens is the biggest factor, as it should be (the four-layer separation: skill sets how productive each screen is, the habit sets how often).
- **Now:** (a) a **screen-assists** count in every new-ratings box score (`screens.py`, its own random numbers, so scores and every other stat are unchanged; never more than the teammates' made baskets); (b) the **Screening rating** shown on the player page, used in team offence and in trade value, is that fitted screen production placed on the old rating's league scale (same average and spread over 377 rotation players), so team-offence and trade calibrations keep their meaning.
- **Check (full-season replay, 376 players with 500+ minutes in both):** simulated vs real 2025-26 screen assists per 36: correlation **0.84**, mean error 0.50, simulated average 1.22 vs real 1.18; 8.0 per team game. Kornet 5.3 (real 6.1), Queta 7.0 (5.6), Sabonis 4.8 (5.1), Ayton 4.9 (5.1); biggest miss Nurkić 10.1 (5.8). Before: no such stat.
- **Team effect of screening:** unchanged in size. The team-offence term is 0.025 points per 100 possessions per point of the team's minutes-weighted Screening rating, which spreads teams by only ~0.04 points per 100 (Denver best, +0.21; Milwaukee lowest, +0.02). I did not find usable evidence to resize it: Basketball Index's "impact on teammates' shot quality" runs the wrong way for screeners (correlation -0.60 with screen assists, because screening bigs share the floor with weak creators), so it is confounded. A lineup-data study is proposed below.
- **Roll vs pop:** the habit's roll share now raises screen production; pop bigs' three-point volume already comes from their own record. The roll/pop split does not otherwise steer the box score (proposal below).

### 2. Shot difficulty (and why Ingram was too efficient)

- **What I found first:** the over-efficiency of tough-shot scorers is not about shot difficulty as such. Each player's shooting percentages come from his own 2024-26 record, which already contains his shot difficulty (Ingram's two-point .514, three-point .377 are right). The defect is in how the box score shares a team's shooting luck. The game's score fixes each team's points and possessions; when a team scores more efficiently than its players' own percentages imply (on balance it does: across a 400-game sample this step lifted the league's two-point percentage from the players' own .539 to .564), the extra two-point makes were shared in plain proportion, so a team's good offence made its high-usage creators exactly as much better as its spot-up shooters and finishers. Result: the top quarter by usage shot .584 on twos vs their own .540 (true shooting .616 vs real .594), Ingram .628 vs .573, Booker .650 vs .585, Brunson .635 vs .580.
- **Basketball reasoning and data:** real team offence mostly improves the shots teammates are set up for; a player who lives on difficult self-created shots keeps close to his own shot-making. Shot-difficulty tolerance (built from Basketball Index shot quality and openness) measures exactly that. Over the 150 heaviest-minute players, the error in simulated true shooting correlated 0.28 with shot-difficulty tolerance.
- **Now:** each player's share of the team's hot or cold swing is scaled by exp(-k x his tolerance in league standard deviations). k = 0.5 was fitted to real 2025-26 true shooting (`scripts/fit_shot_difficulty_share.py`): mean true-shooting error of the 150 players .0258 -> .0246 (k 0.375-0.5 best; 1.0 and above overshoot). Team totals, scores and every random draw are unchanged; only who made which shots moves.
- **Honest caveat:** shot-difficulty tolerance and usage are correlated 0.80. Driving the same share by the engine's usage estimate instead fits about as well overall (.0241) but less well for the tough-shot group (top-15 average error +.009 vs +.007 at the same setting). I kept shot difficulty because it is the mechanism and it is an approved, displayed rating; usage is not.

| Top 15 shot-difficulty tolerance (of the 150) | Tolerance | Real TS | Before | After |
|---|---:|---:|---:|---:|
| Brandon Ingram | 0.386 | 0.573 | 0.628 | 0.591 |
| DeMar DeRozan | 0.372 | 0.594 | 0.544 | 0.552 |
| Kevin Durant | 0.356 | 0.640 | 0.660 | 0.656 |
| Luka Dončić | 0.356 | 0.616 | 0.635 | 0.617 |
| Jalen Brunson | 0.354 | 0.580 | 0.635 | 0.613 |
| Cade Cunningham | 0.350 | 0.564 | 0.609 | 0.585 |
| James Harden | 0.350 | 0.610 | 0.619 | 0.601 |
| Devin Booker | 0.347 | 0.585 | 0.650 | 0.627 |
| Zion Williamson | 0.345 | 0.643 | 0.630 | 0.620 |
| Kawhi Leonard | 0.340 | 0.629 | 0.640 | 0.631 |
| Nikola Jokić | 0.339 | 0.670 | 0.689 | 0.689 |
| Cooper Flagg | 0.338 | 0.548 | 0.571 | 0.568 |
| LaMelo Ball | 0.335 | 0.546 | 0.543 | 0.532 |
| Keyonte George | 0.335 | 0.609 | 0.598 | 0.589 |
| Shai Gilgeous-Alexander | 0.334 | 0.665 | 0.705 | 0.687 |
| **Average error (sim - real)** | | | **+.019** | **+.006** |
| Average absolute error | | | .029 | .020 |

By usage quarter (true shooting, sim vs real): lowest .571 -> .577 (real .586); second .588 -> .592 (.594); third .585 -> .585 (.578); highest .616 -> .607 (.594). Two-point attempts per 36 of the highest-usage quarter 10.97 -> 11.28 (real 12.08).

### 3. Rebounding skills -> rebounds

- **Before:** each player's share of his team's rebounds came from height and the offensive-rebounding rating only (fit r 0.82). Defensive-rebound positioning, box-out technique and rebound control, all shown on the card, never moved a rebound; the pursue-vs-box-out habit was unused.
- **Evidence:** log-linear fit to real 2025-26 rebounds per 36 of 377 rotation players (`scripts/fit_box_stat_rates.py`, same method and data as the other box rates): the three defensive-rebounding skills, the crash habit, the pursue share, height and wingspan. Out-of-fold correlation **0.94**. Jumping took a negative weight (its values are position-based estimates, not measurements, and guards out-jump centres there), so it is left out. Team rebound totals are still set by the missed shots in the game; this only decides who gets them.
- **Check (full-season replay, 150 players):** correlation with real rebounds per 36 **0.849 -> 0.940**; mean error **1.14 -> 0.70**. Jokić 10.6 -> 13.3 (real 13.3), Clingan 11.1 -> 13.3 (15.3), Gobert 11.5 -> 14.4 (13.2). New biggest misses: Amen Thompson 11.3 (real 7.5) and Nic Claxton 12.6 (9.0), whose crash and rebounding inputs are high; worth a look in the next ratings review (not changed here).

## Scorecards

| | Before | After |
|---|---|---|
| Real-stat targets (`calibration_report.py --games 1230 --mode replay-real-minutes`) | 18/18 | **18/18** |
| Player true shooting, mean error (150 players) | .026 | .025 |
| Player rebounds per 36, mean error | 1.142 | 0.704 |
| Player shot attempts per 36, mean error | 1.136 | 1.063 |
| Player points per 36, mean error | 1.296 | 1.300 |
| Betting odds (`validate-season-probabilities --runs 100`), Brier / log loss | main 0.1959 / 0.5786 | **0.1958 / 0.5782** (market 0.1962 / 0.574; spread error 4.52, totals error 5.48) |

League metrics barely move (points 115.45 -> 115.41, true shooting .580 -> .580, pace 101.9 -> 101.9). Only the screening change can move a score (through the small team-offence term); the shot-difficulty, rebounding and screen-assist changes are box-score only.

Speed: the 1,230-game replay ran in 16.4 s after vs 16.6 s before (the added work is a few look-ups per player per game), so a simulated month is unchanged within noise.

## Sweep after the changes

Same 120 players, same 400 games, after the changes (the "Sweep after" column above):
- **Screen setting +15:** screen assists +0.30 per 36 (+26%; league-average bumped player 1.17); team points move 0.05 per game (the small team-offence term). Screen reads +15: +0.61 per 36. Roll share +10 points: +0.12; pop or slip share +10 points: -0.18.
- **Defensive-rebound positioning / box-out / rebound control +15:** rebounds +0.29 / +0.59 / +0.28 per 36 (no score change: team totals still come from missed shots). Pursue share +10 points: +0.03.
- **Shot-difficulty tolerance x1.3:** the bumped players take +0.15 more shots per 36 for the same points (lower efficiency on good-offence nights); scores unchanged by construction (the team-points change comes from the tolerance's 10% share of shot versatility, as before).
- **Still no effect at all:** strength, jumping, shooting-mode habit, pace habit, cutting habit, steal gambling (proposals below).

## Remaining gaps, with proposals

1. **Strength (P08):** unused. Proposal: post scoring and screen effect. Needs post-up and screen-contact evidence; the current screen fit uses body mass, which carries most of the same signal (correlation of strength with screen assists 0.39 vs body mass 0.68).
2. **Jumping (P10):** unused, and its values are position-based estimates (guards out-jump centres). Proposal: fix the estimate first (measured vertical where it exists), then let it feed rebounds, blocks and lob finishing.
3. **Shooting-mode habit (catch / pull-up / movement, T03):** unused. The engine has no shot types. Proposal: weight a player's three-point percentage by his catch, pull-up and movement grades through this mix, for players without a long shooting record (draftees).
4. **Pace habit (T05):** unused. Proposal: a small team-pace term from the minutes-weighted habit, fitted to real team pace; it would move scores, so it needs the odds scorecard.
5. **Cutting habit (T09)** and the cutting/relocation route grades (10% of portability each): no box-score effect. Proposal: let cutting raise a player's share of assisted close shots once the box score splits shots by zone.
6. **Steal gambling (T14)** and **foul control (S45):** steals and fouls ignore them. Proposal: fit steals and personal fouls per 36 to steal technique plus gambling, and fouls to foul control plus contest style. Personal fouls feed in-game foul trouble (`game_minutes.py`, another agent's area), so this needs coordination.
7. **Free-throw execution (S07):** sets three-point volume (through the range rating) but not free-throw percentage. Fine for real players (their own record), wrong for draftees. Proposal: draftees' free-throw percentage from the free-throw grade.
8. **Screening's team effect:** keep at its current small size until a lineup-data check (Basketball Index lineup explorer: lineup offence vs screening of the bigs on the floor, controlling for creators) gives a number.
9. **Development of inputs outside the blends:** screen setting, defensive rebounding, steal technique, foul control, strength, jumping and most habits never change with growth or aging. Now that screen setting and defensive rebounding drive the box score, they should develop too. Proposal (ratings_model, not changed here): route development to every graded input, using each input's own age curve.
10. **Ratings questions for the next review (not changed, rule 1):** Jokić's defensive-rebound positioning grade is 41.7 (his box-out 76.9 and control 85.5 carry his rebounding); Amen Thompson and Nic Claxton now simulate well above their real rebounds.
11. **Display:** the screen-assists count exists in every simulated box score but the browser screens do not show it yet (GUI is another agent's area). Suggest adding it to the box score and season stats tables.
12. **Remaining true-shooting bias:** after this change, high-usage players still run about +.013 above real true shooting and low-usage three-point shooters below (AJ Green .497 vs .627): the points model shares points without reading shooting skill, and low-scoring shooters lose made threes to the points budget. A points-share refit that includes three-point skill would address it (box-score only).

## Files

- `src/nba_gm_data/box_rates.py`: rebound and screen-assist fits, `tendency_from_inputs`.
- `src/nba_gm_data/box_variation.py`: shot-difficulty share of the team's miss swing (`team_context_share`, `removed_by_weight`), screen assists hook.
- `src/nba_gm_data/screens.py` (new): screen assists in the box score.
- `src/nba_gm_data/offense.py`: Screening rating from screen production (new ratings only).
- `src/nba_gm_data/sim.py`: box-score features only (rebounds, screen assists, shot difficulty) in `player_feature_vector`'s inputs block and `rebound_rate_per_minute`.
- `scripts/fit_screen_assists.py`, `scripts/fit_shot_difficulty_share.py` (new); `scripts/fit_box_stat_rates.py` (rebounds).
- `tests/test_unused_ratings.py` (new).
- Not touched: trade code, the value formula, fatigue/rest/minutes, GUI, the experimental possession engine, any rating.

## Tests

- New `tests/test_unused_ratings.py` (7 tests: screen assists follow screening skill and role; Screening rating reads screen production; screen assists need teammates' baskets, are deterministic and absent on old-ratings saves; tough-shot players absorb less of the team swing; the weighted miss removal is exact and bounded; rebounds follow the rebounding skills).
- Box-score, offence, rotation, ratings-model, player-card and runtime-reuse modules: 93 tests OK.
- Core suite (`scripts/run_core_tests.sh`): 337 tests OK (2 skips).
- Known unrelated error in this worktree: `test_offense_interior_interaction` needs a reference file from the main checkout's ignored `output/` folder (experimental engine).
