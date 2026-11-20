"""Front-office trade personality (TRADE-MARKET): lasting traits per front office and the bounded, explained value
adjustments they make to a team's trade evaluation.

Plan and user decisions: docs/agents/tasks/trade-market-personality-plan.md. Report: docs/agents/tasks/trade-market.md.

The textbook model (value plus context, transactions.evaluate_trade_for_team) decides what a deal is worth to a team.
Personality is a small layer on top: why real trades are not all textbook. Each front office has

- **savvy** (0-100): how accurate its value judgements are. A savvy office (65+) makes no systematic mistakes; a less
  savvy one misjudges in its own lasting direction (its *biases*: overpays for veterans, spends picks too freely,
  overrates its own players, chases star names), more strongly the lower its savvy;
- **urgency** (risk appetite): how readily it pays a premium for players who help now while its window is open;
- **patience**: how long it negotiates, how small its concessions are and how long it waits before a final offer
  (used by trade_market.py);
- **loyalty**: attachment to players who have been with it for years (scales step 1's tenure premium);
- **preferences** that are not mistakes: prizes draft picks, avoids the luxury tax, pays the tax to win;
- **player opinions**: players it is higher or lower on than the league, from its scouting lead's lasting taste
  (the same taste that shapes its draft board, draft_scouting.staff_profile) and from documented real connections
  (the Knicks' Villanova players).

Real front offices start from widely held public reputations, each with its sources
(data/overrides/front_office_overrides.json, section ``trade_personality``). Traits without a widely held view, and
front offices whose regime is too new, are drawn from the measured spread of the listed values, seeded by the save
(persistent: the same save always has the same front offices). Traits drift a little each season, again seeded.

No dice: every adjustment is a fixed function of the traits and the assets in the deal, bounded, and comes with a
plain-words reason that is stored on the evaluation and shown with the trade.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import random
import statistics
from typing import Any

TRAITS = ("savvy", "urgency", "patience", "loyalty")
DEFAULT_TRAIT = 50.0
TRAIT_FLOOR, TRAIT_CEILING = 10.0, 95.0
# Spread used for traits without a widely held view when the listed values are too few to measure one.
FALLBACK_SPREAD = 14.0
DRIFT_PER_SEASON = 2.5  # seeded drift each season (standard deviation, trait points)

# Misjudgments (scaled by how far savvy is below SAVVY_ACCURATE) and preferences (fixed size).
MISJUDGMENTS = {
    "overpays_veterans": "tends to overpay for veterans",
    "underrates_picks": "spends draft picks freely",
    "overrates_own": "overrates its own players",
    "chases_stars": "chases star names",
}
PREFERENCES = {
    "values_picks": "prizes draft picks",
    "tax_averse": "works hard to stay under the luxury tax",
    "spends_tax": "will pay the luxury tax to win",
}
SAVVY_ACCURATE = 65.0  # savvy at or above this: no systematic misjudgment
SAVVY_SPAN = 45.0      # savvy 20 or lower: full-size misjudgment

# Sizes, in the trade evaluation's value points (a future first is about 43, a future second about 9.5, a solid
# rotation player 40-55, a star 75+). Every term has its own cap and the sum is capped at PERSONALITY_CAP.
URGENCY_RATE = 0.10        # premium per unit of urgency above the middle, share of incoming rotation players' value
URGENCY_LOW_RATE = 0.05    # discount for low urgency
URGENCY_CAP = 6.0
URGENCY_ON_COURT = 55.0    # "help now": an incoming rotation-level player (on-court value) better than any going out
WINDOW_FACTOR = {"contend": 1.0, "rise": 0.6, "retool": 0.0, "rebuild": 0.0}
URGENCY_PICK_ALLOWANCE = 12.0  # extra draft value a fully urgent contender will spend on a marginal player
VETERAN_AGE = 29.0
VETERAN_RATE, VETERAN_CAP = 0.12, 5.0
PICKS_FREE_RATE, PICKS_FREE_CAP = 0.30, 6.0
PICKS_FREE_ALLOWANCE = 12.0
OWN_RATE, OWN_CAP = 0.10, 5.0
STAR_VALUE, STAR_RATE, STAR_CAP = 68.0, 0.10, 6.0
PICK_PREFERENCE_RATE, PICK_PREFERENCE_CAP = 0.10, 4.0
TAX_AVERSE_RATE, TAX_SPEND_RATE, TAX_PREFERENCE_CAP = 0.25, 0.30, 4.0
LOYALTY_CAP = 5.0
OPINION_SHARE = 0.015      # the office's strongest leans at each end: about 6 players high and 6 low per office
OPINION_MIN_VALUE = 20.0   # players worth less than this are nobody's particular opinion
OPINION_BASE = 2.5         # value points at the cut-off ...
OPINION_SLOPE = 1.5        # ... plus this per unit of lean beyond it
OPINION_CAP = 5.0
CONNECTION_POINTS = 5.0
PERSONALITY_CAP = 10.0

# The scouting taste groups (draft_scouting.TASTE_GROUPS) read on an NBA player's display ratings.
TASTE_FACTS = {
    "shooting": ("shooting", "range"),
    "tools": ("athleticism", "lateral_agility"),
    "feel": ("iq", "passing"),
    "defense": ("defense", "rim_deterrence"),
    "motor": ("rebounding", "def_effort"),
}

OVERRIDES_FILE = Path("data/overrides/front_office_overrides.json")


# ----------------------------------------------------------------------------------------------- the traits

@lru_cache(maxsize=4)
def reputation_data(root: str = ".") -> dict[str, Any]:
    from .resource_paths import game_resource_root
    for base in (Path(root), game_resource_root()):
        path = base / OVERRIDES_FILE
        if path.exists():
            return (json.loads(path.read_text(encoding="utf-8")).get("trade_personality") or {})
    return {}


DOCUMENTED_MISJUDGMENT_SAVVY = 50.0
UNKNOWN_SPREAD_SHARE = 0.6  # offices without a reputation are drawn closer to the middle than the reputed ones
DRAW_CLIP = 2.0


def measured_spread(data: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Centre and spread for drawing a trait that has no widely held view.

    The centre is the league middle (50) by definition. The spread is measured from the reputed offices (their
    distance from the middle, root mean square), scaled down by UNKNOWN_SPREAD_SHARE: reputations exist mostly for
    the extreme offices (an aggressive star chaser gets written about, an ordinary one does not), so an office
    without one is more likely near the middle. Too few reputed values: FALLBACK_SPREAD."""
    out = {}
    for trait in TRAITS:
        values = [float(row[trait]["value"]) for row in (data.get("teams") or {}).values() if trait in row]
        spread = (statistics.fmean((v - DEFAULT_TRAIT) ** 2 for v in values) ** 0.5 if len(values) >= 4
                  else FALLBACK_SPREAD)
        out[trait] = (DEFAULT_TRAIT, round(max(8.0, spread * UNKNOWN_SPREAD_SHARE), 2))
    return out


def _clip(value: float) -> float:
    return round(min(TRAIT_CEILING, max(TRAIT_FLOOR, value)), 1)


def base_traits(teams: list[dict[str, Any]], seed: int, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Every front office's starting traits for a save: reputation where widely held, else a seeded draw from the
    measured spread. Plain data, stored in the save (``save['front_office_traits']``)."""
    data = reputation_data() if data is None else data
    spread = measured_spread(data)
    reputations = data.get("teams") or {}
    too_new = set((data.get("regimes_too_new") or {}).keys())
    out = {}
    for team in sorted(teams, key=lambda t: t["id"]):
        abbrev = team.get("abbrev")
        rep = reputations.get(abbrev) or {}
        row: dict[str, Any] = {"abbrev": abbrev, "sources": {}, "why": {}, "from_reputation": []}
        for trait in TRAITS:
            if trait in rep:
                row[trait] = _clip(float(rep[trait]["value"]))
                row["sources"][trait] = list(rep[trait].get("sources") or [])
                row["why"][trait] = rep[trait].get("why")
                row["from_reputation"].append(trait)
            else:
                mean, sd = spread[trait]
                rng = random.Random(f"{seed}:{abbrev}:{trait}:front-office-trait-v1")
                row[trait] = _clip(mean + sd * max(-DRAW_CLIP, min(DRAW_CLIP, rng.gauss(0.0, 1.0))))
        biases = []
        for item in rep.get("biases") or []:
            biases.append({"key": item["key"], "why": item.get("why"), "sources": list(item.get("sources") or [])})
        if (any(b["key"] in MISJUDGMENTS for b in biases) and "savvy" not in row["from_reputation"]
                and row["savvy"] > DOCUMENTED_MISJUDGMENT_SAVVY):
            # A documented misjudging habit means the office is not among the accurate ones: its drawn savvy is
            # capped so the habit actually shows (rule 4: the hint describes what the engine uses).
            row["savvy"] = DOCUMENTED_MISJUDGMENT_SAVVY
        if not rep.get("biases") and row["savvy"] < 55.0:
            # A less savvy office without a documented habit still misjudges in one lasting direction (seeded).
            key = sorted(MISJUDGMENTS)[random.Random(f"{seed}:{abbrev}:bias:front-office-trait-v1").randrange(len(MISJUDGMENTS))]
            biases.append({"key": key, "why": None, "sources": []})
        row["biases"] = biases
        row["connections"] = [dict(item) for item in rep.get("connections") or []]
        row["regime_new"] = abbrev in too_new
        out[team["id"]] = row
    return {"base_season": None, "seed": seed, "teams": out}


def drifted(base: dict[str, Any], season_start: int | None) -> dict[str, dict[str, Any]]:
    """Traits for a season: the stored starting traits plus a small seeded drift per season since the start."""
    teams = base.get("teams") or {}
    start = base.get("base_season")
    if season_start is None or start is None or season_start <= int(start):
        return teams
    out = {}
    seed = base.get("seed")
    for team_id, row in teams.items():
        moved = dict(row)
        for trait in TRAITS:
            value = float(row[trait])
            for year in range(int(start) + 1, int(season_start) + 1):
                value += random.Random(f"{seed}:{row.get('abbrev')}:{trait}:{year}:front-office-drift-v1").gauss(0.0, DRIFT_PER_SEASON)
            moved[trait] = _clip(value)
        out[team_id] = moved
    return out


def ensure_save_traits(save: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
    """Create the save's front-office traits once (league saves only)."""
    stored = save.get("front_office_traits")
    if isinstance(stored, dict) and stored.get("teams"):
        return stored
    seed = int((save.get("meta") or {}).get("seed") or 1)
    stored = base_traits(canonical.get("teams") or [], seed)
    from .save import season_start_year_from_date
    current = str((save.get("state") or {}).get("current_date") or "2026-07-01")
    stored["base_season"] = season_start_year_from_date(current)
    save["front_office_traits"] = stored
    return stored


def traits_view(save: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The traits the engine uses today (drift applied), for canonical_with_save."""
    stored = save.get("front_office_traits")
    if not isinstance(stored, dict) or not stored.get("teams"):
        return {}
    from .save import season_start_year_from_date
    current = str((save.get("state") or {}).get("current_date") or "")
    return drifted(stored, season_start_year_from_date(current) if current else None)


def office(canonical: dict[str, Any], team_id: str) -> dict[str, Any] | None:
    """This team's traits, or None for the human team and for leagues without traits (the bare canonical league and
    test fixtures: a league save always has them, ``ensure_save_traits``)."""
    if team_id in set(canonical.get("_human_team_ids") or []):
        return None
    traits = canonical.get("front_office_traits")
    if not traits:
        return None
    return traits.get(team_id)


def has_bias(row: dict[str, Any] | None, key: str) -> bool:
    return bool(row) and any(item.get("key") == key for item in row.get("biases") or [])


def misjudgment(row: dict[str, Any]) -> float:
    """0 (accurate) to 1 (full-size misjudgment), from savvy."""
    return max(0.0, min(1.0, (SAVVY_ACCURATE - float(row["savvy"])) / SAVVY_SPAN))


def urgency_level(row: dict[str, Any]) -> float:
    """-1 (no urgency) to +1 (maximum), 0 at the league middle."""
    return max(-1.0, min(1.0, (float(row["urgency"]) - 50.0) / 40.0))


def loyalty_level(row: dict[str, Any]) -> float:
    return max(-0.6, min(1.0, (float(row["loyalty"]) - 50.0) / 40.0))


def _stance(canonical: dict[str, Any], team_id: str) -> str:
    from .trade_targets import team_stance
    state = next((s for s in canonical.get("team_strategic_states", []) if s.get("team_id") == team_id), {}) or {}
    return team_stance(state)


def _abbrev(canonical: dict[str, Any], team_id: str) -> str:
    return next((t.get("abbrev") for t in canonical.get("teams", []) if t.get("id") == team_id), team_id)


# ------------------------------------------------------------------------------------------ player opinions

def _taste(canonical: dict[str, Any], team_id: str) -> dict[str, float]:
    memo = canonical.setdefault("_fo_taste", {}) if canonical.get("_allow_internal_caches") else {}
    if team_id not in memo:
        from .draft_scouting import staff_profile
        memo[team_id] = staff_profile(canonical, team_id)["taste"]
    return memo[team_id]


def _taste_groups(canonical: dict[str, Any], player: dict[str, Any]) -> dict[str, float] | None:
    from .trade_wants import player_facts
    facts = player_facts(canonical, player)
    groups = {}
    for group, keys in TASTE_FACTS.items():
        values = [float(facts[k]) for k in keys if isinstance(facts.get(k), (int, float))]
        if values:
            groups[group] = sum(values) / len(values)
    return groups if len(groups) >= 3 else None


def _lean(taste: dict[str, float], groups: dict[str, float]) -> float:
    mean = sum(groups.values()) / len(groups)
    return sum(taste.get(g, 0.0) * (v - mean) / 10.0 for g, v in groups.items())


def _office_leans(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    """The office's scouting lean on every rostered player of real value, and the cut-offs that make the few
    strongest an "opinion" (OPINION_SHARE of the league at each end)."""
    memo = canonical.setdefault("_fo_leans", {}) if canonical.get("_allow_internal_caches") else {}
    if team_id in memo:
        return memo[team_id]
    from .transactions import player_asset_values_by_id
    taste = _taste(canonical, team_id)
    values = player_asset_values_by_id(canonical)
    leans = {}
    for player in canonical.get("players", []):
        if not player.get("team_id") or player.get("_inactive_player"):
            continue
        if float((values.get(player["id"]) or {}).get("player_value") or 0.0) < OPINION_MIN_VALUE:
            continue
        groups = _taste_groups(canonical, player)
        if groups:
            leans[player["id"]] = _lean(taste, groups)
    ordered = sorted(leans.values())
    count = max(1, int(round(len(ordered) * OPINION_SHARE)))
    low = ordered[count - 1] if ordered else -1e9
    high = ordered[-count] if ordered else 1e9
    memo[team_id] = {"leans": leans, "low": low, "high": high}
    return memo[team_id]


def player_opinion(canonical: dict[str, Any], team_id: str, player_id: str) -> dict[str, Any] | None:
    """How much higher (or lower) this office is on a player than the league, in value points, with the reason.
    None when it has no particular opinion (the usual case).

    Two sources: a documented real connection (data file), and the office's scouting lean (its scouting lead's
    lasting taste, the same one behind its draft board, read on the player's ratings). Only the few players at the
    two ends of the office's lean (OPINION_SHARE of the league's players of real value at each end, about a dozen)
    count; the size grows with how far past the cut-off he is, up to OPINION_CAP, scaled by his value."""
    row = office(canonical, team_id)
    if not row:
        return None
    memo = canonical.setdefault("_fo_opinions", {}) if canonical.get("_allow_internal_caches") else {}
    key = (team_id, player_id)
    if key in memo:
        return memo[key]
    from .transactions import player_asset_values_by_id, player_by_id
    player = player_by_id(canonical, player_id)
    result = None
    if player:
        name = player.get("name")
        connection = next((c for c in row.get("connections") or [] if c.get("player") == name), None)
        if connection:
            result = {"points": CONNECTION_POINTS, "kind": "connection", "why": connection.get("why"),
                      "sources": list(connection.get("sources") or [])}
        else:
            table = _office_leans(canonical, team_id)
            lean = table["leans"].get(player_id)
            if lean is not None and (lean >= table["high"] or lean <= table["low"]):
                edge = table["high"] if lean > 0 else table["low"]
                size = OPINION_BASE + OPINION_SLOPE * abs(lean - edge)
                value = float((player_asset_values_by_id(canonical).get(player_id) or {}).get("player_value") or 0.0)
                points = (1 if lean > 0 else -1) * min(OPINION_CAP, size) * max(0.0, min(1.0, value / 50.0))
                groups = _taste_groups(canonical, player) or {}
                taste = _taste(canonical, team_id)
                mean = sum(groups.values()) / len(groups) if groups else 0.0
                best = max(groups, key=lambda g: taste.get(g, 0.0) * (groups[g] - mean) * (1 if points > 0 else -1)) if groups else "feel"
                from .draft_scouting import TASTE_WORDS
                result = {"points": round(points, 2), "kind": "scouting", "group": best,
                          "why": (f"its scouts weigh {TASTE_WORDS.get(best, best)}"
                                  f"{' and like' if points > 0 else ' and are cool on'} his")}
    memo[key] = result
    return result


# ------------------------------------------------------------------------------------------ the evaluation

def _player_value(canonical: dict[str, Any], player_id: str) -> float:
    from .transactions import player_asset_values_by_id
    return float((player_asset_values_by_id(canonical).get(player_id) or {}).get("player_value") or 0.0)


def _on_court(canonical: dict[str, Any], player_id: str) -> float:
    from .transactions import player_asset_values_by_id
    return float((player_asset_values_by_id(canonical).get(player_id) or {}).get("on_court_value") or 0.0)


def _age(canonical: dict[str, Any], player_id: str) -> float:
    from .transactions import player_by_id
    player = player_by_id(canonical, player_id) or {}
    try:
        return float(player.get("display_age", player.get("age")) or 27.0)
    except (TypeError, ValueError):
        return 27.0


def _name(canonical: dict[str, Any], player_id: str) -> str:
    from .transactions import player_by_id
    return (player_by_id(canonical, player_id) or {}).get("name") or player_id


def _picks(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in assets if a.get("kind") in {"pick", "pick_swap"}]


def _players(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in assets if a.get("kind") == "player" and a.get("id")]


def _term(key: str, points: float, text: str) -> dict[str, Any]:
    return {"key": key, "points": round(points, 3), "text": text}


def personality_terms(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
                      outgoing: list[dict[str, Any]], *, tax_term: float = 0.0,
                      proposal: Any = None) -> dict[str, Any]:
    """The bounded personality adjustment to this team's evaluation of a deal, term by term with reasons."""
    row = office(canonical, team_id)
    if not row:
        return {"total": 0.0, "terms": []}
    abbrev = row.get("abbrev") or _abbrev(canonical, team_id)
    terms = []
    stance = _stance(canonical, team_id)
    window = WINDOW_FACTOR.get(stance, 0.0)
    level = urgency_level(row)
    # 1. Win-now urgency: a premium for players who help now, while the window is open.
    if window > 0 and level != 0:
        best_out = max((_on_court(canonical, a["id"]) for a in _players(outgoing)), default=0.0)
        help_now = sum(_player_value(canonical, a["id"]) for a in _players(incoming)
                       if _on_court(canonical, a["id"]) >= URGENCY_ON_COURT and _on_court(canonical, a["id"]) > best_out)
        if help_now:
            if level > 0:
                points = min(URGENCY_CAP, level * URGENCY_RATE * help_now * window)
                text = f"{abbrev}'s win-now urgency: it pays a premium while its window is open"
            else:
                points = max(-URGENCY_CAP / 2, level * URGENCY_LOW_RATE * help_now * window)
                text = f"{abbrev} is in no hurry: it will not pay up for help now"
            if abs(points) >= 0.25:
                terms.append(_term("urgency", points, text))
    # 2. Misjudgments of a less savvy office (its lasting biases), and preferences.
    size = misjudgment(row)
    if size > 0 and has_bias(row, "overpays_veterans"):
        vets = [a for a in _players(incoming) if _age(canonical, a["id"]) >= VETERAN_AGE]
        value = sum(_player_value(canonical, a["id"]) for a in vets)
        if value:
            points = min(VETERAN_CAP, size * VETERAN_RATE * value)
            terms.append(_term("overpays_veterans", points,
                               f"{abbrev} tends to overpay for veterans ({', '.join(_name(canonical, a['id']) for a in vets)})"))
    if size > 0 and has_bias(row, "chases_stars"):
        stars = [a for a in _players(incoming) if _player_value(canonical, a["id"]) >= STAR_VALUE]
        value = sum(_player_value(canonical, a["id"]) for a in stars)
        if value:
            points = min(STAR_CAP, size * STAR_RATE * value)
            terms.append(_term("chases_stars", points,
                               f"{abbrev} chases star names ({', '.join(_name(canonical, a['id']) for a in stars)})"))
    picks_out = _picks(outgoing)
    picks_in = _picks(incoming)
    if (size > 0 and has_bias(row, "underrates_picks")) or has_bias(row, "values_picks"):
        from .transactions import package_value_for_team
        out_value = package_value_for_team(canonical, picks_out, team_id) if picks_out else 0.0
        in_value = package_value_for_team(canonical, picks_in, team_id) if picks_in else 0.0
        if size > 0 and has_bias(row, "underrates_picks") and out_value > 0:
            points = min(PICKS_FREE_CAP, size * PICKS_FREE_RATE * out_value)
            terms.append(_term("underrates_picks", points, f"{abbrev} spends draft picks freely"))
        if has_bias(row, "values_picks") and (in_value or out_value):
            points = max(-PICK_PREFERENCE_CAP, min(PICK_PREFERENCE_CAP, PICK_PREFERENCE_RATE * (in_value - out_value)))
            if abs(points) >= 0.25:
                terms.append(_term("values_picks", points, f"{abbrev} prizes draft picks"))
    if size > 0 and has_bias(row, "overrates_own"):
        value = sum(_player_value(canonical, a["id"]) for a in _players(outgoing))
        if value:
            points = -min(OWN_CAP, size * OWN_RATE * value)
            terms.append(_term("overrates_own", points, f"{abbrev} overrates its own players"))
    if tax_term and has_bias(row, "tax_averse"):
        points = max(-TAX_PREFERENCE_CAP, min(TAX_PREFERENCE_CAP, TAX_AVERSE_RATE * tax_term))
        if abs(points) >= 0.25:
            terms.append(_term("tax_averse", points, f"{abbrev} works hard to stay under the luxury tax"))
    if tax_term < 0 and has_bias(row, "spends_tax"):
        points = min(TAX_PREFERENCE_CAP, TAX_SPEND_RATE * -tax_term)
        if points >= 0.25:
            terms.append(_term("spends_tax", points, f"{abbrev} will pay the luxury tax to win"))
    # 3. Player opinions: higher on a player it gets, or on one it gives up.
    for sign, assets in ((1.0, incoming), (-1.0, outgoing)):
        for asset in _players(assets):
            opinion = player_opinion(canonical, team_id, asset["id"])
            if not opinion:
                continue
            points = sign * float(opinion["points"])
            name = _name(canonical, asset["id"])
            if opinion["kind"] == "connection":
                text = f"{abbrev} has a long connection with {name}: {opinion['why']}"
            elif opinion["points"] > 0:
                text = f"{abbrev} has always liked {name} ({opinion['why']} game)"
            else:
                text = f"{abbrev} is lower on {name} than the league ({opinion['why']} game)"
            terms.append(_term("opinion", points, text))
    # 4. Loyalty: attachment to players who have been with the team for years (step 1's tenure premium, scaled).
    loyal = loyalty_level(row)
    if loyal and _players(outgoing):
        from .trade_ownership import own_player_premium
        from .transactions import player_by_id
        tenure = 0.0
        names = []
        for asset in _players(outgoing):
            player = player_by_id(canonical, asset["id"])
            premium = own_player_premium(canonical, player, team_id, _player_value(canonical, asset["id"]))
            if premium.get("tenure"):
                tenure += float(premium["tenure"])
                names.append(_name(canonical, asset["id"]))
        if tenure:
            points = max(-LOYALTY_CAP, min(LOYALTY_CAP, loyal * tenure))
            if abs(points) >= 0.25:
                text = (f"{abbrev} is loyal to its long-time players ({', '.join(names)})" if points > 0 else
                        f"{abbrev} is unsentimental about long-time players ({', '.join(names)})")
                terms.append(_term("loyalty", -points, text))
    # 5. A live negotiation: concessions as patience runs out (trade_market.py).
    from .trade_market import concession_term
    concession = concession_term(canonical, team_id, proposal, incoming, outgoing)
    if concession:
        terms.append(concession)
    total = sum(t["points"] for t in terms)
    capped = max(-PERSONALITY_CAP, min(PERSONALITY_CAP, total))
    return {"total": round(capped, 3), "terms": terms, "uncapped": round(total, 3)}


def pick_allowance(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]] | None = None,
                   outgoing: list[dict[str, Any]] | None = None) -> tuple[float, str | None]:
    """Extra draft value this office will spend on a player who would not start for it (the pick-investment rule):
    urgency while the window is open, a less savvy office that spends picks freely, and the concession of a live
    negotiation or a deadline-day final offer. With the reason."""
    row = office(canonical, team_id)
    if not row:
        return 0.0, None
    extra, reasons = 0.0, []
    if incoming is not None:
        from .trade_market import concession_allowance
        conceded = concession_allowance(canonical, team_id, incoming, outgoing or [])
        if conceded:
            extra += conceded
            reasons.append("final offer" if _today_is_deadline(canonical) else "concession in a long negotiation")
    window = WINDOW_FACTOR.get(_stance(canonical, team_id), 0.0)
    level = urgency_level(row)
    if window > 0 and level > 0:
        extra += URGENCY_PICK_ALLOWANCE * level * window
        reasons.append("win-now urgency")
    if has_bias(row, "underrates_picks"):
        extra += PICKS_FREE_ALLOWANCE * misjudgment(row)
        reasons.append("spends picks freely")
    return round(extra, 3), (f"{row.get('abbrev')}'s {' and '.join(reasons)}" if reasons and extra >= 0.5 else None)


def _today_is_deadline(canonical: dict[str, Any]) -> bool:
    from .trade_market import _today, is_deadline_day
    return is_deadline_day(_today(canonical))


def player_price_terms(canonical: dict[str, Any], team_id: str, player_id: str, *, buying: bool) -> float:
    """Personality points on one player alone, for the target search's quick price screens (asking price and buyer
    value). Same terms as the evaluation, for a one-player deal."""
    asset = [{"kind": "player", "id": player_id}]
    result = personality_terms(canonical, team_id, asset if buying else [], [] if buying else asset)
    return float(result["total"])


REASON_MIN_POINTS = 1.0  # personality terms this large are stated in the trade's reasons


def with_market_reasons(canonical: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Add the personality and market parts to a deal's stated reasons: each personality term of a point or more (by
    team), a final offer, the days of negotiation and a bidding war."""
    reasons = dict(candidate.get("trade_reasons") or {})
    terms, finals = [], []
    for evaluation in candidate.get("evaluations") or []:
        tid = evaluation.get("perspective_team_id")
        for term in (evaluation.get("personality_adjustments") or {}).get("terms") or []:
            points = float(term.get("points") or 0.0)
            if term.get("key") == "final_offer":
                finals.append(_abbrev(canonical, tid))
            if abs(points) >= REASON_MIN_POINTS:
                terms.append({"team_id": tid, "key": term.get("key"), "points": round(points, 2), "text": term.get("text")})
    extra = []
    if terms:
        reasons["personality"] = terms
        extra.append("Personality: " + "; ".join(f"{t['text']} ({t['points']:+.1f})" for t in terms) + ".")
    if finals:
        reasons["final_offer"] = {"by": finals}
    neg = reasons.get("negotiation")
    if neg and neg.get("days", 0) >= 2:
        extra.append(f"Agreed after {neg['days']} days of talks{' and a final offer' if finals else ''}.")
    war = reasons.get("bidding_war")
    if war:
        others = [_abbrev(canonical, t) for t in war.get("bidders") or [] if t != war.get("winner")]
        rounds = len(war.get("rounds") or [])
        extra.append(f"{_abbrev(canonical, war.get('winner'))} won a bidding war against {', '.join(others)}"
                     f" ({rounds} round{'s' if rounds != 1 else ''}).")
    if extra:
        reasons["text"] = " ".join([reasons.get("text") or ""] + extra).strip()
    if reasons:
        candidate = {**candidate, "trade_reasons": reasons}
    return candidate


# ---------------------------------------------------------------------------------------------- the hints

PATIENCE_WORDS = ((75, "very patient: it holds out for its price and rarely makes a final offer before deadline day"),
                  (58, "patient in negotiations"), (42, "neither quick nor slow to deal"),
                  (25, "impatient: it concedes quickly and makes final offers early"),
                  (0, "very impatient: it wants deals done fast"))
URGENCY_WORDS = ((75, "very aggressive when its window is open: it pays a clear premium for help now"),
                 (58, "willing to pay a little extra for help now"), (42, "measured about win-now moves"),
                 (0, "unwilling to pay up for help now"))
SAVVY_WORDS = ((80, "one of the sharpest judges of value in the league"), (65, "a sound judge of value"),
               (45, "uneven in its judgement of value"), (0, "known for misjudging value"))
LOYALTY_WORDS = ((70, "loyal to its long-time players"), (42, "ordinary about long-time players"),
                 (0, "unsentimental about long-time players"))
LEVEL_WORDS = {"savvy": SAVVY_WORDS, "urgency": URGENCY_WORDS, "patience": PATIENCE_WORDS, "loyalty": LOYALTY_WORDS}
COARSE = {"savvy": ("sharp", "average", "error-prone"), "urgency": ("aggressive", "measured", "cautious"),
          "patience": ("patient", "steady", "impatient"), "loyalty": ("loyal", "neutral", "unsentimental")}


def _level_words(trait: str, value: float) -> str:
    return next(words for floor, words in LEVEL_WORDS[trait] if value >= floor)


def _coarse(trait: str, value: float) -> str:
    high, mid, low = COARSE[trait]
    return high if value >= 60 else low if value < 40 else mid


def scouting_lean(canonical: dict[str, Any], team_id: str) -> str | None:
    from .draft_scouting import TASTE_WORDS
    taste = _taste(canonical, team_id)
    if not taste:
        return None
    best = max(taste, key=lambda g: taste[g])
    return TASTE_WORDS.get(best, best) if taste[best] >= 0.8 else None


def office_hints(canonical: dict[str, Any], team_id: str, dealings: int) -> dict[str, Any]:
    """The assistant GM's read on a front office, in words (rule 4: the traits the engine uses; exact numbers hidden).

    Precision grows with dealings with the user's team (trades, negotiations, offers): with none, only widely held
    reputations; then rough levels for every trait; with three or more, the fuller description of each trait and its
    habits."""
    traits = canonical.get("front_office_traits") or {}
    row = traits.get(team_id) or office({**canonical, "_human_team_ids": []}, team_id)
    if not row:
        return {"lines": [], "precision": "none", "dealings": dealings}
    abbrev = row.get("abbrev") or _abbrev(canonical, team_id)
    precision = "reputation" if dealings <= 0 else "rough" if dealings < 3 else "sharp"
    lines = []
    for trait in TRAITS:
        value = float(row[trait])
        known = trait in (row.get("from_reputation") or [])
        if precision == "reputation":
            if known:
                lines.append({"trait": trait, "text": f"Known to be {_level_words(trait, value)}.",
                              "basis": "reputation", "why": (row.get("why") or {}).get(trait),
                              "sources": (row.get("sources") or {}).get(trait) or []})
        elif precision == "rough":
            lines.append({"trait": trait, "text": ROUGH_WORDS[trait].format(_coarse(trait, value)),
                          "basis": "reputation" if known else "dealings"})
        else:
            lines.append({"trait": trait, "text": f"{_level_words(trait, value)[0].upper()}{_level_words(trait, value)[1:]}.",
                          "basis": "reputation" if known else "dealings"})
    for bias in row.get("biases") or []:
        key = bias.get("key")
        words = MISJUDGMENTS.get(key) or PREFERENCES.get(key)
        if not words:
            continue
        documented = bool(bias.get("sources"))
        if key in MISJUDGMENTS and misjudgment(row) <= 0:
            continue
        if precision == "reputation" and not documented:
            continue
        lines.append({"trait": "habit", "text": f"{'Known: it' if documented else 'From your dealings: it'} {words}.",
                      "basis": "reputation" if documented else "dealings", "why": bias.get("why"),
                      "sources": bias.get("sources") or []})
    if precision != "reputation":
        lean = scouting_lean(canonical, team_id)
        if lean:
            lines.append({"trait": "scouting", "text": f"Its scouts lean toward {lean}; it tends to be high on players strong there.",
                          "basis": "dealings"})
    for connection in row.get("connections") or []:
        lines.append({"trait": "connection", "text": f"Close ties to {connection.get('player')}: {connection.get('why')}",
                      "basis": "reputation", "sources": connection.get("sources") or []})
    summary = ", ".join(_coarse(t, float(row[t])) for t in ("savvy", "urgency", "patience")) if precision != "reputation" else None
    return {"team_id": team_id, "abbrev": abbrev, "lines": lines, "precision": precision, "dealings": dealings,
            "summary": summary, "regime_new": bool(row.get("regime_new"))}


TRAIT_LABELS = {"savvy": "judging value", "urgency": "win-now urgency", "patience": "patience", "loyalty": "loyalty"}
ROUGH_WORDS = {"savvy": "Seems {} at judging value.", "urgency": "Seems {} about win-now moves.",
               "patience": "Seems {} in negotiations.", "loyalty": "Seems {} about long-time players."}
