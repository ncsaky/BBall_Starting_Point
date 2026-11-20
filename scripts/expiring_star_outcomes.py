#!/usr/bin/env python3
"""Where the league's best players with expiring contracts went in an offseason, and at what price (KEEP-STARS).

Measurement only. ``--before`` is a save taken before the offseason's re-signings (a probe's draft snapshot); the
league's top players by current on-court value (the trade code's valuation) whose contracts end that season are
followed into ``--after`` (a later save: the training-camp snapshot or the end state).

  PYTHONPATH=src:scripts .venv/bin/python scripts/expiring_star_outcomes.py \
      --before output/probe/snapshots/draft_2028/current/league.json --after output/probe/saves/league.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path, canonical):
    from nba_gm_data.save import canonical_with_save, ensure_league_save_defaults, load_save
    save = ensure_league_save_defaults(load_save(path), canonical)
    return save, canonical_with_save(canonical, save)


def contract_last_season(contract):
    seasons = [str(r.get("season")) for r in (contract or {}).get("seasons", []) if r.get("salary") is not None]
    return max(seasons) if seasons else None


def outcomes(before_path: Path, after_path: Path, top: int = 30) -> list[dict]:
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.transactions import with_transaction_context
    canonical = load_app_canonical(ROOT)
    save, active = load(before_path, canonical)
    season = str(save["meta"]["season"])
    priced = with_transaction_context(active)
    on_team = {p["id"]: p for p in priced["players"] if p.get("team_id")}
    ranked = sorted((v for v in priced.get("player_asset_valuations", []) if v.get("player_id") in on_team),
                    key=lambda v: -float(v.get("on_court_value") or 0.0))
    contracts = {c.get("player_id"): c for c in active.get("contracts", [])}
    expiring = [(i + 1, v) for i, v in enumerate(ranked[:top])
                if contract_last_season(contracts.get(v["player_id"])) == season]
    after, after_active = load(after_path, canonical)
    after_players = {p["id"]: p for p in after_active["players"]}
    after_contracts = {c.get("player_id"): c for c in after_active.get("contracts", [])}
    rows = []
    for rank, value in expiring:
        pid = value["player_id"]
        player = on_team[pid]
        now = after_players.get(pid, {})
        contract = after_contracts.get(pid) or {}
        new = [r for r in contract.get("seasons", []) if str(r.get("season")) > season and r.get("salary") is not None]
        how = next((log.get("transaction_type") for log in reversed(after.get("transaction_logs", []))
                    if (log.get("assets") or {}).get("player_id") == pid
                    and str(log.get("date") or "") >= f"{season[:4]}-06-01"
                    and str(log.get("date") or "") <= f"{int(season[:4]) + 1}-10-31"), None)
        rows.append({
            "rank": rank, "name": player["name"], "age": player.get("display_age", player.get("age")),
            "from": player["team_id"], "to": now.get("team_id"),
            "stayed": now.get("team_id") == player["team_id"],
            "first_salary_millions": round(float(new[0]["salary"]) / 1e6, 1) if new else None,
            "years": len(new), "how": how or ("retired" if pid in set(after.get("retired_player_ids", [])) else None),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    rows = outcomes(args.before, args.after, args.top)
    for r in rows:
        print(f"#{r['rank']:>2} {r['name']:<26} {r['age']!s:>4} {str(r['from']):<9} -> {str(r['to']):<9} "
              f"{'stayed' if r['stayed'] else 'MOVED ':<6} ${r['first_salary_millions']}M x {r['years']}  {r['how']}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
