#!/usr/bin/env python3
"""RATINGS-AUDIT-GSW: the game's player order against real use and analyst / impact evidence (2026-11-22).

Diagnostic only: nothing here moves a rating. Reads
- a ratings snapshot (scripts/research/rookie_fit_check.py snapshot <file>): the game's overall / offense / defense
  and value per player;
- Basketball Reference 2026-27 pages saved under output/ratings-audit-gsw/bbref/ (NBA_2027_advanced.html,
  NBA_2027_per_poss.html; fetched for ROOKIE-FIT-2 on 2026-11-22, paths allowed by robots.txt);
- the analyst consensus of scripts/research/ratings_consensus.py (output/ratings-consensus/consensus.json);
- Basketball Index multi-year LEBRON (local only).

    PYTHONPATH=src .venv/bin/python scripts/research/ratings_audit_gsw.py team GSW output/ratings-audit-gsw/snapshot_before.json
    PYTHONPATH=src .venv/bin/python scripts/research/ratings_audit_gsw.py league output/ratings-audit-gsw/snapshot_before.json
"""
from __future__ import annotations

import csv
import html
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
BBREF = ROOT / "output/ratings-audit-gsw/bbref"
LEBRON_CSV = ROOT / "data/research/bbi/captures/fanspo_tools/lebron/lebron_separate-seasons_raw_all-2010-2026.csv"
TEAM_ABBR = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}


def norm(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = "".join(ch if ch.isalnum() or ch == " " else " " for ch in text.replace("'", "").replace(".", ""))
    words = [w for w in text.split() if w not in ("jr", "sr", "ii", "iii", "iv")]
    return " ".join(words)


def _num(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bbref_table(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    start = text.find("<tbody")
    body = text[start:text.find("</tbody>", start)]
    rows = []
    for raw in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = {k: html.unescape(re.sub("<[^>]+>", "", v)) for k, v in
                 re.findall(r'data-stat="([^"]+)"[^>]*>(.*?)</t[dh]>', raw, re.S)}
        if cells.get("name_display"):
            rows.append(cells)
    return rows


def real_2027() -> dict[str, dict]:
    """Per player (normalized name): 2026-27 so far, the combined row for traded players (team = last listed)."""
    per_poss = {}
    for r in bbref_table(BBREF / "NBA_2027_per_poss.html"):
        per_poss.setdefault(norm(r["name_display"]), r)
    out = {}
    for r in bbref_table(BBREF / "NBA_2027_advanced.html"):
        key = norm(r["name_display"])
        if key in out:      # first row is the season total for a traded player
            out[key]["teams"].append(TEAM_ABBR.get(r["team_name_abbr"], r["team_name_abbr"]))
            continue
        p = per_poss.get(key, {})
        out[key] = {"name": r["name_display"], "team": TEAM_ABBR.get(r["team_name_abbr"], r["team_name_abbr"]),
                    "teams": [], "g": _num(r["games"]), "gs": _num(r["games_started"]), "mp": _num(r["mp"]),
                    "usg": _num(r["usg_pct"]), "ts": _num(r["ts_pct"]), "obpm": _num(r["obpm"]),
                    "dbpm": _num(r["dbpm"]), "bpm": _num(r["bpm"]), "vorp": _num(r["vorp"]),
                    "ws48": _num(r["ws_per_48"]), "pts100": _num(p.get("pts_per_poss")),
                    "ast100": _num(p.get("ast_per_poss")), "ortg": _num(p.get("off_rtg")), "drtg": _num(p.get("def_rtg"))}
    return out


def lebron(season: str = "2026") -> dict[str, dict]:
    out = {}
    if not LEBRON_CSV.exists():
        return out
    with LEBRON_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["Season"] == season:
                out[norm(row["Player"])] = {k: row[k] for k in row}
    return out


def multi_year_lebron() -> dict[str, dict]:
    path = ROOT / "data/research/bbi/normalized.json"
    out = {}
    if not path.exists():
        return out
    data = json.loads(path.read_text())
    for rec in data.get("players", data if isinstance(data, list) else []):
        name = rec.get("name") or rec.get("player")
        if name:
            out[norm(name)] = rec
    return out


def team(abbr: str, snapshot_path: str) -> None:
    snap = json.loads(Path(snapshot_path).read_text())
    real = real_2027()
    leb = lebron()
    rows = [r for r in snap if r["team"] == abbr]
    print("| Rank | Player | Age | OVR | OFF | DEF | Value off/def | 26-27 G/GS | MPG | USG | TS | BPM (O/D) | 25-26 LEBRON (O/D) |")
    print("|---:|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|")
    for r in rows:
        x = real.get(norm(r["name"]), {})
        l = leb.get(norm(r["name"]), {})
        mpg = (x["mp"] / x["g"]) if x.get("g") else None
        lb = f"{float(l['LEBRON']):+.2f} ({float(l['O-LEBRON']):+.2f}/{float(l['D-LEBRON']):+.2f}), {float(l.get('Minutes') or 0):.0f} min" if l else ""
        real_txt = (f"{x['g']:.0f}/{x['gs']:.0f} | {mpg:.1f} | {x['usg']} | {x['ts']} | {x['bpm']:+.1f} ({x['obpm']:+.1f}/{x['dbpm']:+.1f})"
                    if x.get("g") else " | | | | ")
        print(f"| {r['rank']} | {r['name']} | {r['age']:.0f} | {r['ovr']} | {r['off']} | {r['def']} | "
              f"{r['impact_off']:+.2f}/{r['impact_def']:+.2f} | {real_txt} | {lb} |")


def age_band(age: float) -> str:
    for hi, label in ((21, "19-21"), (24, "22-24"), (27, "25-27"), (30, "28-30"), (33, "31-33"), (99, "34+")):
        if age <= hi:
            return label
    return "34+"


BANDS = ("19-21", "22-24", "25-27", "28-30", "31-33", "34+")


def lag_by_age() -> dict:
    """How the measured multi-season level lags the next season, by age.

    (a) Basketball Index Multi-Year LEBRON at season t (the number the game's player value is fitted to) against
        single-season LEBRON at t+1, for 2023-24 -> 2024-25 and 2024-25 -> 2025-26 (current players).
    (b) Long history 2010-2026 (separate-season LEBRON): a three-season blend with the builder's season weights
        (1 / 0.7 / 0.45 for t, t-1, t-2) against t+1. Players with 20+ minutes a game in t+1, weighted by them.
    Age is the age in season t+1 (the season being forecast).
    """
    from nba_gm_data import bbi_evidence as be
    from nba_gm_data.app_actions import load_app_canonical
    out = {}
    table = be.collect_values(ROOT, {"Multi-Year O-LEBRON", "Multi-Year D-LEBRON", "O-LEBRON", "D-LEBRON"})
    canonical = load_app_canonical(ROOT)
    ages = {p["id"]: float(p.get("age") or 27) for p in canonical["players"]}   # age at 2026-27
    pairs = []
    for t, t1, back in (("2023-24", "2024-25", 2), ("2024-25", "2025-26", 1)):
        for pid, cell in table.get((t, "Multi-Year O-LEBRON"), {}).items():
            o_my = cell[0]
            d_my = table.get((t, "Multi-Year D-LEBRON"), {}).get(pid)
            o1 = table.get((t1, "O-LEBRON"), {}).get(pid)
            d1 = table.get((t1, "D-LEBRON"), {}).get(pid)
            if d_my and o1 and d1 and o1[1] >= 1000 and pid in ages:
                pairs.append((ages[pid] - back, (o1[0] + d1[0]) - (o_my + d_my[0]), o1[1]))
    out["multi_year"] = _band_means(pairs)
    # (b) long history, ages from Basketball Reference for everyone (not only today's players)
    panel = json.loads((ROOT / "data/research/development_evidence.json").read_text())["public_inputs"]["seasons"]
    info = {(norm(r[2]), int(r[0])): (float(r[3]), float(r[4]), float(r[5])) for r in panel
            if r[3] is not None and r[4] is not None and r[5] is not None}   # age, minutes, bpm
    leb_rows: dict[str, dict[int, float]] = {}
    with LEBRON_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            leb_rows.setdefault(norm(row["Player"]), {})[int(row["Season"])] = float(row["LEBRON"])
    out["three_season_blend_lebron"] = _blend_pairs({k: v for k, v in leb_rows.items()}, info)
    bpm_rows: dict[str, dict[int, float]] = {}
    for (name, year), (_, minutes, bpm) in info.items():
        if minutes >= 250:
            bpm_rows.setdefault(name, {})[year] = bpm
    out["three_season_blend_bpm"] = _blend_pairs(bpm_rows, info)
    out["note"] = ("measured level = the builder's season weights 1 / 0.7 / 0.45 (t, t-1, t-2) x minutes; players with "
                   "1,000+ minutes in t; change = season t+1 (500+ minutes) minus that level; drop-outs counted apart")
    return out


def _blend_pairs(rows, info, weights=(1.0, 0.7, 0.45)):
    pairs, gone = [], []
    for name, by_season in rows.items():
        for t, _ in by_season.items():
            meta = info.get((name, t))
            if not meta or meta[1] < 1000:
                continue
            past = []
            for k in range(3):
                m = info.get((name, t - k))
                if (t - k) in by_season and m and m[1] >= 250:
                    past.append((by_season[t - k], weights[k] * min(m[1], 2500.0)))
            level = sum(v * w for v, w in past) / sum(w for _, w in past)
            nxt = info.get((name, t + 1))
            age1 = meta[0] + 1
            if (t + 1) in by_season and nxt and nxt[1] >= 500:
                pairs.append((age1, by_season[t + 1] - level, min(meta[1], 2500.0)))
            elif t + 1 <= 2026:
                gone.append(age1)
    res = _band_means(pairs)
    total = {b: sum(1 for a, _, _ in pairs if age_band(a) == b) + sum(1 for a in gone if age_band(a) == b) for b in BANDS}
    res["dropped_share"] = {b: round(sum(1 for a in gone if age_band(a) == b) / total[b], 3) for b in BANDS if total[b]}
    return res


def _band_means(pairs):
    res = {}
    for band in BANDS:
        sel = [(d, w) for a, d, w in pairs if age_band(a) == band]
        if sel:
            sw = sum(w for _, w in sel)
            res[band] = {"n": len(sel), "mean_change": round(sum(d * w for d, w in sel) / sw, 3)}
    by_age = {}
    for a, d, w in pairs:
        by_age.setdefault(int(round(a)), []).append((d, w))
    res["by_age"] = {a: [len(v), round(sum(d * w for d, w in v) / sum(w for _, w in v), 3)] for a, v in sorted(by_age.items())}
    return res


def analyst_rank_map() -> dict[str, dict]:
    raw = json.loads((ROOT / "output/ratings-consensus/raw/public_rankings.json").read_text())
    out: dict[str, dict] = {}
    for lst in raw["lists"]:
        src = "espn" if "ESPN" in lst["source"] else "ringer" if "Ringer" in lst["source"] else None
        if not src:
            continue
        for entry in lst.get("players") or lst.get("ranking") or []:
            name = entry.get("name") or entry.get("player")
            out.setdefault(norm(name), {})[src] = entry.get("rank")
    return out


def league(snapshot_path: str) -> None:
    snap = json.loads(Path(snapshot_path).read_text())
    real = real_2027()
    ranks = analyst_rank_map()
    leb = lebron()
    rows = []
    for r in snap:
        key = norm(r["name"])
        a = ranks.get(key, {})
        x = real.get(key, {})
        l = leb.get(key)
        rows.append({**r, "espn": a.get("espn"), "ringer": a.get("ringer"),
                     "analyst": statistics.fmean([a.get("espn") or 110, a.get("ringer") or 110]) if a else None,
                     "real": x, "lebron_2526": float(l["LEBRON"]) if l else None,
                     "lebron_mpg": float(l["MPG"]) if l else None})
    # 1. Top-100 lists: game rank vs analyst rank by age
    ranked = sorted([r for r in rows if r["analyst"] is not None and r["draft_year"] != "2026"], key=lambda r: r["analyst"])
    for i, r in enumerate(ranked, 1):
        r["analyst_rank"] = i
    by_game = sorted(ranked, key=lambda r: -r["impact"])
    for i, r in enumerate(by_game, 1):
        r["game_rank_in_set"] = i
    print(f"## Analyst top-100 players ({len(ranked)}): game rank minus analyst rank (+ = game rates him lower), by age")
    for band in BANDS:
        sel = [r["game_rank_in_set"] - r["analyst_rank"] for r in ranked if age_band(r["age"]) == band]
        if sel:
            print(f"- {band}: {len(sel)} players, mean gap {statistics.fmean(sel):+.1f}, median {statistics.median(sel):+.1f}")
    # 2. This season so far: BPM against the game's value, residual by age (minutes-weighted)
    pts = [(r, r["real"]) for r in rows if r["real"].get("mp") and r["real"]["mp"] >= 150]
    xs = [r["impact"] for r, _ in pts]
    ys = [x["bpm"] for _, x in pts]
    ws = [x["mp"] for _, x in pts]
    sw = sum(ws)
    mx, my = sum(a * w for a, w in zip(xs, ws)) / sw, sum(b * w for b, w in zip(ys, ws)) / sw
    slope = sum(w * (a - mx) * (b - my) for a, b, w in zip(xs, ys, ws)) / sum(w * (a - mx) ** 2 for a, w in zip(xs, ws))
    corr = sum(w * (a - mx) * (b - my) for a, b, w in zip(xs, ys, ws)) / (
        sum(w * (a - mx) ** 2 for a, w in zip(xs, ws)) ** .5 * sum(w * (b - my) ** 2 for b, w in zip(ys, ws)) ** .5)
    print(f"\n## 2026-27 so far ({len(pts)} players, 150+ minutes): box plus-minus vs game value: slope {slope:.2f}, "
          f"correlation {corr:.2f}")
    print("Residual (real minus expected from game value), minutes-weighted, by age:")
    for band in BANDS:
        sel = [(b - (my + slope * (a - mx)), w) for (r, x), a, b, w in zip(pts, xs, ys, ws) if age_band(r["age"]) == band]
        if sel:
            print(f"- {band}: {len(sel)} players, {sum(w for _, w in sel):.0f} minutes, residual "
                  f"{sum(d * w for d, w in sel) / sum(w for _, w in sel):+.2f}")
    json.dump(rows, open(ROOT / "output/ratings-audit-gsw/league_rows.json", "w"), indent=0, default=str)


CURVE_OUT = ROOT / "data/research/age_projection_2026_27.json"
SEASON_WEIGHTS = (1.0, 0.7, 0.45)      # the builder's season weights (input_estimator: 2025-26, 2024-25, 2023-24)
BANDWIDTH = 1.5                         # years; Gaussian smoothing across ages


def _smooth(points: dict[int, tuple[float, float]], ages=range(19, 42)) -> dict[int, float]:
    """Kernel-smoothed mean by age; points = {age: (mean, weight)}."""
    import math
    out = {}
    for a in ages:
        num = den = 0.0
        for b, (m, w) in points.items():
            k = w * math.exp(-0.5 * ((a - b) / BANDWIDTH) ** 2)
            num += k * m
            den += k
        out[a] = num / den
    return out


def age_curve() -> dict:
    """Expected change from the builder's measured level to the next season's opening day, by age (LEBRON points).

    Evidence: Basketball Index separate-season LEBRON 2010-2026 (offense and defense), ages from Basketball Reference
    (development_evidence.json). For every player-season t with 1,000+ minutes:
      level  = minutes-weighted blend of t, t-1, t-2 with the builder's season weights (1 / 0.7 / 0.45);
      lag    = LEBRON in t+1 (500+ minutes) minus level;
      annual = LEBRON in t+1 minus LEBRON in t (the per-season change at that age).
    Opening day of t+1 = the t+1 season average minus half a season of change, so
      shift(age) = lag(age) - 0.5 x annual(age).
    The half season matters because the game's own monthly development runs through the season from opening day.
    Ages are the age in season t+1. Each side is smoothed across ages (Gaussian, 1.5 years). Survivors only: players
    who left the league are missing (13-22% of those 28 and older), so older players' decline is if anything
    understated.
    """
    panel = json.loads((ROOT / "data/research/development_evidence.json").read_text())["public_inputs"]["seasons"]
    info = {(norm(r[2]), int(r[0])): (float(r[3]), float(r[4])) for r in panel if r[3] is not None and r[4] is not None}
    rows: dict[str, dict[int, tuple[float, float]]] = {}
    with LEBRON_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.setdefault(norm(row["Player"]), {})[int(row["Season"])] = (float(row["O-LEBRON"]), float(row["D-LEBRON"]))
    acc = {side: {"lag": {}, "annual": {}} for side in ("offense", "defense")}
    for name, seasons in rows.items():
        for t, now in seasons.items():
            meta = info.get((name, t))
            nxt = info.get((name, t + 1))
            if not meta or meta[1] < 1000 or (t + 1) not in seasons or not nxt or nxt[1] < 500:
                continue
            past = []
            for k in range(3):
                m = info.get((name, t - k))
                if (t - k) in seasons and m and m[1] >= 250:
                    past.append((seasons[t - k], SEASON_WEIGHTS[k] * min(m[1], 2500.0)))
            age = int(round(meta[0] + 1))
            w = min(meta[1], 2500.0)
            for i, side in enumerate(("offense", "defense")):
                level = sum(v[i] * wt for v, wt in past) / sum(wt for _, wt in past)
                acc[side]["lag"].setdefault(age, []).append((seasons[t + 1][i] - level, w))
                acc[side]["annual"].setdefault(age, []).append((seasons[t + 1][i] - now[i], w))
    out = {"version": "age_projection_v1_2026_11_22", "method": " ".join(age_curve.__doc__.split()),
           "sources": ["Basketball Index LEBRON by season 2010-2026 (fanspo tools capture, local)",
                       "Basketball Reference ages and minutes (data/research/development_evidence.json)"],
           "measured_season": "2025-26", "season_weights": list(SEASON_WEIGHTS), "bandwidth_years": BANDWIDTH,
           "raw": {}, "shift": {}}
    for side, parts in acc.items():
        means = {}
        for part, by_age in parts.items():
            pts = {a: (sum(d * w for d, w in v) / sum(w for _, w in v), float(len(v))) for a, v in by_age.items()}
            means[part] = _smooth(pts)
            out["raw"].setdefault(side, {})[part] = {str(a): [round(m, 3), int(n)] for a, (m, n) in sorted(pts.items())}
        out["shift"][side] = {str(a): round(means["lag"][a] - 0.5 * means["annual"][a], 3) for a in means["lag"]}
        out.setdefault("annual", {})[side] = {str(a): round(means["annual"][a], 3) for a in means["annual"]}
    CURVE_OUT.write_text(json.dumps(out, indent=1) + "\n")
    return out


def thin_evidence_level() -> dict:
    """Real impact of players with little or no NBA track record, when they do play (Basketball Index LEBRON).

    For each player-season s (2011-2026, 250+ minutes): the player's NBA minutes in the three seasons before s
    (Basketball Reference). Groups: none (<1), thin (1-249), 250-999, 1000-1999, 2000+. First-round picks are left out
    of the first two groups (they are the rookie translation's job). Mean O-/D-LEBRON in s, unweighted. Players who
    never got 250 minutes are missing, so the low groups' means are an upper bound on their level.
    """
    panel = json.loads((ROOT / "data/research/development_evidence.json").read_text())["public_inputs"]
    minutes = {}
    for r in panel["seasons"]:
        if r[4] is not None:
            key = (norm(r[2]), int(r[0]))
            minutes[key] = minutes.get(key, 0.0) + float(r[4])
    first_round = {norm(r[3]) for r in panel["draft"] if r[1] is not None and int(r[1]) <= 30}
    groups = {}
    with LEBRON_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            s = int(row["Season"])
            name = norm(row["Player"])
            if s < 2011 or minutes.get((name, s), 0) < 250:
                continue
            before = sum(minutes.get((name, s - k), 0.0) for k in (1, 2, 3))
            label = ("none" if before < 1 else "thin" if before < 250 else "250-999" if before < 1000
                     else "1000-1999" if before < 2000 else "2000+")
            if label in ("none", "thin") and name in first_round:
                continue
            groups.setdefault(label, []).append((float(row["O-LEBRON"]), float(row["D-LEBRON"])))
    return {g: {"n": len(v), "offense": round(statistics.fmean(x[0] for x in v), 3),
                "defense": round(statistics.fmean(x[1] for x in v), 3)} for g, v in groups.items()}


def compare(before_path: str, after_path: str, team_abbr: str | None = None, names: list[str] | None = None) -> None:
    """Before/after table (overall, league rank, value offense/defense) for a team or named players."""
    before = {r["id"]: r for r in json.loads(Path(before_path).read_text())}
    after = {r["id"]: r for r in json.loads(Path(after_path).read_text())}
    rows = [r for r in after.values() if (team_abbr and r["team"] == team_abbr) or (names and r["name"] in names)]
    rows.sort(key=lambda r: r["rank"])
    print("| Player | Age | Overall before → after | League rank before → after | Value off/def before → after |")
    print("|---|---:|---:|---:|---|")
    for r in rows:
        b = before[r["id"]]
        print(f"| {r['name']} | {r['age']:.0f} | {b['ovr']} → {r['ovr']} | {b['rank']} → {r['rank']} | "
              f"{b['impact_off']:+.2f}/{b['impact_def']:+.2f} → {r['impact_off']:+.2f}/{r['impact_def']:+.2f} |")
    moved = [abs(after[p]["ovr"] - before[p]["ovr"]) for p in after if p in before]
    print(f"\nPlayers whose overall moved by 0.1+: {sum(1 for m in moved if m >= 0.1)} of {len(moved)}; "
          f"by 1.0+: {sum(1 for m in moved if m >= 1.0)}; largest {max(moved):.1f}")


def sim_minutes(*probe_dirs: str) -> None:
    """Warriors' minutes per game in simulated stretches (rookie_season_probe.py output), side by side."""
    runs = [json.loads((Path(d) / "rookies.json").read_text())["league_stats"] for d in probe_dirs]
    ids = sorted({p for run in runs for p in run if p.startswith("player_gsw-")},
                 key=lambda p: -(runs[-1].get(p, {}).get("minutes") or 0))
    print("| Player | " + " | ".join(f"{Path(d).name}: games, minutes a game" for d in probe_dirs) + " |")
    print("|---|" + "---:|" * len(runs))
    for p in ids:
        cells = []
        for run in runs:
            s = run.get(p, {})
            g = s.get("games") or 0
            cells.append(f"{g}, {(s.get('minutes') or 0) / g:.1f}" if g else "-")
        print(f"| {p.split('-', 1)[1].replace('-', ' ').title()} | " + " | ".join(cells) + " |")


def main() -> None:
    cmd = sys.argv[1]
    if cmd == "sim":
        sim_minutes(*sys.argv[2:])
        return
    if cmd == "compare":
        compare(sys.argv[2], sys.argv[3], team_abbr=sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None,
                names=sys.argv[5:] or None)
        return
    if cmd == "thin":
        groups = thin_evidence_level()
        out = {"version": "no_track_record_level_v1_2026_11_22", "method": " ".join(thin_evidence_level.__doc__.split()),
               "sources": ["Basketball Index LEBRON by season 2010-2026 (fanspo tools capture, local)",
                           "Basketball Reference minutes and draft (data/research/development_evidence.json)"],
               "groups": groups, "level": {"offense": groups["none"]["offense"], "defense": groups["none"]["defense"]}}
        (ROOT / "data/research/no_track_record_level_2026_27.json").write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps(out, indent=1))
        return
    if cmd == "team":
        team(sys.argv[2], sys.argv[3])
    elif cmd == "lag":
        print(json.dumps(lag_by_age(), indent=1))
    elif cmd == "curve":
        c = age_curve()
        for side in ("offense", "defense"):
            print(side, c["shift"][side])
    elif cmd == "player":
        player_inputs(sys.argv[2:])
    elif cmd == "league":
        league(sys.argv[2])
    else:
        raise SystemExit(__doc__)



def _grade(record):
    value = (record or {}).get("value")
    if isinstance(value, dict):
        if isinstance(value.get("grade"), (int, float)):
            return float(value["grade"])
        display = value.get("display_grade")
        if isinstance(display, dict) and isinstance(display.get("grade"), (int, float)):
            return float(display["grade"])
    return None


def player_inputs(names: list[str]) -> None:
    """Each named player's technique and physical grades with their league percentile (rostered players)."""
    from nba_gm_data import ratings_model
    from nba_gm_data.input_estimator import DEFINITIONS
    _, league = ratings_model._load_inputs_keyed(ROOT)
    cols = {}
    for pid, inputs in league.items():
        for iid, rec in inputs.items():
            g = _grade(rec)
            if g is not None:
                cols.setdefault(iid, []).append(g)
    for iid in cols:
        cols[iid].sort()
    import bisect
    for name in names:
        pid = next((p for p in league if norm(p.split("-", 1)[-1].replace("-", " ")) == norm(name)), None)
        if not pid:
            print("not found", name)
            continue
        print(f"### {name} ({pid})")
        line = []
        for iid, d in DEFINITIONS.items():
            g = _grade(league[pid].get(iid))
            if g is None:
                continue
            pct = 100 * bisect.bisect_left(cols[iid], g) / len(cols[iid])
            line.append(f"{iid} {d.get('name', '')[:28]}: {g:.0f} (p{pct:.0f})")
        print("\n".join(line))


if __name__ == "__main__":
    main()
