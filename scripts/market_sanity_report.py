#!/usr/bin/env python3
"""Front-office market sanity report: who does the AI think is most valuable?

Prints the top players by AI asset value (player_value) and by trade-target market value, how many players
tie at the top, and where well-known stars rank. Use it before/after any valuation change.

    PYTHONPATH=src .venv/bin/python scripts/market_sanity_report.py [--top 30] [--json-out PATH]
    NBA_GM_RATINGS_MODEL=inputs_v1 PYTHONPATH=src .venv/bin/python scripts/market_sanity_report.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.ratings_model import INPUTS_V1, install_inputs_model, ratings_model_for
from nba_gm_data.transactions import market_trade_target_value, with_transaction_context

ROOT = Path(__file__).resolve().parents[1]
WATCH = [
    "Victor Wembanyama", "Shai Gilgeous-Alexander", "Nikola Jokić", "Luka Dončić", "Giannis Antetokounmpo",
    "Anthony Edwards", "Jayson Tatum", "Cade Cunningham", "Jalen Brunson", "Stephen Curry", "Cooper Flagg",
    "Tyler Herro", "Ausar Thompson", "Donovan Clingan", "Stephon Castle",
]


def build(top: int) -> dict:
    canonical = load_app_canonical(ROOT)
    if ratings_model_for() == INPUTS_V1:
        install_inputs_model(canonical, ROOT)
    canonical = with_transaction_context(canonical)
    players = {p["id"]: p for p in canonical["players"]}
    rows = []
    for valuation in canonical["player_asset_valuations"]:
        player = players.get(valuation["player_id"])
        if not player:
            continue
        rows.append({
            "name": player["name"], "age": player.get("age"), "team": player.get("team_abbrev"),
            "player_value": valuation["player_value"], "market_value": market_trade_target_value(player, valuation),
            "on_court": valuation["on_court_value"], "surplus": valuation["contract_surplus"],
        })
    by_value = sorted(rows, key=lambda r: -r["player_value"])
    by_market = sorted(rows, key=lambda r: -r["market_value"])
    top_value = by_value[0]["player_value"]
    return {
        "ratings_model": ratings_model_for(),
        "ties_at_top_player_value": sum(1 for r in rows if r["player_value"] == top_value),
        "top_by_player_value": by_value[:top],
        "top_by_market_value": by_market[:top],
        "watch": {
            r["name"]: {"value_rank": by_value.index(r) + 1, "market_rank": by_market.index(r) + 1,
                        "player_value": r["player_value"], "market_value": r["market_value"], "on_court": r["on_court"]}
            for r in rows if r["name"] in WATCH
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--json-out")
    args = parser.parse_args()
    report = build(args.top)
    print(f"ratings model: {report['ratings_model']}; players tied at the top player_value: {report['ties_at_top_player_value']}")
    print(f"\n{'#':>3} {'by market value (trade targeting)':34s} {'mkt':>6} {'val':>6} {'onct':>5}")
    for i, r in enumerate(report["top_by_market_value"], 1):
        print(f"{i:>3} {r['name'][:22]:22s} {r['team'] or '':4s} {r['age'] or '':>4} {r['market_value']:6.1f} {r['player_value']:6.1f} {r['on_court']:5.1f}")
    print("\nWatch list (rank by asset value / by market value):")
    for name in WATCH:
        w = report["watch"].get(name)
        if w:
            print(f"  {name:26s} value #{w['value_rank']:<4} market #{w['market_rank']:<4} "
                  f"(value {w['player_value']:.1f}, market {w['market_value']:.1f}, on-court {w['on_court']:.1f})")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
