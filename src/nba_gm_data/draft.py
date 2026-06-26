from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

from .schema import (
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
from .transactions import (
    compact_player,
    evaluate_trade,
    pick_asset_value,
    pick_by_id,
    player_by_id,
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


def default_draft_model_config() -> dict[str, Any]:
    return {
        "version": "draft_model_v1",
        "generated_class_size": 60,
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
            "season_variance": 9.0,
            "top_end_variance": 11.0,
            "depth_variance": 8.0,
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


def build_draft_context(canonical: dict[str, Any] | Any, draft_research: dict[str, Any] | None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_transaction_context(canonical)
    config = config or default_draft_model_config()
    draft_classes, prospects, traits = build_2026_draft_records(draft_research, config)
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


def with_draft_context(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_transaction_context(canonical)
    if canonical.get("draft_classes") and canonical.get("draft_prospects") and canonical.get("draft_board_entries"):
        return canonical
    context = build_draft_context(canonical, None, config)
    return {**canonical, **context}


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
    age = maybe_float(row.get("age"))
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


def generate_draft_class_records(year: str, seed: int = 1, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or default_draft_model_config()
    rng = random.Random(f"{year}:{seed}:draft_class")
    size = int(config.get("generated_class_size", 60))
    strength_mean = float(config["class_strength"]["mean"])
    class_strength = clamp(rng.gauss(strength_mean, float(config["class_strength"]["season_variance"])), 42, 76)
    top_strength = clamp(class_strength + rng.gauss(0, float(config["class_strength"]["top_end_variance"])), 38, 84)
    depth_strength = clamp(class_strength + rng.gauss(0, float(config["class_strength"]["depth_variance"])), 38, 76)
    prospects: list[DraftProspect] = []
    traits: list[DraftProspectTrait] = []
    archetypes = weighted_archetypes(config)
    seen_names: set[str] = set()
    for rank in range(1, size + 1):
        archetype = rng.choices([item[0] for item in archetypes], weights=[item[1] for item in archetypes], k=1)[0]
        position = position_for_archetype(archetype)
        age = round(clamp(rng.gauss(19.8 if rank <= 35 else 20.8, 1.15), 18.4, 23.8), 1)
        readiness = top_strength if rank <= 14 else depth_strength
        current_cap = 69 if rank <= 3 else 65 if rank <= 14 else 60 if rank <= 30 else 56
        current = clamp(43 + (readiness - 55) * 0.46 + max(0, 18 - rank) * 0.36 + rng.gauss(0, 3.6), 28, current_cap)
        potential = clamp(current + 11 + max(0, 22 - rank) * 0.5 + rng.gauss(0, 5.6), current + 2, 97)
        floor = clamp(current - rng.uniform(5, 13), 20, current)
        ceiling = clamp(potential + rng.uniform(2, 9), potential, 99)
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
            source_team=generated_source_team(rng),
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
            source_ids=["src_draft_model_config_v1"],
            notes="Generated future draft prospect. True ratings are deterministic from year/seed and hidden behind scouting estimates.",
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
                source_ids=["src_draft_model_config_v1"],
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
    return {"draft_classes": [draft_class], "draft_prospects": prospects, "draft_prospect_traits": traits}


def draft_class_payload(canonical: dict[str, Any] | Any, year: str, seed: int = 1, scouted_for: str | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_draft_context(canonical, config)
    if str(year) == "2026":
        prospects = [p for p in canonical["draft_prospects"] if p["draft_year"] == "2026"]
        draft_classes = [c for c in canonical["draft_classes"] if c["season"] == "2026"]
        reports = []
        if scouted_for:
            team = resolve_team(canonical, scouted_for)
            reports = [r for r in canonical["scouting_reports"] if r["team_id"] == team["id"]]
    else:
        generated = generate_draft_class_records(str(year), seed=seed, config=config)
        prospects = to_plain(generated["draft_prospects"])
        draft_classes = to_plain(generated["draft_classes"])
        reports = []
    return {"year": str(year), "draft_classes": draft_classes, "prospect_count": len(prospects), "prospects": prospects, "scouting_reports": reports}


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
                    and (pick.get("original_team_id") == original_team_id or pick.get("team_id") == original_team_id)
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
                and (pick.get("original_team_id") == original_team["id"] or pick.get("team_id") == original_team["id"])
                and pick.get("current_owner_team_id")
            ]
            existing_pick = sorted(existing_candidates, key=lambda item: (item.get("status") == "research_pending", item.get("id", "")))[0] if existing_candidates else None
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


def draft_board_report(canonical: dict[str, Any] | Any, team_query: str, year: str = "2026", limit: int | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_draft_context(canonical, config)
    if str(year) != "2026":
        return generated_board_report(canonical, team_query, year, seed=1, limit=limit, config=config)
    team = resolve_team(canonical, team_query)
    prospects = {p["id"]: p for p in canonical["draft_prospects"]}
    entries = [entry for entry in canonical["draft_board_entries"] if entry["team_id"] == team["id"] and entry["draft_year"] == str(year)]
    entries = sorted(entries, key=lambda item: item["board_rank"])[: limit or len(entries)]
    return {"team": team, "year": str(year), "entry_count": len(entries), "entries": [board_entry_payload(entry, prospects[entry["prospect_id"]]) for entry in entries]}


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
    canonical = with_draft_context(canonical, config)
    team = resolve_team(canonical, team_query)
    pick = pick_by_id(canonical, pick_id)
    if not pick:
        raise ValueError(f"No pick found with id {pick_id!r}")
    year = str(pick.get("season") or "2026")
    prospects = {p["id"]: p for p in canonical["draft_prospects"] if p["draft_year"] == year}
    entries = [entry for entry in canonical["draft_board_entries"] if entry["team_id"] == team["id"] and entry["draft_year"] == year]
    taken_before = int(pick["id"].split("-")[2]) - 1 if pick.get("status") == "verified_2026_draft_board" and "-" in pick["id"] else 0
    unavailable_prospect_ids = unavailable_prospect_ids or set()
    available = [
        entry
        for entry in sorted(entries, key=lambda item: item["board_rank"])
        if entry["prospect_id"] not in unavailable_prospect_ids
        and int(prospects[entry["prospect_id"]]["rank"]) > max(0, taken_before - 2)
    ]
    recommendations = []
    for entry in available[:limit]:
        decision = draft_pick_decision(canonical, team, pick, prospects[entry["prospect_id"]], seed=seed, config=config)
        recommendations.append({"entry": board_entry_payload(entry, prospects[entry["prospect_id"]]), "decision": to_plain(decision)})
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
            report = evaluate_trade(canonical, seller["abbrev"], buyer["abbrev"], from_assets, to_assets, seed=seed)
        except ValueError:
            continue
        score = draft_trade_score(report, buyer_entries[0], seller_top_grade)
        candidate = DraftTradeCandidate(
            id=stable_id("draft_trade", pick["id"], buyer["id"], target_id, seed),
            pick_id=pick["id"],
            from_team_id=seller["id"],
            to_team_id=buyer["id"],
            target_prospect_id=target_id,
            trade_type="trade_down_or_trade_up",
            proposal=report["proposal"],
            evaluation=report,
            score=round(score, 3),
            reasons=draft_trade_reasons(report, buyer_entries[0], seller_top_grade),
            source_ids=["src_draft_model_config_v1", "src_transaction_model_config_v1"],
            notes="Draft-night trade candidate using existing trade legality/evaluation plus prospect board urgency.",
        )
        candidates.append(candidate)
    candidates = sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]
    return {"team": seller, "pick": pick, "candidate_count": len(candidates), "candidates": to_plain(candidates)}


def simulate_draft(canonical: dict[str, Any] | Any, year: str = "2026", seed: int = 1, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_draft_context(canonical, config)
    if str(year) != "2026":
        return simulate_generated_draft(canonical, str(year), seed=seed, config=config)
    prospects = {p["id"]: p for p in canonical["draft_prospects"] if p["draft_year"] == "2026"}
    available = set(prospects)
    selections: list[DraftSelection] = []
    decisions: list[DraftPickDecision] = []
    picks = sorted([p for p in canonical["draft_picks"] if p["season"] == "2026" and p.get("current_owner_team_id")], key=lambda item: (int(item["round"]), pick_overall(item)))
    for pick in picks:
        team = team_by_id(canonical, pick["current_owner_team_id"])
        entries = [entry for entry in canonical["draft_board_entries"] if entry["team_id"] == team["id"] and entry["prospect_id"] in available]
        if not entries:
            continue
        best = choose_entry_with_draft_chaos(canonical, entries, pick_overall(pick), team["id"], seed, prospects)
        prospect = prospects[best["prospect_id"]]
        decision = draft_pick_decision(canonical, team, pick, prospect, seed=seed, config=config)
        selection = DraftSelection(
            id=stable_id("draft_selection", pick["id"], prospect["id"], seed),
            pick_id=pick["id"],
            team_id=team["id"],
            prospect_id=prospect["id"],
            draft_year="2026",
            overall_pick=pick_overall(pick),
            status="selected",
            decision_id=decision.id,
            source_ids=["src_draft_model_config_v1"],
            notes="Simulated draft selection. Draft-night trades are exposed via find-draft-trade and can be applied separately to a save ledger.",
        )
        selections.append(selection)
        decisions.append(decision)
        available.remove(prospect["id"])
    selection_payload = to_plain(selections)
    rookie_payload = draft_onboarding_records(canonical, selection_payload, list(prospects.values()), picks, config or default_draft_model_config())
    return {
        "year": "2026",
        "seed": seed,
        "selection_count": len(selections),
        "selections": selection_payload,
        "decisions": to_plain(decisions),
        "pending_draft_selections": pending_draft_selection_records(selection_payload, to_plain(decisions), list(prospects.values()), picks),
        **rookie_payload,
    }


def apply_draft_selection_to_save(save_path: str | Path, selection_id: str, date: str = CANONICAL_START_DATE, sign_rookie: bool = False) -> dict[str, Any]:
    path = Path(save_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            save = json.load(handle)
    else:
        save = {"version": "save_transaction_ledger_v1", "pending_draft_selections": [], "transaction_logs": []}
    selection = next((item for item in save.get("pending_draft_selections", []) if item.get("id") == selection_id or item.get("selection", {}).get("id") == selection_id), None)
    if not selection:
        return {"status": "not_found", "selection_id": selection_id, "save": str(path), "notes": "No pending draft selection with this id exists in the save ledger."}
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
    save["pending_draft_selections"] = [item for item in save.get("pending_draft_selections", []) if (item.get("id") or item.get("selection", {}).get("id")) != selection_id]
    with path.open("w", encoding="utf-8") as handle:
        json.dump(save, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return {
        "status": "applied",
        "save": str(path),
        "draft_rights": to_plain(rights),
        "rookie_contract": to_plain(contract),
        "incoming_rookie": onboarding,
        "transaction_log": to_plain(log),
    }


def simulate_generated_draft(canonical: dict[str, Any], year: str, seed: int, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or default_draft_model_config()
    generated = generate_draft_class_records(year, seed=seed, config=config)
    prospects = [to_plain(prospect) for prospect in generated["draft_prospects"]]
    traits = to_plain(generated["draft_prospect_traits"])
    order_payload = generate_draft_order(canonical, year, seed=seed, config=config)
    available = {prospect["id"] for prospect in prospects}
    prospects_by_id = {prospect["id"]: prospect for prospect in prospects}
    team_board_cache = {
        team["id"]: rank_generated_prospects_for_team(canonical, team["id"], prospects)
        for team in canonical.get("teams", [])
    }
    bpa_order = sorted(prospects, key=generated_bpa_grade, reverse=True)
    selections: list[DraftSelection] = []
    decisions: list[DraftPickDecision] = []
    for pick in order_payload["draft_order"]:
        team = team_by_id(canonical, pick["current_owner_team_id"])
        candidates = [prospects_by_id[prospect_id] for prospect_id in available]
        if not candidates:
            break
        ranked = [prospect for prospect in team_board_cache.get(team["id"], bpa_order) if prospect["id"] in available]
        chosen = choose_generated_with_draft_chaos(ranked, int(pick["overall_pick"]), team["id"], seed)
        bpa = next((prospect for prospect in bpa_order if prospect["id"] in available), candidates[0])
        decision = DraftPickDecision(
            id=stable_id("draft_pick_decision", pick["id"], team["id"], chosen["id"], seed),
            pick_id=pick["id"],
            team_id=team["id"],
            prospect_id=chosen["id"],
            decision="select",
            bpa_rank=1,
            team_board_rank=1,
            grade_gap_to_bpa=round(generated_bpa_grade(bpa) - generated_bpa_grade(chosen), 3),
            reasons=generated_pick_reasons(canonical, team["id"], chosen, bpa),
            source_ids=["src_draft_model_config_v1"],
            notes=f"{team['abbrev']} generated draft decision v1 from deterministic board, team fit, and rookie-contract value.",
        )
        selection = DraftSelection(
            id=stable_id("draft_selection", pick["id"], chosen["id"], seed),
            pick_id=pick["id"],
            team_id=team["id"],
            prospect_id=chosen["id"],
            draft_year=year,
            overall_pick=int(pick["overall_pick"]),
            status="selected",
            decision_id=decision.id,
            source_ids=["src_draft_model_config_v1"],
            notes="Simulated generated draft selection using generated lottery/order, prospect class, and team board logic.",
        )
        selections.append(selection)
        decisions.append(decision)
        available.remove(chosen["id"])
    selection_payload = to_plain(selections)
    rookie_payload = draft_onboarding_records(canonical, selection_payload, prospects, order_payload["draft_order"], config)
    return {
        "year": year,
        "seed": seed,
        **to_plain(generated),
        "draft_order": order_payload["draft_order"],
        "lottery": order_payload["lottery"],
        "selection_count": len(selections),
        "selections": selection_payload,
        "decisions": to_plain(decisions),
        "pending_draft_selections": pending_draft_selection_records(selection_payload, to_plain(decisions), prospects, order_payload["draft_order"]),
        **rookie_payload,
        "notes": "Generated future draft with lottery/order scaffold, selections, rookie rights, and rookie contract projections.",
    }


def choose_entry_with_draft_chaos(
    canonical: dict[str, Any],
    entries: list[dict[str, Any]],
    overall_pick: int,
    team_id: str,
    seed: int,
    prospects: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ranked = sorted(entries, key=lambda item: item["board_rank"])
    prospects = prospects or {}
    staff = scouting_staff_score(canonical, team_id)
    confidence = float(staff.get("confidence") or 0.55)
    top_grade = draft_selection_score(canonical, ranked[0], prospects.get(ranked[0]["prospect_id"], {}), team_id, overall_pick, seed, confidence) if ranked else 0.0
    if overall_pick <= 5:
        tier_gap = 10.0 + (1.0 - confidence) * 6.0
        window = 10
        temperature = 4.8
    elif overall_pick <= 14:
        tier_gap = 18.0 + (1.0 - confidence) * 8.5
        window = 22
        temperature = 8.5
    elif overall_pick <= 30:
        tier_gap = 30.0 + (1.0 - confidence) * 10.0
        window = 38
        temperature = 12.0
    else:
        tier_gap = 44.0 + (1.0 - confidence) * 12.0
        window = 55
        temperature = 16.0
    pool = [
        item for item in ranked[: min(window, len(ranked))]
        if top_grade - draft_selection_score(canonical, item, prospects.get(item["prospect_id"], {}), team_id, overall_pick, seed, confidence) <= tier_gap
    ] or ranked[: min(3, len(ranked))]
    elite_pool = [
        item for item in pool
        if prospect_priority_tier(prospects.get(item["prospect_id"], {})) == 1
    ]
    if overall_pick <= 3 and elite_pool:
        pool = elite_pool
    elif overall_pick <= 5 and elite_pool and not any(prospect_priority_tier(prospects.get(item["prospect_id"], {})) > 1 for item in pool[:2]):
        pool = elite_pool + [item for item in pool if item not in elite_pool][:2]
    rng = random.Random(f"{seed}:{team_id}:{overall_pick}:draft_chaos")
    scored = [
        (draft_selection_score(canonical, item, prospects.get(item["prospect_id"], {}), team_id, overall_pick, seed, confidence), item)
        for item in pool
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    pool = [item for _, item in scored]
    top_grade = scored[0][0] if scored else top_grade
    second_gap = top_grade - scored[1][0] if len(scored) > 1 else 99.0
    if overall_pick <= 3 and second_gap >= 9.0 and rng.random() < 0.58:
        return pool[0]
    weights = []
    for idx, item in enumerate(pool):
        score = draft_selection_score(canonical, item, prospects.get(item["prospect_id"], {}), team_id, overall_pick, seed, confidence)
        grade_weight = math.exp((score - top_grade) / max(temperature, 0.5))
        rank_drag = max(1.0, idx + 1) ** (0.025 if overall_pick <= 14 else 0.01)
        swing = rng.uniform(0.82, 1.18) if overall_pick <= 5 else rng.uniform(0.55, 1.55)
        weights.append(max(0.02, grade_weight * swing / rank_drag))
    return weighted_choice(pool, weights, rng)


def draft_selection_score(
    canonical: dict[str, Any],
    entry: dict[str, Any],
    prospect: dict[str, Any],
    team_id: str,
    overall_pick: int,
    seed: int,
    confidence: float,
) -> float:
    state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == team_id), {})
    phase = state.get("phase", "balanced")
    base = float(entry.get("risk_adjusted_grade") or entry.get("bpa_grade") or 0.0)
    current = float(prospect.get("current_ability") or 50.0)
    ceiling = float(prospect.get("ceiling") or prospect.get("potential") or 60.0)
    potential = float(prospect.get("potential") or ceiling)
    fit = float(entry.get("fit_grade") or 50.0)
    timeline = 0.0
    if phase in {"rebuilding", "developing"}:
        timeline += (ceiling - current) * 0.13 + max(0.0, potential - 72.0) * 0.08
    elif phase in {"contending", "contending_with_future_upside"}:
        timeline += max(0.0, current - 54.0) * 0.18 + max(0.0, fit - 56.0) * 0.06
    bad_fit = max(0.0, 44.0 - fit) * (0.28 if overall_pick <= 14 else 0.18)
    public_tier_bonus = {1: 4.0, 2: 1.6}.get(prospect_priority_tier(prospect), 0.0)
    rng = random.Random(f"{seed}:{team_id}:{overall_pick}:{entry.get('prospect_id')}:scout_pick")
    if overall_pick <= 5:
        chaos = 5.8
    elif overall_pick <= 14:
        chaos = 12.0
    elif overall_pick <= 30:
        chaos = 18.0
    else:
        chaos = 24.0
    uncertainty = rng.uniform(-1.0, 1.0) * (1.15 - confidence * 0.45) * chaos
    return base + timeline + public_tier_bonus + uncertainty - bad_fit


def prospect_priority_tier(prospect: dict[str, Any]) -> int:
    name = normalize_name(prospect.get("name") or "")
    if name in {"aj dybantsa", "darryn peterson", "cameron boozer"}:
        return 1
    if name in {"caleb wilson", "nate acuff", "jj mccain"}:
        return 2
    rank = int(prospect.get("rank") or 99)
    return 2 if rank <= 6 else 3


def choose_generated_with_draft_chaos(ranked: list[dict[str, Any]], overall_pick: int, team_id: str, seed: int) -> dict[str, Any]:
    top_grade = generated_bpa_grade(ranked[0]) if ranked else 0.0
    if overall_pick <= 5:
        tier_gap = 10.0
        window = 10
        temperature = 4.8
    elif overall_pick <= 14:
        tier_gap = 18.0
        window = 22
        temperature = 8.5
    elif overall_pick <= 30:
        tier_gap = 30.0
        window = 38
        temperature = 12.0
    else:
        tier_gap = 44.0
        window = 55
        temperature = 16.0
    pool = [
        prospect for prospect in ranked[: min(window, len(ranked))]
        if top_grade - generated_bpa_grade(prospect) <= tier_gap
    ] or ranked[: min(3, len(ranked))]
    rng = random.Random(f"{seed}:{team_id}:{overall_pick}:generated_draft_chaos")
    second_gap = top_grade - generated_bpa_grade(pool[1]) if len(pool) > 1 else 99.0
    if overall_pick <= 3 and second_gap >= 9.0 and rng.random() < 0.54:
        return pool[0]
    weights = []
    for idx, prospect in enumerate(pool):
        score = generated_bpa_grade(prospect)
        grade_weight = math.exp((score - top_grade) / max(temperature, 0.5))
        rank_drag = max(1.0, idx + 1) ** (0.025 if overall_pick <= 14 else 0.01)
        swing = rng.uniform(0.82, 1.18) if overall_pick <= 5 else rng.uniform(0.55, 1.55)
        weights.append(max(0.02, grade_weight * swing / rank_drag))
    return weighted_choice(pool, weights, rng)


def weighted_choice(items: list[Any], weights: list[float], rng: random.Random) -> Any:
    total = sum(weights) or 1.0
    draw = rng.random() * total
    running = 0.0
    for item, weight in zip(items, weights, strict=False):
        running += weight
        if draw <= running:
            return item
    return items[-1]


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
        "age": prospect.get("age"),
        "height_inches": prospect.get("height_inches"),
        "weight_lbs": prospect.get("weight_lbs"),
        "archetype": prospect.get("archetype"),
        "potential": prospect.get("potential"),
        "current_ability": prospect.get("current_ability"),
        "rights_status": "signed_rookie_contract" if signed else "exclusive_unsigned_rights",
        "roster_status": "signed_rookie" if signed else "draft_rights_unsigned",
        "contract_id": contract.id,
        "source_ids": ["src_draft_model_config_v1"],
        "notes": "Save-state rookie onboarding stub. Full player-trait conversion and roster-slot mutation can build from this record.",
    }


def rookie_player_record(onboarding: dict[str, Any], prospect: dict[str, Any], team: dict[str, Any], contract: RookieContractProjection) -> dict[str, Any]:
    overall = int(onboarding.get("overall_pick") or 60)
    ability = float(prospect.get("current_ability") or 45.0)
    potential = float(prospect.get("potential") or 55.0)
    slot_bonus = max(0, 31 - overall) * 0.38 if overall <= 30 else max(0, 45 - overall) * 0.08
    readiness = max(0.0, ability - 43.0) * 0.48 + max(0.0, potential - 64.0) * 0.08
    minutes = clamp(4.0 + readiness + slot_bonus, 2.0, 29.0)
    if overall <= 5:
        minutes = max(minutes, 22.0)
    elif overall <= 10:
        minutes = max(minutes, 17.0)
    elif overall <= 20:
        minutes = max(minutes, 11.0)
    priority = "core_rotation" if overall <= 8 and ability >= 55 else "development_priority" if overall <= 20 or potential >= 72 else "rookie_depth"
    return {
        "id": stable_id("rookie_player", onboarding.get("draft_year"), team.get("id"), onboarding.get("name")),
        "name": onboarding.get("name"),
        "normalized_name": normalize_name(onboarding.get("name")),
        "slug": stable_id("", onboarding.get("name")).strip("_"),
        "team_id": team.get("id"),
        "team_abbrev": team.get("abbrev"),
        "position": primary_position_label(prospect.get("position")),
        "position_detail": prospect.get("position"),
        "age": prospect.get("age") or 20.0,
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
    }


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
    prospect_values = {trait.get("trait_key"): float(trait.get("value") or 50.0) for trait in (draft_traits or []) if trait.get("trait_key")}
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
    values = nba_trait_values_from_prospect(prospect_values, current, potential, str(player.get("position") or ""), archetype)
    return [
        {
            "id": stable_id("generated_trait", player["id"], trait_key),
            "player_id": player["id"],
            "trait_key": trait_key,
            "label": NBA_TRAIT_LABELS[trait_key],
            "value": round(clamp(value, 25, 95), 2),
            "confidence": 0.48,
            "source_kind": "draft_model_conversion",
            "source_ids": ["src_draft_model_config_v1"],
            "last_verified": CANONICAL_START_DATE,
            "notes": "Converted from draft prospect trait model when rookie was signed into save state.",
            "components": {
                "prospect_current_ability": round(current, 2),
                "prospect_potential": round(potential, 2),
                "prospect_archetype": archetype,
            },
        }
        for trait_key, value in sorted(values.items())
    ]


def nba_trait_values_from_prospect(values: dict[str, float], current: float, potential: float, position: str, archetype: str) -> dict[str, float]:
    def v(key: str, default: float = 50.0) -> float:
        return float(values.get(key, default))

    def blend(items: list[tuple[float, float]]) -> float:
        total = sum(weight for _, weight in items) or 1.0
        return sum(value * weight for value, weight in items) / total

    pos = position.upper()
    guard = "PG" in pos or "SG" in pos
    big = "PF" in pos or "C" in pos
    ability_anchor = current * 0.55 + potential * 0.22 + 11.5
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
    if archetype in {"lead_creator", "scoring_wing"}:
        output["shot_versatility"] += 3.0
        output["handle_pressure"] += 2.0
    if archetype == "rim_protecting_big":
        output["rim_deterrence"] += 5.0
        output["offensive_rebounding"] += 2.0
    if archetype == "movement_shooter":
        output["release_speed"] += 4.0
        output["shooting_range"] += 3.0
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
            estimated_potential = noisy_range(prospect.potential, noise * 1.15, rng)
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
    reports_by_key = {(report.team_id, report.prospect_id): report for report in reports}
    entries: list[DraftBoardEntry] = []
    for team in canonical.get("teams", []):
        team_entries = []
        for prospect in prospects:
            report = reports_by_key[(team["id"], prospect.id)]
            fit = prospect_team_fit(canonical, team["id"], prospect)
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


def draft_pick_decision(canonical: dict[str, Any], team: dict[str, Any], pick: dict[str, Any], prospect: dict[str, Any], seed: int = 1, config: dict[str, Any] | None = None) -> DraftPickDecision:
    config = config or default_draft_model_config()
    entries = [entry for entry in canonical["draft_board_entries"] if entry["team_id"] == team["id"] and entry["draft_year"] == str(pick.get("season") or "2026")]
    prospects = {p["id"]: p for p in canonical["draft_prospects"]}
    by_prospect = {entry["prospect_id"]: entry for entry in entries}
    entry = by_prospect[prospect["id"]]
    bpa_entry = max(entries, key=lambda item: item["bpa_grade"])
    grade_gap = float(bpa_entry["bpa_grade"]) - float(entry["bpa_grade"])
    reasons = []
    decision = "select"
    if entry["prospect_id"] == bpa_entry["prospect_id"]:
        reasons.append("best_player_available")
    elif grade_gap <= float(config["bpa_gap_threshold"]):
        reasons.append("same_tier_fit_or_need")
    elif float(entry["fit_grade"]) - float(bpa_entry["fit_grade"]) >= float(config["need_override_threshold"]):
        reasons.append("overwhelming_team_fit_need")
    else:
        decision = "recommend_bpa_instead"
        reasons.append("bpa_gap_too_large")
    if float(entry["cap_value"]) >= 62:
        reasons.append("rookie_contract_depth_value")
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team["id"])
    if state["phase"] in {"rebuilding", "developing"} and prospect.get("ceiling", 0) >= prospect.get("potential", 0) + 5:
        reasons.append("upside_matches_timeline")
    if state["phase"] in {"contending", "contending_with_future_upside"} and prospect.get("current_ability", 0) >= 58:
        reasons.append("near_term_rotation_path")
    return DraftPickDecision(
        id=stable_id("draft_pick_decision", pick["id"], team["id"], prospect["id"], seed),
        pick_id=pick["id"],
        team_id=team["id"],
        prospect_id=prospect["id"],
        decision=decision,
        bpa_rank=int(bpa_entry["board_rank"]),
        team_board_rank=int(entry["board_rank"]),
        grade_gap_to_bpa=round(grade_gap, 3),
        reasons=sorted(dict.fromkeys(reasons)),
        source_ids=["src_draft_model_config_v1"],
        notes=f"{team['abbrev']} draft decision v1: BPA first, with fit/need/cap value breaking close tiers.",
    )


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


def generated_trait_values(prospect: DraftProspect, rng: random.Random) -> dict[str, float]:
    base = {key: clamp(prospect.current_ability + rng.gauss(0, 8), 25, 94) for key in DRAFT_TRAITS}
    inferred = infer_trait_values(prospect.position, prospect.archetype, {}, prospect.height_inches)
    return {key: round((base[key] + inferred[key]) / 2, 2) for key in DRAFT_TRAITS}


def development_curve(age: float | None, class_year: str | None, archetype: str) -> str:
    age = float(age or 20.0)
    if age <= 19.2:
        return "long_upside_curve"
    if class_year in {"Senior", "Sr.", "International"} or age >= 22.5:
        return "early_readiness_limited_upside"
    if archetype in {"lead_creator", "rim_protecting_big", "scoring_wing"}:
        return "high_variance_star_curve"
    return "standard_development_curve"


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


def generated_prospect_name(rng: random.Random, rank: int) -> str:
    first = [
        "Malik", "Jalen", "Cameron", "Darius", "Noah", "Elijah", "Isaiah", "Milan", "Andre", "Kobe",
        "Tariq", "Nolan", "Mateo", "Jonas", "Kellan", "Amari", "Dante", "Emil", "Tobias", "Micah",
        "Quentin", "Luca", "Rafael", "Jabari", "Devin", "Kyrie", "Oscar", "Elias", "Myles", "Zaire",
        "Brandon", "Simeon", "Julian", "Kai", "Terrell", "Xavier", "Omar", "Adrian", "Makai", "Tomas",
    ]
    last = [
        "Reed", "Brooks", "Carter", "Holland", "Bennett", "Okafor", "Murray", "Silva", "Hayes", "Ndiaye",
        "Wallace", "Porter", "Daniels", "Ilic", "Freeman", "Vargas", "Bishop", "Mathis", "Gaines", "Lawson",
        "Cross", "Santos", "Balde", "Moreau", "Hawkins", "Whitaker", "Morrison", "Diallo", "Petrovic", "Sato",
        "Ellis", "Kowalski", "Mensah", "Harrison", "Navarro", "Griffin", "Stone", "Camara", "Blackwell", "Rhodes",
        "Mendez", "Laurent", "Robinson", "Foster", "Klein", "Turner", "Boateng", "Hart", "Walters", "Sullivan",
        "Kimani", "Montgomery", "Hughes", "Bamba", "Carlson", "Rojas", "Ibrahim", "Vaughn", "Parker", "Bates",
        "Grant", "Okoro", "Hendrix", "Adebayo", "Baker", "Lang", "Shepard", "Morales", "Washington", "Keita",
    ]
    return f"{rng.choice(first)} {rng.choice(last)}"


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


def generated_source_team(rng: random.Random) -> str:
    return rng.choice(["Duke", "Kentucky", "Kansas", "Arizona", "G League", "France", "Serbia", "Michigan", "Alabama", "Houston", "UConn", "Overtime Elite"])


def generated_class_year(age: float) -> str:
    if age <= 19.4:
        return "Freshman"
    if age <= 20.5:
        return "Sophomore"
    if age <= 21.7:
        return "Junior"
    return "Senior"


def generated_height(position: str, rng: random.Random) -> float:
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


def prospect_team_fit(canonical: dict[str, Any], team_id: str, prospect: DraftProspect | dict[str, Any]) -> float:
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
    if state["phase"] in {"rebuilding", "developing"}:
        fit += max(0.0, float(prospect["ceiling"]) - 76) * 0.35
    if state["phase"] in {"contending", "contending_with_future_upside"}:
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
    value = float(prospect["rookie_contract_value"])
    if state["salary_posture"].startswith("expensive"):
        value += 12
    if state["salary_posture"].startswith("above_cap"):
        value += 7
    if state["phase"] in {"contending", "contending_with_future_upside"} and float(prospect["current_ability"]) >= 56:
        value += 5
    return clamp(value, 1, 99)


def board_entry_payload(entry: dict[str, Any], prospect: dict[str, Any]) -> dict[str, Any]:
    return {
        **entry,
        "prospect": {
            "prospect_id": prospect["id"],
            "name": prospect["name"],
            "rank": prospect["rank"],
            "position": prospect["position"],
            "source_team": prospect.get("source_team"),
            "archetype": prospect["archetype"],
            "current_ability": prospect["current_ability"],
            "potential": prospect["potential"],
            "ceiling": prospect["ceiling"],
            "volatility": prospect["volatility"],
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


def generated_board_report(canonical: dict[str, Any], team_query: str, year: str, seed: int, limit: int | None, config: dict[str, Any] | None) -> dict[str, Any]:
    team = resolve_team(canonical, team_query)
    generated = generate_draft_class_records(str(year), seed=seed, config=config)
    prospects = [to_plain(p) for p in generated["draft_prospects"]]
    entries = []
    for prospect in prospects:
        fit = prospect_team_fit(canonical, team["id"], prospect)
        cap = prospect_cap_value(canonical, team["id"], prospect)
        grade = float(prospect["potential"]) * 0.65 + float(prospect["current_ability"]) * 0.25 + fit * 0.06 + cap * 0.04
        entries.append({"prospect": prospect, "risk_adjusted_grade": round(grade, 2), "fit_grade": round(fit, 2), "cap_value": round(cap, 2)})
    entries = sorted(entries, key=lambda item: item["risk_adjusted_grade"], reverse=True)[: limit or len(entries)]
    return {"team": team, "year": str(year), "entry_count": len(entries), "entries": entries}


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


def rank_generated_prospects_for_team(canonical: dict[str, Any], team_id: str, prospects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def score(prospect: dict[str, Any]) -> float:
        fit = prospect_team_fit(canonical, team_id, prospect)
        cap = prospect_cap_value(canonical, team_id, prospect)
        return generated_bpa_grade(prospect) * 0.78 + fit * 0.13 + cap * 0.09 - float(prospect.get("volatility") or 0) * 0.04

    return sorted(prospects, key=lambda prospect: (score(prospect), generated_bpa_grade(prospect), -int(prospect.get("rank") or 99)), reverse=True)


def generated_bpa_grade(prospect: dict[str, Any]) -> float:
    return (
        float(prospect.get("potential") or 0) * 0.56
        + float(prospect.get("current_ability") or 0) * 0.28
        + float(prospect.get("floor") or 0) * 0.1
        + float(prospect.get("ceiling") or 0) * 0.06
        - float(prospect.get("volatility") or 0) * 0.05
    )


def generated_pick_reasons(canonical: dict[str, Any], team_id: str, prospect: dict[str, Any], bpa: dict[str, Any]) -> list[str]:
    reasons = ["best_player_available"] if prospect["id"] == bpa["id"] else ["same_tier_fit_or_need"]
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team_id)
    if float(prospect.get("rookie_contract_value") or 0) >= 62:
        reasons.append("rookie_contract_depth_value")
    if state["phase"] in {"rebuilding", "developing"} and float(prospect.get("ceiling") or 0) >= 82:
        reasons.append("upside_matches_timeline")
    if state["phase"] in {"contending", "contending_with_future_upside"} and float(prospect.get("current_ability") or 0) >= 57:
        reasons.append("cheap_near_term_depth")
    return sorted(dict.fromkeys(reasons))


def season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"
