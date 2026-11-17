"""Versioned skill diversity and career capacity; never an annual talent quota."""
import random
from functools import lru_cache
from typing import Any

from .utils import clamp

MODEL_VERSION = 2
SOURCE_ID = "src_talent_balance_v2"


def enabled(canonical: dict[str, Any]) -> bool:
    return (canonical.get("meta") or {}).get("talent_model_version") == MODEL_VERSION


def modeled(record: dict[str, Any]) -> bool:
    return SOURCE_ID in (record.get("source_ids") or [])


PROFILE_SKILLS = {
    "lead_creator": (("shot_creation", "passing", "feel"), ("defense", "shooting", "rebounding")),
    "scoring_wing": (("shot_creation", "shooting", "rim_pressure"), ("passing", "defense", "feel")),
    "two_way_wing": (("defense", "shooting", "athleticism"), ("shot_creation", "passing", "rim_pressure")),
    "connector_guard": (("passing", "feel", "motor"), ("shooting", "shot_creation", "rim_pressure")),
    "movement_shooter": (("shooting", "motor", "feel"), ("shot_creation", "defense", "athleticism")),
    "rim_pressure_guard": (("rim_pressure", "athleticism", "shot_creation"), ("shooting", "passing", "defense")),
    "versatile_forward": (("passing", "feel", "defense"), ("shooting", "shot_creation", "athleticism")),
    "stretch_big": (("shooting", "size", "feel"), ("defense", "athleticism", "shot_creation")),
    "rim_protecting_big": (("rim_protection", "size", "rebounding"), ("shooting", "shot_creation", "passing")),
    "energy_big": (("motor", "rebounding", "rim_pressure"), ("shooting", "passing", "shot_creation")),
}


def diverse_prospect_skills(prospect: Any, values: dict[str, float]) -> dict[str, float]:
    """Independent stream keeps identity/class/medical draws exactly unchanged."""
    rng = random.Random(f"{prospect.id}:skill_shape_v2")
    output = dict(values)
    strengths, weaknesses = PROFILE_SKILLS.get(prospect.archetype, PROFILE_SKILLS["two_way_wing"])
    for key in strengths:
        output[key] += rng.uniform(3, 9)
    # Not every player has two severe holes; complete prospects remain possible.
    holes = rng.sample(list(weaknesses), 1 if rng.random() < .35 else 2)
    for key in holes:
        output[key] -= rng.uniform(12, 27)
    if "C" in prospect.position:
        if prospect.archetype in {"rim_protecting_big", "energy_big"} and rng.random() < .88:
            output["shooting"] = min(output["shooting"], rng.uniform(9, 29))
        output["shot_creation"] -= rng.uniform(3, 10)
    elif "G" in prospect.position and rng.random() < .90:
        output["rim_protection"] = min(output["rim_protection"], rng.uniform(8, 30))
    return {key: round(clamp(value, 5, 95), 2) for key, value in output.items()}


def role_weights(position: str) -> tuple[float, ...]:
    position = str(position or "").upper().split("/")[0]
    # Shooting, creation, defense, athleticism, IQ, rebounding. Each sums to .94.
    if position == "C":
        return (.06, .14, .28, .12, .14, .20)
    if position == "PF":
        return (.14, .19, .26, .12, .13, .10)
    if position in {"PG", "SG", "G"}:
        return (.20, .27, .22, .12, .11, .02)
    return (.18, .22, .25, .12, .12, .05)


def role_skill_value(values: tuple[float, ...], position: str) -> float:
    weights = role_weights(position)
    balanced = sum(value * weight for value, weight in zip(values, weights, strict=True)) / .94
    relevant = sorted((value for value, weight in zip(values, weights, strict=True) if weight >= .12), reverse=True)
    # A dominant role skill has value beyond the all-skill average. Restrict the
    # premium to relevant composites, not the player's best arbitrary raw trait.
    standout = sum(relevant[:2]) / 2
    return balanced * .80 + standout * .20


def career_trait_profile(entry: float, ability: float, potential: float,
                         aptitude: float) -> dict[str, float]:
    return {"version": MODEL_VERSION, "entry_value": round(entry, 3),
            "ability": ability, "potential": potential,
            "aptitude": round(clamp(aptitude, .15, 1.15), 3)}


def trait_ceiling(player: dict[str, Any], key: str, profile: dict[str, Any],
                  realization: float, seed: int) -> float | None:
    if profile.get("version") != MODEL_VERSION:
        return None
    return _trait_ceiling(str(player["id"]), key, float(profile["entry_value"]),
                          float(profile["potential"]), float(profile["ability"]),
                          float(profile["aptitude"]), realization, seed)


@lru_cache(maxsize=32768)
def _trait_ceiling(player_id: str, key: str, entry: float, potential: float,
                   ability: float, aptitude: float, realization: float, seed: int) -> float:
    rng = random.Random(f"{seed}:{player_id}:{key}:capacity_v2")
    upside = max(0, potential - ability)
    # Successful careers retain generous headroom in their strong skills. The
    # plateau is binding for low realization and low aptitude, not every star.
    fulfillment = .12 if realization <= .55 else .45 if realization <= .8 else realization * 2.0
    room = (3 + upside * .78) * aptitude * fulfillment * rng.uniform(.85, 1.15)
    return min(97.0, entry + room)
