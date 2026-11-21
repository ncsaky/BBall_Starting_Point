"""Counter-offers for near-miss trades (trade AI step 3; docs/agents/tasks/trade-steps-3-5-plan.md).

Before this, an AI team answered every offer with yes or no. Real front offices answer a near miss with a counter:
"we'll do it if Jaden Ivey is in it" (Chicago turning Kevin Huerter into the younger Ivey, data/research/real_trades/
trades_2025_2027.json), or, when the other team has nothing they want, "add a second". Here, when one side of a deal is
a little short of its own price and the other side has room to give, the short side asks for one change:

1. **A player it targets** on the other team (its own trade targets, ``trade_targets.team_trade_targets``), added to
   the deal or in place of a piece it was getting;
2. otherwise **more value** in the order its phase prefers: rebuilding and retooling teams ask for a pick, then a
   young player, then salary relief (taking back less salary); teams competing now ask to keep a piece of their own
   out of the deal, then a pick, then a young player.

The counter must be legal and must leave the asking side close to its own price (at most COUNTER_OVERSHOOT above
it): it is a fair ask, not a gouge. The other side then decides with its own unchanged acceptance check
(``transactions.ai_trade_candidate_accepted`` for AI teams; the user decides for the user's team). One counter, and at
most one answer back (COUNTER_ROUNDS); then the deal dies or the buyer moves on to its alternatives.

Every counter is explained in plain words ("UTA asked for Jaden Ivey; DET agreed: he was out of its rotation").
The user's own evaluations are never changed; for the user's offers the AI only counters, it never decides for the
user, and the counter shown is the exact deal that is executed if the user accepts it.

Nothing here writes the league; the human team never asks (it is never the short AI side).
"""
from __future__ import annotations

from typing import Any

COUNTER_GAP = 20.0          # the short side may be at most this far below its price (about one second-round pick)
# A counter may leave the asking side at most this far above its price: about one second-round pick, the smallest
# piece real teams ask for (a future second is worth about 12-20 to a team here), and among the asks that close
# the gap the one closest to the price is chosen.
COUNTER_OVERSHOOT = 15.0
# Rounds of counters before a deal dies. Each round costs at most FULL_CHECKS_PER_COUNTER full checks; four rounds
# cover the real back-and-forth (an ask, an answer, a last concession from each side) while a deadline day's counters
# stay within COUNTER_CHECKS_PER_SEARCH full checks.
COUNTER_ROUNDS = 4
GAP_STEP = 0.5              # a counter must bring the two sides at least this much closer
RULE_GAP = 5.0              # a refusal on a rule (roster plan, draft spending) at or above price counts this far apart
FULL_CHECKS_PER_COUNTER = 3  # counter options sent to the full acceptance check, best first
AI_NEGOTIATION_FLOOR = -9.0  # transactions.ai_trade_candidate_accepted: one AI side may be up to 9 short ...
AI_NEGOTIATION_SUM = -2.0    # ... when the two sides' nets sum to at least -2
YOUNG_AGE = 23.5
YOUNG_DEVELOPMENT = 6.0
MAX_ASSETS_PER_SIDE = 5
COUNTERS_PER_SEARCH = {1: 12, 2: 40}  # counter attempts per market search (normal day, deadline week)
COUNTER_CHECKS_PER_SEARCH = {1: 24, 2: 80}  # full checks spent on counters per market search

KIND_WORDS = {"target_player": "a player it targets", "pick": "a pick", "young_player": "a young player",
              "keep_own": "to keep a piece of its own", "salary_relief": "to take back less salary",
              "swap_own": "a player of its own instead of a pick"}


def _tx():
    from . import transactions
    return transactions


def _tt():
    from . import trade_targets
    return trade_targets


def _key(asset: dict[str, Any]) -> tuple[str, str]:
    return (str(asset.get("kind")), str(asset.get("id") or asset.get("value")))


def asset_label(canonical: dict[str, Any], asset: dict[str, Any]) -> str:
    tx = _tx()
    if asset.get("kind") == "player":
        player = tx.player_by_id(canonical, asset.get("id")) or {}
        return str(player.get("name") or asset.get("label") or asset.get("id"))
    pick = tx.pick_by_id(canonical, asset.get("id")) if asset.get("kind") == "pick" else None
    if pick:
        return tx.pick_label(canonical, pick)
    return str(asset.get("label") or asset.get("id"))


def _pick_words(canonical: dict[str, Any], asset: dict[str, Any]) -> str:
    """'a 2029 second-round pick' or 'a 2030 first-round pick swap', never the long protection label."""
    tx = _tx()
    swap = asset.get("kind") == "pick_swap"
    pick = (tx.pick_swap_by_id(canonical, asset.get("id")) if swap else tx.pick_by_id(canonical, asset.get("id"))) or {}
    round_ = int(pick.get("round") or asset.get("round") or 2)
    season = str(pick.get("season") or asset.get("season") or "")[:4]
    words = f"{season} {'first' if round_ == 1 else 'second'}-round pick{' swap' if swap else ''}".strip()
    return f"a {words}"


def _words(canonical: dict[str, Any], asset: dict[str, Any]) -> str:
    return (_pick_words(canonical, asset) if asset.get("kind") in {"pick", "pick_swap"}
            else asset_label(canonical, asset))


def _net(canonical, team_id, incoming, outgoing, config) -> float:
    tx = _tx()
    return (_tt().quick_net(canonical, team_id, incoming, outgoing, config)
            - tx.acceptance_threshold(canonical, team_id, config))


def _unavailable(canonical: dict[str, Any]) -> set[str]:
    tx = _tx()
    memo = canonical.get("_trade_counter_unavailable")
    date = (canonical.get("meta") or {}).get("current_date")
    if memo is None or memo[0] is not canonical.get("players") or memo[1] != date:
        ids = (set(tx.recently_traded_player_ids(canonical, date)) | set(tx.recently_signed_player_ids(canonical, date))
               | set(tx.re_trade_hold_player_ids(canonical, date)))
        memo = (canonical.get("players"), date, ids)
        canonical["_trade_counter_unavailable"] = memo
    return memo[2]


def _stance(canonical: dict[str, Any], team_id: str) -> str:
    tt = _tt()
    return tt.team_stance(tt._state(canonical, team_id))


def tier_order(stance: str) -> list[str]:
    """What a team asks for when the other side has no player it targets, by phase."""
    if stance in {"rebuild", "retool"}:
        return ["pick", "young_player", "salary_relief"]
    if stance == "contend":
        return ["keep_own", "pick", "young_player"]
    return ["pick", "young_player", "keep_own"]


def counter_options(canonical: dict[str, Any], asking_id: str, giving_id: str, asking_out: list[dict[str, Any]],
                    giving_out: list[dict[str, Any]], *, fixed: set[tuple[str, str]] = frozenset(),
                    prefer_player_back: bool = False) -> list[tuple[str, list[dict], list[dict], str | None]]:
    """Every single change the asking side could ask for: (kind, new asking_out, new giving_out, target label).

    ``fixed``: assets that must stay in the deal (the target of a target-driven deal)."""
    tx, tt = _tx(), _tt()
    from .team_planning import core_commitment
    rows = tt.player_rows(canonical)
    in_deal = {_key(a) for a in [*asking_out, *giving_out]}
    unavailable = _unavailable(canonical)
    human = set(canonical.get("_human_team_ids") or [])
    targets = [] if asking_id in human else tt.team_trade_targets(canonical, asking_id)
    giving_stance = _stance(canonical, giving_id)
    options = []
    if len(giving_out) < MAX_ASSETS_PER_SIDE:
        for row in rows.values():
            if row["team_id"] != giving_id or ("player", row["id"]) in in_deal or row["id"] in unavailable:
                continue
            if core_commitment(canonical, giving_id, row["id"]) or tx.goat_exception_player(row["player"]):
                continue
            if ((tt.young_piece_kept(row, giving_stance) or tt.recent_lottery_pick(canonical, row["player"]))
                    and not tt.exposing_reasons(tt.team_sell_reasons(canonical, giving_id).get(row["id"], []))):
                continue
            asset = {"kind": "player", "id": row["id"], "label": row["name"]}
            label = None
            for target in targets:
                if tt.target_match(target, row) is not None:
                    label = target["label"]
                    break
            if label is None and prefer_player_back:
                # A competing seller losing a rotation player asks for one back.
                out_rows = [rows[a["id"]] for a in asking_out if a.get("kind") == "player" and a.get("id") in rows]
                if out_rows and row["on_court"] >= max(r["on_court"] for r in out_rows) - 6.0:
                    label = "a rotation player back"
            if label is not None:
                options.append(("target_player", asking_out, [*giving_out, asset], label))
                # ... or in place of one of the pieces it was getting (the usual shape: "Ivey instead of the pick").
                for other in giving_out:
                    if _key(other) not in fixed:
                        options.append(("target_player", asking_out,
                                         [a for a in giving_out if _key(a) != _key(other)] + [asset], label))
            elif (row["age"] <= YOUNG_AGE and row["development"] >= YOUNG_DEVELOPMENT and row["minutes"] < 24.0):
                options.append(("young_player", asking_out, [*giving_out, asset], None))
        seconds = []
        for pick in tx.tradeable_picks_for_team(canonical, giving_id):
            asset = {"kind": "pick", "id": pick["id"]}
            if ("pick", pick["id"]) in in_deal or pick.get("_obligation_locked"):
                continue
            options.append(("pick", asking_out, [*giving_out, asset], None))
            if int(pick.get("round") or 2) == 2:
                seconds.append((tx.pick_asset_value(pick, "neutral"), str(pick["id"]), asset))
        if len(seconds) >= 2 and len(giving_out) + 2 <= MAX_ASSETS_PER_SIDE:
            # "Two seconds": the most common real ask after one (Finney-Smith, LeVert, Isaiah Joe, Aaron Wiggins).
            cheapest = [asset for _, _, asset in sorted(seconds, key=lambda s: s[:2])[:2]]
            options.append(("pick", asking_out, [*giving_out, *cheapest], None))
    sheds_tax = None
    for asset in asking_out:
        if _key(asset) not in fixed:
            rest = [a for a in asking_out if _key(a) != _key(asset)]
            if not rest:
                # Taking a player for nothing back is a salary dump: only when the other side saves luxury tax.
                if sheds_tax is None:
                    from .trade_tax import tax_value
                    sheds_tax = tax_value(canonical, giving_id, [], giving_out) > 0.0
                if not sheds_tax:
                    continue
            options.append(("keep_own", rest, giving_out, None))
    for asset in giving_out:
        if asset.get("kind") == "player" and _key(asset) not in fixed and len(giving_out) > 1:
            options.append(("salary_relief", asking_out, [a for a in giving_out if _key(a) != _key(asset)], None))
    return options


def swap_pick_options(canonical: dict[str, Any], asking_id: str, asking_out: list[dict[str, Any]],
                      giving_out: list[dict[str, Any]], fixed: set[tuple[str, str]]) -> list[tuple]:
    """A buyer refusing to spend a pick on this player offers one of its own bench players or salary filler in its
    place ("Merrill instead of the second"). Never a core, committed or young building-block player, nor one who plays
    24 minutes or more for it."""
    tx, tt = _tx(), _tt()
    from .team_planning import core_commitment
    rows = tt.player_rows(canonical)
    in_deal = {_key(a) for a in [*asking_out, *giving_out]}
    unavailable = _unavailable(canonical)
    stance = _stance(canonical, asking_id)
    core = set(((canonical.get("team_plans") or {}).get(asking_id) or {}).get("core_ids") or [])
    picks = [a for a in asking_out if a.get("kind") in {"pick", "pick_swap"} and _key(a) not in fixed]
    options = []
    for row in rows.values():
        if (row["team_id"] != asking_id or ("player", row["id"]) in in_deal or row["id"] in unavailable
                or row["id"] in core or row["minutes"] >= 24.0 or core_commitment(canonical, asking_id, row["id"])
                or tt.young_piece_kept(row, stance) or tt.recent_lottery_pick(canonical, row["player"])
                or tx.goat_exception_player(row["player"])):
            continue
        for pick in picks:
            options.append(("swap_own", [a for a in asking_out if _key(a) != _key(pick)]
                            + [{"kind": "player", "id": row["id"], "label": row["name"]}], giving_out, None))
    return options


def choose_counters(canonical: dict[str, Any], asking_id: str, giving_id: str, asking_out: list[dict[str, Any]],
                    giving_out: list[dict[str, Any]], config: dict[str, Any], *, giving_is_ai: bool = True,
                    fixed: set[tuple[str, str]] = frozenset(), prefer_player_back: bool = False,
                    keep: int = FULL_CHECKS_PER_COUNTER, kinds: set[str] | None = None,
                    overshoot: float = COUNTER_OVERSHOOT) -> list[dict[str, Any]]:
    """The asking side's counters, best first: its first tier with any option that brings it to its price (by the
    quick price both sides use in the search) without passing it by more than COUNTER_OVERSHOOT; within a tier the
    option closest to its price. For an AI giving side the option must also stay inside the bounded AI negotiation
    (the giving side at most 9 short, the two nets summing to at least -2), which its full check then confirms."""
    options = counter_options(canonical, asking_id, giving_id, asking_out, giving_out, fixed=fixed,
                              prefer_player_back=prefer_player_back)
    if kinds is not None and "swap_own" in kinds:
        options += swap_pick_options(canonical, asking_id, asking_out, giving_out, fixed)
    order = ["target_player"] + tier_order(_stance(canonical, asking_id)) + ["swap_own"]
    scored: dict[str, list] = {kind: [] for kind in order}
    for index, (kind, new_ask_out, new_give_out, label) in enumerate(options):
        if kind not in scored or (kinds is not None and kind not in kinds):
            continue
        ask_net = _net(canonical, asking_id, new_give_out, new_ask_out, config)
        if ask_net < 0.0 or ask_net > overshoot:
            continue
        give_net = _net(canonical, giving_id, new_ask_out, new_give_out, config) if giving_is_ai else 0.0
        if giving_is_ai and (give_net < AI_NEGOTIATION_FLOOR or give_net + ask_net < AI_NEGOTIATION_SUM):
            continue
        scored[kind].append((ask_net, index, {"kind": kind, "asking_out": new_ask_out, "giving_out": new_give_out,
                                              "target_label": label, "asking_net": round(ask_net, 2),
                                              "giving_net": round(give_net, 2)}))
    for kind in order:
        if scored[kind]:
            return [item[2] for item in sorted(scored[kind], key=lambda s: s[:2])[:keep]]
    return []


def describe(canonical: dict[str, Any], asking_id: str, giving_id: str, before_ask_out: list[dict], before_give_out: list[dict],
             counter: dict[str, Any], *, giving_is_user: bool = False) -> dict[str, Any]:
    """The counter in plain words, plus the changed pieces."""
    tx, tt = _tx(), _tt()
    asking = tx.team_by_id(canonical, asking_id)["abbrev"]
    giving = tx.team_by_id(canonical, giving_id)["abbrev"]
    before_give = {_key(a) for a in before_give_out}
    before_ask = {_key(a) for a in before_ask_out}
    added = [a for a in counter["giving_out"] if _key(a) not in before_give]
    dropped_give = [a for a in before_give_out if _key(a) not in {_key(b) for b in counter["giving_out"]}]
    kept_own = [a for a in before_ask_out if _key(a) not in {_key(b) for b in counter["asking_out"]}]
    kind = counter["kind"]
    if kind == "target_player":
        ask = f"{asking} asked for {_words(canonical, added[0])} ({counter['target_label']})"
        if dropped_give:
            ask += f" instead of {_words(canonical, dropped_give[0])}"
    elif kind in {"pick", "young_player"}:
        ask = f"{asking} asked for {_words(canonical, added[0])} as well"
    elif kind == "keep_own":
        ask = f"{asking} wanted to keep {_words(canonical, kept_own[0])} out of the deal"
    elif kind == "swap_own":
        offered = [a for a in counter["asking_out"] if _key(a) not in before_ask]
        ask = (f"{asking} would not spend {_words(canonical, kept_own[0])} on him and offered "
               f"{_words(canonical, offered[0])} instead")
    else:
        ask = f"{asking} asked to leave {_words(canonical, dropped_give[0])} out of the deal"
    if giving_is_user:
        text = f"{ask}."
    else:
        why = ""
        if added and added[0].get("kind") == "player":
            reasons = tt.team_sell_reasons(canonical, giving_id).get(added[0]["id"], [])
            if reasons:
                why = f": {_words(canonical, added[0])} was {tt.SELL_REASON_WORDS.get(reasons[0], reasons[0].replace('_', ' '))}"
            else:
                why = ": it still came out ahead at that price"
        elif added:
            why = ": it still came out ahead with the pick included"
        elif kind == "keep_own" and not counter["asking_out"]:
            why = ": moving his salary for nothing still cut its luxury tax"
        text = f"{ask}; {giving} agreed{why}."
    return {"asking_team_id": asking_id, "giving_team_id": giving_id, "asking_team": asking, "giving_team": giving, "kind": kind,
            "target_label": counter.get("target_label"),
            "added": [{"kind": a.get("kind"), "id": a.get("id"), "label": _words(canonical, a)} for a in added],
            "removed": [{"kind": a.get("kind"), "id": a.get("id"), "label": _words(canonical, a)}
                        for a in [*dropped_give, *kept_own]],
            "text": text}


def _specs(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"kind": a.get("kind"), "value": a.get("id") or a.get("value")} for a in assets]


def _flows(candidate: dict[str, Any]) -> tuple[str, str, list[dict], list[dict]]:
    proposal = candidate.get("proposal") or {}
    return (proposal.get("from_team_id"), proposal.get("to_team_id"),
            list(proposal.get("from_assets") or []), list(proposal.get("to_assets") or []))


def short_side(candidate: dict[str, Any], human: set[str]) -> tuple[str, str, dict] | None:
    """(short AI team, other team, its evaluation) when exactly one side refused and could be satisfied by a counter:
    no premium-return or core-commitment refusal, and the short side's net within COUNTER_GAP of its price."""
    if (candidate.get("legality") or {}).get("status") != "legal":
        return None
    if candidate.get("pick_obligation_terms") or candidate.get("pick_trade_terms") or (candidate.get("proposal") or {}).get("transfers"):
        return None
    evaluations = candidate.get("evaluations") or []
    if len(evaluations) != 2:
        return None
    if any(e.get("decision") == "reject_premium_return" for e in evaluations):
        return None
    if any(str(r).startswith("Core commitment:") for e in evaluations for r in e.get("decision_reasons") or []):
        return None
    refused = [e for e in evaluations if not e.get("accepted") and e.get("perspective_team_id") not in human]
    accepted = [e for e in evaluations if e.get("accepted") or e.get("perspective_team_id") in human]
    if len(refused) != 1 or len(accepted) != 1:
        return None
    short = refused[0]
    gap = float(short.get("net_value") or 0.0) - float(short.get("acceptance_threshold") or 0.0)
    if gap < -COUNTER_GAP:
        return None
    return short["perspective_team_id"], accepted[0]["perspective_team_id"], short


def package_key(from_assets: list[dict[str, Any]], to_assets: list[dict[str, Any]]) -> str:
    """One deal's identity: what each side sends (order-free)."""
    return "|".join(",".join(sorted(f"{a.get('kind')}:{a.get('id') or a.get('value')}" for a in side))
                    for side in (from_assets, to_assets))


def disagreement(candidate: dict[str, Any], human: set[str]) -> float:
    """How far apart the AI sides still are: each refusing AI team's shortfall below its price, plus RULE_GAP when
    it refuses on a rule (roster plan, draft spending) while at or above its price. A counter must shrink this."""
    total = 0.0
    for e in candidate.get("evaluations") or []:
        if e.get("perspective_team_id") in human or e.get("accepted"):
            continue
        short = float(e.get("acceptance_threshold") or 0.0) - float(e.get("net_value") or 0.0)
        total += short if short > 0 else RULE_GAP
    return total


def _offer(canonical, candidate) -> dict[str, Any]:
    tx = _tx()
    from_id, to_id, from_assets, to_assets = _flows(candidate)
    nets = {tx.team_by_id(canonical, e["perspective_team_id"])["abbrev"]:
            round(float(e.get("net_value") or 0.0) - float(e.get("acceptance_threshold") or 0.0), 2)
            for e in candidate.get("evaluations") or [] if e.get("perspective_team_id")}
    return {"from_team": tx.team_by_id(canonical, from_id)["abbrev"], "to_team": tx.team_by_id(canonical, to_id)["abbrev"],
            "from_assets": [_words(canonical, a) for a in from_assets],
            "to_assets": [_words(canonical, a) for a in to_assets], "nets_over_price": nets}


def _options_for(canonical, asking_id, giving_id, asking_out, giving_out, config, decision, fixed, giving_is_ai=True):
    if decision == "reject_pick_investment":
        # Too much draft capital for this player: the buyer first offers a player of its own in place of the pick
        # ("Merrill instead of the second"), then asks to keep the pick (taking less is never a gouge, so only the
        # other side's bound applies).
        swaps = choose_counters(canonical, asking_id, giving_id, asking_out, giving_out, config, fixed=fixed,
                                kinds={"swap_own"}, overshoot=1e9, keep=2, giving_is_ai=giving_is_ai)
        keeps = [o for o in choose_counters(canonical, asking_id, giving_id, asking_out, giving_out, config,
                                            fixed=fixed, kinds={"keep_own"}, overshoot=1e9, keep=6,
                                            giving_is_ai=giving_is_ai)
                 if any(a.get("kind") in {"pick", "pick_swap"} for a in asking_out
                        if _key(a) not in {_key(b) for b in o["asking_out"]})]
        return swaps + keeps
    return choose_counters(canonical, asking_id, giving_id, asking_out, giving_out, config, fixed=fixed,
                           prefer_player_back=decision == "reject_roster_plan", giving_is_ai=giving_is_ai,
                           keep=FULL_CHECKS_PER_COUNTER + 3)


def ai_counter(canonical: dict[str, Any], candidate: dict[str, Any], *, seed: int, date: str, config: dict[str, Any],
               fixed: set[tuple[str, str]] = frozenset(), diagnostics: dict[str, Any] | None = None,
               rounds: int = COUNTER_ROUNDS, check_budget: int | None = None) -> dict[str, Any] | None:
    """A refused AI-AI deal negotiated by counters; the accepted deal (both AI checks), or None.

    Each round, the side that is short asks for one change (``choose_counters``) and the other side answers with its
    own full check. Either side may counter again, but every counter must narrow the gap between them
    (``disagreement``) and no package may come back; the deal dies when the short side has no ask that does, or
    after COUNTER_ROUNDS rounds. The whole chain (each round's offer, both sides' distance from their price and the
    plain-words reason) is returned on the deal."""
    tx = _tx()
    human = set(canonical.get("_human_team_ids") or [])
    history = []
    current = candidate
    from_id, to_id, first_from, first_to = _flows(candidate)
    seen = {package_key(first_from, first_to)}
    gap = disagreement(candidate, human)
    for round_ in range(1, rounds + 1):
        side = short_side(current, human)
        if side is None:
            return None
        asking_id, giving_id, evaluation = side
        if giving_id in human:
            return None
        _, _, from_assets, to_assets = _flows(current)
        asking_out, giving_out = (from_assets, to_assets) if asking_id == from_id else (to_assets, from_assets)
        options = _options_for(canonical, asking_id, giving_id, asking_out, giving_out, config,
                               evaluation.get("decision"), fixed)
        if diagnostics is not None:
            diagnostics["counter_attempts"] = diagnostics.get("counter_attempts", 0) + 1
        answered, checks = None, 0
        for option in options:
            new_from, new_to = ((option["asking_out"], option["giving_out"]) if asking_id == from_id
                                else (option["giving_out"], option["asking_out"]))
            key = package_key(new_from, new_to)
            if key in seen:
                continue  # no package comes back
            if checks >= FULL_CHECKS_PER_COUNTER or (
                    check_budget is not None and diagnostics is not None
                    and diagnostics.get("counter_checks", 0) >= check_budget):
                break
            seen.add(key)
            checks += 1
            report = tx.evaluate_trade_decision(
                canonical, tx.team_by_id(canonical, from_id)["abbrev"], tx.team_by_id(canonical, to_id)["abbrev"],
                _specs(new_from), _specs(new_to), seed=seed, date=date, config=config, context_ready=True,
                search_only=True)
            result = tx.candidate_from_decision(report)
            if diagnostics is not None:
                diagnostics["counter_checks"] = diagnostics.get("counter_checks", 0) + 1
            if (result.get("legality") or {}).get("status") != "legal":
                continue
            step = {**describe(canonical, asking_id, giving_id, asking_out, giving_out, option), "round": round_,
                    "offer": _offer(canonical, result)}
            if tx.ai_trade_candidate_accepted(canonical, result):
                history.append({**step, "answer": "agreed"})
                result["counter"] = {"rounds": round_, "steps": history, "text": " ".join(s["text"] for s in history)}
                return result
            new_gap = disagreement(result, human)
            if new_gap >= gap - GAP_STEP:
                continue  # not a real concession: the two sides are no closer
            gap = new_gap
            history.append({**step, "answer": "refused", "text": step["text"].split(";")[0] + "."})
            answered = result
            break
        if answered is None:
            return None  # nobody can concede more within its tolerance
        current = answered
    return None


def counter_round_limit(canonical: dict[str, Any], team_id: str, previous: int = 0) -> int:
    """How many counters an AI office makes to the user before its last one, which is its final offer (TRADE-MARKET):
    1 for a very impatient office to COUNTER_ROUNDS for a patient one; on deadline day the next counter is final."""
    from .front_office import office
    from .trade_market import _today, is_deadline_day, max_rounds
    row = office(canonical, team_id)
    if not row:
        return COUNTER_ROUNDS
    if is_deadline_day(_today(canonical)):
        return min(COUNTER_ROUNDS, previous + 1)
    return max(1, min(COUNTER_ROUNDS, max_rounds(float(row["patience"])) - 2))


def user_counter(canonical: dict[str, Any], candidate: dict[str, Any], user_team_id: str, *, seed: int, date: str,
                 config: dict[str, Any] | None = None, chain: list[dict[str, Any]] | None = None,
                 required_margin: float | None = None) -> dict[str, Any] | None:
    """The AI partner's counter to the user's offer, or None: only when the partner refused it but is a little short
    (``short_side``). The counter is the partner's best ask on the user's roster and picks (its targets first), and it
    is returned only when the partner's own full check accepts it; the user decides. The returned candidate is the
    exact deal (built by ``transactions.evaluate_trade``) that is executed if the user accepts it.

    ``chain``: this negotiation so far, as sent back by the trade window: the partner's earlier counters
    ({"package", "asking_net"}) and the user's earlier offers ({"package"}). A new counter never repeats a package
    and must ask for less than the partner's last counter (a real concession); after COUNTER_ROUNDS counters the
    partner stops countering."""
    tx = _tx()
    config = config or tx.default_transaction_model_config()
    chain = [c for c in (chain or []) if isinstance(c, dict)]
    previous = [c for c in chain if c.get("asking_net") is not None]
    if len(previous) >= COUNTER_ROUNDS:
        return None
    human = set(canonical.get("_human_team_ids") or []) | {user_team_id}
    side = short_side(candidate, human)
    if side is None:
        return None
    asking_id, giving_id, evaluation = side
    if giving_id != user_team_id:
        return None
    limit = counter_round_limit(canonical, asking_id, len(previous))
    if len(previous) >= limit:
        return None  # its last counter was its final offer
    from_id, to_id, from_assets, to_assets = _flows(candidate)
    asking_out, giving_out = (from_assets, to_assets) if asking_id == from_id else (to_assets, from_assets)
    seen = {str(c.get("package")) for c in chain} | {package_key(from_assets, to_assets)}
    ceiling = min((float(c["asking_net"]) for c in previous), default=None)
    options = _options_for(canonical, asking_id, giving_id, asking_out, giving_out, config,
                           evaluation.get("decision"), frozenset(), giving_is_ai=False)
    checks = 0
    for option in options:
        new_from, new_to = ((option["asking_out"], option["giving_out"]) if asking_id == from_id
                            else (option["giving_out"], option["asking_out"]))
        key = package_key(new_from, new_to)
        if key in seen or (ceiling is not None and option["asking_net"] > ceiling - GAP_STEP):
            continue  # never the same package twice; each new counter asks for less than the last one
        if checks >= FULL_CHECKS_PER_COUNTER:
            break
        checks += 1
        result = tx.evaluate_trade(canonical, tx.team_by_id(canonical, from_id)["abbrev"],
                                   tx.team_by_id(canonical, to_id)["abbrev"], _specs(new_from), _specs(new_to),
                                   seed=seed, date=date, config=config, context_ready=True)
        if (result.get("legality") or {}).get("status") != "legal":
            continue
        partner = next((e for e in result.get("evaluations") or [] if e.get("perspective_team_id") == asking_id), {})
        if not partner.get("accepted"):
            continue
        margin = float(partner.get("net_value") or 0.0) - float(partner.get("acceptance_threshold") or 0.0)
        if required_margin is not None and margin < required_margin:
            continue  # it must beat the best offer the partner already has for this player (TRADE-MARKET)
        round_ = len(previous) + 1
        step = {**describe(canonical, asking_id, giving_id, asking_out, giving_out, option, giving_is_user=True),
                "round": round_}
        final = round_ >= limit
        text = step["text"]
        if final:
            abbrev = tx.team_by_id(canonical, asking_id).get("abbrev")
            text = f"{text} This is {abbrev}'s final offer: take it or leave it."
        result["counter"] = {"rounds": round_, "steps": [step], "text": text, "for_user": True,
                             "package": key, "asking_net": option.get("asking_net"),
                             "last_round": final, "final_offer": final}
        return result
    return None


def seller_target_match(canonical: dict[str, Any], candidate: dict[str, Any], seller_id: str) -> str | None:
    """The first of the seller's own targets matched by a player it receives (measurement and explanation)."""
    tt = _tt()
    if seller_id in set(canonical.get("_human_team_ids") or []):
        return None
    rows = tt.player_rows(canonical)
    proposal = candidate.get("proposal") or {}
    incoming = proposal.get("to_assets") if proposal.get("from_team_id") == seller_id else proposal.get("from_assets")
    for asset in incoming or []:
        row = rows.get(asset.get("id")) if asset.get("kind") == "player" else None
        if row is None:
            continue
        for target in tt.team_trade_targets(canonical, seller_id):
            if tt.target_match(target, row) is not None:
                return target["label"]
    return None
