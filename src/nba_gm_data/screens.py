"""Screen assists in the box score (new ratings): screens that directly lead to a teammate's made shot.

Each player's expected count is his fitted screen assists per 36 (box_rates.SCREEN_ASSISTS_INPUTS: screen execution,
screen-action recognition, screen and roll frequency, body mass; out-of-fold r 0.85 with Basketball Index) times his
minutes. Counts are drawn from a generator of their own, so game scores, every other box-score stat and the game's
random stream are unchanged. A screen assist needs a teammate's made field goal, so a player never gets more than his
teammates made. Old-ratings saves (no inputs) get no screen-assist column.
"""
from __future__ import annotations

import random
from typing import Any, Mapping

from .box_rates import poisson_quantile

FEATURE = "screen_assists_per36"


def add_screen_assists(groups: list[list[dict[str, Any]]], features: Mapping[str, Mapping[str, float]], seed: str) -> None:
    rng = random.Random(f"{seed}:screen-assists")
    for lines in groups:
        if not any(features.get(line["player_id"], {}).get(FEATURE) is not None for line in lines):
            continue
        team_fgm = sum(int(line.get("fgm") or 0) for line in lines)
        for line in lines:
            u = rng.random()   # one draw per line in a fixed order, whatever the player's rate
            minutes = float(line.get("minutes") or 0.0)
            rate = features.get(line["player_id"], {}).get(FEATURE)
            if minutes <= 0 or rate is None:
                line["screen_assists"] = 0
                continue
            count = poisson_quantile(minutes / 36.0 * float(rate), u)
            line["screen_assists"] = min(count, max(0, team_fgm - int(line.get("fgm") or 0)))
