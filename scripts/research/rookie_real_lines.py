#!/usr/bin/env python3
"""ROOKIE-FIT-2: real rookie stat lines from Basketball Reference, for checks (no simulation).

Reads pages saved under output/rookie-fit-2/bbref/ (fetched politely: one page every 6 seconds, paths allowed by
basketball-reference.com/robots.txt):
  leagues/NBA_<2016..2027>_rookies.html   every rookie's season totals (2015-16 .. 2026-27 so far)
  leagues/NBA_2027_advanced.html          2026-27 box plus-minus, usage, true shooting, team (rookies kept)
  leagues/NBA_2027.html                   2026-27 team ratings (net rating, record) for team context
and writes data/research/rookie_real_lines.json:
  classes: {season_end: [rookie rows]} with draft pick where Basketball Reference's draft table has him
  season_2027: {as_of, teams, rookies}

    python3 scripts/research/rookie_real_lines.py [--as-of 2026-11-22]
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "output/rookie-fit-2/bbref"
OUT = ROOT / "data/research/rookie_real_lines.json"
NUM = ("g", "mp", "fg", "fga", "fg3", "fg3a", "ft", "fta", "orb", "trb", "ast", "stl", "blk", "tov", "pf", "pts")


def table(text: str, table_id: str) -> list[dict]:
    start = text.find(f'id="{table_id}"')
    if start < 0:
        return []
    body = text[start:text.find("</table>", start)]
    rows = []
    for raw in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = dict(re.findall(r'data-stat="([^"]+)"[^>]*>(.*?)</t[dh]>', raw, re.S))
        if not cells:
            continue
        link = (re.search(r"""href=["']/players/\w/(\w+)\.html["']""", raw)
                or re.search(r"href='/teams/(\w+)/", raw))
        clean = {k: html.unescape(re.sub(r"<[^>]+>", "", v)).strip() for k, v in cells.items()}
        clean["_id"] = link.group(1) if link else None
        rows.append(clean)
    return rows


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rookies(season: int) -> list[dict]:
    text = (PAGES / f"NBA_{season}_rookies.html").read_text(encoding="utf-8", errors="replace")
    out = []
    for row in table(text, "rookies"):
        if not row.get("_id") or not row.get("g", "").isdigit():
            continue
        out.append({"bref_id": row["_id"], "name": row["player"], "age": number(row.get("age")),
                    **{k: number(row.get(k)) or 0.0 for k in NUM}})
    return out


def advanced(season: int) -> dict[str, dict]:
    """A season's advanced table by player id (the season-total row for a traded player)."""
    path = PAGES / f"NBA_{season}_advanced.html"
    if not path.exists():
        return {}
    out = {}
    for row in table(path.read_text(encoding="utf-8", errors="replace"), "advanced"):
        if not row.get("_id") or not row.get("games", "").isdigit():
            continue
        if row["_id"] in out and out[row["_id"]]["team"] in ("TOT", "2TM", "3TM", "4TM"):
            continue
        out[row["_id"]] = {"team": row.get("team_name_abbr"), "gs": number(row.get("games_started")),
                           "name": row.get("name_display"), "adv_mp": number(row.get("mp")),
                           **{k: number(row.get(k)) for k in ("per", "ts_pct", "usg_pct", "obpm", "dbpm", "bpm",
                                                                "ast_pct", "trb_pct", "stl_pct", "blk_pct", "tov_pct")}}
    return out


def totals(season: int) -> dict[str, dict]:
    """A season's totals table by player id (the season-total row for a traded player). The rookies page of a past
    season shows CAREER totals, so a past rookie season's box numbers come from here."""
    path = PAGES / f"NBA_{season}_totals.html"
    out = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    for row in table(text, "totals_stats") or table(text, "totals"):
        games = row.get("games", row.get("g", ""))
        if not row.get("_id") or not games.isdigit():
            continue
        if row["_id"] in out and out[row["_id"]]["team"] in ("TOT", "2TM", "3TM", "4TM"):
            continue
        out[row["_id"]] = {"team": row.get("team_name_abbr"), "g": float(games),
                           **{k: number(row.get(k)) or 0.0 for k in NUM if k != "g"}}
    return out


def draft_picks() -> dict[str, tuple[int, int]]:
    """Player id -> (draft year, pick): Basketball Reference draft pages saved for 2020-2026, plus the older draft
    table already in development_evidence.json."""
    dev = json.loads((ROOT / "data/research/development_evidence.json").read_text())["public_inputs"]
    picks = {pid: (year, pick) for year, pick, pid, _ in dev["draft"]}
    for year in range(2020, 2027):
        path = PAGES / f"draft_NBA_{year}.html"
        if not path.exists():
            continue
        for row in table(path.read_text(encoding="utf-8", errors="replace"), "stats"):
            if row.get("_id") and row.get("pick_overall", "").isdigit():
                picks[row["_id"]] = (year, int(row["pick_overall"]))
    return picks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default="2026-11-22")
    args = parser.parse_args()
    picks = draft_picks()
    classes = {}
    for season in range(2016, 2027):
        adv, tot = advanced(season), totals(season)
        rows = []
        for r in rookies(season):
            if r["bref_id"] not in tot:
                continue
            year, pick = picks.get(r["bref_id"], (None, None))
            r = {"bref_id": r["bref_id"], "name": r["name"], "draft_year": year, "pick": pick,
                 **adv.get(r["bref_id"], {}), **tot[r["bref_id"]]}
            rows.append(r)
        classes[str(season)] = rows
    adv = advanced(2027)
    teams = {}
    text = (PAGES / "NBA_2027.html").read_text(encoding="utf-8", errors="replace")
    for row in table(text, "advanced-team"):
        if row.get("_id") and row.get("wins", "").isdigit():
            teams[row["_id"]] = {"name": row["team"], "wins": int(row["wins"]), "losses": int(row["losses"]),
                                 "net_rtg": number(row.get("net_rtg")), "off_rtg": number(row.get("off_rtg")),
                                 "def_rtg": number(row.get("def_rtg"))}
    current = rookies(2027)
    for r in current:
        r.update(adv.get(r["bref_id"], {}))
        year, pick = picks.get(r["bref_id"], (None, None))
        r["draft_year"], r["pick"] = year, pick
    usage = {a["name"]: a["usg_pct"] for a in advanced(2026).values()
             if a.get("name") and (a.get("adv_mp") or 0) >= 1000 and a.get("usg_pct") is not None}
    out = {"source": "Basketball Reference (basketball-reference.com) rookie, totals, advanced, draft and team pages; "
                     f"fetched {args.as_of}, one page every 6 seconds",
           "classes": classes, "season_2027": {"as_of": args.as_of, "teams": teams, "rookies": current},
           "usage_2025_26": usage}
    OUT.write_text(json.dumps(out, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {sum(len(v) for v in classes.values())} rookie seasons 2016-2026, "
          f"{len(current)} rookies in 2026-27, {len(teams)} teams")


if __name__ == "__main__":
    main()
