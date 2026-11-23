"""Offensive and defensive roles for players drafted in 2026 or later (playtest 2026-11-22).

Veterans carry real primary roles from how they were used. Drafted players have no NBA usage yet, so the roster
data gave them placeholders from their position (every guard a primary ball handler, every center a rim protector)
and in-sim draftees got a prospect archetype and a "Rookie" defensive role. Here each one takes the role of the
veterans whose ratings are shaped most like his: the 15 nearest veterans by the direction of their relative strengths
plus height, each vote weighted by closeness. On veterans held out of the fit this picks the real role 54% of the time
on offense (8 roles; the position placeholder 36%) and 66% on defense (6 roles; placeholder 46%). Evidence:
data/research/rookie_roles_fit_2026.json, scripts/research/rookie_roles_fit.py.

Roles follow the player's current ratings, so a draftee's role can change as he develops. Deterministic: ties break
on distance, then player id.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping

ESTIMATED_FROM_DRAFT_YEAR = 2026
NEIGHBOURS = 15
HEIGHT_WEIGHT = 2.0
ROLE_SOURCE = "ratings: 15 nearest veterans (data/research/rookie_roles_fit_2026.json)"


def _draft_year(player: Mapping[str, Any]) -> int | None:
    value = str(player.get("draft_year") or "")
    return int(value) if value.isdigit() else None


def assign_estimated_roles(canonical: dict[str, Any], traits: Mapping[str, Mapping[str, float]]) -> int:
    """Set primary_off_role / primary_def_role for every player drafted in 2026 or later. Returns how many."""
    players = canonical.get("players", [])
    veterans = [p for p in players
                if p.get("primary_off_role") and p.get("primary_def_role") and p.get("id") in traits
                and (_draft_year(p) or 0) < ESTIMATED_FROM_DRAFT_YEAR and p.get("role_source") != ROLE_SOURCE]
    targets = [p for p in players if (_draft_year(p) or 0) >= ESTIMATED_FROM_DRAFT_YEAR and p.get("id") in traits]
    if len(veterans) < NEIGHBOURS or not targets:
        return 0
    keys = sorted({key for p in veterans for key in traits[p["id"]]})

    def raw(player: Mapping[str, Any]) -> list[float]:
        values = traits[player["id"]]
        return [float(values.get(key, 50.0)) for key in keys] + [float(player.get("height_inches") or 78.0)]

    rows = [raw(p) for p in veterans]
    columns = list(zip(*rows))
    mean = [sum(column) / len(column) for column in columns]
    spread = [max(1e-6, math.sqrt(sum((x - m) ** 2 for x in column) / len(column))) for column, m in zip(columns, mean)]

    def scaled(values: list[float]) -> list[float]:
        # Shape, not level: a draftee's ratings are flatter than a veteran's (thin evidence pulls them toward the
        # middle), so matching on level made almost every rookie a "Connector". Compare the direction of each
        # player's relative strengths (trait z-scores minus his own average, scaled to one length) plus height,
        # which stays absolute and counts double. Same held-out accuracy on veterans, far less collapse.
        z = [(x - m) / s for x, m, s in zip(values, mean, spread)]
        body = z[:-1]
        average = sum(body) / len(body)
        body = [v - average for v in body]
        length = math.sqrt(sum(v * v for v in body)) or 1.0
        return [v / length * math.sqrt(len(body)) for v in body] + [z[-1] * HEIGHT_WEIGHT]

    reference = [(scaled(row), p) for row, p in zip(rows, veterans)]
    for player in targets:
        point = scaled(raw(player))
        nearest = sorted(((sum((a - b) ** 2 for a, b in zip(point, vector)), vet["id"], vet) for vector, vet in reference),
                         key=lambda item: (item[0], item[1]))[:NEIGHBOURS]
        for field in ("primary_off_role", "primary_def_role"):
            votes: Counter[str] = Counter()
            for distance, _vid, vet in nearest:
                votes[vet[field]] += 1.0 / (1.0 + distance)
            player[field] = max(votes, key=lambda role: (votes[role], role))
        player["role_source"] = ROLE_SOURCE
    return len(targets)
