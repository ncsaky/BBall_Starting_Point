#!/usr/bin/env python3
"""Real end-of-game states from public play-by-play (S2-FINISHES, part 1).

Reads the rotation study's public play-by-play archive (github.com/ramirobentes/nba_data, release "pbp"; the regular
seasons 2023-24 to 2025-26, checksums in data/research/rotation_evidence.json) and records, for every 4th quarter:

* the state at the first possession that starts with 300 / 180 / 120 / 60 / 24 seconds or less left: the margin from
  the side of the team with the ball, and the time left when that possession started;
* the margin at the end of regulation (0 = overtime) and the final margin;
* the regulation-end margin given the state at each checkpoint (the transitions the engine's end of game must match).

Run with the research environment (DuckDB reads Parquet; the game itself needs nothing):

    uv run --no-project --python 3.12 --with duckdb==2.0.1 python -I scripts/research/s2_endgame_pbp.py \
        output/rotation-evidence output/s2finishes/endgame_pbp_real.json

The output is a compact JSON of counts; `s2_endgame_states.py` measures the same things on Stage 2 games.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from itertools import groupby
from pathlib import Path

import duckdb

CHECKS = (300, 180, 120, 60, 24)
SEASONS = (2024, 2025, 2026)
FIT_SEASONS = (2024, 2025)


def clock_seconds(text: str | None) -> float | None:
    if not text:
        return None
    m, s = text.split(":")
    return int(m) * 60 + float(s)


def tband(t: float) -> str:
    return "0_24" if t <= 24 else "24_60" if t <= 60 else "60_120" if t <= 120 else "120_300" if t <= 300 else None


def mband(m: int) -> str:
    return ("-11" if m <= -11 else "-10_-7" if m <= -7 else "-6_-4" if m <= -4 else "-3_-1" if m <= -1 else "0" if m == 0
            else "1_3" if m <= 3 else "4_6" if m <= 6 else "7_10" if m <= 10 else "11+")


def game_states(rows):
    """rows: (period, clock, off_team, start_poss, hs, vs, team_home, msg_type, team_abb, description) in event order
    for one game."""
    home = rows[0][6]
    q4 = [r for r in rows if r[0] == 4]
    if not q4:
        return None
    # Group the quarter's events into possessions by their start clock (start_poss). The team with the ball is the
    # one the group's later events name: in the 2023-24 and 2024-25 files the first row of a possession (usually the
    # defensive rebound) still names the previous offense.
    groups = []
    for r in q4:
        st = clock_seconds(r[3])
        if st is None:
            if groups:
                groups[-1][1].append(r)
            continue
        if not groups or st != groups[-1][0]:
            groups.append((st, [r]))
        else:
            groups[-1][1].append(r)
    states = {}
    poss = []          # last 5 minutes: (t_start, m_off, seconds, points, fg3a, fta, tov)
    score = None
    for gi, (st, evs) in enumerate(groups):
        offs = [e[2] for e in evs if e[2] is not None]
        if score is None:
            score = next(((e[4], e[5]) for e in evs if e[4] is not None and e[5] is not None), (0, 0))
        start_score = score
        for e in evs:
            if e[4] is not None and e[5] is not None:
                score = (e[4], e[5])
        if not offs:
            continue
        off = offs[-1]
        is_home = off == home
        margin = start_score[0] - start_score[1]
        m_off = margin if is_home else -margin
        for c in CHECKS:
            if c not in states and st <= c:
                states[c] = {"t": st, "m_off": m_off, "m_home": margin}
        if st <= 300:
            end_t = groups[gi + 1][0] if gi + 1 < len(groups) else 0.0
            pts = (score[0] - start_score[0]) if is_home else (score[1] - start_score[1])
            f3 = sum(1 for e in evs if e[8] == off and e[7] in (1, 2) and e[9] and "3pt" in e[9].lower())
            fta = sum(1 for e in evs if e[8] == off and e[7] == 3)
            tov = sum(1 for e in evs if e[8] == off and e[7] == 5)
            poss.append((st, m_off, round(st - end_t, 2), pts, f3, fta, tov))
    end4 = q4[-1]
    reg = int(end4[4] - end4[5])
    last = rows[-1]
    final = int(last[4] - last[5])
    periods = max(r[0] for r in rows)
    return {"states": states, "reg_margin": reg, "final": final, "ot": periods > 4, "poss": poss}


def add_poss(table, poss):
    for t, m, secs, pts, f3, fta, tov in poss:
        keys = [f"{tband(t)}|{mband(m)}"]
        if t <= 60 and -3 <= m <= 0:
            keys.append(f"x{tband(t)}|{m}")      # exact deficits in the last minute (tying vs winning shots)
        for key in keys:
            row = table.setdefault(key, [0, 0.0, 0, 0, 0, 0])
            row[0] += 1
            row[1] += secs
            row[2] += pts
            row[3] += f3
            row[4] += fta
            row[5] += tov


def poss_summary(table):
    return {k: {"n": v[0], "secs": round(v[1] / v[0], 2), "pts": round(v[2] / v[0], 3), "fg3a": round(v[3] / v[0], 3),
                "fta": round(v[4] / v[0], 3), "tov": round(v[5] / v[0], 3)} for k, v in sorted(table.items())}


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


def main() -> int:
    cache = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    con = duckdb.connect()
    per_season = {}
    trans = {c: defaultdict(Counter) for c in CHECKS}  # check -> m_off (clipped) -> regulation band from offense side
    trans_signed = {c: defaultdict(Counter) for c in CHECKS}  # check -> m_off -> signed reg margin (offense side)
    shares = {c: Counter() for c in CHECKS}
    total = 0
    final_bands = Counter()
    poss_table = {}
    poss_fit = {}       # the rotation study's fit seasons (2023-24, 2024-25); 2025-26 is the check season
    poss_check = {}
    check_shares = {c: Counter() for c in CHECKS}
    for season in SEASONS:
        f = cache / f"pbp_regular_{season}.parquet"
        q = f"""SELECT game_id, period::int, clock, off_team_abb, start_poss, hs::int, vs::int, team_home,
                       msg_type::int, team_abb, description
                FROM read_parquet('{f}') ORDER BY game_date, game_id, number_event, event_num, "order" """
        cur = con.execute(q)
        rows = iter(lambda: cur.fetchmany(8192), [])
        stream = (r for batch in rows for r in batch)
        s_games = 0
        s_final = Counter()
        s_close = Counter()
        for gid, grp in groupby(stream, key=lambda r: r[0]):
            g = game_states([r[1:] for r in grp])
            if g is None or 60 not in g["states"]:
                continue
            s_games += 1
            total += 1
            final_bands[band(g["reg_margin"])] += 1
            add_poss(poss_table, g["poss"])
            add_poss(poss_fit if season in FIT_SEASONS else poss_check, g["poss"])
            s_final[band(g["reg_margin"])] += 1
            for c, s in g["states"].items():
                shares[c][max(-15, min(15, s["m_off"]))] += 1
                if season not in FIT_SEASONS:
                    check_shares[c][max(-15, min(15, s["m_off"]))] += 1
                # regulation margin from the side of the team that had the ball at the checkpoint
                reg_off = g["reg_margin"] if s["m_home"] == s["m_off"] else -g["reg_margin"]
                k = max(-8, min(8, s["m_off"]))
                trans[c][k][band(reg_off)] += 1
                trans_signed[c][k][max(-15, min(15, reg_off))] += 1
                if c == 60 and abs(s["m_off"]) <= 3:
                    s_close["within_3_at_60"] += 1
        per_season[season] = {"games": s_games,
                              "regulation_margin": {b: round(v / s_games, 4) for b, v in sorted(s_final.items())},
                              "within_3_at_60": round(s_close["within_3_at_60"] / s_games, 4)}
    out = {
        "source": "github.com/ramirobentes/nba_data release pbp, regular seasons 2023-24..2025-26",
        "games": total,
        "per_season": per_season,
        "regulation_margin": {b: round(v / total, 4) for b, v in sorted(final_bands.items())},
        "margin_at_check": {str(c): {str(k): v for k, v in sorted(shares[c].items())} for c in CHECKS},
        "transitions": {str(c): {str(k): dict(v) for k, v in sorted(trans[c].items())} for c in CHECKS},
        "late_possessions": poss_summary(poss_table),
        "late_possessions_fit": poss_summary(poss_fit),
        "late_possessions_check": poss_summary(poss_check),
        "margin_at_check_2026": {str(c): {str(k): v for k, v in sorted(check_shares[c].items())} for c in CHECKS},
        "transitions_signed": {str(c): {str(k): {str(a): b for a, b in sorted(v.items())}
                                        for k, v in sorted(trans_signed[c].items())} for c in CHECKS},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("games", "per_season", "regulation_margin")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
