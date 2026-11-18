"""Real college players as draft prospects for the first future drafts of a new save (2027-2029).

The derived bundle data/canonical/real_prospects.json (rebuilt by scripts/research/real_prospects.py from the local
Barttorvik tables) lists, per draft year, the current college players most likely to be drafted that year, with a
projected pick, their college team, coach (when captured) and college profile, plus evidence fits:
- skill_scores: each broad skill (shooting, creation, passing, rim protection, ...) as a standard score against
  drafted college players' final seasons;
- input_parts: the college part of fitted college -> NBA 94-input relationships (players drafted 2019-2025).

draft.generate_draft_class_records(..., real_prospects=True) places these players at their projected picks and
fills every other slot with the generated prospect anchored to that slot, so class size, level by slot, upside
spread, class strength and the position mix stay those of a generated class. Years outside the bundle stay fully
generated and unchanged.
"""
from __future__ import annotations

import json
import math
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

from .utils import clamp, normalize_name, stable_id

BUNDLE_FILE = Path("data/canonical/real_prospects.json")
SOURCE_ID = "src_barttorvik_college_prospects_v1"
SOURCE_TITLE = "Barttorvik (T-Rank) college player tables: real-prospect draft projection and college profiles"
SOURCE_NOTES = ("College player-seasons 2008-2027 (local tables, not redistributed). The game uses only the derived "
                "bundle data/canonical/real_prospects.json: projected draft year and pick, college team and profile, "
                "and fitted college-to-NBA skill relationships. Rebuild with scripts/research/real_prospects.py.")

# Broad draft traits: a standard score of one in college production moves a trait this many points. Sized so a real
# prospect's traits spread around his level as much as a generated prospect's do (about 12 points within a player,
# see talent.diverse_prospect_skills); a smaller step left real prospects flatter than generated ones.
TRAIT_POINTS_PER_SD = 16.0
# 94 inputs: share of each fitted college estimate in the entry value (the rest comes from the same real-player
# neighbours generated rookies use). Scales with how well college predicts the input and with the sample.
INPUT_WEIGHT_BASE = 0.2
INPUT_WEIGHT_PER_R = 0.5
INPUT_WEIGHT_MAX = 0.6
RELIABILITY_MINUTES = 300.0


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any]:
    file = Path(path)
    if not file.is_file():
        return {}
    with file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def bundle(root: str | Path | None = None) -> dict[str, Any]:
    if root is None:
        from .resource_paths import game_resource_root
        root = game_resource_root()
    return _load(str(Path(root) / BUNDLE_FILE))


def draft_years(root: str | Path | None = None) -> set[str]:
    return {str(year) for year in bundle(root).get("draft_years", [])}


def prospects_for_year(year: str | int, root: str | Path | None = None) -> list[dict[str, Any]]:
    rows = [p for p in bundle(root).get("prospects", []) if str(p.get("draft_year")) == str(year)]
    return sorted(rows, key=lambda p: (int(p.get("projected_pick") or 99), str(p.get("id"))))


def enabled(config: dict[str, Any] | None) -> bool:
    return bool(((config or {}).get("real_prospects") or {}).get("enabled", True))


def prospect_id(year: str | int, name: str) -> str:
    return stable_id("draft_prospect", str(year), name)


def college_entry_for(prospect: dict[str, Any] | None) -> dict[str, Any] | None:
    """The college block stored on a real prospect (or None for generated / older real prospects)."""
    if not isinstance(prospect, dict):
        return None
    college = (prospect.get("public_stats") or {}).get("college")
    if college:
        return college
    identity = prospect.get("id") or prospect.get("prospect_id")
    year = prospect.get("draft_year")
    if not identity or not year:
        return None
    for entry in prospects_for_year(year):
        if prospect_id(year, entry["name"]) == identity:
            return college_block(entry)
    return None


# ------------------------------------------------------------------------------------------- identity and role


def position_for(entry: dict[str, Any]) -> str:
    role = str(entry.get("role") or "")
    height = float(entry.get("height_inches") or 78)
    if role == "Pure PG":
        return "PG"
    if role == "Scoring PG":
        return "PG/SG" if height >= 76 else "PG"
    if role == "Combo G":
        return "SG/PG" if height >= 76 else "PG/SG"
    if role == "Wing G":
        return "SG/SF" if height >= 79 else "SG"
    if role == "Wing F":
        return "SF/PF" if height >= 81 else "SF"
    if role == "Stretch 4":
        return "PF/C" if height >= 83 else "PF" if height >= 81 else "PF/SF"
    if role == "PF/C":
        return "C/PF" if height >= 84 else "PF/C"
    if role == "C":
        return "C"
    return "C" if height >= 83 else "PF" if height >= 81 else "SF" if height >= 78 else "SG"


def archetype_for(entry: dict[str, Any], position: str) -> str:
    """The generator's archetype vocabulary, read from the college profile."""
    p = entry.get("projected_profile") or {}
    usg, ast, three_rate = p.get("usg", 20), p.get("ast_pct", 12), p.get("three_rate", 0.3)
    blk, stl, ftr, rim = p.get("blk_pct", 2), p.get("stl_pct", 1.5), p.get("ftr", 30), p.get("rim_per40", 5)
    primary = position.split("/")[0]
    if primary == "PG":
        if ast >= 24 and usg >= 20:
            return "lead_creator"
        if usg >= 23 and (ftr >= 35 or rim >= 6.5):
            return "rim_pressure_guard"
        if usg >= 23:
            return "lead_creator" if ast >= 18 else "rim_pressure_guard"
        if three_rate >= 0.5 and ast < 18:
            return "movement_shooter"
        return "connector_guard"
    if primary == "SG":
        if ast >= 24 and usg >= 22:
            return "lead_creator"
        if usg >= 23 and (ftr >= 38 or rim >= 7):
            return "rim_pressure_guard"
        if usg >= 23:
            return "scoring_wing"
        if three_rate >= 0.45:
            return "movement_shooter"
        return "connector_guard" if ast >= 15 else "two_way_wing"
    if primary == "SF":
        if usg >= 23:
            return "scoring_wing"
        if three_rate >= 0.45 and usg < 21:
            return "movement_shooter"
        if ast >= 18:
            return "versatile_forward"
        return "two_way_wing"
    if primary == "PF":
        if three_rate >= 0.3:
            return "stretch_big"
        if usg >= 24 or ast >= 15:
            return "versatile_forward"
        if blk >= 6:
            return "rim_protecting_big"
        return "energy_big"
    if blk >= 5.5:
        return "rim_protecting_big"
    if three_rate >= 0.25:
        return "stretch_big"
    if ast >= 15:
        return "versatile_forward"
    return "energy_big"


def class_year_label(entry: dict[str, Any]) -> str:
    return {"Fr": "Freshman", "So": "Sophomore", "Jr": "Junior", "Sr": "Senior"}.get(
        str(entry.get("class_year_at_draft") or ""), "Senior")


# ------------------------------------------------------------------------------------------- skills


def soft_bounded(value: float, low: float = 5.0, high: float = 95.0) -> float:
    """Rescale into (low, high) smoothly: nearly linear in the middle, no clipping or pile-up at the ends."""
    mid, half = (low + high) / 2, (high - low) / 2
    return mid + half * math.tanh((value - mid) / half)


def draft_trait_values(entry: dict[str, Any], current: float) -> dict[str, float]:
    """Broad draft traits shaped by college production, centred where generated traits sit for this level."""
    center = (current + 55.0) / 2
    scores = entry.get("skill_scores") or {}
    out = {}
    for key, z in scores.items():
        z = 2.5 * math.tanh(float(z) / 2.5)
        out[key] = round(soft_bounded(center + TRAIT_POINTS_PER_SD * z), 2)
    return out


def input_targets(college: dict[str, Any], overall_pick: int | float | None, root: str | Path | None = None) -> dict[str, list[float]]:
    """Entry estimate of each college-informed 94 input and its weight: {input_id: [value, weight]}."""
    mapping = (bundle(root).get("input_mapping") or {}).get("targets") or {}
    parts = college.get("input_parts") or {}
    pick = max(1.0, float(overall_pick or college.get("projected_pick") or 30))
    minutes = float(college.get("effective_minutes") or 0.0)
    reliability = minutes / (minutes + RELIABILITY_MINUTES) if minutes > 0 else 0.0
    out = {}
    for iid, part in parts.items():
        fit = mapping.get(iid)
        if not fit:
            continue
        value = (fit["intercept"] + float(part) + fit["years_coef"] * (0 - 3)
                 + fit["log_pick_coef"] * (math.log(pick) - 3))
        weight = min(INPUT_WEIGHT_MAX, INPUT_WEIGHT_BASE + INPUT_WEIGHT_PER_R * max(0.0, fit.get("r_college", 0.0)))
        out[iid] = [round(value, 4), round(weight * reliability, 4)]
    return out


# ------------------------------------------------------------------------------------------- prospect records


def college_block(entry: dict[str, Any]) -> dict[str, Any]:
    """What the prospect carries about his college career (shown on the card; read when he is drafted)."""
    profile = entry.get("projected_profile") or {}
    keep = ("usg", "ts", "ast_pct", "tov_pct", "orb_pct", "drb_pct", "blk_pct", "stl_pct", "ftr", "gbpm",
            "three_rate", "ft_pct", "three_pct", "rim_pct", "min_pct")
    return {
        "barttorvik_id": entry.get("barttorvik_id"), "team": entry.get("college_team"),
        "conference": entry.get("conference"), "coach": entry.get("coach"),
        "class_year_now": entry.get("class_year_now"), "class_year_at_draft": entry.get("class_year_at_draft"),
        "role": entry.get("role"), "recruit_rating": entry.get("recruit_rating"), "hometown": entry.get("hometown"),
        "projected_pick": entry.get("projected_pick"), "draft_probability": entry.get("draft_probability"),
        "class_rank": entry.get("class_rank"), "birth_date": entry.get("birth_date"),
        "age_estimated": bool(entry.get("age_estimated")), "effective_minutes": entry.get("effective_minutes"),
        "profile": {k: profile[k] for k in keep if k in profile},
        "skill_scores": dict(entry.get("skill_scores") or {}),
        "input_parts": dict(entry.get("input_parts") or {}),
        "seasons": list(entry.get("seasons") or []),
        "source_season": bundle().get("current_college_season"),
    }


def neutral_medical_profile() -> dict[str, Any]:
    """No medical records exist for real college players here; do not invent an injury history for them."""
    return {"durability": 70.0, "injury_prone": False, "body_area_risk_tags": [], "major_prior_injuries": [],
            "current_injury": None, "origin": "real_college_prospect_no_medical_data_v1"}


# ------------------------------------------------------------------------------------------- card


def _season_summary(card: dict[str, Any]) -> dict[str, Any]:
    """A college season in the shape of the player card's season line (per-game numbers, real totals)."""
    return {**card, "college_team": card.get("team"), "team_games": None, "team_abbrevs": []}


def college_card(college: dict[str, Any]) -> dict[str, Any]:
    """Prospect-card block: who he plays for and the college profile the game reads his skills from."""
    profile = college.get("profile") or {}

    def pct(key: str) -> float | None:
        value = profile.get(key)
        return None if value is None else round(100 * float(value), 1)

    def rate(key: str) -> float | None:
        value = profile.get(key)
        return None if value is None else round(float(value), 1)

    stats = [
        ["USG%", rate("usg"), "Usage: share of team plays he finishes while on the floor"],
        ["AST%", rate("ast_pct"), "Assist rate"],
        ["TOV%", rate("tov_pct"), "Turnover rate"],
        ["3PA%", pct("three_rate"), "Share of his shots that are threes"],
        ["3P%", pct("three_pct"), "Three-point percentage over his college career, small samples shrunk"],
        ["FT%", pct("ft_pct"), "Free-throw percentage over his college career, small samples shrunk"],
        ["FTR", rate("ftr"), "Free-throw rate: free-throw attempts per 100 shots"],
        ["OREB%", rate("orb_pct"), "Offensive rebound rate"],
        ["DREB%", rate("drb_pct"), "Defensive rebound rate"],
        ["BLK%", rate("blk_pct"), "Block rate"],
        ["STL%", rate("stl_pct"), "Steal rate"],
        ["BPM", rate("gbpm"), "Box plus-minus"],
    ]
    return {
        "team": college.get("team"), "conference": college.get("conference"), "coach": college.get("coach"),
        "class_year": college.get("class_year_now"), "role": college.get("role"),
        "recruit_rating": college.get("recruit_rating"), "projected_pick": college.get("projected_pick"),
        "draft_probability": college.get("draft_probability"),
        "stats": stats,
        "stats_note": ("Projected for his draft season: this season's games blended with last season (or his "
                       "recruiting class) and his shooting history. These numbers set his skills in the game."),
        "seasons": [_season_summary(card) for card in college.get("seasons") or []],
    }
