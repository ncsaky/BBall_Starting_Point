#!/usr/bin/env python3
"""Build data.json for the new player card mockup (design_concepts/new_player_card).

Reads the canonical player inputs, the universe file and the registry; writes
design_concepts/new_player_card/data.json for three contrasting players.

Provisional OVR / OFF / DEF (mockup only, NOT engine ratings)
-------------------------------------------------------------
1. Every scalar input gets a league percentile over all 691 players (mid-rank:
   (players below + half of ties) / N). Physical inputs with a real measurement
   use the measured value; the rest use their grade.
2. Group scores are the mean percentile of the group's inputs.
   OFF composite = weighted mean of six offensive group scores:
     shooting S01-S09, finishing S10-S15, creation/handle S16-S20+S24,
     post S21-S23, off-ball/screens S25-S28, passing F01-F09 (read+delivery).
   Weight of a group = 0.2 + T08 (offensive involvement) * share of the
   player's shot mix that group serves, where the mix comes from T01
   (shoot/drive/pass/post) and T02 (rim/short paint/midrange/three):
     shooting  = shoot * (three + midrange)
     finishing = shoot * (rim + short_paint) + 0.5 * drive
     creation  = 0.5 * drive + 0.5 * pass
     post      = post
     passing   = pass
     off-ball  = 0.15
   DEF composite = 0.55 * defense skills (S33-S46) + 0.15 * rebounding
     (S30-S32) + 0.30 * physical percentile (height, wingspan, standing reach,
     lateral mobility, functional strength, vertical).
   OVR composite = 0.55 * OFF composite + 0.45 * DEF composite.
3. Each composite is turned into a league percentile again (mid-rank over all
   691 composites) and shown as 50 + 15 * z (top of a 691-player league lands near 98, never above 100), z = normal quantile of that
   percentile. No clipping: with 691 players the best player lands slightly
   above 100 by construction (z about 3.2), so elite players stay separated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import NormalDist, mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.player_model_registry import definition_registry  # noqa: E402

INPUTS = ROOT / "data/canonical/player_inputs_2026_27.json"
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"
OUT = ROOT / "design_concepts/new_player_card/data.json"
FEATURED = ["player_bos-jayson-tatum", "player_min-rudy-gobert", "player_cha-kon-knueppel"]

SKILL_GROUPS = [
    ("Shooting", [f"S{n:02d}" for n in range(1, 10)]),
    ("Finishing", [f"S{n:02d}" for n in range(10, 16)]),
    ("Creation & handle", [f"S{n:02d}" for n in (16, 17, 18, 19, 20, 24)]),
    ("Post", [f"S{n:02d}" for n in (21, 22, 23)]),
    ("Off-ball & screens", [f"S{n:02d}" for n in range(25, 29)]),
    ("Rebounding", [f"S{n:02d}" for n in range(29, 33)]),
    ("Defense", [f"S{n:02d}" for n in range(33, 47)]),
]
PASS_FAMILIES = [f"F{n:02d}" for n in range(1, 10)]
GROUP_OF = {i: g for g, ids in SKILL_GROUPS for i in ids}
GROUP_OF.update({f"{f}.{k}": "Passing" for f in PASS_FAMILIES for k in ("recognition", "execution")})
DEF_PHYS = ["P01", "P02", "P03", "P07", "P08", "P10"]


def layer_of(i):
    return {"S": 1, "F": 1, "P": 2, "T": 3}[i[0]]


def parse_notes(r):
    n = r["uncertainty"].get("notes")
    try:
        return json.loads(n) if n else {}
    except (TypeError, ValueError):
        return {}


def extract(iid, r):
    """Return dict(kind, value, unit, interval/intervals, measurement)."""
    v = r["value"]
    notes = parse_notes(r)
    out = {"evidence": "prior" if r["reason"] == "prior" else "player"}
    if "grade" in v:
        out.update(kind="grade", value=v["grade"], interval=notes.get("interval"))
    elif "probability" in v:
        out.update(kind="propensity", value=v["probability"], interval=notes.get("interval"))
    elif "rows" in v:
        probs = v["rows"][0]["probabilities"]
        out.update(kind="distribution", value=probs, intervals=notes.get("intervals"))
    elif "measurements" in v:
        m = v["measurements"][0] if v["measurements"] else None
        if m:
            out.update(kind="measure", value=m["value"], unit=m["unit"], interval=m.get("interval"),
                       protocol=m.get("protocol"))
        if "display_grade" in v:
            out.update(kind="grade", value=v["display_grade"]["grade"], interval=notes.get("interval"))
            out.pop("unit", None)
        if not m and "display_grade" not in v:
            raise ValueError(f"unreadable {iid}")
    else:
        raise ValueError(f"unknown value shape for {iid}: {list(v)}")
    return out


def midrank_percentiles(values):
    """Mid-rank percentile (0-100) for each value in a list."""
    n = len(values)
    order = sorted(values)
    import bisect
    res = []
    for x in values:
        lo, hi = bisect.bisect_left(order, x), bisect.bisect_right(order, x)
        res.append(100.0 * (lo + 0.5 * (hi - lo)) / n)
    return res


def to_display(composites):
    nd = NormalDist()
    pcts = midrank_percentiles(composites)
    return [50 + 15 * nd.inv_cdf(p / 100.0) for p in pcts]


def main():
    reg = {i["id"]: i for i in definition_registry()["inputs"]}
    raw = json.load(open(INPUTS))["players"]
    uni = {p["id"]: p for p in json.load(open(UNIVERSE))["players"]}
    pids = sorted(raw)
    assert len(pids) == 691
    assert len(reg) == 94, len(reg)

    ex = {pid: {iid: extract(iid, r) for iid, r in raw[pid]["inputs"].items()} for pid in pids}

    # Scalar view used for percentiles and averages.
    def scalar(pid, iid):
        e = ex[pid][iid]
        return e["value"] if e["kind"] != "distribution" else None

    scalar_ids = [i for i in reg if ex[pids[0]][i]["kind"] != "distribution"]
    pct = {}
    for iid in scalar_ids:
        pcts = midrank_percentiles([scalar(p, iid) for p in pids])
        for p, v in zip(pids, pcts):
            pct.setdefault(p, {})[iid] = v

    import bisect
    sorted_vals = {i: sorted(scalar(p, i) for p in pids) for i in scalar_ids}

    def pct_of(iid, x):
        sv = sorted_vals[iid]
        return 100.0 * (bisect.bisect_left(sv, x) + 0.5 * (bisect.bisect_right(sv, x) - bisect.bisect_left(sv, x))) / len(sv)

    # Position averages.
    positions = sorted({uni[p]["position"] for p in pids})
    pos_avg = {pos: {} for pos in positions}
    for pos in positions:
        members = [p for p in pids if uni[p]["position"] == pos]
        for iid in reg:
            kind = ex[members[0]][iid]["kind"]
            if kind == "distribution":
                keys = ex[members[0]][iid]["value"].keys()
                pos_avg[pos][iid] = {k: mean(ex[m][iid]["value"][k] for m in members) for k in keys}
            else:
                pos_avg[pos][iid] = mean(ex[m][iid]["value"] for m in members)

    # Provisional composites.
    def group_score(pid, ids):
        return mean(pct[pid][i] for i in ids)

    off_c, def_c = [], []
    for pid in pids:
        e = ex[pid]
        t1, t2, t8 = e["T01"]["value"], e["T02"]["value"], e["T08"]["value"]
        mix = {
            "Shooting": t1["shoot"] * (t2["three"] + t2["midrange"]),
            "Finishing": t1["shoot"] * (t2["rim"] + t2["short_paint"]) + 0.5 * t1["drive"],
            "Creation & handle": 0.5 * t1["drive"] + 0.5 * t1["pass"],
            "Post": t1["post"],
            "Passing": t1["pass"],
        }
        groups = dict(SKILL_GROUPS)
        scores = {g: group_score(pid, groups[g]) for g in ("Shooting", "Finishing", "Creation & handle", "Post", "Off-ball & screens")}
        scores["Passing"] = group_score(pid, [f"{f}.{k}" for f in PASS_FAMILIES for k in ("recognition", "execution")])
        weights = {g: 0.2 + t8 * mix.get(g, 0.15 if g == "Off-ball & screens" else 0) for g in scores}
        wsum = sum(weights.values())
        off_c.append(sum(scores[g] * weights[g] for g in scores) / wsum)
        d = (0.55 * group_score(pid, groups["Defense"]) + 0.15 * group_score(pid, ["S30", "S31", "S32"])
             + 0.30 * group_score(pid, DEF_PHYS))
        def_c.append(d)
    ovr_c = [0.55 * o + 0.45 * d for o, d in zip(off_c, def_c)]
    off_d, def_d, ovr_d = to_display(off_c), to_display(def_c), to_display(ovr_c)
    prov = {pid: {"ovr": ovr_d[k], "off": off_d[k], "def": def_d[k]} for k, pid in enumerate(pids)}
    league_stats = {"max_ovr": max(ovr_d), "max_off": max(off_d), "max_def": max(def_d),
                    "min_ovr": min(ovr_d), "players": len(pids)}

    inputs_meta = []
    for iid, m in reg.items():
        inputs_meta.append({"id": iid, "name": m["name"], "kind": m["kind"], "units": m["units"],
                            "outcomes": m["outcomes"], "meaning": m["meaning"],
                            "layer": layer_of(iid), "group": GROUP_OF.get(iid)})

    players = []
    for pid in FEATURED:
        u = uni[pid]
        rec = []
        for iid in reg:
            e = ex[pid][iid]
            row = {"id": iid, "kind": e["kind"], "evidence": e["evidence"], "value": e["value"]}
            for k in ("interval", "intervals", "unit", "protocol"):
                if e.get(k) is not None:
                    row[k] = e[k]
            row["pct"] = None if e["kind"] == "distribution" else round(pct[pid][iid], 1)
            row["pos_avg"] = pos_avg[u["position"]][iid]
            if e["kind"] == "measure":
                # Bars for measurements are drawn on the league percentile scale.
                row["pos_avg_pct"] = round(pct_of(iid, row["pos_avg"]), 1)
                if row.get("interval"):
                    row["interval_pct"] = [round(pct_of(iid, x), 1) for x in row["interval"]]
            rec.append(row)
        players.append({
            "id": pid, "name": u["name"], "team": u["team_abbrev"], "position": u["position"],
            "age": u["age"], "height_inches": u["height_inches"], "weight_lbs": u["weight_lbs"],
            "wingspan_inches": u["wingspan_inches"], "headshot_url": u.get("headshot_url"),
            "minutes_projection": u["minutes_projection"], "primary_off_role": u["primary_off_role"],
            "secondary_off_role": u["secondary_off_role"], "primary_def_role": u["primary_def_role"],
            "rotation_priority": u["rotation_priority"],
            "provisional": {k: round(v, 1) for k, v in prov[pid].items()},
            "inputs": rec,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"inputs": inputs_meta, "players": players, "league": league_stats,
               "positions": positions}, open(OUT, "w"), separators=(",", ":"))

    # Console summary.
    for p in players:
        lay = {1: [0, 0], 2: [0, 0], 3: [0, 0]}
        for r in p["inputs"]:
            L = layer_of(r["id"])
            lay[L][1] += 1
            lay[L][0] += r["evidence"] == "player"
        print(p["name"], p["provisional"], {f"L{k}": f"{a}/{b} from player data" for k, (a, b) in lay.items()})
    print("league max display:", {k: round(v, 1) for k, v in league_stats.items()})


if __name__ == "__main__":
    main()
