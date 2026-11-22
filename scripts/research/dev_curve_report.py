"""Compare the game's development with the real-NBA evidence.

    # development-only probe output (dev_curve_talent.py)
    PYTHONPATH=src:scripts/research .venv/bin/python scripts/research/dev_curve_report.py talent output/dev-curve/talent-before
    # a multi-season league run (scripts/league_health_audit.py advance --career)
    PYTHONPATH=src:scripts/research .venv/bin/python scripts/research/dev_curve_report.py game output/dev-curve/before

"game" measures simulated seasons the way the evidence measures real ones: a box-score impact estimate on the BPM
scale (dev_curve_box.py) from each season's simulated totals, 1,000+ minutes in both seasons, starting thirds among
same-age qualifiers, top five among qualifiers. It also reports the engine's own player value (fitted impact, from the
card's OVR) at each season's February snapshot.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import dev_curve_box as box  # noqa: E402

BANDS = ((19, 20), (21, 22), (23, 24), (25, 27), (28, 29), (30, 32), (33, 35), (36, 39))
FIXED_BAR = 7.28
DISPLAY_INTERCEPT, DISPLAY_SLOPE = 71.5, 3.0     # impact_value.DISPLAY_LINES["overall"]


def mean(values):
    return round(st.mean(values), 2) if values else None


def q(values, p):
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))], 2)


def evidence() -> dict[str, Any]:
    return json.loads(box.EVIDENCE.read_text())


def real_band_table() -> dict[str, dict[str, Any]]:
    """Real BPM change by age band and same-season third, plus the prior-season-third version."""
    seasons = {y: s for y, s in box.evidence_seasons().items() if y >= 2004}
    same = box.development_table({y: s for y, s in seasons.items() if y >= 2005}, "bpm")
    prior = box.prior_level_table(seasons, "bpm")
    return {"same": band_table(same), "prior": band_table(prior)}


def band_table(table: Mapping[int, Mapping[str, list[float]]]) -> dict[str, dict[str, Any]]:
    out = {}
    for low, high in BANDS:
        cell: dict[str, list[float]] = defaultdict(list)
        for age in range(low, high + 1):
            for k, v in (table.get(age) or {}).items():
                cell[k].extend(v)
        out[f"{low}-{high}"] = {k: {"n": len(v), "mean": mean(v)} for k, v in cell.items()}
    return out


def fmt_band_rows(tables: Mapping[str, Mapping[str, Any]], keys=("all", "bottom", "middle", "top")) -> list[str]:
    lines = ["| Ages | " + " | ".join(f"{name}: {k}" for name in tables for k in keys) + " |",
             "|---|" + "---:|" * (len(tables) * len(keys))]
    for low, high in BANDS:
        band = f"{low}-{high}"
        cells = []
        for t in tables.values():
            for k in keys:
                c = (t.get(band) or {}).get(k)
                cells.append(f"{c['mean']:+.2f} ({c['n']})" if c and c["mean"] is not None else "-")
        lines.append(f"| {band} | " + " | ".join(cells) + " |")
    return lines


# ---- top-five turnover ---------------------------------------------------------------------------------------------
def real_top_five_names() -> set[str]:
    names = set()
    for season in evidence()["superstars"]["by_season"]:
        for row in season["ranked_top_five"]:
            names.add(box.norm_name(row["name"]))
    return names


def top_five_turnover(seasons: Mapping[int, Mapping[str, Mapping[str, Any]]], key: str, names: Mapping[str, str],
                      prior_real: set[str] | None = None, qualify: float = box.QUALIFY, bar: float | None = FIXED_BAR) -> list[dict[str, Any]]:
    out, ever, previous = [], set(prior_real or set()), None
    for year in sorted(seasons):
        rows = [(pid, r[key]) for pid, r in seasons[year].items() if r["minutes"] >= qualify and r.get(key) is not None]
        rows.sort(key=lambda x: (-x[1], x[0]))
        top = [pid for pid, _ in rows[:5]]
        first = [pid for pid in top if box.norm_name(names.get(pid, pid)) not in ever]
        out.append({"year": year, "top": [(names.get(pid, pid), round(v, 2), seasons[year][pid].get("age")) for pid, v in rows[:5]],
                    "mean": round(st.mean(v for _, v in rows[:5]), 2) if rows else None,
                    "above_bar": sum(v >= bar for _, v in rows) if bar is not None else None,
                    "kept": None if previous is None else len(set(top) & previous),
                    "new_or_returning": None if previous is None else len(set(top) - previous),
                    "first_ever": [names.get(pid, pid) for pid in first] if previous is not None else None})
        ever |= {box.norm_name(names.get(pid, pid)) for pid in top}
        previous = set(top)
    return out


def older_by_prior_star(seasons: Mapping[int, Mapping[str, Mapping[str, Any]]], key: str, star_key: str,
                        qualify: float = box.QUALIFY) -> dict[str, dict[str, Any]]:
    """Change t -> t+1 for players aged 28+ at t, split by a league top-25 finish (star_key) in season t-1."""
    bands = {"28-29": (28, 29), "30-32": (30, 32), "33-35": (33, 35), "36-39": (36, 39)}
    cells: dict[str, dict[str, list[float]]] = {b: defaultdict(list) for b in bands}
    for year in sorted(seasons):
        prev, cur, nxt = seasons.get(year - 1), seasons[year], seasons.get(year + 1)
        if not prev or not nxt:
            continue
        ranked = sorted((r[star_key], pid) for pid, r in prev.items() if r["minutes"] >= qualify and r.get(star_key) is not None)
        stars = {pid for _, pid in ranked[-25:]}
        for pid, r in cur.items():
            n = nxt.get(pid)
            if r["minutes"] < qualify or not n or n["minutes"] < qualify or r.get(key) is None or n.get(key) is None:
                continue
            for band, (lo, hi) in bands.items():
                if lo <= int(r["age"]) <= hi:
                    group = "prior_star" if pid in stars else "other"
                    cells[band][group].append(n[key] - r[key])
                    cells[band]["all"].append(n[key] - r[key])
    return {b: {k: {"n": len(v), "mean": mean(v)} for k, v in c.items()} for b, c in cells.items()}


# ---- the game run --------------------------------------------------------------------------------------------------
def load_run(run: Path) -> dict[str, Any]:
    report = json.loads((run / "league_health.json").read_text())
    save_path = run / "saves" / Path(report["save_path"]).name
    saved = json.loads(save_path.read_text())
    model = box.load_model()
    by_year_snap: dict[int, dict[str, Any]] = {}
    for snap in report["snapshots"]:
        if snap.get("phase") != "regular_season" or not snap.get("date"):
            continue
        d = date.fromisoformat(snap["date"])
        year = d.year if d.month <= 6 else d.year + 1
        target = date(year, 2, 1)
        best = by_year_snap.get(year)
        if best is None or abs((d - target).days) < abs((date.fromisoformat(best["date"]) - target).days):
            by_year_snap[year] = snap
    seasons: dict[int, dict[str, dict[str, Any]]] = {}
    names: dict[str, str] = {}
    meta: dict[str, dict[str, Any]] = {}
    for entry in saved.get("season_history", []):
        year = int(entry["season"][:4]) + 1
        snap = by_year_snap.get(year)
        if not snap:
            continue
        rows = {r["id"]: r for r in snap["players"]}
        season = {}
        for pid, totals in (entry.get("player_season_stats") or {}).items():
            row = rows.get(pid)
            if not row or row.get("age") is None:
                continue
            est = box.estimate(model, totals)
            minutes = float(totals.get("minutes") or 0.0)
            season[pid] = {"age": int(float(row["age"])), "minutes": minutes, "box": est,
                           "talent": (float(row["display"]) - DISPLAY_INTERCEPT) / DISPLAY_SLOPE,
                           "vorp_like": None if est is None else (est + 2.0) * minutes / 1000.0}
            names[pid] = row.get("name") or pid
            meta[pid] = {"pick": row.get("overall_pick"), "draft_year": row.get("draft_year"), "origin": row.get("origin")}
        seasons[year] = season
    talent_by_year = {}
    for year, snap in sorted(by_year_snap.items()):
        talent_by_year[year] = {r["id"]: {"age": r.get("age"), "talent": (float(r["display"]) - DISPLAY_INTERCEPT) / DISPLAY_SLOPE,
                                          "name": r.get("name"), "origin": r.get("origin"), "pick": r.get("overall_pick"),
                                          "rostered": r.get("rostered")}
                                for r in snap["players"] if r.get("display") is not None}
        for r in snap["players"]:
            names.setdefault(r["id"], r.get("name") or r["id"])
    return {"seasons": seasons, "names": names, "meta": meta, "talent": talent_by_year, "status": report.get("status")}


def distribution(values: list[float]) -> dict[str, float]:
    s = sorted(values, reverse=True)
    pick = lambda i: round(s[i - 1], 2) if len(s) >= i else None
    return {"best": pick(1), "top5_mean": round(st.mean(s[:5]), 2) if len(s) >= 5 else None, "10th": pick(10),
            "25th": pick(25), "50th": pick(50), "100th": pick(100), "150th": pick(150), "300th": pick(300)}


def slope(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx, 3) if sxx else None


def game_report(run: Path) -> dict[str, Any]:
    data = load_run(run)
    seasons, names = data["seasons"], data["names"]
    same = box.development_table(seasons, "box")
    prior = box.prior_level_table(seasons, "box")
    talent_same = box.development_table(seasons, "talent")
    qualified = [(r["talent"], r["box"]) for s in seasons.values() for r in s.values() if r["minutes"] >= box.QUALIFY and r["box"] is not None]
    real_names = real_top_five_names()
    # Real top-five history before the game starts (seasons up to 2025-26) counts as "already been top five".
    out = {
        "status": data["status"], "seasons": sorted(seasons),
        "qualified_per_season": {y: sum(r["minutes"] >= box.QUALIFY for r in s.values()) for y, s in seasons.items()},
        "box_on_talent_slope": slope([t for t, _ in qualified], [b for _, b in qualified]),
        "box_sd": round(st.pstdev([b for _, b in qualified]), 2) if qualified else None,
        "talent_sd": round(st.pstdev([t for t, _ in qualified]), 2) if qualified else None,
        "development_box_same": band_table(same), "development_box_prior": band_table(prior),
        "development_talent": band_table(talent_same),
        "by_age_box": box.summarize_table(same), "peak_age_box": box.peak_age(same),
        "peak_age_talent": box.peak_age(talent_same),
        "older_box": older_by_prior_star(seasons, "box", "vorp_like"),
        "top_five_box": top_five_turnover(seasons, "box", names, real_names),
        "talent_distribution": {y: distribution([r["talent"] for r in t.values() if r.get("rostered")])
                                for y, t in data["talent"].items()},
        "box_distribution": {y: distribution([r["box"] for r in s.values() if r["minutes"] >= box.QUALIFY and r["box"] is not None])
                             for y, s in seasons.items()},
    }
    named = {}
    for y, t in data["talent"].items():
        for pid, r in t.items():
            if r["name"] in NAMED or (r.get("origin") not in (None, "baseline")):
                named.setdefault(pid, {"name": r["name"], "origin": r.get("origin"), "pick": r.get("pick"), "by_year": {}})
                named[pid]["by_year"][y] = {"age": r["age"], "talent": round(r["talent"], 2),
                                            "box": round(seasons.get(y, {}).get(pid, {}).get("box") or 0, 2) if pid in seasons.get(y, {}) else None,
                                            "minutes": round(seasons.get(y, {}).get(pid, {}).get("minutes") or 0) if pid in seasons.get(y, {}) else None}
    last = max(data["talent"]) if data["talent"] else None
    made_up = sorted((p for p in named.values() if p["origin"] not in (None, "baseline") and last in p["by_year"]),
                     key=lambda p: -p["by_year"][last]["talent"])[:8]
    out["named"] = [p for p in named.values() if p["name"] in NAMED]
    out["best_made_up"] = made_up
    return out


NAMED = {"Victor Wembanyama", "Cooper Flagg", "AJ Dybantsa", "Chet Holmgren", "Shai Gilgeous-Alexander", "Nikola Jokić",
         "Nikola Jokic", "Luka Dončić", "Luka Doncic", "Giannis Antetokounmpo", "LeBron James", "Stephen Curry",
         "Anthony Edwards", "Darryn Peterson", "Cameron Boozer", "Dylan Harper", "Ace Bailey", "Stephon Castle",
         "Amen Thompson", "Jalen Williams", "Kevin Durant", "Tyrese Maxey"}


# ---- the development-only probe -------------------------------------------------------------------------------------
def talent_report(folder: Path) -> dict[str, Any]:
    files = sorted(folder.glob("talent_seed*.json"))
    runs = [json.loads(f.read_text()) for f in files]
    table: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    phys: dict[str, list[float]] = defaultdict(list)
    stamina: list[float] = []
    stars = {"young": defaultdict(lambda: {"n": 0, "hits": defaultdict(int)}), "draft": defaultdict(lambda: {"n": 0, "hits": defaultdict(int)})}
    turnover, dist, named = [], {}, {}
    older: dict[str, dict[str, list[float]]] = {b: defaultdict(list) for b in ("28-29", "30-32", "33-35", "36-39")}
    first_seen_top5 = []
    for run in runs:
        hist = {int(k): v for k, v in run["history"].items()}
        meta = run["players"]
        cuts = run["opening_impacts_sorted"]
        thresholds = {"top_10": cuts[9], "top_25": cuts[24], "top_50": cuts[49]}
        years = sorted(hist)
        sds = {}
        opening = hist[years[0]]
        for k in ("P05", "P06", "P07", "P08", "P09", "P11", "P12"):
            vals = [r["physical"][k] for r in opening.values() if r["physical"].get(k) is not None]
            sds[k] = st.pstdev(vals) if len(vals) > 2 else 1.0
        impact_sd = st.pstdev([r["impact"] for r in opening.values()])
        for y in years[:-1]:
            cur, nxt = hist[y], hist[y + 1]
            by_age: dict[int, dict[str, float]] = defaultdict(dict)
            for pid, r in cur.items():
                # The age a change belongs to is the age during that development season (stored on the next snapshot).
                if r["minutes"] >= 12 and pid in nxt and nxt[pid]["minutes"] >= 12:
                    by_age[int(nxt[pid]["age"])][pid] = r["impact"]
            for age, values in by_age.items():
                for pid, level in box.thirds(values).items():
                    d = nxt[pid]["impact"] - cur[pid]["impact"]
                    table[age]["all"].append(d)
                    table[age][level].append(d)
            for pid, r in cur.items():
                if pid not in nxt:
                    continue
                for k, sd in sds.items():
                    a, b = r["physical"].get(k), nxt[pid]["physical"].get(k)
                    if a is not None and b is not None:
                        phys[k].append((b - a) / sd)
                stamina.append(nxt[pid]["stamina"] - r["stamina"])
            # stars one season before (top 25 impact in y-1) vs others, change y -> y+1
            if y - 1 in hist:
                prev = hist[y - 1]
                top25 = {pid for pid, _ in sorted(prev.items(), key=lambda kv: -kv[1]["impact"])[:25]}
                for pid, r in cur.items():
                    if pid not in nxt or r["minutes"] < 12 or nxt[pid]["minutes"] < 12:
                        continue
                    for band, (lo, hi) in {"28-29": (28, 29), "30-32": (30, 32), "33-35": (33, 35), "36-39": (36, 39)}.items():
                        if lo <= int(nxt[pid]["age"]) <= hi:
                            older[band]["prior_star" if pid in top25 else "other"].append(nxt[pid]["impact"] - r["impact"])
        # top-five turnover by impact among players with 12+ minutes
        prev_top, ever = None, set()
        for y in years:
            ranked = sorted((pid for pid, r in hist[y].items() if r["minutes"] >= 12 or y == years[0]), key=lambda pid: -hist[y][pid]["impact"])
            top = ranked[:5]
            dist.setdefault(y, []).append(distribution([r["impact"] for r in hist[y].values()]))
            if prev_top is not None:
                turnover.append({"year": y, "kept": len(set(top) & prev_top), "new": len(set(top) - prev_top),
                                 "first": len(set(top) - ever)})
                first_seen_top5.extend((y, meta[p]["name"], int(hist[y][p]["age"])) for p in set(top) - ever)
            ever |= set(top)
            prev_top = set(top)
        # young-player star odds (ages 19-23 at the opening season; level among same-age players with 12+ minutes)
        start = hist[years[0]]
        by_age: dict[int, dict[str, float]] = defaultdict(dict)
        below: dict[int, list[str]] = defaultdict(list)
        for pid, r in start.items():
            age = int(r["age"])
            if 19 <= age <= 23:
                (by_age[age].__setitem__(pid, r["impact"]) if r["minutes"] >= 12 else below[age].append(pid))
        groups = {}
        for age, values in by_age.items():
            for pid, level in box.thirds(values).items():
                groups[pid] = f"{age} {level}"
        for age, pids in below.items():
            for pid in pids:
                groups[pid] = f"{age} below minutes cut"
        for pid, group in groups.items():
            cell = stars["young"][group]
            cell["n"] += 1
            peak = max(hist[y][pid]["impact"] for y in years if pid in hist[y])
            for name, cut in thresholds.items():
                if start[pid]["impact"] >= cut:
                    cell["hits"][name + "_already"] += 1
                elif peak >= cut:
                    cell["hits"][name] += 1
        # draft slot: real 2026 draftees (draft_year in meta unknown; use age<=20 and pick) and generated classes
        for pid, m in meta.items():
            if not m.get("pick"):
                continue
            entry = m.get("entry")
            seen = [y for y in years if pid in hist[y]]
            if not seen:
                continue
            if entry is None:
                first = hist[seen[0]][pid]
                if first["age"] > 20.5:   # only this year's real draftees
                    continue
            pick = int(m["pick"])
            group = "1-3" if pick <= 3 else "4-10" if pick <= 10 else "11-30" if pick <= 30 else "second round"
            cell = stars["draft"][group]
            cell["n"] += 1
            peak = max(hist[y][pid]["impact"] for y in seen)
            for name, cut in thresholds.items():
                if peak >= cut:
                    cell["hits"][name] += 1
        for pid, m in meta.items():
            if m["name"] in NAMED or (m.get("generated") and m.get("pick") and int(m["pick"]) <= 5):
                named.setdefault(f"{m['name']} (seed {run['seed']})", [(y, int(hist[y][pid]["age"]), round(hist[y][pid]["impact"], 2))
                                                                     for y in years if pid in hist[y]])
    by_age = {str(a): {k: {"n": len(v), "mean": mean(v)} for k, v in c.items()} for a, c in sorted(table.items())}
    return {
        "runs": len(runs), "impact_sd_opening": round(impact_sd, 3),
        "development_talent": band_table(table), "by_age": by_age, "peak_age": box.peak_age(table),
        "physical_change_in_league_sd": {k: {"median_abs": q([abs(x) for x in v], .5), "p90_abs": q([abs(x) for x in v], .9),
                                              "p99_abs": q([abs(x) for x in v], .99)} for k, v in phys.items()},
        "stamina_trait_change": {"p10": q(stamina, .1), "median": q(stamina, .5), "p90": q(stamina, .9),
                                 "p99": q(stamina, .99), "share_over_5": round(sum(abs(x) > 5 for x in stamina) / max(1, len(stamina)), 4)},
        "older_by_prior_star": {b: {k: {"n": len(v), "mean": mean(v)} for k, v in c.items()} for b, c in older.items()},
        "turnover": turnover, "first_time_top5": first_seen_top5,
        "distribution_by_year": {str(y): v for y, v in dist.items()},
        "young_star_odds": {g: {"n": c["n"], **{k: v for k, v in c["hits"].items()}} for g, c in sorted(stars["young"].items())},
        "draft_star_odds": {g: {"n": c["n"], **{k: v for k, v in c["hits"].items()}} for g, c in sorted(stars["draft"].items())},
        "named": named,
    }


def real_lebron_bands() -> dict[str, dict[str, Any]]:
    """Basketball Index LEBRON change by age band (same pairs as the BPM panel, starting third by BPM)."""
    table = evidence()["basketball_index"]["lebron_development_by_bpm_starting_level"]
    out = {}
    for low, high in BANDS:
        cell = {}
        for k in ("all", "bottom", "middle", "top"):
            rows = [(table[str(a)][k]["n"], table[str(a)][k]["mean"]) for a in range(low, high + 1)
                    if str(a) in table and k in table[str(a)] and table[str(a)][k].get("mean") is not None]
            n = sum(r[0] for r in rows)
            cell[k] = {"n": n, "mean": round(sum(r[0] * r[1] for r in rows) / n, 2) if n else None}
        out[f"{low}-{high}"] = cell
    return out


def compare(before: Path, after: Path, probe_old: Path | None, probe_new: Path | None) -> str:
    """Markdown tables: real evidence next to the game before and after (five-season runs and the probes)."""
    b = json.loads((before / "report_game.json").read_text())
    a = json.loads((after / "report_game.json").read_text())
    real = real_band_table()
    lebron = real_lebron_bands()
    fmt = lambda c, k: f"{c[k]['mean']:+.2f}" if c and c.get(k) and c[k].get("mean") is not None else "-"
    lines = ["### Simulated box-score impact (BPM scale), change per season, 1,000+ minutes both seasons", "",
             "| Ages | Real all | Real bottom / middle / top third | Before all | Before bottom / middle / top | After all | After bottom / middle / top |",
             "|---|---:|---|---:|---|---:|---|"]
    for band in real["same"]:
        r, x, y = real["same"][band], b["development_box_same"].get(band, {}), a["development_box_same"].get(band, {})
        trio = lambda c: " / ".join(fmt(c, k) for k in ("bottom", "middle", "top"))
        n = lambda c: c.get("all", {}).get("n", 0)
        lines.append(f"| {band} | {fmt(r, 'all')} | {trio(r)} | {fmt(x, 'all')} ({n(x)}) | {trio(x)} | {fmt(y, 'all')} ({n(y)}) | {trio(y)} |")
    lines += ["", f"Peak age (running sum of the 'all' column): real 26, before {b['peak_age_box']}, after {a['peak_age_box']}. "
              f"Box-score impact per point of engine value: before {b['box_on_talent_slope']}, after {a['box_on_talent_slope']}.", "",
              "### Starting level taken from the season before (removes most regression to the mean)", "",
              "| Ages | Real bottom / middle / top | Before bottom / middle / top | After bottom / middle / top |", "|---|---|---|---|"]
    for band in real["prior"]:
        trio = lambda c: " / ".join(fmt(c, k) for k in ("bottom", "middle", "top"))
        lines.append(f"| {band} | {trio(real['prior'][band])} | {trio(b['development_box_prior'].get(band, {}))} | {trio(a['development_box_prior'].get(band, {}))} |")
    lines += ["", "### Engine player value (Basketball Index LEBRON units), change per season", "",
              "| Ages | Real LEBRON all | Five seasons before | Five seasons after |" + (" Probe before | Probe after |" if probe_old else ""),
              "|---|---:|---:|---:|" + ("---:|---:|" if probe_old else "")]
    po = json.loads((probe_old / "report_talent.json").read_text()) if probe_old else None
    pn = json.loads((probe_new / "report_talent.json").read_text()) if probe_new else None
    for band in lebron:
        row = f"| {band} | {fmt(lebron[band], 'all')} | {fmt(b['development_talent'].get(band), 'all')} | {fmt(a['development_talent'].get(band), 'all')} |"
        if po:
            row += f" {fmt(po['development_talent'].get(band), 'all')} | {fmt(pn['development_talent'].get(band), 'all')} |"
        lines.append(row)
    lines += ["", "### Older players: change per season by a league top-25 finish the season before (box-score impact)", "",
              "| Ages | Real stars / others | Before stars / others | After stars / others |", "|---|---|---|---|"]
    ev = evidence()["development"]["older_by_prior_star_status"]
    for band in ("28-29", "30-32", "33-35", "36-39"):
        e = ev[band.replace("-", "–")]
        g = lambda r: f"{r['older_box'][band].get('prior_star', {}).get('mean', '-')} ({r['older_box'][band].get('prior_star', {}).get('n', 0)}) / {r['older_box'][band].get('other', {}).get('mean', '-')}"
        lines.append(f"| {band} | {e['prior_top_25_vorp']['mean']:+.2f} / {e['other_prior_qualifiers']['mean']:+.2f} | {g(b)} | {g(a)} |")
    lines += ["", "### Top five by simulated box-score impact", "",
              "| Season | Before: top five (mean) | Kept / new / first-ever | After: top five (mean) | Kept / new / first-ever |", "|---|---|---|---|---|"]
    for x, y in zip(b["top_five_box"], a["top_five_box"]):
        names = lambda r: ", ".join(f"{n} {v:+.1f}" for n, v, _ in r["top"]) + f" ({r['mean']:+.1f})"
        turn = lambda r: "-" if r["kept"] is None else f"{r['kept']} / {r['new_or_returning']} / {', '.join(r['first_ever']) or 'none'}"
        lines.append(f"| {x['year'] - 1}-{str(x['year'])[2:]} | {names(x)} | {turn(x)} | {names(y)} | {turn(y)} |")
    lines += ["", "### League talent (engine value of rostered players, February of each season)", "",
              "| Season | Before best / top-5 mean / 10th / 50th / 150th | After best / top-5 mean / 10th / 50th / 150th |", "|---|---|---|"]
    for year in b["talent_distribution"]:
        d = lambda r: " / ".join(f"{r['talent_distribution'][year][k]:.2f}" for k in ("best", "top5_mean", "10th", "50th", "150th")) if year in r["talent_distribution"] else "-"
        lines.append(f"| {int(year) - 1}-{str(year)[2:]} | {d(b)} | {d(a)} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("talent", "game", "real", "compare"))
    parser.add_argument("path", nargs="*")
    args = parser.parse_args()
    if args.mode == "compare":
        paths = [Path(p) for p in args.path]
        print(compare(paths[0], paths[1], paths[2] if len(paths) > 2 else None, paths[3] if len(paths) > 3 else None))
        return
    args.path = args.path[0] if args.path else None
    if args.mode == "real":
        tables = real_band_table()
        print("\n".join(fmt_band_rows({"same-season thirds": tables["same"], "prior-season thirds": tables["prior"]})))
        return
    path = Path(args.path)
    result = talent_report(path) if args.mode == "talent" else game_report(path)
    (path / f"report_{args.mode}.json").write_text(json.dumps(result, indent=1, default=str) + "\n")
    if args.mode == "talent":
        print("\n".join(fmt_band_rows({"talent": result["development_talent"]})))
        print("peak", result["peak_age"], "impact sd", result["impact_sd_opening"])
        for k in ("physical_change_in_league_sd", "stamina_trait_change", "older_by_prior_star", "young_star_odds", "draft_star_odds"):
            print(k, json.dumps(result[k]))
        print("turnover", result["turnover"])
        print("first-time top five", result["first_time_top5"])
        for y, v in result["distribution_by_year"].items():
            print(y, v)
        for name, traj in result["named"].items():
            print(name, traj)
    else:
        print("\n".join(fmt_band_rows({"box": result["development_box_same"], "talent": result["development_talent"]})))
        print("peak box", result["peak_age_box"], "peak talent", result["peak_age_talent"], "slope", result["box_on_talent_slope"],
              "box sd", result["box_sd"], "talent sd", result["talent_sd"])
        print("prior-thirds box"); print("\n".join(fmt_band_rows({"box prior": result["development_box_prior"]})))
        print("older", json.dumps(result["older_box"]))
        for row in result["top_five_box"]:
            print(row)
        for y, v in result["talent_distribution"].items():
            print("talent", y, v)
        for y, v in result["box_distribution"].items():
            print("box", y, v)
        for p in result["named"] + result["best_made_up"]:
            print(p["name"], p["origin"], p["pick"], p["by_year"])


if __name__ == "__main__":
    main()
