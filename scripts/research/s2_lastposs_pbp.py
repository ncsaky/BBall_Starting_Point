#!/usr/bin/env python3
"""Real last possessions from public play-by-play (S2-LAST-POSSESSION, part 1).

Reads the rotation study's public play-by-play archive (github.com/ramirobentes/nba_data, release "pbp"; regular
seasons 2023-24 to 2025-26; the same files as s2_endgame_pbp.py) and writes one row per possession that starts with 300
seconds or less left in the 4th quarter or an overtime, with the exact score from the side of the team with the ball:

    season, game, period, t (seconds left at the start), m (offense margin), secs, pts, fga, fgm, f3a, f3m, fta, ftm,
    tov, take (deliberate / non-shooting fouls by the defense), sfoul (shooting fouls by the defense), reg (the period's
    final margin from the offense's side; 0 = another overtime follows)

plus, for the 1st-3rd quarters, every field-goal try in the last three seconds (distance and make), the end-of-quarter
heaves. 2023-24 and 2024-25 are the fit seasons, 2025-26 the check season.

    uv run --no-project --python 3.12 --with duckdb==2.0.1 python -I scripts/research/s2_lastposs_pbp.py \
        output/rotation-evidence output/s2last/lastposs_real.json
"""
from __future__ import annotations

import json
import sys
from itertools import groupby
from pathlib import Path

import duckdb

SEASONS = (2024, 2025, 2026)


def clock_seconds(text):
    if not text:
        return None
    m, s = text.split(":")
    return int(m) * 60 + float(s)


def period_rows(rows, home):
    """Possessions (start clock, events) of one period, grouped like s2_endgame_pbp.game_states."""
    groups = []
    for r in rows:
        st = clock_seconds(r[2])
        if st is None:
            if groups:
                groups[-1][1].append(r)
            continue
        if not groups or st != groups[-1][0]:
            groups.append((st, [r]))
        else:
            groups[-1][1].append(r)
    return groups


def last_minute(season, gid, period, rows, home):
    """rows: (period, clock, start_poss, off_team, hs, vs, msg_type, act_type, team_abb, description) in order."""
    groups = period_rows([(r[0], r[1], r[2], *r[3:]) for r in rows], home)
    out = []
    score = None
    end = rows[-1]
    end_home = int(end[4] - end[5])
    for gi, (st, evs) in enumerate(groups):
        offs = [e[3] for e in evs if e[3] is not None]
        if score is None:
            score = next(((e[4], e[5]) for e in evs if e[4] is not None and e[5] is not None), (0, 0))
        start = score
        for e in evs:
            if e[4] is not None and e[5] is not None:
                score = (e[4], e[5])
        if not offs or st > 300:
            continue
        off = offs[-1]
        is_home = off == home
        m = int(start[0] - start[1]) if is_home else int(start[1] - start[0])
        end_t = groups[gi + 1][0] if gi + 1 < len(groups) else 0.0
        pts = int((score[0] - start[0]) if is_home else (score[1] - start[1]))
        fga = fgm = f3a = f3m = fta = ftm = tov = take = sfoul = 0
        for e in evs:
            mt, at, team, desc = e[6], e[7], e[8], (e[9] or "")
            if team == off:
                if mt in (1, 2):
                    fga += 1
                    three = "3pt" in desc.lower()
                    f3a += three
                    if mt == 1:
                        fgm += 1
                        f3m += three
                elif mt == 3:
                    fta += 1
                    ftm += "miss" not in desc.lower()
                elif mt == 5:
                    tov += 1
            elif team is not None and mt == 6:
                if at == 2:
                    sfoul += 1
                elif at in (1, 28, 31):
                    take += 1
        reg = end_home if is_home else -end_home
        out.append((season, gid, period, round(st, 1), m, round(st - end_t, 1), pts, fga, fgm, f3a, f3m, fta, ftm, tov,
                    take, sfoul, reg))
    return out


def main() -> int:
    cache = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    con = duckdb.connect()
    poss, heaves = [], []
    games = {}
    for season in SEASONS:
        f = cache / f"pbp_regular_{season}.parquet"
        q = f"""SELECT game_id, period::int, clock, start_poss, off_team_abb, hs::int, vs::int, msg_type::int,
                       act_type::int, team_abb, description, team_home, shot_distance
                FROM read_parquet('{f}') ORDER BY game_date, game_id, number_event, event_num, "order" """
        cur = con.execute(q)
        batches = iter(lambda: cur.fetchmany(8192), [])
        stream = (r for b in batches for r in b)
        n = 0
        for gid, grp in groupby(stream, key=lambda r: r[0]):
            rows = list(grp)
            home = rows[0][11]
            periods = max(r[1] for r in rows)
            if periods < 4:
                continue
            n += 1
            q4 = [r for r in rows if r[1] == 4]
            reg_end = int(q4[-1][5] - q4[-1][6])
            fin = int(rows[-1][5] - rows[-1][6])
            games[gid] = (season, reg_end, fin, periods)
            for p in range(4, periods + 1):
                pr = [r[1:11] for r in rows if r[1] == p]
                if pr:
                    poss.extend(last_minute(season, gid, p, pr, home))
            for p in (1, 2, 3):
                for r in rows:
                    if r[1] == p and r[7] in (1, 2):
                        t = clock_seconds(r[2])
                        if t is not None and t <= 3.0:
                            heaves.append((season, p, t, r[12], int(r[7] == 1), int("3pt" in (r[10] or "").lower())))
        print(season, n, "games", file=sys.stderr)
    cols = ["season", "game", "period", "t", "m", "secs", "pts", "fga", "fgm", "f3a", "f3m", "fta", "ftm", "tov",
            "take", "sfoul", "reg"]
    out = {"source": "github.com/ramirobentes/nba_data release pbp, regular seasons 2023-24..2025-26",
           "cols": cols, "poss": poss, "heave_cols": ["season", "period", "t", "dist", "made", "three"],
           "heaves": heaves, "games": {g: list(v) for g, v in games.items()}}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, separators=(",", ":")))
    print(len(poss), "possessions,", len(heaves), "end-of-quarter shots,", len(games), "games")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
