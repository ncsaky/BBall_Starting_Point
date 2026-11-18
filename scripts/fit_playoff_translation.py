#!/usr/bin/env python3
"""Fit the "playoff translation" recipe (trait_adapter) to real playoff production.

Evidence: data/research/player_playoff_stats.json (ESPN + Basketball Reference playoff box totals, 2013-14..2025-26).
Target: recent playoff Game Score per 36 minutes (Hollinger), seasons weighted by minutes x DECAY^(years ago).
Predictors: league percentiles of the player's SKILL and PHYSICAL inputs only (no tendencies: what a player chooses
to do stays a separate layer). Non-negative ridge, so a better skill never lowers the rating. Weights below
MIN_WEIGHT are dropped and the rest renormalized into an ADAPTER_SPEC recipe.

    PYTHONPATH=src .venv/bin/python scripts/fit_playoff_translation.py
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from fit_impact_value import ridge_nonnegative, wcorr  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.ratings_model import effective_inputs, install_inputs_model  # noqa: E402
from nba_gm_data.trait_adapter import ADAPTER_SPEC, _definitions, _percentile, _term_keys, scalar_value  # noqa: E402

DECAY = 0.8
LAST = 2026            # 2025-26 playoffs
FIRST = 2017
MIN_EFFECTIVE_MINUTES = 150.0
RIDGE = 3.0
MIN_WEIGHT = 0.03
WATCH = ["Nikola Jokić", "Giannis Antetokounmpo", "Shai Gilgeous-Alexander", "Luka Dončić", "Jayson Tatum",
         "Stephen Curry", "Jamal Murray", "Jalen Brunson", "Anthony Edwards", "Victor Wembanyama", "Derrick White",
         "Rudy Gobert", "Domantas Sabonis", "Tyrese Haliburton", "Donovan Mitchell", "Kawhi Leonard", "Draymond Green",
         "Trae Young", "Jaren Jackson Jr.", "Paolo Banchero", "LeBron James", "Kevin Durant", "Anthony Davis"]


def game_score(r):
    return (r["points"] + .4 * r["fgm"] - .7 * r["fga"] - .4 * (r["fta"] - r["ftm"]) + .7 * r.get("offensive_rebounds", 0)
            + .3 * r.get("defensive_rebounds", 0) + r["steals"] + .7 * r["assists"] + .7 * r["blocks"]
            - .4 * r.get("personal_fouls", 0) - r["turnovers"])


def weighted_rate(seasons):
    num = den = eff = 0.0
    for r in seasons:
        year = int(r["season"][:4]) + 1
        if year < FIRST or not r.get("minutes"):
            continue
        w = DECAY ** (LAST - year)
        num += w * game_score(r)
        den += w * r["minutes"]
        eff += w * r["minutes"]
    return (36.0 * num / den, eff) if den else (None, 0.0)


def candidate_keys():
    defs = _definitions()
    keys = set()
    for terms in ADAPTER_SPEC.values():
        for term, _ in terms:
            for input_id, outcome in _term_keys(term):
                keys.add(f"{input_id}:{outcome}" if outcome else input_id)
    keys |= {i for i in defs if i[0] in "SP"}
    return sorted(k for k in keys if k[0] in "SPF")   # skills, physical, pass families; no tendencies (T)


def scalar(defs, inputs, key):
    input_id, _, outcome = key.partition(":")
    if input_id not in defs:
        return None
    return scalar_value(defs[input_id], inputs.get(input_id), outcome or None)


GROUPS = {
    "shooting": [f"S{n:02d}" for n in range(1, 10)],
    "finishing": [f"S{n:02d}" for n in range(10, 16)],
    "creation": ["S16", "S17", "S18", "S19", "S20", "S24"],
    "post": ["S21", "S22", "S23"],
    "offball": [f"S{n:02d}" for n in range(25, 29)],
    "rebounding": [f"S{n:02d}" for n in range(29, 33)],
    "perimeter_defense": ["S33", "S34", "S35", "S36", "S38", "S39", "S41", "S42"],
    "interior_defense": ["S37", "S40", "S43", "S44", "S45", "S46"],
    "pass_reading": [f"F0{n}.recognition" for n in range(1, 10)],
    "size": ["P01", "P02", "P03", "P04"],
    "athletic": ["P05", "P06", "P07", "P08", "P10"],
}


def main():
    grouped = "--groups" in sys.argv
    canonical = load_app_canonical(ROOT)
    install_inputs_model(canonical, ROOT)
    defs = _definitions()
    keys = candidate_keys()
    players = [p for p in canonical["players"] if p.get("team_id")]
    raw = {}
    for p in players:
        inputs = effective_inputs(canonical, p["id"]) or {}
        raw[p["id"]] = {k: scalar(defs, inputs, k) for k in keys}
    tables = {k: sorted(v[k] for v in raw.values() if v[k] is not None) for k in keys}
    keys = [k for k in keys if len(tables[k]) >= 200]
    lower_better = {("P07", "s"), ("P09", "s"), ("P12", "s")}
    def pct(pid, k):
        v = raw[pid][k]
        if v is None:
            return 0.5
        q = _percentile(tables[k], v)
        return 1 - q if (k[:3], defs.get(k[:3], {}).get("primary_unit")) in lower_better else q
    playoff = json.loads((ROOT / "data/research/player_playoff_stats.json").read_text())["players"]
    rows = []
    for p in players:
        rec = playoff.get(str(p.get("espn_player_id") or ""))
        if not rec:
            continue
        rate, eff = weighted_rate(rec["playoffs"]["seasons"])
        reg, _ = weighted_rate(rec["regular"]["seasons"])
        if rate is None or eff < MIN_EFFECTIVE_MINUTES:
            continue
        feats = ([statistics.fmean(pct(p["id"], k) for k in g if k in keys) for g in GROUPS.values()] if grouped
                 else [pct(p["id"], k) for k in keys])
        rows.append((p["id"], p["name"], feats, rate, eff, reg))
    if "--blend" in sys.argv:
        # Blend with Basketball Index's playoff offensive talent grades (latest 3-year windows; local-only data):
        # half box-score Game Score, half playoff talent (shooting + playmaking + shot creation), each standardized.
        import csv, gzip
        talent = {}
        path = ROOT / "data/research/bbi/tools/playoff_talent_windows.csv.gz"
        for r in csv.DictReader(gzip.open(path, "rt")):
            if not r.get("player_id") or float(r.get("ss_off_minutes") or 0) < 150:
                continue
            if r["window"] not in ("2023-24 to 2025-26", "2022-23 to 2024-25"):
                continue
            try:
                value = (float(r["Overall_Shooting_Talent"]) + float(r["playmaking_talent"]) + float(r["Overall_Shot_Creation"])) / 3.0
            except (TypeError, ValueError):
                continue
            weight = 2.0 if r["window"].startswith("2023") else 1.0
            prev = talent.get(r["player_id"], (0.0, 0.0))
            talent[r["player_id"]] = (prev[0] + weight * value, prev[1] + weight)
        talent = {k: v[0] / v[1] for k, v in talent.items()}
        gm = [r[3] for r in rows]
        gmu, gms = statistics.fmean(gm), statistics.pstdev(gm)
        tv = [talent[r[0]] for r in rows if r[0] in talent]
        tu, ts = statistics.fmean(tv), statistics.pstdev(tv)
        rows = [(pid, nm, f, 0.5 * (rate - gmu) / gms + (0.5 * (talent[pid] - tu) / ts if pid in talent else 0.5 * (rate - gmu) / gms), eff, reg)
                for pid, nm, f, rate, eff, reg in rows]
        print(f"blend: {sum(1 for r in rows if r[0] in talent)} of {len(rows)} players have playoff talent grades")
    w = [e / (e + 400.0) for *_, e, _ in rows]
    y = [r[3] for r in rows]
    X = [r[2] for r in rows]
    mu = [statistics.fmean(c) for c in zip(*X)]
    sd = [statistics.pstdev(c) or 1.0 for c in zip(*X)]
    Z = [[1.0, *[(v - m) / s for v, m, s in zip(x, mu, sd)]] for x in X]
    idx = list(range(len(rows)))
    random.Random(5).shuffle(idx)
    oof = [0.0] * len(rows)
    for f in (idx[i::5] for i in range(5)):
        tr = [i for i in idx if i not in f]
        c = ridge_nonnegative([Z[i] for i in tr], [y[i] for i in tr], [w[i] for i in tr], RIDGE)
        for i in f:
            oof[i] = sum(a * b for a, b in zip(Z[i], c))
    coef = ridge_nonnegative(Z, y, w, RIDGE)
    # Recipe weights on the percentile scale (undo standardization), keep the meaningful ones.
    names_ = list(GROUPS) if grouped else keys
    raw_w = {k: c / s for k, c, s in zip(names_, coef[1:], sd) if c > 0}
    total = sum(raw_w.values())
    recipe = {k: v / total for k, v in raw_w.items() if v / total >= MIN_WEIGHT}
    t2 = sum(recipe.values())
    recipe = {k: round(v / t2, 3) for k, v in sorted(recipe.items(), key=lambda kv: -kv[1])}
    print(f"{len(rows)} players with >= {MIN_EFFECTIVE_MINUTES:.0f} decayed playoff minutes; "
          f"out-of-fold weighted r = {wcorr(y, oof, w):.3f}; regular-season Game Score r with playoff = "
          f"{wcorr(y, [r[5] or 0 for r in rows], w):.3f}")
    print("recipe:", recipe)
    # Score every rostered player with the recipe (as trait_adapter would), rank, and show the watch list.
    if grouped:
        comp = {p["id"]: sum(wt * statistics.fmean(pct(p["id"], k) for k in GROUPS[g] if k in keys) for g, wt in recipe.items()) for p in players}
    else:
        comp = {p["id"]: sum(wt * pct(p["id"], k) for k, wt in recipe.items()) for p in players}
    order = sorted(comp, key=lambda pid: -comp[pid])
    rank = {pid: n + 1 for n, pid in enumerate(order)}
    names = {p["id"]: p["name"] for p in players}
    print("top 25:", [names[pid] for pid in order[:25]])
    real = {r[0]: r[3] for r in rows}
    for nm in WATCH:
        pid = next((p["id"] for p in players if p["name"] == nm), None)
        if pid:
            print(f"  {nm:26s} rank {rank[pid]:4d}   target {real.get(pid, float('nan')):5.2f}")
    out = ROOT / ("output/playoff-fit/recipe_groups" + ("_blend" if "--blend" in sys.argv else "") + ".json" if grouped else "output/playoff-fit/recipe.json")
    out.write_text(json.dumps({"recipe": recipe, "players": len(rows), "keys": keys, "groups": GROUPS if grouped else None,
                               "oof_r": round(wcorr(y, oof, w), 3)}, indent=1))


if __name__ == "__main__":
    main()
