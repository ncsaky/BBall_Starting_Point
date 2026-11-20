#!/usr/bin/env python3
"""Trade-search funnel on a saved league, one market day (measurement only; nothing is applied or saved).

For one date it runs the same AI-to-AI search the game runs that day and counts each stage: teams searching,
targets per team (by kind), pairings, packages built / screened / sent to the acceptance check, legal, accepted,
and who turned the rest down (the seller, the buyer, both, or a hard rule), plus the day's trade slots. With
``--no-limit`` the search runs past the day's slots, to show how many deals the market could supply.

  PYTHONPATH=src:scripts .venv/bin/python -u scripts/trade_funnel_probe.py \
      --save output/tv2/base-src/output/probe/snapshots/deadline_2027/current/league.json \
      --date 2027-02-05 --depth 2 --no-limit --out output/tv2/funnel/deadline_2027.json
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--save", type=Path, required=True)
    ap.add_argument("--date", help="market date (default: the save's date)")
    ap.add_argument("--depth", type=int, default=None, help="search depth (default: 2 in deadline week, else 1)")
    ap.add_argument("--limit", type=int, default=None, help="search limit (default: the day's slots + 3)")
    ap.add_argument("--no-limit", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    from nba_gm_data import transactions as tx
    from nba_gm_data import trade_targets as tt
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.save import canonical_with_save, load_save, season_start_year_from_date, trade_deadline_date
    from nba_gm_data.trade_calendar import market_day
    from nba_gm_data.trade_review import MarketReview

    saved = load_save(args.save)
    stamp = args.date or saved["state"]["current_date"]
    seed = int(saved["meta"].get("seed") or 17)
    start_year = season_start_year_from_date(stamp)
    deadline = trade_deadline_date(start_year)
    market = market_day(stamp, seed, start_year, deadline)
    to_deadline = (date.fromisoformat(deadline) - date.fromisoformat(stamp)).days
    depth = args.depth or (2 if 0 <= to_deadline <= 6 else 1)
    limit = 999 if args.no_limit else (args.limit or min(35, market["slots"] + 3))

    checks: list[dict] = []
    current = {"kind": None, "stage": "other"}
    original_ranked = tt.ranked_packages

    def ranked(canonical, pairing, *a, **k):
        current["kind"] = pairing["target"]["key"]
        current["stage"] = "target"
        return original_ranked(canonical, pairing, *a, **k)

    tt.ranked_packages = ranked
    original_dumps = tt.salary_dump_offers

    def dumps(*a, **k):
        current["kind"], current["stage"] = "salary_dump", "dump"
        return original_dumps(*a, **k)

    tt.salary_dump_offers = dumps
    original = tx.candidate_from_decision

    def recording(report):
        candidate = original(report)
        evals = candidate.get("evaluations") or []
        proposal = candidate.get("proposal") or {}
        row = {"legal": (candidate.get("legality") or {}).get("status") == "legal", "kind": current["kind"],
               "stage": current["stage"],
               "sides": [{"team": e.get("perspective_team_id"), "accepted": bool(e.get("accepted")),
                          "reasons": [str(r)[:110] for r in (e.get("decision_reasons") or [])
                                      if not str(r).startswith("Net value")][:2],
                          "net": round(float(e.get("net_value") or 0) - float(e.get("acceptance_threshold") or 0), 2),
                          "decision": e.get("decision"),
                          "seller": e.get("perspective_team_id") == proposal.get("from_team_id")} for e in evals]}
        checks.append(row)
        candidate["_funnel_row"] = len(checks) - 1
        return candidate

    tx.candidate_from_decision = recording
    original_accept = tx.ai_trade_candidate_accepted

    def accept(canonical, candidate):
        ok = original_accept(canonical, candidate)
        index = candidate.get("_funnel_row")
        if index is not None and index < len(checks):
            checks[index]["accepted"] = bool(ok)
        return ok

    tx.ai_trade_candidate_accepted = accept

    canonical = load_app_canonical(ROOT)
    active = canonical_with_save(canonical, deepcopy(saved))
    # Targets and pairings, measured on the same prepared context the search uses.
    review = MarketReview()
    prepared = review.prepare(active, None)
    human = set(prepared.get("_human_team_ids") or [])
    buyers = [t["id"] for t in prepared.get("teams", []) if t["id"] not in human]
    targets = {tid: tt.team_trade_targets(prepared, tid) for tid in buyers}
    excluded = tx.recently_traded_player_ids(prepared, stamp)
    import random
    pairings = tt.target_pairings(prepared, sorted(buyers), excluded, depth, tx.default_transaction_model_config(),
                                  random.Random(0))
    started = time.monotonic()
    result = tx.simulate_ai_trades(active, stamp, stamp, seed=seed, review=review, limit=limit, reserve_assets=True,
                                   search_depth=depth)
    seconds = time.monotonic() - started
    review.close()
    tx.candidate_from_decision = original
    tx.ai_trade_candidate_accepted = original_accept
    tt.ranked_packages = original_ranked
    tt.salary_dump_offers = original_dumps

    two_team = [c for c in checks if len(c["sides"]) == 2]
    legal = [c for c in two_team if c["legal"]]
    refused = Counter()
    decisions = Counter()
    for c in legal:
        if c.get("accepted"):
            continue
        seller = next((s for s in c["sides"] if s["seller"]), None)
        buyer = next((s for s in c["sides"] if not s["seller"]), None)
        s_ok = bool(seller and seller["net"] >= -9)
        b_ok = bool(buyer and buyer["net"] >= -9)
        if s_ok and b_ok:
            refused["hard rule or bounded sum"] += 1
        elif s_ok:
            refused["buyer short"] += 1
        elif b_ok:
            refused["seller short"] += 1
        else:
            refused["both short"] += 1
        for s in c["sides"]:
            if not s["accepted"]:
                decisions[f'{c["stage"]}/{c["kind"]} {"seller" if s["seller"] else "buyer"} {s["decision"]}: '
                          f'{(s["reasons"] or [""])[0]}'] += 1
    by_source = Counter(p.get("target_source") or ("three_team" if (p.get("proposal") or {}).get("transfers") else "other")
                        for p in result["proposals"])
    out = {
        "save": str(args.save), "date": stamp, "depth": depth, "limit": limit,
        "market_slots": market.get("slots"), "expected_slots": market.get("expected_slots"),
        "teams_searching": len(buyers),
        "teams_with_targets": sum(1 for v in targets.values() if v),
        "targets": sum(len(v) for v in targets.values()),
        "targets_by_kind": dict(Counter(t["key"] for v in targets.values() for t in v)),
        "pairings": len(pairings),
        "pairings_by_kind": dict(Counter(p["target"]["key"] for p in pairings)),
        "teams_with_pairings": len({p["buyer_id"] for p in pairings}),
        "diagnostics": {k: v for k, v in result["search_diagnostics"].items() if k != "financial_work"},
        "checks_two_team": len(two_team), "checks_legal": len(legal),
        "checks_accepted": sum(1 for c in legal if c.get("accepted")),
        "refused": dict(refused), "refusal_decisions": dict(decisions.most_common(25)),
        "checks_by_kind": dict(Counter(f'{c["stage"]}/{c["kind"]}' for c in legal)),
        "accepted_by_kind": dict(Counter(f'{c["stage"]}/{c["kind"]}' for c in legal if c.get("accepted"))),
        "proposals": result["proposal_count"], "proposals_by_source": dict(by_source),
        "proposal_texts": [((p.get("trade_reasons") or {}).get("text") or (p.get("proposal") or {}).get("id"))
                           for p in result["proposals"]],
        "seconds": round(seconds, 1),
    }
    text = json.dumps(out, indent=1)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")


if __name__ == "__main__":
    main()
