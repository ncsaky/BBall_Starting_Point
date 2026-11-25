"""Stage 2 possession engine (under construction; never used by normal gameplay).

Pieces so far (S2-SEAM-SHOOTING, 2026-11-21):
- engine.py: the `engine="stage2"` entry point the game sim's seam calls.
- league_inputs.py: the league input bridge, compiling every player's 94 inputs into the physics pieces' profiles.
- shooting_check.py: the shooting/finishing spot-check against real 2025-26 shooting.

S2-REBOUND-FOULS (2026-11-21):
- rebounding.py / fouls.py: the rebound kernel and the foul/free-throw kernel (with their refit coefficients, FITTED).
- game_contexts.py: real 2025-26 lineups and per-player real rates; rebound_check.py / foul_check.py: the spot-checks.

S2-POSSESSION-LOOP (2026-11-21):
- cards.py: each player's numbers for the loop (usage, turnovers, action-and-shot menu, make chances with the
  per-family conversion, hook and dunk rules, defense indices, rebound and foul profiles).
- game.py: the whole-game loop (clock, quarters, possessions, team fouls and bonus, live substitutions, box score).
- engine.py now plays Stage 2 games through game.py; loop_fit.py holds the rule fits and spot-check helpers.

S2-TOTALS-MATCHUPS (2026-11-21):
- matchups.py: who guards whom; game.py: the defender's terms on each shot, foul and turnover; both fives' pace.

S2-COACH (2026-11-24):
- coach.py: the in-game coach (who plays at every stoppage: tonight's plan, rhythm and fatigue, foul trouble, blowouts
  and garbage time, close finishes, hot and cold hands, injuries and rust), its decisions taken from the real 2023-26
  rotation study (data/research/rotation_evidence.json).
- screens.py: pick-and-roll coverages and switching (switch, drop, show, trap) on self-created shots and rolls.
- game.py: substitutions at every dead ball and timeout, players in foul trouble foul less, the real end-of-game
  fouling rates, screen assists in the box score.

S2-SCHEMES (2026-11-24):
- schemes.py / scheme_table.py: each head coach's ball-screen scheme (aggression: drop less and trap more; switching)
  on top of his personnel, fitted to the scheme study's 2025-26 team measures.
- game.py: a share of shooting fouls is charged to a teammate of the shot's defender (help, rotations, closeouts;
  fitted to real fouls per 36), two-for-ones and late timeouts that advance the ball (fitted to the rotation study),
  league turnover and pace levels refitted to the real 2025-26 games.
"""
