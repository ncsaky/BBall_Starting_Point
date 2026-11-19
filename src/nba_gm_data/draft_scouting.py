"""What each team's scouts believe about a draft class, month by month, and the league consensus built from them.

Two layers (user decisions, 2026-11-19; docs/agents/tasks/draft-boards-plan.md):
- **Scouts** judge talent only: how good a prospect is now, how much upside he has, how long he needs, his age and
  his risk. They never weigh fit, team needs or whether the team is rebuilding. That is the general manager's job
  (draft.gm_* functions).
- **Consensus** is the league's view: the median of the 30 teams' scouted grades, with the spread of their ranks.

Nothing here is drawn at pick time. Every number is a fixed function of the class, the save seed, the team's
scouting lead and the month, so a team's view changes only when its scouts learn more (monthly through the
season) or when it hires another scouting lead.

How a view is formed:
- The **public view** of a prospect starts at the class's public numbers (the same numbers the board is ranked by)
  and drifts through the season: a quarter of what scouts could not see at first (part of his hidden upside or
  shortfall) plus news nobody could predict. Most of the movement comes early; by June the boards are firm.
- A **team's view** is the public view plus: what a good scouting lead sees that others miss (a share of the gap
  to the truth, larger with better staff and more coverage), the staff's lasting taste (some leads weigh shooting,
  some physical tools, some feel), and a fixed estimation error that shrinks as coverage grows.
- **Coverage** grows through the season, faster for better staffs and for the prospects everyone watches.
Hidden true ratings are never shown: what the user sees is his own team's view, built exactly as the AI's.
"""
from __future__ import annotations

import random
import statistics
from datetime import date
from typing import Any

from .utils import clamp

DRAFT_MONTH = 8
# The scouts' monthly updates: month k (1..8) starts on these dates of the draft season (Nov 1 ... Jun 1).
MONTH_STARTS = ((11, 1), (12, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1))
MONTH_LABELS = ("preseason", "November", "December", "January", "February", "March", "April", "May", "June")

# Season movement of the public view (potential points): a share of the hidden gap (clipped) plus unforeseeable news.
# Sized so the June view misses the truth by about as much as the class-building calibration assumes (the
# talent model's scouting miss, spread 6): 0.75 x 6 and 3.5 combine to about 5.7.
MOVE_INFO = 0.25
MOVE_NOISE = 3.5
GAP_CLIP = 9.0
# A team's estimation error, as a share of its scouting noise (draft.scouting_noise, 3 to 11 points), and how much
# full coverage removes. Current level is easier to see than upside.
POT_NOISE = 1.10
CUR_NOISE = 0.50
TRAIT_NOISE = 0.45
WIDTH_FLOOR = 0.20  # share of the error left at full coverage
WIDTH_SLOPE = 1.30  # extra share per unit of coverage missing (60% coverage: 0.72)
# What a scouting lead sees that the consensus misses: up to this share of the hidden gap, by talent evaluation.
EDGE_MAX = 0.25
# Preseason coverage by public rank: everyone watches the top of the board; the rest is scouted unevenly.
COVERAGE_TOP, COVERAGE_LOTTERY, COVERAGE_FIRST, COVERAGE_REST = 76.0, 66.0, 40.0, 26.0
# Staff taste: lasting weights on skill groups (shooting, physical tools, feel, defense, motor).
TASTE_SCALE = 1.20
TASTE_GROUPS = {
    "shooting": ("shooting",),
    "tools": ("athleticism", "size"),
    "feel": ("feel", "passing"),
    "defense": ("defense", "rim_protection"),
    "motor": ("motor", "rebounding"),
}
TASTE_WORDS = {
    "shooting": "shooting", "tools": "physical tools", "feel": "feel for the game",
    "defense": "defense", "motor": "motor and rebounding",
}
TRAIT_WORDS = {
    "shot_creation": "shot creation", "shooting": "shooting", "rim_pressure": "rim pressure", "passing": "passing",
    "defense": "defense", "rim_protection": "rim protection", "rebounding": "rebounding", "feel": "feel for the game",
    "athleticism": "athleticism", "size": "size", "motor": "motor", "nba_readiness": "NBA readiness",
}
# Scouting-lead archetypes weigh talent differently (still talent only).
ARCHETYPE_WEIGHTS = {
    "upside evaluator": {"potential": 0.62, "current": 0.22, "volatility": 0.04, "medical": 1.0},
    "role-player value hunter": {"potential": 0.51, "current": 0.33, "volatility": 0.05, "medical": 1.0},
    "risk-balanced drafter": {"potential": 0.56, "current": 0.28, "volatility": 0.09, "medical": 1.4},
}
DEFAULT_WEIGHTS = {"potential": 0.56, "current": 0.28, "volatility": 0.05, "medical": 1.0}

_CACHE: dict[tuple, dict[str, Any]] = {}
_CACHE_LIMIT = 24


# ----------------------------------------------------------------------------------------------- calendar


def scouting_month(current_date: Any, draft_year: Any) -> int:
    """0 = preseason view (before November 1 of the draft season), 8 = the final June board."""
    if not current_date:
        return 0
    try:
        today = date.fromisoformat(str(current_date)[:10])
        year = int(draft_year)
    except (TypeError, ValueError):
        return 0
    month = 0
    for index, (m, d) in enumerate(MONTH_STARTS, start=1):
        start = date(year - 1 if m >= 7 else year, m, d)
        if today >= start:
            month = index
    return month


def years_ahead(current_date: Any, draft_year: Any) -> int:
    """0 for the next draft; 1 or more for classes further out (scouts barely watch them yet)."""
    try:
        today = date.fromisoformat(str(current_date)[:10])
        season_end = today.year + 1 if today.month >= 7 else today.year
        return max(0, int(draft_year) - season_end)
    except (TypeError, ValueError):
        return 0


def movement_fraction(month: int) -> float:
    """Share of the season's movement already made: big steps early, small ones near the draft."""
    m = clamp(float(month), 0.0, float(DRAFT_MONTH)) / DRAFT_MONTH
    return 1.0 - (1.0 - m) ** 2


def canonical_month(canonical: dict[str, Any], year: Any) -> tuple[int, int]:
    current = (canonical.get("meta") or {}).get("current_date")
    return scouting_month(current, year), years_ahead(current, year)


# ---------------------------------------------------------------------------------------------- the class


def class_records(canonical: dict[str, Any], year: Any) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]], int]:
    """The class's prospects, their true draft skills (by prospect) and the class seed."""
    from .draft import generated_class_for_context
    from .schema import to_plain

    year = str(year)
    stored = [p for p in canonical.get("draft_prospects") or [] if str(p.get("draft_year")) == year]
    if stored:
        ids = {p["id"] for p in stored}
        traits = [t for t in canonical.get("draft_prospect_traits") or [] if t.get("prospect_id") in ids]
        seed = next((c.get("seed") for c in canonical.get("draft_classes") or [] if str(c.get("season")) == year), None)
        prospects = stored
    else:
        generated = generated_class_for_context(canonical, year)
        prospects = [p if isinstance(p, dict) else to_plain(p) for p in generated["draft_prospects"]]
        traits = [t if isinstance(t, dict) else to_plain(t) for t in generated["draft_prospect_traits"]]
        seed = (generated.get("draft_classes") or [{}])[0].get("seed")
    prospects = _with_latent_tails(canonical, year, prospects, seed)
    by_prospect: dict[str, dict[str, float]] = {}
    for trait in traits:
        by_prospect.setdefault(trait["prospect_id"], {})[trait["trait_key"]] = float(trait["value"])
    return prospects, by_prospect, int(seed if seed is not None else year)


_TAIL_CACHE: dict[tuple[str, int, bool], dict[str, float]] = {}


def _with_latent_tails(canonical: dict[str, Any], year: str, prospects: list[dict[str, Any]], seed: Any) -> list[dict[str, Any]]:
    """Classes stored before the hidden upside tail was recorded (the universe's 2027 class) get it back from a
    regeneration of the same class (same year and seed give the same prospects), so scouts never learn it."""
    priors = [p.get("scouting_prior") or {} for p in prospects]
    if seed is None or not any(priors) or any("latent_tail" in prior for prior in priors):
        return prospects
    from .draft import generate_draft_class_records
    from .schema import to_plain
    from .talent import enabled as talent_enabled

    key = (year, int(seed), talent_enabled(canonical))
    if key not in _TAIL_CACHE:
        regenerated = to_plain(generate_draft_class_records(year, int(seed), talent_model=key[2], real_prospects=True))
        _TAIL_CACHE[key] = {p["id"]: float((p.get("scouting_prior") or {}).get("latent_tail") or 0.0)
                            for p in regenerated["draft_prospects"]}
    tails = _TAIL_CACHE[key]
    return [{**p, "scouting_prior": {**p["scouting_prior"], "latent_tail": tails.get(p["id"], 0.0)}}
            if p.get("scouting_prior") else p for p in prospects]


def public_value(prospect: dict[str, Any], key: str) -> float:
    prior = prospect.get("scouting_prior") or {}
    return float(prior.get(key, prospect.get(key)) or 0.0)


def hidden_gap(prospect: dict[str, Any], reference_potential: float) -> float:
    """What scouting can still learn about a prospect's upside: his true potential minus the reference view,
    without the hidden upside tail (that stays latent until he plays; draft.generated_prospect_upside), clipped."""
    tail = float((prospect.get("scouting_prior") or {}).get("latent_tail") or 0.0)
    return clamp(float(prospect.get("potential") or 0.0) - tail - reference_potential, -GAP_CLIP, GAP_CLIP)


def public_view(prospect: dict[str, Any], month: int, class_seed: int) -> dict[str, float]:
    """The league's public read of a prospect in a given month (current level, upside, ceiling)."""
    base_potential = public_value(prospect, "potential")
    base_ceiling = public_value(prospect, "ceiling") or base_potential + 5.0
    rng = random.Random(f"{prospect.get('draft_year')}:{class_seed}:{prospect.get('id')}:season_move_v1")
    total = MOVE_INFO * hidden_gap(prospect, base_potential) + MOVE_NOISE * rng.gauss(0.0, 1.0)
    delta = total * movement_fraction(month)
    current = float(prospect.get("current_ability") or 0.0)
    potential = max(current + 1.0, base_potential + delta)
    return {"current": current, "potential": potential, "ceiling": max(potential, base_ceiling + delta),
            "delta": delta}


# ---------------------------------------------------------------------------------------------- the staff


def staff_profile(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    from .draft import scouting_staff_score

    slot = next((s for s in canonical.get("gameplay_staff_slots") or []
                 if s.get("team_id") == team_id and s.get("slot") == "scouting_lead"), None) or {}
    staff = dict(scouting_staff_score(canonical, team_id))
    staff["name"] = slot.get("name") or "Scouting staff"
    staff["archetype"] = str(slot.get("archetype") or "")
    staff["key"] = f"{team_id}:{slot.get('id') or ''}:{slot.get('name') or ''}"
    rng = random.Random(f"{staff['key']}:scouting_taste_v1")
    staff["taste"] = {group: rng.gauss(0.0, 1.0) for group in TASTE_GROUPS}
    staff["weights"] = ARCHETYPE_WEIGHTS.get(staff["archetype"], DEFAULT_WEIGHTS)
    staff["edge"] = clamp((float(staff["talent_eval"]) - 55.0) / 100.0, 0.0, EDGE_MAX)
    return staff


def staff_noise(staff: dict[str, Any], prospect: dict[str, Any]) -> float:
    """draft.scouting_noise for a plain prospect: 3 (excellent staff) to 11 points (poor)."""
    from .draft import default_draft_model_config

    scouting = default_draft_model_config()["scouting"]
    noise = float(scouting["base_noise"]) - (float(staff["score"]) - 60.0) * 0.09
    if prospect.get("league") == "International":
        noise += max(0.0, 65.0 - float(staff["international_coverage"])) * 0.04
    noise += float(prospect.get("volatility") or 0.0) * 0.05
    return clamp(noise, float(scouting["excellent_staff_noise"]), float(scouting["poor_staff_noise"]))


def coverage_pct(staff: dict[str, Any], public_rank: int, month: int, team_id: str, prospect_id: str,
                 class_seed: int, ahead: int = 0) -> float:
    """How much of a prospect this team's scouts have seen (18-100%). Everyone watches the top of the board;
    better staffs see more and learn faster through the season. Classes beyond next June are barely scouted."""
    score = float(staff["score"])
    rank = int(public_rank or 45)
    public_base = COVERAGE_TOP if rank <= 5 else COVERAGE_LOTTERY if rank <= 14 else COVERAGE_FIRST if rank <= 30 else COVERAGE_REST
    staff_multiplier = clamp(score / 62.0, 0.65, 1.75)
    progress = clamp(month / DRAFT_MONTH, 0.0, 1.0)
    focus = 9.0 if rank <= 8 else 0.0
    wobble = ((sum(ord(ch) for ch in f"{team_id}:{prospect_id}:{class_seed}") % 17) - 8) * 0.8
    value = (public_base + focus * (0.25 + 0.75 * progress) + (score - 55.0) * 0.72 + wobble
             + 18.0 * staff_multiplier * progress)
    if ahead > 0:
        value *= 0.6 ** ahead
    if ahead == 0 and rank <= 3 and score >= 62.0 and progress >= 0.8 and value >= 92.0:
        return 100.0
    return round(clamp(value, 18.0, 100.0), 1)


def taste_bias(staff: dict[str, Any], traits: dict[str, float]) -> float:
    """The staff's lasting lean: a shooting-first staff grades good shooters up and poor shooters down."""
    if not traits:
        return 0.0
    overall = sum(traits.values()) / len(traits)
    total = 0.0
    for group, keys in TASTE_GROUPS.items():
        values = [traits[k] for k in keys if k in traits]
        if values:
            total += staff["taste"][group] * (sum(values) / len(values) - overall) / 10.0
    return TASTE_SCALE * total


def favourite_group(staff: dict[str, Any]) -> str:
    return max(staff["taste"], key=lambda g: staff["taste"][g])


# --------------------------------------------------------------------------------------------- the reports


def _range(mid: float, half: float) -> dict[str, float]:
    return {"low": round(clamp(mid - half, 1, 99), 2), "mid": round(clamp(mid, 1, 99), 2),
            "high": round(clamp(mid + half, 1, 99), 2)}


def scout_grade(staff: dict[str, Any], current: float, potential: float, ceiling: float, floor: float,
                volatility: float, medical: float) -> float:
    """Talent only: upside and current level, downside, risk. Same form as the public grade
    (draft.generated_bpa_grade), with each staff's own weights."""
    w = staff["weights"]
    return (w["potential"] * potential + w["current"] * current + 0.10 * floor + 0.06 * ceiling
            - w["volatility"] * volatility - w["medical"] * medical)


def development_label(current: float, potential: float, age: Any) -> dict[str, str]:
    room = potential - current
    try:
        years = float(age)
    except (TypeError, ValueError):
        years = 20.0
    if room >= 28.0 or (years <= 19.0 and room >= 24.0):
        return {"key": "raw", "label": "Raw, high upside", "timeline": "needs two or three years"}
    if room <= 16.0 or years >= 22.0:
        return {"key": "ready", "label": "Ready now, less growth", "timeline": "can help soon"}
    return {"key": "balanced", "label": "Some now, some upside", "timeline": "a year or two"}


def team_report(prospect: dict[str, Any], traits: dict[str, float], staff: dict[str, Any], team_id: str,
                month: int, class_seed: int, ahead: int = 0) -> dict[str, Any]:
    from .health import prospect_medical_penalty

    pid = str(prospect["id"])
    rng = random.Random(f"{prospect.get('draft_year')}:{class_seed}:{team_id}:{pid}:scout_view_v1")
    z_potential, z_current = rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)
    trait_draws = {key: rng.gauss(0.0, 1.0) for key in sorted(traits)}
    coverage = coverage_pct(staff, int(prospect.get("rank") or 45), month, team_id, pid, class_seed, ahead)
    noise = staff_noise(staff, prospect)
    width = WIDTH_FLOOR + WIDTH_SLOPE * (1.0 - coverage / 100.0)
    public = public_view(prospect, month, class_seed)
    from .draft import trait_noise_multiplier
    position = str(prospect.get("position") or "")
    estimates = {key: clamp(value + trait_draws[key] * noise * TRAIT_NOISE * width
                            * trait_noise_multiplier(key, position, staff), 1, 99)
                 for key, value in sorted(traits.items())}
    edge = staff["edge"] * coverage / 100.0
    potential = (public["potential"] + edge * hidden_gap(prospect, public["potential"])
                 + taste_bias(staff, estimates) + z_potential * noise * POT_NOISE * width)
    current = public["current"] + z_current * noise * CUR_NOISE * width
    potential = max(potential, current + 1.0)
    ceiling = potential + max(2.0, public["ceiling"] - public["potential"])
    floor = current - max(0.0, float(prospect.get("current_ability") or 0) - float(prospect.get("floor") or 0))
    volatility = float(prospect.get("volatility") or 0.0)
    medical = prospect_medical_penalty(prospect)
    grade = scout_grade(staff, current, potential, ceiling, floor, volatility, medical)
    half = max(1.2, noise * width)
    return {
        "team_id": team_id, "prospect_id": pid, "draft_year": str(prospect.get("draft_year")), "month": month,
        "scouted_grade": round(grade, 2),
        "estimated_current": _range(current, half * 0.6),
        "estimated_potential": _range(potential, half * 1.15),
        "estimated_ceiling": round(ceiling, 2), "estimated_floor": round(floor, 2),
        "trait_estimates": {key: _range(value, half * 0.8) for key, value in estimates.items()},
        "coverage": coverage, "confidence": round(float(staff["confidence"]), 3),
        "development": development_label(current, potential, prospect.get("age")),
        "risk": {"volatility": round(volatility, 1), "medical": round(medical, 2)},
    }


def class_scouting(canonical: dict[str, Any], year: Any, month: int | None = None) -> dict[str, Any]:
    """Every team's report on every prospect in the class for one month, each team's scouts' board (talent order)
    and the consensus. Cached by class, month and the league's scouting leads."""
    year = str(year)
    if month is None:
        month, ahead = canonical_month(canonical, year)
    else:
        ahead = 0
    prospects, traits, class_seed = class_records(canonical, year)
    teams = [t["id"] for t in canonical.get("teams") or []]
    staffs = {team_id: staff_profile(canonical, team_id) for team_id in teams}
    key = (year, class_seed, int(month), ahead, tuple(sorted(p["id"] for p in prospects)),
           tuple((t, staffs[t]["key"], round(staffs[t]["score"], 3), staffs[t]["archetype"]) for t in teams))
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    reports: dict[str, dict[str, dict[str, Any]]] = {}
    boards: dict[str, list[str]] = {}
    ranks: dict[str, dict[str, int]] = {}
    for team_id in teams:
        team_reports = {p["id"]: team_report(p, traits.get(p["id"], {}), staffs[team_id], team_id, month,
                                             class_seed, ahead) for p in prospects}
        order = sorted(team_reports, key=lambda pid: (-team_reports[pid]["scouted_grade"], pid))
        reports[team_id] = team_reports
        boards[team_id] = order
        ranks[team_id] = {pid: index for index, pid in enumerate(order, start=1)}
        for pid, rank in ranks[team_id].items():
            team_reports[pid]["scout_rank"] = rank
    consensus = consensus_board(prospects, reports, ranks)
    result = {"year": year, "month": month, "month_label": MONTH_LABELS[int(month)], "ahead": ahead,
              "class_seed": class_seed, "reports": reports, "boards": boards, "ranks": ranks,
              "consensus": consensus, "staffs": staffs,
              "prospects": {p["id"]: p for p in prospects}}
    if len(_CACHE) >= _CACHE_LIMIT:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = result
    return result


def consensus_board(prospects: list[dict[str, Any]], reports: dict[str, dict[str, dict[str, Any]]],
                    ranks: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    """The league's board: the median of the teams' scouted grades, with each prospect's best and worst team rank
    and the median of the teams' skill estimates (to say where one team's scouts differ)."""
    rows = {}
    for prospect in prospects:
        pid = prospect["id"]
        team_rows = [reports[t][pid] for t in reports]
        if not team_rows:
            continue
        team_ranks = sorted(ranks[t][pid] for t in ranks)
        traits = {}
        for key in team_rows[0]["trait_estimates"]:
            traits[key] = statistics.median(r["trait_estimates"][key]["mid"] for r in team_rows)
        rows[pid] = {
            "grade": statistics.median(r["scouted_grade"] for r in team_rows),
            "current": statistics.median(r["estimated_current"]["mid"] for r in team_rows),
            "potential": statistics.median(r["estimated_potential"]["mid"] for r in team_rows),
            "best": team_ranks[0], "worst": team_ranks[-1],
            "middle": (team_ranks[len(team_ranks) // 4], team_ranks[(3 * len(team_ranks)) // 4]),
            "traits": traits,
            "public_rank": int(prospect.get("rank") or 999),
        }
    order = sorted(rows, key=lambda pid: (-rows[pid]["grade"], rows[pid]["public_rank"], pid))
    for rank, pid in enumerate(order, start=1):
        rows[pid]["rank"] = rank
    return rows


def report_for(canonical: dict[str, Any], prospect: dict[str, Any] | str | None, team_id: str | None,
               year: Any = None, month: int | None = None) -> dict[str, Any]:
    """This team's current report on one prospect ({} when the prospect is not in a known class)."""
    if not prospect or not team_id:
        return {}
    pid = prospect if isinstance(prospect, str) else str(prospect.get("id") or prospect.get("prospect_id") or "")
    if year is None:
        if isinstance(prospect, dict) and prospect.get("draft_year"):
            year = prospect["draft_year"]
        else:
            year = next((p.get("draft_year") for p in canonical.get("draft_prospects") or [] if p.get("id") == pid), None)
    if year is None:
        return {}
    try:
        scouting = class_scouting(canonical, year, month)
    except (KeyError, ValueError, TypeError):
        return {}
    return (scouting["reports"].get(team_id) or {}).get(pid) or {}


def where_scouts_differ(scouting: dict[str, Any], team_id: str, prospect_id: str) -> str | None:
    """'Your scouts are lower on his shooting': the skill where this team's read differs most from the league's."""
    report = (scouting["reports"].get(team_id) or {}).get(prospect_id)
    consensus = scouting["consensus"].get(prospect_id)
    if not report or not consensus:
        return None
    diffs = [(report["trait_estimates"][k]["mid"] - consensus["traits"][k], k)
             for k in report["trait_estimates"] if k in consensus["traits"] and k != "nba_readiness"]
    potential_diff = report["estimated_potential"]["mid"] - consensus["potential"]
    diffs.append((potential_diff * 1.5, "upside"))
    if not diffs:
        return None
    diff, key = max(diffs, key=lambda item: abs(item[0]))
    if abs(diff) < 2.0:
        return None
    word = "his upside" if key == "upside" else f"his {TRAIT_WORDS.get(key, key.replace('_', ' '))}"
    return f"{'higher' if diff > 0 else 'lower'} on {word}"


def previous_month_ranks(canonical: dict[str, Any], year: Any, team_id: str, month: int) -> dict[str, int]:
    if month <= 0:
        return {}
    previous = class_scouting(canonical, year, month - 1)
    return previous["ranks"].get(team_id) or {}


def clear_cache() -> None:
    _CACHE.clear()
