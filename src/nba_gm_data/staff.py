from __future__ import annotations

import random
from copy import deepcopy
from typing import Any

from .schema import TransactionLog, to_plain
from .utils import clamp, stable_id


STAFF_SLOTS = [
    "head_coach",
    "offensive_coordinator",
    "defensive_coordinator",
    "development_lead",
    "scouting_lead",
    "performance_lead",
]

ROLE_LABELS = {
    "head_coach": "Head Coach",
    "offensive_coordinator": "Offensive Coordinator",
    "defensive_coordinator": "Defensive Coordinator",
    "development_lead": "Development Lead",
    "scouting_lead": "Scouting Lead",
    "performance_lead": "Performance Lead",
}

ROLE_EFFECTS = {
    "head_coach": "Sets rotation trust, locker-room stability, playoff preparation, and how strongly the staff identity reaches the floor.",
    "offensive_coordinator": "Improves shot quality, spacing design, creator usage, and late-clock offensive structure.",
    "defensive_coordinator": "Improves coverage discipline, matchup counters, point-of-attack help, and opponent targeting resistance.",
    "development_lead": "Raises monthly trait growth odds, especially for young players with minutes and clear roles.",
    "scouting_lead": "Narrows draft scouting fog and helps identify upside, role fit, and prospect risk.",
    "performance_lead": "Modestly reduces injury odds, fatigue accumulation, recovery time, and return-from-injury rust.",
}

FIRST_NAMES = [
    "Andre",
    "Caleb",
    "Damon",
    "Elliot",
    "Gabe",
    "Isaiah",
    "Julian",
    "Marcus",
    "Nolan",
    "Quentin",
    "Reid",
    "Theo",
]

LAST_NAMES = [
    "Bennett",
    "Coleman",
    "Ellis",
    "Foster",
    "Hayes",
    "Lang",
    "Mercer",
    "Porter",
    "Reed",
    "Sullivan",
    "Turner",
    "Wallace",
]

SLOT_ARCHETYPES = {
    "head_coach": ["culture setter", "rotation tactician", "scheme balancer"],
    "offensive_coordinator": ["spacing architect", "creator optimizer", "shot-quality designer"],
    "defensive_coordinator": ["coverage technician", "matchup planner", "discipline teacher"],
    "development_lead": ["prospect builder", "mechanics teacher", "confidence developer"],
    "scouting_lead": ["upside detector", "risk modeler", "global talent scout"],
    "performance_lead": ["availability planner", "conditioning specialist", "recovery coordinator"],
}

SLOT_SKILLS = {
    "head_coach": ["rotation_management", "locker_room", "scheme_balance"],
    "offensive_coordinator": ["shot_quality", "spacing_design", "player_usage"],
    "defensive_coordinator": ["coverage_design", "matchup_adjustment", "discipline"],
    "development_lead": ["skill_development", "prospect_patience", "feedback_clarity"],
    "scouting_lead": ["talent_eval", "risk_modeling", "international_coverage"],
    "performance_lead": ["injury_prevention", "conditioning", "recovery_planning"],
}

HEAD_COACH_REPUTATION_GRADES = {
    "steve kerr": 93.0,
    "erik spoelstra": 92.0,
    "rick carlisle": 88.0,
    "tyronn lue": 86.0,
    "joe mazzulla": 85.0,
    "mark daigneault": 85.0,
    "ime udoka": 83.0,
    "mike brown": 80.0,
    "j.b. bickerstaff": 78.0,
    "jb bickerstaff": 78.0,
    "chris finch": 78.0,
    "nick nurse": 77.0,
    "jason kidd": 76.0,
    "doc rivers": 74.0,
    "kenny atkinson": 73.0,
    "quin snyder": 72.0,
    "jamahl mosley": 71.0,
    "charles lee": 69.0,
    "david adelman": 68.0,
    "chauncey billups": 66.0,
    "jj redick": 65.0,
    "billy donovan": 65.0,
    "willie green": 63.0,
    "darko rajakovic": 62.0,
    "darko rajaković": 62.0,
    "will hardy": 61.0,
    "mitch johnson": 60.0,
    "tuomas iisalo": 59.0,
    "doug christie": 58.0,
    "brian keefe": 57.0,
    "jordi fernandez": 56.0,
    "jordi fernández": 56.0,
    "jordan ott": 55.0,
}


def initialize_save_staff_slots(canonical: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for slot in sorted(canonical.get("gameplay_staff_slots", []), key=lambda item: (item["team_id"], item["slot"])):
        record = deepcopy(slot)
        score = staff_grade(record)
        record.update(
            {
                "contract": staff_contract(record["slot"], score, seed, record["id"]),
                "morale": 64.0,
                "job_security": round(clamp(58 + (score - 60) * 0.35, 35, 88), 2),
                "market_status": "employed",
                "role_preference": record["slot"],
                "original_team_id": record["team_id"],
            }
        )
        slots.append(record)
    return slots


def staff_contract(slot: str, score: float, seed: int, key: str) -> dict[str, Any]:
    rng = random.Random(f"{seed}:{key}:staff_contract")
    base = {
        "head_coach": 8.0,
        "offensive_coordinator": 3.4,
        "defensive_coordinator": 3.4,
        "development_lead": 2.4,
        "scouting_lead": 2.2,
        "performance_lead": 2.2,
    }.get(slot, 2.0)
    annual = base + max(0.0, score - 60.0) * 0.12 + rng.uniform(-0.18, 0.18)
    return {
        "annual_salary_millions": round(max(0.8, annual), 2),
        "years_remaining": 2 + int(rng.random() > 0.58),
        "guarantee_level": "standard",
    }


def staff_market_report(canonical: dict[str, Any], save: dict[str, Any], slot: str | None = None, limit: int | None = None) -> dict[str, Any]:
    candidates = generate_staff_market(canonical, save, slot=slot)
    if limit is not None:
        candidates = candidates[: max(0, limit)]
    return {
        "slot": slot,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "notes": "Deterministic fictional staff market. Candidates are gameplay staff, not real NBA staff claims.",
    }


def generate_staff_market(canonical: dict[str, Any], save: dict[str, Any], slot: str | None = None) -> list[dict[str, Any]]:
    seed = int(save.get("meta", {}).get("seed") or 1)
    slots = [slot] if slot else STAFF_SLOTS
    candidates: list[dict[str, Any]] = []
    unavailable_sources = active_staff_market_sources(save)
    for former in save.get("former_staff", []):
        preferred_slot = former.get("role_preference") or former.get("slot")
        if slot and preferred_slot != slot:
            continue
        if former.get("id") in unavailable_sources:
            continue
        candidate = deepcopy(former)
        candidate["team_id"] = None
        candidate["slot"] = preferred_slot
        candidate["role_preference"] = preferred_slot
        candidate["status"] = "fictional_gameplay_staff_market"
        candidate["market_status"] = "free_agent"
        candidate["former_staff_id"] = former.get("id")
        candidate["id"] = stable_id("staff_market_former", candidate.get("name"), preferred_slot, former.get("id"))
        candidate["market_source_id"] = former.get("id") or candidate["id"]
        score = staff_grade(candidate)
        ask = staff_contract(preferred_slot, score, seed, candidate["id"])
        candidate["asking_salary_millions"] = round(float(ask["annual_salary_millions"]) * 0.95, 2)
        candidate["asking_years"] = 2 if score < 68 else 3
        candidate["grade"] = round(score, 2)
        candidates.append(candidate)
    for staff_slot in slots:
        if staff_slot not in STAFF_SLOTS:
            continue
        desired_grades = generated_market_grade_ladder(staff_slot)
        for rank, desired_grade in enumerate(desired_grades, start=1):
            rng = random.Random(f"{seed}:staff_market:{staff_slot}:{rank}")
            first = FIRST_NAMES[int(rng.random() * len(FIRST_NAMES)) % len(FIRST_NAMES)]
            last = LAST_NAMES[int(rng.random() * len(LAST_NAMES)) % len(LAST_NAMES)]
            archetype = SLOT_ARCHETYPES[staff_slot][rank % len(SLOT_ARCHETYPES[staff_slot])]
            base = 60.0 + (desired_grade - 60.0) / 1.75 + rng.gauss(0, 0.8)
            traits = {
                key: round(clamp(base + rng.gauss(0, 3.2), 20, 92), 2)
                for key in SLOT_SKILLS[staff_slot]
            }
            personality = {
                "adaptability": round(clamp(base + rng.gauss(0, 3.6), 20, 92), 2),
                "communication": round(clamp(base + rng.gauss(0, 3.6), 20, 92), 2),
                "ambition": round(clamp(base + rng.gauss(0, 4.4), 20, 94), 2),
            }
            candidate = {
                "id": stable_id("staff_market", staff_slot, rank, first, last),
                "team_id": None,
                "slot": staff_slot,
                "name": f"{first} {last}",
                "archetype": archetype,
                "style_tags": [archetype.replace(" ", "_"), staff_slot],
                "skill_traits": traits,
                "personality_traits": personality,
                "status": "fictional_gameplay_staff_market",
                "confidence": 0.5,
                "source_ids": ["src_gameplay_staff_seed_v1"],
                "notes": "Generated free-agent gameplay staff candidate for staff-management V1.",
                "market_status": "free_agent",
                "role_preference": staff_slot,
            }
            candidate["market_source_id"] = candidate["id"]
            if candidate["market_source_id"] in unavailable_sources:
                continue
            score = staff_grade(candidate)
            ask = staff_contract(staff_slot, score, seed, candidate["id"])
            ask["years_remaining"] = 0
            candidate["asking_salary_millions"] = round(ask["annual_salary_millions"] * 1.08, 2)
            candidate["asking_years"] = 3 if staff_slot == "head_coach" or score >= 68 else 2
            candidate["grade"] = round(score, 2)
            candidates.append(candidate)
    return sorted(
        candidates,
        key=lambda item: (
            -float(item.get("grade") or 0),
            float(item.get("asking_salary_millions") or 0),
            candidate_rank(item),
            item.get("slot") or "",
            item.get("name") or "",
        ),
    )


def staff_team_report(canonical: dict[str, Any], save: dict[str, Any], team_query: str) -> dict[str, Any]:
    team = resolve_team(canonical, team_query)
    slots = sorted([slot for slot in save.get("staff_slots", []) if slot.get("team_id") == team["id"]], key=lambda item: item["slot"])
    real_context = sorted([staff for staff in canonical.get("staff_profiles", []) if staff["team_id"] == team["id"]], key=lambda item: item["role"])
    spent = round(sum(staff_budget_salary(slot) for slot in slots), 2)
    budget = staff_budget_for_team(canonical, team["id"])
    return {
        "team": team,
        "real_staff_context": real_context,
        "budget": {
            "annual_spend_millions": spent,
            "annual_budget_millions": budget,
            "available_millions": round(budget - spent, 2),
            "spend_pct": round(spent / budget * 100.0, 1) if budget else 0.0,
        },
        "gameplay_staff_slots": [
            {**slot, "grade": round(staff_grade(slot), 2), "effect_summary": staff_effect_summary(slot), "effect_rows": staff_effect_rows(slot)}
            for slot in slots
        ],
        "notes": "Real staff context is flavor/source context. Gameplay staff slots are the mutable save-state staff who drive systems.",
    }


def staff_budget_for_team(canonical: dict[str, Any], team_id: str) -> float:
    strategic = next((state for state in canonical.get("team_strategic_states", []) if state.get("team_id") == team_id), {})
    pressure = float(strategic.get("pressure") or 55.0)
    ceiling = float(strategic.get("contention_ceiling") or 55.0)
    deterministic_market = ((sum(ord(char) for char in team_id) % 17) - 8) * 0.55
    phase = str(strategic.get("phase") or "")
    phase_bonus = 2.4 if "contending" in phase else -1.8 if phase in {"rebuilding", "developing"} else 0.0
    budget = 33.0 + (pressure - 50.0) * 0.07 + (ceiling - 55.0) * 0.08 + deterministic_market + phase_bonus
    return round(clamp(budget, 27.0, 47.0), 2)


def evaluate_staff_hire(canonical: dict[str, Any], save: dict[str, Any], staff_id: str, team_query: str, slot: str) -> dict[str, Any]:
    team = resolve_team(canonical, team_query)
    candidate = staff_candidate_by_id(canonical, save, staff_id, slot)
    current = current_staff_slot(save, team["id"], slot)
    front_office = next((profile for profile in canonical.get("front_office_profiles", []) if profile["team_id"] == team["id"]), {})
    strategic = next((state for state in canonical.get("team_strategic_states", []) if state["team_id"] == team["id"]), {})
    current_grade = staff_grade(current) if current else 48.0
    candidate_grade = staff_grade(candidate)
    upgrade = candidate_grade - current_grade
    pressure = float(front_office.get("owner_pressure") or strategic.get("pressure") or 50.0)
    discipline = float(front_office.get("financial_discipline") or 55.0)
    fit = slot_fit_bonus(slot, strategic)
    score = upgrade * 1.15 + fit + (pressure - 50.0) * 0.05 - max(0.0, candidate_grade - 72.0) * (discipline - 50.0) * 0.01
    decision = "strong_target" if score >= 8 else "target" if score >= 2 else "monitor" if score >= -4 else "pass"
    reasons = []
    if upgrade > 4:
        reasons.append("clear_staff_upgrade")
    if fit > 1:
        reasons.append("team_context_fit")
    if pressure > 65:
        reasons.append("owner_pressure_pushes_action")
    if discipline > 65 and candidate.get("asking_salary_millions", 0) > role_salary_anchor(slot) * 1.4:
        reasons.append("financial_discipline_caution")
    if not reasons:
        reasons.append("marginal_staff_market_case")
    return {
        "team": team,
        "slot": slot,
        "candidate": candidate,
        "current_staff": current,
        "current_grade": round(current_grade, 2),
        "candidate_grade": round(candidate_grade, 2),
        "upgrade": round(upgrade, 2),
        "fit_bonus": round(fit, 2),
        "decision_score": round(score, 2),
        "decision": decision,
        "reasons": reasons,
        "notes": "Staff hire evaluation uses role grade, current staff quality, team strategic context, pressure, and financial discipline.",
    }


def negotiate_staff_hire(
    canonical: dict[str, Any],
    save: dict[str, Any],
    staff_id: str,
    team_query: str,
    slot: str,
    seed: int = 1,
    offer_salary_millions: float | None = None,
    offer_years: int | None = None,
) -> dict[str, Any]:
    evaluation = evaluate_staff_hire(canonical, save, staff_id, team_query, slot)
    team = evaluation["team"]
    candidate = evaluation["candidate"]
    rng = random.Random(f"{seed}:{staff_id}:{team['id']}:{slot}:staff_negotiation")
    asking_salary = float(candidate.get("asking_salary_millions") or role_salary_anchor(slot))
    asking_years = int(candidate.get("asking_years") or 2)
    score = float(evaluation["decision_score"])
    max_offer = max_staff_offer_millions(canonical, save, team["id"], slot)
    raw_offer = float(offer_salary_millions) if offer_salary_millions is not None else asking_salary * clamp(0.9 + score * 0.012 + rng.uniform(-0.025, 0.025), 0.82, 1.12)
    team_offer = min(raw_offer, max_offer)
    offer_years = int(offer_years) if offer_years is not None else (asking_years if score >= 0 else max(1, asking_years - 1))
    min_salary = asking_salary * (0.96 if candidate.get("market_status") == "free_agent" else 1.0)
    budget = staff_budget_snapshot(canonical, save, team["id"], slot, team_offer)
    budget_ok = budget["available_after_offer_millions"] >= -0.01
    accepted = team_offer >= min_salary and score >= -1.5 and budget_ok
    negotiation = {
        "id": stable_id("staff_negotiation", save.get("state", {}).get("current_date"), team["id"], slot, staff_id, seed),
        "date": save.get("state", {}).get("current_date"),
        "staff_id": staff_id,
        "team_id": team["id"],
        "slot": slot,
        "seed": seed,
        "staff_ask": {"annual_salary_millions": round(asking_salary, 2), "years": asking_years},
        "team_offer": {"annual_salary_millions": round(team_offer, 2), "years": offer_years},
        "budget": budget,
        "budget_legal": budget_ok,
        "offer_capped_by_budget": round(raw_offer, 2) > round(team_offer, 2),
        "max_offer_millions": round(max_offer, 2),
        "accepted": accepted,
        "decision": "accept" if accepted else ("reject_budget" if not budget_ok else "reject"),
        "candidate": candidate,
        "evaluation": evaluation,
        "status": "accepted_pending_hire" if accepted else ("budget_blocked" if not budget_ok else "rejected"),
        "notes": "Deterministic staff negotiation. Candidate weighs salary, years, role fit, and job quality. Team offers are capped by remaining staff budget for this role.",
    }
    save.setdefault("pending_staff_negotiations", [])
    save["pending_staff_negotiations"] = [
        item for item in save["pending_staff_negotiations"] if item.get("id") != negotiation["id"]
    ]
    save["pending_staff_negotiations"].append(negotiation)
    return negotiation


def hire_staff_from_save(save: dict[str, Any], negotiation_id: str) -> dict[str, Any]:
    pending = save.get("pending_staff_negotiations", [])
    negotiation = next((item for item in pending if item.get("id") == negotiation_id), None)
    if not negotiation:
        return {"status": "not_found", "negotiation_id": negotiation_id, "notes": "No pending staff negotiation with this id exists in the save."}
    if not negotiation.get("accepted"):
        return {"status": "not_applied", "negotiation_id": negotiation_id, "notes": "Rejected staff negotiations cannot be hired."}
    if negotiation.get("budget_legal") is False:
        return {"status": "not_applied", "negotiation_id": negotiation_id, "notes": "This staff deal exceeded the staff budget."}
    team_id = negotiation["team_id"]
    slot_name = negotiation["slot"]
    candidate = deepcopy(negotiation["candidate"])
    current = current_staff_slot(save, team_id, slot_name)
    if current:
        former = deepcopy(current)
        if not is_interim_staff(former):
            former["market_status"] = "fired"
            former["team_id"] = None
            save.setdefault("former_staff", []).append(former)
    candidate.update(
        {
            "market_source_id": candidate.get("market_source_id") or candidate.get("former_staff_id") or candidate.get("id"),
            "id": stable_id("save_staff", team_id, slot_name, candidate["id"]),
            "team_id": team_id,
            "slot": slot_name,
            "status": "fictional_gameplay_staff_hired",
            "market_status": "employed",
            "contract": {
                "annual_salary_millions": negotiation["team_offer"]["annual_salary_millions"],
                "years_remaining": negotiation["team_offer"]["years"],
                "guarantee_level": "standard",
            },
            "morale": 68.0,
            "job_security": 62.0,
        }
    )
    save["staff_slots"] = [
        slot for slot in save.get("staff_slots", []) if not (slot.get("team_id") == team_id and slot.get("slot") == slot_name)
    ]
    save["staff_slots"].append(candidate)
    save["staff_slots"].sort(key=lambda item: (item.get("team_id") or "", item.get("slot") or "", item.get("id") or ""))
    source_id = candidate.get("market_source_id")
    if source_id:
        save["former_staff"] = [
            staff for staff in save.get("former_staff", [])
            if staff.get("id") != source_id
        ]
    save["pending_staff_negotiations"] = [item for item in pending if item.get("id") != negotiation_id]
    log = staff_transaction_log(save, "staff_hire", negotiation_id, [team_id], {"staff": candidate, "previous_staff": current}, [negotiation])
    save.setdefault("transaction_logs", []).append(log)
    team_abbrev = str(team_id).replace("team_", "").upper()
    headline = f"{team_abbrev} hires {candidate['name']} as {ROLE_LABELS.get(slot_name, slot_name)}."
    append_news_item_once(save, news_item(save, "staff_hire", headline))
    queue_press_event_if_user_involved(save, "staff_hire", headline, [team_id])
    return {"status": "applied", "transaction_log": log, "staff": candidate, "previous_staff": current}


def fire_staff_from_save(save: dict[str, Any], team_id: str, slot: str) -> dict[str, Any]:
    current = current_staff_slot(save, team_id, slot)
    if not current:
        return {"status": "not_found", "team_id": team_id, "slot": slot}
    fired = deepcopy(current)
    if not is_interim_staff(fired):
        fired["market_status"] = "fired"
        fired["team_id"] = None
        save.setdefault("former_staff", []).append(fired)
    interim = interim_staff(
        team_id,
        slot,
        save.get("state", {}).get("current_date") or "unknown",
        len(save.get("transaction_logs", [])),
        fired.get("id"),
        fired.get("name"),
    )
    save["staff_slots"] = [
        staff for staff in save.get("staff_slots", []) if not (staff.get("team_id") == team_id and staff.get("slot") == slot)
    ]
    save["staff_slots"].append(interim)
    save["staff_slots"].sort(key=lambda item: (item.get("team_id") or "", item.get("slot") or "", item.get("id") or ""))
    log = staff_transaction_log(save, "staff_fire", stable_id("staff_fire", team_id, slot, save.get("state", {}).get("current_date")), [team_id], {"fired_staff": fired, "interim_staff": interim}, [])
    save.setdefault("transaction_logs", []).append(log)
    append_news_item_once(save, news_item(save, "staff_fire", f"{fired['name']} fired from {ROLE_LABELS.get(slot, slot)}."))
    queue_press_event_if_user_involved(save, "staff_fire", f"{fired['name']} fired from {ROLE_LABELS.get(slot, slot)}.", [team_id])
    return {"status": "applied", "transaction_log": log, "fired_staff": fired, "interim_staff": interim}


def queue_press_event_if_user_involved(save: dict[str, Any], kind: str, headline: str, team_ids: list[str | None]) -> None:
    from .save import queue_aggregated_press_event

    date = save.get("state", {}).get("current_date") or "unknown"
    queue_aggregated_press_event(save, kind, headline, team_ids, date)


def interim_staff(
    team_id: str,
    slot: str,
    date: str,
    nonce: int = 0,
    previous_id: str | None = None,
    previous_name: str | None = None,
) -> dict[str, Any]:
    keys = SLOT_SKILLS.get(slot, ["general_management"])
    name = ""
    rng = random.Random(f"{team_id}:{slot}:{date}:{nonce}:{previous_id}:interim_staff")
    for attempt in range(8):
        first = FIRST_NAMES[int(rng.random() * len(FIRST_NAMES)) % len(FIRST_NAMES)]
        last = LAST_NAMES[int(rng.random() * len(LAST_NAMES)) % len(LAST_NAMES)]
        name = f"{first} {last}"
        if name != previous_name:
            break
    return {
        "id": stable_id("interim_staff", team_id, slot, date, nonce, previous_id),
        "team_id": team_id,
        "slot": slot,
        "name": name,
        "archetype": "interim replacement",
        "style_tags": ["interim", slot],
        "skill_traits": {key: 50.0 for key in keys},
        "personality_traits": {"adaptability": 50.0, "communication": 50.0, "ambition": 45.0},
        "status": "interim_staff_vacancy",
        "confidence": 0.3,
        "source_ids": ["src_gameplay_staff_seed_v1"],
        "notes": f"Temporary save-state interim {ROLE_LABELS.get(slot, slot)} after a firing.",
        "contract": {"annual_salary_millions": role_salary_anchor(slot) * 0.35, "years_remaining": 1, "guarantee_level": "interim"},
        "morale": 50.0,
        "job_security": 25.0,
        "market_status": "employed",
        "role_preference": slot,
    }


def current_staff_slot(save: dict[str, Any], team_id: str, slot: str) -> dict[str, Any] | None:
    return next((staff for staff in save.get("staff_slots", []) if staff.get("team_id") == team_id and staff.get("slot") == slot), None)


def staff_budget_snapshot(canonical: dict[str, Any], save: dict[str, Any], team_id: str, slot: str, offered_salary_millions: float) -> dict[str, Any]:
    current = current_staff_slot(save, team_id, slot)
    current_salary = staff_budget_salary(current)
    spent = sum(
        staff_budget_salary(staff)
        for staff in save.get("staff_slots", [])
        if staff.get("team_id") == team_id
    )
    budget = staff_budget_for_team(canonical, team_id)
    max_offer = max(0.0, budget - (spent - current_salary))
    projected = spent - current_salary + float(offered_salary_millions)
    current_is_interim = is_interim_staff(current)
    return {
        "annual_budget_millions": round(budget, 2),
        "current_spend_millions": round(spent, 2),
        "replaced_salary_millions": round(current_salary, 2),
        "max_offer_millions": round(max_offer, 2),
        "projected_spend_millions": round(projected, 2),
        "available_after_offer_millions": round(budget - projected, 2),
        "current_slot_is_interim": current_is_interim,
        "interim_replacement_credit_millions": round(current_salary if current_is_interim else 0.0, 2),
        "notes": "The current staff salary in this exact role is credited back before testing the new offer. Interim salaries still count against other open roles.",
    }


def max_staff_offer_millions(canonical: dict[str, Any], save: dict[str, Any], team_id: str, slot: str) -> float:
    return float(staff_budget_snapshot(canonical, save, team_id, slot, 0.0)["max_offer_millions"])


def staff_budget_salary(staff: dict[str, Any] | None) -> float:
    if not staff:
        return 0.0
    return float((staff.get("contract") or {}).get("annual_salary_millions") or 0.0)


def is_interim_staff(staff: dict[str, Any] | None) -> bool:
    if not staff:
        return False
    return staff.get("status") == "interim_staff_vacancy" or (staff.get("contract") or {}).get("guarantee_level") == "interim"


def staff_candidate_by_id(canonical: dict[str, Any], save: dict[str, Any], staff_id: str, slot: str | None = None) -> dict[str, Any]:
    active_candidate_ids = {
        staff.get("market_source_id") or staff.get("id")
        for staff in save.get("staff_slots", [])
        if staff.get("market_status") == "employed" and staff.get("team_id")
    }
    for collection in [save.get("former_staff", []), generate_staff_market(canonical, save, slot=slot)]:
        for candidate in collection:
            if candidate.get("id") == staff_id:
                if (candidate.get("market_source_id") or candidate.get("former_staff_id") or candidate.get("id")) in active_candidate_ids:
                    raise ValueError(f"Staff candidate {staff_id!r} is already employed.")
                return deepcopy(candidate)
    raise ValueError(f"No staff candidate found with id {staff_id!r}")


def active_staff_market_sources(save: dict[str, Any]) -> set[str]:
    sources = set()
    for staff in save.get("staff_slots", []):
        if staff.get("market_status") != "employed" or not staff.get("team_id"):
            continue
        source = staff.get("market_source_id")
        if source:
            sources.add(source)
    return sources


def staff_grade(staff: dict[str, Any] | None) -> float:
    if not staff:
        return 0.0
    values = [float(value) for value in (staff.get("skill_traits") or {}).values()]
    if not values:
        return 50.0
    personality = staff.get("personality_traits") or {}
    modifier = (float(personality.get("communication") or 50) - 50) * 0.08 + (float(personality.get("adaptability") or 50) - 50) * 0.05
    raw = sum(values) / len(values) + modifier
    return clamp(60 + (raw - 60) * 1.75, 1, 99)


def generated_market_grade_ladder(slot: str) -> list[float]:
    if slot == "head_coach":
        return [76, 72, 69, 67, 65, 63, 61, 59, 57, 55, 53, 51, 49, 47, 45, 43, 41, 39, 37, 35]
    if slot in {"offensive_coordinator", "defensive_coordinator"}:
        return [74, 70, 68, 66, 64, 62, 60, 58, 56, 54, 52, 50, 48, 46, 44, 42]
    return [72, 69, 67, 65, 63, 61, 59, 57, 55, 53, 51, 49, 47, 45, 43, 41]


def apply_head_coach_reputation(slot: dict[str, Any], coach_name: str) -> None:
    target = HEAD_COACH_REPUTATION_GRADES.get(normalize_name(coach_name))
    if target is None or slot.get("slot") != "head_coach":
        return
    current = staff_grade(slot)
    if abs(current - target) < 0.75 and slot.get("coach_reputation_source") == "bleacher_report_2026_soft_rank":
        return
    skill_target = clamp(60.0 + (target - 60.0) / 1.75, 25.0, 92.0)
    traits = slot.setdefault("skill_traits", {})
    weights = {
        "rotation_management": 0.98,
        "locker_room": 1.03,
        "scheme_balance": 1.0,
    }
    for key, weight in weights.items():
        old = float(traits.get(key) or skill_target)
        traits[key] = round(clamp(old * 0.25 + skill_target * weight * 0.75, 20.0, 96.0), 2)
    personality = slot.setdefault("personality_traits", {})
    personality["communication"] = round(clamp(float(personality.get("communication") or skill_target) * 0.35 + skill_target * 0.65, 20, 96), 2)
    personality["adaptability"] = round(clamp(float(personality.get("adaptability") or skill_target) * 0.45 + skill_target * 0.55, 20, 96), 2)
    slot["reputation_grade_target"] = target
    slot["coach_reputation_source"] = "bleacher_report_2026_soft_rank"
    slot["notes"] = (
        f"{slot.get('notes', '')} Head-coach gameplay grade softly calibrated from user-supplied 2026 coach ranking; "
        "ranking is treated as reputation input, not hard truth."
    ).strip()


def normalize_name(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace(".", "").split())


def staff_effect_summary(staff: dict[str, Any]) -> dict[str, Any]:
    grade = staff_grade(staff)
    slot = staff.get("slot")
    if slot == "performance_lead":
        return {
            "injury_prevention": round((grade - 60) * 0.004, 3),
            "conditioning": round((float((staff.get("skill_traits") or {}).get("conditioning") or grade) - 60) * 0.004, 3),
            "recovery": round((float((staff.get("skill_traits") or {}).get("recovery_planning") or grade) - 60) * 0.004, 3),
        }
    if slot == "development_lead":
        return {"development_multiplier_delta": round((grade - 60) * 0.006, 3)}
    if slot == "scouting_lead":
        return {"scouting_noise_delta": round(-(grade - 60) * 0.08, 3)}
    if slot in {"head_coach", "offensive_coordinator", "defensive_coordinator"}:
        return {"coach_star_equivalent": round(clamp(grade / 20, 0, 5), 2)}
    return {"grade": round(grade, 2)}


def staff_effect_rows(staff: dict[str, Any]) -> list[dict[str, Any]]:
    grade = staff_grade(staff)
    slot = staff.get("slot")
    traits = staff.get("skill_traits") or {}
    if slot == "head_coach":
        return [
            effect_row("Coach stars", grade, "Overall staff quality translated to the 0-5 coach star scale.", stars=grade / 20),
            effect_row("Rotation trust", traits.get("rotation_management", grade), "How well this coach balances depth, stars, and GM minute requests."),
            effect_row("Locker room", traits.get("locker_room", grade), "Morale stability, buy-in, and crisis response."),
            effect_row("Scheme balance", traits.get("scheme_balance", grade), "How strongly the whole staff identity reaches the floor."),
        ]
    if slot == "offensive_coordinator":
        return [
            effect_row("Coach stars", grade, "Offensive staff quality translated to a 0-5 impact shorthand.", stars=grade / 20),
            effect_row("Shot quality", traits.get("shot_quality", grade), "Creates cleaner looks and better late-clock possessions."),
            effect_row("Spacing design", traits.get("spacing_design", grade), "Helps shooters bend help decisions and open driving lanes."),
            effect_row("Creator usage", traits.get("player_usage", grade), "Gets high-usage players the right touches without flattening the offense."),
        ]
    if slot == "defensive_coordinator":
        return [
            effect_row("Coach stars", grade, "Defensive staff quality translated to a 0-5 impact shorthand.", stars=grade / 20),
            effect_row("Coverage design", traits.get("coverage_design", grade), "Improves coverage discipline and rim/paint problem solving."),
            effect_row("Matchup counters", traits.get("matchup_adjustment", grade), "Adjusts to opponent strengths and pressure points."),
            effect_row("Discipline", traits.get("discipline", grade), "Reduces blown assignments and repeated targeting."),
        ]
    if slot == "development_lead":
        return [
            effect_row("Growth boost", grade, "Monthly development odds for young and role-changing players."),
            effect_row("Skill work", traits.get("skill_development", grade), "Trait-level growth from training and role clarity."),
            effect_row("Prospect patience", traits.get("prospect_patience", grade), "Helps raw players grow without overreacting to early mistakes."),
            effect_row("Feedback clarity", traits.get("feedback_clarity", grade), "Makes development outcomes less noisy."),
        ]
    if slot == "scouting_lead":
        return [
            effect_row("Scouting accuracy", grade, "Narrows draft fog and improves outlier detection."),
            effect_row("Talent eval", traits.get("talent_eval", grade), "General board quality and prospect ranking signal."),
            effect_row("Risk modeling", traits.get("risk_modeling", grade), "Better odds of catching bust risk and hidden upside."),
            effect_row("Global coverage", traits.get("international_coverage", grade), "Improves nontraditional prospect reads."),
        ]
    if slot == "performance_lead":
        return [
            effect_row("Availability", grade, "Overall health, fatigue, recovery, and return-to-play support."),
            effect_row("Injury prevention", traits.get("injury_prevention", grade), "Modestly lowers injury odds and severity."),
            effect_row("Conditioning", traits.get("conditioning", grade), "Slows fatigue accumulation during heavy workloads."),
            effect_row("Recovery planning", traits.get("recovery_planning", grade), "Shortens recovery and rust windows."),
        ]
    return [effect_row("Staff grade", grade, "General staff quality.")]


def effect_row(label: str, value: Any, description: str, stars: float | None = None) -> dict[str, Any]:
    numeric = clamp(float(value or 0.0), 0, 100)
    return {
        "label": label,
        "value": round(numeric, 2),
        "bar_value": round(numeric, 2),
        "stars": round(clamp(float(stars), 0, 5), 2) if stars is not None else None,
        "description": description,
    }


def staff_role_effect(slot: str) -> str:
    return ROLE_EFFECTS.get(slot, "General staff quality affects save-state team operations.")


def simulate_ai_staff_changes(
    canonical: dict[str, Any],
    save: dict[str, Any],
    from_date: str,
    through_date: str,
    seed: int = 1,
    limit: int = 3,
) -> dict[str, Any]:
    rng = random.Random(f"{seed}:{from_date}:{through_date}:ai_staff_changes")
    teams = sorted(canonical.get("teams", []), key=lambda item: item["abbrev"])
    states = {state.get("team_id"): state for state in canonical.get("team_strategic_states", [])}
    offices = {profile.get("team_id"): profile for profile in canonical.get("front_office_profiles", [])}
    recommendations: list[dict[str, Any]] = []
    reserved_candidate_ids: set[str] = set()
    for team in teams:
        slots = {slot.get("slot"): slot for slot in save.get("staff_slots", []) if slot.get("team_id") == team["id"]}
        record = save.get("team_records", {}).get(team["id"], {})
        state = states.get(team["id"], {})
        office = offices.get(team["id"], {})
        team_pressure = float(state.get("pressure") or office.get("owner_pressure") or 55.0)
        games = int(record.get("wins") or 0) + int(record.get("losses") or 0)
        win_pct = float(record.get("wins") or 0) / max(1, games)
        expected_pct = clamp(0.25 + float(state.get("contention_ceiling") or 55.0) / 170.0, 0.25, 0.72)
        underperforming = games >= 20 and win_pct + 0.12 < expected_pct
        seasonal_review = through_date[5:] in {"02-05", "09-01", "10-01"}
        for slot in STAFF_SLOTS:
            current = slots.get(slot)
            if not current:
                continue
            score, reasons = ai_staff_trigger_score(current, slot, state, team_pressure, underperforming, through_date)
            market_sample = generate_staff_market(canonical, save, slot=slot)[:18]
            if staff_grade(current) <= 68 and any(staff_grade(candidate) >= 82 for candidate in market_sample):
                score += 10.0
                reasons.append("rare_elite_staff_market_candidate")
            if score < conservative_staff_threshold(slot, seasonal_review):
                continue
            max_offer = max_staff_offer_millions(canonical, save, team["id"], slot)
            candidates = []
            for candidate in market_sample:
                if candidate.get("id") in reserved_candidate_ids:
                    continue
                ask = float(candidate.get("asking_salary_millions") or role_salary_anchor(slot))
                upgrade = staff_grade(candidate) - staff_grade(current)
                minimum_upgrade = 7.0 if slot == "head_coach" and not is_interim_staff(current) else 5.0
                if staff_grade(candidate) >= 82 and staff_grade(current) <= 68:
                    minimum_upgrade = min(minimum_upgrade, 3.0)
                if upgrade < minimum_upgrade:
                    continue
                if max_offer and ask > max_offer * 1.08:
                    continue
                candidates.append((upgrade + min(8.0, max_offer - ask) * 0.12, candidate, ask))
            if not candidates:
                continue
            candidates.sort(key=lambda item: (item[0], item[1].get("grade", 0), item[1].get("name", "")), reverse=True)
            _, candidate, ask = candidates[0]
            reserved_candidate_ids.add(candidate["id"])
            recommendations.append(
                {
                    "id": stable_id("ai_staff_rec", through_date, team["id"], slot, candidate["id"]),
                    "team_id": team["id"],
                    "team_abbrev": team["abbrev"],
                    "slot": slot,
                    "role_label": ROLE_LABELS.get(slot, slot),
                    "current_staff": compact_staff(current),
                    "candidate": candidate,
                    "candidate_id": candidate["id"],
                    "current_grade": round(staff_grade(current), 2),
                    "candidate_grade": round(staff_grade(candidate), 2),
                    "upgrade": round(staff_grade(candidate) - staff_grade(current), 2),
                    "trigger_score": round(score + rng.uniform(-1.5, 1.5), 2),
                    "reasons": reasons,
                    "recommended_offer": {
                        "annual_salary_millions": round(min(ask, max_offer), 2),
                        "years": int(candidate.get("asking_years") or 2),
                    },
                    "max_offer_millions": round(max_offer, 2),
                    "notes": "AI staff-change recommendation. Execution is separate and skips user-team automatic hires.",
                }
            )
    recommendations.sort(key=lambda item: (-float(item["trigger_score"]), -float(item["upgrade"]), item["team_abbrev"], item["slot"]))
    recommendations = recommendations[: max(0, limit)]
    return {
        "from_date": from_date,
        "through_date": through_date,
        "seed": seed,
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "notes": "Deterministic AI staff-change recommendations based on pressure, performance, phase, staff grade, contract status, and market fit.",
    }


def compact_staff(staff: dict[str, Any] | None) -> dict[str, Any]:
    if not staff:
        return {"name": "Vacant", "grade": 0.0}
    contract = staff.get("contract") or {}
    return {
        "id": staff.get("id"),
        "name": staff.get("name"),
        "slot": staff.get("slot"),
        "grade": round(staff_grade(staff), 2),
        "salary_millions": round(float(contract.get("annual_salary_millions") or 0), 2),
        "years_remaining": int(contract.get("years_remaining") or 0),
        "status": staff.get("status"),
    }


def ai_staff_trigger_score(
    current: dict[str, Any],
    slot: str,
    state: dict[str, Any],
    pressure: float,
    underperforming: bool,
    through_date: str,
) -> tuple[float, list[str]]:
    grade = staff_grade(current)
    contract = current.get("contract") or {}
    phase = str(state.get("phase") or state.get("timeline") or "")
    reasons: list[str] = []
    score = 0.0
    if is_interim_staff(current):
        score += 32
        reasons.append("interim_placeholder")
    if int(contract.get("years_remaining") or 0) <= 0:
        score += 22
        reasons.append("expired_staff_contract")
    if grade < 56:
        score += (56 - grade) * 0.85 + 8
        reasons.append("staff_grade_below_league_standard")
    if underperforming and slot in {"head_coach", "offensive_coordinator", "defensive_coordinator", "performance_lead"}:
        score += 8 + max(0.0, pressure - 65) * 0.10
        reasons.append("team_underperforming_expectations")
    if pressure >= 76 and slot in {"head_coach", "offensive_coordinator", "defensive_coordinator"}:
        score += 5
        reasons.append("owner_pressure")
    if phase in {"rebuilding", "developing"} and slot in {"development_lead", "scouting_lead"}:
        score += 4
        reasons.append("phase_values_development_and_scouting")
    if phase in {"contending", "contending_with_future_upside"} and slot in {"head_coach", "offensive_coordinator", "defensive_coordinator", "performance_lead"}:
        score += 3
        reasons.append("phase_values_win_now_staff")
    if through_date[5:] in {"02-05", "09-01", "10-01"}:
        score += 3
        reasons.append("calendar_review_point")
    if not reasons:
        reasons.append("soft_staff_market_monitoring")
    return score, reasons


def conservative_staff_threshold(slot: str, seasonal_review: bool) -> float:
    if slot == "head_coach":
        return 34.0 if seasonal_review else 42.0
    return 28.0 if seasonal_review else 36.0


def candidate_rank(candidate: dict[str, Any]) -> int:
    try:
        return int(str(candidate.get("id", "")).split("-")[-3])
    except (ValueError, IndexError):
        return int(round(100 - float(candidate.get("grade") or 0)))


def slot_fit_bonus(slot: str, strategic: dict[str, Any]) -> float:
    needs = " ".join(str(item) for item in strategic.get("needs", []))
    timeline = str(strategic.get("phase") or strategic.get("timeline") or "")
    bonus = 0.0
    if slot == "offensive_coordinator" and any(token in needs for token in ["creation", "shooting", "spacing"]):
        bonus += 2.0
    if slot == "defensive_coordinator" and any(token in needs for token in ["defense", "rim", "poa"]):
        bonus += 2.0
    if slot == "development_lead" and any(token in timeline for token in ["rebuild", "upside", "youth"]):
        bonus += 2.2
    if slot == "scouting_lead" and any(token in timeline for token in ["rebuild", "future"]):
        bonus += 1.8
    if slot == "performance_lead" and any(token in timeline for token in ["contending", "older"]):
        bonus += 1.6
    return bonus


def role_salary_anchor(slot: str) -> float:
    return {
        "head_coach": 8.0,
        "offensive_coordinator": 3.4,
        "defensive_coordinator": 3.4,
        "development_lead": 2.4,
        "scouting_lead": 2.2,
        "performance_lead": 2.2,
    }.get(slot, 2.0)


def resolve_team(canonical: dict[str, Any], query: str) -> dict[str, Any]:
    low = query.strip().lower()
    matches = [team for team in canonical.get("teams", []) if team["abbrev"].lower() == low or team["id"].lower() == low]
    matches = matches or [team for team in canonical.get("teams", []) if low in team["name"].lower()]
    if not matches:
        raise ValueError(f"No team found matching {query!r}")
    return matches[0]


def staff_transaction_log(save: dict[str, Any], transaction_type: str, proposal_id: str, teams: list[str], assets: dict[str, Any], evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    log = TransactionLog(
        id=stable_id("transaction_log", transaction_type, proposal_id, save.get("state", {}).get("current_date")),
        date=save.get("state", {}).get("current_date") or "",
        transaction_type=transaction_type,
        proposal_id=proposal_id,
        status="applied_to_save_ledger",
        teams=teams,
        assets=assets,
        evaluations=evaluations,
        source_ids=["src_gameplay_staff_seed_v1"],
        notes="Staff transaction applied to league_save_v1 only. Canonical preseason data remains immutable.",
    )
    return to_plain(log)


def news_item(save: dict[str, Any], kind: str, headline: str) -> dict[str, Any]:
    date = save.get("state", {}).get("current_date") or ""
    return {
        "id": stable_id("news", kind, date, headline),
        "date": date,
        "kind": kind,
        "headline": headline,
        "status": "unread",
    }


def append_news_item_once(save: dict[str, Any], item: dict[str, Any]) -> None:
    items = save.setdefault("news_items", [])
    marker = (item.get("kind"), item.get("date"), item.get("headline"))
    if marker in {(news.get("kind"), news.get("date"), news.get("headline")) for news in items}:
        return
    items.append(item)
