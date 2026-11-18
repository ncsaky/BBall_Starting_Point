# New court heat maps: playmaking, on-ball defense, help defense (built 2026-11-19)

**Status: built (route A, user-approved).** Player card → Court Influence panel. The offense court toggles between
Scoring and Playmaking. The defense court toggles between Overall, On his man and Help.

- **Playmaking.** `src/nba_gm_data/court_influence.py`.
  - **Fit:** `scripts/fit_court_influence.py` writes `data/canonical/court_influence_fit.json`. It is fitted to Basketball
    Index's "Offensive eFG% Impact on Teammates", 2023-26, 455 players, out-of-fold r 0.59.
  - **What moves it:** passing reads (+0.36 points per standard deviation) > shooting gravity (+0.15) > handle (+0.10) >
    rim pressure (+0.08) > shot versatility (+0.07). Height adds nothing.
  - **Zero point:** each player is measured against the league's own minutes-weighted players, so league scoring
    doesn't shift.
  - **In the sim:** `spatial.team_spatial_profile` adds 5 x the minutes-weighted mean x 0.8 (teammates' share of shots)
    to each zone's team shooting grade. Teams range from about −0.6 to +0.9 points of team FG%.
- **On-ball and help.** A split of the engine's existing zone defense (no new effect).
  - **Help gets:** 70% of the rim-protection and scheme terms, 40% of effort, 15% of lateral quickness and 10% of
    screen navigation.
  - **Sum:** on-ball + help = Overall exactly.
  - **Check:** the engine's overall defense correlates 0.42 with Basketball Index's "Defensive Impact on Opponent Shot
    Quality" and 0.40 with "Help Effectiveness Rating".
- **Shot volumes.**
  - **Playmaking:** league shot map, nudged toward the zones he improves.
  - **On his man:** the shot map of players his size, from height-matched comparables.
  - **Help:** the league shot map, nudged away from zones he protects.
- **Noticed along the way:** the engine rates Jokić and Gobert identical at rim suppression (+10.8 points). The rim
  term seems to saturate. Worth a ratings and evidence check (not changed).

---


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
