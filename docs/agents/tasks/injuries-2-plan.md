# Injuries 2: real opening night, the right kinds of injuries and lengths (plan)

_Plan written 2026-11-20 by Claude (coordinator). Not started. User priority order: trades first (TRADE-DEADLINE), then this._

## TL;DR
- **New careers open with the real 2026-27 opening-night injuries**, not random draws. Example of the problem: in one test save, Tatum drew a season-long injury at the start; stars with injury history had about a 1-in-25 chance of that. Later seasons keep the random start-of-season model, which matches real rates.
- **Check and fix the mix of injury types and how long each lasts** against real data.
  - Known gap: the game has too few 2–10 game absences (about 4.0 per player against 5.6 real) and too many 11+ game ones. That is why the 30 best players' median games played sits about 4 high (68.5–69 against 64.5).
- Evidence first: real data sets the rates and lengths, never a target outcome (AGENTS.md rules 1 and 9).

## User decisions
- 2026-11-20: a new career uses the real 2026-27 opening-night injuries (who was out, why, and for how many games). The random start-of-season model stays for later seasons.

## Part 1: real opening night for new careers
- **Who was out and for how long.** Use public ESPN box scores for each team's first 2026-27 games (`site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`, then the game summary for box scores; same method as `scripts/research/national_tv.py`).
  - A rostered regular who didn't play in his team's opener counts as out. His games missed is the count until his first game played; anyone still out on the capture date gets an open-ended return estimated from the diagnosis.
  - Separate rest and coach's decisions from injuries using the injury report or notes (ESPN's injury endpoint `.../nba/injuries`, the team's game notes, and news on ESPN or Hoops Rumors), recorded with source and date.
- **Why.** Body part and diagnosis come from the same notes, mapped to the injury model's parts (`injury_model.PART_AREA`).
- **The Basketball Index injury tracker is optional.** The captured copy (`data/research/bbi/tools/injury_*.json`) stops before 2026-27. If the user captures the tracker's current season while signed in (subscription runs to Dec 16), use it to confirm diagnoses. It stays local and is never committed.
- **In the game.**
  - `data/canonical/opening_night_injuries_2026_27.json`: player, team, part, diagnosis, games missed, sources.
  - At `create_league_save`, apply these instead of the random `carried` and offseason draws (`health.season_start_injuries`, `save.apply_season_start_injuries`). Players are matched by id and must be on the same team in the save; otherwise they're skipped and reported.
  - Return dates come from the save's own schedule (out for exactly N team games), the way the current code does it.
  - At rollovers, the random model stays as it is.
- **Checks.**
  - Every listed player in a new save is out for the right count.
  - Nobody else starts hurt in a new career.
  - Tatum and Haliburton are active if they really played on opening night.

## Part 2: injury kinds and lengths against real
- Measure first, with `scripts/research/injury_season_check.py` (fixed rosters, 2 seeds) and the games-played measure from the TV-rest task (`gp.py`):
  - spells per team by body part;
  - days and games out by part (median, 75th and 90th percentiles);
  - share by length band (1, 2–5, 6–10, 11–20, 21+ games);
  - season-ending share;
  - top-30 players' games played.
- Compare with the Basketball Index tracker history (2021-22 to 2025-26) and real 2025-26 box-score absences.
- Likely levers, to be measured before use:
  - the length sampling per part (recovery pools may be too heavy in the tail);
  - per-player recovery speed;
  - how illnesses and minor knocks (1–3 games) are represented;
  - rest versus injury separation, so rest doesn't fill the short-absence gap.
- Follow-ups already on file (`injury-overhaul.md`), in scope only if cheap:
  - `transactions.player_health_risk` still reads the legacy profile fields; move it to the v2 expected injury games;
  - a body-part history view on the player card.

## Measures (done means)
- **Length bands within real ranges for each part:** 2–10 game absences near 5.6 per regular, 11+ near 4.0.
- **Top-30 median games played** within about 1.5 of real (64.5).
- **Spells per team and season-ending share** stay in the Basketball Index range.
- **Real-stat scorecard 18/18.** The betting test isn't affected (it replays real availability).
- **Speed:** the health sim stays about 1.2 seconds per simulated month.

## Files
`health.py`, `injury_model.py`, `data/canonical/injury_model_v2.json` (rebuilt by its script only), `scripts/build_injury_model.py`, `save.py` (the season-start hook only), new research scripts and data, tests. Doesn't touch trade files. `transactions.player_health_risk` is touched only after TRADE-DEADLINE merges.
