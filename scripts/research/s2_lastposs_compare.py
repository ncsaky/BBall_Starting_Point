#!/usr/bin/env python3
"""Compare Stage 2's last possessions with real ones (S2-LAST-POSSESSION).

    .venv/bin/python scripts/research/s2_lastposs_compare.py output/s2last/sim_base.json [--seasons 2024,2025]
        [--detail] [--json out.json]

Prints, from the real file output/s2last/lastposs_real.json (seasons chosen with --seasons; the fit seasons by default)
and a Stage 2 file from s2_lastposs_sim.py:
1. how 4th quarters end from the state at the first possession with 24 (and 60) seconds or less left: overtime, 1-3,
   4-5 and 6+ point regulation margins, for games within three points and by the exact margin;
2. per possession, by time left (the last 10 s, 10-24 s, 24-60 s) and the offense's exact margin: points scored
   (0 / 1 / 2 / 3 / 4+), seconds, deliberate fouls, threes tried and made, free throws, turnovers;
3. end-of-quarter shots in the 1st-3rd quarters (per game, made share).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "output" / "s2last" / "lastposs_real.json"


def rows(d, seasons=None):
    c = d["cols"]
    out = []
    for r in d["poss"]:
        rec = dict(zip(c, r))
        if seasons and rec["season"] not in seasons:
            continue
        out.append(rec)
    return out


def band(m: int) -> str:
    a = abs(m)
    return "ot" if a == 0 else "1_3" if a <= 3 else "4_5" if a <= 5 else "6+"


def first_states(recs, check: float):
    """game -> (m, reg) at the first 4th-quarter possession starting with `check` seconds or less left."""
    out = {}
    for r in recs:
        if r["period"] != 4 or r["t"] > check:
            continue
        g = r["game"]
        if g not in out or r["t"] > out[g][2]:
            out[g] = (r["m"], r["reg"], r["t"])
    return out


def endings(recs, check):
    st = first_states(recs, check)
    by_m = defaultdict(Counter)
    for m, reg, _ in st.values():
        by_m[max(-8, min(8, m))][band(reg)] += 1
    close = Counter()
    for k in range(-3, 4):
        close.update(by_m[k])
    return by_m, close, len(st)


def tb(t: float) -> str:
    return "0_10" if t <= 10 else "10_24" if t <= 24 else "24_60"


def per_poss(recs, periods=(4,)):
    agg = defaultdict(lambda: Counter())
    for r in recs:
        if r["period"] not in periods and not (5 in periods and r["period"] >= 5):
            continue
        if abs(r["m"]) > 8 or r["t"] > 60:
            continue
        a = agg[tb(r["t"]), r["m"]]
        a["n"] += 1
        a[f"p{min(4, r['pts'])}"] += 1
        for k in ("secs", "pts", "take", "f3a", "f3m", "fta", "ftm", "tov", "fga", "fgm", "sfoul"):
            a[k] += r[k]
    return agg


def fmt_end(name, real, sim):
    rt, st = sum(real.values()) or 1, sum(sim.values()) or 1
    return f"{name:<10} n {rt:5d}/{st:6d}  " + "  ".join(
        f"{b} {real[b] / rt:.3f}/{sim[b] / st:.3f}" for b in ("ot", "1_3", "4_5", "6+"))


def summary(recs):
    out = {}
    for c in (60, 24):
        by_m, close, n = endings(recs, c)
        tot = sum(close.values()) or 1
        out[f"within3_at_{c}"] = {b: round(close[b] / tot, 4) for b in ("ot", "1_3", "4_5", "6+")}
        out[f"within3_share_{c}"] = round(tot / max(1, n), 4)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sim")
    ap.add_argument("--seasons", default="2024,2025")
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    seasons = {int(s) for s in args.seasons.split(",")}
    real_d = json.loads(REAL.read_text())
    sim_d = json.loads(Path(args.sim).read_text())
    real, sim = rows(real_d, seasons), rows(sim_d)
    print(f"real seasons {sorted(seasons)}; sim {args.sim} overrides {sim_d.get('overrides')}")
    # regulation endings over all games
    rg = Counter(band(v[1]) for g, v in real_d["games"].items() if v[0] in seasons)
    sg = Counter(band(v[1]) for v in sim_d["games"].values())
    print(fmt_end("all games", rg, sg))
    for c in (60, 24):
        rb, rc, rn = endings(real, c)
        sb, sc, sn = endings(sim, c)
        print(f"-- from the first possession with {c} s or less (within 3: {sum(rc.values()) / rn:.3f}/"
              f"{sum(sc.values()) / sn:.3f} of games)")
        print(fmt_end("within 3", rc, sc))
        if args.detail:
            for k in range(-6, 7):
                print(fmt_end(f"m {k:+d}", rb[k], sb[k]))
    ra, sa = per_poss(real), per_poss(sim)
    print("-- per possession, 4th quarter (real/sim): n, P(0 1 2 3 4+ points), secs, deliberate fouls, 3PA, 3P%, FTA, tov")
    for t in ("24_60", "10_24", "0_10"):
        for m in range(-6, 7):
            r, s = ra.get((t, m)), sa.get((t, m))
            if not r or not s or r["n"] < 25:
                continue
            rn, sn = r["n"], s["n"]
            dist = " ".join(f"{r[f'p{k}'] / rn:.2f}/{s[f'p{k}'] / sn:.2f}" for k in range(5))
            p3 = lambda a: a["f3m"] / a["f3a"] if a["f3a"] else 0  # noqa: E731
            print(f"{t:>5} {m:+d} n {rn:4d}/{sn:5d} | {dist} | s {r['secs'] / rn:4.1f}/{s['secs'] / sn:4.1f} "
                  f"take {r['take'] / rn:.2f}/{s['take'] / sn:.2f} 3a {r['f3a'] / rn:.2f}/{s['f3a'] / sn:.2f} "
                  f"3% {p3(r):.2f}/{p3(s):.2f} fta {r['fta'] / rn:.2f}/{s['fta'] / sn:.2f} tov {r['tov'] / rn:.2f}/{s['tov'] / sn:.2f}")
    # overtime
    ro = Counter(v[3] > 4 for g, v in real_d["games"].items() if v[0] in seasons)
    so = Counter(v[3] > 4 for v in sim_d["games"].values())
    print(f"-- games to overtime {ro[True] / sum(ro.values()):.4f}/{so[True] / sum(so.values()):.4f}; "
          f"2+ overtimes {sum(1 for v in real_d['games'].values() if v[0] in seasons and v[3] > 5) / sum(ro.values()):.4f}/"
          f"{sum(1 for v in sim_d['games'].values() if v[3] > 5) / sum(so.values()):.4f}")
    rh = [h for h in real_d["heaves"] if h[0] in seasons]
    ng_r, ng_s = sum(ro.values()), sum(so.values())
    far = [h for h in rh if h[3] is not None and h[3] >= 30]
    print(f"-- end-of-quarter shots (Q1-Q3, last 3 s) per game: real {len(rh) / ng_r:.2f} (made {sum(h[4] for h in rh) / max(1, len(rh)):.3f}; "
          f"30+ ft {len(far) / ng_r:.2f}, made {sum(h[4] for h in far) / max(1, len(far)):.3f}) | sim {len(sim_d['heaves']) / ng_s:.2f} "
          f"(made {sum(h[3] for h in sim_d['heaves']) / max(1, len(sim_d['heaves'])):.3f}; heaves "
          f"{sum(1 for h in sim_d['heaves'] if h[2] == 'heave') / ng_s:.2f}, made "
          f"{sum(h[3] for h in sim_d['heaves'] if h[2] == 'heave') / max(1, sum(1 for h in sim_d['heaves'] if h[2] == 'heave')):.3f})")
    if args.json:
        Path(args.json).write_text(json.dumps({"real": summary(real), "sim": summary(sim)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
