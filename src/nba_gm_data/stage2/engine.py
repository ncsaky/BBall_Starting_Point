"""Entry point for `sim_game_with_context(..., engine="stage2")`.

Stub (S2-SEAM-SHOOTING): the Stage 2 engine does not exist yet, so this runs today's engine on the same game and
labels the result. It proves the seam carries a game through both scorecards end to end. Later pieces replace the
body with the fast possession loop; the signature (game, teams and tonight's player pools from the shared
preparation) is what they will receive.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

STUB_NOTE = "Stage 2 engine stub: today's engine ran this game (S2-SEAM-SHOOTING)."


def simulate_stage2_game(context: dict[str, Any], game: dict[str, Any], home_team: dict[str, Any],
                         away_team: dict[str, Any], home_players: list[dict[str, Any]],
                         away_players: list[dict[str, Any]], *, game_id: str, mode: str, seed: int):
    from ..sim import sim_game_with_context

    result = sim_game_with_context(context, game_id, mode=mode, seed=seed, engine="current")
    return replace(result, notes=f"{STUB_NOTE} {result.notes}")
