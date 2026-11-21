"""Stage 2 possession engine (under construction; never used by normal gameplay).

Pieces so far (S2-SEAM-SHOOTING, 2026-11-21):
- engine.py: the `engine="stage2"` entry point the game sim's seam calls. For now it runs today's engine.
- league_inputs.py: the league input bridge, compiling every player's 94 inputs into the physics pieces' profiles.
- shooting_check.py: the shooting/finishing spot-check against real 2025-26 shooting.

S2-REBOUND-FOULS (2026-11-21):
- rebounding.py / fouls.py: the rebound kernel and the foul/free-throw kernel (with their refit coefficients, FITTED).
- game_contexts.py: real 2025-26 lineups and per-player real rates; rebound_check.py / foul_check.py: the spot-checks.
"""
