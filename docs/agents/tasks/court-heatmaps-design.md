# New court heat maps: playmaking, on-ball defense, help defense (design, 2026-11-19)

User request (night of Nov 18–19): add spatial heat maps beyond the scoring shot chart:
1. **Playmaking chart.** How this player's presence changes his *teammates'* shots, by court zone: volume and
   efficiency, with his own scoring left out.
2. **On-ball defense chart.** Shots taken by the player he guards, by zone: volume and efficiency allowed.
3. **Help-defense chart ("defensive playmaking").** The opponent's shot chart with him on the court against off.
   Open question: should it leave out his own matchup's shots, the way the playmaking chart leaves out his own?

## What exists today
- The player card's "Court Influence" panel has two half-courts:
  - **Offense:** his projected shot locations and FG% against league average.
  - **Defense:** modeled "suppression" by zone, which is roughly a version of chart 2 already.
- Both come from the player's spatial profile (`spatial.py`, `shot_chart.py`), computed from his ratings. Real
  2025–26 shot zones anchor real players.
- **How the sim uses it:** the normal season sim does **not** play out individual shots with locations, lineups or
  defensive assignments. It blends the ten players' zone profiles into team profiles and adjusts team shot quality
  and shot mix per game (`spatial_matchup_adjustment`).
- **Limit:** no sim record exists of "teammates' shots with him on the court" or "shots by the man he guarded".

Project rule 4 (what the user sees must match what the engine uses) rules out drawing these charts from numbers the
sim ignores.

## Evidence we already have (Basketball Index leaderboards, local)
- **Playmaking:** Offensive Impact on Teammate Shot Quality, Offensive eFG% Impact on Teammates, Passing Creation
  Quality/Volume, Stable At-Rim Assists per 75, Lob Passing Creation Rate, Drive Passout Rate, Drive Assist Rate,
  Assisted Openness Rating, High Value Assists, Teammate Off-Ball Gravity.
- **On-ball defense:** Matchup Difficulty, Perimeter Isolation Defense, % of Time Guarding Primary Ball Handlers,
  Guarded-by measures, 3PT Contests per 75, Rim dFG% vs Expected, Rim Points Saved.
- **Help defense:** Defensive Impact on Opponent Shot Quality, Help Defensive Activity, Help Effectiveness Rating, Rim
  Deterrence, Passing Lane Defense.
- **Lineups:** Lineup Explorer (61,037 lineups) for on/off-style checks.

These are whole-player numbers, not zone-by-zone. They can calibrate how big each effect is. The zone shape has to
come from the model, e.g. lob and rim-assist creators push teammates' shots toward the rim, and drive-and-kick
creators toward the corners.

## Two ways to build it

**A. Modeled charts, wired into the sim (recommended first; a few sessions)**
- **Playmaking:**
  - For each zone, model how much he shifts teammates' shot share and raises their FG%.
  - The model reads his passing reads, handle pressure, rim pressure and gravity.
  - Size the overall effect against "Offensive eFG% Impact on Teammates" and "Impact on Teammate Shot Quality".
- **On-ball:** the existing suppression and contest by zone, weighted by who he usually guards (matchup difficulty,
  % guarding ball handlers) and showing volume as well as efficiency allowed.
- **Help:** a team-level opponent change by zone from rim deterrence, help activity and scheme IQ. Size it against
  "Defensive Impact on Opponent Shot Quality". Leave out his own matchup, so on-ball plus help equals his whole
  on-court effect.
- **Making it real:** the new playmaking and help terms also go into `team_spatial_profile`, so the sim uses exactly
  what the charts show. Both scorecards must hold.
- **Labeling:** like today's chart, these are labeled "projected".

**B. Sim-recorded charts (bigger; later)**
- **What it takes:** give every simulated shot a zone, shooter, assister, the ten players on the court and a primary
  defender, then build the charts from the season's actual sim results, including real on/off.
- **Why later:** the current box-score sim distributes stats instead of playing out possessions. The experimental
  possession engine has assignments and passes, but it is off by default and much too slow for the speed budget.
- **When:** natural once that engine (or a lighter shot-level layer) goes live.

## Recommendations
- Build A now, in the existing Court Influence style: four tabs (Scoring, Playmaking, On-ball D, Help D), the same
  hex court, and the same color key against league average.
- Help defense **should leave out** his own matchup's shots, mirroring the playmaking chart. The two defensive charts
  then split cleanly into "what his man does" and "what everyone else does with him out there".
- Tag every chart "projected" until B exists.

## Decision for the user
Approve route A, including the small engine change, and the "leave out his own matchup" rule for help defense.
