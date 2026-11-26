#!/usr/bin/env python3
"""RATINGS-FIVE-INPUTS: compare five player inputs with independent 2025-26 evidence across rotation players.

Inputs checked (from a built inputs file, default the committed data/canonical/player_inputs_2026_27.json.gz):
- T02 shot-location habit (rim / short paint / midrange / three shares of field-goal attempts);
- T08 involvement;
- rim finishing skills S10 layup, S12 dunk, S15 contact finishing;
- foul drawing T18 contact seeking and S24 craft;
- T17 effort allocation (its transition share), plus T09 cutting and T12 crash for the cut and putback play types.

Evidence (all 2025-26 regular season, players with MIN_MINUTES+ minutes):
- Basketball Index per-75 tables (data/research/bbi/values_recent.json.gz): rim, midrange, two-point and three-point
  attempts, rim FG%, free-throw attempts, true usage, usage rate;
- Basketball-Reference shooting (data/research/bref_shooting_2024_2026.json): share of attempts within 3 ft, FG% there;
- NBA.com play types (output/ratings-evidence/nba_playtypes_2026/, Synergy, offense): share of each player's
  possessions by play type (transition, cut, putbacks, ...), points per possession, free-throw share;
- the calibration targets file (ESPN season totals): minutes, attempts, free throws, usage.

    PYTHONPATH=src .venv/bin/python scripts/research/five_inputs_evidence.py [--inputs FILE] [--out FILE.json]

Research only: nothing is written except the output report.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
INPUTS = "data/canonical/player_inputs_2026_27.json.gz"
BBI_FILE = "data/research/bbi/values_recent.json.gz"
BREF_FILE = "data/research/bref_shooting_2024_2026.json"
TARGETS = "data/calibration/nba_2025_26_targets.json"
PLAYTYPE_DIR = "output/ratings-evidence/nba_playtypes_2026"
PLAY_TYPES = ("Transition", "Isolation", "PRBallHandler", "PRRollman", "Postup", "Spotup", "Handoff", "Cut",
              "OffScreen", "OffRebound", "Misc")
MIN_MINUTES = 500.0
BBI_METRICS = {
    "rim75": "Rim Shot Attempts Per 75 Possessions", "mid75": "Midrange FGA Per 75",
    "two75": "Stable 2PTA Per 75", "three75": "3PT FGA Per 75 Possessions", "three_rate": "3PT Attempt Rate",
    "rim_fg": "Rim FG%", "stable_rim_fg": "Stable Rim FG%", "fta75": "Stable FTA Per 75",
    "true_usage": "Stable True Usage%", "usage": "Usage Rate", "pts75": "Points Per 75 Possessions",
    "fouls_drawn75": "Stable Fouls Drawn Per 75", "sfd75": "Stable Shooting Fouls Drawn Per 75",
    "rim_unast": "% of Shots at Rim Unassisted", "two_dist": "Stable Avg 2PT Shot Distance",
    "drive_foul": "Drive Foul Drawn Rate", "cuts75": "Cuts Per 75 Possessions",
    "trans_impact": "Offensive Transition Frequency Impact", "putback75": "Stable Putback Points Per 75",
}
FLAGGED = ("Nolan Traoré", "Jaren Jackson Jr.", "DeMar DeRozan", "Brandon Ingram", "Zion Williamson", "Anthony Davis",
           "Myles Turner", "Anfernee Simons", "Jusuf Nurkić", "Peyton Watson", "Jaylon Tyson", "Pelle Larsson",
           "Toumani Camara", "Gary Payton II", "Russell Westbrook", "Collin Murray-Boyles", "Giannis Antetokounmpo",
           "Rudy Gobert", "Kristaps Porziņģis", "Josh Hart", "Jaden McDaniels")


def normalize(name: str) -> str:
    from nba_gm_data.input_estimator import _normalize
    return _normalize(name)


def flat_inputs(inputs: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for iid, rec in inputs.items():
        v = rec.get("value") or {}
        if "grade" in v:
            out[iid] = float(v["grade"])
        elif "probability" in v:
            out[iid] = float(v["probability"])
        elif v.get("rows"):
            for k, p in v["rows"][0]["probabilities"].items():
                out[f"{iid}.{k}"] = float(p)
        elif isinstance(v.get("display_grade"), dict):
            out[iid] = float(v["display_grade"]["grade"])
    return out


def load_inputs(path: Path) -> dict[str, dict[str, float]]:
    raw = gzip.open(path).read() if str(path).endswith(".gz") else path.read_bytes()
    return {pid: flat_inputs(doc["inputs"]) for pid, doc in json.loads(raw)["players"].items()}


def load_playtypes(root: Path) -> dict[str, dict[str, dict[str, float]]]:
    """normalized name -> play type -> {poss, pts, total_poss, fta_share, ...} summed over a player's teams."""
    out: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for pt in PLAY_TYPES:
        path = root / PLAYTYPE_DIR / f"synergy_{pt}_offensive_2025-26.json"
        if not path.exists():
            continue
        rs = json.loads(path.read_text())["resultSets"][0]
        h = rs["headers"]
        for row in rs["rowSet"]:
            r = dict(zip(h, row))
            a = out[normalize(r["PLAYER_NAME"])][pt]
            poss = float(r["POSS"] or 0)
            a["poss"] += poss
            a["pts"] += float(r["PTS"] or 0)
            a["fga"] += float(r["FGA"] or 0)
            a["fgm"] += float(r["FGM"] or 0)
            a["ft_poss"] += poss * float(r["FT_POSS_PCT"] or 0)
            a["sf_poss"] += poss * float(r["SF_POSS_PCT"] or 0)
            if r["POSS_PCT"]:
                a["total_poss"] += poss / float(r["POSS_PCT"])
    return out


def playtype_shares(pt: dict[str, dict[str, float]]) -> dict[str, float]:
    """Share of a player's possessions in each play type; total from the largest play type's own ratio."""
    if not pt:
        return {}
    ref = max(pt.values(), key=lambda a: a["poss"])
    total = ref["total_poss"]
    if total <= 0:
        return {}
    out = {k: a["poss"] / total for k, a in pt.items()}
    out["_total"] = total
    return out


def load_real(root: Path) -> dict[str, dict]:
    from nba_gm_data.input_estimator import _normalize
    targets = json.loads((root / TARGETS).read_text())["players"]
    table = json.load(gzip.open(root / BBI_FILE))["table"]
    bbi: dict[str, dict[str, float]] = defaultdict(dict)
    for key, metric in BBI_METRICS.items():
        for pid, row in (table.get(f"2025-26|{metric}") or {}).items():
            if row and row[0] is not None:
                bbi[pid][key] = float(row[0])
    bref = {}
    for p in json.loads((root / BREF_FILE).read_text())["players"].values():
        if isinstance(p, dict) and "name" in p:
            s = (p.get("seasons") or {}).get("2025-26")
            if s:
                bref[_normalize(p["name"])] = s
    pts = load_playtypes(root)
    out = {}
    for pid, t in targets.items():
        if float(t.get("minutes") or 0) < MIN_MINUTES:
            continue
        name = _normalize(t["name"])
        out[pid] = {"name": t["name"], "minutes": float(t["minutes"]), "t": t, "bbi": bbi.get(pid, {}),
                    "bref": bref.get(name, {}), "pt": pts.get(name, {}), "pt_share": playtype_shares(pts.get(name, {}))}
    return out


def stats(pairs: list[tuple[float, float]]) -> dict:
    """Correlation, spread ratio (input SD / evidence SD), slope of input on evidence, means."""
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None and math.isfinite(a) and math.isfinite(b)]
    if len(pairs) < 10:
        return {"n": len(pairs)}
    x, y = [p[0] for p in pairs], [p[1] for p in pairs]
    sx, sy = statistics.pstdev(x), statistics.pstdev(y)
    r = statistics.correlation(x, y) if sx > 0 and sy > 0 else None
    return {"n": len(pairs), "r": round(r, 3) if r is not None else None, "spread_ratio": round(sx / sy, 3) if sy else None,
            "slope": round(r * sx / sy, 3) if r is not None and sy else None,
            "mean_input": round(statistics.fmean(x), 4), "mean_evidence": round(statistics.fmean(y), 4)}


def rank_corr(pairs):
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if len(pairs) < 10:
        return None
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for k, i in enumerate(order):
            r[i] = k
        return r
    return round(statistics.correlation(ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])), 3)


def evidence_mix(r: dict) -> dict[str, float | None]:
    """Real shot mix and rates for one player."""
    b, br, t, sh = r["bbi"], r["bref"], r["t"], r["pt_share"]
    out: dict[str, float | None] = {}
    fga75 = (b.get("two75") or 0) + (b.get("three75") or 0)
    if b.get("rim75") is not None and b.get("three75") is not None and b.get("two75"):
        out["bbi_rim"] = b["rim75"] / fga75
        out["bbi_three"] = b["three75"] / fga75
        if b.get("mid75") is not None:
            out["bbi_mid"] = b["mid75"] / fga75
    out["bref_rim"] = br.get("pct_fga_00_03")
    out["three_rate"] = (t["fg3a_per36"] / t["fga_per36"]) if t.get("fga_per36") else None
    out["fta_per_fga"] = (t["fta_per36"] / t["fga_per36"]) if t.get("fga_per36") else None
    out["usage_pct"] = t.get("usage_pct")
    out["scoring_usage36"] = t["fga_per36"] + .44 * t["fta_per36"] + t["turnovers_per36"]
    out["true_usage"] = b.get("true_usage")
    out["bbi_usage"] = b.get("usage")
    out["rim_fg"] = b.get("rim_fg")
    out["stable_rim_fg"] = b.get("stable_rim_fg")
    out["bref_rim_fg"] = br.get("fg_pct_00_03")
    out["dunk_share"] = br.get("pct_fga_dunk")
    for k in ("Transition", "Cut", "OffRebound", "PRRollman", "Isolation", "PRBallHandler", "Postup", "Spotup"):
        # Missing from a play-type table = under 10 possessions (about zero), except transition, where a few
        # high-volume players are absent altogether (Russell Westbrook): not measured.
        out[f"pt_{k}"] = (sh.get(k) if k == "Transition" else sh.get(k, 0.0)) if sh else None
    out["pt_total_poss"] = sh.get("_total") if sh else None
    if r["pt"]:
        tr = r["pt"].get("Transition")
        out["trans_ppp"] = tr["pts"] / tr["poss"] if tr and tr["poss"] else None
        ftp = sum(a["ft_poss"] for a in r["pt"].values())
        poss = sum(a["poss"] for a in r["pt"].values())
        out["pt_ft_share"] = ftp / poss if poss else None
    return out


def compare(inputs: dict[str, dict[str, float]], real: dict[str, dict]) -> dict:
    rows = []
    for pid, r in real.items():
        f = inputs.get(pid)
        if not f:
            continue
        rows.append((pid, r, f, evidence_mix(r)))
    def S(fx, fy):
        return stats([(fx(f), fy(e)) for _, _, f, e in rows])
    def nonthree(f, k):
        rest = 1 - f["T02.three"]
        return f[f"T02.{k}"] / rest if rest > 0 else None
    def nonthree_e(e, k):
        rest = 1 - (e.get("bbi_three") or 0)
        return e.get(f"bbi_{k}") / rest if e.get(f"bbi_{k}") is not None and rest > 0 else None
    out = {
        "players": len(rows),
        "T02": {
            "rim_vs_bbi": S(lambda f: f["T02.rim"], lambda e: e.get("bbi_rim")),
            "rim_vs_bref_0_3ft": S(lambda f: f["T02.rim"], lambda e: e.get("bref_rim")),
            "bbi_rim_vs_bref": stats([(e.get("bbi_rim"), e.get("bref_rim")) for *_, e in rows]),
            # Basketball Index's "midrange" attempts are all twos outside the rim area (short paint + midrange).
            "other_twos_vs_bbi": S(lambda f: f["T02.short_paint"] + f["T02.midrange"], lambda e: e.get("bbi_mid")),
            "three_vs_bbi": S(lambda f: f["T02.three"], lambda e: e.get("bbi_three")),
            "three_vs_box": S(lambda f: f["T02.three"], lambda e: e.get("three_rate")),
            "rim_of_twos_vs_bbi": S(lambda f: nonthree(f, "rim"), lambda e: nonthree_e(e, "rim")),
        },
        "T08": {
            "vs_true_usage": S(lambda f: f["T08"], lambda e: (e.get("true_usage") or 0) / 100 or None),
            "vs_usage_rate": S(lambda f: f["T08"], lambda e: (e.get("usage_pct") or 0) / 100 or None),
            "vs_scoring_usage36": S(lambda f: f["T08"], lambda e: e.get("scoring_usage36")),
            "true_usage_vs_usage": stats([((e.get("true_usage") or 0) / 100 or None, (e.get("usage_pct") or 0) / 100 or None) for *_, e in rows]),
        },
        "rim_finishing": {
            "S10_vs_rim_fg": S(lambda f: f["S10"], lambda e: e.get("rim_fg")),
            "S10_vs_stable_rim_fg": S(lambda f: f["S10"], lambda e: e.get("stable_rim_fg")),
            "S15_vs_rim_fg": S(lambda f: f["S15"], lambda e: e.get("rim_fg")),
            "S12_vs_dunk_share": S(lambda f: f["S12"], lambda e: e.get("dunk_share")),
            "bbi_rim_fg_vs_bref": stats([(e.get("rim_fg"), (e.get("bref_rim_fg") or 0) * 100 or None) for *_, e in rows]),
        },
        "foul_drawing": {
            "T18_vs_fta_per_fga": S(lambda f: f["T18"], lambda e: e.get("fta_per_fga")),
            "S24_vs_fta_per_fga": S(lambda f: f["S24"], lambda e: e.get("fta_per_fga")),
            "T18_vs_playtype_ft_share": S(lambda f: f["T18"], lambda e: e.get("pt_ft_share")),
        },
        "transition": {
            "T17_transition_vs_playtype_share": S(lambda f: f["T17.transition"], lambda e: e.get("pt_Transition")),
            # Transition as a share of his offensive-end effort (offense + transition), the scale the evidence is on.
            "T17_transition_of_offense_vs_playtype_share": S(
                lambda f: f["T17.transition"] / (f["T17.transition"] + f["T17.offense"]), lambda e: e.get("pt_Transition")),
            "T05_vs_playtype_share": S(lambda f: f["T05"], lambda e: e.get("pt_Transition")),
            "P06_vs_playtype_share": S(lambda f: f["P06"], lambda e: e.get("pt_Transition")),
            "T09_vs_cut_share": S(lambda f: f["T09"], lambda e: e.get("pt_Cut")),
            "T12_vs_putback_share": S(lambda f: f["T12"], lambda e: e.get("pt_OffRebound")),
        },
    }
    out["T17_transition_rank_corr"] = rank_corr([(f["T17.transition"], e.get("pt_Transition")) for _, _, f, e in rows])
    return out, rows


def player_table(rows, names=FLAGGED) -> list[dict]:
    want = {normalize(n) for n in names}
    out = []
    for pid, r, f, e in rows:
        if normalize(r["name"]) not in want:
            continue
        out.append({"name": r["name"], "pid": pid, "minutes": r["minutes"],
                    "T02.rim": round(f["T02.rim"], 3), "bbi_rim": _r(e.get("bbi_rim")), "bref_rim": _r(e.get("bref_rim")),
                    "T02.short": round(f["T02.short_paint"], 3), "T02.mid": round(f["T02.midrange"], 3),
                    "bbi_other2": _r(e.get("bbi_mid")),
                    "T02.three": round(f["T02.three"], 3), "three_rate": _r(e.get("three_rate")),
                    "T08": round(f["T08"], 3), "true_usage": e.get("true_usage"), "usage": e.get("usage_pct"),
                    "S10": round(f["S10"], 1), "S12": round(f["S12"], 1), "S15": round(f["S15"], 1), "rim_fg": e.get("rim_fg"),
                    "T18": round(f["T18"], 3), "S24": round(f["S24"], 1), "fta_per_fga": _r(e.get("fta_per_fga")),
                    "T17.tr": round(f["T17.transition"], 3),
                    "T17.tr_of_off": round(f["T17.transition"] / (f["T17.transition"] + f["T17.offense"]), 3),
                    "pt_trans": _r(e.get("pt_Transition")),
                    "T09": round(f["T09"], 3), "pt_cut": _r(e.get("pt_Cut")), "T12": round(f["T12"], 3),
                    "pt_putback": _r(e.get("pt_OffRebound"))})
    return sorted(out, key=lambda r: r["name"])


def _r(x, d=3):
    return round(x, d) if isinstance(x, (int, float)) else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, default=ROOT / INPUTS)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    inputs = load_inputs(args.inputs)
    real = load_real(ROOT)
    summary, rows = compare(inputs, real)
    table = player_table(rows)
    print(json.dumps(summary, indent=1))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"summary": summary, "flagged": table}, indent=1))


if __name__ == "__main__":
    main()
