#!/usr/bin/env python3
"""ROOKIE-SEASON: how much do real young players improve within a season, and how much over the summer?

Real: ESPN game logs fetched by rookie_halves_fetch.py (regular seasons 2015-16 .. 2025-26), for first-, second- and
third-year players (Basketball Reference rookie classes) with 400+ minutes and a fixed sample of veterans aged 26-30.
Each player-season is split at the season's middle date (the median date of all fetched games). For players with
300+ minutes in both halves:

  in-season change   second half minus first half
  summer change      next season's first half minus this season's second half (same player, both 300+ minutes)

Measures (per 36 minutes unless noted): points, rebounds, assists, steals, blocks, turnovers; true shooting; shot
volume (field-goal attempts + 0.44 free-throw attempts); minutes per game; box impact (the DEV-CURVE box-score
formula, data/research/dev_curve_box_bpm.json, fitted on real box plus-minus, r2 0.87) with minutes per game held at
the season's level so a bigger role does not count as improvement. Points per 36 are split into "more shots" (volume
change at the average efficiency) and "better shooting" (efficiency change at the average volume).

Veterans aged 26-30 are the comparison group: their in-season change is the league's seasonal pattern (more
blowouts, tanking teams' lineups, fatigue), which a young player shares; young minus veteran is the part that is
about being young.

    python3 scripts/research/rookie_halves.py [--sim DIR ...] [--json data/research/rookie_halves.json]

With --sim it adds the same table for simulated seasons (rookie_season_probe.py timelines; the season is split at
the probe step nearest the middle of the regular season).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
from rookie_halves_fetch import CACHE, SEASONS, norm, rookie_classes, season_players  # noqa: E402

BOX = json.loads((ROOT / "data/research/dev_curve_box_bpm.json").read_text())
MIN_HALF = 300.0
STATS = ("pts", "reb", "ast", "stl", "blk", "tov")


def parse_log(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    events = data.get("events") or {}
    out = []
    for st in data.get("seasonTypes", []):
        if "Regular Season" not in st.get("displayName", ""):
            continue
        for cat in st.get("categories", []):
            if cat.get("type") != "event":
                continue
            for e in cat.get("events", []):
                s = e.get("stats") or []
                if len(s) < 14:
                    continue
                try:
                    minutes = float(s[0] or 0)
                except ValueError:
                    continue
                if minutes <= 0:
                    continue
                fgm, fga = (float(x) for x in s[1].split("-"))
                f3m, f3a = (float(x) for x in s[3].split("-"))
                ftm, fta = (float(x) for x in s[5].split("-"))
                meta = events.get(e["eventId"]) or {}
                out.append({"date": str(meta.get("gameDate") or "")[:10], "min": minutes, "fgm": fgm, "fga": fga,
                            "f3m": f3m, "f3a": f3a, "ftm": ftm, "fta": fta, "reb": float(s[7]), "ast": float(s[8]),
                            "blk": float(s[9]), "stl": float(s[10]), "pf": float(s[11]), "tov": float(s[12]),
                            "pts": float(s[13]), "team": str((meta.get("team") or {}).get("id") or "")})
    return out


def totals(games: list[dict]) -> dict:
    t = defaultdict(float)
    for g in games:
        for k, v in g.items():
            if k not in ("date", "team"):
                t[k] += v
    t["g"] = len(games)
    return dict(t)


def box_impact(t: dict, mpg: float, volume: float | None = None) -> float:
    """DEV-CURVE box formula on per-36 rates, minutes per game fixed at mpg. volume: shot volume per 36 to hold
    fixed (his shooting scaled to it at his own efficiency and three-point share), so only how well he plays counts."""
    per = 36.0 / t["min"]
    shots = (t["fga"] + 0.44 * t["fta"]) * per
    scale = volume / shots if volume and shots else 1.0
    g = lambda k: t.get(k, 0.0) * per * (scale if k in ("pts", "fga", "fta", "f3a") else 1.0)
    shots = g("fga") + 0.44 * g("fta")
    ast, reb = g("ast"), g("reb")
    x = [mpg, g("pts"), g("pts") - 2.0 * 0.57 * shots, shots, g("f3a"), ast, reb, g("stl"), g("blk"), g("tov"),
         math.sqrt(max(ast, 0.0) * max(reb, 0.0))]
    return BOX["intercept"] + sum(w * (v - m) / s for w, v, m, s in zip(BOX["weights"], x, BOX["mean"], BOX["sd"]))


def rates(t: dict, mpg_fixed: float, volume: float | None = None) -> dict:
    per = 36.0 / t["min"]
    shots = (t["fga"] + 0.44 * t["fta"]) * per
    out = {k: t[k] * per for k in STATS}
    out["shots"] = shots
    out["ts"] = t["pts"] / (2 * (t["fga"] + 0.44 * t["fta"])) if t["fga"] + t["fta"] else 0.0
    out["mpg"] = t["min"] / t["g"]
    out["box"] = box_impact(t, mpg_fixed)
    out["box_skill"] = box_impact(t, mpg_fixed, volume)
    return out


def volume(*parts: dict) -> float:
    """Shot volume per 36 over several periods together."""
    minutes = sum(p["min"] for p in parts)
    return 36.0 * sum(p["fga"] + 0.44 * p["fta"] for p in parts) / minutes


def change(a: dict, b: dict) -> dict:
    d = {k: b[k] - a[k] for k in a}
    ts, shots = (a["ts"] + b["ts"]) / 2, (a["shots"] + b["shots"]) / 2
    d["pts_from_volume"] = 2 * ts * (b["shots"] - a["shots"])
    d["pts_from_efficiency"] = 2 * shots * (b["ts"] - a["ts"])
    return d


def summarize(changes: list[dict]) -> dict:
    out = {"n": len(changes)}
    for k in (*STATS, "shots", "ts", "mpg", "box", "box_skill", "pts_from_volume", "pts_from_efficiency"):
        vals = [c[k] for c in changes]
        out[k] = {"median": round(statistics.median(vals), 3), "mean": round(statistics.fmean(vals), 3),
                  "se": round(statistics.stdev(vals) / math.sqrt(len(vals)), 3) if len(vals) > 1 else None}
    return out


def team_records(year: int) -> dict[str, float]:
    """ESPN team id -> winning share that season (rookie_halves_fetch.py standings)."""
    try:
        data = json.loads((CACHE / f"standings_{year}.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for conf in data.get("children", []):
        for entry in conf["standings"]["entries"]:
            stats = {x["name"]: x.get("value") for x in entry["stats"]}
            out[str(entry["team"]["id"])] = float(stats.get("winPercent") or 0.0)
    return out


def real_panel() -> dict:
    classes = rookie_classes()
    names = {}
    for year in SEASONS:
        for pid, row in season_players(year, allow=False).items():
            names[(pid, year)] = row.get("name")
    logs: dict[tuple[str, int], list[dict]] = {}
    for path in CACHE.glob("gl_*_*.json"):
        _, pid, year = path.stem.split("_")
        games = parse_log(path)
        if games:
            logs[(pid, int(year))] = games
    mid = {}
    for year in SEASONS:
        dates = sorted(g["date"] for (pid, y), games in logs.items() if y == year for g in games)
        if dates:
            mid[year] = dates[len(dates) // 2]
    halves = {}
    for (pid, year), games in logs.items():
        first = [g for g in games if g["date"] <= mid[year]]
        second = [g for g in games if g["date"] > mid[year]]
        if not first or not second:
            continue
        t1, t2, tall = totals(first), totals(second), totals(games)
        rookie = classes.get(norm(names.get((pid, year)) or ""))
        exp = None if rookie is None else year - rookie + 1
        teams = defaultdict(int)
        for g in games:
            teams[g["team"]] += 1
        win = team_records(year).get(max(teams, key=teams.get)) if teams else None
        halves[(pid, year)] = {"t1": t1, "t2": t2, "mpg": tall["min"] / tall["g"], "exp": exp,
                               "name": names.get((pid, year)), "win": win}
    return {"halves": halves, "mid": mid}


def cohort(exp: int | None) -> str:
    return {1: "first year", 2: "second year", 3: "third year"}.get(exp, "veterans 26-30" if exp is None else "other")


def real_tables(panel: dict) -> dict:
    halves = panel["halves"]
    inseason, summer = defaultdict(list), defaultdict(list)
    for (pid, year), h in halves.items():
        if h["t1"]["min"] >= MIN_HALF and h["t2"]["min"] >= MIN_HALF:
            c = change(rates(h["t1"], h["mpg"], volume(h["t1"], h["t2"])),
                       rates(h["t2"], h["mpg"], volume(h["t1"], h["t2"])))
            inseason[cohort(h["exp"])].append(c)
            if h["exp"] == 1 and h["win"] is not None:
                inseason["first, team <.400" if h["win"] < 0.4 else "first, team .400+"].append(c)
        nxt = halves.get((pid, year + 1))
        if nxt and h["t2"]["min"] >= MIN_HALF and nxt["t1"]["min"] >= MIN_HALF:
            mpg = (h["mpg"] + nxt["mpg"]) / 2
            summer[cohort(h["exp"])].append(change(rates(h["t2"], mpg, volume(h["t2"], nxt["t1"])),
                                                   rates(nxt["t1"], mpg, volume(h["t2"], nxt["t1"]))))
    return {"in_season": {k: summarize(v) for k, v in inseason.items()},
            "summer": {k: summarize(v) for k, v in summer.items()}, "split_dates": panel["mid"],
            "timing": timing(inseason, summer), "timing_box": timing(inseason, summer, "box"),
            "timing_points": timing(inseason, summer, "pts")}


def timing(inseason: dict, summer: dict, key: str = "box_skill", draws: int = 400) -> dict:
    """Share of a young player's yearly growth that happens in the regular season.

    Between the middles of the two halves lie three monthly steps, all in the season; between this season's second
    half and next season's first half lie nine: three in the season (April, November, December) and six in the
    off-season. Veterans give the league's seasonal swing s (both halves of every season share it) and their own
    aging rate a: in = 3a + s, summer = 9a - s. For a young group: in = 3r + s and summer = 3r + 6q - s, with r the
    growth per in-season step and q per off-season step; the in-season share of the year is 6r / (6r + 6q).
    Bootstrap over players for the spread (400 draws)."""
    import random
    rng = random.Random(7)

    def solve(vi, vs, yi, ys):
        a = (vi + vs) / 12.0
        sw = vi - 3 * a
        r = (yi - sw) / 3.0
        q = (ys + sw - 3 * r) / 6.0
        year = 6 * r + 6 * q
        return {"swing": sw, "per_step_in_season": r, "per_step_off_season": q, "year": year,
                "in_season_share": 6 * r / year if abs(year) > 1e-9 else None}

    mean = lambda rows: statistics.fmean(c[key] for c in rows)
    out = {}
    vets_i, vets_s = inseason.get("veterans 26-30", []), summer.get("veterans 26-30", [])
    groups = {"first year": ["first year"], "second year": ["second year"],
              "first and second year": ["first year", "second year"]}
    for label, names in groups.items():
        yi = [c for n in names for c in inseason.get(n, [])]
        ys = [c for n in names for c in summer.get(n, [])]
        if not (yi and ys and vets_i and vets_s):
            continue
        point = solve(mean(vets_i), mean(vets_s), mean(yi), mean(ys))
        shares, years = [], []
        for _ in range(draws):
            pick = lambda rows: [rows[rng.randrange(len(rows))] for _ in rows]
            b = solve(mean(pick(vets_i)), mean(pick(vets_s)), mean(pick(yi)), mean(pick(ys)))
            if b["in_season_share"] is not None and b["year"] > 0:
                shares.append(b["in_season_share"])
            years.append(b["year"])
        shares.sort()
        years.sort()
        point = {k: round(v, 3) for k, v in point.items() if v is not None}
        point["share_80pct_range"] = [round(shares[int(0.1 * len(shares))], 2), round(shares[int(0.9 * len(shares))], 2)]
        point["year_80pct_range"] = [round(years[int(0.1 * len(years))], 2), round(years[int(0.9 * len(years))], 2)]
        out[label] = point
    return out


def sim_tables(dirs: list[Path]) -> dict:
    """Simulated in-season change for first-year (the 2026 class) and older young players, pooled over probes."""
    groups = defaultdict(list)
    for d in dirs:
        timeline = json.loads((d / "rookies.json").read_text())["timeline"]
        starts = [e for e in timeline if e["phase"] == "regular_season"]
        for season_start in sorted({e["date"][:4] for e in starts if e["date"][5:7] >= "10"}):
            year = int(season_start)
            steps = [e for e in timeline if f"{year}-10-15" <= e["date"] <= f"{year + 1}-04-13"]
            if len(steps) < 3:
                continue
            # The probe step nearest the middle of the regular season (real seasons split about January 20-25).
            mid = min(steps, key=lambda e: abs((int(e["date"][5:7]) - 1) * 31 + int(e["date"][8:]) - 22)
                      if e["date"][:4] == str(year + 1) else 999)
            last = steps[-1]
            for key in ("rookies", "young", "vets"):
                for pid, r in (last.get(key) or {}).items():
                    try:
                        exp = None if key == "vets" else year - int(r.get("draft_year") or 2026) + 1
                    except ValueError:
                        continue
                    def tot(entry):
                        s = ((entry.get(key) or {}).get(pid) or {}).get("stats") or {}
                        return {"g": float(s.get("games") or 0), "min": float(s.get("minutes") or 0),
                                "pts": float(s.get("points") or 0), "reb": float(s.get("rebounds") or 0),
                                "ast": float(s.get("assists") or 0), "stl": float(s.get("steals") or 0),
                                "blk": float(s.get("blocks") or 0), "tov": float(s.get("turnovers") or 0),
                                "fga": float(s.get("fga") or 0), "fta": float(s.get("fta") or 0),
                                "f3a": float(s.get("fg3a") or 0)}
                    m, z = tot(mid), tot(last)   # season totals start at zero each season
                    t1 = dict(m)
                    t2 = {k: z[k] - m[k] for k in z}
                    if t1["min"] < MIN_HALF or t2["min"] < MIN_HALF or not t1["g"] or not t2["g"]:
                        continue
                    mpg = (t1["min"] + t2["min"]) / (t1["g"] + t2["g"])
                    groups[cohort(exp)].append(change(rates(t1, mpg, volume(t1, t2)), rates(t2, mpg, volume(t1, t2))))
    return {k: summarize(v) for k, v in groups.items()}


def show(title: str, table: dict) -> None:
    print(f"\n{title}")
    print(f"  {'group':16s} {'n':>4s} {'pts36':>6s} {'(vol':>6s} {'eff)':>6s} {'reb36':>6s} {'ast36':>6s} {'stl36':>6s} "
          f"{'blk36':>6s} {'tov36':>6s} {'TS':>6s} {'shots':>6s} {'mpg':>6s} {'box':>6s} {'skill':>6s}")
    for group in ("first year", "first, team <.400", "first, team .400+", "second year", "third year",
                  "veterans 26-30"):
        row = table.get(group)
        if not row:
            continue
        m = lambda k: row[k]["mean"]
        print(f"  {group:16s} {row['n']:4d} {m('pts'):+6.2f} {m('pts_from_volume'):+6.2f} {m('pts_from_efficiency'):+6.2f} "
              f"{m('reb'):+6.2f} {m('ast'):+6.2f} {m('stl'):+6.2f} {m('blk'):+6.2f} {m('tov'):+6.2f} "
              f"{m('ts'):+6.3f} {m('shots'):+6.2f} {m('mpg'):+6.2f} {m('box'):+6.2f} {m('box_skill'):+6.2f}")
        print(f"  {'  median':16s} {'':4s} {row['pts']['median']:+6.2f} {'':6s} {'':6s} {row['reb']['median']:+6.2f} "
              f"{row['ast']['median']:+6.2f} {'':6s} {'':6s} {'':6s} {row['ts']['median']:+6.3f} "
              f"{row['shots']['median']:+6.2f} {row['mpg']['median']:+6.2f} {row['box']['median']:+6.2f} "
              f"{row['box_skill']['median']:+6.2f}   (se: pts {row['pts']['se']}, box {row['box']['se']}, "
              f"skill {row['box_skill']['se']})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", type=Path, nargs="*")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    real = real_tables(real_panel())
    show("REAL in-season change (second half minus first half; means, per 36 unless noted)", real["in_season"])
    show("REAL summer change (next season's first half minus this season's second half)", real["summer"])
    for name, title in (("timing", "box impact at fixed minutes and shot volume"),
                        ("timing_box", "box impact at fixed minutes"), ("timing_points", "points per 36")):
      print(f"\nWhen in the year young players improve ({title}):")
      for label, t in real[name].items():
        print(f"  {label:22s} in-season share {t.get('in_season_share')} (80% range {t['share_80pct_range']}); "
              f"yearly gain {t['year']:+.2f} (80% range {t['year_80pct_range']}); per step in season "
              f"{t['per_step_in_season']:+.3f}, off season {t['per_step_off_season']:+.3f}; seasonal swing {t['swing']:+.2f}")
    out = {"real": real}
    if args.sim:
        sim = sim_tables(args.sim)
        show("SIMULATED in-season change", sim)
        out["sim"] = sim
    if args.json:
        args.json.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
