#!/usr/bin/env python3
"""ROOKIE-SEASON: do real rebuilding teams play young high picks more than their impact earns? (measurement only)

Real data, 2015-16 .. 2025-26 regular seasons:
  Basketball Reference season advanced pages (output/rookie-fit-2/bbref/NBA_<year>_advanced.html): each player's
    games, minutes and box plus-minus with each team he played for;
  rookie classes with draft pick (data/research/rookie_real_lines.json);
  ESPN standings (output/rookie-season/espn/standings_<year>.json, from rookie_halves_fetch.py): team records.

Method. Within each team-season, players with 10+ games are ranked by a steadied box plus-minus (shrunk toward -2 with
the weight of 400 minutes, so a short hot stretch does not rank a player). Veterans (four or more seasons in the league
by Basketball Reference rookie class, or not in any class since 2015-16) give the minutes a coach hands each rank and
impact level on each kind of team; a young player's "extra minutes" is his minutes per game minus what a veteran of the
same rank and impact gets on the same kind of team. Team kinds by that season's winning share: rebuilding under .400,
contending .580 and up, the rest in between (the previous season's record is also reported).

Writes data/research/rookie_dev_minutes.json and prints the tables.

    python3 scripts/research/rookie_dev_minutes.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import rookie_real_lines as rl  # noqa: E402
from rookie_halves_fetch import norm  # noqa: E402

ESPN = ROOT / "output/rookie-season/espn"
OUT = ROOT / "data/research/rookie_dev_minutes.json"
SEASONS = list(range(2016, 2027))
ESPN_TO_BREF = {"BKN": "BRK", "CHA": "CHO", "PHX": "PHO", "NO": "NOP", "SA": "SAS", "GS": "GSW", "NY": "NYK",
                "UTAH": "UTA", "WSH": "WAS"}
SHRINK_MINUTES = 400.0
SHRINK_TO = -2.0
REBUILD, CONTEND = 0.400, 0.580


def records(year: int) -> dict[str, float]:
    data = json.loads((ESPN / f"standings_{year}.json").read_text())
    out = {}
    for conf in data.get("children", []):
        for entry in conf["standings"]["entries"]:
            stats = {s["name"]: s.get("value") for s in entry["stats"]}
            abbr = entry["team"]["abbreviation"]
            out[ESPN_TO_BREF.get(abbr, abbr)] = float(stats["winPercent"])
    return out


def player_team_rows(year: int) -> list[dict]:
    text = (rl.PAGES / f"NBA_{year}_advanced.html").read_text(encoding="utf-8", errors="replace")
    rows = []
    for row in rl.table(text, "advanced"):
        team = row.get("team_name_abbr")
        if not row.get("_id") or not row.get("games", "").isdigit() or team in ("TOT", "2TM", "3TM", "4TM", "5TM"):
            continue
        mp, g = float(row.get("mp") or 0), float(row["games"])
        try:
            bpm = float(row.get("bpm"))
        except (TypeError, ValueError):
            continue
        rows.append({"id": row["_id"], "name": row.get("name_display"), "team": team, "g": g, "mp": mp, "bpm": bpm,
                     "age": rl.number(row.get("age"))})
    return rows


def kind(win: float) -> str:
    return "rebuilding" if win < REBUILD else "contending" if win >= CONTEND else "middle"


def fit_line(points: list[tuple[float, float, float]]) -> tuple[float, float]:
    """Weighted least squares y = a + b x; points (x, y, w)."""
    sw = sum(w for _, _, w in points)
    mx = sum(x * w for x, _, w in points) / sw
    my = sum(y * w for _, y, w in points) / sw
    sxx = sum(w * (x - mx) ** 2 for x, _, w in points)
    sxy = sum(w * (x - mx) * (y - my) for x, y, w in points)
    b = sxy / sxx if sxx else 0.0
    return my - b * mx, b


def main() -> None:
    classes = json.loads((ROOT / "data/research/rookie_real_lines.json").read_text())["classes"]
    rookie_season, pick = {}, {}
    for season, rows in classes.items():
        for r in rows:
            rookie_season.setdefault(r["bref_id"], int(season))
            if r.get("pick") and r.get("draft_year") == int(season) - 1:
                pick[r["bref_id"]] = int(r["pick"])
    data = []
    for year in SEASONS:
        win = records(year)
        prev = records(year - 1) if (ESPN / f"standings_{year - 1}.json").exists() else {}
        rows = [r for r in player_team_rows(year) if r["g"] >= 10]
        by_team: dict[str, list[dict]] = {}
        for r in rows:
            r["steady"] = (r["bpm"] * r["mp"] + SHRINK_TO * SHRINK_MINUTES) / (r["mp"] + SHRINK_MINUTES)
            by_team.setdefault(r["team"], []).append(r)
        for team, roster in by_team.items():
            if team not in win:
                continue
            roster.sort(key=lambda r: -r["steady"])
            for rank, r in enumerate(roster, 1):
                first = rookie_season.get(r["id"])
                exp = None if first is None else year - first + 1   # 1 = rookie season
                data.append({**r, "year": year, "rank": rank, "win": win[team], "prev_win": prev.get(team),
                             "kind": kind(win[team]), "prev_kind": kind(prev[team]) if team in prev else None,
                             "exp": exp, "pick": pick.get(r["id"]), "mpg": r["mp"] / r["g"]})
    vets = [r for r in data if r["exp"] is None or r["exp"] >= 4]
    young_hi = [r for r in data if r["exp"] in (1, 2) and r["pick"] and r["pick"] <= 10]
    young_any = [r for r in data if r["exp"] in (1, 2, 3) and r["pick"]]
    young_other = [r for r in data if r["exp"] in (1, 2) and not (r["pick"] and r["pick"] <= 10)]

    # Expected minutes per game for a veteran of this rank (1-12) on this kind of team, adjusted for his steadied
    # box plus-minus relative to the average veteran at that rank.
    def expected(r: dict, key: str = "kind") -> float | None:
        group = [v for v in vets if v[key] == r[key] and v["rank"] == min(r["rank"], 12)]
        if len(group) < 30:
            return None
        a, b = fit_line([(v["steady"], v["mpg"], v["g"]) for v in group])
        return a + b * r["steady"]

    out: dict = {"definitions": {"rebuilding": f"win share < {REBUILD}", "contending": f"win share >= {CONTEND}",
                                 "steady_bpm": f"box plus-minus shrunk toward {SHRINK_TO} with {SHRINK_MINUTES:.0f} minutes"},
                 "groups": {}}
    print("Extra minutes per game over a veteran of the same team rank and impact on the same kind of team")
    print("(games-weighted mean; n = player-team seasons with 10+ games)")
    for label, group in (("top-10 picks, years 1-2", young_hi), ("other young players, years 1-2", young_other),
                         ("veterans (check)", vets)):
        for key in ("kind", "prev_kind"):
            row = {}
            for k in ("rebuilding", "middle", "contending"):
                members = [(r, expected(r, key)) for r in group if r[key] == k]
                members = [(r, e) for r, e in members if e is not None]
                if not members:
                    continue
                w = sum(r["g"] for r, _ in members)
                extra = sum((r["mpg"] - e) * r["g"] for r, e in members) / w
                row[k] = {"n": len(members), "extra_mpg": round(extra, 2),
                          "mpg": round(sum(r["mpg"] * r["g"] for r, _ in members) / w, 1),
                          "steady_bpm": round(sum(r["steady"] * r["g"] for r, _ in members) / w, 2),
                          "mean_rank": round(statistics.fmean(r["rank"] for r, _ in members), 1)}
            out["groups"][f"{label} | {key}"] = row
            print(f"  {label:32s} by {'this' if key == 'kind' else 'last'} season's record: " + "; ".join(
                f"{k} n {v['n']} mpg {v['mpg']} steady box {v['steady_bpm']:+.1f} rank {v['mean_rank']} extra {v['extra_mpg']:+.1f}"
                for k, v in row.items()))
    # Minutes against impact lines, top-10 picks years 1-2 vs veterans, by this season's record.
    print("\nMinutes per game at a given steadied box plus-minus (weighted line fits)")
    lines = {}
    for label, group in (("top-10 picks yrs 1-2", young_hi), ("veterans", vets)):
        for k in ("rebuilding", "middle", "contending"):
            members = [r for r in group if r["kind"] == k]
            if len(members) < 15:
                continue
            a, b = fit_line([(r["steady"], r["mpg"], r["g"]) for r in members])
            lines[f"{label} | {k}"] = {"n": len(members), "a": round(a, 2), "b": round(b, 2),
                                       "at": {str(x): round(a + b * x, 1) for x in (-4, -2, 0, 2)}}
            print(f"  {label:22s} {k:11s} n {len(members):4d}: at box -4 / -2 / 0 / +2 -> "
                  + " / ".join(f"{a + b * x:.1f}" for x in (-4, -2, 0, 2)))
    out["lines"] = lines
    # By pick band and year, rebuilding vs contending.
    print("\nTop-10 picks by pick band and season, minutes per game (n): rebuilding vs contending, extra vs veterans")
    bands = {}
    for lo, hi in ((1, 3), (4, 10), (11, 14), (15, 20), (21, 30)):
        for exp in (1, 2, 3):
            cell = {}
            for k in ("rebuilding", "middle", "contending"):
                members = [(r, expected(r)) for r in young_any if lo <= r["pick"] <= hi and r["exp"] == exp and r["kind"] == k]
                members = [(r, e) for r, e in members if e is not None]
                if members:
                    w = sum(r["g"] for r, _ in members)
                    cell[k] = {"n": len(members), "mpg": round(sum(r["mpg"] * r["g"] for r, _ in members) / w, 1),
                               "extra_mpg": round(sum((r["mpg"] - e) * r["g"] for r, e in members) / w, 2)}
            bands[f"picks {lo}-{hi} year {exp}"] = cell
            print(f"  picks {lo}-{hi} year {exp}: " + "; ".join(f"{k} {v['mpg']} ({v['n']}) extra {v['extra_mpg']:+.1f}"
                                                            for k, v in cell.items()))
    out["by_pick_band"] = bands
    # Named recent examples on rebuilding teams.
    examples = sorted((r for r in young_hi if r["kind"] == "rebuilding" and r["year"] >= 2022),
                      key=lambda r: (r["year"], r["pick"]))
    out["examples_rebuilding_recent"] = [
        {k: (round(r[k], 2) if isinstance(r[k], float) else r[k])
         for k in ("name", "year", "team", "pick", "exp", "mpg", "bpm", "steady", "rank", "win")}
        for r in examples]
    OUT.write_text(json.dumps(out, indent=1))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
