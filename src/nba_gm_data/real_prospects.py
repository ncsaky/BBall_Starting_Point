"""Real players as draft prospects for the first future drafts of a new save (2027-2029).

The derived bundle data/canonical/real_prospects.json (rebuilt by scripts/research/real_prospects.py from the local
Barttorvik college tables and the scouting files under data/research/prospect_scouting/) is a pool of real players:
current college players, the top high-school recruits of the classes of 2027 and 2028, and international prospects.
Each carries
- chance_by_year: his chance of being drafted in 2027, 2028 and 2029 (the rest: later or never). For 2027 the
  scouts' consensus big board leads and the college model gains weight as games are played;
- years: what he looks like in each draft he could enter (age, class year, expected pick there and, for college
  players, his college profile projected to that season);
- scouting: consensus or recruiting rank, where it comes from, and the scouts' strengths and concerns.

Who declares when differs by save: each save draws, from its seed and the player, the one draft he enters
(declaration_year). draft.generate_draft_class_records(..., real_prospects=True) then places the declared players
by expected pick and fills every other slot with the generated prospect anchored to that slot, so class size, level
by slot, upside spread, class strength and the position mix stay those of a generated class. Years outside the
bundle stay fully generated and unchanged.
"""
from __future__ import annotations

import json
import math
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

from .utils import stable_id

BUNDLE_FILE = Path("data/canonical/real_prospects.json")
SOURCE_ID = "src_barttorvik_college_prospects_v1"
SOURCE_TITLE = "Barttorvik (T-Rank) college player tables: real-prospect draft projection and college profiles"
SOURCE_NOTES = ("College player-seasons 2008-2027 (local tables, not redistributed). The game uses only the derived "
                "bundle data/canonical/real_prospects.json: chance of being drafted per year, expected pick, college "
                "team and profile, and fitted college-to-NBA skill relationships. Rebuild with "
                "scripts/research/real_prospects.py.")
SCOUTING_SOURCE_ID = "src_prospect_scouting_boards_v1"
SCOUTING_SOURCE_TITLE = "Public 2027 draft boards and mock drafts; 247Sports Composite recruiting ranks (classes of 2027-2028)"
SCOUTING_SOURCE_NOTES = ("data/research/prospect_scouting/: eight 2027 big boards and mocks (ESPN, FanSided, Bleacher "
                         "Report, CBS, ClutchPoints, SI, Tankathon), 247Sports Composite and partial ESPN recruit ranks, "
                         "international prospect notes. Ranks are facts; strength/weakness tags are paraphrased. They "
                         "set the 2027 order, recruits' and internationals' draft timing and their skill shape.")

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
# Scouts' strength / concern tags in standard-score units: one tag is one standard deviation on its skill for a
# player without college numbers (his only evidence besides size and position); half that for a college player,
# whose own numbers already speak to the skill.
TAG_WEIGHT_NO_STATS = 1.0
TAG_WEIGHT_COLLEGE = 0.5

KIND_LEAGUE = {"college": "NCAA", "college_no_stats": "NCAA", "high_school": "High School", "international": "International"}


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


def clear_caches() -> None:
    _load.cache_clear()
    _class_entries.cache_clear()


def draft_years(root: str | Path | None = None) -> set[str]:
    return {str(year) for year in bundle(root).get("draft_years", [])}


def enabled(config: dict[str, Any] | None) -> bool:
    return bool(((config or {}).get("real_prospects") or {}).get("enabled", True))


def prospect_id(year: str | int, name: str) -> str:
    return stable_id("draft_prospect", str(year), name)


# ------------------------------------------------------------------------------------------- who declares when


def declaration_year(entry: dict[str, Any], seed: int) -> str | None:
    """The draft this player enters in the save with this seed (None: later than the bundle's years, or never).

    One uniform draw per save and player against his chances by year, so he is in at most one class per save, the
    same save always gets the same answer, and different saves differ for players whose timing is uncertain."""
    u = random.Random(f"{int(seed)}:{entry.get('id')}:declare_v1").random()
    total = 0.0
    for year in sorted(entry.get("chance_by_year") or {}):
        total += float(entry["chance_by_year"][year] or 0.0)
        if u < total:
            return str(year)
    return None


def _slot_for_rank(table: Any, k: int, used: set[int], size: int) -> int:
    if isinstance(table, list) and table:
        slot = int(round(table[k - 1])) if k <= len(table) else int(round(table[-1])) + (k - len(table))
    else:  # "rank": the boards see the whole draft, the k-th declared player goes k-th
        slot = k
    slot = max(1, slot)
    while slot in used:
        slot += 1
    return slot if slot <= size else 0


@lru_cache(maxsize=64)
def _class_entries(year: str, seed: int, root: str) -> tuple[dict[str, Any], ...]:
    data = _load(str(Path(root) / BUNDLE_FILE))
    declared = []
    for entry in data.get("prospects", []):
        if year in (entry.get("years") or {}) and declaration_year(entry, seed) == year:
            declared.append(entry)
    declared.sort(key=lambda e: (float(e["years"][year]["expected_pick"]), str(e["id"])))
    table = (data.get("slot_tables") or {}).get(year, "rank")
    size = int(data.get("class_size") or 60)
    used: set[int] = set()
    out = []
    for k, entry in enumerate(declared, start=1):
        slot = _slot_for_rank(table, k, used, size)
        if not slot:
            break  # more declared real players than draft slots: the rest go undrafted this year
        used.add(slot)
        out.append(class_entry(entry, year, slot=slot, class_rank=k))
    return tuple(out)


def class_entries(year: str | int, seed: int, root: str | Path | None = None) -> list[dict[str, Any]]:
    """The real players who enter this draft in the save with this seed, flattened for the class builder, with the
    slot they are anchored to (ordered by expected pick; see slot_tables in the bundle)."""
    if root is None:
        from .resource_paths import game_resource_root
        root = game_resource_root()
    return [dict(e) for e in _class_entries(str(year), int(seed), str(root))]


def class_entry(entry: dict[str, Any], year: str, *, slot: int | None = None, class_rank: int | None = None) -> dict[str, Any]:
    """One pool player as he looks in one draft year (his projected profile, age and class year there)."""
    view = entry["years"][year]
    out = {k: v for k, v in entry.items() if k not in {"years", "chance_by_year", "model"}}
    out.update({
        "draft_year": str(year), "projected_pick": slot or int(round(float(view["expected_pick"]))),
        "class_rank": class_rank, "expected_pick_if_drafted": view["expected_pick"],
        "draft_probability": (entry.get("chance_by_year") or {}).get(year),
        "chance_by_year": dict(entry.get("chance_by_year") or {}),
        "age_at_draft": view.get("age_at_draft"), "class_year_at_draft": view.get("class_year_at_draft"),
        "projected_profile": view.get("projected_profile"),
        "effective_minutes": view.get("effective_minutes", entry.get("effective_minutes")),
    })
    out["skill_scores"] = view_skill_scores(out)
    out["input_parts"] = input_parts(out["projected_profile"], bundle_mapping(), out.get("height_inches"))
    return out


def bundle_mapping() -> dict[str, Any]:
    return bundle().get("input_mapping") or {}


def pool_entry_for(year: str | int, identity: str) -> dict[str, Any] | None:
    """The pool player whose prospect id in this draft year is `identity` (any save)."""
    year = str(year)
    for entry in bundle().get("prospects", []):
        if year in (entry.get("years") or {}) and prospect_id(year, entry["name"]) == identity:
            return class_entry(entry, year)
    return None


def real_entry_for(prospect: dict[str, Any] | None) -> dict[str, Any] | None:
    """{"college": block or None, "scouting": block or None} for a real prospect (None for generated prospects)."""
    if not isinstance(prospect, dict):
        return None
    stats = prospect.get("public_stats") or {}
    if stats.get("college") or stats.get("scouting"):
        return {"college": stats.get("college"), "scouting": stats.get("scouting")}
    if prospect.get("league") == "generated":
        return None
    identity = prospect.get("id") or prospect.get("prospect_id")
    year = prospect.get("draft_year")
    if not identity or not year:
        return None
    entry = pool_entry_for(year, identity)
    if entry is None:
        return None
    return {"college": college_block(entry) if entry.get("projected_profile") else None, "scouting": scouting_block(entry)}


def college_entry_for(prospect: dict[str, Any] | None) -> dict[str, Any] | None:
    """The college block stored on a real college prospect (None for generated and non-college prospects)."""
    real = real_entry_for(prospect)
    return (real or {}).get("college")


# ------------------------------------------------------------------------------------------- identity and role


def position_for(entry: dict[str, Any]) -> str:
    if entry.get("position"):
        return str(entry["position"])
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
    """The generator's archetype vocabulary, read from the college profile (or, without one, the skill shape)."""
    p = entry.get("projected_profile")
    if not p:
        return archetype_from_skills(entry.get("skill_scores") or {}, position)
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


def archetype_from_skills(scores: dict[str, float], position: str) -> str:
    """Archetype for a prospect known from scouting only: his standout skills within his position."""
    s = lambda key: float(scores.get(key, 0.0))
    primary = position.split("/")[0]
    if primary in {"PG", "SG"}:
        if s("passing") >= 0.6 and s("passing") >= s("shot_creation") - 0.3:
            return "lead_creator" if s("shot_creation") >= 0.3 else "connector_guard"
        if s("rim_pressure") >= 0.6 and s("rim_pressure") >= s("shooting"):
            return "rim_pressure_guard"
        if s("shot_creation") >= 0.6:
            return "scoring_wing" if primary == "SG" else "lead_creator"
        if s("shooting") >= 0.6:
            return "movement_shooter"
        return "connector_guard" if primary == "PG" or s("passing") > s("defense") else "two_way_wing"
    if primary == "SF":
        if s("shot_creation") >= 0.6:
            return "scoring_wing"
        if s("passing") >= 0.6:
            return "versatile_forward"
        if s("shooting") >= 0.8 and s("defense") < 0.5:
            return "movement_shooter"
        return "two_way_wing"
    if primary == "PF":
        if s("shooting") >= 0.5:
            return "stretch_big"
        if s("passing") >= 0.5 or s("shot_creation") >= 0.6:
            return "versatile_forward"
        if s("rim_protection") >= 0.8:
            return "rim_protecting_big"
        return "energy_big"
    if s("rim_protection") >= 0.5:
        return "rim_protecting_big"
    if s("shooting") >= 0.5:
        return "stretch_big"
    if s("passing") >= 0.6:
        return "versatile_forward"
    return "energy_big"


def class_year_label(entry: dict[str, Any]) -> str:
    if entry.get("kind") == "international":
        return "International"
    return {"Fr": "Freshman", "So": "Sophomore", "Jr": "Junior", "Sr": "Senior"}.get(
        str(entry.get("class_year_at_draft") or ""), "Senior")


def league_for(entry: dict[str, Any]) -> str:
    return KIND_LEAGUE.get(str(entry.get("kind") or "college"), "NCAA")


def source_team_for(entry: dict[str, Any]) -> str | None:
    """College team, club, or (for high-school recruits) the college he committed to, else his school."""
    if entry.get("college_team"):
        return entry["college_team"]
    scouting = entry.get("scouting") or {}
    return scouting.get("committed_to") or scouting.get("team") or None


# ------------------------------------------------------------------------------------------- skills

# Broad draft traits from college rates: weights on standardized rates (against drafted players' final seasons);
# each composite is then rescaled to unit spread over that same drafted pool. Shared with the builder.
SKILL_COMPOSITES = {
    "shooting": {"ft_pct": 0.4, "three_pct": 0.3, "three_rate": 0.2, "three_per40": 0.1},
    "shot_creation": {"usg": 0.45, "unast_per40": 0.35, "unast_three": 0.2},
    "rim_pressure": {"rim_per40": 0.4, "ftr": 0.35, "dunk_per40": 0.25},
    "passing": {"ast_pct": 0.65, "ast_to": 0.35},
    "defense": {"stl_pct": 0.45, "dgbpm": 0.35, "blk_pct": 0.2},
    "rim_protection": {"blk_pct": 0.75, "height_c": 0.25},
    "rebounding": {"drb_pct": 0.5, "orb_pct": 0.5},
    "feel": {"ast_to": 0.3, "gbpm": 0.4, "tov_pct": -0.3},
    "athleticism": {"dunk_per40": 0.35, "stl_pct": 0.2, "blk_pct": 0.15, "rim_per40": 0.15, "orb_pct": 0.15},
    "size": {"height_c": 1.0},
    "motor": {"orb_pct": 0.4, "stl_pct": 0.3, "min_pct": 0.3},
    "nba_readiness": {"gbpm": 0.5, "ortg": 0.25, "min_pct": 0.25},
}
PROFILE_RATES = ("min_pct", "usg", "ortg", "ts", "orb_pct", "drb_pct", "ast_pct", "tov_pct", "blk_pct", "stl_pct",
                 "ftr", "gbpm", "ogbpm", "dgbpm", "three_rate", "three_per40", "rim_per40", "dunk_per40",
                 "unast_per40", "unast_three", "ast_to", "fouls40")


def pair_features(rates: dict, shoot: dict, height: float | None) -> dict[str, float]:
    return {**{k: rates[k] for k in PROFILE_RATES}, **{k: shoot[k] for k in ("ft_pct", "three_pct", "rim_pct", "mid_pct")},
            "height_c": (height or 78) - 78}


def composite(x: dict, weights: dict, rates: dict) -> float:
    return sum(w * (x[k] - rates[k][0]) / rates[k][1] for k, w in weights.items())


def skill_scores(x: dict, norms: dict) -> dict[str, float]:
    """Standard scores of each broad skill against drafted college players (0 = typical draftee)."""
    return {skill: round(composite(x, weights, norms["rates"]) / norms["composite_sd"][skill], 3)
            for skill, weights in SKILL_COMPOSITES.items()}


def size_score(height: float | None, norms: dict) -> float:
    rates = norms["rates"]
    return round(((height or 78) - 78 - rates["height_c"][0]) / rates["height_c"][1] / norms["composite_sd"]["size"], 3)


def input_parts(profile: dict | None, mapping: dict, height: float | None = None) -> dict[str, float]:
    """College part of each fitted 94-input target (the game adds the intercept, years and draft-slot terms)."""
    if not profile:
        return {}
    x = pair_features(profile, profile, height if height is not None else profile.get("height_inches"))
    out = {}
    for iid, fit in (mapping.get("targets") or {}).items():
        out[iid] = round(sum(c * (x[k] - m) / sd for k, c, m, sd in zip(fit["features"], fit["coef"], fit["means"], fit["sds"])), 3)
    return out


def view_skill_scores(entry: dict[str, Any]) -> dict[str, float]:
    """Broad skills as standard scores: college numbers (projected to this draft) or, without them, the position's
    typical draftee and his size; plus the scouts' strength and concern tags."""
    norms = bundle().get("college_norms") or {}
    profile = entry.get("projected_profile")
    if profile and norms:
        x = pair_features(profile, profile, entry.get("height_inches"))
        base, tag_weight = skill_scores(x, norms), TAG_WEIGHT_COLLEGE
    else:
        base, tag_weight = dict(entry.get("skill_base") or {}), TAG_WEIGHT_NO_STATS
    tags = entry.get("tag_scores") or {}
    return {key: round(float(base.get(key, 0.0)) + tag_weight * float(tags.get(key, 0.0)), 3) for key in SKILL_COMPOSITES}


def soft_bounded(value: float, low: float = 5.0, high: float = 95.0) -> float:
    """Rescale into (low, high) smoothly: nearly linear in the middle, no clipping or pile-up at the ends."""
    mid, half = (low + high) / 2, (high - low) / 2
    return mid + half * math.tanh((value - mid) / half)


def draft_trait_values(entry: dict[str, Any], current: float) -> dict[str, float]:
    """Broad draft traits shaped by college production / scouting, centred where generated traits sit for this level."""
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
    """What a real college prospect carries about his college career (shown on the card; read when he is drafted)."""
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


def scouting_block(entry: dict[str, Any]) -> dict[str, Any] | None:
    """The scouts' view carried by every real prospect: where he plays, his rank and the scouts' tags."""
    scouting = entry.get("scouting") or {}
    if not scouting and entry.get("kind") == "college":
        return None
    return {
        "kind": entry.get("kind"), "team": scouting.get("team") or entry.get("college_team"),
        "league": scouting.get("league"), "country": scouting.get("country"),
        "committed_to": scouting.get("committed_to"), "hs_class": scouting.get("hs_class"),
        "consensus_rank": scouting.get("consensus_rank"), "board_count": scouting.get("board_count"),
        "source_ranks": dict(scouting.get("source_ranks") or {}),
        "recruit_ranks": dict(scouting.get("recruit_ranks") or {}),
        "strengths": list(scouting.get("strengths") or []), "weaknesses": list(scouting.get("weaknesses") or []),
        "draft_probability": entry.get("draft_probability"),
        "chance_by_year": dict(entry.get("chance_by_year") or {}),
    }


def neutral_medical_profile() -> dict[str, Any]:
    """No medical records exist for real prospects here; do not invent an injury history for them."""
    return {"durability": 70.0, "injury_prone": False, "body_area_risk_tags": [], "major_prior_injuries": [],
            "current_injury": None, "origin": "real_college_prospect_no_medical_data_v1"}


# ------------------------------------------------------------------------------------------- card


def _season_summary(card: dict[str, Any]) -> dict[str, Any]:
    """A college season in the shape of the player card's season line (per-game numbers, real totals)."""
    return {**card, "college_team": card.get("team"), "team_games": None, "team_abbrevs": []}


OUTLET_LABELS = {
    "espn_2027_bigboard": "ESPN", "fansided_2027_bigboard": "FanSided", "br_2027_bigboard": "Bleacher Report",
    "br_2027_mock_nov": "B/R mock", "cbs_2027_mock": "CBS mock", "clutchpoints_2027_mock": "ClutchPoints mock",
    "si_2027_bigboard_june": "SI (June)", "tankathon_2027_bigboard": "Tankathon",
    "247_composite_2027": "247Sports", "247_composite_2028": "247Sports", "espn_scnext100_2027": "ESPN",
}


def scouting_card(scouting: dict[str, Any] | None) -> dict[str, Any] | None:
    """Prospect-card block: rank and where it comes from, and the scouts' strengths and concerns."""
    if not scouting:
        return None
    rank_label, rank_hint = None, None
    if scouting.get("consensus_rank"):
        ranks = sorted(scouting.get("source_ranks", {}).items(), key=lambda item: item[1])
        rank_label = f"Consensus #{scouting['consensus_rank']} · {scouting.get('board_count') or len(ranks)} draft boards"
        rank_hint = "2027 big boards and mocks: " + ", ".join(f"{OUTLET_LABELS.get(k, k)} #{v}" for k, v in ranks)
    elif scouting.get("recruit_ranks"):
        ranks = scouting["recruit_ranks"]
        composite = next((v for k, v in ranks.items() if k.startswith("247")), None)
        espn = next((v for k, v in ranks.items() if k.startswith("espn")), None)
        parts = [f"247Sports #{composite}" if composite else None, f"ESPN #{espn}" if espn else None]
        rank_label = f"Recruit · class of {scouting.get('hs_class')}: " + " · ".join(p for p in parts if p)
        rank_hint = "High-school recruiting rank (247Sports Composite; ESPN where listed)"
    elif scouting.get("kind") == "international":
        rank_label = "International prospect · unranked"
        rank_hint = "Youth-tournament standout; not on the public big boards"
    where = [scouting.get("team"), scouting.get("country")]
    if scouting.get("committed_to") and scouting.get("committed_to") != scouting.get("team"):
        where.append(f"committed to {scouting['committed_to']}")
    elif scouting.get("kind") == "high_school":
        where.append("uncommitted")
    chances = scouting.get("chance_by_year") or {}
    return {
        "rank_label": rank_label, "rank_hint": rank_hint,
        "where": " · ".join(str(w) for w in where if w),
        "strengths": scouting.get("strengths") or [], "weaknesses": scouting.get("weaknesses") or [],
        "declare_note": ("Chance he is drafted in " + ", ".join(f"{y}: {round(100 * float(p))}%" for y, p in sorted(chances.items()) if p)
                         + ". Each save draws when he declares.") if chances else None,
    }


def college_card(college: dict[str, Any] | None, scouting: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Prospect-card block: who he plays for and the college profile the game reads his skills from."""
    if not college:
        return None
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
