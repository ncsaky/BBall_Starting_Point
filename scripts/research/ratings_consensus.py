#!/usr/bin/env python3
"""Analyst consensus for the top players versus the game's order (ratings-consensus task, 2026-11-19).

Sources (each recorded per player):
- ESPN NBA Rank 2026 (top 100, 2026-09-24) and The Ringer Top 100 (2026-10-14 snapshot), fetched to
  output/ratings-consensus/raw/public_rankings.json (URLs inside).
- Nerd Sesh: position top-10 lists (two hosts, Aug-Sep 2026) and a 48-pick redraft of current players (2026-07-31),
  parsed from docs/ratings-evidence-2026-10-29/ into output/ratings-consensus/raw/nerd_sesh_rankings.json.
- Basketball Index impact (local only): the multi-metric impact consensus of scripts/research/consensus_impact_audit.py
  (LEBRON, DPM, DRIP, RAPTOR and two RAPM variants, 2023-24..2025-26, recency-weighted) and multi-year LEBRON itself,
  which is the target the engine's value model is fitted to.

Consensus rank: players ordered by the mean of the ranks they have among ESPN, Ringer, the Nerd Sesh redraft pick
and the Basketball Index impact rank (players with 1,000+ minutes in 2025-26). A player outside a top-100 list counts
as 110 there; a player not drafted in the 48-pick redraft or without enough minutes for the impact rank simply has
no entry for that source. The consensus is a diagnostic only: no rating is moved toward it (ratings-first rule).

Game side, for every rostered player: the engine's own overall / offense / defense (save.player_attribute_summary,
what tables and AI front offices read), the card header (player_profile.engine_header: the same number re-mapped by
league rank onto 50 + 15z), and the engine's fitted impact prediction (impact_value.predict, LEBRON units) that
decides the engine's order.

    PYTHONPATH=src .venv/bin/python scripts/research/ratings_consensus.py [--top 75]
Writes output/ratings-consensus/consensus.json and prints a markdown table.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))

RAW = ROOT / "output/ratings-consensus/raw"
OUT = ROOT / "output/ratings-consensus/consensus.json"
OUTSIDE_TOP_100 = 110
ALIASES = {"jaren jackson": "jaren jackson jr", "michael porter": "michael porter jr", "jimmy butler": "jimmy butler iii",
           "derrick jones": "derrick jones jr", "gary trent": "gary trent jr", "kelly oubre": "kelly oubre jr",
           "wendell carter": "wendell carter jr", "trey murphy": "trey murphy iii", "jabari smith": "jabari smith jr"}


def norm(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = "".join(ch if ch.isalnum() or ch == " " else " " for ch in text.replace("'", "").replace(".", ""))
    text = " ".join(text.split())
    return ALIASES.get(text, text)


def strip_suffix(name: str) -> str:
    parts = name.split()
    return " ".join(p for p in parts if p not in ("jr", "sr", "ii", "iii", "iv"))


def load_sources():
    public = json.loads((RAW / "public_rankings.json").read_text())
    lists = {}
    for item in public["lists"]:
        key = "espn" if "ESPN" in item["source"] else "ringer"
        lists[key] = {norm(p["name"]): p["rank"] for p in item["players"]}
    ns = json.loads((RAW / "nerd_sesh_rankings.json").read_text())
    redraft = {norm(p["name"]): p["pick"] for p in ns["redraft"]["picks"]}
    position = {}
    for ep in ns["episodes"]:
        for p in ep["players"]:
            ranks = [r for r in (p.get("list_a"), p.get("list_b")) if r]
            if ranks:
                position[norm(p["name"])] = (ep["position"], statistics.fmean(ranks), len(ranks))
    return lists, redraft, position


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=75)
    ap.add_argument("--min-minutes", type=float, default=1000.0)
    args = ap.parse_args()

    from consensus_impact_audit import consensus
    from nba_gm_data import impact_value
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.bbi_evidence import collect_values
    from nba_gm_data.player_profile import engine_header
    from nba_gm_data.ratings_model import effective_inputs, install_inputs_model
    from nba_gm_data.save import player_attribute_summary, trait_values_by_player

    lists, redraft, position = load_sources()
    canonical = load_app_canonical(ROOT)
    install_inputs_model(canonical, ROOT)
    players = [p for p in canonical["players"] if p.get("team_id") and effective_inputs(canonical, p["id"]) is not None]
    traits = trait_values_by_player(canonical)
    fit = impact_value.load_fit(ROOT)

    cons, _detail = consensus(ROOT)
    ids = [pid for pid in cons["offense"] if pid in cons["defense"] and cons["offense"][pid][1] >= args.min_minutes]
    impact_score = {pid: cons["offense"][pid][0] + cons["defense"][pid][0] for pid in ids}
    impact_rank = {pid: i + 1 for i, pid in enumerate(sorted(impact_score, key=lambda k: -impact_score[k]))}
    lebron_table = collect_values(ROOT, {"Multi-Year O-LEBRON", "Multi-Year D-LEBRON"})
    my_o = {cid: v for v, m, cid in (lebron_table.get(("2025-26", "Multi-Year O-LEBRON")) or {}).values() if cid}
    my_d = {cid: v for v, m, cid in (lebron_table.get(("2025-26", "Multi-Year D-LEBRON")) or {}).values() if cid}

    rows = {}
    for p in players:
        pid = p["id"]
        summary = player_attribute_summary(canonical, pid)
        card = engine_header(canonical, pid) or {}
        pred = impact_value.predict(fit, traits.get(pid, {}), p, impact_value._profile(canonical, p, traits.get(pid, {})),
                                    effective_inputs(canonical, pid))
        key = norm(p["name"])
        alt = strip_suffix(key)
        look = lambda table: table.get(key, table.get(alt))
        row = {"id": pid, "name": p["name"], "team": p.get("team_id"), "age": p.get("age"), "position": p.get("position"),
               "engine": {k: summary.get(k) for k in ("overall", "offense", "defense")},
               "card": {k: round(card.get(k, 0.0), 1) for k in ("ovr", "off", "def")},
               "fit": {k: round(v, 2) for k, v in pred.items()},
               "lebron_my": None if pid not in my_o else {"offense": round(my_o[pid], 2), "defense": round(my_d.get(pid, 0.0), 2),
                                                           "overall": round(my_o[pid] + my_d.get(pid, 0.0), 2)},
               "espn": look(lists["espn"]), "ringer": look(lists["ringer"]), "ns_redraft": look(redraft),
               "ns_position": look(position), "bbi_impact_rank": impact_rank.get(pid)}
        rows[pid] = row

    def rank_by(values):
        return {pid: i + 1 for i, pid in enumerate(sorted(values, key=lambda k: -values[k]))}

    engine_rank = rank_by({pid: r["engine"]["overall"] for pid, r in rows.items()})
    fit_rank = rank_by({pid: r["fit"]["overall"] for pid, r in rows.items()})
    lebron_rank = rank_by({pid: r["lebron_my"]["overall"] for pid, r in rows.items() if r["lebron_my"]})
    for pid, r in rows.items():
        r["engine_rank"], r["fit_rank"], r["lebron_my_rank"] = engine_rank[pid], fit_rank[pid], lebron_rank.get(pid)
        sources = []
        if r["espn"] or r["ringer"] or r["ns_redraft"]:
            sources += [r["espn"] or OUTSIDE_TOP_100, r["ringer"] or OUTSIDE_TOP_100]
        if r["ns_redraft"]:
            sources.append(r["ns_redraft"])
        if r["bbi_impact_rank"] and sources:
            sources.append(r["bbi_impact_rank"])
        r["consensus_mean"] = round(statistics.fmean(sources), 2) if sources else None
        analysts = [x for x in (r["espn"], r["ringer"], r["ns_redraft"]) if x]
        r["analyst_mean"] = round(statistics.fmean(analysts), 2) if analysts else None
    ranked = sorted((r for r in rows.values() if r["consensus_mean"] is not None), key=lambda r: (r["consensus_mean"], r["engine_rank"]))
    for i, r in enumerate(ranked):
        r["consensus_rank"] = i + 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"players": ranked, "method": __doc__}, indent=1, ensure_ascii=False))

    top = ranked[: args.top]
    print("| Cons | Player | ESPN | Ringer | NS redraft | NS pos | BBI impact | Real LEBRON | Engine fit | Game | Card OVR | Engine OVR | Gap |")
    print("|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in top:
        pos = r["ns_position"]
        pos_text = f"{pos[0]} {pos[1]:g}" if pos else ""
        dash = lambda x: "" if x is None else x
        print(f"| {r['consensus_rank']} | {r['name']} | {dash(r['espn'])} | {dash(r['ringer'])} | {dash(r['ns_redraft'])} | {pos_text} | "
              f"{dash(r['bbi_impact_rank'])} | {dash(r['lebron_my_rank'])} | {r['fit_rank']} | {r['engine_rank']} | {r['card']['ovr']} | "
              f"{r['engine']['overall']} | {r['engine_rank'] - r['consensus_rank']:+d} |")
    game_top = [r["engine_rank"] for r in top]
    cons_top = [r["consensus_rank"] for r in top]
    print(f"\nTop {len(top)} by consensus: rank correlation with game order {statistics.correlation(cons_top, game_top):.3f}; "
          f"median absolute rank gap {statistics.median(abs(a - b) for a, b in zip(cons_top, game_top)):.0f}")
    fit_top = [r["fit_rank"] for r in top]
    real = [(r["consensus_rank"], r["lebron_my_rank"]) for r in top if r["lebron_my_rank"]]
    print(f"Consensus vs real multi-year LEBRON order: {statistics.correlation(*zip(*real)):.3f} (n={len(real)}); "
          f"game order vs engine fit order identical: {game_top == fit_top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
