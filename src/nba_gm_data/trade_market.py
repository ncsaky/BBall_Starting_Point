"""The trade market (TRADE-MARKET): live negotiations that last several days, shopping, bidding wars and final offers.

Plan and user decisions: docs/agents/tasks/trade-market-personality-plan.md. Traits: front_office.py.

**The negotiation ledger** (``save['trade_market']['negotiations']``). When an AI front office pursues a player and the
two sides end a market day close but apart (both sides' distance from their own price recorded), the negotiation is
kept. On later market days the same pairing meets again; each side concedes a little as its patience runs out
(``concession_term``: bounded, larger for impatient offices, growing with the days of talks and as the trade deadline
nears). The side whose patience runs out first makes a final, take-it-or-leave-it offer (its full concession); if that
fails the negotiation dies and the buyer walks away for a cooldown. A dead negotiation is reopened only when the
buyer is high on the player and the seller's situation has changed (its window, its reasons to sell), never just to
try again.

**Shopping and bidding wars.** A team with a stated reason to move a good player (rebuild, tax, blocked, unhappy,
expiring) shops him when two or more teams are interested. The seller compares every live offer each day: it asks
the bidders for their best, each raises within its own value plus its personality premium, and the best offer wins.
BIDWAR-PRICE: offers are compared on the seller's textbook price (``evaluation_price``); a bidder whose built packages
cannot beat the leader adds one more asset of its own while its own check accepts; the winner pays at least the
second-best bid, and a slightly lower bid wins only for a strong stated reason of the seller's (``SearchMarket.decide``).
A patient seller waits for the decision day (always by the deadline) unless an offer clearly beats its price; an
impatient one takes a good offer early. The user's offers for a shopped player enter the same comparison
(app_actions).

**No harassment.** Players on teams with no reason to sell are never shopped. An unsolicited offer for a contender's
star needs a buyer that is high on him and urgent, at most one per buyer per season, and the owner can refuse to
engage. Every attempt is counted (``stats``).

Determinism: nothing here draws a random number. Ordering ties are broken by ids.
"""
from __future__ import annotations

from datetime import date
from typing import Any

LEDGER_KEY = "trade_market"
CONCESSION_MAX = 6.0            # value points a fully impatient office concedes at the end of its patience
PATIENCE_CONCESSION_SHARE = 0.7 # a fully patient office concedes 30% of that
NEAR_GAP = 24.0                 # combined shortfall (both sides) still worth talking about the next day
RULE_GAP = 6.0                  # a refusal on a hard rule counts as this far apart (pick spending, roster plan)
COOLDOWN_DAYS = 30
NEGOTIATION_MAX_AGE = 45        # an open negotiation not resumed for this long lapses
SHOP_VALUE = 45.0               # market value of a player worth shopping (a solid rotation player and up)
SHOP_MIN_BUYERS = 2
BID_RAISE_MIN = 1.0
BIDDING_ROUNDS = 4
RAISE_CHECKS = {1: 2, 2: 4}     # full checks per bidder per round
EARLY_ACCEPT_BASE = 2.0         # an offer this far over the seller's price (plus patience) is taken before the decision day
STAR_ON_COURT = 66.0            # unsolicited offers: a contender's star (about the league's top 60 players) ...
STAR_VALUE = 75.0               # ... by on-court value or by trade value, with no reason to sell
UNSOLICITED_PER_BUYER = 1
TEXTS_PER_DAY = 2
SELLER_PRINCIPAL_BAND = 4.0     # a seller's principal outgoing players: within this much of its best one
OPINION_PAIRINGS_PER_BUYER = 2  # available players an office pursues because its scouts like them
OPINION_MIN_MINUTES = 14.0      # ... only if he would play for it
OPINION_REBUILD_MAX_AGE = 29.0  # ... and a rebuilding or retooling office does not chase older players
OPINION_RANK = 9                # after every target pairing in the search order

# BIDWAR-PRICE: the price of a bid is the seller's textbook value of it (its net with its personality terms taken out,
# over its acceptance threshold). The war is fought on that price and the winner pays at least the second-best bid.
# A slightly lower bid wins only for a stated, lasting reason of the seller's (docs/agents/tasks/bidwar-price.md).
SLIGHT_GAP = 5.0          # a lower bid can win only this close to the best price (about half a second-round pick)
STRONG_REASON = 2.0       # ... for a stated reason at least this large ...
PREFERENCE_EDGE = 1.0     # ... that makes it worth at least this much more to the seller overall
FLOOR_CHECKS = 3          # full checks for the seller's preferred bidder raising its offer to the best price
TIMELINE_POINTS = 3.0     # a rebuilding seller's preference for a package of young players and picks (all of it)
TIMELINE_YOUNG_AGE = 24.0
RIVAL_POINTS = 4.0        # a competing seller's reluctance to strengthen a contender in its own conference
PREFERENCE_TERMS = {"opinion": "opinion", "tax_averse": "tax", "values_picks": "picks", "urgency": "help_now"}


# ----------------------------------------------------------------------------------------------- utilities

def _today(canonical: dict[str, Any]) -> date | None:
    try:
        return date.fromisoformat(str((canonical.get("meta") or {}).get("current_date") or "")[:10])
    except ValueError:
        return None


def _deadline(day: date) -> date:
    start = day.year if day.month >= 7 else day.year - 1
    return date(start + 1, 2, 5)


def in_season(day: date) -> bool:
    return (day.month >= 10 or day.month <= 2) and day <= _deadline(day)


def deadline_pressure(day: date | None) -> float:
    """0 a week or more before the trade deadline (or outside the season), 1 on deadline day."""
    if day is None or not in_season(day):
        return 0.0
    left = (_deadline(day) - day).days
    return max(0.0, min(1.0, 1.0 - left / 7.0)) if left <= 7 else 0.0


def max_rounds(patience: float) -> int:
    """Market days a front office keeps talking before its final offer: 2 (very impatient) to 7 (very patient)."""
    return 2 + int(round(max(0.0, min(100.0, patience)) / 20.0))


def negotiation_key(buyer_id: str, seller_id: str, player_id: str) -> str:
    return f"{buyer_id}|{seller_id}|{player_id}"


def empty_ledger() -> dict[str, Any]:
    return {"negotiations": {}, "shopping": {}, "stats": {}, "texts": []}


def ledger(save: dict[str, Any]) -> dict[str, Any]:
    book = save.get(LEDGER_KEY)
    if not isinstance(book, dict):
        book = empty_ledger()
        save[LEDGER_KEY] = book
    for key, default in empty_ledger().items():
        book.setdefault(key, default)
    return book


def ledger_view(save: dict[str, Any]) -> dict[str, Any]:
    """Read-only copy for the active league (canonical_with_save)."""
    book = save.get(LEDGER_KEY) or {}
    return {"negotiations": dict(book.get("negotiations") or {}), "shopping": dict(book.get("shopping") or {}),
            "stats": dict(book.get("stats") or {})}


def _season_label(day: date) -> str:
    start = day.year if day.month >= 7 else day.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def _proposal_team_ids(proposal: Any) -> set[str]:
    if proposal is None:
        return set()
    from .transactions import trade_team_ids
    try:
        return set(trade_team_ids(proposal))
    except Exception:
        return set()


# ------------------------------------------------------------------------------------------ concessions

def _negotiation_index(canonical: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    memo = canonical.get("_market_negotiation_index") if canonical.get("_allow_internal_caches") else None
    if memo is not None:
        return memo
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for neg in ((canonical.get("trade_market_ledger") or {}).get("negotiations") or {}).values():
        # "agreed": agreed today and waiting for the trade itself. The apply-time re-check must see the same
        # concession the two sides agreed with (TRADE-FOLLOWUPS: an agreed deal is executed or cancelled the same day).
        if neg.get("status") not in {"open", "final_offer", "agreed"}:
            continue
        for team in (neg.get("buyer_id"), neg.get("seller_id")):
            index.setdefault((team, neg.get("player_id")), []).append(neg)
    if canonical.get("_allow_internal_caches"):
        canonical["_market_negotiation_index"] = index
    return index


def is_deadline_day(day: date | None) -> bool:
    return bool(day and in_season(day) and day == _deadline(day))


def negotiation_pressure(canonical: dict[str, Any], team_id: str, neg: dict[str, Any] | None) -> tuple[float, bool]:
    """How far this side's patience has run in a negotiation (0-1) and whether this is its final offer.

    Each market day of talks uses up 1 / max_rounds(patience) of it, and the trade deadline closes in on everyone
    in its last week. On deadline day there is no tomorrow: every negotiation, even one that starts that day, is a
    final offer."""
    from .front_office import office
    row = office(canonical, team_id)
    if not row:
        return 0.0, False
    today = _today(canonical)
    if is_deadline_day(today):
        return 1.0, True
    rounds = len((neg or {}).get("rounds") or [])
    if rounds <= 0:
        return 0.0, False
    pressure = min(1.0, max(rounds / max_rounds(float(row["patience"])), deadline_pressure(today)))
    return pressure, pressure >= 1.0


def concession_size(canonical: dict[str, Any], team_id: str, neg: dict[str, Any] | None) -> tuple[float, bool]:
    """Value points this side gives up from its price: up to CONCESSION_MAX for a fully impatient office, 30% of
    that for a fully patient one, scaled by how far its patience has run."""
    from .front_office import office
    row = office(canonical, team_id)
    if not row:
        return 0.0, False
    pressure, final = negotiation_pressure(canonical, team_id, neg)
    size = CONCESSION_MAX * (1.0 - PATIENCE_CONCESSION_SHARE * float(row["patience"]) / 100.0) * pressure
    return round(size, 3), final


def _motivated(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
               outgoing: list[dict[str, Any]]) -> bool:
    """A side with its own reason to deal. A buyer (it gets a better player than any it sends, or sends no player)
    is pursuing a target. A seller is motivated only when the players it is really selling (its best outgoing
    players) are ones it has a stated reason to move or salary it would move: a team giving up a player it had no
    plan to move is never in a hurry, whatever it gets back."""
    from .front_office import _on_court
    players_out = [a for a in outgoing if a.get("kind") == "player"]
    players_in = [a for a in incoming if a.get("kind") == "player"]
    if not players_out:
        return bool(players_in)
    best_out = max(_on_court(canonical, a["id"]) for a in players_out)
    best_in = max((_on_court(canonical, a["id"]) for a in players_in), default=0.0)
    if best_in > best_out:
        return True
    from .trade_targets import salary_filler, team_sell_reasons
    reasons = team_sell_reasons(canonical, team_id)
    filler = salary_filler(canonical, team_id)
    principal = [a for a in players_out if _on_court(canonical, a["id"]) >= best_out - SELLER_PRINCIPAL_BAND]
    return all(reasons.get(a.get("id")) or a.get("id") in filler for a in principal)


def concession_term(canonical: dict[str, Any], team_id: str, proposal: Any, incoming: list[dict[str, Any]],
                    outgoing: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The concession this team makes in a live negotiation for a player in this deal (a personality term), or on
    deadline day, when every motivated side makes its final offer."""
    from .front_office import office
    row = office(canonical, team_id)
    if not row:
        return None
    abbrev = row.get("abbrev") or team_id
    if not _motivated(canonical, team_id, incoming, outgoing):
        return None  # a team with no reason of its own to make this deal gives no ground
    teams = _proposal_team_ids(proposal)
    index = _negotiation_index(canonical) if canonical.get("trade_market_ledger") else {}
    moving = [a.get("id") for a in list(incoming) + list(outgoing) if a.get("kind") == "player"]
    for pid in moving:
        for neg in index.get((team_id, pid), []):
            other = neg["seller_id"] if neg["buyer_id"] == team_id else neg["buyer_id"]
            if teams and other not in teams:
                continue
            size, final = concession_size(canonical, team_id, neg)
            if size < 0.25:
                return None
            days = len(neg.get("rounds") or [])
            name = neg.get("player_name") or pid
            if final:
                text = (f"{abbrev}'s patience ran out after {days + 1} day{'s' if days else ''} of talks over "
                        f"{name}: a final, take-it-or-leave-it offer")
            else:
                text = f"{abbrev} has talked about {name} for {days + 1} days and gives a little ground"
            return {"key": "final_offer" if final else "concession", "points": size, "text": text,
                    "negotiation": neg.get("key")}
    if is_deadline_day(_today(canonical)):
        size, _ = concession_size(canonical, team_id, None)
        if size >= 0.25:
            return {"key": "final_offer", "points": size,
                    "text": f"deadline day: {abbrev} makes its final, take-it-or-leave-it offer"}
    return None


def concession_allowance(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
                         outgoing: list[dict[str, Any]]) -> float:
    """The same concession as extra draft value a conceding buyer will spend (trade_roster pick investment)."""
    term = concession_term(canonical, team_id, None, incoming, outgoing)
    return float(term["points"]) if term else 0.0


# ------------------------------------------------------------------------------------------ the search

def _office(canonical, team_id):
    from .front_office import office
    return office(canonical, team_id)


class SearchMarket:
    """The market's part of one day's AI trade search (transactions.target_driven_ai_trades). Reads the ledger from
    the active league; everything it learns is returned as ``updates`` for ``apply_market_updates``."""

    def __init__(self, canonical: dict[str, Any], through_date: str, depth: int):
        self.canonical = canonical
        self.date = through_date
        self.day = date.fromisoformat(through_date[:10])
        self.depth = depth
        book = canonical.get("trade_market_ledger") or {}
        self.negotiations = book.get("negotiations") or {}
        self.shopping = book.get("shopping") or {}
        self.stats = book.get("stats") or {}
        self.observed: dict[str, dict[str, Any]] = {}
        self.deals: dict[str, dict[str, Any]] = {}
        self.bids: dict[str, list[dict[str, Any]]] = {}
        self.interest: dict[str, set[str]] = {}
        self.unsolicited: list[dict[str, Any]] = []
        self.wars: list[dict[str, Any]] = []
        self.waiting: list[dict[str, Any]] = []

    # --- which pairings to pursue -------------------------------------------------------------------------
    def filter_pairings(self, pairings: list[dict[str, Any]], diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
        from .front_office import player_opinion, urgency_level
        from .trade_targets import team_sell_reasons, team_stance, _state
        kept, skipped_dead, refused = [], 0, 0
        season = _season_label(self.day)
        used = dict((self.stats.get(season) or {}).get("unsolicited_by_buyer") or {})
        for pairing in pairings:
            row = pairing["row"]
            buyer, seller, pid = pairing["buyer_id"], row["team_id"], row["id"]
            neg = self.negotiations.get(negotiation_key(buyer, seller, pid))
            if neg and neg.get("status") == "dead" and not self.reopen(neg, pairing):
                skipped_dead += 1
                continue
            reasons = pairing.get("reasons") or []
            seller_state = _state(self.canonical, seller)
            if (not reasons and team_stance(seller_state) == "contend"
                    and (float(row.get("on_court") or 0.0) >= STAR_ON_COURT or float(row.get("value") or 0.0) >= STAR_VALUE)):
                # An unsolicited offer for a competing team's star: only an urgent buyer that is high on him, once a
                # season, and the owner may refuse to engage.
                buyer_row = _office(self.canonical, buyer)
                opinion = player_opinion(self.canonical, buyer, pid)
                keen = bool(buyer_row and opinion and opinion["points"] > 0 and urgency_level(buyer_row) >= 0.25)
                record = {"date": self.date, "buyer_id": buyer, "seller_id": seller, "player_id": pid,
                          "player_name": row.get("name")}
                if not keen or used.get(buyer, 0) >= UNSOLICITED_PER_BUYER:
                    refused += 1
                    continue
                seller_row = _office(self.canonical, seller)
                engaged = bool(seller_row and float(seller_row["patience"]) < 40.0)
                record["engaged"] = engaged
                self.unsolicited.append(record)
                used[buyer] = used.get(buyer, 0) + 1
                if not engaged:
                    continue
                pairing = {**pairing, "unsolicited": True}
            self.interest.setdefault(pid, set()).add(buyer)
            kept.append(pairing)
        diagnostics["market_dead_skipped"] = skipped_dead
        diagnostics["market_unsolicited_screened_out"] = refused
        # Open negotiations first (the seller compares every live offer), then the usual order.
        order = {id(p): i for i, p in enumerate(kept)}
        kept.sort(key=lambda p: (0 if self.open_negotiation(p) else 1, order[id(p)]))
        self.sellers = {p["row"]["id"]: p["row"]["team_id"] for p in kept}
        self.rows = {p["row"]["id"]: p["row"] for p in kept}
        self.reasons = {p["row"]["id"]: p.get("reasons") or [] for p in kept}
        return kept

    def opinion_pairings(self, buyer_ids: list[str], excluded: set[str], existing: list[dict[str, Any]],
                         config: dict[str, Any]) -> list[dict[str, Any]]:
        """Interest from player opinions: an AI office pursues an available player its scouts have always liked even
        when he is not on its target list, if he would play for it and the two sides' prices can meet. Only players
        whose teams have a stated reason to move them (no harassment); a rebuilding or retooling buyer does not
        chase veterans. These come after every target pairing, so they only use capacity the targets leave."""
        from . import trade_targets as tt
        from . import transactions as tx
        from .front_office import _office_leans, player_opinion, office
        from .team_planning import core_commitment
        rows = tt.player_rows(self.canonical)
        human = set(self.canonical.get("_human_team_ids") or [])
        have = {(p["buyer_id"], p["row"]["id"]) for p in existing}
        held = tx.re_trade_hold(self.canonical)
        out = []
        for buyer_id in buyer_ids:
            if not office(self.canonical, buyer_id):
                continue
            stance = _stance(self.canonical, buyer_id)
            table = _office_leans(self.canonical, buyer_id)
            liked = sorted((pid for pid, lean in table["leans"].items() if lean >= table["high"]),
                           key=lambda pid: (-table["leans"][pid], pid))
            kept = []
            for pid in liked:
                row = rows.get(pid)
                if (row is None or row["team_id"] in human or row["team_id"] == buyer_id or pid in excluded
                        or (buyer_id, pid) in have):
                    continue
                seller = row["team_id"]
                reasons = tt.team_sell_reasons(self.canonical, seller).get(pid, [])
                if not reasons or core_commitment(self.canonical, seller, pid):
                    continue
                seller_stance = tt.team_stance(tt._state(self.canonical, seller))
                if ((tt.young_piece_kept(row, seller_stance) or tt.recent_lottery_pick(self.canonical, row["player"]))
                        and not tt.exposing_reasons(reasons)):
                    continue
                if held.get(pid) == seller and not (seller_stance == "rebuild" and row["age"] >= tt.FLIP_AGE):
                    continue
                if stance in {"rebuild", "retool"} and row["age"] > OPINION_REBUILD_MAX_AGE:
                    continue
                minutes = tt.buyer_minutes(self.canonical, buyer_id, row)
                if minutes < OPINION_MIN_MINUTES or tx.effectively_untouchable(self.canonical, row["player"]):
                    continue
                ask = tt.asking_price(self.canonical, seller, pid, config)
                value = tt.buyer_value(self.canonical, buyer_id, pid, config)
                zone = value - ask["ask"]
                if zone < -tt.ZONE_TOLERANCE - 40.0:
                    continue
                zone += tt.trade_surplus(self.canonical, buyer_id, seller, pid, excluded, config)
                if zone < -tt.ZONE_TOLERANCE:
                    continue
                opinion = player_opinion(self.canonical, buyer_id, pid) or {}
                target = {"id": f"opinion:{buyer_id}:{pid}", "key": "opinion", "filters": {},
                          "label": "a player its scouts have always liked",
                          "reason": (opinion.get("why") or "its scouts like him") + " game"}
                kept.append({"buyer_id": buyer_id, "target": target, "rank": OPINION_RANK, "row": row,
                             "reasons": reasons, "ask": ask, "buyer_value": value, "zone": zone,
                             "buyer_minutes": minutes, "priority": min(zone, 10.0) * 0.5, "opinion": True})
                if len(kept) >= OPINION_PAIRINGS_PER_BUYER:
                    break
            out.extend(kept)
        out.sort(key=lambda p: (-p["priority"], p["buyer_id"], p["row"]["id"]))
        return out

    def open_negotiation(self, pairing: dict[str, Any]) -> dict[str, Any] | None:
        neg = self.negotiations.get(negotiation_key(pairing["buyer_id"], pairing["row"]["team_id"], pairing["row"]["id"]))
        return neg if neg and neg.get("status") in {"open", "final_offer"} else None

    def reopen(self, neg: dict[str, Any], pairing: dict[str, Any]) -> bool:
        """A dead negotiation comes back only after its cooldown, when the buyer is high on the player (or the player
        is its first target and it is urgent) and the seller's situation has changed."""
        from .front_office import player_opinion, urgency_level
        from .trade_targets import team_stance, _state
        until = neg.get("cooldown_until")
        if until and self.date < until:
            return False
        buyer, seller = pairing["buyer_id"], pairing["row"]["team_id"]
        opinion = player_opinion(self.canonical, buyer, pairing["row"]["id"])
        row = _office(self.canonical, buyer)
        keen = bool(opinion and opinion["points"] > 0) or bool(row and pairing.get("rank") == 0 and urgency_level(row) >= 0.25)
        death = neg.get("death") or {}
        changed = (team_stance(_state(self.canonical, seller)) != death.get("seller_stance")
                   or bool(set(pairing.get("reasons") or []) - set(death.get("seller_reasons") or [])))
        return keen and changed

    # --- what happened to each pairing ----------------------------------------------------------------------
    def observe(self, pairing: dict[str, Any], candidate: dict[str, Any] | None, *, quick_nets: dict[str, float] | None = None) -> None:
        """Remember the closest the two sides came today (declined full checks and quick-priced near misses)."""
        key = negotiation_key(pairing["buyer_id"], pairing["row"]["team_id"], pairing["row"]["id"])
        gaps = self.gaps(candidate) if candidate is not None else dict(quick_nets or {})
        if not gaps:
            return
        combined = sum(min(0.0, v) for v in gaps.values())
        best = self.observed.get(key)
        if best is None or combined > best["combined"]:
            self.observed[key] = {"pairing": pairing, "gaps": gaps, "combined": combined,
                                  "offer": _offer_summary(self.canonical, candidate) if candidate else None}

    @staticmethod
    def gaps(candidate: dict[str, Any]) -> dict[str, float]:
        out = {}
        for evaluation in candidate.get("evaluations") or []:
            tid = evaluation.get("perspective_team_id")
            gap = float(evaluation.get("net_value") or 0.0) - float(evaluation.get("acceptance_threshold") or 0.0)
            if str(evaluation.get("decision") or "").startswith("reject_") and gap > -RULE_GAP:
                gap = -RULE_GAP
            out[tid] = round(gap, 2)
        return out

    def deal(self, pairing: dict[str, Any], candidate: dict[str, Any], *, sale: bool = False) -> dict[str, Any]:
        """An agreed deal. The candidate is tagged (``market_deal``) so the review can say which agreed deals it
        chose to execute today and the apply step can record a cancellation with its reason."""
        row = pairing["row"]
        key = negotiation_key(pairing["buyer_id"], row["team_id"], row["id"])
        neg = self.open_negotiation(pairing)
        tag = {"key": key, "buyer_id": pairing["buyer_id"], "seller_id": row["team_id"], "player_id": row["id"],
               "player_name": row.get("name"), "date": self.date,
               "kind": "sale" if sale else "negotiation" if neg else "target",
               "seller_reasons": list(pairing.get("reasons") or []),
               "seller_stance": _stance(self.canonical, row["team_id"])}
        candidate["market_deal"] = tag
        self.deals[key] = {"pairing": pairing, "proposal_id": (candidate.get("proposal") or {}).get("id"), "tag": tag}
        return tag

    def hold_sale(self, war: dict[str, Any], reason: str) -> None:
        """A bidding war's winner that cannot be finalized today (its offer uses a player or pick already in another
        deal agreed today): the seller keeps the player on the market and decides again on a later market day."""
        if war in self.wars:
            self.wars.remove(war)
        war["status"] = "held"
        war["held_reason"] = reason
        self.waiting.append(war)

    # --- shopping and bidding -------------------------------------------------------------------------------
    def shopped(self, pairing: dict[str, Any]) -> bool:
        """A good player whose team has a stated reason to move him and two or more interested teams."""
        row = pairing["row"]
        return (bool(pairing.get("reasons")) and float(row.get("market") or row.get("value") or 0.0) >= SHOP_VALUE
                and len(self.interest.get(row["id"], ())) >= SHOP_MIN_BUYERS and not pairing.get("unsolicited"))

    def add_bid(self, pairing: dict[str, Any], candidate: dict[str, Any], options: list[dict[str, Any]],
                evaluation_canonical: dict[str, Any], order: int) -> None:
        bids = self.bids.setdefault(pairing["row"]["id"], [])
        entry = {"pairing": pairing, "candidate": candidate, "options": options, "order": order,
                 "evaluation_canonical": evaluation_canonical, "tried": set()}
        same = next((b for b in bids if b["pairing"]["buyer_id"] == pairing["buyer_id"]), None)
        if same is None:
            bids.append(entry)
        elif self.seller_margin(candidate, pairing["row"]["team_id"]) > self.seller_margin(same["candidate"], pairing["row"]["team_id"]):
            bids[bids.index(same)] = entry  # one bid per buyer (its target and its opinion can both find him)

    def seller_margin(self, candidate: dict[str, Any], seller_id: str) -> float:
        return self.gaps(candidate).get(seller_id, -99.0)

    def seller_price(self, candidate: dict[str, Any], seller_id: str) -> float:
        """The bid's price: the seller's textbook value of it over its threshold (personality terms taken out)."""
        evaluation = _evaluation_for(candidate, seller_id)
        return evaluation_price(evaluation) if evaluation else -99.0

    def resolve_bidding(self, evaluate, raise_options) -> list[dict[str, Any]]:
        """Each shopped player with bids: the bidding war (raises in rounds) and the seller's decision. Returns the
        winning bids to finalize today (each with its war record).

        BIDWAR-PRICE: bidders raise on the seller's textbook price, and the winner pays at least the second-best bid.
        When the seller prefers a lower bid for a stated reason of its own (``seller_preferences``), that bidder must
        raise its offer to the best price (``raise_to_floor``, within its own price limit); if it cannot, its offer
        still wins only when it is a slightly lower one (SLIGHT_GAP) and the reason is a strong one. Otherwise the
        seller takes the best price."""
        winners = []
        for pid in sorted(self.bids):
            bids = self.bids[pid]
            seller = bids[0]["pairing"]["row"]["team_id"]
            war = {"player_id": pid, "player_name": bids[0]["pairing"]["row"].get("name"), "seller_id": seller,
                   "date": self.date, "bidders": sorted({b["pairing"]["buyer_id"] for b in bids}), "rounds": []}
            price = lambda b: self.seller_price(b["candidate"], seller)  # noqa: E731
            lead = max(bids, key=lambda b: (price(b), -b["order"]))
            war["rounds"].append({"round": 1, "bids": {b["pairing"]["buyer_id"]: round(price(b), 2) for b in bids},
                                  "leader": lead["pairing"]["buyer_id"]})
            if len(bids) >= 2:
                for round_ in range(2, BIDDING_ROUNDS + 1):
                    raised = {}
                    for bid in sorted(bids, key=lambda b: b["order"]):
                        if bid is lead:
                            continue
                        better = None
                        for option in raise_options(bid)[:RAISE_CHECKS[min(2, self.depth)]]:
                            candidate = evaluate(bid, option)
                            if candidate is None:
                                continue
                            if self.seller_price(candidate, seller) > price(lead) + BID_RAISE_MIN:
                                better = candidate
                                break
                        if better is None:
                            # None of its built packages beats the leader: it adds one more asset of its own, as
                            # long as its own check still accepts (BIDWAR-PRICE: losing bidders bid up to their own
                            # limit, so the winner pays at least what the runner-up was willing to pay).
                            better = self.raise_to_floor(bid, seller, price(lead) + BID_RAISE_MIN, evaluate)
                        if better is not None:
                            bid["candidate"] = better
                            raised[bid["pairing"]["buyer_id"]] = round(price(bid), 2)
                    if not raised:
                        break
                    lead = max(bids, key=lambda b: (price(b), -b["order"]))
                    war["rounds"].append({"round": round_, "bids": raised, "leader": lead["pairing"]["buyer_id"]})
            winner = self.decide(war, bids, lead, seller, evaluate)
            war["winner"] = winner["pairing"]["buyer_id"]
            war["key"] = negotiation_key(war["winner"], seller, pid)
            war["winning_margin"] = self.seller_margin(winner["candidate"], seller)
            war["winning_price"] = round(price(winner), 2)
            war["winning_offer"] = _offer_summary(self.canonical, winner["candidate"])
            war["prices"] = {b["pairing"]["buyer_id"]: round(price(b), 2) for b in bids}
            others = [price(b) for b in bids if b is not winner]
            war["second_price"] = round(max(others), 2) if others else None
            war["best_price"] = round(max(price(b) for b in bids), 2)
            war["price_leader"] = max(bids, key=lambda b: (price(b), -b["order"]))["pairing"]["buyer_id"]
            entry = self.shopping.get(pid) or {}
            decide_by = self.current_decision_day(pid, seller)
            war["decide_by"] = decide_by
            user_bid = entry.get("user_bid") or {}
            if (user_bid.get("accepted_by_seller") and self.date <= decide_by
                    and user_bid_leads(user_bid, war["best_price"], war.get("leader_preferences") or {})):
                # The user's offer is the best one: the seller waits for the user until its decision day.
                war["status"] = "user_leads"
                self.waiting.append(war)
                continue
            row = _office(self.canonical, seller)
            early = EARLY_ACCEPT_BASE + (float(row["patience"]) / 20.0 if row else 2.5)
            if self.date < decide_by and war["winning_margin"] < early:
                war["status"] = "waiting"   # the seller waits for its decision day
                self.waiting.append(war)
                continue
            war["status"] = "sold"
            self.wars.append(war)
            winners.append({"bid": winner, "war": war})
        return winners

    def decide(self, war: dict[str, Any], bids: list[dict[str, Any]], lead: dict[str, Any], seller: str,
               evaluate) -> dict[str, Any]:
        """The seller's choice between the bids (BIDWAR-PRICE), recorded on the war as ``decision``: the best price
        ("best_price"), its preferred bidder raising to the best price ("matched"), or rarely a slightly lower bid
        for a stated reason ("lower_bid")."""
        preferences = {id(b): seller_preferences(self.canonical, seller, b["pairing"]["buyer_id"], b["candidate"])
                       for b in bids}
        war["leader_preferences"] = {k: round(v["points"], 2) for k, v in preferences[id(lead)].items()}
        war["decision"] = {"rule": "best_price"}
        if len(bids) < 2:
            return lead
        price = lambda b: self.seller_price(b["candidate"], seller)  # noqa: E731
        score = lambda b: price(b) + sum(v["points"] for v in preferences[id(b)].values())  # noqa: E731
        preferred = max(bids, key=lambda b: (score(b), price(b), -b["order"]))
        if preferred is lead or score(preferred) < score(lead) + PREFERENCE_EDGE:
            return lead
        reasons = favoring_reasons(self.canonical, seller, preferred["pairing"]["buyer_id"], preferences[id(preferred)],
                                   lead["pairing"]["buyer_id"], preferences[id(lead)])
        if not reasons:
            return lead
        floor = price(lead)
        gap = round(floor - price(preferred), 2)
        base = {"preferred": preferred["pairing"]["buyer_id"], "best_price_by": lead["pairing"]["buyer_id"],
                "gap": gap, "reasons": reasons}
        if gap <= 0:
            war["decision"] = {**base, "rule": "best_price", "tie_broken_by_preference": True}
            return preferred  # the same price: the seller's preference breaks the tie
        raised = self.raise_to_floor(preferred, seller, floor, evaluate)
        if raised is not None:
            preferred["candidate"] = raised
            war["decision"] = {**base, "rule": "matched", "raised_price": round(price(preferred), 2)}
            war["rounds"].append({"round": len(war["rounds"]) + 1, "bids": {base["preferred"]: round(price(preferred), 2)},
                                  "leader": base["preferred"], "matched": True})
            return preferred
        if lower_bid_allowed(gap, reasons):
            war["decision"] = {**base, "rule": "lower_bid"}
            return preferred
        war["decision"] = {**base, "rule": "best_price", "passed_over": base["preferred"]}
        return lead

    def raise_to_floor(self, bid: dict[str, Any], seller: str, floor: float, evaluate) -> dict[str, Any] | None:
        """A bidder raises its offer to ``floor``: one more asset of its own (a pick, a young player or a player the
        seller targets, the same additions a counter-offer asks for), the smallest that gets there and never one that
        jumps far past it (COUNTER_OVERSHOOT, as counters), checked in full.
        Used by a losing bidder in the rounds (to beat the leader) and by the seller's preferred bidder (to match the
        best price).
        The raise must stay within the buyer's own price limit (its own full check accepts it, personality premium
        included) and bring the seller's textbook price up to the floor."""
        from . import trade_counters as tc
        from .trade_targets import PRESCREEN_TOLERANCE, quick_net
        from .transactions import default_transaction_model_config
        buyer = bid["pairing"]["buyer_id"]
        pid = bid["pairing"]["row"]["id"]
        proposal = bid["candidate"].get("proposal") or {}
        seller_out = list(proposal.get("from_assets") or [])
        buyer_out = list(proposal.get("to_assets") or [])
        if proposal.get("from_team_id") != seller or proposal.get("transfers") or bid["candidate"].get("pick_obligation_terms"):
            return None
        config = default_transaction_model_config()
        need = floor - self.seller_price(bid["candidate"], seller)
        current = quick_net(self.canonical, seller, buyer_out, seller_out, config)
        scored = []
        for index, (kind, ask_out, give_out, _) in enumerate(tc.counter_options(
                self.canonical, seller, buyer, seller_out, buyer_out, fixed={("player", pid)})):
            if kind not in {"pick", "young_player", "target_player"} or ask_out != seller_out:
                continue
            gain = quick_net(self.canonical, seller, give_out, seller_out, config) - current
            if gain < need - PRESCREEN_TOLERANCE or gain > need + tc.COUNTER_OVERSHOOT:
                continue  # too small to get there, or a jump far past it (a first where a second would do)
            if quick_net(self.canonical, buyer, seller_out, give_out, config) < -9.0 - PRESCREEN_TOLERANCE:
                continue
            scored.append((gain, index, give_out))
        scored.sort(key=lambda s: s[:2])
        for _, _, give_out in scored[:FLOOR_CHECKS]:
            candidate = evaluate(bid, {"assets": tc._specs(give_out)})
            if candidate is None:
                continue
            own = _evaluation_for(candidate, buyer) or {}
            if own.get("accepted") and self.seller_price(candidate, seller) >= floor:
                return candidate
        return None

    def current_decision_day(self, pid: str, seller_id: str | None = None) -> str:
        """The seller's decision day for a shopped player: the one set when shopping began, or a new one if it has
        passed and he is still on the market."""
        entry = self.shopping.get(pid) or {}
        stored = str(entry.get("decide_by") or "")
        if stored and entry.get("status") in {"shopping", "bidding"}:
            if stored >= self.date:
                return stored
            if summer_hold(entry, self.day):
                return self.date  # its decision day passed between summer market days: it decides today
        return self.decision_day(seller_id or self.sellers.get(pid))

    def decision_day(self, seller_id: str) -> str:
        row = _office(self.canonical, seller_id)
        days = 2 + int(round(float(row["patience"]) / 25.0)) if row else 4
        day = date.fromordinal(self.day.toordinal() + days)
        if in_season(self.day):
            day = min(day, _deadline(self.day))
        return day.isoformat()

    # --- the record ------------------------------------------------------------------------------------------
    def updates(self) -> dict[str, Any]:
        rows = []
        for key, seen in sorted(self.observed.items()):
            if key in self.deals:
                continue
            if seen["combined"] < -NEAR_GAP:
                continue
            pairing = seen["pairing"]
            rows.append({"key": key, "buyer_id": pairing["buyer_id"], "seller_id": pairing["row"]["team_id"],
                         "player_id": pairing["row"]["id"], "player_name": pairing["row"].get("name"),
                         "gaps": seen["gaps"], "offer": seen["offer"], "seller_reasons": list(pairing.get("reasons") or []),
                         "seller_stance": _stance(self.canonical, pairing["row"]["team_id"]),
                         "unsolicited": bool(pairing.get("unsolicited"))})
        deals = [{"key": key, "player_id": d["pairing"]["row"]["id"], "proposal_id": d["proposal_id"],
                  "kind": (d.get("tag") or {}).get("kind")}
                 for key, d in sorted(self.deals.items())]
        shopping = []
        for pid, buyers in sorted(self.interest.items()):
            row = self.rows.get(pid) or {}
            reasons = self.reasons.get(pid) or []
            if (len(buyers) >= SHOP_MIN_BUYERS and reasons
                    and float(row.get("market") or row.get("value") or 0.0) >= SHOP_VALUE):
                shopping.append({"player_id": pid, "player_name": row.get("name"), "seller_id": self.sellers[pid],
                                 "reasons": list(reasons), "interested": sorted(buyers),
                                 "decide_by": self.current_decision_day(pid)})
        return {"date": self.date, "negotiations": rows, "deals": deals, "shopping": shopping,
                "wars": self.wars, "waiting": self.waiting, "unsolicited": self.unsolicited}


def _stance(canonical, team_id):
    from .trade_targets import team_stance, _state
    return team_stance(_state(canonical, team_id))


def _offer_summary(canonical: dict[str, Any], candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    from .trade_counters import asset_label
    from .transactions import trade_team_flows
    proposal = candidate.get("proposal") or {}
    out = {}
    try:
        for tid, outgoing, _ in trade_team_flows(proposal):
            out[tid] = [asset_label(canonical, a) for a in outgoing]
    except Exception:
        return None
    return out


# ------------------------------------------------------------------------------------------ the price of a bid

def _evaluation_for(candidate: dict[str, Any] | None, team_id: str) -> dict[str, Any] | None:
    return next((e for e in (candidate or {}).get("evaluations") or [] if e.get("perspective_team_id") == team_id), None)


def evaluation_price(evaluation: dict[str, Any]) -> float:
    """A team's textbook value of a deal over its threshold: its net with its personality terms (opinions, habits,
    concessions) taken out. Bidding wars are fought and settled on this price (BIDWAR-PRICE)."""
    personality = float((evaluation.get("personality_adjustments") or {}).get("total") or 0.0)
    return round(float(evaluation.get("net_value") or 0.0) - personality
                 - float(evaluation.get("acceptance_threshold") or 0.0), 3)


def _conference(canonical: dict[str, Any], team_id: str) -> str | None:
    return next((t.get("conference") for t in canonical.get("teams", []) if t.get("id") == team_id), None)


def _package_for(candidate: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    from .transactions import trade_team_flows
    try:
        return next((incoming for tid, _out, incoming in trade_team_flows(candidate.get("proposal") or {}) if tid == team_id), [])
    except Exception:
        return []


def _young_share(canonical: dict[str, Any], seller_id: str, package: list[dict[str, Any]]) -> float:
    """Share of a package's value (the seller's own value) in draft picks and players 24 or younger."""
    from .transactions import package_value_for_team, player_by_id
    total = young = 0.0
    for asset in package:
        try:
            value = max(0.0, float(package_value_for_team(canonical, [asset], seller_id)))
        except Exception:
            continue
        total += value
        if asset.get("kind") in {"pick", "pick_swap"}:
            young += value
        elif asset.get("kind") == "player":
            player = player_by_id(canonical, asset.get("id")) or {}
            try:
                age = float(player.get("display_age", player.get("age")) or 99.0)
            except (TypeError, ValueError):
                age = 99.0
            if age <= TIMELINE_YOUNG_AGE:
                young += value
    return young / total if total > 0 else 0.0


def seller_preferences(canonical: dict[str, Any], seller_id: str, buyer_id: str,
                       candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The seller's lasting, stated reasons to like one bid more than its price says (BIDWAR-PRICE), in value points
    by kind, each with its words:

    - ``opinion``: its scouts' view of a player in the package (front_office.player_opinion; also a player it is cool
      on), as in its full evaluation;
    - ``tax``: a tax-averse owner's extra weight on the tax a package saves (the "works hard to stay under the luxury
      tax" habit), as in its full evaluation;
    - ``picks``: an office that prizes draft picks, as in its full evaluation;
    - ``help_now``: a competing seller's urgency for a player who helps now, as in its full evaluation;
    - ``timeline``: a rebuilding or retooling seller's preference for a package of young players and picks;
    - ``rival``: a competing seller's reluctance to strengthen a contender in its own conference.

    Concessions in a negotiation are not reasons to prefer a bid and are left out. The first four are the seller's
    personality terms; the last two count only here, between bids, never in any acceptance check."""
    from .front_office import office
    out: dict[str, dict[str, Any]] = {}
    row = office(canonical, seller_id)
    if not row:
        return out
    evaluation = _evaluation_for(candidate, seller_id) or {}
    for term in (evaluation.get("personality_adjustments") or {}).get("terms") or []:
        kind = PREFERENCE_TERMS.get(term.get("key"))
        if not kind:
            continue
        item = out.setdefault(kind, {"points": 0.0, "texts": []})
        item["points"] += float(term.get("points") or 0.0)
        item["texts"].append(str(term.get("text") or ""))
    stance = _stance(canonical, seller_id)
    if stance in {"rebuild", "retool"}:
        share = _young_share(canonical, seller_id, _package_for(candidate, seller_id))
        if share > 0:
            out["timeline"] = {"points": TIMELINE_POINTS * share, "texts": [], "share": round(share, 2)}
    if stance in {"contend", "rise"} and buyer_id and _stance(canonical, buyer_id) == "contend":
        conference = _conference(canonical, seller_id)
        if conference and conference == _conference(canonical, buyer_id):
            out["rival"] = {"points": -RIVAL_POINTS, "texts": [], "conference": conference}
    return out


def _abbrev_of(canonical: dict[str, Any], team_id: str) -> str:
    return next((t.get("abbrev") for t in canonical.get("teams", []) if t.get("id") == team_id), None) or str(team_id)


def favoring_reasons(canonical: dict[str, Any], seller_id: str, preferred_id: str, preferred: dict[str, Any],
                     other_id: str, other: dict[str, Any]) -> list[dict[str, Any]]:
    """The seller's stated reasons to prefer one bid over another, largest first: each kind where the preferred bid is
    worth at least a quarter point more to it, in plain words."""
    seller = _abbrev_of(canonical, seller_id)
    winner, loser = _abbrev_of(canonical, preferred_id), _abbrev_of(canonical, other_id)
    out = []
    for kind in sorted(set(preferred) | set(other)):
        mine, theirs = preferred.get(kind) or {}, other.get(kind) or {}
        points = float(mine.get("points") or 0.0) - float(theirs.get("points") or 0.0)
        if points < 0.25:
            continue
        if kind == "opinion":
            liked = [t for t in mine.get("texts") or [] if "always liked" in t or "long connection" in t]
            cool = [t for t in theirs.get("texts") or [] if "lower on" in t]
            text = "; ".join(liked + cool) or f"{seller}'s scouts like {winner}'s players more"
        elif kind == "tax":
            text = f"{seller} works hard to stay under the luxury tax, and {winner}'s offer saves it more"
        elif kind == "picks":
            text = f"{seller} prizes draft picks, and {winner}'s offer has more of them"
        elif kind == "help_now":
            text = f"{seller} wants help now, and {winner}'s offer brings a player who gives it"
        elif kind == "timeline":
            text = (f"{seller} is rebuilding, and {winner}'s offer is built from young players and picks that fit its "
                    f"timeline")
        else:
            conference = theirs.get("conference") or ""
            text = (f"{seller} would rather not strengthen {loser}, a contender in its own "
                    f"{conference + ' ' if conference else ''}conference")
        out.append({"key": kind, "points": round(points, 2), "text": text})
    out.sort(key=lambda r: (-r["points"], r["key"]))
    return out


def lower_bid_allowed(gap: float, reasons: list[dict[str, Any]]) -> bool:
    """A lower bid wins only when it is slightly lower and the seller has a strong stated reason that makes it worth
    more to it overall (the rare exception; no dice)."""
    if gap <= 0:
        return True
    total = sum(float(r["points"]) for r in reasons)
    return (gap <= SLIGHT_GAP and max((float(r["points"]) for r in reasons), default=0.0) >= STRONG_REASON
            and total >= gap + PREFERENCE_EDGE)


def user_bid_leads(user_bid: dict[str, Any], best_price: float | None, leader_preferences: dict[str, float]) -> bool:
    """The user's recorded offer against the best AI price: it leads at that price or above, or (the same rare
    exception as between AI bids) slightly below it for a strong stated reason of the seller's."""
    if best_price is None:
        return True
    price = user_bid.get("price")
    if price is None:
        price = user_bid.get("margin")
    price = float(price if price is not None else -99.0)
    if price >= best_price:
        return True
    reasons = [{"key": k, "points": float(p) - float(leader_preferences.get(k) or 0.0)}
               for k, p in (user_bid.get("preferences") or {}).items()]
    reasons += [{"key": k, "points": -float(p)} for k, p in leader_preferences.items()
                if k not in (user_bid.get("preferences") or {})]
    reasons = [r for r in reasons if r["points"] >= 0.25]
    return lower_bid_allowed(best_price - price, reasons)


VALUE_WORDS = ((5.0, "a little more (less than a second-round pick)"), (14.0, "about a second-round pick"),
               (26.0, "about two second-round picks"), (40.0, "about a late first-round pick"),
               (55.0, "about a first-round pick"))


def value_words(points: float) -> str:
    """A value gap in the trade evaluation's points as draft picks (a future second is about 9.5, a late first about
    35, a future first about 43)."""
    for limit, words in VALUE_WORDS:
        if points <= limit:
            return words
    return "well over a first-round pick"


def decision_text(canonical: dict[str, Any], war: dict[str, Any]) -> str | None:
    """The seller's choice in a bidding war, in plain words (the trade's explanation and the Trade Market board)."""
    decision = war.get("decision") or {}
    seller = _abbrev_of(canonical, war.get("seller_id"))
    winner = _abbrev_of(canonical, war.get("winner"))
    reasons = "; ".join(r["text"] for r in decision.get("reasons") or [])
    rule = decision.get("rule")
    if rule == "lower_bid":
        best = _abbrev_of(canonical, decision.get("best_price_by"))
        return (f"{seller} took {winner}'s offer although {best}'s was worth slightly more to it (less than a "
                f"second-round pick more): {reasons}.")
    if rule == "matched":
        best = _abbrev_of(canonical, decision.get("best_price_by"))
        return (f"{seller} preferred {winner}'s offer ({reasons}) and {winner} raised it to match {best}'s, the best "
                f"price.")
    if len(war.get("bidders") or []) < 2:
        return None
    second = [t for t, p in (war.get("prices") or {}).items() if t != war.get("winner") and p == war.get("second_price")]
    if decision.get("passed_over"):
        passed = _abbrev_of(canonical, decision["passed_over"])
        return (f"{winner}'s offer was worth the most to {seller}. {seller} preferred {passed}'s ({reasons}), but "
                f"{passed} could not match the price.")
    if second and decision.get("tie_broken_by_preference"):
        return (f"{winner}'s offer was worth as much to {seller} as {_abbrev_of(canonical, sorted(second)[0])}'s, and "
                f"{seller} preferred it: {reasons}.")
    if second:
        return f"{winner}'s offer was worth the most to {seller}, more than {_abbrev_of(canonical, sorted(second)[0])}'s."
    return f"{winner}'s offer was worth the most to {seller}."


# ------------------------------------------------------------------------------------------ the save side

HELD_NO_ROOM = "no room for another trade today; the seller decides again on the next market day"
TERMINAL_SHOPPING = frozenset({"sold", "lapsed", "moved", "cancelled"})


def _new_shopping_entry(row: dict[str, Any], day: str) -> dict[str, Any]:
    return {"player_id": row["player_id"], "player_name": row.get("player_name"), "seller_id": row["seller_id"],
            "started": day, "decide_by": row.get("decide_by"), "reasons": list(row.get("reasons") or []),
            "status": "shopping", "interested": [], "bids": [], "rounds": 0}


def apply_market_updates(save: dict[str, Any], updates: dict[str, Any] | None, active: dict[str, Any],
                         chosen: set[str] | None = None) -> None:
    """Fold one day's market updates into the save's ledger (negotiations, shopping, wars, stats).

    ``chosen``: the agreed deals (their ``market_deal`` keys) the day's review will execute. An agreed deal it does
    not execute (no room left today) is not recorded as agreed: a negotiation stays open and a shopped player stays
    on the market. A chosen deal is recorded as agreed; the apply step then either completes it or cancels it with
    its reason the same day (``note_market_execution``). None: every agreed deal is chosen (tests, old callers)."""
    if not updates:
        return
    book = ledger(save)
    day = str(updates.get("date") or (save.get("state") or {}).get("current_date") or "")[:10]
    season = _season_label(date.fromisoformat(day))
    stats = book["stats"].setdefault(season, {})
    negotiations = book["negotiations"]

    def executes(key: str | None) -> bool:
        return chosen is None or key in chosen

    for deal in updates.get("deals") or []:
        if not executes(deal["key"]):
            stats["agreed_not_chosen"] = int(stats.get("agreed_not_chosen") or 0) + 1
            continue
        neg = negotiations.get(deal["key"])
        if neg and neg.get("status") in {"open", "final_offer"}:
            neg["status"] = "agreed"
            neg["last_date"] = day
            neg["agreed_date"] = day
            neg["proposal_id"] = deal.get("proposal_id")
        stats["deals_agreed"] = int(stats.get("deals_agreed") or 0) + 1
    for row in updates.get("negotiations") or []:
        neg = negotiations.get(row["key"])
        if neg is None or neg.get("status") in {"closed", "agreed", "lapsed"}:
            stats["negotiations_opened"] = int(stats.get("negotiations_opened") or 0) + 1
            neg = {"key": row["key"], "buyer_id": row["buyer_id"], "seller_id": row["seller_id"],
                   "player_id": row["player_id"], "player_name": row.get("player_name"), "opened": day,
                   "rounds": [], "status": "open", "reopened": 0}
            negotiations[row["key"]] = neg
        elif neg.get("status") == "dead":
            neg.update(status="open", reopened=int(neg.get("reopened") or 0) + 1, rounds=[], opened=day)
            stats["negotiations_reopened"] = int(stats.get("negotiations_reopened") or 0) + 1
        if neg["rounds"] and neg["rounds"][-1].get("date") == day:
            continue
        finals = []
        for team in (neg["buyer_id"], neg["seller_id"]):
            size, final = concession_size({**active, "trade_market_ledger": {"negotiations": {neg["key"]: neg}}},
                                          team, neg)
            if final:
                finals.append(team)
        neg["rounds"].append({"date": day, "gaps": row["gaps"], "offer": row.get("offer"),
                              "final_by": finals or None})
        neg["last_date"] = day
        if finals:
            # The final offer was made today and refused: the maker walks away.
            neg["status"] = "dead"
            neg["cooldown_until"] = date.fromordinal(date.fromisoformat(day).toordinal() + COOLDOWN_DAYS).isoformat()
            neg["death"] = {"date": day, "seller_reasons": row.get("seller_reasons"), "seller_stance": row.get("seller_stance"),
                            "final_by": finals}
            stats["final_offers_refused"] = int(stats.get("final_offers_refused") or 0) + 1
    for row in updates.get("shopping") or []:
        entry = book["shopping"].get(row["player_id"])
        if entry is None or entry.get("status") in TERMINAL_SHOPPING:
            entry = _new_shopping_entry(row, day)
            book["shopping"][row["player_id"]] = entry
            stats["players_shopped"] = int(stats.get("players_shopped") or 0) + 1
        entry["interested"] = sorted(set(entry.get("interested") or []) | set(row["interested"]))
        entry["last_date"] = day
        if str(entry.get("decide_by") or "") < day:
            entry["decide_by"] = row["decide_by"]  # still on the market after its decision day: a new deadline
    for war in list(updates.get("waiting") or []) + list(updates.get("wars") or []):
        entry = book["shopping"].get(war["player_id"])
        if entry is None or entry.get("status") in TERMINAL_SHOPPING:
            entry = _new_shopping_entry(war, day)
            entry["interested"] = list(war.get("bidders") or [])
            book["shopping"][war["player_id"]] = entry
        entry["rounds"] = int(entry.get("rounds") or 0) + len(war.get("rounds") or [])
        entry["bids"] = [{"date": day, "leader": war.get("winner"), "margin": war.get("winning_margin"),
                          "offer": war.get("winning_offer"), "bidders": war.get("bidders"),
                          "price": war.get("best_price"), "price_leader": war.get("price_leader"),
                          "leader_preferences": war.get("leader_preferences"),
                          "decision": (war.get("decision") or {}).get("rule")}] + list(entry.get("bids") or [])[:4]
        entry["interested"] = sorted(set(entry.get("interested") or []) | set(war.get("bidders") or []))
        entry["last_date"] = day
        status = war.get("status")
        if status == "sold" and not executes(war.get("key")):
            status = "held"
            war = {**war, "status": "held", "held_reason": HELD_NO_ROOM}
        if status == "sold":
            entry["status"] = "agreed"
            entry["winner"] = war.get("winner")
            entry["agreed_date"] = day
            entry["agreed_key"] = war.get("key")
            note = decision_text(active, war)
            if note:
                entry["sale_note"] = note
            book.setdefault("wars", []).append(war)
            stats["sales_agreed"] = int(stats.get("sales_agreed") or 0) + 1
            counted = "war_counted" if len(war.get("bidders") or []) >= 2 else "sale_counted"
            if not entry.get(counted):
                entry[counted] = True
                key = "bidding_wars" if counted == "war_counted" else "shopped_single_bidder_sales"
                stats[key] = int(stats.get(key) or 0) + 1
                rule = (war.get("decision") or {}).get("rule")
                if counted == "war_counted" and (rule in {"lower_bid", "matched"} or (war.get("decision") or {}).get("passed_over")):
                    name = {"lower_bid": "wars_won_by_lower_bid", "matched": "wars_preferred_bid_matched"}.get(
                        rule, "wars_preferred_bid_passed_over")
                    stats[name] = int(stats.get(name) or 0) + 1
        elif status == "user_leads":
            entry["status"] = "bidding"
            entry["user_leads"] = day
        else:
            entry["status"] = "bidding"
            if status == "held":
                entry["held"] = {"date": day, "reason": war.get("held_reason"), "leader": war.get("winner")}
                stats["sales_held"] = int(stats.get("sales_held") or 0) + 1
    for record in updates.get("unsolicited") or []:
        stats.setdefault("unsolicited_by_buyer", {})
        stats["unsolicited_by_buyer"][record["buyer_id"]] = int(stats["unsolicited_by_buyer"].get(record["buyer_id"]) or 0) + 1
        stats["unsolicited_star_offers"] = int(stats.get("unsolicited_star_offers") or 0) + 1
        if not record.get("engaged"):
            stats["unsolicited_refused"] = int(stats.get("unsolicited_refused") or 0) + 1
        book.setdefault("unsolicited", []).append(record)


def chosen_market_keys(proposals: list[dict[str, Any]]) -> set[str]:
    """The ``market_deal`` keys of the deals a review will execute today."""
    return {str((p.get("market_deal") or {}).get("key")) for p in proposals if (p.get("market_deal") or {}).get("key")}


def begin_market_day(save: dict[str, Any], active: dict[str, Any], day: str, payload: dict[str, Any] | None,
                     chosen: list[dict[str, Any]]) -> None:
    """A summer market day (free agency, late summer, camp: play.py's market hooks) keeps the same ledger as the
    season's: stale records closed, today's negotiations, shopping and bids recorded, and the deals the hook will
    try today recorded as agreed. Talks that end a day close but apart continue on the next market day."""
    refresh_ledger(save, active, day)
    season_rollover(save, day)
    apply_market_updates(save, (payload or {}).get("market_updates"), active, chosen=chosen_market_keys(chosen))


def release_agreements(save: dict[str, Any], proposals: list[dict[str, Any]], day: str) -> int:
    """Agreed deals the day's hook did not try after all (its trades for the day were used up): not agreements. A
    negotiation goes back to open, a shopped player back on the market with the reason."""
    book = save.get(LEDGER_KEY)
    if not isinstance(book, dict):
        return 0
    released = 0
    for proposal in proposals:
        tag = proposal.get("market_deal") or {}
        if not tag.get("key"):
            continue
        neg = (book.get("negotiations") or {}).get(tag["key"])
        if neg and neg.get("status") == "agreed" and neg.get("agreed_date") == day:
            neg["status"] = "open"
            released += 1
        entry = (book.get("shopping") or {}).get(tag.get("player_id"))
        if entry and entry.get("status") == "agreed" and entry.get("agreed_key") == tag["key"]:
            entry.update(status="bidding", held={"date": day, "reason": HELD_NO_ROOM, "leader": tag.get("buyer_id")})
            for war in reversed(book.get("wars") or []):
                if war.get("key") == tag["key"] and war.get("date") == day and war.get("status") == "sold":
                    war.update(status="held", held_reason=HELD_NO_ROOM)
                    break
            released += 1
    return released


APPLY_FAILURE_WORDS = {
    "not_applied_stale_assets": "a player or pick in the deal had moved or could no longer be traded",
    "not_applied_salary_legality": "the salaries no longer worked under the cap rules",
    "not_applied_roster_plan": "a team reconsidered the deal against its current roster",
    "not_applied_rejected": "the deal was no longer authorized",
    "not_found": "the deal could not be found when it was due to be completed",
    "not_applied": "another deal completed today already used one of its players or picks",
}


def failure_reason(result: dict[str, Any]) -> str:
    """Plain words for why an agreed deal failed the apply-time re-check, with the check's own issues."""
    status = str(result.get("status") or "not_applied")
    words = APPLY_FAILURE_WORDS.get(status, "the deal failed its final check")
    issues = [str(i) for i in (result.get("issues") or []) if i][:2]
    return f"{words} ({'; '.join(issues)})" if issues else words


def note_market_execution(save: dict[str, Any], proposal: dict[str, Any] | None, result: dict[str, Any],
                          day: str) -> None:
    """The apply step's answer for an agreed market deal (transactions.apply_trade_to_state): completed, or
    cancelled with the reason. A cancelled deal ends that negotiation (the buyer walks away for COOLDOWN_DAYS; the
    pairing comes back only on a real change, ``SearchMarket.reopen``) and a shopped player's sale is cancelled, so
    the same deal is never agreed again the next day. Other teams may still bid for him."""
    tag = (proposal or {}).get("market_deal") or {}
    book = save.get(LEDGER_KEY)
    if not tag.get("key") or not isinstance(book, dict):
        return
    day = str(day or tag.get("date") or "")[:10]
    season = _season_label(date.fromisoformat(day))
    stats = book.setdefault("stats", {}).setdefault(season, {})
    negotiations = book.setdefault("negotiations", {})
    entry = (book.get("shopping") or {}).get(tag.get("player_id"))
    sale = bool(entry and entry.get("status") == "agreed" and entry.get("agreed_key") == tag["key"])
    if result.get("status") == "applied":
        stats["agreed_executed"] = int(stats.get("agreed_executed") or 0) + 1
        neg = negotiations.get(tag["key"])
        if neg and neg.get("status") == "agreed":
            neg.update(status="closed", outcome="traded", closed_date=day)
        if sale:
            entry.update(status="sold", moved_to=tag.get("buyer_id"), sold_date=day)
        return
    reason = failure_reason(result)
    neg = negotiations.get(tag["key"])
    if neg is None:
        neg = {"key": tag["key"], "buyer_id": tag.get("buyer_id"), "seller_id": tag.get("seller_id"),
               "player_id": tag.get("player_id"), "player_name": tag.get("player_name"), "opened": day,
               "rounds": [], "reopened": 0}
        negotiations[tag["key"]] = neg
    neg.update(status="dead", last_date=day,
               cooldown_until=date.fromordinal(date.fromisoformat(day).toordinal() + COOLDOWN_DAYS).isoformat(),
               death={"date": day, "seller_reasons": tag.get("seller_reasons"), "seller_stance": tag.get("seller_stance"),
                      "cancelled": reason})
    if sale:
        entry.update(status="cancelled", cancelled_date=day, cancel_reason=reason)
        for war in reversed(book.get("wars") or []):
            if war.get("key") == tag["key"] and war.get("status") == "sold":
                war.update(status="cancelled", cancel_reason=reason)
                break
    stats["agreed_cancelled"] = int(stats.get("agreed_cancelled") or 0) + 1
    book.setdefault("cancelled", []).append({"date": day, "player_id": tag.get("player_id"),
                                             "player_name": tag.get("player_name"), "buyer_id": tag.get("buyer_id"),
                                             "seller_id": tag.get("seller_id"), "kind": tag.get("kind"),
                                             "reason": reason, "status": result.get("status")})


def refresh_ledger(save: dict[str, Any], active: dict[str, Any], today: str) -> None:
    """Close negotiations and shopping whose player has moved, and let stale ones lapse (every market day). An
    agreement still pending from an earlier day (the apply step never reached it) is cancelled with that reason."""
    book = save.get(LEDGER_KEY)
    if not isinstance(book, dict):
        return
    teams = {p.get("id"): p.get("team_id") for p in active.get("players", [])}
    day = date.fromisoformat(today[:10])
    season_stats = book.setdefault("stats", {}).setdefault(_season_label(day), {})
    for neg in (book.get("negotiations") or {}).values():
        if neg.get("status") in {"closed", "lapsed"}:
            continue
        if teams.get(neg.get("player_id")) != neg.get("seller_id"):
            neg["status"] = "closed"
            neg["closed_date"] = today
            neg["outcome"] = "traded" if teams.get(neg.get("player_id")) == neg.get("buyer_id") else "player_moved"
        elif neg.get("status") == "agreed" and str(neg.get("agreed_date") or neg.get("last_date") or "") < today:
            neg.update(status="dead", cooldown_until=date.fromordinal(day.toordinal() + COOLDOWN_DAYS).isoformat(),
                       death={"date": today, "cancelled": "the agreed deal was not completed"})
            season_stats["agreed_cancelled"] = int(season_stats.get("agreed_cancelled") or 0) + 1
        elif neg.get("status") in {"open", "final_offer"} and neg.get("last_date") and (
                day - date.fromisoformat(neg["last_date"])).days > NEGOTIATION_MAX_AGE:
            neg["status"] = "lapsed"
    for entry in (book.get("shopping") or {}).values():
        if entry.get("status") in TERMINAL_SHOPPING:
            continue
        if teams.get(entry.get("player_id")) != entry.get("seller_id"):
            entry["moved_to"] = teams.get(entry.get("player_id"))
            entry["status"] = "sold" if entry["moved_to"] == entry.get("winner") else "moved"
            entry["sold_date"] = today
        elif entry.get("status") == "agreed":
            entry.update(status="cancelled", cancelled_date=today, cancel_reason="the agreed deal was not completed")
            season_stats["agreed_cancelled"] = int(season_stats.get("agreed_cancelled") or 0) + 1
        elif entry.get("decide_by") and today > entry["decide_by"] and not summer_hold(entry, day):
            entry["status"] = "lapsed"


def summer_hold(entry: dict[str, Any], day: date) -> bool:
    """Outside the season, market days are days apart (free agency, then late summer, then camp): a seller with
    bids whose decision day passed between them decides at the next market day instead of letting the sale lapse."""
    if in_season(day) or not entry.get("bids"):
        return False
    last = str(entry.get("last_date") or entry.get("started") or "")
    return bool(last) and (day - date.fromisoformat(last[:10])).days <= NEGOTIATION_MAX_AGE


def season_rollover(save: dict[str, Any], today: str) -> None:
    """Drop finished records from earlier seasons (the stats per season are kept)."""
    book = save.get(LEDGER_KEY)
    if not isinstance(book, dict):
        return
    season = _season_label(date.fromisoformat(today[:10]))
    for key in ("negotiations", "shopping"):
        rows = book.get(key) or {}
        for k in list(rows):
            row = rows[k]
            stamp = str(row.get("last_date") or row.get("opened") or row.get("started") or "")
            if stamp and _season_label(date.fromisoformat(stamp[:10])) != season and row.get("status") not in {"open", "bidding", "shopping"}:
                del rows[k]


# ------------------------------------------------------------------------------------------ the user's side

FINAL_OFFER_PATIENCE = 45.0  # an AI office below this patience makes its offers to you final (respond by a date)
NOTABLE_SHOP_VALUE = 55.0    # shopped players worth an assistant GM text


def _abbrevs(save: dict[str, Any], active: dict[str, Any] | None = None) -> dict[str, str]:
    teams = (active or {}).get("teams") or []
    out = {t.get("id"): t.get("abbrev") for t in teams}
    for tid, row in ((save.get("front_office_traits") or {}).get("teams") or {}).items():
        out.setdefault(tid, row.get("abbrev"))
    return out


def _human_ids(save: dict[str, Any]) -> set[str]:
    from .save import human_controlled_team_ids
    return set(human_controlled_team_ids(save))


def _save_office(save: dict[str, Any], team_id: str) -> dict[str, Any] | None:
    from .front_office import traits_view
    return traits_view(save).get(team_id)


def record_dealing(save: dict[str, Any], team_id: str, day: str, kind: str) -> bool:
    """One dealing between the user's team and an AI office (an offer, a counter, a trade, a reply to its offer), at
    most one a day per office. The assistant GM's read on that office sharpens with these (front_office.office_hints)."""
    if not team_id or team_id in _human_ids(save):
        return False
    book = ledger(save)
    row = book.setdefault("dealings", {}).setdefault(team_id, {"count": 0, "days": []})
    if day in row["days"]:
        return False
    row["count"] = int(row.get("count") or 0) + 1
    row["days"] = (list(row.get("days") or []) + [day])[-20:]
    row["last_kind"] = kind
    return True


def dealings(save: dict[str, Any], team_id: str) -> int:
    return int((((save.get(LEDGER_KEY) or {}).get("dealings") or {}).get(team_id) or {}).get("count") or 0)


def user_offer_terms(save: dict[str, Any], offer: dict[str, Any], day: str) -> dict[str, Any] | None:
    """Whether an AI team's offer to the user is a final, take-it-or-leave-it offer, and the day to answer by: an
    impatient office makes every offer final, and in deadline week every office does."""
    from .transactions import trade_team_ids
    human = _human_ids(save)
    makers = [t for t in trade_team_ids(offer) if t not in human]
    if not makers:
        return None
    maker = makers[0]
    row = _save_office(save, maker)
    if not row:
        return None
    today = date.fromisoformat(day[:10])
    deadline_week = in_season(today) and 0 <= (_deadline(today) - today).days <= 6
    patience = float(row["patience"])
    if patience >= FINAL_OFFER_PATIENCE and not deadline_week:
        return None
    days = 1 if patience < 30 else 2
    respond_by = date.fromordinal(today.toordinal() + days)
    if in_season(today):
        respond_by = min(respond_by, _deadline(today))
    abbrev = row.get("abbrev") or maker
    why = "it is deadline week" if deadline_week and patience >= FINAL_OFFER_PATIENCE else "it is an impatient front office"
    return {"maker_id": maker, "respond_by": respond_by.isoformat(),
            "text": f"Final offer from {abbrev}: take it or leave it by {respond_by.isoformat()} ({why})."}


def expire_final_offers(save: dict[str, Any], today: str) -> int:
    """Final offers the user did not answer in time lapse; the maker walks away."""
    expired = 0
    for offer in save.get("user_trade_offers", []) or []:
        context = offer.setdefault("offer_context", {})
        final = context.get("final_offer") or {}
        if context.get("status") != "pending_user_review" or not final.get("respond_by"):
            continue
        if today > final["respond_by"]:
            context["status"] = "expired_final_offer"
            context["expired_date"] = today
            expired += 1
    return expired


def _latest_bid(entry: dict[str, Any]) -> dict[str, Any] | None:
    bids = [b for b in entry.get("bids") or [] if b.get("price") is not None or b.get("margin") is not None]
    return bids[0] if bids else None


def _latest_bid_price(entry: dict[str, Any]) -> float | None:
    """The best AI offer's price for a shopped player (the seller's textbook value of it over its threshold)."""
    bid = _latest_bid(entry)
    if bid is None:
        return None
    return float(bid["price"] if bid.get("price") is not None else bid["margin"])


def user_bid_state(active: dict[str, Any], entry: dict[str, Any]) -> tuple[str | None, str | None]:
    """The user's offer for a shopped player against the best AI offer, and why, in plain words (the Trade Market
    board). The same comparison the seller makes (``user_bid_leads``)."""
    user_bid = entry.get("user_bid") or {}
    if not user_bid:
        return None, None
    seller = _abbrev_of(active, entry.get("seller_id"))
    bid = _latest_bid(entry) or {}
    best = _latest_bid_price(entry)
    leader_id = bid.get("price_leader") or bid.get("leader")
    leader = _abbrev_of(active, leader_id) if leader_id else "Another team"
    if entry.get("status") == "sold" and entry.get("winner") and entry.get("winner") != user_bid.get("team_id"):
        winner = _abbrev_of(active, entry.get("winner"))
        return "outbid", entry.get("sale_note") or f"{seller} sold him to {winner}."
    if best is None or user_bid_leads(user_bid, best + BID_RAISE_MIN, bid.get("leader_preferences") or {}):
        return "leading", f"Your offer is the best {seller} has."
    mine = float(user_bid.get("price") if user_bid.get("price") is not None else user_bid.get("margin") or -99.0)
    return "outbid", (f"{leader}'s offer was worth more to {seller}; you'd need to add "
                      f"{value_words(best + BID_RAISE_MIN - mine)}.")


def user_offer_competition(active: dict[str, Any], save: dict[str, Any], candidate: dict[str, Any],
                           user_team_id: str, day: str) -> dict[str, Any] | None:
    """The user's offer for a player an AI team is shopping enters the same comparison as the AI bids.

    Returns, for the shopped player in this offer, the best AI bid's margin over the seller's price, the user's
    margin, and whether the user's offer is beaten (the seller then turns it down and asks for more than the best
    bid). The user's best offer is recorded on the shopping entry, so AI bidders must beat it on later days."""
    from .transactions import trade_team_flows
    shopping = (save.get(LEDGER_KEY) or {}).get("shopping") or {}
    if not shopping:
        return None
    proposal = candidate.get("proposal") or {}
    try:
        flows = trade_team_flows(proposal)
    except Exception:
        return None
    for tid, outgoing, _incoming in flows:
        if tid == user_team_id or tid in _human_ids(save):
            continue
        for asset in outgoing:
            entry = shopping.get(asset.get("id")) if asset.get("kind") == "player" else None
            if not entry or entry.get("seller_id") != tid or entry.get("status") not in {"shopping", "bidding"}:
                continue
            evaluation = next((e for e in candidate.get("evaluations") or [] if e.get("perspective_team_id") == tid), {})
            margin = float(evaluation.get("net_value") or 0.0) - float(evaluation.get("acceptance_threshold") or 0.0)
            # BIDWAR-PRICE: offers compete on the seller's textbook price, as the AI bids do; the same rare exception
            # (a slightly lower offer the seller prefers for a strong stated reason) applies to yours.
            price = evaluation_price(evaluation) if evaluation else -99.0
            full_preferences = seller_preferences(active, tid, user_team_id, candidate)
            preferences = {k: round(v["points"], 2) for k, v in full_preferences.items()}
            bid = _latest_bid(entry) or {}
            best = _latest_bid_price(entry)
            leader_preferences = bid.get("leader_preferences") or {}
            accepted = bool(evaluation.get("accepted"))
            required = (best + BID_RAISE_MIN) if best is not None else None
            own = {"price": price, "preferences": preferences}
            beaten = accepted and required is not None and not user_bid_leads(own, required, leader_preferences)
            preferred = accepted and required is not None and not beaten and price < required
            abbrev = _abbrevs(save, active).get(tid, tid)
            leader_id = bid.get("price_leader") or bid.get("leader")
            leader = _abbrev_of(active, leader_id) if leader_id else "Another team"
            others = [t for t in entry.get("interested") or [] if t != user_team_id]
            interest = (f"{len(others)} other team{'s' if len(others) != 1 else ''} interested; "
                        f"decision by {entry.get('decide_by')}")
            text = None
            if beaten:
                text = (f"{leader}'s offer for {entry.get('player_name')} is worth more to {abbrev}; you'd need to add "
                        f"{value_words(required - price)} ({interest}). Beat it to get him.")
            elif preferred:
                lead_prefs = {k: {"points": p} for k, p in leader_preferences.items()}
                reasons = favoring_reasons(active, tid, user_team_id, full_preferences, leader_id or "", lead_prefs)
                why = "; ".join(r["text"] for r in reasons) or "its own reasons"
                text = (f"Your offer is a little below {leader}'s, but {abbrev} prefers it for {entry.get('player_name')}: "
                        f"{why} ({interest}).")
            elif accepted:
                text = (f"Your offer is the best {abbrev} has for {entry.get('player_name')} right now "
                        f"(decision by {entry.get('decide_by')}).")
            current = entry.get("user_bid") or {}
            entry["interested"] = sorted(set(entry.get("interested") or []) | {user_team_id})
            current_price = current.get("price") if current.get("price") is not None else current.get("margin")
            if accepted and price > float(current_price if current_price is not None else -99.0):
                entry["user_bid"] = {"team_id": user_team_id, "margin": round(margin, 2), "price": round(price, 2),
                                     "preferences": preferences, "date": day, "accepted_by_seller": accepted}
            return {"player_id": asset.get("id"), "player_name": entry.get("player_name"), "seller_id": tid,
                    "best_margin": best, "best_price": best, "user_margin": round(margin, 2),
                    "user_price": round(price, 2), "beaten": beaten, "price_leader": bid.get("price_leader"),
                    "required_margin": required, "required_price": required,
                    "interested": len(others), "decide_by": entry.get("decide_by"), "text": text}
    return None


def market_board(active: dict[str, Any], save: dict[str, Any]) -> dict[str, Any]:
    """The Trade Market board: players being shopped, who is interested, how far talks have gone, your offers, the
    final offers waiting for you, and your assistant GM's read on each front office."""
    from .front_office import office_hints
    from .trade_targets import SELL_REASON_WORDS
    from .save import player_display_attribute_summary
    book = save.get(LEDGER_KEY) or {}
    today = str((save.get("state") or {}).get("current_date") or "")[:10]
    names = _abbrevs(save, active)
    human = _human_ids(save)
    players = {p.get("id"): p for p in active.get("players", [])}
    cutoff = date.fromordinal(date.fromisoformat(today).toordinal() - 10).isoformat() if today else ""
    shopped = []
    for entry in (book.get("shopping") or {}).values():
        status = entry.get("status")
        recent = str(entry.get("sold_date") or entry.get("last_date") or "") >= cutoff
        if status not in {"shopping", "bidding", "agreed"} and not (status == "sold" and recent):
            continue
        if status in {"shopping", "bidding", "agreed"} and str(entry.get("last_date") or "") < cutoff:
            continue
        pid = entry.get("player_id")
        player = players.get(pid) or {}
        try:
            overall = player_display_attribute_summary(active, pid).get("overall") if player else None
        except Exception:
            overall = None
        interested = list(entry.get("interested") or [])
        user_state, user_note = user_bid_state(active, entry)
        stage = ("sold" if status == "sold" else "deal agreed" if status == "agreed"
                 else "bidding war" if status == "bidding" and len(interested) >= 2 else "taking offers")
        shopped.append({
            "player_id": pid, "player_name": entry.get("player_name") or player.get("name"),
            "headshot_url": player.get("headshot_url"), "age": player.get("display_age", player.get("age")),
            "overall": overall, "team": names.get(entry.get("seller_id")), "team_id": entry.get("seller_id"),
            "why": [SELL_REASON_WORDS.get(r, str(r).replace("_", " ")) for r in entry.get("reasons") or []][:2],
            "interested_count": len(interested), "interested": [names.get(t, t) for t in interested if t not in human],
            "you_interested": bool(human & set(interested)), "stage": stage, "rounds": int(entry.get("rounds") or 0),
            "decide_by": entry.get("decide_by"), "started": entry.get("started"), "your_offer": user_state,
            "sold_to": names.get(entry.get("winner")) if status == "sold" else None,
            "your_offer_note": user_note, "sale_note": entry.get("sale_note") if status in {"sold", "agreed"} else None,
        })
    shopped.sort(key=lambda r: (r["stage"] == "sold", -(r["overall"] or 0), r["player_name"] or ""))
    finals = []
    for offer in save.get("user_trade_offers", []) or []:
        context = offer.get("offer_context") or {}
        final = context.get("final_offer")
        if context.get("status") == "pending_user_review" and final:
            finals.append({"proposal_id": (offer.get("proposal") or {}).get("id"), "team": names.get(final.get("maker_id")),
                           "respond_by": final.get("respond_by"), "text": final.get("text"),
                           "why": (offer.get("trade_reasons") or {}).get("text")})
    reads = {}
    for team in active.get("teams", []):
        if team["id"] in human:
            continue
        reads[team["abbrev"]] = office_hints(active, team["id"], dealings(save, team["id"]))
    stats = book.get("stats") or {}
    return {"date": today, "shopped": shopped, "final_offers": finals, "front_offices": reads,
            "season_stats": stats.get(_season_label(date.fromisoformat(today))) if today else None}


def assistant_texts(active: dict[str, Any], save: dict[str, Any], today: str) -> list[dict[str, Any]]:
    """The assistant GM's texts about the market (at most TEXTS_PER_DAY a day): final offers waiting for you, notable
    players being shopped with several teams interested, and bidding wars."""
    book = save.get(LEDGER_KEY) or {}
    names = _abbrevs(save, active)
    human = _human_ids(save)
    values = {v.get("player_id"): float(v.get("player_value") or 0.0) for v in active.get("player_asset_valuations") or []}
    messages = []
    for offer in save.get("user_trade_offers", []) or []:
        context = offer.get("offer_context") or {}
        final = context.get("final_offer")
        if context.get("status") == "pending_user_review" and final and str(context.get("created_date") or "") >= today:
            messages.append({"id": f"final-offer:{(offer.get('proposal') or {}).get('id')}", "date": today,
                             "kind": "final_offer", "title": "A final offer", "text": final.get("text"),
                             "target": "trade-market"})
    for entry in (book.get("shopping") or {}).values():
        bid = entry.get("user_bid") or {}
        if (entry.get("status") in {"shopping", "bidding"} and bid.get("accepted_by_seller")
                and entry.get("decide_by") == today):
            messages.append({"id": f"market:yours:{entry.get('player_id')}:{today}", "date": today, "kind": "your_bid",
                             "title": "Decision day",
                             "text": (f"{names.get(entry.get('seller_id'), '')} decides on {entry.get('player_name')} today. "
                                      f"Your offer is in the running: make it now if you still want him."),
                             "target": "trade-market", "player_id": entry.get("player_id")})
    for entry in sorted((book.get("shopping") or {}).values(), key=lambda e: -values.get(e.get("player_id"), 0.0)):
        if entry.get("status") not in {"shopping", "bidding"} or values.get(entry.get("player_id"), 0.0) < NOTABLE_SHOP_VALUE:
            continue
        interested = [t for t in entry.get("interested") or [] if t not in human]
        if len(interested) < SHOP_MIN_BUYERS or str(entry.get("last_date") or "") != today:
            continue
        team = names.get(entry.get("seller_id"), "")
        decide = entry.get("decide_by")
        if entry.get("status") == "bidding":
            text = (f"Bidding war: {team} is taking offers for {entry.get('player_name')} from {len(interested)} teams; "
                    f"decision by {decide}.")
            kind = "bidding_war"
        else:
            text = f"{team} is shopping {entry.get('player_name')}; {len(interested)} teams interested; decision by {decide}."
            kind = "shopping"
        messages.append({"id": f"market:{kind}:{entry.get('player_id')}:{entry.get('started')}", "date": today,
                         "kind": kind, "title": "Trade market", "text": text, "target": "trade-market",
                         "player_id": entry.get("player_id")})
    return messages[:TEXTS_PER_DAY]
