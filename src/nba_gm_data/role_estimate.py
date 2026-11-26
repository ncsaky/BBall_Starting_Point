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


# Every league rebuild (canonical_with_save, several a simulated day) re-runs this on the same baseline ratings; the
# nearest-veteran search grew to half a second a rebuild by the third season. The result is a pure function of the
# veterans' ratings, heights, roles and ids and of each draftee's own ratings and height, so it is kept per reference
# set (keyed on all of that, compared exactly) and per draftee vector. A new draftee, a roster's development or any
# veteran change makes a new key; nothing is reused across different inputs. SEASON-SPEED-FLOOR, 2026-11-25.
_REFERENCE_CACHE: dict[tuple[Any, ...], tuple[int, list[float], list[float], list[tuple[list[float], dict[str, Any]]]]] = {}
_ROLE_CACHE: dict[tuple[Any, ...], tuple[str, str]] = {}
_CACHE_LIMIT = 4
_ROLE_CACHE_LIMIT = 20000


def _clear_caches() -> None:
    _REFERENCE_CACHE.clear()
    _ROLE_CACHE.clear()


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
    signature = (tuple(keys), tuple((p["id"], p["primary_off_role"], p["primary_def_role"], tuple(row))
                                    for p, row in zip(veterans, rows)))
    prepared = _REFERENCE_CACHE.get(signature)
    if prepared is None:
        if len(_REFERENCE_CACHE) >= _CACHE_LIMIT:
            _clear_caches()
        columns = list(zip(*rows))
        mean = [sum(column) / len(column) for column in columns]
        spread = [max(1e-6, math.sqrt(sum((x - m) ** 2 for x in column) / len(column))) for column, m in zip(columns, mean)]
        reference = [(_scaled(row, mean, spread), {"id": p["id"], "primary_off_role": p["primary_off_role"],
                                                    "primary_def_role": p["primary_def_role"]})
                     for row, p in zip(rows, veterans)]
        prepared = (len(_REFERENCE_CACHE) + 1, mean, spread, reference)
        _REFERENCE_CACHE[signature] = prepared
    token, mean, spread, reference = prepared
    for player in targets:
        vector = tuple(raw(player))
        roles = _ROLE_CACHE.get((token, vector))
        if roles is None:
            point = _scaled(list(vector), mean, spread)
            nearest = sorted(((sum((a - b) ** 2 for a, b in zip(point, ref_vector)), vet["id"], vet)
                              for ref_vector, vet in reference),
                             key=lambda item: (item[0], item[1]))[:NEIGHBOURS]
            picked = []
            for field in ("primary_off_role", "primary_def_role"):
                votes: Counter[str] = Counter()
                for distance, _vid, vet in nearest:
                    votes[vet[field]] += 1.0 / (1.0 + distance)
                picked.append(max(votes, key=lambda role: (votes[role], role)))
            roles = (picked[0], picked[1])
            if len(_ROLE_CACHE) >= _ROLE_CACHE_LIMIT:
                _ROLE_CACHE.clear()
            _ROLE_CACHE[(token, vector)] = roles
        player["primary_off_role"], player["primary_def_role"] = roles
        player["role_source"] = ROLE_SOURCE
    return len(targets)


def _scaled(values: list[float], mean: list[float], spread: list[float]) -> list[float]:
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
