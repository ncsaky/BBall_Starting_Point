"""Player card profile: the 94 inputs in four layers, plus provisional OVR / OFF / DEF.

Used by the inputs-model player card (page 2, "Ratings & Profiles") and by
scripts/build_card_mockup_data.py. Only valid for universes that use the inputs ratings model, so the
card shows the same inputs the engine derives its ratings from.

Provisional OVR / OFF / DEF (derived for display; the engine does not read these)
--------------------------------------------------------------------------------
1. Every scalar input gets a league percentile over all baseline players (mid-rank:
   (players below + half of ties) / N). Physical inputs with a real measurement use the measured value;
   the rest use their grade.
2. Group scores are the mean percentile of the group's inputs.
   OFF composite = weighted mean of six offensive group scores:
     shooting S01-S09, finishing S10-S15, creation/handle S16-S20+S24,
     post S21-S23, off-ball/screens S25-S28, passing F01-F09 (read+delivery).
   Weight of a group = 0.2 + T08 (offensive involvement) * share of the player's shot mix that group
   serves, where the mix comes from T01 (shoot/drive/pass/post) and T02 (rim/short paint/midrange/three):
     shooting  = shoot * (three + midrange)
     finishing = shoot * (rim + short_paint) + 0.5 * drive
     creation  = 0.5 * drive + 0.5 * pass
     post      = post
     passing   = pass
     off-ball  = 0.15
   DEF composite = 0.55 * defense skills (S33-S46) + 0.15 * rebounding (S30-S32) + 0.30 * physical
     percentile (height, wingspan, standing reach, lateral mobility, functional strength, vertical).
   OVR composite = 0.55 * OFF composite + 0.45 * DEF composite.
3. Each composite is turned into a league percentile again (mid-rank over the baseline league's
   composites) and shown as 50 + 15 * z, z = normal quantile of that percentile. There is no clipping:
   the best of ~700 players lands near 98 and a player who develops past the baseline league's best keeps
   rising (linear extension past the ends of the baseline curve) instead of being capped.

The league reference tables are computed once from the baseline (pre-development) league and cached at
module level, never stored in the active universe (the game deep-copies it).
"""
from __future__ import annotations

import bisect
import json
from pathlib import Path
from statistics import NormalDist, mean
from typing import Any, Mapping

from . import ratings_model
from .player_model_registry import definition_registry

UNIVERSE_FILE = "universe_2026_27_offseason.json"

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
DIST_IDS = ["T01", "T02", "T03", "T11", "T13", "T16", "T17"]
LEFT_GROUPS = ("Shooting", "Finishing", "Creation & handle", "Post", "Off-ball & screens")
SCALE_NOTE = "The same overall, offense and defense the game's AI uses, shown against the whole league with no cap at 100."


def layer_of(input_id: str) -> int:
    return {"S": 1, "F": 1, "P": 2, "T": 3}[input_id[0]]


def parse_notes(record: Mapping[str, Any]) -> dict[str, Any]:
    notes = (record.get("uncertainty") or {}).get("notes")
    try:
        return json.loads(notes) if notes else {}
    except (TypeError, ValueError):
        return {}


def extract(input_id: str, record: Mapping[str, Any]) -> dict[str, Any]:
    """One input record -> dict(kind, value, unit, interval/intervals, evidence)."""
    v = record["value"]
    notes = parse_notes(record)
    out: dict[str, Any] = {"evidence": "prior" if record.get("reason") == "prior" else "player"}
    if "grade" in v:
        out.update(kind="grade", value=v["grade"], interval=notes.get("interval"))
    elif "probability" in v:
        out.update(kind="propensity", value=v["probability"], interval=notes.get("interval"))
    elif "rows" in v:
        out.update(kind="distribution", value=v["rows"][0]["probabilities"], intervals=notes.get("intervals"))
    elif "measurements" in v:
        m = v["measurements"][0] if v["measurements"] else None
        if m:
            out.update(kind="measure", value=m["value"], unit=m["unit"], interval=m.get("interval"),
                       protocol=m.get("protocol"))
        if "display_grade" in v:
            out.update(kind="grade", value=v["display_grade"]["grade"], interval=notes.get("interval"))
            out.pop("unit", None)
        if not m and "display_grade" not in v:
            raise ValueError(f"unreadable {input_id}")
    else:
        raise ValueError(f"unknown value shape for {input_id}: {list(v)}")
    return out


def midrank_percentiles(values: list[float]) -> list[float]:
    """Mid-rank percentile (0-100) for each value in a list."""
    n = len(values)
    order = sorted(values)
    res = []
    for x in values:
        lo, hi = bisect.bisect_left(order, x), bisect.bisect_right(order, x)
        res.append(100.0 * (lo + 0.5 * (hi - lo)) / n)
    return res


def _pct_in(sorted_values: list[float], x: float) -> float:
    lo, hi = bisect.bisect_left(sorted_values, x), bisect.bisect_right(sorted_values, x)
    return 100.0 * (lo + 0.5 * (hi - lo)) / len(sorted_values)


def to_display(composites: list[float]) -> list[float]:
    nd = NormalDist()
    return [50 + 15 * nd.inv_cdf(p / 100.0) for p in midrank_percentiles(composites)]


def group_ids() -> dict[str, list[str]]:
    groups = dict(SKILL_GROUPS)
    groups["Passing"] = [f"{f}.{k}" for f in PASS_FAMILIES for k in ("recognition", "execution")]
    return groups


def composites(ex: Mapping[str, Mapping[str, Any]], pct: Mapping[str, float]) -> tuple[float, float]:
    """(OFF composite, DEF composite) for one player from extracted inputs and per-input percentiles."""
    groups = group_ids()

    def score(ids):
        return mean(pct[i] for i in ids)

    t1, t2, t8 = ex["T01"]["value"], ex["T02"]["value"], ex["T08"]["value"]
    mix = {
        "Shooting": t1["shoot"] * (t2["three"] + t2["midrange"]),
        "Finishing": t1["shoot"] * (t2["rim"] + t2["short_paint"]) + 0.5 * t1["drive"],
        "Creation & handle": 0.5 * t1["drive"] + 0.5 * t1["pass"],
        "Post": t1["post"],
        "Passing": t1["pass"],
    }
    scores = {g: score(groups[g]) for g in ("Shooting", "Finishing", "Creation & handle", "Post",
                                            "Off-ball & screens", "Passing")}
    weights = {g: 0.2 + t8 * mix.get(g, 0.15 if g == "Off-ball & screens" else 0) for g in scores}
    off = sum(scores[g] * weights[g] for g in scores) / sum(weights.values())
    dfn = 0.55 * score(groups["Defense"]) + 0.15 * score(["S30", "S31", "S32"]) + 0.30 * score(DEF_PHYS)
    return off, dfn


class _Curve:
    """Composite -> display rating, built from the baseline league, extended linearly past both ends."""

    def __init__(self, composite_values: list[float]):
        display = to_display(composite_values)
        by_composite: dict[float, float] = {}
        for c, d in zip(composite_values, display):
            by_composite[c] = d
        self.xs = sorted(by_composite)
        self.ys = [by_composite[x] for x in self.xs]
        self.max_display = max(self.ys)
        self.min_display = min(self.ys)

    def __call__(self, x: float) -> float:
        xs, ys = self.xs, self.ys
        if len(xs) < 2:
            return ys[0] if ys else 50.0
        if x <= xs[0] or x >= xs[-1]:
            k = min(len(xs) - 1, 8)
            i, j = (0, k) if x <= xs[0] else (len(xs) - 1 - k, len(xs) - 1)
            slope = (ys[j] - ys[i]) / max(1e-9, xs[j] - xs[i])
            edge = 0 if x <= xs[0] else -1
            return ys[edge] + slope * (x - xs[edge])
        i = bisect.bisect_left(xs, x)
        if xs[i] == x:
            return ys[i]
        frac = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
        return ys[i - 1] + frac * (ys[i] - ys[i - 1])


_REFERENCE: dict[str, dict[str, Any]] = {}


def league_reference(inputs_key: str, league_inputs: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """League tables from the baseline inputs, computed once per inputs file."""
    if inputs_key in _REFERENCE:
        return _REFERENCE[inputs_key]
    if league_inputs is None:
        league_inputs = ratings_model.load_league_inputs(Path(inputs_key).parents[2])
    reg = {item["id"]: item for item in definition_registry()["inputs"]}
    universe = json.loads((Path(inputs_key).parent / UNIVERSE_FILE).read_text())
    position = {p["id"]: p["position"] for p in universe["players"]}
    pids = sorted(league_inputs)
    ex = {pid: {iid: extract(iid, r) for iid, r in league_inputs[pid].items()} for pid in pids}
    scalar_ids = [i for i in reg if ex[pids[0]][i]["kind"] != "distribution"]
    sorted_vals = {i: sorted(ex[p][i]["value"] for p in pids) for i in scalar_ids}
    pct = {pid: {iid: _pct_in(sorted_vals[iid], ex[pid][iid]["value"]) for iid in scalar_ids} for pid in pids}

    positions = sorted({position[p] for p in pids if p in position})
    pos_avg: dict[str, dict[str, Any]] = {}
    for pos in positions:
        members = [p for p in pids if position.get(p) == pos]
        pos_avg[pos] = {}
        for iid in reg:
            if ex[members[0]][iid]["kind"] == "distribution":
                keys = ex[members[0]][iid]["value"].keys()
                pos_avg[pos][iid] = {k: mean(ex[m][iid]["value"][k] for m in members) for k in keys}
            else:
                pos_avg[pos][iid] = mean(ex[m][iid]["value"] for m in members)

    off_c, def_c = [], []
    for pid in pids:
        o, d = composites(ex[pid], pct[pid])
        off_c.append(o)
        def_c.append(d)
    ovr_c = [0.55 * o + 0.45 * d for o, d in zip(off_c, def_c)]
    curves = {"ovr": _Curve(ovr_c), "off": _Curve(off_c), "def": _Curve(def_c)}
    ref = {
        "reg": reg, "pids": pids, "ex": ex, "position": position, "positions": positions,
        "scalar_ids": scalar_ids, "sorted_vals": sorted_vals, "pct": pct, "pos_avg": pos_avg,
        "curves": curves,
        "display": {pid: {"ovr": curves["ovr"](ovr_c[k]), "off": curves["off"](off_c[k]),
                          "def": curves["def"](def_c[k])} for k, pid in enumerate(pids)},
        "league": {"max_ovr": curves["ovr"].max_display, "max_off": curves["off"].max_display,
                   "max_def": curves["def"].max_display, "min_ovr": curves["ovr"].min_display,
                   "players": len(pids)},
    }
    _REFERENCE[inputs_key] = ref
    return ref


def pct_of(ref: Mapping[str, Any], input_id: str, x: float) -> float:
    return _pct_in(ref["sorted_vals"][input_id], x)


def header_for(ref: Mapping[str, Any], current: Mapping[str, Mapping[str, Any]]) -> dict[str, float]:
    """Provisional OVR / OFF / DEF for a player's current inputs."""
    ex = {i: extract(i, r) for i, r in current.items()}
    pct = {i: pct_of(ref, i, ex[i]["value"]) for i in ref["scalar_ids"]}
    off, dfn = composites(ex, pct)
    ovr = 0.55 * off + 0.45 * dfn
    c = ref["curves"]
    return {"ovr": c["ovr"](ovr), "off": c["off"](off), "def": c["def"](dfn)}


_ENGINE_CURVES: dict[tuple, dict[str, "_Curve"]] = {}


def _engine_triplet(summary: Mapping[str, float]) -> tuple[float, float, float]:
    offense = summary.get("offense", summary.get("creation", 50.0))
    return float(summary.get("overall", 50.0)), float(offense), float(summary.get("defense", 50.0))


def engine_header(active: Mapping[str, Any], player_id: str) -> dict[str, float] | None:
    """OVR/OFF/DEF exactly as the game's own AI computes them, shown on the unclipped display scale.

    The front office (trades, contracts, rotations, free agency) reads save.player_attribute_summary, which is
    computed from the traits the adapter derives from the 94 inputs. The card shows that same number, mapped
    through the league's distribution onto 50 + 15z (no clipping at 100, elite players spread apart), so the
    card and the AI can never disagree about who is better. The league curve is built once per baseline league.
    """
    from .save import player_attribute_summary

    model = active.get(ratings_model.MODEL_KEY) or {}
    if not model:
        return None
    key = (model.get("inputs_key"), tuple(model.get("fitted_key") or ()))
    if key not in _ENGINE_CURVES:
        triplets = []
        for p in active.get("players", []):
            pid = str(p.get("id") or "")
            if pid and ratings_model.effective_inputs(active, pid) is not None:
                triplets.append(_engine_triplet(player_attribute_summary(active, pid)))
        if len(triplets) < 50:
            return None
        _ENGINE_CURVES[key] = {name: _Curve([t[i] for t in triplets]) for i, name in enumerate(("ovr", "off", "def"))}
    curves = _ENGINE_CURVES[key]
    ovr, off, dfn = _engine_triplet(player_attribute_summary(active, player_id))
    return {"ovr": curves["ovr"](ovr), "off": curves["off"](off), "def": curves["def"](dfn),
            "engine_raw": {"ovr": ovr, "off": off, "def": dfn}}


def _shift(interval, delta, lo=0.0, hi=100.0):
    return [round(max(lo, min(hi, x + delta)), 2) for x in interval]


def _entry(ref, iid, ex_cur, base_ex, position):
    d = ref["reg"][iid]
    e = ex_cur[iid]
    row: dict[str, Any] = {"id": iid, "name": d["name"], "kind": e["kind"], "evidence": e["evidence"],
                           "value": e["value"], "meaning": d.get("meaning")}
    interval = e.get("interval")
    if interval and e["kind"] == "grade" and base_ex is not None and base_ex["kind"] == "grade":
        delta = e["value"] - base_ex["value"]
        if delta:
            interval = _shift(interval, delta)
    for k, v in (("interval", interval), ("intervals", e.get("intervals")), ("unit", e.get("unit")),
                 ("protocol", e.get("protocol"))):
        if v is not None:
            row[k] = v
    if d.get("outcomes"):
        row["outcomes"] = d["outcomes"]
    avg = ref["pos_avg"].get(position, {}).get(iid)
    row["pos_avg"] = avg
    if e["kind"] == "distribution":
        row["pct"] = None
        return row
    row["pct"] = round(pct_of(ref, iid, e["value"]), 1)
    if e["kind"] == "measure" and avg is not None:
        row["pos_avg_pct"] = round(pct_of(ref, iid, avg), 1)
        if interval:
            row["interval_pct"] = [round(pct_of(ref, iid, x), 1) for x in interval]
    return row


def player_profile(active: Mapping[str, Any], player_id: str) -> dict[str, Any] | None:
    """Everything the new player card needs for one player, or None without inputs.

    Layers: technique (skills + passing), physical, tendencies, and the coach usage block.
    """
    current = ratings_model.effective_inputs(active, player_id)
    if not current:
        return None
    model = active[ratings_model.MODEL_KEY]
    inputs_key = model["inputs_key"]
    ref = league_reference(inputs_key, ratings_model._base_inputs(model))
    player = next((p for p in active.get("players", []) if str(p.get("id")) == player_id), {})
    position = ref["position"].get(player_id) or str(player.get("position") or "")
    if position not in ref["pos_avg"]:
        position = next(iter(ref["pos_avg"]))
    ex_cur = {i: extract(i, r) for i, r in current.items()}
    base = ratings_model._base_inputs(model).get(player_id) or {}
    ex_base = {i: extract(i, r) for i, r in base.items()}

    def entry(iid):
        return _entry(ref, iid, ex_cur, ex_base.get(iid), position)

    groups = group_ids()
    technique = []
    for name, ids in SKILL_GROUPS:
        technique.append({"name": name, "column": 0 if name in LEFT_GROUPS else 1,
                          "entries": [entry(i) for i in ids]})
    pairs = []
    for fam in PASS_FAMILIES:
        read, delivery = entry(f"{fam}.recognition"), entry(f"{fam}.execution")
        pairs.append({"id": fam, "name": read["name"].replace(" — recognition", ""), "read": read, "delivery": delivery})
    technique.append({"name": "Passing", "column": 1, "pairs": pairs})
    physical = [{"name": "Body and athleticism", "entries": [entry(i) for i in ref["reg"] if layer_of(i) == 2]}]
    tend_ids = [i for i in ref["reg"] if layer_of(i) == 3]
    tendencies = [
        {"name": "Choices and style", "note": "how often", "entries": [entry(i) for i in tend_ids if i not in DIST_IDS]},
        {"name": "Mixes", "note": "each bar adds to 100%", "entries": [entry(i) for i in DIST_IDS]},
    ]

    def count(group_list):
        ids = []
        for g in group_list:
            for e in g.get("entries", []):
                ids.append(e)
            for p in g.get("pairs", []):
                ids.extend([p["read"], p["delivery"]])
        return len(ids), sum(1 for e in ids if e["evidence"] == "player")

    layers = []
    for key, title, sub, glist in (
        ("technique", "Technique & Recognition", "What the player can do, separate from size and speed.", technique),
        ("physical", "Physical Tools", "Body and athleticism. Measurements are shown where known.", physical),
        ("tendencies", "Tendencies", "What the player chooses to do, not how well.", tendencies),
    ):
        total, from_player = count(glist)
        layers.append({"key": key, "title": title, "subtitle": sub, "groups": glist,
                       "total": total, "from_player_data": from_player})
    head = engine_header(active, player_id) or header_for(ref, current)
    return {
        "player_id": player_id,
        "position": position,
        "header": {"ovr": round(head["ovr"], 1), "off": round(head["off"], 1), "def": round(head["def"], 1),
                   "source": "engine" if "engine_raw" in head else "inputs_composite",
                   "engine_raw": head.get("engine_raw"),
                   "scale_note": SCALE_NOTE, "league_players": ref["league"]["players"]},
        "layers": layers,
        "coach": {
            "position": position,
            "primary_off_role": player.get("primary_off_role"),
            "secondary_off_role": player.get("secondary_off_role"),
            "primary_def_role": player.get("primary_def_role"),
            "rotation_priority": player.get("rotation_priority"),
            "minutes_projection": player.get("minutes_projection"),
            "weight_lbs": player.get("weight_lbs"),
            "height_inches": player.get("height_inches"),
        },
    }
