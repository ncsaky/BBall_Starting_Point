"""What a computer team must get back before it gives up a star or a core player (TRADE-PRICE, 2026-11-27).

Offer tests on saved test seasons had computer teams selling stars and prized young players for one or two first-round
picks: a good pick is priced as high as the best players, and the older minimum return (transactions.premium_return_issue)
only covers players rated 76.5 on court, or 68 on a competing team. A test season also had New York add a pick to send
Jalen Brunson, one of its three best players, away for a bench guard because the deal cut its luxury tax
(docs/agents/tasks/trade-price.md). The user approved two rules. Both only refuse, and only for computer teams:

1. A star leaves only for a comparable player, a top young player or STAR_FIRSTS first-round picks, and each departing
   star needs a return of his own. A star is one of the STAR_LEAGUE_RANK best players on court today, or
   STAR_YOUNG_AGE or younger and priced at STAR_YOUNG_PRICE or more. A comparable player must also be priced at least
   STAR_COMPARABLE_PRICE_SHARE as high as the star: ratings alone let a deep reserve count as comparable to a prized
   young player (a test season sent Alex Condon away for D'Angelo Russell and two picks).
2. A team does not add a pick to get rid of one of its CORE_TOP best players (rated CORE_MIN_ON_COURT or better) unless
   a comparable player, a top young player or a first-round pick comes back.

Neither covers a player aged OLD_AGE or older, or one with a costly contract or a high injury risk (the older rule's two
exits). Ratings, pick values and the other trade rules are untouched.
"""
from __future__ import annotations

from typing import Any

STAR_LEAGUE_RANK = 30
# No one rated below this on court is a star by rank, however thin the league (a full league's thirtieth best is about
# 70, so this never decides anything there).
STAR_MIN_ON_COURT = 62.0
STAR_YOUNG_AGE = 25
STAR_YOUNG_PRICE = 80.0
STAR_FIRSTS = 3
STAR_COMPARABLE_PRICE_SHARE = 0.8
CORE_TOP = 3
CORE_MIN_ON_COURT = 62.0
OLD_AGE = 34
COSTLY_CONTRACT_SURPLUS = -16.0
HIGH_HEALTH_RISK = 30.0
# A first-round pick counts only if it is worth something: an unprotected late first is worth about 28 points or more,
# so this leaves out picks whose protections make them a first in name only.
COUNTED_FIRST_VALUE = 20.0


def _tx():
    from . import transactions
    return transactions


def _age(player: dict[str, Any]) -> float:
    return float(player.get("display_age", player.get("age")) or 27)


def _on_court(values: dict[str, Any], player_id: str) -> float:
    return float((values.get(player_id) or {}).get("on_court_value") or 0.0)


def comparable(canonical: dict[str, Any], departing: dict[str, Any], arriving: dict[str, Any]) -> bool:
    """The arriving player rates close to the departing one, on court and in the playoffs."""
    values = _tx().player_asset_values_by_id(canonical)
    gone, value = values.get(departing["id"]) or {}, values.get(arriving["id"]) or {}
    return (float(value.get("on_court_value") or 0.0) >= float(gone.get("on_court_value") or 0.0) - 4
            and float(value.get("playoff_value") or 0.0) >= float(gone.get("playoff_value") or 50.0) - 8)


def young_centerpiece(canonical: dict[str, Any], departing: dict[str, Any], arriving: dict[str, Any]) -> bool:
    """The arriving player is young (25 or younger) with real upside, already decent and priced near the departing one."""
    tx = _tx()
    values = tx.player_asset_values_by_id(canonical)
    gone, value = values.get(departing["id"]) or {}, values.get(arriving["id"]) or {}
    return (_age(arriving) <= 25
            and float(value.get("on_court_value") or 0.0) >= max(60, float(gone.get("on_court_value") or 0.0) - 18)
            and float(value.get("development_upside") or 0.0) >= 12
            and tx.market_trade_target_value(arriving, value) >= tx.market_trade_target_value(departing, gone) * .6)


def replaces(canonical: dict[str, Any], departing: dict[str, Any], arriving: dict[str, Any]) -> bool:
    """The arriving player is a real return for the departing one: comparable, or a young centerpiece."""
    return comparable(canonical, departing, arriving) or young_centerpiece(canonical, departing, arriving)


def replaces_star(canonical: dict[str, Any], star: dict[str, Any], arriving: dict[str, Any]) -> bool:
    """As ``replaces``, but a comparable player must also be priced near the star."""
    if young_centerpiece(canonical, star, arriving):
        return True
    if not comparable(canonical, star, arriving):
        return False
    tx = _tx()
    values = tx.player_asset_values_by_id(canonical)
    price = lambda p: tx._search_market_value(canonical, p, values.get(p["id"]) or {})
    return price(arriving) >= STAR_COMPARABLE_PRICE_SHARE * price(star)


def _covered(player: dict[str, Any], value: dict[str, Any]) -> bool:
    return (_age(player) < OLD_AGE
            and float(value.get("contract_surplus") or 0.0) > COSTLY_CONTRACT_SURPLUS
            and float(value.get("health_risk") or 0.0) < HIGH_HEALTH_RISK)


def star_bar(canonical: dict[str, Any]) -> float:
    """The on-court value of the league's STAR_LEAGUE_RANK-th best rostered player (infinite in a league too small to
    have a top thirty). Kept until the players or their valuations are replaced."""
    players, valuations = canonical.get("players"), canonical.get("player_asset_valuations")
    memo = canonical.get("_star_bar_memo")
    if memo is not None and memo[0] is players and memo[1] is valuations:
        return memo[2]
    values = _tx().player_asset_values_by_id(canonical)
    ranked = sorted((_on_court(values, p["id"]) for p in players or []
                     if p.get("team_id") and not p.get("_inactive_player")), reverse=True)
    bar = ranked[STAR_LEAGUE_RANK - 1] if len(ranked) > STAR_LEAGUE_RANK else float("inf")
    canonical["_star_bar_memo"] = (players, valuations, bar)
    return bar


def is_star(canonical: dict[str, Any], player: dict[str, Any]) -> bool:
    tx = _tx()
    value = tx.player_asset_values_by_id(canonical).get(player["id"]) or {}
    if not value or not _covered(player, value):
        return False
    if float(value.get("on_court_value") or 0.0) >= max(STAR_MIN_ON_COURT, star_bar(canonical)):
        return True
    return _age(player) <= STAR_YOUNG_AGE and tx._search_market_value(canonical, player, value) >= STAR_YOUNG_PRICE


def counted_firsts(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> int:
    """Different first-round picks among the assets that are worth at least COUNTED_FIRST_VALUE."""
    tx = _tx()
    found = 0
    for pick_id in {a.get("id") for a in assets if a.get("kind") == "pick"}:
        pick = tx.pick_by_id(canonical, pick_id) or {}
        if pick.get("round") == 1 and tx.pick_asset_value(pick, "balanced") >= COUNTED_FIRST_VALUE:
            found += 1
    return found


def _players(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tx = _tx()
    found = (tx.player_by_id(canonical, a.get("id")) for a in assets if a.get("kind") == "player")
    return [player for player in found if player]


def _best_players(canonical: dict[str, Any], team_id: str) -> set[str]:
    tx = _tx()
    values = tx.player_asset_values_by_id(canonical)
    rows = tx._search_team_rows(canonical, team_id)
    roster = [p for p in (canonical.get("players", []) if rows is None else rows)
              if p.get("team_id") == team_id and not p.get("_inactive_player")]
    ranked = sorted(roster, key=lambda p: (-_on_court(values, p["id"]), p["id"]))
    return {p["id"] for p in ranked[:CORE_TOP]}


def _star_issue(canonical, incoming_assets, outgoing):
    stars = [p for p in outgoing if is_star(canonical, p)]
    if not stars:
        return None
    values = _tx().player_asset_values_by_id(canonical)
    spare = _players(canonical, incoming_assets)
    firsts = counted_firsts(canonical, incoming_assets)
    # The best star first; each takes the weakest arrival that replaces him, so a better one stays for the next.
    for star in sorted(stars, key=lambda p: (-_on_court(values, p["id"]), p["id"])):
        match = next((p for p in sorted(spare, key=lambda p: (_on_court(values, p["id"]), p["id"]))
                      if replaces_star(canonical, star, p)), None)
        if match is not None:
            spare.remove(match)
        elif firsts >= STAR_FIRSTS:
            firsts -= STAR_FIRSTS
        else:
            return (f"{star.get('name', 'This player')} is a star: it takes a comparable player, a top young player "
                    "or three first-round picks.")
    return None


def _pay_to_move_issue(canonical, team_id, incoming_assets, outgoing_assets, outgoing):
    if not any(a.get("kind") in {"pick", "pick_swap"} for a in outgoing_assets):
        return None
    if counted_firsts(canonical, incoming_assets):
        return None
    values = _tx().player_asset_values_by_id(canonical)
    arriving = _players(canonical, incoming_assets)
    best = None
    for player in outgoing:
        value = values.get(player["id"]) or {}
        if float(value.get("on_court_value") or 0.0) < CORE_MIN_ON_COURT or not _covered(player, value):
            continue
        best = _best_players(canonical, team_id) if best is None else best
        if player["id"] in best and not any(replaces(canonical, player, p) for p in arriving):
            return (f"The team will not add a pick to give away {player.get('name', 'this player')}, "
                    "one of its three best players.")
    return None


def return_issue(canonical: dict[str, Any], team_id: str, incoming_assets: list[dict[str, Any]],
                 outgoing_assets: list[dict[str, Any]]) -> str | None:
    """Why a computer team refuses this return for the players it sends, or None. The caller skips human teams."""
    outgoing = _players(canonical, outgoing_assets)
    if not outgoing:
        return None
    return (_star_issue(canonical, incoming_assets, outgoing)
            or _pay_to_move_issue(canonical, team_id, incoming_assets, outgoing_assets, outgoing))
