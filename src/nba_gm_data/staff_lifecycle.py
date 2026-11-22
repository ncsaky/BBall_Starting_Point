"""Save-owned career progression for employed and available gameplay staff."""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from copy import deepcopy
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from .utils import clamp, normalize_name


COORDINATOR_ROLES = {"offensive_coordinator", "defensive_coordinator"}
EXPERIENCE_SKILLS = {"rotation_management", "scheme_balance", "player_usage", "matchup_adjustment"}
BIO_SOURCES = {
    "src_espn_coaches_2026",
    "src_nba_official_team_pages_2026",
    "src_bref_team_pages_2026",
}


def staff_person_id(staff: dict[str, Any]) -> str:
    return staff.get("market_source_id") or staff["id"]


@lru_cache(maxsize=12)
def _staff_source_profiles(path: str, source_id: str) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = list(data.get("coaches", []))
    for team in data.get("teams", []):
        coach = team.get("coach")
        if isinstance(coach, dict):
            rows.append(coach)
        # NBA.com supplies staff names in its coaching groups, with no
        # numeric biography fields in the current captures.
    return {
        normalize_name(row.get("coach") or row["name"]): {**row, "source_id": source_id}
        for row in rows
        if row.get("coach") or row.get("name")
    }


def staff_bio_evidence(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profiles = {}
    for source in canonical.get("sources", []):
        if source.get("id") not in BIO_SOURCES or not source.get("path"):
            continue
        for name, row in _staff_source_profiles(source["path"], source["id"]).items():
            traits = profiles.setdefault(name, {})
            for field in ("age", "experience", "record"):
                value = row.get(field)
                if value is not None and str(value) not in {"", "--"}:
                    traits[field] = value
                    traits[f"{field}_source"] = row["source_id"]
    for staff in canonical.get("staff_profiles", []):
        if not staff.get("name"):
            continue
        traits = profiles.setdefault(normalize_name(staff["name"]), {})
        for field in ("age", "experience", "record"):
            value = (staff.get("traits") or {}).get(field)
            if value is not None and str(value) not in {"", "--"}:
                traits[field] = value
                traits[f"{field}_source"] = next(iter(staff.get("source_ids") or []), None)
    return profiles


def initialize_staff_bio(
    staff: dict[str, Any],
    seed: int,
    grade: float,
    evidence: dict[str, Any] | None = None,
    *,
    young: bool = False,
) -> None:
    staff.setdefault("reputation", round(grade, 2))
    staff.setdefault("rating_change_log", [])
    if "age" in staff and "years_experience" in staff:
        return
    evidence = evidence or {}
    rng = random.Random(f"{seed}:{staff_person_id(staff)}:staff_bio")
    role = staff["slot"]
    if young:
        age_center, age_low, age_high, entry_age = 34, 28, 42, 24
    elif role == "head_coach":
        age_center, age_low, age_high, entry_age = 50, 36, 66, 28
    elif role in COORDINATOR_ROLES:
        age_center, age_low, age_high, entry_age = 43, 30, 63, 25
    else:
        age_center, age_low, age_high, entry_age = 44, 30, 64, 25
    reported_age = str(evidence.get("age", "")).strip()
    reported_experience = str(evidence.get("experience", "")).strip()
    age = int(reported_age) if reported_age.isdecimal() else round(clamp(rng.gauss(age_center, 6), age_low, age_high))
    experience = (
        int(reported_experience) if reported_experience.isdecimal()
        else max(1, age - entry_age - rng.randint(0, 6))
    )
    if not reported_age.isdecimal():
        age = max(age, 25 + experience)
    staff.setdefault("age", age)
    staff.setdefault("years_experience", experience)
    for field, value in (("age", reported_age), ("experience", reported_experience)):
        staff.setdefault("bio_sources", {})[field] = (
            (evidence.get(f"{field}_source") or "staff_profile") if value.isdecimal() else "seeded_estimate"
        )
    record = str(evidence.get("record") or "").strip()
    if re.fullmatch(r"\d+-\d+", record):
        staff["source_record"] = record
        staff["bio_sources"]["record"] = evidence.get("record_source") or "staff_profile"


def retirement_probability(age: int, status: str) -> float:
    if age >= 80:
        return 1.0
    base = max(0, age - 55) ** 2 / 625
    if age >= 58 and status == "fired":
        return min(1.0, base + (age - 57) * 0.018)
    return base


def _age_ratings(
    staff: dict[str, Any], season: str, rng: random.Random, employed: bool,
) -> dict[str, Any]:
    age = staff["age"]
    experience = staff["years_experience"]
    age_drift = 0.085 * max(0, 46 - age) - 0.095 * max(0, age - 54)
    entry = {
        "season": season,
        "age": age + 1,
        "years_experience": experience + int(employed),
        "slot": staff["slot"],
        "rating_deltas": {},
    }
    for group in ("skill_traits", "personality_traits"):
        traits = staff.get(group) or {}
        deltas = entry["rating_deltas"][group] = {}
        for key in sorted(traits):
            current = float(traits[key])
            drift = age_drift if group == "skill_traits" else age_drift * 0.45
            if employed and key in EXPERIENCE_SKILLS:
                drift += 0.9 / (1 + experience / 12)
            step = drift + rng.uniform(-0.7, 0.7)
            room = 96 - current if step > 0 else current - 20
            # Ease toward the endpoints so small gains/losses retain separation.
            step *= clamp(room / 5, 0.0, 1.0)
            traits[key] = round(current + step, 2)
            deltas[key] = round(traits[key] - current, 2)
    staff["age"] = entry["age"]
    staff["years_experience"] = entry["years_experience"]
    staff.setdefault("rating_change_log", []).append(entry)
    return entry


def staff_retires_after_season(staff: dict[str, Any], seed: int, season: str) -> bool:
    # The summer bench review needs to count an upcoming retirement as one departure.
    # Reuse the career stream and its rating draws so the lifecycle keeps the same outcomes.
    next_age = int(staff.get("age") or 0) + 1
    chance = retirement_probability(next_age, staff.get("market_status", ""))
    if chance <= 0:
        return False
    rng = random.Random(f"{seed}:{season}:{staff_person_id(staff)}:staff_lifecycle")
    _age_ratings(deepcopy(staff), season, rng, employed=False)
    return rng.random() < chance


def staff_win_expectations(strategic_states: list[dict[str, Any]]) -> dict[str, float]:
    ceilings = {row["team_id"]: float(row.get("contention_ceiling") or 55) for row in strategic_states}
    league_mean = sum(ceilings.values()) / max(1, len(ceilings))
    return {
        team_id: round(clamp(0.5 + (ceiling - league_mean) / 170, 0.25, 0.75), 4)
        for team_id, ceiling in ceilings.items()
    }


def _season_results(
    completed: dict[str, Any], expectations: dict[str, float],
) -> dict[str, dict[str, Any]]:
    playoff = completed.get("playoff_state") or {}
    series_wins = Counter(row["winner_team_id"] for row in playoff.get("series", []) if row.get("winner_team_id"))
    results = {}
    for team_id, record in (completed.get("team_records") or {}).items():
        wins = int(record.get("wins") or 0)
        games = wins + int(record.get("losses") or 0)
        if games:
            results[team_id] = {
                "wins": wins,
                "games": games,
                "expected_wins": round(expectations.get(team_id, 0.5) * games, 2),
                "playoff_series_wins": series_wins[team_id],
            }
    return results


def _regular_season_service(staff: dict[str, Any], season: str, left_on: str | None) -> tuple[float, bool]:
    start_year = int(season[:4])
    opener, finale = date(start_year, 10, 20), date(start_year + 1, 4, 15)
    hired_on = staff.get("staff_hired_on")
    start = max(opener, date.fromisoformat(hired_on)) if hired_on else opener
    end = min(finale, date.fromisoformat(left_on)) if left_on else finale
    tenure = max(0.0, (end - start).days / (finale - opener).days)
    return tenure, end == finale


def _review_results(
    staff: dict[str, Any], result: dict[str, Any], entry: dict[str, Any],
    team_id: str, tenure: float, playoff_credit: bool, previous_security: float,
) -> None:
    surprise = (result["wins"] - result["expected_wins"]) * 82 / result["games"]
    playoff_bonus = 1.75 * result["playoff_series_wins"] if playoff_credit else 0
    role_weight = 1.0 if staff["slot"] == "head_coach" else 0.55
    performance = clamp(0.58 * surprise + playoff_bonus, -15, 15) * tenure * role_weight
    old_rep = staff["reputation"]
    staff["reputation"] = round(clamp(old_rep + performance, 0, 100), 2)
    entry["results"] = {
        "team_id": team_id, **result, "tenure_share": round(tenure, 3),
        "playoff_credit": playoff_credit,
    }
    entry["reputation_delta"] = round(staff["reputation"] - old_rep, 2)
    if staff.get("team_id"):
        security_target = 60 + (staff["reputation"] - 60) * 0.48 + performance * 1.65
        staff["job_security"] = round(clamp(0.35 * previous_security + 0.65 * security_target, 15, 95), 2)
        if staff.get("market_status") == "contract_expired_pending_user_decision":
            staff["job_security"] = min(staff["job_security"], 45)
        entry["job_security"] = staff["job_security"]


def roll_staff_lifecycle(
    save: dict[str, Any],
    canonical: dict[str, Any] | None,
    next_roster: dict[str, Any] | None,
    ending_slots: list[dict[str, Any]],
    seed: int,
) -> None:
    from .staff import (
        STAFF_SLOTS, generated_staff_candidates, interim_staff, is_interim_staff,
        resolve_matching_staff_retention_window, staff_grade,
    )

    meta = save.get("meta") or {}
    new_season = meta.get("season")
    seed = int(meta.get("seed", seed))
    employed = save.get("staff_slots", [])
    evidence = staff_bio_evidence(canonical or {})
    for staff in employed:
        initialize_staff_bio(
            staff, seed, staff_grade(staff), evidence.get(normalize_name(staff.get("name"))),
            young=is_interim_staff(staff),
        )
    history = save.get("season_history") or []
    if not (new_season and history):
        return
    completed = history[-1]
    season = completed.get("season")
    if not season or season >= new_season or save.get("staff_lifecycle_season") == new_season:
        return

    preseason = save.setdefault("staff_preseason_expectations", {})
    expectations = preseason.setdefault(season, staff_win_expectations((canonical or {}).get("team_strategic_states", [])))
    results = _season_results(completed, expectations)
    if next_roster and next_roster.get("players"):
        from .schema import to_plain
        from .transactions import build_team_strategic_states

        preseason[new_season] = staff_win_expectations(to_plain(build_team_strategic_states(next_roster, _final_needs_only=True)))

    incumbents = {staff_person_id(staff): staff for staff in ending_slots if not is_interim_staff(staff)}
    former = save.get("former_staff", [])
    retired = save.setdefault("retired_staff", [])
    visited = {staff_person_id(staff) for staff in retired}
    pool = save.get("staff_market_pool")
    if pool is None:
        pool = [staff for role in STAFF_SLOTS for staff in generated_staff_candidates(seed, role)]
    survivors = []
    today = (save.get("state") or {}).get("current_date") or f"{new_season[:4]}-10-01"
    for group in (employed, former, pool):
        kept = []
        for staff in group:
            person_id = staff_person_id(staff)
            if person_id in visited:
                continue
            visited.add(person_id)
            initialize_staff_bio(staff, seed, staff_grade(staff), evidence.get(normalize_name(staff.get("name"))))
            if is_interim_staff(staff):
                kept.append(staff)
                continue
            incumbent = incumbents.get(person_id)
            team_id = incumbent.get("team_id") if incumbent else staff.get("last_team_id")
            left_on = staff.get("staff_left_on") if not incumbent else None
            if not incumbent and (not left_on or left_on < f"{season[:4]}-10-20"):
                team_id = None
            tenure, playoff_credit = _regular_season_service(staff, season, left_on) if team_id else (0.0, False)
            rng = random.Random(f"{seed}:{season}:{person_id}:staff_lifecycle")
            entry = _age_ratings(staff, season, rng, employed=tenure >= 0.5)
            if tenure and team_id in results:
                previous_security = (incumbent or staff).get("job_security", 60)
                _review_results(staff, results[team_id], entry, team_id, tenure, playoff_credit, previous_security)
            if not staff.get("team_id") and team_id:
                staff.setdefault("last_team_id", team_id)
            if rng.random() >= retirement_probability(staff["age"], staff.get("market_status", "")):
                kept.append(staff)
                continue
            if staff.get("team_id"):
                team_id, slot = staff["team_id"], staff["slot"]
                replacement = interim_staff(team_id, slot, today, previous_id=staff["id"], previous_name=staff["name"], seed=seed)
                kept.append(replacement)
                resolve_matching_staff_retention_window(save, team_id, slot, "resolved_retired")
            last_team = (incumbent or staff).get("team_id") or staff.get("last_team_id")
            staff.update(market_status="retired", retired_in=new_season, last_team_id=last_team, team_id=None)
            retired.append(staff)
        survivors.append(kept)
    save["staff_slots"], save["former_staff"], pool = survivors
    refill_staff_pool(pool, save["former_staff"], seed, new_season)
    save["staff_market_pool"] = pool
    save["staff_lifecycle_season"] = new_season
    # New interims and the new market intake get gender-matched faces not already held in the league.
    from .faces import ensure_save_staff_faces
    ensure_save_staff_faces(save)


def refill_staff_pool(pool: list[dict[str, Any]], former: list[dict[str, Any]], seed: int, season: str) -> None:
    from .staff import STAFF_SLOTS, generated_staff_candidates, staff_grade

    available = pool + former
    eligible = [
        staff for staff in available
        if staff["slot"] in COORDINATOR_ROLES
        and staff["years_experience"] >= 8
        and 34 <= staff["age"] <= 59
        and staff_grade(staff) >= 70
    ]
    if eligible:
        def promotion_score(staff: dict[str, Any]) -> float:
            rng = random.Random(f"{seed}:{season}:{staff_person_id(staff)}:promotion")
            return staff_grade(staff) + rng.uniform(-3, 3)

        staff = max(eligible, key=lambda staff: (promotion_score(staff), staff_person_id(staff)))
        skills = staff["skill_traits"]
        management = skills["player_usage"] if staff["slot"] == "offensive_coordinator" else skills["matchup_adjustment"]
        staff.update(
            promoted_from=staff["slot"],
            promotion_season=season,
            slot="head_coach",
            role_preference="head_coach",
            archetype="former coordinator",
            style_tags=["former_coordinator", "head_coach"],
            skill_traits={
                "rotation_management": management,
                "locker_room": staff["personality_traits"]["communication"],
                "scheme_balance": round(sum(skills.values()) / len(skills), 2),
            },
        )

    for role in STAFF_SLOTS:
        same_role = [staff for staff in available if staff["slot"] == role]
        floor = 20 if role == "head_coach" else 16
        intake = max(2, floor - len(same_role))
        grades = [66, 55] + [61, 50, 71, 46] * ((intake + 1) // 4)
        # Keep a strong option on the market without making every class elite.
        strong_grade = 88 if role == "head_coach" else 82
        if max((staff_grade(staff) for staff in same_role), default=0) < strong_grade - 4:
            grades[0] = strong_grade
        pool.extend(generated_staff_candidates(seed, role, season=season, grades=grades[:intake]))
