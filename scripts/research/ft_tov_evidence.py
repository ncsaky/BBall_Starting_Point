#!/usr/bin/env python3
"""RATINGS-FT-TOV research: held-out check of foul drawing and handle security, and before/after comparisons.

    PYTHONPATH=src .venv/bin/python scripts/research/ft_tov_evidence.py validate
    PYTHONPATH=src .venv/bin/python scripts/research/ft_tov_evidence.py compare BEFORE.json AFTER.json

validate: fit everything on 2023-24 and 2024-25 only (league rates, spread, player ratios, and the current Basketball
Index method restricted to the same two seasons), then score 2025-26:
  (a) rank correlation of each grade with the held-out per-chance rate (free throws over expected; turnovers over
      expected), the skill itself;
  (b) rank correlation with the raw held-out outcome from the ESPN box score (free throws per field-goal attempt;
      turnovers per used possession = TOV / (FGA + 0.44 FTA + TOV)), which also contains how often he attacks;
  (c) the "card plus chances" test: each method's grade, calibrated on the fit seasons to a rate multiplier, times the
      held-out season's own chances, against the ESPN outcome (mean absolute error and rank correlation).
The current canonical grades (built from all three seasons and the analyst claims, so they have seen 2025-26) are
shown as a reference. compare: league spread and named players for two built input files.
Writes output/ratings-ft-tov/validation.json.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data import bbi_evidence as be  # noqa: E402
from nba_gm_data import foul_security_evidence as fse  # noqa: E402

FIT = {"2024-25": 1.0, "2023-24": 0.6}
HELD = "2025-26"
NAMED = ["Deni Avdija", "Luka Dončić", "Stephon Castle", "Austin Reaves", "James Harden", "Anthony Davis",
         "Deandre Ayton", "Paolo Banchero", "Jaylen Brown", "Cade Cunningham"]
OUT = ROOT / "output/ratings-ft-tov"


def spearman(a: list[float], b: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    return statistics.correlation(ranks(a), ranks(b))


def load_universe() -> dict:
    return json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text())


def espn_held(universe: dict) -> dict[str, dict[str, float]]:
    careers = json.loads((ROOT / "data/research/player_career_stats.json").read_text())["players"]
    out = {}
    for p in universe["players"]:
        prof = careers.get(str(p.get("espn_player_id") or ""))
        rows = [r for r in (prof or {}).get("seasons", []) if r.get("season") == HELD]
        if len(rows) != 1:
            continue
        r = rows[0]
        fga, fta, tov, mins = (r.get(k) for k in ("fga", "fta", "turnovers", "minutes"))
        if None in (fga, fta, tov, mins) or fga <= 0 or mins <= 0:
            continue
        out[str(p["id"])] = {"ftr": fta / fga, "tov_pct": tov / (fga + 0.44 * fta + tov), "minutes": mins,
                             "fta36": 36 * fta / mins, "tov36": 36 * tov / mins}
    return out


def current_method_scores(root: Path) -> dict[str, dict[str, float]]:
    """The Basketball Index overlay's S24/S17 scores as they were before this task, from the fit seasons only."""
    mapping = be.load_mapping(root)
    mapping = {**mapping, "inputs": {iid: {k: v for k, v in mapping["inputs"][iid].items() if k != "measured_by"}
                                     for iid in fse.MEASURED_INPUTS}}
    saved, collect = dict(be.SEASON_WEIGHTS), be.collect_values
    be.SEASON_WEIGHTS.clear()
    be.SEASON_WEIGHTS.update(FIT)
    be.collect_values = lambda r, m: {k: v for k, v in collect(r, m).items() if k[0] in FIT}
    try:
        scores = be.player_input_scores(root, mapping)
    finally:
        be.SEASON_WEIGHTS.clear()
        be.SEASON_WEIGHTS.update(saved)
        be.collect_values = collect
    return {cid: {iid: v["z"] for iid, v in inputs.items()} for cid, inputs in scores.items()}


def canonical_grades(path: Path) -> dict[str, dict[str, float]]:
    section = json.loads(path.read_text())
    return {pid: {iid: float(doc["inputs"][iid]["value"]["grade"]) for iid in fse.MEASURED_INPUTS}
            for pid, doc in section["players"].items()}


def validate() -> dict:
    universe = load_universe()
    names = {str(p["id"]): p["name"] for p in universe["players"]}
    fit = fse.build(ROOT, universe, season_weights=FIT, fit_seasons=tuple(FIT))
    new = {cid: {iid: s["z"] for iid, s in v.items()} for cid, v in fit["scores"].items()}
    old = current_method_scores(ROOT)
    canon = canonical_grades(ROOT / "data/canonical/player_inputs_2026_27.json")
    espn = espn_held(universe)
    # Naive baselines from the same fit seasons: raw free-throw rate; turnovers per play used or created.
    naive: dict[str, dict[str, list[float]]] = {}
    held_rows = {}
    table = fse.collect_values(ROOT, set(fse.METRICS.values()))
    rows = fse.season_rows(table, [*FIT, HELD])
    for (season, _), r in rows.items():
        cid = r["cid"]
        if not cid:
            continue
        if season == HELD:
            held_rows[cid] = r
            continue
        w = FIT[season] * r["minutes"]
        acc = naive.setdefault(cid, {"fta": [0.0, 0.0], "tov": [0.0, 0.0]})
        acc["fta"][0] += w * r["fta"]; acc["fta"][1] += w * r["fga"]
        acc["tov"][0] += w * r["turnovers"]; acc["tov"][1] += w * (r["shots"] + r["turnovers"] + r["potential_assists"])
    naive_z = {cid: {"S24": a["fta"][0] / a["fta"][1] if a["fta"][1] else None,
                     "S17": -(a["tov"][0] / a["tov"][1]) if a["tov"][1] else None} for cid, a in naive.items()}

    pool = [cid for cid, p in fit["pooled"].items()
            if p["weight"] >= fse.SCALE_WEIGHT and cid in held_rows and held_rows[cid]["minutes"] >= 1000
            and cid in espn and cid in old and cid in canon]
    held_ratio = {}
    for cid in pool:
        r = held_rows[cid]
        held_ratio[cid] = {}
        for model in ("foul", "handle", "turnover"):
            o, e = fse.counts(r, model, fit["rates"])
            held_ratio[cid][model] = o / e if e > 0 else None

    def calibrate(z: dict[str, float], model: str) -> tuple[float, float]:
        """log(fit-season ratio) = a + b z over pool players (fit seasons only)."""
        xs, ys = [], []
        for cid in pool:
            p = fit["pooled"][cid][model]
            if z.get(cid) is not None and p["raw_ratio"]:
                xs.append(z[cid]); ys.append(math.log(p["raw_ratio"]))
        reg = statistics.linear_regression(xs, ys)
        return reg.intercept, reg.slope

    report = {"players": len(pool), "fit_seasons": list(FIT), "held_out": HELD, "inputs": {}}
    for iid, model, raw_key in (("S24", "foul", "ftr"), ("S17", "turnover", "tov_pct")):
        sign = -1 if iid == "S17" else 1
        methods = {
            "new (opportunity-adjusted, fit seasons)": {c: new[c][iid] for c in pool},
            "current method (fit seasons)": {c: old[c].get(iid) for c in pool},
            "naive raw rate (fit seasons)": {c: naive_z.get(c, {}).get(iid) for c in pool},
            "current canonical grade (has seen 2025-26)": {c: canon[c][iid] for c in pool},
        }
        rows_out = {}
        for label, z in methods.items():
            ids = [c for c in pool if z.get(c) is not None and held_ratio[c][model] is not None]
            entry = {
                "players": len(ids),
                "rank_corr_held_out_rate_over_expected": round(
                    spearman([z[c] for c in ids], [sign * held_ratio[c][model] for c in ids]), 3),
                "rank_corr_held_out_raw_outcome": round(
                    spearman([z[c] for c in ids], [sign * espn[c][raw_key] for c in ids]), 3),
            }
            if iid == "S17":
                hid = [c for c in ids if held_ratio[c]["handle"] is not None]
                entry["rank_corr_held_out_ball_losses_over_expected"] = round(
                    spearman([z[c] for c in hid], [-held_ratio[c]["handle"] for c in hid]), 3)
            if True:  # every method gets the same fit-season calibration
                a, b = calibrate(z, model)
                errors, preds, actual = [], [], []
                for c in ids:
                    r = held_rows[c]
                    _, e = fse.counts(r, model, fit["rates"])
                    scale = r["minutes"] * be.POSSESSIONS_PER_MINUTE / 75.0
                    predicted = e * math.exp(a + b * z[c]) / scale   # per 75
                    if iid == "S24":
                        value = predicted / r["fga"]
                    else:
                        value = predicted / (r["fga"] + 0.44 * r["fta"] + predicted)
                    preds.append(value); actual.append(espn[c][raw_key])
                    errors.append(abs(value - espn[c][raw_key]))
                entry["card_plus_chances_mae"] = round(sum(errors) / len(errors), 4)
                entry["card_plus_chances_rank_corr"] = round(spearman(preds, actual), 3)
            rows_out[label] = entry
        report["inputs"][iid] = rows_out
    # Named players: held-out actual vs the two fit-season methods' standing.
    named = {}
    for n in NAMED:
        cid = next((c for c, nm in names.items() if nm == n), None)
        if cid not in fit["pooled"]:
            continue
        named[n] = {"held_out_ftr": round(espn.get(cid, {}).get("ftr", float("nan")), 3),
                    "held_out_tov_pct": round(espn.get(cid, {}).get("tov_pct", float("nan")), 3),
                    "fit_free_throws_over_expected": round(fit["pooled"][cid]["foul"]["raw_ratio"], 3),
                    "held_free_throws_over_expected": round(held_ratio.get(cid, {}).get("foul") or float("nan"), 3),
                    "fit_turnovers_over_expected": round(fit["pooled"][cid]["turnover"]["raw_ratio"], 3),
                    "held_turnovers_over_expected": round(held_ratio.get(cid, {}).get("turnover") or float("nan"), 3)}
    report["named"] = named
    report["fit_rates"] = {m: {**{k: round(v, 4) for k, v in f["rates"].items()},
                               "usage_elasticity": round(f["usage_elasticity"], 3)} for m, f in fit["rates"].items()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "validation.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    return report


def compare(before: Path, after: Path) -> dict:
    universe = load_universe()
    names = {str(p["id"]): p["name"] for p in universe["players"]}
    b, a = json.loads(before.read_text())["players"], json.loads(after.read_text())["players"]
    # Rotation players: about a season of Basketball Index minutes (the grade scale's pool).
    pooled = fse.build(ROOT, universe)["pooled"]
    rotation = [c for c, p in pooled.items() if p["weight"] >= fse.SCALE_WEIGHT and c in a and c in b]
    out = {"rotation_players": len(rotation)}
    for iid in ("S24", "S17", "T18"):
        def val(sec, c):
            v = sec[c]["inputs"][iid]["value"]
            return float(v["grade"] if "grade" in v else v["probability"])
        vb = [val(b, c) for c in rotation]
        va = [val(a, c) for c in rotation]
        def summary(v):
            s = sorted(v)
            q = lambda p: s[min(len(s) - 1, int(p * (len(s) - 1)))]
            return {"sd": round(statistics.pstdev(v), 3), "min": round(s[0], 3), "p10": round(q(.1), 3),
                    "median": round(q(.5), 3), "p90": round(q(.9), 3), "max": round(s[-1], 3)}
        top = sorted(rotation, key=lambda c: -val(a, c))
        out[iid] = {"before": summary(vb), "after": summary(va),
                    "all_players_after_max": round(max(val(a, c) for c in a), 3),
                    "top15_after": [(names.get(c, c), round(val(b, c), 1), round(val(a, c), 1)) for c in top[:15]],
                    "bottom10_after": [(names.get(c, c), round(val(b, c), 1), round(val(a, c), 1)) for c in top[-10:]],
                    "top15_before": [(names.get(c, c), round(val(b, c), 1), round(val(a, c), 1))
                                     for c in sorted(rotation, key=lambda c: -val(b, c))[:15]],
                    "bottom10_before": [(names.get(c, c), round(val(b, c), 1), round(val(a, c), 1))
                                        for c in sorted(rotation, key=lambda c: -val(b, c))[-10:]],
                    "named": {n: (round(val(b, c), 1), round(val(a, c), 1)) for n in NAMED + [
                        "Shai Gilgeous-Alexander", "Jimmy Butler III", "Joel Embiid", "Trae Young", "Kawhi Leonard",
                        "Chris Paul", "Jalen Brunson", "Tyrese Haliburton"]
                              for c in [next((k for k, v in names.items() if v == n), None)] if c in a}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "compare.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    c = sub.add_parser("compare")
    c.add_argument("before", type=Path)
    c.add_argument("after", type=Path)
    args = ap.parse_args()
    result = validate() if args.cmd == "validate" else compare(args.before, args.after)
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
