"""Read-only decision support for the extension page; never changes a save."""
from __future__ import annotations

from copy import deepcopy
from statistics import mean, median
from typing import Any

from .health import (
    DEVELOPMENT_TRAITS, coach_development_by_team, development_staff_modifiers,
    development_trait_focus, monthly_trait_delta, should_generate_development_event,
)
from .save import RATING_SCALE, cap_lines_for_season, display_minutes_projection, display_ratings_for_traits, player_display_attribute_summary, trait_values_by_player


def season_label(year: int) -> str:
    return f"{year}-{str(year + 1)[-2:]}"


def position_group(position: str) -> str:
    position = str(position).upper()
    if "SF" in position or "PF" in position or position == "F":
        return "Forwards"
    if "PG" in position or "SG" in position or position == "G":
        return "Guards"
    return "Centers"


def ability_projection(active: dict[str, Any], player: dict[str, Any], current_year: int, end_year: int) -> list[dict[str, Any]]:
    """Explore the existing monthly development model with fixed role scenarios.

    Seeds belong to this preview, not the save's future simulation. The envelope
    is a scenario range, not a confidence interval or a prediction of injuries.
    """
    player_id = player["id"]
    age = float(player.get("display_age", player.get("age")) or 27)
    minutes = display_minutes_projection(player)
    values = trait_values_by_player(active).get(player_id, {})
    if not values:
        return []
    coaches = coach_development_by_team(active)
    staff = development_staff_modifiers(active, player["team_id"], coaches.get(player["team_id"], 3.0))
    baseline = player_display_attribute_summary(active, player_id)["overall"]
    paths = []
    components = {t["trait_key"]: (t.get("components") or {}).get("career_capacity")
                  for t in active.get("traits", []) if t.get("player_id") == player_id}
    for scenario in range(7):
        projected = dict(player)
        traits = {key: {"value": value} for key, value in values.items()}
        projected_staff = dict(staff)
        context = (scenario - 3) / 3
        projected_staff["development_multiplier"] = float(staff.get("development_multiplier", 1)) * (1 + context * .2)
        role_minutes = max(0, min(40, minutes + context * 4))
        path = [baseline]
        for year in range(current_year + 1, end_year + 1):
            for month in range(1, 13):
                projected["age"] = age + year - current_year - 1 + month / 12
                projected["minutes_projection"] = role_minutes
                month_key = f"{year}-{month:02}"
                focus = development_trait_focus(projected, projected_staff, traits, 4100 + scenario, month_key)
                if not should_generate_development_event(projected, projected["age"], role_minutes):
                    continue
                for key in DEVELOPMENT_TRAITS:
                    current = float(traits.get(key, {}).get("value", 50))
                    delta = monthly_trait_delta(projected, key, current, projected["age"], role_minutes, projected_staff, (1 - context) * .25, 4100 + scenario, month_key, focus.get(key, .32), components.get(key))
                    if abs(delta) >= .015:
                        traits[key] = {"value": max(1, min(99, current + round(delta, 3)))}
            # Hold the presentation minutes adjustment fixed: this graph shows
            # ability development, not an artificial OVR jump from a new role.
            projected_traits = {key: value["value"] for key, value in traits.items()}
            # Valued exactly like the card (one OVR display scale; OVERALL-SCALE, 2026-11-21), so the path starts at
            # the player's displayed OVR. Outside new-ratings mode, the summary formula as before.
            shown = display_ratings_for_traits(active, player, projected_traits)
            if shown is None:
                snapshot = {"meta": active.get("meta", {}), "players": [player], "_trait_values_by_player": {player_id: projected_traits}}
                shown = player_display_attribute_summary(snapshot, player_id)
            path.append(shown["overall"])
        paths.append(path)
    return [{"season": season_label(year), "age": round(age + year - current_year),
             "overall": round(median(path[index] for path in paths), 1),
             "low": round(min(path[index] for path in paths), 1),
             "high": round(max(path[index] for path in paths), 1)}
            for index, year in enumerate(range(current_year, end_year + 1))]


def extension_analysis_payload(active: dict[str, Any], player: dict[str, Any], current_season: str, start_season: str, max_years: int) -> dict[str, Any]:
    current_year, start_year = int(current_season[:4]), int(start_season[:4])
    player_id = player["id"]
    # Local indexes avoid rebuilding all traits for every league peer.
    indexed = dict(active, _trait_values_by_player=trait_values_by_player(active),
                   _players_by_id={p["id"]: p for p in active.get("players", [])})
    contracts = {c["player_id"]: c for c in active.get("contracts", [])}
    ratings = {}
    def overall(p):
        if p["id"] not in ratings:
            ratings[p["id"]] = player_display_attribute_summary(indexed, p["id"])["overall"]
        return ratings[p["id"]]
    def age(p):
        return float(p.get("display_age", p.get("age")) or 27)
    def summary(p):
        return {"player_id": p["id"], "name": p["name"], "position": p.get("position"), "age": round(age(p)),
                "overall": overall(p), "minutes": round(display_minutes_projection(p), 1),
                "seasons": deepcopy(contracts.get(p["id"], {}).get("seasons", []))}
    group = position_group(player.get("position", ""))
    teammates = [p for p in active.get("players", []) if p.get("team_id") == player.get("team_id") and p["id"] != player_id
                 and not p.get("_inactive_player") and position_group(p.get("position", "")) == group]
    teammates.sort(key=lambda p: (-display_minutes_projection(p), -overall(p), p["name"]))
    alternatives = [p for p in teammates if display_minutes_projection(p) < 28]
    replacement = max(alternatives, key=overall, default=None)
    peers = []
    target_growth = cap_lines_for_season(start_season)["growth_factor"]
    for peer in active.get("players", []):
        if peer["id"] == player_id or peer.get("_inactive_player") or not peer.get("team_id"):
            continue
        if position_group(peer.get("position", "")) != group or abs(age(peer) - age(player)) > 3:
            continue
        draft_year = int(peer.get("draft_year") or current_year)
        if current_year - draft_year < 5 or abs(overall(peer) - overall(player)) > 4:
            continue
        contract = contracts.get(peer["id"], {})
        signed = str(contract.get("signed_season") or "")
        if not signed[:4].isdigit() or not 0 <= current_year - int(signed[:4]) <= 3:
            continue
        seasons = [s for s in contract.get("seasons", []) if str(s.get("season", "")) >= current_season and float(s.get("salary") or 0) > 0]
        if not seasons:
            continue
        adjusted = mean(float(s["salary"]) / 1e6 * target_growth / cap_lines_for_season(s["season"])["growth_factor"] for s in seasons)
        if adjusted <= 3 * target_growth:
            continue
        peers.append({**summary(peer), "annual_salary": round(adjusted, 2), "signed_season": signed})
    peers.sort(key=lambda p: (abs(p["overall"] - overall(player)), abs(p["age"] - age(player)), p["name"]))
    peers = peers[:10]
    return {"rating_scale": RATING_SCALE, "position_group": group, "player": summary(player),
            "projection": ability_projection(indexed, player, current_year, start_year + max(1, max_years) - 1),
            "replacement": summary(replacement) if replacement else None,
            "succession": [summary(player)] + [summary(p) for p in teammates[:3]],
            "peers": peers, "peer_median": round(median(p["annual_salary"] for p in peers), 2) if peers else None,
            "peer_criteria": [f"{group}; current age within 3 years and current OVR within 4 points.",
                              "Veterans at least 5 seasons past their draft; contracts signed within 3 seasons; up to 10 closest matches.",
                              "Deals below the cap-adjusted $3M salary floor are excluded.",
                              f"Mean of known remaining salaries, adjusted to the {start_season} cap using the game's cap growth.",
                              "Signing-date ratings and full original contract ledgers are unavailable; these comparisons use current ratings and remaining salaries."],
            "projection_note": "Seven development-model scenarios with varied minutes and development support; current role and staff held broadly stable. Range is illustrative, not a guarantee."}
