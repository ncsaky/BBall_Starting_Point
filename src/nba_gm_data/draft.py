from __future__ import annotations

import json
import math
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

from .schema import (
    CANONICAL_SEASON,
    CANONICAL_START_DATE,
    DraftBoardEntry,
    DraftClass,
    DraftLotteryResult,
    DraftOrderPick,
    DraftPickDecision,
    DraftProspect,
    DraftProspectTrait,
    DraftRights,
    DraftSelection,
    DraftTradeCandidate,
    RookieContractProjection,
    ScoutingReport,
    TransactionLog,
    to_plain,
)
from .spatial import invalidate_spatial_cache, prospect_spatial_fit_delta
from .health import generated_prospect_medical_profile, prospect_medical_penalty
from . import real_prospects as real_prospect_data
from . import draft_scouting
from .faces import assign_class_faces, prospect_headshot_url
from .talent import SOURCE_ID as TALENT_SOURCE_ID, enabled as talent_enabled, modeled as talent_modeled, diverse_prospect_skills, career_trait_profile
from .transactions import (
    compact_player,
    candidate_from_decision,
    evaluate_trade_decision,
    evaluate_trade,
    pick_asset_value,
    pick_by_id,
    player_by_id,
    prepare_ai_trade_candidate,
    resolve_team,
    team_by_id,
    with_transaction_context,
)
from .utils import clamp, maybe_float, normalize_name, parse_inches, stable_id


DRAFT_MODEL_CONFIG_FILE = Path("data/overrides/draft_model_config.json")
DRAFT_TRAITS = [
    "shot_creation",
    "shooting",
    "rim_pressure",
    "passing",
    "defense",
    "rim_protection",
    "rebounding",
    "feel",
    "athleticism",
    "size",
    "motor",
    "nba_readiness",
]

NBA_TRAIT_LABELS = {
    "release_speed": "Release Speed",
    "shooting_range": "Shooting Range",
    "shot_versatility": "Shot Versatility",
    "rim_pressure": "Rim Pressure",
    "handle_pressure": "Handle Under Pressure",
    "passing_reads": "Passing Reads",
    "foot_speed_lateral_agility": "Foot Speed / Lateral Agility",
    "stamina_cardio": "Stamina / Cardio",
    "defensive_effort": "Defensive Effort",
    "scheme_iq": "Scheme IQ",
    "rim_deterrence": "Rim Deterrence",
    "screen_navigation": "Screen Navigation",
    "offensive_rebounding": "Offensive Rebounding",
    "portability": "Portability",
    "playoff_translation": "Playoff Translation",
}


# The general manager's layer (draft-boards plan, user decision 2026-11-19): the scouts' board is talent only
# (draft_scouting); the GM adds the team's context. Weights are in the scouts' grade points (a slot near the top
# of the draft is worth about 0.6 of a point).
GM_NEED_WEIGHTS = ((5, 0.05), (14, 0.10), (30, 0.20), (60, 0.25))  # per point of need fit, by pick
GM_PHASE_UPSIDE = 0.10  # rebuilding/developing: per point of upside room beyond a typical prospect's
GM_PHASE_READY = 0.14  # contending: per point of current level above a typical first-rounder's
GM_TYPICAL_ROOM = 22.0
GM_TYPICAL_CURRENT = 54.0
GM_CONTENDER_RISK = 0.03  # contenders dislike volatile prospects a little more than the scouts do
GM_REACH_WEIGHT = 0.25  # per point of slot value paid above the prospect's consensus slot (beyond the tolerance)
GM_REACH_TOLERANCE = 2.0
GM_NEUTRAL_PICK = 15  # the pick used for the GM order shown on pre-draft boards
REBUILD_PHASES = {"rebuilding", "developing"}
CONTEND_PHASES = {"contending", "contending_with_future_upside"}


def default_draft_model_config() -> dict[str, Any]:
    return {
        "version": "draft_model_v1",
        "generated_class_size": 60,
        # Real college players (data/canonical/real_prospects.json) in the first future classes of a new save.
        "real_prospects": {"enabled": True},
        "bpa_gap_threshold": 6.5,
        "need_override_threshold": 10.0,
        "scouting": {
            "base_noise": 7.5,
            "excellent_staff_noise": 3.0,
            "poor_staff_noise": 11.0,
            "minimum_confidence": 0.38,
            "maximum_confidence": 0.88,
        },
        "class_strength": {
            "mean": 58.0,
            "season_variance": 4.5,
            "top_end_variance": 5.5,
            "depth_variance": 4.0,
        },
        "archetype_weights": {
            "lead_creator": 0.11,
            "scoring_wing": 0.12,
            "two_way_wing": 0.13,
            "connector_guard": 0.09,
            "movement_shooter": 0.08,
            "rim_pressure_guard": 0.08,
            "versatile_forward": 0.13,
            "stretch_big": 0.08,
            "rim_protecting_big": 0.1,
            "energy_big": 0.08,
        },
        "lottery": {
            "draw_count": 4,
            "team_count": 14,
            "odds_weights": [140, 140, 140, 125, 105, 90, 75, 60, 45, 30, 20, 15, 10, 5],
            "standings_noise": 1.75,
        },
        "rookie_scale": {
            "first_round_years": 4,
            "second_round_years": 2,
            "first_pick_year1_salary": 12_700_000,
            "first_round_decay": 0.925,
            "first_round_floor": 2_650_000,
            "second_round_year1_salary": 1_350_000,
            "second_round_pick_bonus": 18_000,
            "annual_raise": 0.08,
            "cap_hold_multiplier": 1.2,
        },
        "notes": "Draft generation, scouting fog, board, and AI pick logic config. Values are gameplay tuning constants, not draft research claims.",
    }


def load_draft_model_config(root: str | Path = ".") -> dict[str, Any]:
    path = Path(root) / DRAFT_MODEL_CONFIG_FILE
    config = default_draft_model_config()
    if path.exists():
        from .transactions import deep_merge

        with path.open("r", encoding="utf-8") as handle:
            config = deep_merge(config, json.load(handle))
    return config


def build_draft_context(canonical: dict[str, Any] | Any, draft_research: dict[str, Any] | None, config: dict[str, Any] | None = None,
                        seed: int | None = None) -> dict[str, Any]:
    """The next draft's class, scouting reports and team boards. The stored universe uses seed = the draft year;
    a save with another seed gets its own draw of which real players declare (draft_class_for_save)."""
    canonical = with_transaction_context(canonical)
    config = config or default_draft_model_config()
    draft_year = str(int(str(CANONICAL_SEASON).split("-")[0]) + 1)
    if draft_year == "2026" and draft_research:
        draft_classes, prospects, traits = build_2026_draft_records(
            draft_research, config
        )
    else:
        generated = generate_draft_class_records(
            draft_year, seed=int(seed if seed is not None else draft_year), config=config, talent_model=talent_enabled(canonical),
            real_prospects=real_prospect_data.enabled(config),
        )
        draft_classes = generated["draft_classes"]
        prospects = generated["draft_prospects"]
        traits = generated["draft_prospect_traits"]
    working = {**canonical, "draft_classes": to_plain(draft_classes), "draft_prospects": to_plain(prospects), "draft_prospect_traits": to_plain(traits)}
    reports = build_scouting_reports(working, prospects, traits, config)
    working["scouting_reports"] = to_plain(reports)
    board_entries = build_draft_board_entries(working, prospects, reports, config)
    return {
        "draft_classes": to_plain(draft_classes),
        "draft_prospects": to_plain(prospects),
        "draft_prospect_traits": to_plain(traits),
        "scouting_reports": to_plain(reports),
        "draft_board_entries": to_plain(board_entries),
    }


REAL_CLASS_TYPE = "real_college_plus_generated"
_SAVE_CLASS_CACHE: dict[tuple[int, int], tuple[dict[str, Any], dict[str, Any]]] = {}


def draft_class_for_save(canonical: dict[str, Any], seed: Any) -> dict[str, Any]:
    """The starting universe with the next draft drawn for this save's seed.

    The stored next-year class (with real prospects) is the draw for seed = draft year. In a save with another
    seed, real players declare in other years (real_prospects.declaration_year), so that save gets its own class,
    scouting reports and team boards: built once per process and seed from the unchanged starting universe and
    returned as the same object every time (callers copy it; runtime baseline copies stay cached)."""
    if not isinstance(canonical, dict) or seed is None:
        return canonical
    stored = next((c for c in canonical.get("draft_classes") or [] if c.get("class_type") == REAL_CLASS_TYPE), None)
    if stored is None or int(stored.get("seed") or 0) == int(seed):
        return canonical
    key = (id(canonical), int(seed))
    hit = _SAVE_CLASS_CACHE.get(key)
    if hit is not None and hit[0] is canonical:
        return hit[1]
    year = str(stored.get("season"))
    source = {k: v for k, v in canonical.items() if not str(k).startswith("_")}
    context = build_draft_context(source, None, seed=int(seed))
    old_ids = {p.get("id") for p in canonical.get("draft_prospects") or [] if str(p.get("draft_year")) == year}
    replaced = {}
    for collection, records in context.items():
        keep = [r for r in canonical.get(collection) or []
                if str(r.get("season") if collection == "draft_classes" else r.get("draft_year") or "") != year
                and r.get("prospect_id") not in old_ids and r.get("id") not in old_ids]
        replaced[collection] = [*keep, *records]
    overlay = {**canonical, **replaced}
    if len(_SAVE_CLASS_CACHE) >= 8:
        _SAVE_CLASS_CACHE.pop(next(iter(_SAVE_CLASS_CACHE)))
    _SAVE_CLASS_CACHE[key] = (canonical, overlay)
    return overlay


def with_draft_context(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_transaction_context(canonical)
    # Keep generated classes shared across the temporary draft contexts.
    canonical.setdefault("_generated_draft_records_cache", {})
    # The GM's need-fit reads are shared by every draft context made from this universe (one per pick on draft
    # night). They depend on the teams' needs and rosters, which a universe object does not change.
    canonical.setdefault("_draft_need_fit_cache", {})
    canonical.setdefault("_draft_spatial_fit_cache", {})
    if not (canonical.get("draft_classes") and canonical.get("draft_prospects") and canonical.get("draft_board_entries")):
        canonical = {**canonical, **build_draft_context(canonical, None, config)}
    seeds = {str(c["season"]): c.get("seed") or 0 for c in canonical.get("draft_classes", [])}
    prospects = [dict(p) for p in canonical.get("draft_prospects", [])]
    for prospect in prospects:
        if prospect.get("league") == "generated" and not prospect.get("medical_profile"):
            prospect["medical_profile"] = generated_prospect_medical_profile(prospect["id"], prospect["draft_year"], seeds.get(prospect["draft_year"], 0))
    penalties = {p["id"]: prospect_medical_penalty(p) for p in prospects}
    entries = []
    for old in canonical.get("draft_board_entries", []):
        entry = dict(old)
        penalty = penalties.get(entry["prospect_id"], 0.0)
        entry["risk_adjusted_grade"] = round(float(entry["risk_adjusted_grade"]) + float(entry.get("medical_penalty", 0)) - penalty, 2)
        entry["medical_penalty"] = penalty
        entries.append(entry)
    return {**canonical, "draft_prospects": prospects, "draft_board_entries": entries}


def build_2026_draft_records(draft_research: dict[str, Any] | None, config: dict[str, Any]) -> tuple[list[DraftClass], list[DraftProspect], list[DraftProspectTrait]]:
    rows = (draft_research or {}).get("prospects", [])
    if not rows:
        generated = generate_draft_class_records("2026", seed=2026, config=config)
        return generated["draft_classes"], generated["draft_prospects"], generated["draft_prospect_traits"]
    prospects: list[DraftProspect] = []
    traits: list[DraftProspectTrait] = []
    for row in sorted(rows, key=lambda item: int(item.get("mock_rank") or item.get("rank") or 999)):
        prospect = prospect_from_research_row(row, "2026")
        prospects.append(prospect)
        traits.extend(prospect_traits_from_row(prospect, row))
    strength = sum(prospect.potential for prospect in prospects[:14]) / max(1, min(14, len(prospects)))
    depth = sum(prospect.potential for prospect in prospects[14:45]) / max(1, min(31, max(0, len(prospects) - 14)))
    draft_class = DraftClass(
        id=stable_id("draft_class", "2026"),
        season="2026",
        class_type="real_public_source_bundle",
        seed=None,
        class_strength=round((strength * 0.58 + depth * 0.42), 2),
        top_end_strength=round(strength, 2),
        depth_strength=round(depth, 2),
        prospect_count=len(prospects),
        source_ids=sorted({source for prospect in prospects for source in prospect.source_ids}),
        notes="2026 draft class from free public source bundle. Existing pick order/ownership remains in DraftPick records.",
    )
    return [draft_class], prospects, traits


def prospect_from_research_row(row: dict[str, Any], draft_year: str) -> DraftProspect:
    rank = int(row.get("mock_rank") or row.get("rank") or 60)
    stats = row.get("public_stats") or {}
    position = str(row.get("position") or "UNK")
    age = whole_prospect_age(row.get("age"))
    archetype = infer_prospect_archetype(position, stats)
    current, potential, floor, ceiling, volatility = prospect_grades(rank, age, position, stats, archetype)
    source_ids = list(row.get("source_ids") or ["src_tankathon_2026_mock_draft"])
    if rank <= 14:
        confidence = 0.72
    elif rank <= 30:
        confidence = 0.64
    else:
        confidence = 0.56
    return DraftProspect(
        id=stable_id("draft_prospect", draft_year, row.get("player")),
        draft_year=draft_year,
        name=str(row.get("player")),
        normalized_name=normalize_name(row.get("player")),
        rank=rank,
        rank_range=dict(row.get("rank_range") or {"low": rank, "high": rank}),
        position=position,
        source_team=row.get("source_team"),
        league=str(row.get("league") or "NCAA"),
        class_year=row.get("class_year"),
        age=age,
        height_inches=parse_inches(row.get("height")),
        weight_lbs=maybe_float(row.get("weight_lbs")),
        archetype=archetype,
        current_ability=round(current, 2),
        potential=round(potential, 2),
        floor=round(floor, 2),
        ceiling=round(ceiling, 2),
        development_curve=development_curve(age, row.get("class_year"), archetype),
        volatility=round(volatility, 2),
        rookie_contract_value=round(rookie_contract_value(rank, current, potential), 2),
        public_stats=stats,
        confidence=confidence,
        source_ids=source_ids,
        notes=row.get("notes") or "Draft prospect from public source bundle.",
    )


def prospect_grades(rank: int, age: float | None, position: str, stats: dict[str, Any], archetype: str) -> tuple[float, float, float, float, float]:
    per36 = stats.get("per_36") or {}
    advanced = stats.get("advanced") or {}
    age_bonus = max(-3.0, min(5.0, (20.2 - float(age or 20.2)) * 1.6))
    production = (
        float(per36.get("pts", 14)) * 0.18
        + float(per36.get("reb", 5)) * 0.12
        + float(per36.get("ast", 2)) * 0.16
        + float(per36.get("stl", 0.8)) * 1.2
        + float(per36.get("blk", 0.5)) * 1.0
        + float(advanced.get("bpm", 5)) * 0.45
    )
    rank_signal = 80 - (rank - 1) * 0.66
    potential = clamp(rank_signal + age_bonus + production * 0.42, 35, 96)
    current = clamp(49 + production * 0.55 - rank * 0.18 + max(0, rank_signal - 72) * 0.16, 30, potential - 2)
    floor = clamp(current - 8 - max(0, rank - 20) * 0.08, 20, current)
    ceiling = clamp(potential + 5 + max(0, 12 - rank) * 0.45, potential, 99)
    volatility = clamp(14 + max(0, rank - 10) * 0.14 + max(0, 19.5 - float(age or 19.5)) * 1.4, 5, 34)
    if "International" in str(stats):
        volatility += 1
    if archetype in {"lead_creator", "scoring_wing", "rim_protecting_big"} and rank <= 8:
        ceiling = min(99, ceiling + 2)
    return current, potential, floor, ceiling, volatility


def prospect_traits_from_row(prospect: DraftProspect, row: dict[str, Any]) -> list[DraftProspectTrait]:
    stats = row.get("public_stats") or {}
    values = infer_trait_values(prospect.position, prospect.archetype, stats, prospect.height_inches)
    return [
        DraftProspectTrait(
            id=stable_id("draft_trait", prospect.id, trait_key),
            prospect_id=prospect.id,
            trait_key=trait_key,
            value=round(value, 2),
            confidence=round(min(0.76, prospect.confidence), 3),
            source_ids=prospect.source_ids,
            notes="Inferred true prospect trait from public prospect data and draft model v1.",
        )
        for trait_key, value in values.items()
    ]


def generate_draft_class_records(year: str, seed: int = 1, config: dict[str, Any] | None = None, *, talent_model: bool = False,
                                 real_prospects: bool = False) -> dict[str, Any]:
    """A deterministic future class. With real_prospects, years covered by the real-prospect bundle (2027-2029)
    place real college players at their projected picks and keep the generated prospects of every other slot;
    other years are identical either way."""
    config = config or default_draft_model_config()
    generated = _generated_class_records(str(year), seed, config, talent_model=talent_model)
    if real_prospects and str(year) in real_prospect_data.draft_years():
        return assemble_real_prospect_class(str(year), seed, generated, talent_model=talent_model)
    return generated


def _generated_class_records(year: str, seed: int, config: dict[str, Any], *, talent_model: bool) -> dict[str, Any]:
    rng = random.Random(f"{year}:{seed}:draft_class")
    size = int(config.get("generated_class_size", 60))
    strength_mean = float(config["class_strength"]["mean"])
    class_strength = clamp(rng.gauss(strength_mean, float(config["class_strength"]["season_variance"])), 50, 68)
    top_strength = clamp(
        max(class_strength + 1.5, class_strength + rng.gauss(3.0, float(config["class_strength"]["top_end_variance"]))),
        53,
        74,
    )
    depth_strength = clamp(
        class_strength + rng.gauss(-1.5, float(config["class_strength"]["depth_variance"])),
        50,
        66,
    )
    prospects: list[DraftProspect] = []
    traits: list[DraftProspectTrait] = []
    archetypes = weighted_archetypes(config)
    seen_names: set[str] = set()
    available_source_teams = [*GENERATED_SOURCE_TEAMS, *GENERATED_SOURCE_TEAMS]
    for rank in range(1, size + 1):
        archetype = rng.choices([item[0] for item in archetypes], weights=[item[1] for item in archetypes], k=1)[0]
        position = generated_position(archetype, random.Random(f"{year}:{seed}:{rank}:position_v2"))
        # Keep the main stream's draw count (age, current, potential) so names and the rest of the class keep
        # their own random numbers; the profile below has its own stream.
        rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
        profile = generated_prospect_profile(rank, size, top_strength, depth_strength,
                                             random.Random(f"{year}:{seed}:{rank}:prospect_profile_v2"))
        age = whole_prospect_age(profile["age"])
        current = profile["current"]
        public_potential = generated_prospect_upside(profile["public_potential"], rank, top_strength, year, seed)
        # The true potential carries what scouts cannot see: the hidden upside tail and (in the career-capacity
        # model, where potential shapes growth rather than today's ratings) a scouting miss either way.
        potential = generated_prospect_upside(profile["public_potential"], rank, top_strength, year, seed, talent_model)
        latent_tail = potential - public_potential  # the hidden upside tail: never observable before he plays
        if talent_model:
            potential = clamp(potential + profile["scouting_miss"], current + 1.0, 97.0)
        floor = clamp(current - rng.uniform(5, 13), 20, current)
        ceiling_room = rng.uniform(2, 9)
        ceiling = clamp(potential + ceiling_room, potential, 99)
        volatility = clamp(12 + rng.random() * 17 + max(0, 20 - age) * 1.3, 5, 36)
        name = generated_prospect_name(rng, rank)
        normalized_generated_name = normalize_name(name)
        reroll_count = 0
        while normalized_generated_name in seen_names and reroll_count < 24:
            name = generated_prospect_name(random.Random(f"{year}:{seed}:{rank}:{reroll_count}:name_retry"), rank)
            normalized_generated_name = normalize_name(name)
            reroll_count += 1
        if normalized_generated_name in seen_names:
            name = generated_unique_fallback_name(rank, seen_names)
            normalized_generated_name = normalize_name(name)
        seen_names.add(normalized_generated_name)
        prospect = DraftProspect(
            id=stable_id("draft_prospect", year, name),
            draft_year=year,
            name=name,
            normalized_name=normalized_generated_name,
            rank=rank,
            rank_range={"low": max(1, rank - 3), "high": min(size, rank + 5)},
            position=position,
            source_team=generated_source_team(rng, available_source_teams),
            league="generated",
            class_year=generated_class_year(age),
            age=age,
            height_inches=generated_height(position, rng),
            weight_lbs=generated_weight(position, rng),
            archetype=archetype,
            current_ability=round(current, 2),
            potential=round(potential, 2),
            floor=round(floor, 2),
            ceiling=round(ceiling, 2),
            development_curve=development_curve(age, None, archetype),
            volatility=round(volatility, 2),
            rookie_contract_value=round(rookie_contract_value(rank, current, potential), 2),
            public_stats={},
            confidence=0.46,
            source_ids=["src_draft_model_config_v1", *([TALENT_SOURCE_ID] if talent_model else [])],
            notes="Generated future draft prospect. True ratings are deterministic from year/seed and hidden behind scouting estimates.",
            medical_profile=generated_prospect_medical_profile(stable_id("draft_prospect", year, name), year, seed),
            scouting_prior=({
                "potential": round(public_potential, 2),
                "ceiling": round(clamp(public_potential + ceiling_room, public_potential, 99), 2),
                "rookie_contract_value": round(rookie_contract_value(rank, current, public_potential), 2),
                "latent_tail": round(latent_tail, 2),
            } if potential != public_potential else {}),
        )
        prospects.append(prospect)
        trait_values = generated_trait_values(prospect, rng)
        traits.extend(
            DraftProspectTrait(
                id=stable_id("draft_trait", prospect.id, trait_key),
                prospect_id=prospect.id,
                trait_key=trait_key,
                value=round(value, 2),
                confidence=0.46,
                source_ids=list(prospect.source_ids),
                notes="Generated true prospect trait.",
            )
            for trait_key, value in trait_values.items()
        )
    draft_class = DraftClass(
        id=stable_id("draft_class", year, seed),
        season=year,
        class_type="generated_future_class",
        seed=seed,
        class_strength=round(class_strength, 2),
        top_end_strength=round(top_strength, 2),
        depth_strength=round(depth_strength, 2),
        prospect_count=len(prospects),
        source_ids=["src_draft_model_config_v1"],
        notes="Generated deterministic future draft class with season-to-season talent variance.",
    )
    prospects = assign_class_faces(apply_public_ranks(prospects))  # stock photos, none repeated in the class
    return {"draft_classes": [draft_class], "draft_prospects": prospects, "draft_prospect_traits": traits}


# Real prospects' level comes from their projected slot like a generated prospect's, then production and recruiting:
# a standard score of college readiness (box plus-minus, offensive rating, minutes) moves current ability up to about
# the generator's own random spread; elite recruits carry a little more public upside.
REAL_PRODUCTION_CURRENT = 1.2
REAL_RECRUIT_POTENTIAL_PER_POINT = 0.15
REAL_UNRANKED_POTENTIAL = -1.0
REAL_PUBLIC_POTENTIAL_SPREAD = 3.0
# Share of the public grade (generated_bpa_grade) carried by potential (with ceiling) and by current (with floor):
# per year older, potential falls current-gain x 0.38 / 0.62 so the grade is unchanged.
GRADE_POTENTIAL_SHARE, GRADE_CURRENT_SHARE = 0.62, 0.38


def assemble_real_prospect_class(year: str, seed: int, generated: dict[str, Any], *, talent_model: bool) -> dict[str, Any]:
    """Real college prospects at their projected picks; every other slot keeps the generated prospect made for it.

    Generated prospects are created slot by slot (list order = slot), so keeping the ones at free slots preserves
    the generator's level-by-slot profile, class strength draws, upside spread and position mix for the slots the
    college data cannot fill (international, high-school and G League prospects)."""
    entries = real_prospect_data.class_entries(year, seed)
    gen_prospects = list(generated["draft_prospects"])
    size = len(gen_prospects)
    if not entries or not size:
        return generated
    draft_class = generated["draft_classes"][0]
    real_by_slot: dict[int, dict[str, Any]] = {}
    for entry in entries:
        slot = max(1, int(entry.get("projected_pick") or size))
        while slot in real_by_slot:
            slot += 1
        if slot <= size:
            real_by_slot[slot] = entry
    traits_by_prospect: dict[str, list[DraftProspectTrait]] = {}
    for trait in generated["draft_prospect_traits"]:
        traits_by_prospect.setdefault(trait.prospect_id, []).append(trait)
    prospects: list[DraftProspect] = []
    traits: list[DraftProspectTrait] = []
    real_ids: dict[str, str] = {}
    for slot in range(1, size + 1):
        if slot in real_by_slot:
            prospect, prospect_traits = real_prospect_record(real_by_slot[slot], slot, size, year, seed,
                                                             draft_class.top_end_strength, draft_class.depth_strength,
                                                             talent_model=talent_model)
            real_ids[prospect.id] = str(real_by_slot[slot].get("id") or "")
        else:
            prospect = gen_prospects[slot - 1]
            prospect_traits = traits_by_prospect.get(prospect.id, [])
        prospects.append(prospect)
        traits.extend(prospect_traits)
    draft_class = replace(
        draft_class,
        class_type=REAL_CLASS_TYPE,
        source_ids=[*draft_class.source_ids, real_prospect_data.SOURCE_ID, real_prospect_data.SCOUTING_SOURCE_ID],
        notes=(f"{len(real_by_slot)} real players who declare for this draft in this save (college, high-school "
               "and international prospects; data/canonical/real_prospects.json), placed by expected pick; other "
               "slots generated deterministically from year and seed."),
    )
    # Real players' photos where found (gui/assets/headshots/real), else a stock photo not used in this class.
    prospects = assign_class_faces(apply_public_ranks(prospects), real_ids)
    return {"draft_classes": [draft_class], "draft_prospects": prospects, "draft_prospect_traits": traits}


REAL_PROSPECT_NOTES = {
    "college": ("Real college player who declares for this draft in this save (scouts' boards and the college "
                "projection model). Skills follow his college profile and the scouts' notes; level follows his "
                "slot, age and production."),
    "college_no_stats": ("Real college player on the public boards without games this season. Skills follow the "
                         "scouts' notes, his size and position; level follows his slot and age."),
    "high_school": ("Real high-school recruit (247Sports Composite) who declares for this draft in this save. Skills "
                    "follow the scouts' notes, his size and position; level follows his slot and age."),
    "international": ("Real international prospect who declares for this draft in this save. Skills follow the "
                      "scouts' notes, his size and position; level follows his slot and age."),
}


def real_prospect_record(entry: dict[str, Any], slot: int, size: int, year: str, seed: int, top_strength: float,
                         depth_strength: float, *, talent_model: bool) -> tuple[DraftProspect, list[DraftProspectTrait]]:
    """One real college player as a draft prospect on the generator's scale for his projected slot.

    What every save shares (the public board: level, public upside, body, college profile) uses a stream keyed by
    the player; what scouts cannot see (the hidden upside tail and scouting miss) uses the save's seed."""
    name = str(entry["name"])
    prospect_id = real_prospect_data.prospect_id(year, name)
    public_rng = random.Random(f"{year}:{entry.get('id')}:real_prospect_v1")
    slot60 = max(1, round(slot * 60 / max(1, size)))
    position = real_prospect_data.position_for(entry)
    archetype = real_prospect_data.archetype_for(entry, position)
    typical_age = _slot_value(PROFILE_AGE, slot60)
    raw_age = maybe_float(entry.get("age_at_draft")) or typical_age
    age = whole_prospect_age(raw_age)
    age_gap = age - typical_age
    # The class-strength draw (top_strength / depth_strength) is a save-seed coin flip; it shapes only the generated
    # slots. Real players are who they are in every save: slot profile, age, production and recruiting only.
    # scout_share: how much of his place in the order comes from scouts (2027 boards, recruiting ranks). Scouts'
    # ranks already price in age, pedigree and production, so for that share age only splits now vs later without
    # moving his overall grade, and production, recruiting grade and the public spread do not move it again.
    scout_share = clamp(float(entry.get("scout_share") or 0.0), 0.0, 1.0)
    model_share = 1.0 - scout_share
    readiness = float((entry.get("skill_scores") or {}).get("nba_readiness", 0.0))
    current = (_slot_value(PROFILE_CURRENT, slot60) + AGE_CURRENT_PER_YEAR * age_gap
               + model_share * REAL_PRODUCTION_CURRENT * 2 * math.tanh(readiness / 2))
    recruit = maybe_float(entry.get("recruit_rating"))
    kind = str(entry.get("kind") or "college")
    # Unranked college players carry a little less public upside; internationals and board-only players have no
    # recruiting rank to read (neutral).
    recruit_term = (REAL_RECRUIT_POTENTIAL_PER_POINT * (clamp(recruit, 80, 100) - 90) if recruit is not None
                    else REAL_UNRANKED_POTENTIAL if kind == "college" else 0.0)
    age_potential = (model_share * AGE_POTENTIAL_PER_YEAR
                     + scout_share * AGE_CURRENT_PER_YEAR * GRADE_CURRENT_SHARE / GRADE_POTENTIAL_SHARE)
    public_potential = (_slot_value(PROFILE_POTENTIAL, slot60) - age_potential * age_gap + model_share * recruit_term
                        + model_share * public_rng.gauss(0.0, REAL_PUBLIC_POTENTIAL_SPREAD))
    current = clamp(current, 30.0, 70.0)
    public_potential = clamp(public_potential, current + 1.0, 96.0)
    potential = generated_prospect_upside(public_potential, slot, top_strength, year, seed, talent_model)
    latent_tail = potential - public_potential  # the hidden upside tail: never observable before he plays
    if talent_model:
        miss = random.Random(f"{year}:{seed}:{entry.get('id')}:real_scouting_miss_v1").gauss(0.0, SCOUTING_MISS_SPREAD)
        potential = clamp(potential + miss, current + 1.0, 97.0)
    floor = clamp(current - public_rng.uniform(5, 13), 20, current)
    ceiling_room = public_rng.uniform(2, 9)
    ceiling = clamp(potential + ceiling_room, potential, 99)
    volatility = clamp(12 + public_rng.random() * 17 + max(0, 20 - age) * 1.3, 5, 36)
    height = maybe_float(entry.get("height_inches")) or generated_height(position, public_rng)
    weight = maybe_float(entry.get("weight_lbs")) or generated_weight(position, public_rng)
    college = real_prospect_data.college_block(entry) if entry.get("projected_profile") else None
    scouting = real_prospect_data.scouting_block(entry)
    public_stats = {**({"college": college} if college else {}), **({"scouting": scouting} if scouting else {})}
    source_ids = [real_prospect_data.SOURCE_ID, *([real_prospect_data.SCOUTING_SOURCE_ID] if scouting else []),
                  "src_draft_model_config_v1", *([TALENT_SOURCE_ID] if talent_model else [])]
    class_year = real_prospect_data.class_year_label(entry)
    prospect = DraftProspect(
        id=prospect_id,
        draft_year=year,
        name=name,
        normalized_name=normalize_name(name),
        rank=slot,
        rank_range={"low": max(1, slot - 3), "high": min(size, slot + 5)},
        position=position,
        source_team=real_prospect_data.source_team_for(entry),
        league=real_prospect_data.league_for(entry),
        class_year=class_year,
        age=age,
        height_inches=height,
        weight_lbs=weight,
        archetype=archetype,
        current_ability=round(current, 2),
        potential=round(potential, 2),
        floor=round(floor, 2),
        ceiling=round(ceiling, 2),
        development_curve=development_curve(age, class_year, archetype),
        volatility=round(volatility, 2),
        rookie_contract_value=round(rookie_contract_value(slot, current, potential), 2),
        public_stats=public_stats,
        confidence=0.6,
        source_ids=source_ids,
        notes=REAL_PROSPECT_NOTES.get(kind, REAL_PROSPECT_NOTES["college"]),
        medical_profile=real_prospect_data.neutral_medical_profile(),
        scouting_prior=({
            "potential": round(public_potential, 2),
            "ceiling": round(clamp(public_potential + ceiling_room, public_potential, 99), 2),
            "rookie_contract_value": round(rookie_contract_value(slot, current, public_potential), 2),
            "latent_tail": round(latent_tail, 2),
        } if round(potential, 2) != round(public_potential, 2) else {}),
    )
    tools = 0.0 if talent_model else clamp((potential - 80.0) / 12.0, 0.0, 1.0) * 4.0
    values = real_prospect_data.draft_trait_values(entry, current)
    traits = [
        DraftProspectTrait(
            id=stable_id("draft_trait", prospect_id, key),
            prospect_id=prospect_id,
            trait_key=key,
            value=round(real_prospect_data.soft_bounded(values.get(key, current) + tools), 2),
            confidence=0.6,
            source_ids=list(source_ids),
            notes=("Real prospect trait from his college profile (standard score against drafted college players) "
                   "and the scouts' strength/concern tags." if college else
                   "Real prospect trait from the scouts' strength/concern tags, his size and his position."),
        )
        for key in DRAFT_TRAITS
    ]
    return prospect, traits


def draft_class_payload(canonical: dict[str, Any] | Any, year: str, seed: int = 1, scouted_for: str | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_draft_context(canonical, config)
    year = str(year)
    prospects = [p for p in canonical["draft_prospects"] if str(p.get("draft_year")) == year]
    if prospects:
        draft_classes = [c for c in canonical["draft_classes"] if str(c.get("season")) == year]
        reports = []
        if scouted_for:
            team = resolve_team(canonical, scouted_for)
            prospect_ids = {prospect["id"] for prospect in prospects}
            reports = [
                report
                for report in canonical["scouting_reports"]
                if report["team_id"] == team["id"] and report.get("prospect_id") in prospect_ids
            ]
    else:
        generated = generate_draft_class_records(year, seed=seed, config=config, talent_model=talent_enabled(canonical),
                                                 real_prospects=real_prospect_data.enabled(config))
        prospects = to_plain(generated["draft_prospects"])
        draft_classes = to_plain(generated["draft_classes"])
        reports = []
    display_prospects = []
    for prospect in prospects:
        display_prospect = dict(prospect)
        display_prospect["age"] = whole_prospect_age(display_prospect.get("age"))
        display_prospects.append(display_prospect)
    return {"year": year, "draft_classes": draft_classes, "prospect_count": len(display_prospects), "prospects": display_prospects, "scouting_reports": reports}


def generate_draft_order(canonical: dict[str, Any] | Any, year: str, seed: int = 1, standings: Any | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_draft_context(canonical, config)
    config = config or default_draft_model_config()
    year = str(year)
    if year == "2026" and standings is None:
        picks = sorted(
            [pick for pick in canonical["draft_picks"] if pick.get("season") == "2026" and pick.get("current_owner_team_id")],
            key=lambda item: (int(item.get("round") or 1), pick_overall(item)),
        )
        order = [
            DraftOrderPick(
                id=pick["id"],
                draft_year="2026",
                round=int(pick.get("round") or 1),
                overall_pick=pick_overall(pick),
                original_team_id=pick.get("original_team_id") or pick.get("team_id"),
                current_owner_team_id=pick.get("current_owner_team_id") or pick.get("team_id"),
                pre_lottery_rank=pick_overall(pick) if int(pick.get("round") or 1) == 1 and pick_overall(pick) <= 14 else None,
                lottery_slot=pick_overall(pick) if int(pick.get("round") or 1) == 1 and pick_overall(pick) <= 14 else None,
                status="fixed_researched_2026_order",
                source_ids=list(pick.get("source_ids") or ["src_espn_2026_draft_picks"]),
                notes="Fixed researched 2026 order from canonical DraftPick ledger.",
            )
            for pick in picks
        ]
        lottery = DraftLotteryResult(
            id=stable_id("draft_lottery", year, "fixed"),
            draft_year=year,
            seed=seed,
            draw_count=0,
            pre_lottery_order=[item.original_team_id for item in order[:14]],
            lottery_draw=[],
            final_lottery_order=[item.original_team_id for item in order[:14]],
            odds_by_team={},
            source_ids=["src_espn_2026_draft_picks"],
            notes="2026 order is fixed from researched pick order; no generated lottery draw was run.",
        )
        return {"year": year, "seed": seed, "lottery": to_plain(lottery), "pick_count": len(order), "draft_order": to_plain(order)}

    if year == "2026" and standings is not None:
        teams_by_strength = projected_standings_order(canonical, seed, standings, config)
        lottery_count = int(config["lottery"].get("team_count", 14))
        lottery_candidates = teams_by_strength[:lottery_count]
        playoff_order = teams_by_strength[lottery_count:]
        drawn = draw_lottery_teams(lottery_candidates, seed, year, config)
        drawn_ids = {team["id"] for team in drawn}
        final_lottery = drawn + [team for team in lottery_candidates if team["id"] not in drawn_ids]
        first_round_original_order = final_lottery + playoff_order
        second_round_original_order = teams_by_strength
        pre_rank = {team["id"]: index for index, team in enumerate(lottery_candidates, start=1)}
        odds = lottery_odds_by_team(lottery_candidates, config)
        canonical_picks = list(canonical.get("draft_picks", []))

        def existing_pick(round_no: int, original_team_id: str, overall: int) -> dict[str, Any]:
            match = next(
                (
                    pick for pick in canonical_picks
                    if pick.get("season") == "2026"
                    and int(pick.get("round") or 1) == round_no
                    and (pick.get("original_team_id") or pick.get("team_id")) == original_team_id
                ),
                None,
            )
            if match:
                return match
            owner = team_by_id(canonical, original_team_id)
            return {
                "id": stable_id("pick", "2026", round_no, overall, owner["abbrev"].lower()),
                "season": "2026",
                "round": round_no,
                "overall_pick": overall,
                "original_team_id": original_team_id,
                "current_owner_team_id": original_team_id,
                "source_ids": ["src_draft_model_config_v1"],
            }

        order: list[DraftOrderPick] = []
        for round_no, team_order in [(1, first_round_original_order), (2, second_round_original_order)]:
            for slot, original_team in enumerate(team_order, start=1):
                overall = slot if round_no == 1 else 30 + slot
                pick = existing_pick(round_no, original_team["id"], overall)
                order.append(
                    DraftOrderPick(
                        id=pick["id"],
                        draft_year="2026",
                        round=round_no,
                        overall_pick=overall,
                        original_team_id=original_team["id"],
                        current_owner_team_id=pick.get("current_owner_team_id") or original_team["id"],
                        pre_lottery_rank=pre_rank.get(original_team["id"]) if round_no == 1 else None,
                        lottery_slot=slot if round_no == 1 and slot <= lottery_count else None,
                        status="save_standings_2026_order",
                        source_ids=list(pick.get("source_ids") or ["src_draft_model_config_v1"]),
                        notes="2026 save-state draft order generated from simulated standings and lottery odds while preserving pick ownership.",
                    )
                )
        lottery = DraftLotteryResult(
            id=stable_id("draft_lottery", year, seed, "save"),
            draft_year=year,
            seed=seed,
            draw_count=len(drawn),
            pre_lottery_order=[team["id"] for team in lottery_candidates],
            lottery_draw=[team["id"] for team in drawn],
            final_lottery_order=[team["id"] for team in final_lottery],
            odds_by_team=odds,
            source_ids=["src_draft_model_config_v1"],
            notes="Save-state 2026 lottery generated from this save's standings, not fixed preseason research order.",
        )
        return {"year": year, "seed": seed, "lottery": to_plain(lottery), "pick_count": len(order), "draft_order": to_plain(order)}

    teams_by_strength = projected_standings_order(canonical, seed, standings, config)
    lottery_count = int(config["lottery"].get("team_count", 14))
    lottery_candidates = teams_by_strength[:lottery_count]
    playoff_order = teams_by_strength[lottery_count:]
    drawn = draw_lottery_teams(lottery_candidates, seed, year, config)
    drawn_ids = {team["id"] for team in drawn}
    final_lottery = drawn + [team for team in lottery_candidates if team["id"] not in drawn_ids]
    first_round_original_order = final_lottery + playoff_order
    second_round_original_order = teams_by_strength
    pre_rank = {team["id"]: index for index, team in enumerate(lottery_candidates, start=1)}
    odds = lottery_odds_by_team(lottery_candidates, config)
    order: list[DraftOrderPick] = []
    canonical_picks = list(canonical.get("draft_picks", []))
    for round_no, team_order in [(1, first_round_original_order), (2, second_round_original_order)]:
        for slot, original_team in enumerate(team_order, start=1):
            overall = slot if round_no == 1 else 30 + slot
            existing_candidates = [
                pick
                for pick in canonical_picks
                if str(pick.get("season")) == str(year)
                and int(pick.get("round") or 0) == round_no
                and (pick.get("original_team_id") or pick.get("team_id")) == original_team["id"]
                and pick.get("current_owner_team_id")
            ]
            existing_pick = sorted(existing_candidates, key=lambda item: (item.get("status") == "research_pending", item.get("id", "")))[0] if existing_candidates else None
            if (existing_pick or {}).get("status") == "forfeited":
                continue
            owner_team_id = (existing_pick or {}).get("current_owner_team_id") or owner_for_generated_pick(canonical, year, round_no, original_team["id"])
            owner = team_by_id(canonical, owner_team_id)
            order.append(
                DraftOrderPick(
                    id=(existing_pick or {}).get("id") or stable_id("pick", year, round_no, overall, owner["abbrev"].lower()),
                    draft_year=year,
                    round=round_no,
                    overall_pick=overall,
                    original_team_id=original_team["id"],
                    current_owner_team_id=owner_team_id,
                    pre_lottery_rank=pre_rank.get(original_team["id"]) if round_no == 1 else None,
                    lottery_slot=slot if round_no == 1 and slot <= lottery_count else None,
                    status="generated_save_state_order",
                    source_ids=["src_draft_model_config_v1"],
                    notes="Generated future draft order from projected standings, lottery odds, and current pick-owner ledger where available.",
                )
            )
    lottery = DraftLotteryResult(
        id=stable_id("draft_lottery", year, seed),
        draft_year=year,
        seed=seed,
        draw_count=len(drawn),
        pre_lottery_order=[team["id"] for team in lottery_candidates],
        lottery_draw=[team["id"] for team in drawn],
        final_lottery_order=[team["id"] for team in final_lottery],
        odds_by_team=odds,
        source_ids=["src_draft_model_config_v1"],
        notes="Generated NBA-style lottery scaffold: top picks are weighted draws, then remaining lottery teams stay in projected standings order.",
    )
    return {"year": year, "seed": seed, "lottery": to_plain(lottery), "pick_count": len(order), "draft_order": to_plain(order)}


def draft_board_report(canonical: dict[str, Any] | Any, team_query: str, year: str = "2026", limit: int | None = None,
                       config: dict[str, Any] | None = None, month: int | None = None) -> dict[str, Any]:
    """A team's scouts' board for a class: talent order (draft_scouting), with the league consensus beside it and
    the GM's "fit for us" kept separate. Built the same way for every class, in the month the canonical is in."""
    canonical = with_draft_context(canonical, config)
    year = str(year)
    team = resolve_team(canonical, team_query)
    scouting = draft_scouting.class_scouting(canonical, year, month)
    order = scouting["boards"].get(team["id"]) or []
    previous = draft_scouting.previous_month_ranks(canonical, year, team["id"], scouting["month"]) if not scouting["ahead"] else {}
    gm = {row["prospect_id"]: row for row in gm_rows(canonical, scouting, team["id"], GM_NEUTRAL_PICK, order)}
    entries = []
    for pid in order[: limit or len(order)]:
        entries.append(scouting_board_entry(canonical, scouting, team["id"], pid, gm.get(pid), previous.get(pid)))
    return {"team": team, "year": year, "month": scouting["month"], "month_label": scouting["month_label"],
            "entry_count": len(entries), "entries": entries}


def evaluate_draft_pick(canonical: dict[str, Any] | Any, team_query: str, pick_id: str, prospect_query: str, seed: int = 1, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_draft_context(canonical, config)
    team = resolve_team(canonical, team_query)
    pick = pick_by_id(canonical, pick_id)
    if not pick:
        raise ValueError(f"No pick found with id {pick_id!r}")
    prospect = resolve_prospect(canonical, prospect_query, str(pick.get("season") or "2026"))
    decision = draft_pick_decision(canonical, team, pick, prospect, seed=seed, config=config)
    return {"team": team, "pick": pick, "prospect": prospect, "decision": to_plain(decision)}


def project_rookie_contract(canonical: dict[str, Any] | Any, team_query: str, pick_id: str, prospect_query: str, signed: bool = False, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_draft_context(canonical, config)
    config = config or default_draft_model_config()
    team = resolve_team(canonical, team_query)
    pick = pick_by_id(canonical, pick_id)
    if not pick:
        raise ValueError(f"No pick found with id {pick_id!r}")
    prospect = resolve_prospect(canonical, prospect_query, str(pick.get("season") or "2026"))
    selection = {
        "id": stable_id("draft_selection", pick["id"], prospect["id"], "projection"),
        "pick_id": pick["id"],
        "team_id": team["id"],
        "prospect_id": prospect["id"],
        "draft_year": str(pick.get("season") or "2026"),
        "overall_pick": pick_overall(pick),
    }
    contract = rookie_contract_projection(selection, prospect, team, pick, config, signed=signed)
    rights = draft_rights_record(selection, prospect, team)
    onboarding = rookie_onboarding_record(selection, prospect, team, contract, signed=signed)
    return {"team": team, "pick": pick, "prospect": prospect, "draft_rights": to_plain(rights), "rookie_contract": to_plain(contract), "incoming_rookie": onboarding}


def pick_recommendations(
    canonical: dict[str, Any] | Any,
    team_query: str,
    pick_id: str,
    limit: int = 5,
    seed: int = 1,
    config: dict[str, Any] | None = None,
    unavailable_prospect_ids: set[str] | None = None,
) -> dict[str, Any]:
    """The prospects this team would take with this pick, best first: its GM's order over its scouts' final board
    (the same choice simulate_draft makes). No draw: seed is kept for callers only."""
    canonical = with_draft_context(canonical, config)
    team = resolve_team(canonical, team_query)
    pick = pick_by_id(canonical, pick_id)
    if not pick:
        raise ValueError(f"No pick found with id {pick_id!r}")
    year = str(pick.get("season") or "2026")
    scouting = draft_scouting.class_scouting(canonical, year, draft_scouting.DRAFT_MONTH)
    unavailable = unavailable_prospect_ids or set()
    candidates = [pid for pid in scouting["boards"].get(team["id"]) or [] if pid not in unavailable]
    rows = gm_rows(canonical, scouting, team["id"], pick_overall(pick), candidates)
    recommendations = []
    for row in rows[:limit]:
        entry = scouting_board_entry(canonical, scouting, team["id"], row["prospect_id"], row)
        decision = gm_decision(canonical, scouting, team, pick, row, rows, seed)
        recommendations.append({"entry": entry, "decision": to_plain(decision)})
    return {"team": team, "pick": pick, "recommendation_count": len(recommendations), "recommendations": recommendations}


def find_draft_trade(canonical: dict[str, Any] | Any, team_query: str, pick_id: str, limit: int = 5, seed: int = 1, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_draft_context(canonical, config)
    seller = resolve_team(canonical, team_query)
    pick = pick_by_id(canonical, pick_id)
    if not pick:
        raise ValueError(f"No pick found with id {pick_id!r}")
    if pick.get("current_owner_team_id") != seller["id"]:
        raise ValueError(f"{seller['abbrev']} does not own {pick_id}.")
    candidates: list[DraftTradeCandidate] = []
    decision_candidates: dict[str, dict[str, Any]] = {}
    top_targets = pick_recommendations(canonical, seller["abbrev"], pick_id, limit=6, seed=seed, config=config)["recommendations"]
    seller_top_grade = top_targets[0]["entry"]["risk_adjusted_grade"] if top_targets else 0.0
    for buyer in canonical["teams"]:
        if buyer["id"] == seller["id"]:
            continue
        buyer_entries = draft_board_report(canonical, buyer["abbrev"], str(pick.get("season") or "2026"), limit=4)["entries"]
        if not buyer_entries:
            continue
        target = buyer_entries[0]["prospect"]
        target_id = target.get("id") or target.get("prospect_id")
        buyer_pick = best_lower_pick_for_trade(canonical, buyer["id"], pick)
        if not buyer_pick:
            continue
        from_assets = [{"kind": "pick", "value": pick["id"]}]
        to_assets = [{"kind": "pick", "value": buyer_pick["id"]}]
        sweetener = draft_trade_sweetener(canonical, buyer["id"], seller_top_grade, buyer_entries[0]["risk_adjusted_grade"])
        if sweetener:
            to_assets.append(sweetener)
        try:
            report = evaluate_trade_decision(canonical, seller["abbrev"], buyer["abbrev"], from_assets, to_assets, seed=seed)
        except ValueError:
            continue
        compact = candidate_from_decision(report)
        score = draft_trade_score(report, buyer_entries[0], seller_top_grade)
        candidate = DraftTradeCandidate(
            id=stable_id("draft_trade", pick["id"], buyer["id"], target_id, seed),
            pick_id=pick["id"],
            from_team_id=seller["id"],
            to_team_id=buyer["id"],
            target_prospect_id=target_id,
            trade_type="trade_down_or_trade_up",
            proposal=compact["proposal"],
            evaluation=compact,
            score=round(score, 3),
            reasons=draft_trade_reasons(report, buyer_entries[0], seller_top_grade),
            source_ids=["src_draft_model_config_v1", "src_transaction_model_config_v1"],
            notes="Draft-night trade candidate using existing trade legality/evaluation plus prospect board urgency.",
        )
        candidates.append(candidate)
        decision_candidates[candidate.id] = compact
    candidates = sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]
    candidates = [replace(candidate, proposal=prepared['proposal'], evaluation=prepared)
                  for candidate in candidates
                  for prepared in [prepare_ai_trade_candidate(canonical, decision_candidates[candidate.id], seed=seed,
                      date=(candidate.proposal or {}).get('date'))]]
    return {"team": seller, "pick": pick, "candidate_count": len(candidates), "candidates": to_plain(candidates)}


def simulate_draft(canonical: dict[str, Any] | Any, year: str = "2026", seed: int = 1, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """One AI drafting path for every class. Each team's scouts hold their final (June) board; at each pick the
    owner's GM takes the best prospect left for his team (draft.gm_rows). Nothing is drawn at pick time: the
    seed only sets the lottery and order for classes without a fixed order."""
    canonical = with_draft_context(canonical, config)
    config = config or default_draft_model_config()
    year = str(year)
    stored_years = {str(item.get("season")) for item in canonical.get("draft_classes", []) if item.get("season")}
    order_payload = None
    generated = None
    if year in stored_years:
        prospects_list = [p for p in canonical["draft_prospects"] if str(p.get("draft_year")) == year]
        traits = [trait for trait in canonical.get("draft_prospect_traits", []) if trait.get("prospect_id") in {p["id"] for p in prospects_list}]
        ledger_picks = [pick for pick in canonical["draft_picks"] if str(pick.get("season")) == year and pick.get("current_owner_team_id")]
        explicit_slots = {int(pick["overall_pick"]) for pick in ledger_picks if pick.get("overall_pick") is not None}
        if len(ledger_picks) == 60 and explicit_slots == set(range(1, 61)):
            picks = sorted(ledger_picks, key=pick_overall)
        else:
            # A pre-lottery ownership ledger identifies which franchise controls each originating pick, but it does
            # not identify pick slots. Pair the class with a real 60-slot order before making selections.
            order_payload = generate_draft_order(canonical, year, seed=seed, config=config)
            picks = order_payload["draft_order"]
    else:
        if (canonical.get("meta") or {}).get("draft_class_seed") is None:
            canonical = {**canonical, "meta": {**(canonical.get("meta") or {}), "draft_class_seed": int(seed)}}
        generated = generated_class_for_context(canonical, year, seed, config)
        prospects_list = [to_plain(prospect) for prospect in generated["draft_prospects"]]
        traits = to_plain(generated["draft_prospect_traits"])
        order_payload = generate_draft_order(canonical, year, seed=seed, config=config)
        picks = order_payload["draft_order"]
    prospects = {p["id"]: p for p in prospects_list}
    scouting = draft_scouting.class_scouting(canonical, year, draft_scouting.DRAFT_MONTH)
    available = [pid for pid in sorted(prospects, key=lambda pid: scouting["consensus"].get(pid, {}).get("rank", 999))]
    selections: list[DraftSelection] = []
    decisions: list[DraftPickDecision] = []
    for pick in picks:
        if not available:
            break
        team = team_by_id(canonical, pick["current_owner_team_id"])
        rows = gm_rows(canonical, scouting, team["id"], pick_overall(pick), available)
        if not rows:
            continue
        decision = gm_decision(canonical, scouting, team, pick, rows[0], rows, seed)
        prospect = prospects[rows[0]["prospect_id"]]
        selection = DraftSelection(
            id=stable_id("draft_selection", pick["id"], prospect["id"], seed),
            pick_id=pick["id"],
            team_id=team["id"],
            prospect_id=prospect["id"],
            draft_year=year,
            overall_pick=pick_overall(pick),
            status="selected",
            decision_id=decision.id,
            source_ids=["src_draft_model_config_v1"],
            notes="Simulated draft selection: the GM's best fit on its scouts' final board. Draft-night trades are separate.",
        )
        selections.append(selection)
        decisions.append(decision)
        available.remove(prospect["id"])
    selection_payload = to_plain(selections)
    order_rows = order_payload["draft_order"] if order_payload else picks
    rookie_payload = draft_onboarding_records(canonical, selection_payload, prospects_list, order_rows, config)
    result = {
        "year": year,
        "seed": seed,
        **(to_plain(generated) if generated else {}),
        "draft_prospects": prospects_list,
        "draft_prospect_traits": traits,
        "selection_count": len(selections),
        "selections": selection_payload,
        "decisions": to_plain(decisions),
        "pending_draft_selections": pending_draft_selection_records(selection_payload, to_plain(decisions), prospects_list, order_rows),
        **rookie_payload,
    }
    if order_payload:
        result["draft_order"] = order_payload["draft_order"]
        result["lottery"] = order_payload["lottery"]
    if generated:
        result["notes"] = "Generated future draft with lottery/order scaffold, selections, rookie rights, and rookie contract projections."
    return result


def preferred_prospect_for_pick(canonical: dict[str, Any], year: str, team_id: str, overall_pick: int,
                                candidates: list[dict[str, Any]], seed: int, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The prospect this team would take at this slot from the given candidates: the same GM choice as
    simulate_draft. Used when a pick changes hands mid-draft, when an AI pick comes up after the user's pick, and
    as the target of a draft-night trade-up."""
    if not candidates:
        return None
    canonical = with_draft_context(canonical, config)
    plain = [c if isinstance(c, dict) else to_plain(c) for c in candidates]
    scouting = draft_scouting.class_scouting(canonical, str(year), draft_scouting.DRAFT_MONTH)
    by_id = {c["id"]: c for c in plain}
    rows = gm_rows(canonical, scouting, team_id, int(overall_pick), [pid for pid in by_id if pid in scouting["prospects"]])
    return by_id.get(rows[0]["prospect_id"]) if rows else None


def load_draft_application_save(save_path: str | Path) -> dict[str, Any]:
    """Include archived consumption logs without hydrating unrelated history."""
    from .history_store import load_history_records, record_id
    from .save import load_save

    save = load_save(save_path)
    archived = load_history_records(save_path, save, "transaction_logs", _validated=True)
    if archived:
        hot = save.get("transaction_logs") or []
        hot_ids = {record_id("transaction_logs", row) for row in hot}
        save["transaction_logs"] = [row for row in archived if record_id("transaction_logs", row) not in hot_ids] + hot
    return save


def draft_selection_rejection(save: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any] | None:
    """Check consumption records, independently of a pending selection's id.

    Live queues contain future selections too; only their applied prefix (or
    explicitly applied ids) is evidence of consumption. Prospect ids are scoped
    by year so an older class cannot block a legitimate later draft.
    """
    payload = selection.get("selection") or selection
    year = str(payload.get("draft_year") or "")
    pick_id = payload.get("pick_id")
    prospect_id = payload.get("prospect_id")
    issues = []
    if not year.isdigit() or not pick_id or not prospect_id:
        issues.append("Draft year, pick id, and prospect id are required.")
    for key, identity in (("pick", pick_id), ("prospect", prospect_id)):
        nested_id = (selection.get(key) or {}).get("id")
        if nested_id and nested_id != identity:
            issues.append(f"The {key} identity does not match the selection.")
    state = save.get("draft_state") or {}
    pick_used = (save.get("draft_pick_overrides") or {}).get(pick_id) == "used_draft_pick"
    pick_used = pick_used or pick_id in (state.get("used_pick_ids") or [])
    prospect_used = False
    records = [row for key in ("draft_rights", "rookie_contracts", "incoming_rookies") for row in save.get(key, [])]
    records += [row.get("assets") or {} for row in save.get("transaction_logs", [])
                if row.get("transaction_type") == "draft_selection"
                and row.get("status") == "applied_to_save_ledger"]
    queue = (state.get("draft") or {}).get("pending_draft_selections") or []
    applied_ids = set(state.get("applied_selection_ids") or [])
    records += [(row.get("selection") or row) for index, row in enumerate(queue)
                if index < int(state.get("current_index") or 0)
                or row.get("id") in applied_ids or (row.get("selection") or {}).get("id") in applied_ids]
    records += [row.get("selection") or row for row in state.get("selections") or []]
    # Older/bulk onboarding records lack pick ids. Join their recorded slot to
    # the saved draft order rather than treating the future queue as consumed.
    order = ((save.get("draft_orders") or {}).get(year) or {}).get("draft_order") or []
    slots = {str(row.get("overall_pick")) for row in order if (row.get("pick_id") or row.get("id")) == pick_id}
    for row in records:
        record_year = str(row.get("draft_year") or "")
        if record_year and record_year != year:
            continue
        prospect_used = prospect_used or row.get("prospect_id") == prospect_id
        pick_used = pick_used or row.get("pick_id") == pick_id
        if record_year == year and row.get("overall_pick") is not None:
            pick_used = pick_used or str(row["overall_pick"]) in slots
    # Automated offseason processing records the completed year even when it
    # did not retain a live queue or individual pick overrides.
    pick_used = pick_used or str(state.get("completed_year") or "") == year
    if pick_used:
        issues.append("This draft pick has already been consumed.")
    if prospect_used:
        issues.append("This prospect has already been selected in this draft year.")
    if issues:
        return {"status": "not_applied", "selection_id": payload.get("id"), "issues": issues}
    return None


def apply_draft_selection_to_save_state(
    save: dict[str, Any],
    selection_id: str,
    date: str = CANONICAL_START_DATE,
    sign_rookie: bool = False,
) -> dict[str, Any]:
    """Apply one pending selection to an already-loaded save.

    Draft-night simulation calls this state-level boundary so a pick can update
    rookie records, the live draft queue, and the transaction ledger before one
    durable save write. The file wrapper below remains the compatibility API for
    standalone ledger callers.
    """
    selection = next((item for item in save.get("pending_draft_selections", []) if item.get("id") == selection_id or item.get("selection", {}).get("id") == selection_id), None)
    if not selection:
        return {"status": "not_found", "selection_id": selection_id, "notes": "No pending draft selection with this id exists in the save ledger."}
    rejection = draft_selection_rejection(save, selection)
    if rejection:
        return rejection
    payload = selection.get("selection") or selection
    prospect_payload = selection.get("prospect") or {"id": payload.get("prospect_id"), "name": payload.get("prospect_name") or payload.get("prospect_id")}
    pick_payload = selection.get("pick") or {"id": payload.get("pick_id"), "round": 1 if int(payload.get("overall_pick") or 60) <= 30 else 2}
    team_payload = selection.get("team") or {"id": payload.get("team_id"), "abbrev": str(payload.get("team_id") or "").replace("team_", "").upper()}
    rights = draft_rights_record(payload, prospect_payload, team_payload)
    contract = rookie_contract_projection(payload, prospect_payload, team_payload, pick_payload, default_draft_model_config(), signed=sign_rookie)
    onboarding = rookie_onboarding_record(payload, prospect_payload, team_payload, contract, signed=sign_rookie)
    log = TransactionLog(
        id=stable_id("transaction_log", "draft_selection", selection_id, date),
        date=date,
        transaction_type="draft_selection",
        proposal_id=selection_id,
        status="applied_to_save_ledger",
        teams=[payload.get("team_id")],
        assets={
            "pick_id": payload.get("pick_id"),
            "prospect_id": payload.get("prospect_id"),
            "draft_year": payload.get("draft_year"),
            "draft_rights_id": rights.id,
            "rookie_contract_id": contract.id,
            "rookie_signed": sign_rookie,
        },
        evaluations=[selection.get("decision")] if selection.get("decision") else [],
        source_ids=["src_draft_model_config_v1"],
        notes="Draft selection, rookie rights, rookie contract projection, and incoming-rookie onboarding applied to save ledger only. Canonical preseason data remains immutable.",
    )
    upsert_save_record(save, "draft_rights", to_plain(rights))
    upsert_save_record(save, "rookie_contracts", to_plain(contract))
    if save.get("version") == "league_save_v1":
        if sign_rookie:
            rookie_player = rookie_player_record(onboarding, prospect_payload, team_payload, contract)
            upsert_save_record(save, "generated_players", rookie_player)
            for trait in rookie_trait_records(rookie_player, prospect_payload, draft_traits_for_prospect(save, prospect_payload.get("id"))):
                upsert_save_record(save, "generated_traits", trait)
            save.setdefault("roster_overrides", {})[rookie_player["id"]] = team_payload.get("id")
            save.setdefault("contract_overrides", {})[rookie_player["id"]] = {
                "team_id": team_payload.get("id"),
                "seasons": contract.seasons,
                "status": "signed_rookie_contract",
                "original_contract_years": len(contract.seasons),
                "signed_season": contract.seasons[0].get("season") if contract.seasons else None,
            }
            onboarding["player_id"] = rookie_player["id"]
            onboarding["roster_status"] = "signed_rookie"
            onboarding["rights_status"] = "signed_rookie_contract"
            save.setdefault("rotation_baselines", {})[rookie_player["id"]] = float(rookie_player.get("minutes_projection") or 0.0)
        if payload.get("pick_id"):
            save.setdefault("draft_pick_overrides", {})[payload["pick_id"]] = "used_draft_pick"
            draft_state = save.setdefault("draft_state", {})
            used_pick_ids = set(draft_state.get("used_pick_ids") or [])
            used_pick_ids.add(payload["pick_id"])
            draft_state["used_pick_ids"] = sorted(used_pick_ids)
        if draft_selection_newsworthy(payload, prospect_payload, selection):
            append_unique_news(save, "draft_selection", f"{team_payload.get('abbrev', 'TEAM')} selects {onboarding.get('name', payload.get('prospect_id'))} at #{payload.get('overall_pick')}.", date)
    upsert_save_record(save, "incoming_rookies", onboarding)
    save.setdefault("transaction_logs", []).append(to_plain(log))
    save["pending_draft_selections"] = [item for item in save.get("pending_draft_selections", []) if item is not selection]
    return {
        "status": "applied",
        "draft_rights": to_plain(rights),
        "rookie_contract": to_plain(contract),
        "incoming_rookie": onboarding,
        "transaction_log": to_plain(log),
    }


def apply_draft_selection_to_save(save_path: str | Path, selection_id: str, date: str = CANONICAL_START_DATE, sign_rookie: bool = False) -> dict[str, Any]:
    path = Path(save_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            save = json.load(handle)
        if save.get("version") == "league_save_v1":
            save = load_draft_application_save(path)
    else:
        save = {"version": "save_transaction_ledger_v1", "pending_draft_selections": [], "transaction_logs": []}
    result = apply_draft_selection_to_save_state(save, selection_id, date=date, sign_rookie=sign_rookie)
    if result.get("status") == "applied":
        # Local import avoids coupling the draft model to save construction while
        # keeping one consistent, deduplicating persistence boundary.
        from .save import write_save

        write_save(path, save)
    result["save"] = str(path)
    return result


def prospect_priority_tier(prospect: dict[str, Any]) -> int:
    """Consensus tier from the public board rank (1: top 3, 2: top 6). Ranks are public grades for every class
    (apply_public_ranks), so this works for generated classes too - it used to name three 2026 prospects."""
    rank = int(prospect.get("rank") or 99)
    return 1 if rank <= 3 else 2 if rank <= 6 else 3


def draft_onboarding_records(canonical: dict[str, Any], selections: list[dict[str, Any]], prospects: list[dict[str, Any]], picks: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    prospects_by_id = {prospect["id"]: prospect for prospect in prospects}
    picks_by_id = {pick["id"]: pick for pick in picks}
    rights: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    rookies: list[dict[str, Any]] = []
    for selection in selections:
        prospect = prospects_by_id.get(selection["prospect_id"], {"id": selection["prospect_id"], "name": selection["prospect_id"]})
        team = team_by_id(canonical, selection["team_id"])
        pick = picks_by_id.get(selection["pick_id"], {"id": selection["pick_id"], "round": 1 if selection["overall_pick"] <= 30 else 2})
        rights_record = draft_rights_record(selection, prospect, team)
        contract = rookie_contract_projection(selection, prospect, team, pick, config, signed=False)
        rights.append(to_plain(rights_record))
        contracts.append(to_plain(contract))
        rookies.append(rookie_onboarding_record(selection, prospect, team, contract, signed=False))
    return {"draft_rights": rights, "rookie_contracts": contracts, "incoming_rookies": rookies}


def pending_draft_selection_records(selections: list[dict[str, Any]], decisions: list[dict[str, Any]], prospects: list[dict[str, Any]], picks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prospects_by_id = {prospect["id"]: prospect for prospect in prospects}
    picks_by_id = {pick["id"]: pick for pick in picks}
    decisions_by_selection = {decision.get("pick_id"): decision for decision in decisions}
    return [
        {
            "id": selection["id"],
            "selection": selection,
            "decision": decisions_by_selection.get(selection["pick_id"]),
            "prospect": prospects_by_id.get(selection["prospect_id"]),
            "pick": picks_by_id.get(selection["pick_id"]),
            "status": "pending_save_application",
            "source_ids": ["src_draft_model_config_v1"],
            "notes": "Store this object in pending_draft_selections, then apply-draft-selection can create rights, contract, and onboarding records.",
        }
        for selection in selections
    ]


def draft_rights_record(selection: dict[str, Any], prospect: dict[str, Any], team: dict[str, Any]) -> DraftRights:
    return DraftRights(
        id=stable_id("draft_rights", selection.get("draft_year"), team.get("id"), prospect.get("id")),
        selection_id=selection["id"],
        prospect_id=selection["prospect_id"],
        team_id=selection["team_id"],
        draft_year=str(selection["draft_year"]),
        rights_status="exclusive_unsigned_rights",
        roster_status="draft_rights_unsigned",
        source_ids=["src_draft_model_config_v1"],
        notes="Save-state rights record created from a draft selection. Rights can later become a signed rookie roster record or be traded/renounced.",
    )


def rookie_contract_projection(selection: dict[str, Any], prospect: dict[str, Any], team: dict[str, Any], pick: dict[str, Any], config: dict[str, Any], signed: bool = False) -> RookieContractProjection:
    rookie_config = config.get("rookie_scale", default_draft_model_config()["rookie_scale"])
    round_no = int(pick.get("round") or (1 if int(selection.get("overall_pick") or 60) <= 30 else 2))
    overall = int(selection.get("overall_pick") or (1 if round_no == 1 else 31))
    draft_year = int(selection["draft_year"])
    if round_no == 1:
        years = int(rookie_config["first_round_years"])
        year_one = max(
            float(rookie_config["first_round_floor"]),
            float(rookie_config["first_pick_year1_salary"]) * (float(rookie_config["first_round_decay"]) ** max(0, overall - 1)),
        )
        contract_type = "first_round_rookie_scale"
    else:
        years = int(rookie_config["second_round_years"])
        year_one = float(rookie_config["second_round_year1_salary"]) + max(0, 60 - overall) * float(rookie_config["second_round_pick_bonus"])
        contract_type = "second_round_minimum_framework"
    seasons = []
    for offset in range(years):
        salary = round(year_one * ((1 + float(rookie_config["annual_raise"])) ** offset))
        seasons.append(
            {
                "season": season_label(draft_year + offset),
                "salary": int(salary),
                "guaranteed": round_no == 1 and offset <= 1,
                "option_type": "team_option" if round_no == 1 and offset >= 2 else None,
            }
        )
    cap_hold = int(round(seasons[0]["salary"] * float(rookie_config["cap_hold_multiplier"])))
    return RookieContractProjection(
        id=stable_id("rookie_contract", selection["id"]),
        selection_id=selection["id"],
        prospect_id=selection["prospect_id"],
        team_id=selection["team_id"],
        draft_year=str(selection["draft_year"]),
        contract_type=contract_type,
        status="signed" if signed else "projected_unsigned_offer",
        seasons=seasons,
        cap_hold=float(cap_hold),
        total_salary=float(sum(item["salary"] for item in seasons)),
        source_ids=["src_draft_model_config_v1"],
        notes="Practical rookie-scale projection for save-state onboarding. Exact CBA scale tables are intentionally approximated in v1.",
    )


def rookie_onboarding_record(selection: dict[str, Any], prospect: dict[str, Any], team: dict[str, Any], contract: RookieContractProjection, signed: bool = False) -> dict[str, Any]:
    name = prospect.get("name") or prospect.get("id") or selection["prospect_id"]
    return {
        "id": stable_id("incoming_rookie", selection.get("draft_year"), team.get("id"), name),
        "selection_id": selection["id"],
        "prospect_id": selection["prospect_id"],
        "name": name,
        "normalized_name": normalize_name(name),
        "team_id": selection["team_id"],
        "team_abbrev": team.get("abbrev"),
        "draft_year": str(selection["draft_year"]),
        "overall_pick": selection.get("overall_pick"),
        "position": prospect.get("position"),
        "age": whole_prospect_age(prospect.get("age")),
        "height_inches": prospect.get("height_inches"),
        "weight_lbs": prospect.get("weight_lbs"),
        "archetype": prospect.get("archetype"),
        "potential": prospect.get("potential"),
        "current_ability": prospect.get("current_ability"),
        "medical_profile": prospect.get("medical_profile") or {},
        "rights_status": "signed_rookie_contract" if signed else "exclusive_unsigned_rights",
        "roster_status": "signed_rookie" if signed else "draft_rights_unsigned",
        "contract_id": contract.id,
        "source_ids": list(dict.fromkeys(["src_draft_model_config_v1", *prospect.get("source_ids", [])])),
        "notes": "Save-state rookie onboarding stub. Full player-trait conversion and roster-slot mutation can build from this record.",
    }


def rookie_rotation_projection(prospect: dict[str, Any], overall: int, *, talent_model: bool = False) -> tuple[float, str]:
    ability = float(prospect.get("current_ability") or 45.0)
    potential = float(prospect.get("potential") or 55.0)
    slot_bonus = max(0, 31 - overall) * 0.38 if overall <= 30 else max(0, 45 - overall) * 0.08
    readiness = max(0.0, ability - 43.0) * 0.48 + (0 if talent_model else max(0.0, potential - 64.0) * 0.08)
    minutes = clamp(4.0 + readiness + slot_bonus, 2.0, 29.0)
    if overall <= 5:
        minutes = max(minutes, 22.0)
    elif overall <= 10:
        minutes = max(minutes, 17.0)
    elif overall <= 20:
        minutes = max(minutes, 11.0)
    priority = "core_rotation" if overall <= 8 and ability >= 55 else "development_priority" if overall <= 20 or potential >= 72 else "rookie_depth"
    return round(minutes, 1), priority


def rookie_player_record(onboarding: dict[str, Any], prospect: dict[str, Any], team: dict[str, Any], contract: RookieContractProjection) -> dict[str, Any]:
    overall = int(onboarding.get("overall_pick") or 60)
    ability = float(prospect.get("current_ability") or 45.0)
    potential = float(prospect.get("potential") or 55.0)
    new_model = talent_modeled(prospect) or talent_modeled(onboarding)
    minutes, priority = rookie_rotation_projection(prospect, overall, talent_model=new_model)
    player = {
        "id": stable_id("rookie_player", onboarding.get("draft_year"), team.get("id"), onboarding.get("name")),
        "name": onboarding.get("name"),
        "normalized_name": normalize_name(onboarding.get("name")),
        "slug": stable_id("", onboarding.get("name")).strip("_"),
        "team_id": team.get("id"),
        "team_abbrev": team.get("abbrev"),
        "position": primary_position_label(prospect.get("position")),
        "position_detail": prospect.get("position"),
        "age": whole_prospect_age(prospect.get("age")) or 20,
        "age_base_season": f"{onboarding.get('draft_year')}-{str(int(onboarding.get('draft_year') or 2026) + 1)[-2:]}",
        "age_base_start_year": int(onboarding.get("draft_year") or 2026),
        "height_inches": prospect.get("height_inches"),
        "weight_lbs": prospect.get("weight_lbs"),
        "minutes_projection": round(minutes, 1),
        "rotation_priority": priority,
        "primary_off_role": prospect.get("archetype"),
        "primary_def_role": "Rookie",
        "source_kind": "generated_rookie",
        "source_ids": ["src_draft_model_config_v1"],
        "missing_critical_fields": [],
        "critical_field_fallbacks": {},
        "rookie_contract_id": contract.id,
        "draft_pick": overall,
        "overall_pick": overall,
        "draft_year": str(onboarding.get("draft_year") or ""),
        "current_ability": round(ability, 2),
        "potential": round(potential, 2),
        "medical_profile": prospect.get("medical_profile") or {},
        "headshot_url": prospect_headshot_url(prospect),  # the face he had as a prospect
    }
    if new_model:
        player["source_ids"].append(TALENT_SOURCE_ID)
    real = real_prospect_data.real_entry_for(prospect) or {}
    if real.get("scouting") and real_prospect_data.SCOUTING_SOURCE_ID not in player["source_ids"]:
        player["source_ids"].append(real_prospect_data.SCOUTING_SOURCE_ID)
    college = real.get("college")
    if college:
        # Real college player: his college profile informs his entry skills in the 94-input ratings
        # (input_estimator blends these estimates with the real-player neighbours generated rookies use).
        player["source_ids"].append(real_prospect_data.SOURCE_ID)
        player["college_profile"] = {
            "team": college.get("team"), "conference": college.get("conference"), "coach": college.get("coach"),
            "class_year": college.get("class_year_at_draft"), "projected_pick": college.get("projected_pick"),
            "inputs": real_prospect_data.input_targets(college, overall),
        }
    return player


def primary_position_label(position: Any) -> str:
    text = str(position or "").upper().replace("POSITION_", "")
    for separator in ["/", ",", "-", " "]:
        if separator in text:
            text = text.split(separator)[0]
            break
    text = text.strip()
    return text if text in {"PG", "SG", "SF", "PF", "C"} else str(position or "G")[:2].upper()


def draft_traits_for_prospect(save: dict[str, Any], prospect_id: str | None) -> list[dict[str, Any]]:
    if not prospect_id:
        return []
    draft_state_traits = (((save.get("draft_state") or {}).get("draft") or {}).get("draft_prospect_traits") or [])
    traits = [trait for trait in draft_state_traits if trait.get("prospect_id") == prospect_id]
    if traits:
        return traits
    return [
        trait
        for item in save.get("pending_draft_selections", [])
        for trait in (item.get("draft_prospect_traits") or item.get("prospect_traits") or [])
        if trait.get("prospect_id") == prospect_id
    ]


def rookie_trait_records(player: dict[str, Any], prospect: dict[str, Any], draft_traits: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    prospect_values = {
        trait.get("trait_key"): float(trait.get("value") if trait.get("value") is not None else 50.0)
        for trait in (draft_traits or [])
        if trait.get("trait_key")
    }
    if not prospect_values:
        prospect_values = infer_trait_values(
            str(prospect.get("position") or player.get("position") or ""),
            str(prospect.get("archetype") or player.get("primary_off_role") or "connector_guard"),
            prospect.get("public_stats") or {},
            maybe_float(prospect.get("height_inches") or player.get("height_inches")),
        )
    current = maybe_float(prospect.get("current_ability")) or 50.0
    potential = maybe_float(prospect.get("potential")) or current
    archetype = str(prospect.get("archetype") or player.get("primary_off_role") or "")
    new_model = talent_modeled(player) or talent_modeled(prospect)
    values = nba_trait_values_from_prospect(prospect_values, current, potential, str(player.get("position") or ""), archetype, talent_model=new_model)
    return [
        {
            "id": stable_id("generated_trait", player["id"], trait_key),
            "player_id": player["id"],
            "trait_key": trait_key,
            "label": NBA_TRAIT_LABELS[trait_key],
            "value": round(clamp(value, 5 if new_model else 25, 95), 2),
            "confidence": 0.48,
            "source_kind": "draft_model_conversion",
            "source_ids": ["src_draft_model_config_v1", *([TALENT_SOURCE_ID] if new_model else [])],
            "last_verified": CANONICAL_START_DATE,
            "notes": "Converted from draft prospect trait model when rookie was signed into save state.",
            "components": {
                "prospect_current_ability": round(current, 2),
                "prospect_potential": round(potential, 2),
                "prospect_archetype": archetype,
                **({"career_capacity": career_trait_profile(
                    clamp(value, 5, 95), current, potential,
                    .55 + (value - (current + 5)) / 35
                    + (prospect_values.get("motor", 50) + prospect_values.get("feel", 50) - 100) / 200,
                )} if new_model else {}),
            },
        }
        for trait_key, value in sorted(values.items())
    ]


def nba_trait_values_from_prospect(values: dict[str, float], current: float, potential: float, position: str, archetype: str, *, talent_model: bool = False) -> dict[str, float]:
    def v(key: str, default: float = 50.0) -> float:
        return float(values.get(key, default))

    def blend(items: list[tuple[float, float]]) -> float:
        total = sum(weight for _, weight in items) or 1.0
        return sum(value * weight for value, weight in items) / total

    pos = position.upper()
    guard = "PG" in pos or "SG" in pos
    big = "PF" in pos or "C" in pos
    ability_anchor = current + 5 if talent_model else current * 0.55 + potential * 0.22 + 11.5
    shooting = v("shooting")
    creation = v("shot_creation")
    pressure = v("rim_pressure")
    passing = v("passing")
    defense = v("defense")
    rim_protection = v("rim_protection")
    rebounding = v("rebounding")
    feel = v("feel")
    athleticism = v("athleticism")
    size = v("size")
    motor = v("motor")
    readiness = v("nba_readiness")
    output = {
        "release_speed": blend([(shooting, 0.76), (readiness, 0.14), (motor, 0.10)]),
        "shooting_range": blend([(shooting, 0.84), (creation, 0.08), (feel, 0.08)]),
        "shot_versatility": blend([(creation, 0.58), (shooting, 0.22), (feel, 0.12), (ability_anchor, 0.08)]),
        "rim_pressure": blend([(pressure, 0.68), (athleticism, 0.20), (size, 0.12 if big else 0.04)]),
        "handle_pressure": blend([(creation, 0.48), (passing, 0.22), (athleticism, 0.20), (feel, 0.10)]) + (3.0 if guard else -2.0 if big else 0.0),
        "passing_reads": blend([(passing, 0.66), (feel, 0.25), (readiness, 0.09)]),
        "offensive_rebounding": blend([(rebounding, 0.70), (size, 0.18), (motor, 0.12)]),
        "defensive_effort": blend([(defense, 0.50), (motor, 0.30), (athleticism, 0.12), (readiness, 0.08)]),
        "foot_speed_lateral_agility": blend([(athleticism, 0.62), (defense, 0.22), (motor, 0.16)]) - (4.0 if "C" in pos else 0.0),
        "screen_navigation": blend([(defense, 0.42), (athleticism, 0.30), (feel, 0.18), (motor, 0.10)]),
        "rim_deterrence": blend([(rim_protection, 0.64), (size, 0.22), (defense, 0.10), (athleticism, 0.04)]),
        "scheme_iq": blend([(feel, 0.52), (defense, 0.24), (readiness, 0.16), (passing, 0.08)]),
        "stamina_cardio": blend([(motor, 0.48), (readiness, 0.30), (athleticism, 0.22)]),
        "portability": blend([(shooting, 0.24), (defense, 0.22), (feel, 0.20), (readiness, 0.14), (athleticism, 0.10), (size, 0.10)]),
        "playoff_translation": blend([(ability_anchor, 0.30), (potential, 0.22), (feel, 0.20), (readiness, 0.16), (creation, 0.12)]),
    }
    if talent_model:
        output.update({
            "release_speed": shooting * .90 + readiness * .10,
            "shooting_range": shooting * .95 + creation * .05,
            "handle_pressure": creation * .68 + passing * .22 + athleticism * .10 + (3 if guard else -2 if big else 0),
            "screen_navigation": defense * .62 + athleticism * .18 + feel * .20,
            "rim_deterrence": rim_protection * .84 + size * .12 + defense * .04,
            "playoff_translation": current * .40 + feel * .25 + readiness * .25 + creation * .10,
        })
    if archetype in {"lead_creator", "scoring_wing"}:
        output["shot_versatility"] += 3.0
        output["handle_pressure"] += 2.0
    if archetype == "rim_protecting_big":
        output["rim_deterrence"] += 5.0
        output["offensive_rebounding"] += 2.0
    if archetype == "movement_shooter":
        output["release_speed"] += 4.0
        output["shooting_range"] += 3.0
    # Prospect subtraits are intentionally expressive, but public-stat and
    # archetype priors can otherwise make a low-readiness second-rounder look
    # like an established NBA starter. Preserve the shape of the profile while
    # anchoring its league-ready level to the scout model's current ability.
    raw_mean = sum(output.values()) / max(1, len(output))
    target_mean = clamp(float(current) + (5.0 if talent_model else 7.0), 30.0 if talent_model else 35.0, 82.0)
    anchor_shift = clamp(target_mean - raw_mean, -15.0 if talent_model else -10.0, 0.0 if talent_model else 4.0)
    output = {trait_key: value + anchor_shift for trait_key, value in output.items()}
    if talent_model:
        # NBA readiness can raise the usable parts of an elite profile without
        # turning a non-shooter into a shooter or a weak defender into a stopper.
        readiness_gain = clamp((current - 44) * .75, 0, 9)
        if "C" in pos:
            ready_skills = {"rim_pressure", "rim_deterrence", "offensive_rebounding", "defensive_effort",
                            "scheme_iq", "stamina_cardio", "portability", "passing_reads"}
        else:
            ready_skills = set(output) - {"rim_deterrence", "offensive_rebounding"}
        output = {key: value + (readiness_gain if key in ready_skills and value >= 35 else 0)
                  for key, value in output.items()}
    return output


def append_unique_news(save: dict[str, Any], kind: str, headline: str, date_value: str) -> None:
    item = {
        "id": stable_id("news", kind, date_value, headline),
        "date": date_value,
        "kind": kind,
        "headline": headline,
        "status": "unread",
    }
    if item["id"] not in {existing.get("id") for existing in save.setdefault("news_items", [])}:
        save["news_items"].append(item)


def draft_selection_newsworthy(payload: dict[str, Any], prospect_payload: dict[str, Any], selection: dict[str, Any]) -> bool:
    try:
        overall = int(payload.get("overall_pick") or 999)
    except (TypeError, ValueError):
        overall = 999
    if overall <= 10:
        return True
    public_rank = prospect_payload.get("consensus_rank") or prospect_payload.get("rank")
    try:
        rank_gap = abs(float(public_rank) - overall) if public_rank is not None else 0.0
    except (TypeError, ValueError):
        rank_gap = 0.0
    reasons = " ".join(str(item) for item in ((selection.get("decision") or {}).get("reasons") or []))
    return rank_gap >= 12 or any(token in reasons.lower() for token in ["reach", "steal", "surprise", "upside swing"])


def upsert_save_record(save: dict[str, Any], collection: str, record: dict[str, Any]) -> None:
    records = [item for item in save.get(collection, []) if item.get("id") != record.get("id")]
    records.append(record)
    save[collection] = records


def build_scouting_reports(canonical: dict[str, Any], prospects: list[DraftProspect], traits: list[DraftProspectTrait], config: dict[str, Any]) -> list[ScoutingReport]:
    traits_by_prospect: dict[str, list[DraftProspectTrait]] = {}
    for trait in traits:
        traits_by_prospect.setdefault(trait.prospect_id, []).append(trait)
    reports: list[ScoutingReport] = []
    for team in canonical.get("teams", []):
        staff = scouting_staff_score(canonical, team["id"])
        for prospect in prospects:
            rng = random.Random(f"{team['id']}:{prospect.id}:scouting")
            noise = scouting_noise(staff, prospect, config)
            estimated_current = noisy_range(prospect.current_ability, noise, rng)
            estimated_potential = noisy_range(prospect_evaluation_value(prospect, "potential"), noise * 1.15, rng)
            trait_estimates = {
                trait.trait_key: noisy_range(trait.value, noise * trait_noise_multiplier(trait.trait_key, prospect.position, staff), rng)
                for trait in traits_by_prospect.get(prospect.id, [])
            }
            grade = estimate_grade(estimated_current, estimated_potential, prospect.floor, prospect.volatility)
            reports.append(
                ScoutingReport(
                    id=stable_id("scouting_report", team["id"], prospect.id),
                    team_id=team["id"],
                    prospect_id=prospect.id,
                    scouted_grade=round(grade, 2),
                    estimated_current=estimated_current,
                    estimated_potential=estimated_potential,
                    trait_estimates=trait_estimates,
                    confidence=round(staff["confidence"], 3),
                    source_ids=["src_draft_model_config_v1", "src_gameplay_staff_seed_v1"],
                    notes=f"Scouted estimate from {team['abbrev']} scouting staff. True ratings remain internal; ranges drive board uncertainty.",
                )
            )
    return reports


def build_draft_board_entries(canonical: dict[str, Any], prospects: list[DraftProspect], reports: list[ScoutingReport], config: dict[str, Any]) -> list[DraftBoardEntry]:
    # Rebuilding a board must not inherit a trait index from a discarded
    # universe whose Python object IDs have since been reused.
    invalidate_spatial_cache(canonical)
    reports_by_key = {(report.team_id, report.prospect_id): report for report in reports}
    entries: list[DraftBoardEntry] = []
    spatial_cache: dict[Any, Any] = {}  # each team's / prospect's spatial profile once per board build
    for team in canonical.get("teams", []):
        team_entries = []
        for prospect in prospects:
            report = reports_by_key[(team["id"], prospect.id)]
            fit = prospect_team_fit(canonical, team["id"], prospect, spatial_cache)
            cap_value = prospect_cap_value(canonical, team["id"], prospect)
            bpa = report.scouted_grade
            risk_adjusted = bpa * 0.72 + fit * 0.16 + cap_value * 0.12 - prospect.volatility * 0.05
            team_entries.append((risk_adjusted, bpa, fit, cap_value, prospect, report))
        for rank, (risk_adjusted, bpa, fit, cap_value, prospect, _) in enumerate(sorted(team_entries, key=lambda item: (item[0], item[1], -item[4].rank), reverse=True), start=1):
            entries.append(
                DraftBoardEntry(
                    id=stable_id("draft_board", team["id"], prospect.id),
                    team_id=team["id"],
                    prospect_id=prospect.id,
                    draft_year=prospect.draft_year,
                    board_rank=rank,
                    bpa_grade=round(bpa, 2),
                    fit_grade=round(fit, 2),
                    need_fit=round(fit - 50, 2),
                    cap_value=round(cap_value, 2),
                    risk_adjusted_grade=round(risk_adjusted, 2),
                    source_ids=["src_draft_model_config_v1"],
                    notes="Team draft board entry. BPA dominates; need, fit, cap value, volatility, and front-office context break closer tiers.",
                )
            )
    return entries


def draft_pick_decision(canonical: dict[str, Any], team: dict[str, Any], pick: dict[str, Any], prospect: dict[str, Any], seed: int = 1,
                        config: dict[str, Any] | None = None, available: set[str] | None = None) -> DraftPickDecision:
    """Explain a pick against the prospects still available (or the whole class) with the GM's own reasoning."""
    draft_year = str(pick.get("season") or pick.get("draft_year") or "2026")
    scouting = draft_scouting.class_scouting(canonical, draft_year, draft_scouting.DRAFT_MONTH)
    pool = [pid for pid in scouting["prospects"] if available is None or pid in available or pid == prospect["id"]]
    rows = gm_rows(canonical, scouting, team["id"], pick_overall(pick), pool)
    row = next(item for item in rows if item["prospect_id"] == prospect["id"])
    return gm_decision(canonical, scouting, team, pick, row, rows, seed)


def infer_prospect_archetype(position: str, stats: dict[str, Any]) -> str:
    pos = position.upper()
    per36 = stats.get("per_36") or {}
    advanced = stats.get("advanced") or {}
    ast = float(per36.get("ast", 0))
    reb = float(per36.get("reb", 0))
    blk = float(per36.get("blk", 0))
    pts = float(per36.get("pts", 0))
    ts = float(advanced.get("tspct", 0))
    if "PG" in pos and ast >= 5:
        return "lead_creator"
    if ("SG" in pos or "PG" in pos) and pts >= 22:
        return "rim_pressure_guard"
    if ("SF" in pos or "SG" in pos) and pts >= 20:
        return "scoring_wing"
    if "SF" in pos and blk + float(per36.get("stl", 0)) >= 2.2:
        return "two_way_wing"
    if ("PF" in pos or "C" in pos) and blk >= 1.8:
        return "rim_protecting_big"
    if ("PF" in pos or "C" in pos) and reb >= 9 and ast >= 2.5:
        return "versatile_forward"
    if ("PF" in pos or "C" in pos) and ts >= 0.6:
        return "stretch_big"
    if "SG" in pos or "SF" in pos:
        return "movement_shooter"
    return "connector_guard" if "PG" in pos else "energy_big"


def infer_trait_values(position: str, archetype: str, stats: dict[str, Any], height_inches: float | None) -> dict[str, float]:
    per36 = stats.get("per_36") or {}
    advanced = stats.get("advanced") or {}
    values = {key: 50.0 for key in DRAFT_TRAITS}
    values["shot_creation"] += float(per36.get("pts", 14)) * 0.9 + float(advanced.get("usg", 20)) * 0.35 - 26
    values["shooting"] += float(advanced.get("tspct", 0.55)) * 85 - 45
    values["rim_pressure"] += float(per36.get("pts", 14)) * 0.45 + float(advanced.get("usg", 20)) * 0.2 - 13
    values["passing"] += float(per36.get("ast", 2)) * 5.2 - 6
    values["defense"] += float(per36.get("stl", 0.8)) * 5 + float(advanced.get("dbpm", 2)) * 1.4
    values["rim_protection"] += float(per36.get("blk", 0.5)) * 9
    values["rebounding"] += float(per36.get("reb", 5)) * 2.4 - 5
    values["feel"] += float(advanced.get("bpm", 5)) * 1.6
    values["size"] += max(0.0, (float(height_inches or 78) - 76) * 1.8)
    archetype_bias = {
        "lead_creator": {"shot_creation": 10, "passing": 10},
        "scoring_wing": {"shot_creation": 9, "shooting": 5},
        "two_way_wing": {"defense": 10, "shooting": 4},
        "connector_guard": {"passing": 7, "feel": 7},
        "movement_shooter": {"shooting": 11, "motor": 5},
        "rim_pressure_guard": {"rim_pressure": 10, "shot_creation": 5},
        "versatile_forward": {"rebounding": 6, "passing": 5, "size": 5},
        "stretch_big": {"shooting": 8, "size": 7},
        "rim_protecting_big": {"rim_protection": 14, "size": 7},
        "energy_big": {"rebounding": 9, "motor": 8},
    }.get(archetype, {})
    athletic_bias = {
        "lead_creator": 4.0,
        "scoring_wing": 4.5,
        "two_way_wing": 5.0,
        "connector_guard": 1.5,
        "movement_shooter": 1.0,
        "rim_pressure_guard": 8.0,
        "versatile_forward": 4.0,
        "stretch_big": 1.5,
        "rim_protecting_big": 3.0,
        "energy_big": 6.0,
    }.get(archetype, 0.0)
    for key, bonus in archetype_bias.items():
        values[key] += bonus
    values["athleticism"] = (
        38.0
        + values["rim_pressure"] * 0.22
        + values["defense"] * 0.10
        + values["size"] * 0.08
        + athletic_bias
        + max(0.0, float(advanced.get("usg", 20)) - 22.0) * 0.18
    )
    values["motor"] += float(per36.get("reb", 5)) * 0.7 + float(per36.get("stl", 0.8)) * 2.5
    values["nba_readiness"] += float(advanced.get("bpm", 5)) * 1.1 + float(advanced.get("tspct", 0.55)) * 22 - 12
    return {key: clamp(value, 25, 95) for key, value in values.items()}


def generated_prospect_upside(potential: float, rank: int, top_strength: float, year: str, seed: int,
                             talent_model: bool = False) -> float:
    """A class-sensitive upper tail, not a guaranteed star or draft-slot bonus."""
    quality = clamp((top_strength - 53.0) / 21.0, 0.0, 1.0)
    # Consensus rank predicts upside but must not almost eliminate the hidden
    # tail. This is latent opportunity, still subject to skill holes and busts.
    hidden_tail = .012 + .012 * quality if talent_model else .004
    probability = hidden_tail + (0.12 + 0.30 * quality) * math.exp(-(rank - 1) / 9.0)
    # Separate draws preserve identities, medicals and the rest of the class.
    rng = random.Random(f"{year}:{seed}:{rank}:ceiling_tail")
    if rng.random() < probability:
        potential = max(potential, 85.0 + quality * 4.0 + rng.uniform(-3.0, 4.0))
    return clamp(potential, 0.0, 97.0)


def prospect_evaluation_value(prospect: DraftProspect | dict[str, Any], key: str) -> float:
    """Draft evaluations cannot observe the additional latent development tail."""
    if isinstance(prospect, dict):
        prior = prospect.get("scouting_prior") or {}
        value = prospect.get(key)
    else:
        prior = prospect.scouting_prior
        value = getattr(prospect, key)
    return float(prior.get(key, value) or 0)


def generated_trait_values(prospect: DraftProspect, rng: random.Random) -> dict[str, float]:
    base = {key: clamp(prospect.current_ability + rng.gauss(0, 8), 25, 94) for key in DRAFT_TRAITS}
    inferred = infer_trait_values(prospect.position, prospect.archetype, {}, prospect.height_inches)
    new_model = TALENT_SOURCE_ID in prospect.source_ids
    tools = 0 if new_model else clamp((prospect.potential - 80.0) / 12.0, 0.0, 1.0) * 4.0
    values = {key: round(clamp((base[key] + inferred[key]) / 2 + tools, 25, 95), 2) for key in DRAFT_TRAITS}
    return diverse_prospect_skills(prospect, values) if new_model else values


def development_curve(age: float | None, class_year: str | None, archetype: str) -> str:
    age = float(age or 20.0)
    if age <= 19.2:
        return "long_upside_curve"
    if class_year in {"Senior", "Sr.", "International"} or age >= 22.5:
        return "early_readiness_limited_upside"
    if archetype in {"lead_creator", "rim_protecting_big", "scoring_wing"}:
        return "high_variance_star_curve"
    return "standard_development_curve"


def apply_public_ranks(prospects: list[Any]) -> list[Any]:
    """Number each generated class by the public grade every team can see. Dicts are updated in place; frozen
    dataclasses are replaced, so use the returned list.

    Generated classes used to keep their creation order as "rank" (rank 3 could have 64 potential while rank 11
    had 87), so the public board said nothing and AI teams "passed" on top-ranked prospects. The grade is
    generated_bpa_grade: public potential, current ability, floor, public ceiling, volatility and medicals -
    the same numbers the AI drafts on, never the hidden upside tail. Imported (real) classes keep their mock
    ranks. Rookie-contract value follows the new slot.
    """
    import dataclasses
    plain = lambda p: p if isinstance(p, dict) else to_plain(p)
    replaced: dict[int, Any] = {}
    by_year: dict[str, list[Any]] = {}
    generated_years = {str(plain(p).get("draft_year")) for p in prospects if plain(p).get("league") == "generated"
                       or real_prospect_data.SOURCE_ID in (plain(p).get("source_ids") or [])}
    for prospect in prospects:
        # A class with generated members is ranked as a whole (real college prospects mixed into a future class
        # share its board); fully imported classes keep their own ranks.
        if str(plain(prospect).get("draft_year")) in generated_years:
            by_year.setdefault(str(plain(prospect).get("draft_year")), []).append(prospect)
    for members in by_year.values():
        size = len(members)
        ordered = sorted(members, key=lambda p: (-generated_bpa_grade(plain(p)), int(plain(p).get("rank") or 99)))
        for rank, prospect in enumerate(ordered, start=1):
            row = plain(prospect)
            current, potential = float(row.get("current_ability") or 0), float(row.get("potential") or 0)
            updates = {"rank": rank, "rank_range": {"low": max(1, rank - 3), "high": min(size, rank + 5)},
                       "rookie_contract_value": round(rookie_contract_value(rank, current, potential), 2)}
            prior = row.get("scouting_prior") or {}
            if prior.get("potential") is not None:
                updates["scouting_prior"] = {**prior, "rookie_contract_value": round(
                    rookie_contract_value(rank, current, float(prior["potential"])), 2)}
            if isinstance(prospect, dict):
                prospect.update(updates)
            else:
                replaced[id(prospect)] = dataclasses.replace(prospect, **updates)
    return [replaced.get(id(p), p) for p in prospects]


def rookie_contract_value(rank: int, current: float, potential: float) -> float:
    return clamp((potential * 0.5 + current * 0.3) + max(0, 35 - rank) * 0.42, 1, 99)


def weighted_archetypes(config: dict[str, Any]) -> list[tuple[str, float]]:
    return [(key, float(value)) for key, value in config["archetype_weights"].items()]


def position_for_archetype(archetype: str) -> str:
    return {
        "lead_creator": "PG",
        "scoring_wing": "SG/SF",
        "two_way_wing": "SF",
        "connector_guard": "PG/SG",
        "movement_shooter": "SG",
        "rim_pressure_guard": "PG",
        "versatile_forward": "SF/PF",
        "stretch_big": "PF/C",
        "rim_protecting_big": "C",
        "energy_big": "PF/C",
    }[archetype]


# Primary/secondary position by archetype. Weighted with the archetype mix this gives about 19% PG, 22% SG,
# 24% SF, 18% PF and 17% C primaries, close to real draftees 2022-26 still in the league (18 / 22 / 26 / 18 / 16%).
ARCHETYPE_POSITIONS: dict[str, tuple[tuple[str, float], ...]] = {
    "lead_creator": (("PG", 1.0),),
    "connector_guard": (("PG/SG", 0.5), ("SG/PG", 0.5)),
    "rim_pressure_guard": (("PG/SG", 0.4), ("SG/PG", 0.6)),
    "movement_shooter": (("SG", 0.75), ("SF/SG", 0.25)),
    "scoring_wing": (("SG/SF", 0.4), ("SF/SG", 0.6)),
    "two_way_wing": (("SF", 0.7), ("SG/SF", 0.15), ("PF/SF", 0.15)),
    "versatile_forward": (("SF/PF", 0.4), ("PF/SF", 0.6)),
    "stretch_big": (("PF/C", 0.6), ("C/PF", 0.4)),
    "rim_protecting_big": (("C", 1.0),),
    "energy_big": (("PF/C", 0.45), ("C/PF", 0.55)),
}


def generated_position(archetype: str, rng: random.Random) -> str:
    options = ARCHETYPE_POSITIONS.get(archetype) or ((position_for_archetype(archetype), 1.0),)
    return rng.choices([o[0] for o in options], weights=[o[1] for o in options], k=1)[0]


# Prospect profile by draft slot, on the game's own prospect scale (current ability and potential). Anchored to the
# real 2026 class as the game rates it (53 drafted players): pick 1-3 current ~58 / potential ~88, picks 6-10 ~54 / 80,
# 11-20 ~52.5 / 73, 21-30 ~51 / 69, second round ~46 / 50. Ages follow real rookie-season ages of the 2015-2022
# classes (Basketball Index): 19 for picks 1-3, 20 for 4-20, 21 for 21-30, 22 in the second round.
PROFILE_CURRENT = ((1, 62.0), (3, 60.0), (5, 56.5), (10, 54.0), (20, 52.0), (30, 50.8), (40, 47.5), (50, 45.5), (60, 43.5))
PROFILE_POTENTIAL = ((1, 88.0), (4, 85.0), (8, 80.5), (12, 77.0), (18, 72.0), (24, 69.5), (30, 65.0), (36, 56.5),
                     (45, 51.0), (60, 46.5))
PROFILE_AGE = ((1, 19.2), (3, 19.35), (10, 19.9), (20, 20.3), (30, 20.9), (40, 21.8), (60, 22.4))
# Each year younger than the slot's typical age means a little less now and more upside later (real 2026 class:
# older picks at a slot carry lower potential).
AGE_CURRENT_PER_YEAR = 0.8
AGE_POTENTIAL_PER_YEAR = 2.5
# Spread around the slot profile (the real 2026 class's residual spread is about 2.5 current and 5-7 potential).
CURRENT_SPREAD = 2.4
PUBLIC_POTENTIAL_SPREAD = 4.5
# What scouting misses about a prospect's true upside, either way. Sized so that year-4 outcomes by pick range
# (stars, starters, busts) match real classes; see docs/agents/tasks/prospect-realism.md.
SCOUTING_MISS_SPREAD = 6.0
# Strong and weak drafts: a class's top-end / depth strength shifts its prospects' level and upside.
CLASS_CURRENT_PER_POINT = 0.30
CLASS_POTENTIAL_PER_POINT = 0.55


def _slot_value(table: tuple[tuple[int, float], ...], rank: int) -> float:
    rank = max(table[0][0], min(table[-1][0], rank))
    for (r0, v0), (r1, v1) in zip(table, table[1:]):
        if r0 <= rank <= r1:
            return v0 + (v1 - v0) * (rank - r0) / (r1 - r0)
    return table[-1][1]


def generated_prospect_profile(rank: int, size: int, top_strength: float, depth_strength: float,
                               rng: random.Random) -> dict[str, float]:
    """Age, current ability, public potential and the scouting miss for the prospect expected at this slot."""
    slot = max(1, round(rank * 60 / max(1, size)))
    typical_age = _slot_value(PROFILE_AGE, slot)
    age = clamp(rng.gauss(typical_age, 0.55 if slot <= 10 else 0.9 if slot <= 30 else 1.0), 18.6, 24.4)
    age_gap = whole_prospect_age(age) - typical_age
    # Top-end strength (mean ~61) drives the lottery, depth (mean ~56.5) the rest; blend across picks 10-20.
    blend = clamp((slot - 10) / 10, 0.0, 1.0)
    strength = (1 - blend) * (top_strength - 61.0) + blend * (depth_strength - 56.5)
    current = (_slot_value(PROFILE_CURRENT, slot) + CLASS_CURRENT_PER_POINT * strength
               + AGE_CURRENT_PER_YEAR * age_gap + rng.gauss(0.0, CURRENT_SPREAD))
    public_potential = (_slot_value(PROFILE_POTENTIAL, slot) + CLASS_POTENTIAL_PER_POINT * strength
                        - AGE_POTENTIAL_PER_YEAR * age_gap + rng.gauss(0.0, PUBLIC_POTENTIAL_SPREAD))
    current = clamp(current, 30.0, 70.0)
    public_potential = clamp(public_potential, current + 1.0, 96.0)
    return {"age": age, "current": current, "public_potential": public_potential,
            "scouting_miss": rng.gauss(0.0, SCOUTING_MISS_SPREAD)}


def generated_prospect_name(rng: random.Random, rank: int) -> str:
    first = [
        "Malik", "Jalen", "Cameron", "Darius", "Noah", "Elijah", "Isaiah", "Milan", "Andre", "Kobe",
        "Tariq", "Nolan", "Mateo", "Jonas", "Kellan", "Amari", "Dante", "Emil", "Tobias", "Micah",
        "Quentin", "Luca", "Rafael", "Jabari", "Devin", "Kyrie", "Oscar", "Elias", "Myles", "Zaire",
        "Brandon", "Simeon", "Julian", "Kai", "Terrell", "Xavier", "Omar", "Adrian", "Makai", "Tomas",
        "Aamir", "Aden", "Alessandro", "Alonzo", "Arjun", "August", "Baylor", "Bennett", "Blaise", "Caleb",
        "Cassius", "Cedi", "Chance", "Coby", "Dajuan", "Damari", "Deni", "Dominic", "Donovan", "Efe",
        "Emanuel", "Enzo", "Felix", "Francis", "Gabe", "Hassan", "Henrik", "Ikenna", "Ismael", "Jace",
        "Jamal", "Javon", "Jeremiah", "Joao", "Kacper", "Kamari", "Keon", "Khalil", "Kofi", "Leandro",
        "Liam", "Malachi", "Marcel", "Matas", "Niko", "Omari", "Pavel", "Remy", "Rocco", "Samir",
        "Sekou", "Silas", "Solomon", "Tadej", "Trey", "Viktor", "Yannick", "Yusuf", "Zion", "Zoran",
    ]
    last = [
        "Reed", "Brooks", "Carter", "Holland", "Bennett", "Okafor", "Murray", "Silva", "Hayes", "Ndiaye",
        "Wallace", "Porter", "Daniels", "Ilic", "Freeman", "Vargas", "Bishop", "Mathis", "Gaines", "Lawson",
        "Cross", "Santos", "Balde", "Moreau", "Hawkins", "Whitaker", "Morrison", "Diallo", "Petrovic", "Sato",
        "Ellis", "Kowalski", "Mensah", "Harrison", "Navarro", "Griffin", "Stone", "Camara", "Blackwell", "Rhodes",
        "Mendez", "Laurent", "Robinson", "Foster", "Klein", "Turner", "Boateng", "Hart", "Walters", "Sullivan",
        "Kimani", "Montgomery", "Hughes", "Bamba", "Carlson", "Rojas", "Ibrahim", "Vaughn", "Parker", "Bates",
        "Grant", "Okoro", "Hendrix", "Adebayo", "Baker", "Lang", "Shepard", "Morales", "Washington", "Keita",
        "Abdoulaye", "Akinyemi", "Almeida", "Andersson", "Armitage", "Barrett", "Beauchamp", "Belmonte", "Bjelica", "Bouanga",
        "Bouchard", "Brankovic", "Bridges", "Cabral", "Caldwell", "Castillo", "Cisse", "Coleman", "Conley", "Dabo",
        "DaSilva", "DeWitt", "Dominguez", "Duarte", "Eke", "El-Amin", "Fall", "Fofana", "Fontaine", "Galloway",
        "Garcia", "Gueye", "Haddad", "Halvorsen", "Hampton", "Hernandez", "Ionescu", "Jallow", "Jensen", "Kaba",
        "Kamara", "Kouame", "Kovacevic", "Larsson", "Lemaire", "Lombardi", "Lundqvist", "Mabry", "Maldonado", "Marinkovic",
        "Mbaye", "McAllister", "Mekonnen", "Mercer", "Mokoena", "Nwosu", "Ogunleye", "Oliveira", "Onyeka", "Owusu",
        "Pacheco", "Papadopoulos", "Quintana", "Rahman", "Renard", "Sarr", "Schroeder", "Sissoko", "Stojanovic", "Toure",
        "Valencia", "VanDijk", "Vasquez", "Watanabe", "Williams", "Yilmaz", "Zoric", "Adeyemi", "Bellamy", "Chukwu",
    ]
    first_name = rng.choice(first)
    last_name = rng.choice(last)
    name_style = rng.random()
    if name_style < 0.12:
        second_last = rng.choice([candidate for candidate in last if candidate != last_name])
        last_name = f"{last_name}-{second_last}"
    elif name_style < 0.20:
        second_last = rng.choice([candidate for candidate in last if candidate != last_name])
        last_name = f"{last_name} {second_last}"
    name = f"{first_name} {last_name}"
    suffix_roll = rng.random()
    if suffix_roll < 0.025:
        name += " Jr."
    elif suffix_roll < 0.045:
        name += " II"
    return name


def whole_prospect_age(value: Any) -> int | None:
    """Use the league's shared whole-year age convention for draft players."""
    age = maybe_float(value)
    if age is None:
        return None
    return int(math.floor(age + 0.5))


def generated_unique_fallback_name(rank: int, seen_names: set[str]) -> str:
    first = ["Ari", "Blaise", "Cade", "Dorian", "Ezra", "Finn", "Gabe", "Hugo", "Ivan", "Jude"]
    last = [
        "Ashford", "Beasley", "Caldwell", "Drake", "Easton", "Fleming", "Gibson", "Hampton", "Irving", "Jennings",
        "King", "Larsen", "Mercer", "Nolan", "Osborne", "Preston", "Quinn", "Ramsey", "Sanders", "Tucker",
    ]
    for offset in range(len(first) * len(last)):
        name = f"{first[(rank + offset) % len(first)]} {last[(rank * 3 + offset) % len(last)]}"
        if normalize_name(name) not in seen_names:
            return name
    return f"{first[rank % len(first)]} {last[rank % len(last)]}"


GENERATED_SOURCE_TEAMS = (
    "Alabama", "Arizona", "Arkansas", "Auburn", "Baylor", "BYU", "Cincinnati", "Creighton", "Duke", "Florida",
    "Florida State", "Gonzaga", "Houston", "Illinois", "Indiana", "Iowa", "Iowa State", "Kansas", "Kentucky",
    "Louisville", "Marquette", "Memphis", "Michigan", "Michigan State", "North Carolina", "Northwestern", "Ohio State",
    "Oregon", "Purdue", "San Diego State", "Santa Clara", "South Florida", "St. John's", "Stanford", "Tennessee",
    "Texas", "Texas Tech", "UConn", "USC", "UCLA", "Vanderbilt", "Villanova", "Virginia", "Washington",
    "Australia", "Brazil", "Canada", "China", "Croatia", "France", "Germany", "Greece", "Italy", "Japan", "Latvia",
    "Lithuania", "New Zealand", "Nigeria", "Serbia", "Slovenia", "South Sudan", "Spain", "Turkey",
)


def generated_source_team(rng: random.Random, available: list[str] | None = None) -> str:
    if available is None:
        return rng.choice(GENERATED_SOURCE_TEAMS)
    if not available:
        available.extend(GENERATED_SOURCE_TEAMS)
    return available.pop(rng.randrange(len(available)))


def generated_class_year(age: float) -> str:
    if age <= 19.4:
        return "Freshman"
    if age <= 20.5:
        return "Sophomore"
    if age <= 21.7:
        return "Junior"
    return "Senior"


def generated_height(position: str, rng: random.Random) -> float:
    position = primary_position_label(position)
    if "C" in position:
        return round(rng.gauss(82, 1.8), 1)
    if "PF" in position:
        return round(rng.gauss(80, 1.8), 1)
    if "SF" in position:
        return round(rng.gauss(78, 1.7), 1)
    if "SG" in position:
        return round(rng.gauss(76, 1.6), 1)
    return round(rng.gauss(74, 1.8), 1)


def generated_weight(position: str, rng: random.Random) -> float:
    position = primary_position_label(position)
    if "C" in position:
        return round(rng.gauss(245, 18), 0)
    if "PF" in position:
        return round(rng.gauss(225, 17), 0)
    if "SF" in position:
        return round(rng.gauss(210, 15), 0)
    return round(rng.gauss(190, 14), 0)


def scouting_staff_score(canonical: dict[str, Any], team_id: str) -> dict[str, float]:
    slot = next((slot for slot in canonical.get("gameplay_staff_slots", []) if slot["team_id"] == team_id and slot["slot"] == "scouting_lead"), None)
    traits = (slot or {}).get("skill_traits") or {}
    talent = float(traits.get("talent_eval", 60))
    risk = float(traits.get("risk_modeling", 60))
    international = float(traits.get("international_coverage", 60))
    score = talent * 0.58 + risk * 0.27 + international * 0.15
    return {"talent_eval": talent, "risk_modeling": risk, "international_coverage": international, "score": score, "confidence": clamp(0.42 + (score - 50) / 100, 0.38, 0.88)}


def scouting_noise(staff: dict[str, float], prospect: DraftProspect, config: dict[str, Any]) -> float:
    scouting = config["scouting"]
    score = staff["score"]
    noise = float(scouting["base_noise"]) - (score - 60) * 0.09
    if prospect.league == "International":
        noise += max(0.0, 65 - staff["international_coverage"]) * 0.04
    noise += prospect.volatility * 0.05
    return clamp(noise, float(scouting["excellent_staff_noise"]), float(scouting["poor_staff_noise"]))


def noisy_range(value: float, noise: float, rng: random.Random) -> dict[str, float]:
    estimated = clamp(value + rng.gauss(0, noise * 0.45), 1, 99)
    half = max(1.2, noise)
    return {"low": round(clamp(estimated - half, 1, 99), 2), "mid": round(estimated, 2), "high": round(clamp(estimated + half, 1, 99), 2)}


def trait_noise_multiplier(trait_key: str, position: str, staff: dict[str, float]) -> float:
    if ("PG" in position or "SG" in position) and trait_key in {"shot_creation", "passing", "shooting"}:
        return 0.9
    if ("PF" in position or "C" in position) and trait_key in {"rim_protection", "rebounding", "size"}:
        return 0.9
    return 1.0


def estimate_grade(current: dict[str, float], potential: dict[str, float], floor: float, volatility: float) -> float:
    return clamp(current["mid"] * 0.33 + potential["mid"] * 0.49 + floor * 0.12 - volatility * 0.06, 1, 99)


def prospect_team_fit(canonical: dict[str, Any], team_id: str, prospect: DraftProspect | dict[str, Any],
                      spatial_cache: dict[Any, Any] | None = None, *, include_phase: bool = True) -> float:
    prospect = to_plain(prospect)
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team_id)
    fit = 50.0
    pos = str(prospect["position"]).lower()
    needs = " ".join(state.get("needs", []))
    if "primary_creation" in needs and prospect["archetype"] in {"lead_creator", "scoring_wing"}:
        fit += 10
    if "shooting" in needs and prospect["archetype"] in {"movement_shooter", "stretch_big", "scoring_wing"}:
        fit += 9
    if "rim_protection" in needs and "big" in pos or ("c" in pos and "rim_protection" in needs):
        fit += 8
    if "wing_depth" in needs and ("sf" in pos or "wing" in prospect["archetype"]):
        fit += 7
    if include_phase and state["phase"] in {"rebuilding", "developing"}:
        fit += max(0.0, prospect_evaluation_value(prospect, "ceiling") - 76) * 0.35
    if include_phase and state["phase"] in {"contending", "contending_with_future_upside"}:
        fit += max(0.0, float(prospect["current_ability"]) - 56) * 0.45
    if prospect["archetype"] in {"two_way_wing", "movement_shooter", "rim_protecting_big"}:
        fit += 3
    if prospect.get("position") == "C":
        values = {item.get("player_id"): item for item in canonical.get("player_asset_valuations", [])}
        young_franchise_center = any(
            player.get("team_id") == team_id
            and player.get("position") == "C"
            and float(player.get("age") or 30.0) <= 27.0
            and float((values.get(player.get("id")) or {}).get("player_value") or 0.0) >= 68.0
            for player in canonical.get("players", [])
        )
        if young_franchise_center and prospect.get("archetype") in {"rim_protecting_big", "traditional_center", "interior_big"}:
            fit -= 12.0
    if redundant_small_offense_guard_pick(canonical, team_id, prospect):
        fit -= 14.0
    fit += prospect_spatial_fit_delta(canonical, team_id, prospect, cap=6.0, cache=spatial_cache)
    return clamp(fit, 1, 99)


def redundant_small_offense_guard_pick(canonical: dict[str, Any], team_id: str, prospect: dict[str, Any]) -> bool:
    position = str(prospect.get("position") or "").upper()
    archetype = str(prospect.get("archetype") or "")
    if "PG" not in position and "SG" not in position:
        return False
    if archetype not in {"lead_creator", "rim_pressure_guard", "scoring_guard", "movement_shooter"}:
        return False
    try:
        height = float(prospect.get("height_inches") or 78.0)
    except (TypeError, ValueError):
        height = 78.0
    if height > 76.5:
        return False
    values = {item.get("player_id"): item for item in canonical.get("player_asset_valuations", [])}
    for player in canonical.get("players", []):
        if player.get("team_id") != team_id:
            continue
        name = normalize_name(player.get("name"))
        pos = str(player.get("position") or "").upper()
        value = float((values.get(player.get("id")) or {}).get("player_value") or 0.0)
        if name == normalize_name("Luka Doncic"):
            return True
        if ("PG" in pos or "SG" in pos) and value >= 84.0 and float(player.get("age") or 30.0) <= 31.0:
            return True
    return False


def prospect_cap_value(canonical: dict[str, Any], team_id: str, prospect: DraftProspect | dict[str, Any]) -> float:
    prospect = to_plain(prospect)
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team_id)
    value = prospect_evaluation_value(prospect, "rookie_contract_value")
    if state["salary_posture"].startswith("expensive"):
        value += 12
    if state["salary_posture"].startswith("above_cap"):
        value += 7
    if state["phase"] in {"contending", "contending_with_future_upside"} and float(prospect["current_ability"]) >= 56:
        value += 5
    return clamp(value, 1, 99)


def board_entry_payload(entry: dict[str, Any], prospect: dict[str, Any], consensus: dict[str, Any] | None = None) -> dict[str, Any]:
    """Expose canonical prospect.id and retain prospect_id for API compatibility.

    Only public numbers: the league consensus when it is known, else the class's public potential and ceiling.
    The hidden true potential and ceiling never leave the engine (rule 4; draft-boards plan step 1)."""
    height_inches = maybe_float(prospect.get("height_inches"))
    height = ""
    if height_inches is not None:
        rounded_height = int(round(height_inches))
        height = f"{rounded_height // 12}'{rounded_height % 12}\""
    potential = prospect_evaluation_value(prospect, "potential")
    ceiling = prospect_evaluation_value(prospect, "ceiling")
    current = float(prospect.get("current_ability") or 0.0)
    if consensus:
        ceiling = round(ceiling + float(consensus["potential"]) - potential, 2)
        potential = round(float(consensus["potential"]), 2)
        current = round(float(consensus["current"]), 2)
    return {
        **entry,
        "prospect": {
            "id": prospect["id"],
            "prospect_id": prospect["id"],
            "name": prospect["name"],
            "rank": (consensus or {}).get("rank") or prospect["rank"],
            "public_rank": prospect["rank"],
            "rank_range": ({"low": consensus["middle"][0], "high": consensus["middle"][1]} if consensus
                           else dict(prospect.get("rank_range") or {})),
            "position": prospect["position"],
            "age": whole_prospect_age(prospect.get("age")),
            "height_inches": height_inches,
            "height": height,
            "source_team": prospect.get("source_team"),
            "league": prospect.get("league"),
            "draft_year": prospect.get("draft_year"),
            "archetype": prospect["archetype"],
            "current_ability": current,
            "potential": potential,
            "floor": prospect.get("floor"),
            "ceiling": ceiling,
            "volatility": prospect["volatility"],
            "confidence": prospect.get("confidence"),
            "development_curve": prospect.get("development_curve"),
            "rookie_contract_value": prospect_evaluation_value(prospect, "rookie_contract_value"),
            "weight_lbs": prospect.get("weight_lbs"),
            "headshot_url": prospect_headshot_url(prospect),
        },
    }


def resolve_prospect(canonical: dict[str, Any], query: str, year: str = "2026") -> dict[str, Any]:
    needle = normalize_name(query)
    prospects = [p for p in canonical.get("draft_prospects", []) if p["draft_year"] == str(year)]
    matches = [p for p in prospects if p["id"] == query or p["normalized_name"] == needle or needle in normalize_name(p["name"])]
    if not matches:
        raise ValueError(f"No draft prospect found matching {query!r}")
    return sorted(matches, key=lambda item: item["rank"])[0]


def pick_overall(pick: dict[str, Any]) -> int:
    for field in ("overall_pick", "projected_pick_slot"):
        if pick.get(field) is not None:
            try:
                return int(pick[field])
            except (TypeError, ValueError):
                pass
    try:
        return int(pick["id"].split("-")[2])
    except (IndexError, ValueError):
        return int(pick.get("round") or 1) * 30


def best_lower_pick_for_trade(canonical: dict[str, Any], team_id: str, target_pick: dict[str, Any]) -> dict[str, Any] | None:
    target_overall = pick_overall(target_pick)
    picks = [p for p in canonical["draft_picks"] if p.get("current_owner_team_id") == team_id and p.get("season") == target_pick.get("season")]
    lower = [p for p in picks if pick_overall(p) > target_overall]
    if lower:
        return sorted(lower, key=pick_overall)[0]
    future = [p for p in canonical["draft_picks"] if p.get("current_owner_team_id") == team_id and str(p.get("season")) > str(target_pick.get("season")) and int(p.get("round") or 0) == 1]
    return sorted(future, key=lambda item: (str(item.get("season")), item["id"]))[0] if future else None


def draft_trade_sweetener(canonical: dict[str, Any], buyer_team_id: str, seller_top_grade: float, buyer_target_grade: float) -> dict[str, Any] | None:
    if buyer_target_grade - seller_top_grade < 8:
        return None
    block = [entry for entry in canonical.get("trade_block_entries", []) if entry["team_id"] == buyer_team_id]
    if not block:
        return None
    players = {p["id"]: p for p in canonical["players"]}
    candidate = sorted(block, key=lambda item: item["block_score"], reverse=True)[0]
    player = players.get(candidate["player_id"])
    return {"kind": "player", "value": player["name"]} if player else None


def draft_trade_score(report: dict[str, Any], buyer_entry: dict[str, Any], seller_top_grade: float) -> float:
    evals = report.get("evaluations", [])
    acceptance = 18 if report.get("accepted_by_all") else 0
    combined = sum(float(item.get("net_value") or 0) for item in evals)
    urgency = max(0.0, float(buyer_entry["risk_adjusted_grade"]) - seller_top_grade)
    return combined + urgency + acceptance


def draft_trade_reasons(report: dict[str, Any], buyer_entry: dict[str, Any], seller_top_grade: float) -> list[str]:
    reasons = []
    if report.get("accepted_by_all"):
        reasons.append("accepted_by_existing_trade_model")
    if float(buyer_entry["risk_adjusted_grade"]) - seller_top_grade >= 8:
        reasons.append("buyer_targets_clear_board_tier")
    if not reasons:
        reasons.append("diagnostic_trade_candidate")
    return reasons


def generated_class_for_context(canonical: dict[str, Any], year: str, seed: int = 1, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """A career's preview and draft share a class; selection RNG stays separate."""
    saved_seed = canonical.get("meta", {}).get("draft_class_seed")
    class_seed = int(saved_seed if saved_seed is not None else seed)
    config = config or default_draft_model_config()
    key = (str(year), class_seed, talent_enabled(canonical), json.dumps(config, sort_keys=True))
    cache = canonical.setdefault("_generated_draft_records_cache", {}) if canonical.get("_allow_internal_caches") else {}
    if key not in cache:
        cache[key] = to_plain(generate_draft_class_records(str(year), class_seed, config, talent_model=talent_enabled(canonical),
                                                           real_prospects=real_prospect_data.enabled(config)))
    return cache[key]


def generated_board_report(canonical: dict[str, Any], team_query: str, year: str, seed: int, limit: int | None, config: dict[str, Any] | None) -> dict[str, Any]:
    """Kept for callers: every class now has team scouting, so this is draft_board_report."""
    return draft_board_report(canonical, team_query, year, limit=limit, config=config)


def projected_standings_order(canonical: dict[str, Any], seed: int, standings: Any | None, config: dict[str, Any]) -> list[dict[str, Any]]:
    explicit = explicit_standings_order(canonical, standings)
    if explicit:
        return explicit
    rng = random.Random(f"{seed}:projected_standings")
    states = {state["team_id"]: state for state in canonical.get("team_strategic_states", [])}
    phase_bonus = {
        "rebuilding": -9,
        "developing": -4,
        "retooling": 0,
        "playoff_chase": 4,
        "contending": 10,
        "contending_with_future_upside": 11,
    }
    scored = []
    for team in canonical["teams"]:
        state = states.get(team["id"], {})
        score = float(state.get("contention_ceiling") or 50)
        score += phase_bonus.get(str(state.get("phase")), 0)
        score -= float(state.get("health_risk") or 0) * 0.06
        score += rng.uniform(-float(config["lottery"].get("standings_noise", 1.75)), float(config["lottery"].get("standings_noise", 1.75)))
        scored.append((score, team))
    return [team for _, team in sorted(scored, key=lambda item: (item[0], item[1]["abbrev"]))]


def explicit_standings_order(canonical: dict[str, Any], standings: Any | None) -> list[dict[str, Any]] | None:
    if not standings:
        return None
    rows = standings.get("teams", standings) if isinstance(standings, dict) else standings
    if not isinstance(rows, list):
        return None
    indexed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        team_key = row.get("team") or row.get("team_abbrev") or row.get("abbrev") or row.get("team_id")
        if not team_key:
            continue
        team = resolve_team(canonical, str(team_key))
        wins = maybe_float(row.get("wins"))
        losses = maybe_float(row.get("losses"))
        rank = maybe_float(row.get("reverse_rank") or row.get("lottery_rank") or row.get("rank"))
        if wins is not None:
            score = wins
        elif losses is not None:
            score = -losses
        elif rank is not None:
            score = rank
        else:
            score = len(indexed) + 1
        indexed.append((score, team))
    if len(indexed) != len(canonical.get("teams", [])):
        return None
    return [team for _, team in sorted(indexed, key=lambda item: (item[0], item[1]["abbrev"]))]


def draw_lottery_teams(lottery_candidates: list[dict[str, Any]], seed: int, year: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    rng = random.Random(f"{year}:{seed}:draft_lottery")
    weights = list(config["lottery"].get("odds_weights") or [])
    remaining = list(lottery_candidates)
    remaining_weights = {team["id"]: float(weights[index] if index < len(weights) else 1) for index, team in enumerate(lottery_candidates)}
    drawn = []
    for _ in range(min(int(config["lottery"].get("draw_count", 4)), len(remaining))):
        total = sum(remaining_weights[team["id"]] for team in remaining)
        target = rng.random() * total
        running = 0.0
        selected = remaining[-1]
        for team in remaining:
            running += remaining_weights[team["id"]]
            if running >= target:
                selected = team
                break
        drawn.append(selected)
        remaining = [team for team in remaining if team["id"] != selected["id"]]
    return drawn


def lottery_odds_by_team(lottery_candidates: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, float]:
    weights = [float(value) for value in config["lottery"].get("odds_weights", [])]
    total = sum(weights[: len(lottery_candidates)]) or 1.0
    return {team["id"]: round((weights[index] if index < len(weights) else 1.0) / total, 4) for index, team in enumerate(lottery_candidates)}


def owner_for_generated_pick(canonical: dict[str, Any], year: str, round_no: int, original_team_id: str) -> str:
    candidates = [
        pick
        for pick in canonical.get("draft_picks", [])
        if str(pick.get("season")) == str(year)
        and int(pick.get("round") or 0) == round_no
        and (pick.get("original_team_id") == original_team_id or pick.get("team_id") == original_team_id)
        and pick.get("current_owner_team_id")
    ]
    if not candidates:
        return original_team_id
    candidates = sorted(candidates, key=lambda item: (item.get("status") == "research_pending", item.get("id", "")))
    return candidates[0].get("current_owner_team_id") or original_team_id


def generated_bpa_grade(prospect: dict[str, Any]) -> float:
    return (
        prospect_evaluation_value(prospect, "potential") * 0.56
        + float(prospect.get("current_ability") or 0) * 0.28
        + float(prospect.get("floor") or 0) * 0.1
        + prospect_evaluation_value(prospect, "ceiling") * 0.06
        - float(prospect.get("volatility") or 0) * 0.05
        - prospect_medical_penalty(prospect)
    )


def season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def scouting_board_entry(canonical: dict[str, Any], scouting: dict[str, Any], team_id: str, prospect_id: str,
                         gm_row: dict[str, Any] | None = None, previous_rank: int | None = None) -> dict[str, Any]:
    """One row of a team's board: its scouts' rank and read, the consensus rank and spread, and the GM's fit note."""
    report = scouting["reports"][team_id][prospect_id]
    prospect = scouting["prospects"][prospect_id]
    consensus = scouting["consensus"][prospect_id]
    fit = gm_row["fit"] if gm_row else gm_need_fit(canonical, team_id, prospect)
    entry = {
        "id": stable_id("draft_board", team_id, prospect_id),
        "team_id": team_id,
        "prospect_id": prospect_id,
        "draft_year": str(prospect.get("draft_year")),
        "board_rank": report["scout_rank"],
        "scout_rank": report["scout_rank"],
        "previous_scout_rank": previous_rank,
        "scout_rank_change": (previous_rank - report["scout_rank"]) if previous_rank else None,
        "bpa_grade": report["scouted_grade"],
        "scout_grade": report["scouted_grade"],
        "consensus_rank": consensus["rank"],
        "consensus_best": consensus["best"],
        "consensus_worst": consensus["worst"],
        "consensus_middle": list(consensus["middle"]),
        "fit_grade": round(fit, 2),
        "need_fit": round(fit - 50.0, 2),
        "risk_adjusted_grade": round(gm_row["score"], 2) if gm_row else report["scouted_grade"],
        "cap_value": round(prospect_cap_value(canonical, team_id, prospect), 2),
        "development": report["development"],
        "coverage": report["coverage"],
        "scouts_differ": draft_scouting.where_scouts_differ(scouting, team_id, prospect_id),
        "month": scouting["month"],
        "month_label": scouting["month_label"],
    }
    return board_entry_payload(entry, prospect, consensus)


def gm_need_weight(overall_pick: int) -> float:
    for limit, weight in GM_NEED_WEIGHTS:
        if overall_pick <= limit:
            return weight
    return GM_NEED_WEIGHTS[-1][1]


def team_state(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    return next((s for s in canonical.get("team_strategic_states", []) if s.get("team_id") == team_id), {})


def gm_need_fit(canonical: dict[str, Any], team_id: str, prospect: dict[str, Any]) -> float:
    """Positional need and roster fit only (prospect_team_fit without its phase terms, which the GM adds itself)."""
    cache = canonical.setdefault("_draft_need_fit_cache", {})
    key = (team_id, prospect.get("id"))
    if key not in cache:
        spatial = canonical.setdefault("_draft_spatial_fit_cache", {})
        cache[key] = prospect_team_fit(canonical, team_id, prospect, spatial, include_phase=False)
    return cache[key]


def gm_rows(canonical: dict[str, Any], scouting: dict[str, Any], team_id: str, overall_pick: int,
            candidate_ids: list[str]) -> list[dict[str, Any]]:
    """The GM's order for this pick: his scouts' talent grade plus the team's context. Deterministic.

    - Phase: a rebuilding or developing team adds value for upside room beyond a typical prospect's; a contender
      adds value for a current level above a typical first-rounder's and dislikes volatility.
    - Need and fit: weighs more as the draft goes on (teams take the best talent at the top).
    - What is left: the GM takes the best of what is still there, so a prospect who slides gets taken.
    """
    state = team_state(canonical, team_id)
    phase = str(state.get("phase") or "")
    reports = scouting["reports"].get(team_id) or {}
    need_weight = gm_need_weight(int(overall_pick))
    rows = []
    for pid in candidate_ids:
        report = reports.get(pid)
        prospect = scouting["prospects"].get(pid)
        if not report or not prospect:
            continue
        current = report["estimated_current"]["mid"]
        potential = report["estimated_potential"]["mid"]
        phase_term = 0.0
        if phase in REBUILD_PHASES:
            phase_term = GM_PHASE_UPSIDE * (potential - current - GM_TYPICAL_ROOM)
        elif phase in CONTEND_PHASES:
            phase_term = GM_PHASE_READY * (current - GM_TYPICAL_CURRENT) - GM_CONTENDER_RISK * report["risk"]["volatility"]
        fit = gm_need_fit(canonical, team_id, prospect)
        need_term = need_weight * (fit - 50.0)
        # Price: taking a prospect the league ranks far below this pick pays this pick's price for a later pick's
        # player; a GM knows he could likely get him later or trade down for him.
        consensus_rank = scouting["consensus"][pid]["rank"]
        reach_term = -GM_REACH_WEIGHT * max(0.0, _slot_value(PROFILE_POTENTIAL, int(overall_pick))
                                            - _slot_value(PROFILE_POTENTIAL, consensus_rank) - GM_REACH_TOLERANCE)
        rows.append({
            "prospect_id": pid,
            "score": round(report["scouted_grade"] + phase_term + need_term + reach_term, 4),
            "reach_term": round(reach_term, 3),
            "scout_grade": report["scouted_grade"],
            "scout_rank": report["scout_rank"],
            "consensus_rank": scouting["consensus"][pid]["rank"],
            "phase_term": round(phase_term, 3),
            "need_term": round(need_term, 3),
            "fit": fit,
            "phase": phase,
        })
    rows.sort(key=lambda row: (-row["score"], row["consensus_rank"], row["prospect_id"]))
    return rows


def need_label(state: dict[str, Any], prospect: dict[str, Any]) -> str | None:
    needs = " ".join(state.get("needs") or [])
    archetype = str(prospect.get("archetype") or "")
    position = str(prospect.get("position") or "").lower()
    if "primary_creation" in needs and archetype in {"lead_creator", "scoring_wing"}:
        return "needs a lead creator"
    if "shooting" in needs and archetype in {"movement_shooter", "stretch_big", "scoring_wing"}:
        return "needs shooting"
    if "rim_protection" in needs and ("c" in position or "big" in archetype):
        return "needs a rim protector"
    if "wing_depth" in needs and ("sf" in position or "wing" in archetype):
        return "needs a wing"
    return None


def gm_decision(canonical: dict[str, Any], scouting: dict[str, Any], team: dict[str, Any], pick: dict[str, Any],
                row: dict[str, Any], rows: list[dict[str, Any]], seed: int = 1) -> DraftPickDecision:
    """The pick and its explanation, e.g. "PHX took Smith Jr. (consensus #4, their board #2): needs a wing; their
    scouts are higher on his defense"."""
    prospect = scouting["prospects"][row["prospect_id"]]
    overall = pick_overall(pick)
    best_scout = min(rows, key=lambda item: (item["scout_rank"], item["prospect_id"]))
    state = team_state(canonical, team["id"])
    reasons: list[str] = []
    words: list[str] = []
    if row["prospect_id"] == best_scout["prospect_id"]:
        reasons.append("best_player_available")
        words.append("the best player left on their board")
    label = need_label(state, prospect)
    if row["need_term"] >= 0.5 and label:
        reasons.append("team_need")
        words.append(label)
    if row["phase_term"] >= 0.5:
        if row["phase"] in REBUILD_PHASES:
            reasons.append("upside_matches_timeline")
            words.append("rebuilding, so they bet on his upside")
        else:
            reasons.append("near_term_rotation_path")
            words.append("contending, and he can help sooner")
    differ = draft_scouting.where_scouts_differ(scouting, team["id"], row["prospect_id"])
    if differ:
        reasons.append("scouts_differ")
        words.append(f"their scouts are {differ}")
    if row["consensus_rank"] - overall >= 4:
        reasons.append("value_reach")
    elif overall - row["consensus_rank"] >= 4:
        reasons.append("value_slide")
        words.append(f"he slid to {overall}")
    if not words:
        words.append("the best mix of talent and fit left")
    explanation = (f"{team.get('abbrev')} took {prospect.get('name')} (consensus #{row['consensus_rank']}, their board "
                   f"#{row['scout_rank']}): " + "; ".join(words) + ".")
    return DraftPickDecision(
        id=stable_id("draft_pick_decision", pick["id"], team["id"], prospect["id"], seed),
        pick_id=pick["id"],
        team_id=team["id"],
        prospect_id=prospect["id"],
        decision="select",
        bpa_rank=int(row["consensus_rank"]),
        team_board_rank=int(row["scout_rank"]),
        grade_gap_to_bpa=round(float(best_scout["scout_grade"]) - float(row["scout_grade"]), 3),
        reasons=sorted(dict.fromkeys(reasons)),
        source_ids=["src_draft_model_config_v1"],
        notes=explanation,
    )
