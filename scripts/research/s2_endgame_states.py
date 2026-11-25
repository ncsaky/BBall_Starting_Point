#!/usr/bin/env python3
"""Stage 2 end-of-game states against real play-by-play (S2-FINISHES, part 1).

Replays (or generates) 2025-26 games and records, with exactly the definitions of `s2_endgame_pbp.py`: the state at the
first 4th-quarter possession starting with 300 / 180 / 120 / 60 / 24 seconds or less left (margin from the side of the
team with the ball), the regulation-end margin and the transitions between them. Prints the comparison with the real
file (output/s2finishes/endgame_pbp_real.json).

    PYTHONPATH=src .venv/bin/python scripts/research/s2_endgame_states.py --runs 4 [--limit 600] [--tag x] \
        [loop.KEY=V ...] [coach.KEY=V ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "output" / "s2finishes"
CHECKS = (300, 180, 120, 60, 24)


def band(m: int) -> str:
    a = abs(m)
    if a == 0:
        return "ot"
    if a <= 3:
        return "1_3"
    if a <= 5:
        return "4_5"
    if a <= 8:
        return "6_8"
    if a <= 12:
        return "9_12"
    return "13+"


def tband(t: float) -> str | None:
    return "0_24" if t <= 24 else "24_60" if t <= 60 else "60_120" if t <= 120 else "120_300" if t <= 300 else None


def mband(m: int) -> str:
    return ("-11" if m <= -11 else "-10_-7" if m <= -7 else "-6_-4" if m <= -4 else "-3_-1" if m <= -1 else "0" if m == 0
            else "1_3" if m <= 3 else "4_6" if m <= 6 else "7_10" if m <= 10 else "11+")


def summarize(shares: dict, trans: dict, reg: Counter, n: int) -> dict:
    out = {"games": n, "regulation_margin": {b: round(v / n, 4) for b, v in sorted(reg.items())}}
    for c in CHECKS:
        dist = shares[str(c)]
        tot = sum(dist.values()) or 1
        w = lambda k: sum(v for m, v in dist.items() if abs(int(m)) <= k) / tot  # noqa: E731
        out[f"within_at_{c}"] = {"3": round(w(3), 4), "5": round(w(5), 4), "10": round(w(10), 4)}
    for c in (120, 60, 24):
        tr = trans[str(c)]
        close = [tr.get(str(k), {}) for k in range(-3, 4)]
        tot = sum(sum(v.values()) for v in close) or 1
        out[f"from_within_3_at_{c}"] = {b: round(sum(v.get(b, 0) for v in close) / tot, 4)
                                        for b in ("ot", "1_3", "4_5", "6_8")}
        rows = {}
        for k in range(-6, 7):
            v = tr.get(str(k), {})
            t = sum(v.values())
            if t:
                rows[str(k)] = {"n": t, **{b: round(v.get(b, 0) / t, 3) for b in ("ot", "1_3", "4_5")}}
        out[f"by_margin_at_{c}"] = rows
    return out


def real_summary(path: Path) -> dict:
    d = json.loads(path.read_text())
    reg = Counter({b: v * d["games"] for b, v in d["regulation_margin"].items()})
    return summarize(d["margin_at_check"], d["transitions"], reg, d["games"])


def measure(ctx, ids, runs: int, seed: int, mode: str = "replay-real-minutes") -> dict:
    """Plays every game `runs` times and returns the Stage 2 summary (states, transitions, late possessions)."""
    from nba_gm_data.sim import sim_game_with_context
    from nba_gm_data.stage2 import game as G
    state: dict = {}
    orig = G.Game.possession

    poss_table: dict = {}

    def tally(team):
        f3 = fta = tov = 0
        for st in team.stats:
            f3 += st[G.S_3PA]
            fta += st[G.S_FTA]
            tov += st[G.S_TOV]
        return f3, fta, tov

    def possession(self, off, de, start):
        rec = state.get(id(self))
        if rec is None:
            rec = state[id(self)] = {"s": {}, "game": self}
        if self.period != 4:
            return orig(self, off, de, start)
        t = self.t_left
        m = off.points - de.points
        for c in CHECKS:
            if c not in rec["s"] and t <= c:
                rec["s"][c] = (m, off is self.home)
        if t > 300:
            return orig(self, off, de, start)
        p0, before = off.points, tally(off)
        res = orig(self, off, de, start)
        after = tally(off)
        keys = [f"{tband(t)}|{mband(m)}"]
        if t <= 60 and -3 <= m <= 0:
            keys.append(f"x{tband(t)}|{m}")
        for key in keys:
            row = poss_table.setdefault(key, [0, 0.0, 0, 0, 0, 0])
            row[0] += 1
            row[1] += t - self.t_left
            row[2] += off.points - p0
            for k in range(3):
                row[3 + k] += after[k] - before[k]
        return res

    G.Game.possession = possession
    shares = {str(c): Counter() for c in CHECKS}
    trans = {str(c): defaultdict(Counter) for c in CHECKS}
    reg = Counter()
    n = 0
    t0 = time.time()
    for gid in ids:
        for r in range(runs):
            state.clear()
            sim_game_with_context(ctx, gid, mode=mode, seed=seed + r, engine="stage2")
            rec = next(iter(state.values()), None)
            if rec is None or 60 not in rec["s"]:
                continue
            g = rec["game"]
            reg_home = 0 if g.period > 4 else g.home.points - g.away.points
            n += 1
            reg[band(reg_home)] += 1
            for c, (m, home_off) in rec["s"].items():
                shares[str(c)][str(max(-15, min(15, m)))] += 1
                reg_off = reg_home if home_off else -reg_home
                trans[str(c)][str(max(-8, min(8, m)))][band(reg_off)] += 1
    sim = summarize(shares, {c: {k: dict(v) for k, v in t.items()} for c, t in trans.items()}, reg, n)
    sim["late_possessions"] = {k: {"n": v[0], "secs": round(v[1] / v[0], 2), "pts": round(v[2] / v[0], 3),
                                   "fg3a": round(v[3] / v[0], 3), "fta": round(v[4] / v[0], 3),
                                   "tov": round(v[5] / v[0], 3)} for k, v in sorted(poss_table.items())}
    sim["seconds"] = round(time.time() - t0, 1)
    G.Game.possession = orig
    return sim


def install_table(table: dict) -> None:
    """A candidate late-game table (s2_finishes_fit.py): cells, the 24-60 s take-foul rates, the hold chance."""
    from nba_gm_data.stage2 import finishes as FIN, game as G
    FIN.install({k: tuple(v) for k, v in table["cells"].items()}, table.get("exact", {}))
    FIN.TAKE_24_60 = table.get("take_24_60")
    for key in ("end_last_shot_behind", "late_runout", "late_concede"):
        if key in table:
            G.LOOP[key] = table[key]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--mode", default="replay-real-minutes")
    ap.add_argument("--tag", default="")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--table", default=None, help="a candidate late-game table (JSON from s2_finishes_fit.py)")
    args, rest = ap.parse_known_args()
    from nba_gm_data.stage2 import coach as C, game as G, screens as S
    applied = {}
    for a in rest:
        key, value = a.split("=", 1)
        table, name = key.split(".", 1)
        {"loop": G.LOOP, "coach": C.COACH, "screens": S.SCREENS}[table][name] = float(value)
        applied[key] = float(value)
    if args.table:
        install_table(json.loads(Path(args.table).read_text()))
    from nba_gm_data.sim import load_sim_context, validation_game_ids
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    if args.limit:
        ids = ids[:: max(1, len(ids) // args.limit)][:args.limit]
    sim = measure(ctx, ids, args.runs, args.seed, args.mode)
    sim["overrides"] = applied
    real = real_summary(OUT / "endgame_pbp_real.json")
    real["late_possessions"] = json.loads((OUT / "endgame_pbp_real.json").read_text())["late_possessions"]
    print(f"games {sim['games']}  ({sim['seconds']} s)  overrides {applied}")
    r26 = json.loads((OUT / "endgame_pbp_real.json").read_text())["per_season"]["2026"]["regulation_margin"]
    print("2025-26 only        " + "  ".join(f"{b} {r26.get(b, 0):.3f}" for b in ("ot", "1_3", "4_5", "6_8", "9_12", "13+")))
    print("regulation margin   " + "  ".join(f"{b} {real['regulation_margin'].get(b, 0):.3f}/{sim['regulation_margin'].get(b, 0):.3f}"
                                         for b in ("ot", "1_3", "4_5", "6_8", "9_12", "13+")) + "   (real/sim)")
    for c in CHECKS:
        rw, sw = real[f"within_at_{c}"], sim[f"within_at_{c}"]
        print(f"within at {c:>3}s: " + "  ".join(f"<={k} {rw[k]:.3f}/{sw[k]:.3f}" for k in ("3", "5", "10")))
    for c in (120, 60, 24):
        rf, sf = real[f"from_within_3_at_{c}"], sim[f"from_within_3_at_{c}"]
        print(f"from within 3 at {c:>3}s: " + "  ".join(f"{b} {rf[b]:.3f}/{sf[b]:.3f}" for b in rf))
    if args.verbose:
        print("late possessions (time left | offense margin): real/sim  seconds, points, threes, free throws, turnovers")
        for tb in ("120_300", "60_120", "24_60", "0_24"):
            for mb in ("-10_-7", "-6_-4", "-3_-1", "0", "1_3", "4_6", "7_10", "x-3", "x-2", "x-1"):
                k = f"x{tb}|{mb[1:]}" if mb.startswith("x") else f"{tb}|{mb}"
                r, s_ = real["late_possessions"].get(k), sim["late_possessions"].get(k)
                if r and s_:
                    print(f"  {k:<16} " + "  ".join(f"{q} {r[q]:.2f}/{s_[q]:.2f}" for q in ("secs", "pts", "fg3a", "fta", "tov")))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"endgame_states{'_' + args.tag if args.tag else ''}.json").write_text(json.dumps({"sim": sim, "real": real}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
