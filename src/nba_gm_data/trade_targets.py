"""Target-driven AI trade search: each front office starts from what it is looking for (trade AI step 2).

Step 3 of the order of work in docs/agents/TRADE_AI_DIRECTION.md; report in docs/agents/tasks/trade-step2-targets.md.

How a front office works here, in the user's words: it starts from a target, specific or a profile ("a starting-level
wing who can shoot, under $25M"), that fits its phase and plan; it looks at its options and alternatives at a
reasonable price; wanting a player doesn't mean getting him (the seller has its own price). So instead of offering
packages for every listed player to every interested team (the old brute-force search), each AI team:

1. sets a few **targets** from its phase and roster (``team_trade_targets``), each with a plain-language reason;
2. every team lists who it **would move and why** (``team_sell_reasons``: step 1's move reasons plus tax, expiring
   veterans on teams that are not contending, and players out of the rotation);
3. the search pairs each target with the players that match it, preferring players a seller would move; players on
   teams with no reason to sell are still possible, at that team's higher own price (step 1's own-player premium is
   not scaled down when the team has no reason to move him);
4. it only pursues a pairing when the buyer values the player about as much as the seller's **asking price**
   (``asking_price``), builds packages aimed at that price, prices them quickly from both sides and sends only the
   few best to the unchanged acceptance check (``transactions.evaluate_trade_decision``), which stays the judge.

Grounding in real trades (data/research/real_trades/trades_2025_2027.json, 43 trades with context). Reading who
bought what, by the buyer's situation:
- Contenders (OKC, CLE, BOS, NYK, LAL, MIN, GSW, DET, MIA, PHI, TOR): mostly a rotation player at a position of need
  or to cover an injury (Clifford, Alvarado, Porzingis, Vucevic, Kennard, Dosunmu, McCain, Huerter), a few stars
  (Harden, Giannis, LaMelo Ball, Jaylen Brown, Kawhi Leonard), paid with picks, expiring salary and young non-core
  players. Ages of the rotation targets ran 21 to 36; stars 26 to 34.
- Rebuilders (MEM, CHI, LAC, MIL, CHA, ATL, UTA): young players with upside (Dillingham 21, Ivey 24, Kuminga 23,
  Mathurin 23, Hendricks 22, Clayton 22, Ware 22, Jakucionis 20, Risacher 21) and picks; veterans only as expiring
  salary that came with a pick (Simons + a second, Conley, Vincent + a second) or as salary absorbed for seconds
  (Saric, Finney-Smith, LeVert). No rebuilder took a 30+ veteran on a long deal without being paid for it.
- Middle teams (WAS, IND, POR, DAL, CHA in 2026): a fit need (a scoring guard, a center upgrade, shooting) or a young
  starter (Morant 26, Risacher 21).
- Sellers' stated reasons: rebuild sell (veterans for picks/youth), tax or apron savings (12 of the 43), a crowded
  position, a player wanting out (Trae Young, Jaylen Brown), an expiring player the team would lose anyway.

Everything here reads the league and never writes it, and the human team is never a buyer or seller in this search
(its offers come from the separate user-offer search, unchanged).
"""
from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------------------------- plain-language words
STANCE_WORDS = {"contend": "contending", "rise": "on the rise", "retool": "retooling", "rebuild": "rebuilding"}
BUCKET_WORDS = {"guard": "guard", "wing": "wing", "big": "big"}
SKILL_NEEDS = (
    # team feature, words, player attribute used to match
    ("spacing", "shooting", "range"),
    ("rim_deterrence", "rim protection", "rim_deterrence"),
    ("defensive_events", "perimeter defense", "defense"),
    ("primary_creator", "shot creation", "creation"),
    ("passing", "playmaking", "passing"),
    ("offensive_rebounding", "rebounding", "rebounding"),
    ("rim_pressure", "rim pressure", "rim_pressure"),
)
SELL_REASON_WORDS = {
    "older_than_team_timeline": "a veteran older than its timeline",
    "extension_talks_stalled": "contract talks had stalled",
    "gm_listed": "he was on the trade block",
    "negative_contract_value": "his contract pays more than he gives",
    "upgradeable_expensive_rotation_slot": "an expensive role player it wanted to upgrade",
    "position_surplus": "a surplus at his position",
    "veteran_surplus_slot": "a veteran surplus at his position",
    "blocked_prospect": "a young player blocked from minutes",
    "health_risk_for_win_now_team": "a health risk for a win-now team",
    "planned_core_retool_not_full_teardown": "retooling around a younger core",
    "over_tax_line": "getting under the luxury tax",
    "expiring_veteran_non_contender": "an expiring veteran it would otherwise lose for nothing",
    "out_of_rotation": "a player out of its rotation",
}
# How strongly each reason makes the seller want to move the player (search order only; the price itself is
# step 1's own-player premium, already scaled by the same move reasons).
SELL_REASON_STRENGTH = {
    "gm_listed": 3.0, "extension_talks_stalled": 3.0, "older_than_team_timeline": 3.0,
    "planned_core_retool_not_full_teardown": 2.5, "negative_contract_value": 2.0, "over_tax_line": 2.0,
    "expiring_veteran_non_contender": 2.5, "upgradeable_expensive_rotation_slot": 2.0, "veteran_surplus_slot": 1.5,
    "position_surplus": 1.0, "blocked_prospect": 1.5, "health_risk_for_win_now_team": 1.0, "out_of_rotation": 1.0,
}

# Search sizes. Deadline-depth searches (search_depth >= 2) explore more alternatives and packages per target.
TARGETS_PER_TEAM = 5                    # TRADE-VOLUME-2: up to three plan targets plus the two market targets
ALTERNATIVES = {1: 3, 2: 5}             # players explored per target
MATCHES_SCANNED = 24                    # best-fitting players checked for a price both sides could agree on
PACKAGES_EVALUATED = {1: 3, 2: 6}       # packages sent to the full acceptance check per pairing
ZONE_TOLERANCE = 4.0                    # the buyer's value plus what its spare assets are worth extra to the
                                        # seller may sit this far below the seller's ask
PRESCREEN_TOLERANCE = 4.0               # quick price check, before the personality, wants and roster terms


def _tx():
    from . import transactions
    return transactions


def _memo(canonical: dict[str, Any]) -> dict[str, Any]:
    """Per-search memo: a search context's league objects are never edited while the search runs."""
    memo = canonical.get("_trade_target_memo")
    if memo is None or memo.get("players_source") is not canonical.get("players"):
        memo = {"players_source": canonical.get("players")}
        canonical["_trade_target_memo"] = memo
    return memo


def _state(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    return next((s for s in canonical.get("team_strategic_states", []) if s.get("team_id") == team_id), {}) or {}


def team_stance(state: dict[str, Any]) -> str:
    """Contend / rise / retool / rebuild from the league-relative window (team_planning.window_assessments)."""
    window = state.get("window_phase")
    phase = state.get("phase")
    if window == "peak" or (window is None and phase in {"contending", "contending_with_future_upside"}):
        return "contend"
    if window == "rebuilding" or (window is None and phase == "rebuilding"):
        return "rebuild"
    if window == "exiting" or (window is None and phase == "retooling"):
        return "retool"
    return "rise"


def _season(canonical: dict[str, Any]) -> str:
    tx = _tx()
    return str((canonical.get("meta") or {}).get("active_season") or tx.CANONICAL_SEASON)


def player_rows(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Facts the targets read, one row per rostered player (memoized per search)."""
    memo = _memo(canonical)
    if "rows" in memo:
        return memo["rows"]
    tx = _tx()
    from .save import player_display_attribute_summary
    values = tx.player_asset_values_by_id(canonical)
    season = _season(canonical)
    rows = {}
    for player in canonical.get("players", []):
        team_id = player.get("team_id")
        if not team_id or player.get("_inactive_player"):
            continue
        valuation = tx.valuation_or_fallback(values, player["id"], player)
        contract = tx.contract_for_player(canonical, player["id"]) or {}
        seasons = [s for s in contract.get("seasons", []) if float(s.get("salary") or 0) > 0
                   and str(s.get("season") or "") >= season]
        salary = tx.current_salary(contract) or 0.0
        try:
            attrs = player_display_attribute_summary(canonical, player["id"])
        except Exception:  # a player without inputs still trades on value; he just matches no skill target
            attrs = {}
        rows[player["id"]] = {
            "id": player["id"], "name": player.get("name"), "team_id": team_id, "player": player,
            "age": float(player.get("display_age", player.get("age")) or 27.0),
            "bucket": tx.player_position_bucket(player),
            "minutes": tx.trade_value_role_minutes(player, valuation),
            "on_court": float(valuation.get("on_court_value") or 0.0),
            "playoff": float(valuation.get("playoff_value") or 0.0),
            "value": float(valuation.get("player_value") or 0.0),
            "market": tx._search_market_value(canonical, player, valuation),
            "development": float(valuation.get("development_upside") or 0.0),
            "surplus": float(valuation.get("contract_surplus") or 0.0),
            "health": float(valuation.get("health_risk") or 0.0),
            "salary": salary,
            "years": len(seasons) or (1 if salary else 0),
            "attrs": {key: float(attrs.get(key) or 0.0) for _, _, key in SKILL_NEEDS},
        }
    memo["rows"] = rows
    return rows


def _team_rows(canonical: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    return [row for row in player_rows(canonical).values() if row["team_id"] == team_id]


def _payroll(canonical: dict[str, Any], team_id: str) -> float:
    return _tx().team_current_salary_total(canonical, team_id)


def _tax_line(canonical: dict[str, Any]) -> float:
    return _tx().cap_lines_for_season(_season(canonical))["tax_line"]


SLOT_DEPTH = {"guard": 3, "wing": 3, "big": 2}
REPLACEMENT_ON_COURT = 42.0


def position_slots(canonical: dict[str, Any], team_id: str) -> dict[str, dict[str, Any]]:
    """For each position group: the quality of the team's last regular slot (3rd guard, 3rd wing, 2nd big)."""
    healthy = [row for row in _team_rows(canonical, team_id) if row["minutes"] >= 4.0]
    out = {}
    for bucket, depth in SLOT_DEPTH.items():
        group = sorted((row for row in healthy if row["bucket"] == bucket), key=lambda r: -r["on_court"])
        top = [row["on_court"] for row in group[:depth]] + [REPLACEMENT_ON_COURT] * max(0, depth - len(group))
        out[bucket] = {"slot_quality": top[depth - 1], "average": sum(top) / depth, "count": len(group)}
    return out


def league_slot_averages(canonical: dict[str, Any]) -> dict[str, float]:
    memo = _memo(canonical)
    if "slot_averages" not in memo:
        teams = [t["id"] for t in canonical.get("teams", [])]
        slots = [position_slots(canonical, tid) for tid in teams]
        memo["slot_averages"] = {bucket: sum(s[bucket]["average"] for s in slots) / max(1, len(slots))
                                 for bucket in SLOT_DEPTH}
    return memo["slot_averages"]


def skill_gaps(canonical: dict[str, Any], team_id: str) -> list[tuple[float, str, str]]:
    """The team's skills relative to the league (z-scores of its rotation features), weakest first."""
    memo = _memo(canonical)
    if "features" not in memo:
        from .sim import team_feature_vector
        memo["features"] = {team["id"]: team_feature_vector(canonical, team, include_spatial=False).features
                            for team in canonical.get("teams", [])}
    features = memo["features"]
    gaps = []
    for feature, words, attr in SKILL_NEEDS:
        values = [float(f.get(feature) or 50.0) for f in features.values()]
        mean = sum(values) / len(values)
        spread = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5 or 1.0
        gaps.append(((float(features.get(team_id, {}).get(feature) or 50.0) - mean) / spread, words, attr))
    return sorted(gaps)


def _matchable_salary(canonical: dict[str, Any], team_id: str) -> float:
    """Roughly the largest incoming salary the team can match from players outside its core."""
    plan = (canonical.get("team_plans") or {}).get(team_id) or {}
    core = set(plan.get("core_ids") or [])
    salaries = sorted((row["salary"] for row in _team_rows(canonical, team_id) if row["id"] not in core), reverse=True)
    return sum(salaries[:3]) * 1.25 + 5_000_000


# --------------------------------------------------------------------------------------------------- targets
def team_trade_targets(canonical: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    """A few targets for this front office this trade window, each with its reason in plain words.

    Profiles, not lists of names: the search finds the players who fit (the best fit is the specific target, the rest
    are the alternatives). Contenders look for rotation upgrades at their weakest position or skill and, with the
    assets for it, a playoff-level player; rebuilders look for young players with upside; teams on the rise look for
    fit and young starters; retooling teams look for a younger successor to an aging core player.
    """
    memo = _memo(canonical).setdefault("targets", {})
    if team_id in memo:
        return memo[team_id]
    tx = _tx()
    state = _state(canonical, team_id)
    stance = team_stance(state)
    plan = (canonical.get("team_plans") or {}).get(team_id) or {}
    roster = _team_rows(canonical, team_id)
    if not state or not roster:
        memo[team_id] = []
        return []
    slots = position_slots(canonical, team_id)
    league = league_slot_averages(canonical)
    weakest = max(SLOT_DEPTH, key=lambda b: (league[b] - slots[b]["average"], b))
    weak_slot = slots[weakest]["slot_quality"]
    gap_z, skill_words, skill_attr = skill_gaps(canonical, team_id)[0]
    # The evaluation values an incoming player by the minutes he would play here (his on-court rank on this roster),
    # so a target has to be good enough to take a real role: "nth(k)" is the on-court value of the team's k-th best.
    order = sorted((r["on_court"] for r in roster if r["minutes"] >= 4.0 or r["on_court"] >= 50.0), reverse=True)
    nth = lambda k: order[min(k, len(order)) - 1] if order else 45.0
    second_best = nth(2)
    matchable = _matchable_salary(canonical, team_id)
    firsts = int((state.get("pick_inventory") or {}).get("first_round_count") or 0)
    targets: list[dict[str, Any]] = []

    def add(key, label, reason, **filters):
        targets.append({"id": f"{team_id}:{key}", "team_id": team_id, "stance": stance, "key": key,
                        "label": label, "reason": reason, "filters": filters})

    position = BUCKET_WORDS[weakest]
    if stance == "contend":
        add("rotation_upgrade", f"a {position} for its top six", f"its {position} rotation is the thinnest part of "
            f"a contending roster", buckets={weakest}, min_on_court=max(weak_slot + 3.0, nth(6) + 1.0),
            min_playoff=56.0, age_min=21.0, age_max=35.0, max_salary=min(matchable, 32e6))
        if gap_z < -0.3:
            add("skill", f"a rotation player who adds {skill_words}", f"its rotation is short on {skill_words}",
                skill=(skill_attr, 60.0), min_on_court=nth(7) + 1.0, min_playoff=54.0, age_min=21.0,
                age_max=35.0, max_salary=min(matchable, 25e6))
        if firsts >= 2 or float(state.get("pressure") or 55) >= 70:
            add("star", "a playoff-level starter", "a contender pushing for a title with picks to spend",
                min_on_court=max(68.0, second_best - 2.0), min_playoff=68.0, age_min=21.0, age_max=33.0,
                max_salary=min(matchable, 55e6), seller_reason_required=True)
    elif stance == "rebuild":
        # Real rebuilders took young players from teams competing now, where they were surplus (Dillingham,
        # Kuminga, Mathurin, Hendricks); rebuilders do not sell each other their young players.
        add("prospect", "a young player who would play", "a rebuild collects young players to develop",
            age_max=23.5, min_development=6.0, min_on_court=nth(8), max_salary=20e6, max_years=4,
            no_bad_contract=True, seller_stances={"contend", "rise"})
        add("young_starter", f"a young {position} who can start", f"a rebuild needs a young {position} to build around",
            buckets={weakest}, age_max=25.5, min_on_court=max(56.0, weak_slot, nth(5)), max_salary=min(matchable, 28e6),
            no_bad_contract=True, seller_stances={"contend", "rise", "retool"})
    elif stance == "retool":
        core = set(plan.get("core_ids") or [])
        aging = sorted((r for r in roster if r["id"] in core and r["age"] >= 30.0), key=lambda r: -r["age"])
        if aging:
            old = aging[0]
            add("successor", f"a younger {BUCKET_WORDS[old['bucket']]} to succeed {old['name']}",
                f"{old['name']} is {old['age']:.0f} and the team is retooling around a younger core",
                buckets={old["bucket"]}, age_max=27.0, min_on_court=max(55.0, old["on_court"] - 8.0, nth(5)),
                max_salary=min(matchable, 32e6), no_bad_contract=True)
        if gap_z < -0.3:
            add("skill", f"a younger rotation player who adds {skill_words}", f"short on {skill_words} while retooling",
                skill=(skill_attr, 58.0), min_on_court=nth(7) + 1.0, age_max=29.0, max_salary=min(matchable, 22e6),
                no_bad_contract=True)
        add("prospect", "a young player who would play", "restocking young talent while retooling",
            age_max=23.5, min_development=6.0, min_on_court=nth(7), max_salary=15e6, no_bad_contract=True,
            seller_stances={"contend", "rise"})
    else:  # rise
        add("rotation_upgrade", f"a {position} for its top six", f"a rising team filling its thinnest position "
            f"({position})", buckets={weakest}, min_on_court=max(weak_slot + 3.0, nth(6) + 1.0), age_max=30.0,
            max_salary=min(matchable, 28e6), max_years=4)
        if gap_z < -0.3:
            add("skill", f"a rotation player who adds {skill_words}", f"its rotation is short on {skill_words}",
                skill=(skill_attr, 60.0), min_on_court=nth(7) + 1.0, age_max=31.0, max_salary=min(matchable, 25e6))
        add("young_starter", "a young starter", "a rising team adding a young starter to its core",
            age_max=25.5, min_on_court=max(60.0, nth(5)), max_salary=min(matchable, 30e6), no_bad_contract=True)
    if stance in {"contend", "rise"}:
        add_market_targets(add, stance, roster, slots, nth, matchable)
    targets = targets[:TARGETS_PER_TEAM]
    memo[team_id] = targets
    return targets


# TRADE-VOLUME-2: the two most common real deals the targets above never asked for. In the real 2025-27 trade list
# (data/research/real_trades/trades_2025_2027.json) competing teams bought proven veterans that non-contenders were
# selling, whatever the position (rebuild sales: Dosunmu, Vucevic, Conley, Middleton, Huerter; the most common real
# trade after tax moves), and swapped or bought bench players to shore up a thin spot (Kennard, Alvarado, Isaiah
# Joe, Aaron Wiggins; the "value-neutral role swaps"). The search above only looked for a top-six player at the
# single thinnest position or one skill, so none of those were ever pursued.
BACKUP_UPGRADE = 8.0


def add_market_targets(add, stance: str, roster: list[dict[str, Any]], slots: dict[str, dict[str, Any]], nth,
                       matchable: float) -> None:
    contend = stance == "contend"
    add("seller_veteran", "a proven rotation player from a team that is selling",
        ("a contending team adding a proven player that a non-contender was selling" if contend
         else "a rising team adding a proven player that a non-contender was selling"),
        min_on_court=nth(8) + 1.0, min_playoff=52.0 if contend else 0.0, age_min=24.0,
        age_max=34.0 if contend else 31.0, max_salary=min(matchable, 35e6), max_years=99 if contend else 3,
        seller_stances={"rebuild", "retool"}, seller_reason_required=True)
    # Depth: the position group with the weakest backup (its second-best player, or the third guard or wing).
    def backup_quality(bucket: str) -> float:
        group = sorted((r["on_court"] for r in roster if r["bucket"] == bucket and r["minutes"] >= 4.0), reverse=True)
        depth = SLOT_DEPTH[bucket]
        return (group + [REPLACEMENT_ON_COURT] * depth)[depth - 1]
    thin = min(SLOT_DEPTH, key=lambda b: (backup_quality(b), b))
    # A real upgrade on the backup (8+ points of on-court value): the acceptance check lets a team spend draft capital
    # on a non-starter only for measured depth (trade_roster.pick_investment_outlook, 0.6 per point of backup gain).
    add("backup", f"a backup {BUCKET_WORDS[thin]}", f"its {BUCKET_WORDS[thin]} depth behind the starters is thin",
        buckets={thin}, min_on_court=max(backup_quality(thin) + BACKUP_UPGRADE, nth(10)), age_min=22.0, age_max=34.0,
        max_salary=min(matchable, 15e6), max_years=3, seller_reason_required=True)


def target_match(target: dict[str, Any], row: dict[str, Any]) -> float | None:
    """How well a player fits a target (higher is better), or None if he doesn't fit it."""
    f = target["filters"]
    if f.get("buckets") and row["bucket"] not in f["buckets"]:
        return None
    if row["age"] < f.get("age_min", 0.0) or row["age"] > f.get("age_max", 99.0):
        return None
    if row["on_court"] < f.get("min_on_court", 0.0) or row["playoff"] < f.get("min_playoff", 0.0):
        return None
    if row["development"] < f.get("min_development", -99.0):
        return None
    if row["salary"] > f.get("max_salary", 1e12) or row["years"] > f.get("max_years", 99):
        return None
    if f.get("no_bad_contract") and row["surplus"] < -8.0:
        return None
    if row["health"] >= 30.0:
        return None
    score = (row["on_court"] - f.get("min_on_court", 0.0)) * 0.5
    if f.get("skill"):
        attr, minimum = f["skill"]
        if row["attrs"].get(attr, 0.0) < minimum:
            return None
        score += (row["attrs"][attr] - minimum) * 0.4
    if target["key"] in {"prospect", "young_starter"}:
        score += row["development"] * 0.3 + max(0.0, 24.0 - row["age"]) * 0.5
    return round(score, 3)


# ------------------------------------------------------------------------------------------------ sellers
def team_sell_reasons(canonical: dict[str, Any], team_id: str) -> dict[str, list[str]]:
    """Who this team would move and why: step 1's move reasons plus players out of the rotation."""
    memo = _memo(canonical).setdefault("sellers", {})
    if team_id in memo:
        return memo[team_id]
    from .trade_ownership import move_reasons
    from .team_planning import core_commitment
    plan = (canonical.get("team_plans") or {}).get(team_id) or {}
    core = set(plan.get("core_ids") or [])
    out = {}
    for row in _team_rows(canonical, team_id):
        if core_commitment(canonical, team_id, row["id"]):
            continue
        reasons = sorted(move_reasons(canonical, row["player"], team_id, core=row["id"] in core))
        if row["minutes"] < 10.0 and row["age"] >= 24.0 and row["id"] not in core:
            reasons.append("out_of_rotation")
        if reasons:
            out[row["id"]] = reasons
    memo[team_id] = out
    return out


# TRADE-DEADLINE: salary a buyer would rather move. The deadline funnel (docs/agents/tasks/trade-volume-2.md) showed
# that buyers matched salary with rotation players they valued, so the two sides' prices rarely met. Real contenders
# match with contracts they don't want: out of the rotation, overpaid, injured for a long time, or an expiring bench
# deal (Harden for Garland's longer deal; the Lakers' and Warriors' bench salary at the 2025 and 2026 deadlines;
# data/research/real_trades/trades_2025_2027.json). The seller still prices every player it takes with its own check,
# so negative-value filler needs picks attached.
FILLER_REASONS = frozenset({"negative_contract_value", "out_of_rotation", "over_tax_line", "veteran_surplus_slot",
                            "health_risk_for_win_now_team", "upgradeable_expensive_rotation_slot", "gm_listed",
                            "older_than_team_timeline", "expiring_veteran_non_contender", "position_surplus"})
FILLER_MIN_SALARY = 2_500_000
FILLER_LONG_INJURY_DAYS = 30
FILLER_BENCH_MINUTES = 15.0
FILLER_PER_BUYER = 3


def salary_filler(canonical: dict[str, Any], team_id: str) -> dict[str, str]:
    """The team's "salary I'd move" list for matching salary in its own offers: player id -> why, most movable first
    (at most FILLER_PER_BUYER). Never a core player, a young piece the team builds around or a recent draft pick."""
    memo = _memo(canonical).setdefault("filler", {})
    if team_id in memo:
        return memo[team_id]
    tx = _tx()
    from .team_planning import core_commitment
    plan = (canonical.get("team_plans") or {}).get(team_id) or {}
    core = set(plan.get("core_ids") or [])
    stance = team_stance(_state(canonical, team_id))
    reasons = team_sell_reasons(canonical, team_id)
    today = tx.parse_iso_date((canonical.get("meta") or {}).get("current_date"))
    injured = {}
    for health in canonical.get("player_health_states") or []:
        end = tx.parse_iso_date(health.get("return_date"))
        if health.get("availability_status") == "out" and today and end and (end - today).days >= FILLER_LONG_INJURY_DAYS:
            injured[health.get("player_id")] = (end - today).days
    found = []
    for row in _team_rows(canonical, team_id):
        if (row["id"] in core or row["salary"] < FILLER_MIN_SALARY or core_commitment(canonical, team_id, row["id"])
                or young_piece_kept(row, stance) or recent_draft_pick(canonical, row["player"])):
            continue
        why = next((r for r in reasons.get(row["id"], []) if r in FILLER_REASONS), None)
        if why is None and row["id"] in injured:
            why = "long_term_injury"
        if why is None and row["years"] <= 1 and row["minutes"] < FILLER_BENCH_MINUTES and row["age"] >= 24.0:
            why = "expiring_bench_salary"
        if why is not None:
            found.append((row["minutes"], -row["salary"], row["id"], why))
    found.sort()
    memo[team_id] = {pid: why for _, _, pid, why in found[:FILLER_PER_BUYER]}
    return memo[team_id]


YOUNG_PIECE_AGE = 25.5
YOUNG_STARTER_MINUTES = 24.0


def young_piece_kept(row: dict[str, Any], seller_stance: str) -> bool:
    """Young players a team builds around are not on the market unless the team has its own reason to move them:
    every young player (25 or younger) on a rebuilding or retooling team, and young starters (24+ minutes) anywhere.
    A blocked prospect on a team competing now is still available (the Dillingham / Kuminga pattern). The first
    two-season run without this rule had rebuilders selling 21-year-old starters (Knueppel, Acuff, Flemings) to
    teams that happened to target them, at prices the acceptance check allowed."""
    if row["age"] > YOUNG_PIECE_AGE:
        return False
    return seller_stance in {"rebuild", "retool"} or row["minutes"] >= YOUNG_STARTER_MINUTES


# Reasons that never put a young player a team builds around on the market (trade 2b, the user's direction: young
# starters are highly valuable and are not sold for tax savings). In step 2, San Antonio sold Stephon Castle (23, 34
# minutes) because it was over the tax. A team can still trade one in a real deal: as part of its own offer for a
# target, or when it has a reason of its own (a listing, stalled contract talks, a blocked prospect, a bad contract).
MONEY_ONLY_REASONS = frozenset({"over_tax_line", "expiring_veteran_non_contender", "out_of_rotation"})


def exposing_reasons(reasons: list[str]) -> list[str]:
    """The reasons that can put a young piece on the market (money reasons alone cannot)."""
    return [r for r in reasons if r not in MONEY_ONLY_REASONS]


def sell_strength(reasons: list[str]) -> float:
    return max((SELL_REASON_STRENGTH.get(r, 1.0) for r in reasons), default=0.0)


def asking_price(canonical: dict[str, Any], seller_id: str, player_id: str, config: dict[str, Any]) -> dict[str, float]:
    """The seller's own price for the player: what it loses (step 1's own value, premium scaled by its reasons to
    sell), plus its acceptance margin and the contender's playoff-player term. In the same units as the trade
    evaluation, so a package the seller values at least this much passes its price check."""
    memo = _memo(canonical).setdefault("asks", {})
    key = (seller_id, player_id)
    if key in memo:
        return memo[key]
    tx = _tx()
    asset = [{"kind": "player", "id": player_id}]
    own = tx.package_value_for_team(canonical, asset, seller_id)
    strategic = tx.strategic_fit_adjustment(canonical, [], asset, seller_id, config)
    threshold = tx.acceptance_threshold(canonical, seller_id, config)
    # Tax the seller saves by moving him (trade 2b). A package usually brings some salary back, so half of the saving
    # with nothing back is counted here; the packages are then priced exactly (quick_net, the acceptance check).
    from .trade_tax import tax_value
    tax = 0.5 * max(0.0, tax_value(canonical, seller_id, [], asset))
    memo[key] = {"own": own, "ask": own - strategic - tax + threshold, "threshold": threshold, "tax": tax}
    return memo[key]


def buyer_value(canonical: dict[str, Any], buyer_id: str, player_id: str, config: dict[str, Any]) -> float:
    tx = _tx()
    asset = [{"kind": "player", "id": player_id}]
    return tx.package_value_for_team(canonical, asset, buyer_id) + tx.strategic_fit_adjustment(canonical, asset, [], buyer_id, config)


def trade_surplus(canonical: dict[str, Any], buyer_id: str, seller_id: str, player_id: str, excluded: set[str],
                  config: dict[str, Any]) -> float:
    """How much more the seller values the buyer's best spare assets than the buyer does (the two best players or
    picks): a bench player who would start for the seller, or a pick a rebuilder prizes and a contender doesn't.
    This is the room a package can add on top of the buyer's value for the target."""
    tx = _tx()
    from .team_planning import core_commitment
    memo = _memo(canonical).setdefault("surplus", {})
    key = (buyer_id, seller_id, player_id)
    if key in memo:
        return memo[key]
    target_out = [{"kind": "player", "id": player_id}]
    gains = []
    for row in _team_rows(canonical, buyer_id):
        if row["id"] in excluded or core_commitment(canonical, buyer_id, row["id"]):
            continue
        asset = [{"kind": "player", "id": row["id"]}]
        gains.append(tx.package_value_for_team(canonical, asset, seller_id, outgoing_assets=target_out)
                     - tx.package_value_for_team(canonical, asset, buyer_id))
    for pick in tx.tradeable_picks_for_team(canonical, buyer_id):
        asset = [{"kind": "pick", "id": pick["id"]}]
        gains.append(tx.package_value_for_team(canonical, asset, seller_id)
                     + tx.strategic_fit_adjustment(canonical, asset, [], seller_id, config)
                     - tx.package_value_for_team(canonical, asset, buyer_id)
                     + tx.strategic_fit_adjustment(canonical, [], asset, buyer_id, config))
    best = sorted((g for g in gains if g > 0), reverse=True)[:2]
    memo[key] = sum(best)
    return memo[key]


def quick_net(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]], outgoing: list[dict[str, Any]],
              config: dict[str, Any]) -> float:
    """The price part of the team's evaluation (incoming minus outgoing plus phase and tax terms), without the personality,
    wants, roster-space and final-roster terms. Used only to choose which packages to send to the real check."""
    tx = _tx()
    from .trade_tax import money_value
    return (tx.package_value_for_team(canonical, incoming, team_id, outgoing_assets=outgoing)
            - tx.package_value_for_team(canonical, outgoing, team_id)
            + tx.strategic_fit_adjustment(canonical, incoming, outgoing, team_id, config)
            + money_value(canonical, team_id, incoming, outgoing))


# ------------------------------------------------------------------------------------------------ search
def target_pairings(canonical: dict[str, Any], buyer_ids: list[str], excluded: set[str], depth: int,
                    config: dict[str, Any], rng) -> list[dict[str, Any]]:
    """Each buyer's targets matched to players, best few per target, ordered for the search."""
    tx = _tx()
    from .team_planning import core_commitment
    rows = player_rows(canonical)
    human = set(canonical.get("_human_team_ids") or [])
    alternatives = ALTERNATIVES[min(2, depth)]
    pairings = []
    for buyer_id in buyer_ids:
        for rank, target in enumerate(team_trade_targets(canonical, buyer_id)):
            matches = []
            for row in rows.values():
                if row["team_id"] == buyer_id or row["team_id"] in human or row["id"] in excluded:
                    continue
                score = target_match(target, row)
                if score is not None and core_commitment(canonical, row["team_id"], row["id"]):
                    continue  # the seller is committed to him for this window
                if score is None:
                    continue
                reasons = team_sell_reasons(canonical, row["team_id"]).get(row["id"], [])
                if target["filters"].get("seller_reason_required") and not reasons:
                    continue
                seller_stance = team_stance(_state(canonical, row["team_id"]))
                stances = target["filters"].get("seller_stances")
                if stances and seller_stance not in stances:
                    continue
                if young_piece_kept(row, seller_stance) and not exposing_reasons(reasons):
                    continue
                matches.append((score + 4.0 * sell_strength(reasons), row, reasons))
            matches.sort(key=lambda m: (-m[0], m[1]["id"]))
            kept = []
            for score, row, reasons in matches[:MATCHES_SCANNED]:
                if tx.effectively_untouchable(canonical, row["player"]):
                    continue
                ask = asking_price(canonical, row["team_id"], row["id"], config)
                value = buyer_value(canonical, buyer_id, row["id"], config)
                zone = value - ask["ask"]
                if zone < -ZONE_TOLERANCE - 40.0:
                    continue  # no package of spare assets closes a gap this large
                zone += trade_surplus(canonical, buyer_id, row["team_id"], row["id"], excluded, config)
                if zone < -ZONE_TOLERANCE:
                    continue
                kept.append({"buyer_id": buyer_id, "target": target, "rank": rank, "row": row, "reasons": reasons,
                             "ask": ask, "buyer_value": value, "zone": zone,
                             "buyer_minutes": buyer_minutes(canonical, buyer_id, row),
                             "priority": score + min(zone, 10.0) * 0.5})
                if len(kept) >= alternatives:
                    break
            pairings.extend(kept)
    # Interleave: every team's first target before anyone's second, best pairings first within a round, with a
    # small seeded shuffle so the same pairing does not lead every day.
    jitter = {id(p): rng.random() for p in pairings}
    pairings.sort(key=lambda p: (p["rank"], -(p["priority"] + jitter[id(p)] * 4.0), p["buyer_id"], p["row"]["id"]))
    return pairings


def stance_words(canonical: dict[str, Any], team_id: str) -> str:
    return STANCE_WORDS[team_stance(_state(canonical, team_id))]


def trade_reasons(canonical: dict[str, Any], pairing: dict[str, Any]) -> dict[str, Any]:
    """Why each side made the deal, in plain words (stored on the trade and its log)."""
    tx = _tx()
    buyer = tx.team_by_id(canonical, pairing["buyer_id"])
    seller = tx.team_by_id(canonical, pairing["row"]["team_id"])
    target = pairing["target"]
    name = pairing["row"]["name"]
    reasons = [SELL_REASON_WORDS.get(r, r.replace("_", " ")) for r in pairing["reasons"]]
    buyer_text = (f"{buyer['abbrev']} ({stance_words(canonical, buyer['id'])}) targeted {target['label']}: "
                  f"{target['reason']}, and chose {name}")
    if reasons:
        seller_text = f"{seller['abbrev']} ({stance_words(canonical, seller['id'])}) moved him as {reasons[0]}"
    else:
        seller_text = (f"{seller['abbrev']} ({stance_words(canonical, seller['id'])}) had no plan to move him "
                       f"but took an offer at its own price")
    return {"buyer_team_id": buyer["id"], "seller_team_id": seller["id"], "target_id": target["id"],
            "target_key": target["key"], "target_label": target["label"], "target_reason": target["reason"],
            "player_id": pairing["row"]["id"], "seller_reasons": list(pairing["reasons"]),
            "asking_price": round(pairing["ask"]["ask"], 2), "buyer_value": round(pairing["buyer_value"], 2),
            "text": f"{buyer_text}; {seller_text}."}


def buyer_minutes(canonical: dict[str, Any], buyer_id: str, row: dict[str, Any]) -> float:
    """Minutes the target would get on the buyer, from his on-court rank there (as the evaluation prices him)."""
    tx = _tx()
    better = sum(1 for other in _team_rows(canonical, buyer_id) if other["on_court"] > row["on_court"])
    return tx.expected_minutes_for_destination_rank(better + 1)


def package_fits_rules(canonical: dict[str, Any], pairing: dict[str, Any], assets: list[dict[str, Any]]) -> bool:
    """Cheap versions of the acceptance check's hard rules, so packages that must fail are never sent to it:
    a premium player needs a comparable return; a team competing now does not give up a rotation player without a
    like-for-like player back (unless he is a costly contract it is exiting); and a buyer does not spend more than a
    couple of seconds' worth of picks on a player who would not play starter minutes for it."""
    tx = _tx()
    row = pairing["row"]
    seller_id, buyer_id = row["team_id"], pairing["buyer_id"]
    target = [{"kind": "player", "id": row["id"]}]
    if tx.premium_return_issue(canonical, seller_id, assets, target):
        return False
    rows = player_rows(canonical)
    incoming = [rows[a["id"]] for a in assets if a.get("kind") == "player" and a.get("id") in rows]
    seller_state = _state(canonical, seller_id)
    competitive = (seller_state.get("window_phase") in {"peak", "entering"}
                   or seller_state.get("phase") in {"contending", "contending_with_future_upside"})
    if (competitive and row["minutes"] >= 20.0 and row["surplus"] > -16.0
            and not any(p["on_court"] >= row["on_court"] - 6.0 for p in incoming)):
        return False
    picks = [a for a in assets if a.get("kind") in {"pick", "pick_swap"}]
    minutes = pairing.get("buyer_minutes", 0.0)
    if picks and minutes < 24.0:
        spend = tx.package_value_for_team(canonical, picks, buyer_id)
        if spend > quick_capital_limit(canonical, buyer_id, row, minutes, assets, target):
            return False
    return True


def quick_capital_limit(canonical: dict[str, Any], buyer_id: str, row: dict[str, Any], minutes: float,
                        outgoing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> float:
    """The cheap terms of the full check's draft-spending limit (trade_roster.pick_investment_outlook): the base 8,
    measured depth, the rotation-role allowance, salary relief and the tax saved. TRADE-DEADLINE: the screen used to
    keep only the base and depth, so it dropped packages the full check would allow (a 17-20 minute rotation player
    for a second, or filler that sheds $5M+ of salary); the terms that need a roster forecast (rotation strength,
    upside, injury cover) are still left to the full check."""
    from .trade_roster import ROTATION_ROLE_PICK_ALLOWANCE, BACKUP_ROLE_MINUTES
    from .trade_tax import tax_value
    tx = _tx()
    limit = 8.0 + 0.6 * backup_gain(canonical, buyer_id, row)
    limit += ROTATION_ROLE_PICK_ALLOWANCE * min(1.0, max(0.0, (minutes - BACKUP_ROLE_MINUTES) / 8.0))
    out_salary, in_salary = tx.package_salary(canonical, outgoing), tx.package_salary(canonical, incoming)
    relief = ((out_salary or 0.0) - (in_salary or 0.0)) / 1e6 if out_salary is not None and in_salary is not None else 0.0
    if relief >= 5.0:
        limit += relief * 2.0
    limit += max(0.0, tax_value(canonical, buyer_id, incoming, outgoing))
    return limit


def backup_gain(canonical: dict[str, Any], buyer_id: str, row: dict[str, Any]) -> float:
    """How much the player would raise the buyer's backup at his position group (TRADE-VOLUME-2). The acceptance
    check allows 0.6 points of draft spending per point of backup gain on a non-starter
    (trade_roster.pick_investment_outlook); the quick screen allows the same, so a real depth buy is not dropped
    before the check sees it."""
    group = sorted((r["on_court"] for r in _team_rows(canonical, buyer_id)
                    if r["bucket"] == row["bucket"] and r["minutes"] >= 4.0), reverse=True)
    backup = (group + [0.0, 0.0])[1]
    return max(0.0, row["on_court"] - backup)


def ranked_packages(canonical: dict[str, Any], pairing: dict[str, Any], options: list[dict[str, Any]],
                    config: dict[str, Any], keep: int, near: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Price each built package quickly from both sides; keep the few that clear both prices, fairest first.

    ``near`` (trade step 4) collects packages that miss only on price, by at most NEAR_MISS_GAP for the short side,
    so a third team may complete them (multi_team_trades.multi_team_repairs)."""
    tx = _tx()
    seller_id, buyer_id = pairing["row"]["team_id"], pairing["buyer_id"]
    target = [{"kind": "player", "id": pairing["row"]["id"]}]
    buyer_team = tx.team_by_id(canonical, buyer_id)
    scored, missed = [], []
    for option in options:
        assets = []
        for asset in option.get("assets") or []:
            # A pick swap created for this offer (or a protected pick) is priced here as plain assets; the real
            # check prices the terms exactly.
            try:
                assets.extend(tx.normalize_assets(canonical, buyer_team, [asset]))
            except ValueError:
                continue
        if not assets or not package_fits_rules(canonical, pairing, assets):
            continue
        seller_raw = quick_net(canonical, seller_id, assets, target, config)
        buyer_raw = quick_net(canonical, buyer_id, target, assets, config)
        # The acceptance check lets two AI teams agree with one side up to 9 short as long as the two nets sum to
        # at least -2 (bounded negotiation, transactions.ai_trade_candidate_accepted). Packages clearly outside
        # that are dropped; the margin covers the terms this quick price leaves out.
        seller_net = seller_raw - pairing["ask"]["threshold"]
        buyer_net = buyer_raw - tx.acceptance_threshold(canonical, buyer_id, config)
        if (min(seller_raw, buyer_raw) < -9.0 - PRESCREEN_TOLERANCE
                or seller_raw + buyer_raw < -2.0 - PRESCREEN_TOLERANCE):
            if near is not None and min(seller_net, buyer_net) >= -NEAR_MISS_GAP and max(seller_net, buyer_net) >= 0:
                missed.append((-min(seller_net, buyer_net), len(missed), assets, seller_net, buyer_net))
            continue
        # Fairest first: the deal both sides clear by the most, then the one closest to the seller's price.
        scored.append((-min(seller_net, buyer_net), abs(seller_net), len(scored), option))
    scored.sort(key=lambda item: item[:3])
    if near is not None and not scored:
        # Only pairings that found no two-team package: keep their closest misses (at most two).
        for _, _, assets, seller_net, buyer_net in sorted(missed, key=lambda m: m[:2])[:NEAR_MISSES_PER_PAIRING]:
            near.append({"seller_id": seller_id, "buyer_id": buyer_id, "target": target, "assets": assets,
                         "nets": {seller_id: seller_net, buyer_id: buyer_net}, "pairing": pairing})
    return [item[3] for item in scored[:keep]]


NEAR_MISS_GAP = 45.0  # absorbed dead salary alone can cost up to 60 (trade_tax.ABSORB_VALUE_CAP)
NEAR_MISSES_PER_PAIRING = 2


def near_miss_candidate(canonical: dict[str, Any], miss: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """A two-team package that missed on quick price, in the candidate shape multi_team_trades.repair_routes reads."""
    tx = _tx()
    seller_id, buyer_id = miss["seller_id"], miss["buyer_id"]
    proposal = {"id": f"near:{seller_id}:{buyer_id}:{miss['target'][0]['id']}", "from_team_id": seller_id,
                "to_team_id": buyer_id, "from_assets": miss["target"], "to_assets": miss["assets"]}
    evaluations = [{"perspective_team_id": tid, "net_value": round(net + tx.acceptance_threshold(canonical, tid, config), 3),
                    "acceptance_threshold": tx.acceptance_threshold(canonical, tid, config), "accepted": net >= 0,
                    "decision": "accept" if net >= 0 else "reject", "decision_reasons": []}
                   for tid, net in miss["nets"].items()]
    return {"proposal": proposal, "legality": {"status": "legal", "issues": []}, "evaluations": evaluations,
            "quick_priced": True}


# ------------------------------------------------------------------------------------------- salary dumps (2b)
DUMPS_PER_TEAM = 3              # players a tax team tries to shed per trade window
ABSORBERS_PER_DUMP = 3          # teams with room asked to take each one
DUMP_MIN_SALARY = 3_000_000
# Prospects are not salary-dump material: the real dumps were veterans (Saric 31, Finney-Smith 33, LeVert 31, Randle,
# Schroder) and established role players (Isaiah Stewart 25, Isaiah Joe 27, Aaron Wiggins 27). The game still values a
# blocked prospect mostly by his current minutes (step 2, still wrong #6), so without this a contender over the tax
# would give away its recent draft picks for nothing.
DUMP_MIN_AGE = 24.0
DUMP_FILLER_MAX_SALARY = 3_000_000
# TRADE-TAXPOOL: recent draft picks are protected by years in the league, not age. In the step-4 runs Oklahoma City
# dumped Bennett Stirtz (24, picked 16th in 2026 after it traded up for him) for tax savings, because he was past the
# age floor and the step-1 investment memory is a share of his current value to the team (a few percent of a bench
# rookie's small role), which a tax saving outweighs. Real teams do not dump a pick they just made; the Nique Clifford
# sale (17 months after Sacramento traded up for him) was criticised as a front-office mistake.
RECENT_DRAFT_SEASONS = 3                # a player's first three seasons after his draft


def recent_draft_pick(canonical: dict[str, Any], player: dict[str, Any] | None) -> bool:
    """Drafted in one of the last RECENT_DRAFT_SEASONS drafts (his first three NBA seasons), whatever his age."""
    year = _tx().maybe_float((player or {}).get("draft_year"))
    if year is None:
        return False
    start = _tx().season_start_from_label(_season(canonical))
    return start - int(year) < RECENT_DRAFT_SEASONS


def dump_age_ok(canonical: dict[str, Any], player: dict[str, Any] | None, age: float) -> bool:
    """A player a team may shed for money: never a recent draft pick; an undrafted player from age 24."""
    if recent_draft_pick(canonical, player):
        return False
    return (player or {}).get("draft_year") not in (None, "") or age >= DUMP_MIN_AGE
DUMP_MAX_SECONDS = 3
DUMP_FIRST_MIN_TAX_VALUE = 25.0  # a first-round pick is attached only when the tax saved is worth this much
ROSTER_ROOM_LIMIT = 15


def salary_dump_offers(canonical: dict[str, Any], team_ids: list[str], excluded: set[str],
                       config: dict[str, Any]) -> list[dict[str, Any]]:
    """Tax teams shedding salary to teams with room under the tax, with picks attached when needed (trade 2b).

    The real pattern (12 of 43 real trades were tax moves): a team over the tax moves a paid player it can spare, and
    pays one to three second-round picks to a team under the tax that takes the salary (Finney-Smith, LeVert, Saric,
    Isaiah Stewart). Seller-driven, unlike the target search: each team over the tax picks the players whose tax saving
    is worth the most against what it loses on the court; each is offered to the few teams with room that value him
    most, with the cheapest pick package first. Never a young starter or a young core player, never the team's core
    plan, never the human team. Each offer lists the packages to try, cheapest first; the acceptance check decides.
    """
    from .trade_tax import tax_value, tax_saved
    from .team_planning import core_commitment
    tx = _tx()
    human = set(canonical.get("_human_team_ids") or [])
    excluded = set(excluded) | tx.recently_signed_player_ids(canonical) | tx.re_trade_hold_player_ids(canonical)
    # A team with a full roster sends back its least valuable minimum-salary player (real absorbers waive or include
    # one); a team with an open spot sends nothing.
    room = {}
    for tid in team_ids:
        if tid in human:
            continue
        rows_here = _team_rows(canonical, tid)
        if len(rows_here) < ROSTER_ROOM_LIMIT:
            room[tid] = []
            continue
        plan = (canonical.get("team_plans") or {}).get(tid) or {}
        spare = [r for r in rows_here if r["salary"] <= DUMP_FILLER_MAX_SALARY and r["id"] not in excluded
                 and r["id"] not in set(plan.get("core_ids") or []) and r["minutes"] < 10.0
                 and not core_commitment(canonical, tid, r["id"])]
        if spare:
            filler = min(spare, key=lambda r: (r["value"], r["id"]))
            room[tid] = [{"kind": "player", "id": filler["id"]}]
    offers = []
    for seller_id in team_ids:
        if seller_id in human:
            continue
        plan = (canonical.get("team_plans") or {}).get(seller_id) or {}
        core = set(plan.get("core_ids") or [])
        stance = team_stance(_state(canonical, seller_id))
        candidates = []
        for row in _team_rows(canonical, seller_id):
            if (row["id"] in excluded or row["id"] in core or row["salary"] < DUMP_MIN_SALARY
                    or not dump_age_ok(canonical, row["player"], row["age"]) or core_commitment(canonical, seller_id, row["id"]) or young_piece_kept(row, stance)
                    or tx.effectively_untouchable(canonical, row["player"])):
                continue
            asset = [{"kind": "player", "id": row["id"]}]
            tax = tax_value(canonical, seller_id, [], asset)
            if tax <= 3.0:
                continue
            own = tx.package_value_for_team(canonical, asset, seller_id)
            candidates.append((tax - own, tax, own, row))
        candidates.sort(key=lambda c: (-c[0], c[3]["id"]))
        for gain, tax, own, row in candidates[:DUMPS_PER_TEAM]:
            if gain < -25.0:
                continue  # more than about a first-round pick's worth to shed him: not a dump
            asset = [{"kind": "player", "id": row["id"]}]
            takers = []
            for buyer_id in team_ids:
                if buyer_id == seller_id or buyer_id in human or buyer_id not in room:
                    continue
                back = room[buyer_id]
                if tax_value(canonical, buyer_id, asset, back) < -2.0:
                    continue  # it would pay tax itself
                takers.append((quick_net(canonical, buyer_id, asset, back, config), buyer_id))
            takers.sort(key=lambda t: (-t[0], t[1]))
            for _, buyer_id in takers[:ABSORBERS_PER_DUMP]:
                back = room[buyer_id]
                saving = tax_saved(canonical, seller_id, back, asset)
                offers.append({"seller_id": seller_id, "buyer_id": buyer_id, "row": row, "tax_value": tax,
                               "own": own, "gain": gain, "saved": saving["saved"], "saving": saving, "return": back,
                               "packages": dump_packages(canonical, seller_id, row, tax)})
    offers.sort(key=lambda o: (-o["gain"], o["seller_id"], o["row"]["id"], o["buyer_id"]))
    return offers


def dump_packages(canonical: dict[str, Any], seller_id: str, row: dict[str, Any], tax: float) -> list[list[dict[str, Any]]]:
    """The player alone, then with the seller's cheapest one, two or three seconds, then with its cheapest first."""
    tx = _tx()
    picks = tx.tradeable_picks_for_team(canonical, seller_id)
    seconds = sorted((p for p in picks if int(p.get("round") or 0) == 2),
                     key=lambda p: (tx.pick_asset_value(p, "neutral"), str(p.get("id"))))
    firsts = sorted((p for p in picks if int(p.get("round") or 0) == 1),
                    key=lambda p: (tx.pick_asset_value(p, "neutral"), str(p.get("id"))))
    player = {"kind": "player", "id": row["id"]}
    packages = [[player]]
    for count in range(1, min(DUMP_MAX_SECONDS, len(seconds)) + 1):
        packages.append([player] + [{"kind": "pick", "id": p["id"]} for p in seconds[:count]])
    if firsts and tax >= DUMP_FIRST_MIN_TAX_VALUE:
        packages.append([player, {"kind": "pick", "id": firsts[0]["id"]}])
    return packages


def dump_reasons(canonical: dict[str, Any], offer: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    """Why each side made a salary dump, in plain words."""
    from .trade_tax import saving_words
    tx = _tx()
    seller = tx.team_by_id(canonical, offer["seller_id"])
    buyer = tx.team_by_id(canonical, offer["buyer_id"])
    row = offer["row"]
    picks = [a for a in assets if a.get("kind") == "pick"]
    rounds = [int((tx.pick_by_id(canonical, a["id"]) or {}).get("round") or 2) for a in picks]
    paid = ""
    if picks:
        words = []
        if rounds.count(1):
            words.append("a first-round pick")
        if rounds.count(2):
            words.append(f"{rounds.count(2)} second-round pick{'s' if rounds.count(2) > 1 else ''}")
        paid = ", paying " + " and ".join(words)
    seller_text = (f"{seller['abbrev']} ({stance_words(canonical, seller['id'])}) moved {row['name']} "
                   f"(${row['salary'] / 1e6:.1f}M) {saving_words(offer.get('saving') or {'saved': offer['saved']})}{paid}")
    buyer_text = (f"{buyer['abbrev']} ({stance_words(canonical, buyer['id'])}) had room under the tax and took him"
                  + (" for the picks" if picks else " as a rotation player"))
    return {"buyer_team_id": buyer["id"], "seller_team_id": seller["id"], "target_id": f"{seller['id']}:salary_dump",
            "target_key": "salary_dump", "target_label": "luxury-tax savings", "target_reason": "over the luxury tax",
            "player_id": row["id"], "seller_reasons": ["over_tax_line"], "tax_saved": round(offer["saved"], 0),
            "text": f"{seller_text}; {buyer_text}."}
