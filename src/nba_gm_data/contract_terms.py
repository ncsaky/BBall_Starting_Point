"""Salary paths and final-season options (CONTRACT-TERMS part 2): one place for the shape of a contract.

- **Salary path.** Rising (the largest legal raise each season: 5% of the first year, 8% with Bird rights or in an
  extension), flat, or declining (the same step down; the CBA limits decreases like raises). Salaries are saved year
  by year, and the cap, payroll, tax and roster planning read those years (cap_ledger.raise_schedule).
- **Final-season option.** None, a player option or a team option on the last season. An option needs a contract of
  at least two seasons; Early Bird re-signings need two seasons before the option year; offer sheets carry none (the
  game keeps sheets fully guaranteed, slice 3). The option season is decided by the player or the team when it comes
  due (offseason_decisions).

**How a player values the shape** (``value_factor``): the money is discounted 7% a season (earlier money is worth
more to him: injury, release and the time value of money), a player option counts its season at 1.2x (he keeps the
choice), a team option at 0.6x (he may never be paid it). The factor is the offer's value against the same first-year
salary on the reference shape, so he signs when ``salary x factor`` reaches his price. The reference is the rising
path with no option for free agents and re-signings (what AI bids offer) and the flat path with no option for
extensions (the shape the extension price was set on). These weights are assumptions, stated here; no public data
prices options directly.

**How AI-to-AI deals are shaped** (``ai_structure``): drawn by a fixed hash per player, team and season (no shared
random stream) from the real shares of new signings by kind of deal, from CONTRACT-STRUCTURE-EVIDENCE (1,370 deals
2019-2026; docs/agents/tasks/contract-structure-evidence.md sections 1-2, data/research/contract_structure_evidence.json):
mid-level deals mostly rise 5% with 34% player and 13% team options among multi-year deals; Bird re-signings are often
flat (38%) or declining (18%); new max deals always rise, with player options in 47%; extensions mostly rise 8%,
with player options in 23% (40% for high-scoring regulars, who get no team options); two-year minimums carry an
optional second year in 41 of 74. Without a kind, the shares of running contracts in the 2025-26 salary table by
salary band are used (scripts/contract_structure_shares.py).
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

SALARY_PATHS = ("rising", "flat", "declining")
CONTRACT_OPTIONS = ("none", "player", "team")
PATH_WORDS = {"rising": "Rising", "flat": "Flat", "declining": "Declining"}
OPTION_WORDS = {"none": "No option", "player": "Player option", "team": "Team option"}
PLAYER_DISCOUNT_RATE = 0.07
OPTION_SEASON_WEIGHT = {"none": 1.0, "player": 1.2, "team": 0.6}
OPTION_TYPE = {"player": "player_option", "team": "team_option"}
SHARES_FILE = "data/research/contract_structure_shares_2025_26.json"


def normalize_path(value: Any, default: str = "rising") -> str:
    text = str(value or "").strip().lower()
    aliases = {"max": "rising", "raise": "rising", "increasing": "rising", "0": "flat", "none": "flat",
               "decline": "declining", "decreasing": "declining"}
    text = aliases.get(text, text)
    return text if text in SALARY_PATHS else default


def normalize_option(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_option", "")
    return text if text in CONTRACT_OPTIONS else "none"


def path_rate(path: str, max_raise: float) -> float:
    """The annual change as a share of year one: +max, 0 or -max."""
    path = normalize_path(path)
    return float(max_raise) if path == "rising" else -float(max_raise) if path == "declining" else 0.0


def multipliers(years: int, rate: float) -> list[float]:
    return [1.0 + float(rate) * k for k in range(max(1, int(years)))]


def _present_value(years: int, rate: float, option: str) -> float:
    weights = multipliers(years, rate)
    if years >= 2:
        weights[-1] *= OPTION_SEASON_WEIGHT.get(normalize_option(option), 1.0)
    return sum(w / (1.0 + PLAYER_DISCOUNT_RATE) ** k for k, w in enumerate(weights))


def value_factor(years: int, path: str, option: str, max_raise: float, reference: str = "rising") -> float:
    """What the shape is worth to the player against the reference shape with the same first-year salary."""
    years = max(1, int(years))
    option = normalize_option(option) if years >= 2 else "none"
    ref = _present_value(years, path_rate(reference, max_raise), "none")
    return round(_present_value(years, path_rate(path, max_raise), option) / ref, 4)


def factor_table(max_raise: float, reference: str = "rising", max_years: int = 5) -> dict[str, dict[str, dict[str, float]]]:
    """value_factor for every path, option and length (the screens use it; the engine computes the same numbers)."""
    return {path: {option: {str(y): value_factor(y, path, option, max_raise, reference) for y in range(1, max_years + 1)}
                   for option in CONTRACT_OPTIONS} for path in SALARY_PATHS}


def option_problem(years: int, option: str, *, bird_level: str | None = None, offer_sheet: bool = False) -> str | None:
    """Why this option is not allowed on this contract (None when it is)."""
    option = normalize_option(option)
    if option == "none":
        return None
    if offer_sheet:
        return "Offer sheets in this game are fully guaranteed, with no option."
    if int(years) < 2:
        return "An option needs a contract of at least two seasons (the option is the last one)."
    if bird_level == "early" and int(years) < 3:
        return "With Early Bird rights he must sign two seasons before an option year: offer three seasons for an option."
    return None


def apply_option(seasons: list[dict[str, Any]], option: str) -> list[dict[str, Any]]:
    """Mark the final season as a player or team option (pending: not guaranteed until it is exercised)."""
    option = normalize_option(option)
    if option == "none" or len(seasons) < 2:
        return seasons
    last = seasons[-1]
    last["option_type"] = OPTION_TYPE[option]
    if "guaranteed_salary" in last:
        last["guaranteed_salary"] = None
    return seasons


def schedule(first_salary: float, years: int, path: str, max_raise: float) -> list[int]:
    from .cap_ledger import raise_schedule
    return raise_schedule(first_salary, years, path_rate(path, max_raise))


def describe(path: str, option: str, max_raise: float, years: int) -> str:
    """Plain words for the shape, e.g. "Rising 8% a season, team option on the last season"."""
    path = normalize_path(path)
    pct = round(float(max_raise) * 100)
    words = {"rising": f"rising {pct}% of the first year each season", "flat": "the same salary every season",
             "declining": f"falling {pct}% of the first year each season"}[path] if years >= 2 else "one season"
    option = normalize_option(option)
    if option != "none" and years >= 2:
        words += f", {OPTION_WORDS[option].lower()} on the last season"
    return words[0].upper() + words[1:]


def effect_words(factor: float, path: str, option: str) -> str:
    """How the shape changes what he counts the offer as (for "Will he sign?")."""
    if abs(factor - 1.0) < 0.005:
        return ""
    pieces = []
    path = normalize_path(path)
    if path == "flat":
        pieces.append("flat pay gives him less money than the usual raises")
    elif path == "declining":
        pieces.append("falling pay gives him less in later years")
    option = normalize_option(option)
    if option == "player":
        pieces.append("a player option lets him choose the last season")
    elif option == "team":
        pieces.append("a team option means he may never be paid the last season")
    direction = "more" if factor > 1 else "less"
    return (f"{'; '.join(pieces)[:1].upper() + '; '.join(pieces)[1:]}: he counts it as {abs(factor - 1) * 100:.0f}% "
            f"{direction} than the same first-year salary on the usual terms." if pieces else "")


@lru_cache(maxsize=1)
def _shares() -> dict[str, Any]:
    from .resource_paths import game_resource_root
    try:
        return json.loads((game_resource_root() / SHARES_FILE).read_text()).get("bands") or {}
    except (OSError, ValueError):
        return {}


def _band(salary: float) -> str:
    if salary < 3_000_000:
        return "minimum (under $3M)"
    if salary < 15_000_000:
        return "$3M-$15M"
    if salary < 35_000_000:
        return "$15M-$35M"
    return "$35M and up"


def _unit(*parts: Any) -> float:
    digest = hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(16 ** 12)


def _pick(shares: dict[str, float], unit: float, order: tuple[str, ...]) -> str:
    total = 0.0
    for key in order:
        total += float(shares.get(key) or 0.0)
        if unit < total:
            return key
    return order[0]


# Shares of new multi-year signings by kind of deal (CONTRACT-STRUCTURE-EVIDENCE; counts in the module notes).
# Path: "up other" and "mixed" count as rising. Options: share of multi-year deals with each documented option.
EVIDENCE_SHARES: dict[str, dict[str, dict[str, float]]] = {
    "exception": {"path_share": {"rising": 0.80, "flat": 0.15, "declining": 0.05},
                  "option_share": {"none": 0.53, "player": 0.34, "team": 0.13}},     # 41 and 16 of 119
    "bird": {"path_share": {"rising": 0.44, "flat": 0.38, "declining": 0.18},
             "option_share": {"none": 0.66, "player": 0.19, "team": 0.15}},          # 9 and 7 of 47
    "max": {"path_share": {"rising": 1.0, "flat": 0.0, "declining": 0.0},
            "option_share": {"none": 0.48, "player": 0.47, "team": 0.05}},           # 9 and 1 of 19
    "extension": {"path_share": {"rising": 0.76, "flat": 0.14, "declining": 0.10},
                  "option_share": {"none": 0.68, "player": 0.23, "team": 0.09}},     # 49 and 19 of 216
    "extension_star": {"path_share": {"rising": 0.76, "flat": 0.14, "declining": 0.10},
                       "option_share": {"none": 0.60, "player": 0.40, "team": 0.0}}, # high-scoring regulars, 25 of 62
    "minimum": {"path_share": {"rising": 1.0, "flat": 0.0, "declining": 0.0},
                "option_share": {"none": 0.45, "player": 0.43, "team": 0.12}},       # two-year minimums, 32 and 9 of 74
}
STAR_SALARY = 35_000_000   # extensions and free-agent deals at this first-year salary use the star / max rows


def deal_kind(route: str | None, first_salary: float, *, extension: bool = False) -> str:
    """The evidence row for a deal: by how it is paid (cap_ledger routes) and its size."""
    if extension:
        return "extension_star" if first_salary >= STAR_SALARY else "extension"
    if route == "minimum":
        return "minimum"
    if first_salary >= STAR_SALARY:
        return "max"
    if route == "bird":
        return "bird"
    return "exception"


def ai_structure(first_salary: float, years: int, *, player_id: str, team_id: str, season: str,
                 bird_level: str | None = None, offer_sheet: bool = False, minimum: bool = False,
                 kind: str | None = None) -> dict[str, str]:
    """The path and option an AI team writes into a contract, at the real shares for its kind of deal (``kind``, see
    EVIDENCE_SHARES) or else its salary band (fixed hash; no shared random stream). One-season deals keep the rising,
    option-free shape; minimum deals keep the minimum scale's path."""
    if int(years) < 2 or (minimum and kind is None):
        return {"path": "rising", "option": "none"}
    row = EVIDENCE_SHARES.get(kind) if kind else None
    row = row or _shares().get(_band(float(first_salary))) or {}
    path = _pick(row.get("path_share") or {"rising": 1.0}, _unit(season, team_id, player_id, "path"), SALARY_PATHS)
    option = _pick(row.get("option_share") or {"none": 1.0}, _unit(season, team_id, player_id, "option"), CONTRACT_OPTIONS)
    if option_problem(years, option, bird_level=bird_level, offer_sheet=offer_sheet):
        option = "none"
    if kind == "minimum":
        path = "rising"   # the minimum scale sets the path
    return {"path": path, "option": option}
