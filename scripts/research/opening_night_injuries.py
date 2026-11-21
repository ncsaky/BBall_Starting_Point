"""Who was out injured on the real 2026-27 opening night, why, and for how many games (INJURIES-2, 2026-11-20).

PYTHONPATH=src .venv/bin/python scripts/research/opening_night_injuries.py [--capture 2026-11-20] [--refresh] [--write]

Sources (public; plain HTTP with small delays; no personal data in any request):
- ESPN scoreboard per day: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD
- ESPN game summaries (who played in each game):
  https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=ID
- The NBA's official injury report for each game day (status and reason for every listed player: "Injury/Illness -
  Right Calf; Strain", "G League - Two-Way", "Personal Reasons", "Rest", ...):
  https://ak-static.cms.nba.com/referee/injury/Injury-Report_YYYY-MM-DD_HH_MMPM.pdf (the day's latest report)
- ESPN's current injury report (status, diagnosis, estimated return date, notes), for players still out:
  https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries
- ESPN team schedules (games still to come for players still out):
  https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{id}/schedule

Method:
- Every final regular-season game from opening night (2026-10-20) to the day before the capture date.
- Out on opening night = did not play in his team's first game and was on that day's official injury report with an
  injury or illness reason. Players listed for other reasons (G League, personal reasons, not with team, rest,
  suspension) and healthy players who did not play (coach's decisions) are kept apart and never applied.
- Games missed = his team's games from the opener to the last game he missed while listed with an injury before his first
  game played (a healthy scratch after the injury is a coach's decision, not part of it).
- Still out on the capture date (never played): open-ended. Games already missed plus his team's remaining games until
  ESPN's estimated return date; a season-ending note means the whole season.
- Body part and diagnosis come from the official reason, mapped to the injury model's parts (injury_model.PART_LABELS).

Raw responses are cached in output/injuries-2/ (espn/, nba_pdf/) so a rerun does not refetch. --write writes
data/canonical/opening_night_injuries_2026_27.json.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta
import json
from pathlib import Path
import re
import time
import unicodedata
import urllib.error
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "output/injuries-2/espn"
PDF_CACHE = ROOT / "output/injuries-2/nba_pdf"
OUT = ROOT / "data/canonical/opening_night_injuries_2026_27.json"
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"
BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
SCOREBOARD = BASE + "/scoreboard?dates={day}"
SUMMARY = BASE + "/summary?event={game}"
INJURIES = BASE + "/injuries"
SCHEDULE = BASE + "/teams/{team}/schedule?season=2027&seasontype=2"
NBA_REPORT = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_{day}_{time}.pdf"
REPORT_TIMES = ("09_30PM", "09_00PM", "08_30PM", "08_00PM", "07_30PM", "07_00PM", "06_30PM", "06_00PM", "05_30PM",
                "05_00PM", "01_30PM", "12_00PM")
OPENING_NIGHT = date(2026, 10, 20)
SEASON_GAMES = 82
GAMES_PER_DAY = 82 / 174

NON_INJURY = ("COACH'S DECISION", "COACHS DECISION", "REST", "NOT WITH TEAM", "PERSONAL", "SUSPEND", "G LEAGUE",
              "G-LEAGUE", "TWO-WAY", "TWO- WAY", "TWO WAY", "INACTIVE", "TRADE", "BEREAVEMENT", "FAMILY")
# Reason text -> injury model body part (first match wins; specific before general).
PART_WORDS = [
    ("achilles", "achilles"), ("hamstring", "hamstring"), ("quad", "quadriceps"), ("thigh", "quadriceps"),
    ("calf", "calf"), ("soleus", "calf"), ("shin", "calf"), ("fibula", "calf"), ("tibia", "calf"), ("lower leg", "calf"),
    ("groin", "groin"), ("adductor", "groin"), ("abductor", "groin"), ("hip", "hip"), ("glute", "hip"),
    ("pelvi", "hip"), ("knee", "knee"), ("patella", "knee"), ("acl", "knee"), ("meniscus", "knee"), ("mcl", "knee"),
    ("ankle", "ankle"), ("toe", "toe"), ("plantar", "foot"), ("heel", "foot"), ("lisfranc", "foot"), ("foot", "foot"), ("navicular", "foot"),
    ("thumb", "thumb"), ("finger", "hand"), ("hand", "hand"), ("wrist", "wrist"), ("elbow", "shoulder"),
    ("forearm", "wrist"), ("arm", "shoulder"), ("shoulder", "shoulder"), ("rotator", "shoulder"),
    ("clavicle", "shoulder"), ("collarbone", "shoulder"),
    ("back", "back"), ("lumbar", "back"), ("spine", "back"), ("disc", "back"), ("oblique", "back"), ("rib", "back"),
    ("abdominal", "back"), ("core", "back"), ("neck", "back"),
    ("concussion", "head"), ("head", "head"), ("face", "head"), ("facial", "head"), ("nose", "head"), ("eye", "head"),
    ("orbital", "head"), ("jaw", "head"), ("tooth", "head"), ("dental", "head"),
    ("illness", "illness"), ("sick", "illness"), ("flu", "illness"), ("virus", "illness"), ("viral", "illness"),
    ("covid", "illness"), ("migraine", "illness"), ("health", "illness"), ("medical", "illness"),
]


def fetch_bytes(url: str, path: Path, refresh: bool = False) -> bytes | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    missing = path.with_suffix(path.suffix + ".missing")
    if path.exists() and not refresh:
        return path.read_bytes()
    if missing.exists() and not refresh:
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "research-script"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            missing.write_text(str(error.code))
            time.sleep(0.3)
            return None
        raise
    path.write_bytes(data)
    time.sleep(0.4)
    return data


def fetch(url: str, path: Path, refresh: bool = False) -> dict:
    data = fetch_bytes(url, path, refresh)
    return json.loads(data.decode("utf-8")) if data else {}


def is_injury_reason(reason: str | None) -> bool:
    text = str(reason or "").upper().strip()
    if not text:
        return False
    if text.startswith("INJURY/ILLNESS"):
        return True
    return not any(word in text for word in NON_INJURY)


def official_injury(row: dict) -> bool:
    """An official injury-report row that keeps the player out for an injury or illness ("Available" rows with "-" are
    cleared to play)."""
    return (str(row.get("status") or "").lower() not in ("available", "")
            and str(row.get("reason") or "").upper().startswith("INJURY/ILLNESS"))


def estimated_total_days(part: str | None, days_so_far: int) -> int | None:
    """Median length of the injury model's real absences for this body part that lasted at least as long as this one
    has so far (for players still out without a published return estimate)."""
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from nba_gm_data import injury_model as im
    model = im.load_model(ROOT) or {}
    quantiles = ((model.get("recovery_summary") or {}).get(part or "") or {}).get("quantiles") or []
    longer = [d for d in quantiles if d >= days_so_far]
    if not longer:
        return None
    return int(longer[len(longer) // 2])


def part_of(reason: str | None) -> str | None:
    text = " " + re.sub(r"[^a-z ]", " ", str(reason or "").lower()) + " "
    for word, part in PART_WORDS:
        if re.search(rf"\b{word}", text):
            return part
    return None


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", "", s.replace("-", " "))
    words = [w for w in s.split() if w not in ("jr", "sr", "ii", "iii", "iv")]
    return " ".join(words)


# ---- The NBA's official injury report (PDF; text cells with WinAnsi encoding, standard library only) ---------------
def report_cells(data: bytes) -> list[list[tuple[float, float, str]]]:
    pages = []
    for stream in re.finditer(rb"<<([^<>]*)>>\s*stream\r?\n", data):
        header = stream[1]
        if b"FlateDecode" not in header:
            continue
        # A compressed stream can itself end in CR. Use the PDF's length
        # instead of treating that byte as part of the endstream line break.
        length = re.search(rb"/Length\s+(\d+)\b(?!\s+\d+\s+R)", header)
        start = stream.end()
        stop = start + int(length[1]) if length else len(data)
        try:
            text = zlib.decompress(data[start:stop]).decode("latin-1")
        except zlib.error:
            continue
        if "Tj" not in text:
            continue
        cells, rect = [], None
        for m in re.finditer(r"([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) re\s*\n?W\* n|BT(.*?)ET", text, re.S):
            if m.group(1) is not None:
                rect = (float(m.group(1)), float(m.group(2)))
                continue
            words = re.findall(r"\(((?:\\.|[^\\)])*)\) Tj", m.group(5))
            value = " ".join(w.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\") for w in words)
            if rect and value:
                cells.append((rect[1], rect[0], value))
        pages.append(cells)
    return pages


COLUMNS = ((19, "date"), (116, "time"), (196, "matchup"), (260, "team"), (421, "player"), (582, "status"),
           (662, "reason"))


def report_rows(data: bytes) -> list[dict]:
    """Rows of an official injury report: game date, team, player ("Last, First"), status and reason, with the date and
    team carried down to the rows below them as the report prints them."""
    out, current = [], {"date": None, "team": None}
    for cells in report_cells(data):
        rows = []
        for y, x, value in sorted(cells):
            column = min(COLUMNS, key=lambda c: abs(c[0] - x))
            if abs(column[0] - x) > 12:
                continue
            # On some page breaks the first player's cells sit one point
            # above the date and team cells for the same row.
            if not rows or y - rows[-1][0] > 1.1:
                rows.append((y, {}))
            row = rows[-1][1]
            row[column[1]] = (row.get(column[1], "") + " " + value).strip()
        for _, row in rows:
            if row.get("date") == "Game Date" or "Page" in str(row.get("date") or ""):
                continue
            if re.match(r"\d\d/\d\d/\d{4}", str(row.get("date") or "")):
                m, d, yr = row["date"].split("/")
                current["date"] = f"{yr}-{m}-{d}"
            if row.get("team"):
                current["team"] = row["team"]
            if row.get("player") and current["date"] and current["team"]:
                out.append({"date": current["date"], "team": current["team"], "player": row["player"],
                            "status": row.get("status"), "reason": re.sub(r"\s+", " ", row.get("reason") or "")})
    return out


def day_report(day: date, refresh: bool) -> tuple[list[dict], str | None]:
    """The day's latest official injury report and its URL."""
    for stamp in REPORT_TIMES:
        url = NBA_REPORT.format(day=day.isoformat(), time=stamp)
        data = fetch_bytes(url, PDF_CACHE / f"{day.isoformat()}_{stamp}.pdf", refresh)
        if data:
            return report_rows(data), url
    return [], None


# ---- ESPN box scores -------------------------------------------------------------------------------------------------
def games_list(capture: date, refresh: bool) -> list[dict]:
    games, day = [], OPENING_NIGHT
    while day < capture:
        stamp = day.strftime("%Y%m%d")
        board = fetch(SCOREBOARD.format(day=stamp), CACHE / f"sb_{stamp}.json", refresh)
        for event in board.get("events") or []:
            status = ((event.get("status") or {}).get("type") or {}).get("name")
            if (event.get("season") or {}).get("type") == 2 and status == "STATUS_FINAL":
                games.append({"id": str(event["id"]), "date": day.isoformat()})
        day += timedelta(days=1)
    return games


def box_rows(game: dict, refresh: bool) -> list[dict]:
    data = fetch(SUMMARY.format(game=game["id"]), CACHE / f"sum_{game['id']}.json", refresh)
    rows = []
    for team in (data.get("boxscore") or {}).get("players") or []:
        info = team.get("team") or {}
        for block in team.get("statistics") or []:
            for athlete in block.get("athletes") or []:
                person = athlete.get("athlete") or {}
                stats = athlete.get("stats") or []
                try:
                    minutes = float(stats[0]) if stats else 0.0
                except (TypeError, ValueError):
                    minutes = 0.0
                rows.append({"game_id": game["id"], "date": game["date"], "team_id": str(info.get("id")),
                             "team": str(info.get("abbreviation")), "team_name": info.get("displayName"),
                             "espn_id": str(person.get("id")), "name": person.get("displayName"),
                             "played": minutes > 0 and not athlete.get("didNotPlay")})
    return rows


_ABBREV_FIX = {"UTAH": "UTA", "NY": "NYK", "SA": "SAS", "GS": "GSW", "NO": "NOP", "WSH": "WAS"}


def our_abbrev(espn_abbrev: str) -> str:
    return _ABBREV_FIX.get(espn_abbrev, espn_abbrev)


def clean_diagnosis(reason: str | None) -> str | None:
    text = re.sub(r"^Injury/Illness\s*-\s*", "", str(reason or ""), flags=re.I).strip()
    text = re.sub(r"\s*;\s*", " ", text)
    return text or None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", default=date.today().isoformat())
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    capture = date.fromisoformat(args.capture)
    games = games_list(capture, args.refresh)
    rows = [row for game in games for row in box_rows(game, args.refresh)]
    game_date = {g["id"]: g["date"] for g in games}
    team_games: dict[str, list[str]] = defaultdict(list)       # ESPN team id -> game ids in date order
    team_abbrev, team_name = {}, {}
    played: dict[tuple[str, str], set[str]] = defaultdict(set)  # (team, espn id) -> games played
    names_by_team: dict[str, dict[str, str]] = defaultdict(dict)  # team -> normalized name -> espn id
    for row in sorted(rows, key=lambda r: (r["date"], r["game_id"])):
        if row["game_id"] not in team_games[row["team_id"]]:
            team_games[row["team_id"]].append(row["game_id"])
        team_abbrev[row["team_id"]], team_name[row["team_id"]] = row["team"], row["team_name"]
        if row["played"]:
            played[(row["team_id"], row["espn_id"])].add(row["game_id"])
        names_by_team[row["team_id"]][norm(row["name"])] = row["espn_id"]
    team_by_name = {name: tid for tid, name in team_name.items()}
    print(f"{len(games)} final games, {len(rows)} box-score rows, {len(team_games)} teams, capture {capture}")

    # Official injury reports for every game day.
    reports: dict[str, dict[tuple[str, str], dict]] = {}       # date -> (team id, normalized name) -> row
    report_urls: dict[str, str] = {}
    for day in sorted({g["date"] for g in games}):
        rows_today, url = day_report(date.fromisoformat(day), args.refresh)
        report_urls[day] = url or ""
        listed = {}
        for r in rows_today:
            if r["date"] != day or r["team"] not in team_by_name:
                continue
            last, _, first = r["player"].partition(",")
            listed[(team_by_name[r["team"]], norm(f"{first} {last}"))] = r | {"name": f"{first.strip()} {last.strip()}"}
        reports[day] = listed
        if not url:
            print("  no official report found for", day)

    universe = json.loads(UNIVERSE.read_text())
    rostered = {s["player_id"] for s in universe["roster_slots"] if s.get("status") != "free_agent"}
    ours_by_espn = {str(p["espn_player_id"]): p for p in universe["players"] if p.get("espn_player_id")}
    ours_by_name = defaultdict(list)
    for p in universe["players"]:
        ours_by_name[norm(p["name"])].append(p)

    report_raw = fetch(INJURIES, CACHE / f"injuries_{capture.isoformat()}.json", args.refresh)
    espn_report: dict[str, dict] = {}
    for team in report_raw.get("injuries") or []:
        for item in team.get("injuries") or []:
            for link in (item.get("athlete") or {}).get("links") or []:
                match = re.search(r"/id/(\d+)/", str(link.get("href")))
                if match:
                    espn_report[match.group(1)] = item
                    break

    def remaining_games(team_id: str, until: date | None) -> int:
        data = fetch(SCHEDULE.format(team=team_id), CACHE / f"schedule_{team_id}.json", args.refresh)
        days = sorted(str(e.get("date"))[:10] for e in data.get("events") or [])
        return sum(1 for d in days if capture.isoformat() <= d and (until is None or d < until.isoformat()))

    records, non_injury, skipped = [], [], []
    for team_id, gids in sorted(team_games.items(), key=lambda kv: team_abbrev[kv[0]]):
        opener, abbrev = gids[0], team_abbrev[team_id]
        opener_day = game_date[opener]
        for (tid, key), listing in sorted(reports.get(opener_day, {}).items()):
            if tid != team_id:
                continue
            espn = names_by_team[team_id].get(key)
            candidates = [p for p in ours_by_name.get(key, []) if p.get("team_abbrev") == our_abbrev(abbrev)] or ours_by_name.get(key, [])
            player = ours_by_espn.get(espn) if espn else (candidates[0] if len(candidates) == 1 else None)
            espn = espn or (str(player.get("espn_player_id")) if player and player.get("espn_player_id") else None)
            if espn and opener in played.get((team_id, espn), set()):
                continue      # listed (questionable or probable) but played
            base = {"name": listing["name"], "espn_id": espn, "team": our_abbrev(abbrev), "opener_date": opener_day,
                    "opener_status": listing["status"], "opener_reason": listing["reason"]}
            if not official_injury(listing):
                non_injury.append(base)
                continue
            # Walk his team's games until his first game played.
            first_played, missed, last_injury = None, 0, -1
            for index, gid in enumerate(gids):
                if espn and gid in played.get((team_id, espn), set()):
                    first_played = gid
                    break
                missed += 1
                entry = reports.get(game_date[gid], {}).get((team_id, key))
                if entry and official_injury(entry):
                    last_injury = index
            current = espn_report.get(espn or "")
            # Never played by the capture date: still out only if he is on ESPN's current report or was listed injured
            # for his team's latest game; otherwise the injury ended at his last injury listing (since then he has
            # been a healthy scratch, a G League assignee or off the team).
            open_ended = first_played is None and (current is not None or last_injury == missed - 1)
            games_missed = missed if open_ended else last_injury + 1
            details = (current or {}).get("details") or {}
            note = " ".join(str((current or {}).get(k) or "") for k in ("shortComment", "longComment")).lower()
            season_ending = False
            expected_return = return_estimate_source = None
            if open_ended:
                if re.search(r"(rest of|remainder of|entire|miss the|out for the) (the )?(\d{4}-\d\d )?season|season-ending", note):
                    season_ending, games_missed = True, SEASON_GAMES
                    return_estimate_source = "ESPN injury report note: out for the season"
                elif details.get("returnDate"):
                    expected_return = str(details["returnDate"])[:10]
                    return_estimate_source = "ESPN injury report estimate"
                    games_missed = missed + remaining_games(team_id, date.fromisoformat(expected_return))
                else:
                    total = estimated_total_days(part_of(clean_diagnosis(listing["reason"])),
                                                 (capture - date.fromisoformat(opener_day)).days)
                    if total:
                        expected_return = (date.fromisoformat(opener_day) + timedelta(days=total)).isoformat()
                        games_missed = missed + remaining_games(team_id, date.fromisoformat(expected_return))
                        return_estimate_source = "injury model: median real absence for this body part at least this long"
                games_missed = min(SEASON_GAMES, games_missed)
            diagnosis = clean_diagnosis(listing["reason"])
            records.append({
                **base,
                "player_id": (player or {}).get("id"),
                "universe_team": (player or {}).get("team_abbrev"),
                "body_part": part_of(diagnosis) or part_of(" ".join(str(details.get(k) or "") for k in ("type", "detail"))),
                "diagnosis": diagnosis,
                "games_missed": int(games_missed),
                "games_missed_by_capture": missed if open_ended else int(games_missed),
                "first_game": game_date.get(first_played) if first_played else None,
                "open_ended": open_ended,
                "season_ending": season_ending,
                "expected_return": expected_return,
                "return_estimate_source": return_estimate_source,
                "sources": [s for s in (
                    {"what": "official NBA injury report, opening night", "url": report_urls.get(opener_day),
                     "date": opener_day, "status": listing["status"], "reason": listing["reason"]},
                    {"what": "ESPN box score, opener", "url": SUMMARY.format(game=opener), "date": opener_day},
                    {"what": "ESPN box score, first game played", "url": SUMMARY.format(game=first_played),
                     "date": game_date[first_played]} if first_played else None,
                    {"what": "ESPN injury report", "url": INJURIES, "fetched": capture.isoformat(),
                     "updated": str(current.get("date") or "")[:10], "status": current.get("status"),
                     "return_estimate": details.get("returnDate"), "detail": {k: details.get(k) for k in ("side", "type", "detail")}}
                    if current and open_ended else None,
                ) if s],
            })

    # Our rostered players the opening-night list cannot be applied to: hurt on a different real team.
    for r in records:
        if not r["player_id"]:
            r["apply"] = False
            r["skip_reason"] = "not in the game's 2026-27 universe"
        elif ours_by_espn.get(r["espn_id"] or "", {}).get("id") != r["player_id"] and r["espn_id"]:
            r["apply"] = False
            r["skip_reason"] = "matched by name only"
        elif r["universe_team"] != r["team"]:
            r["apply"] = False
            r["skip_reason"] = f"on {r['universe_team']} in the game's universe"
        elif r["player_id"] not in rostered:
            r["apply"] = False
            r["skip_reason"] = "a free agent in the game's universe"
        else:
            r["apply"] = True
        if not r["apply"]:
            skipped.append({k: r[k] for k in ("name", "team", "player_id", "universe_team", "skip_reason")})
    records.sort(key=lambda r: (-r["games_missed"], r["team"], r["name"]))
    print(f"\nOut injured on opening night: {len(records)} ({sum(r['apply'] for r in records)} applied)")
    for r in records:
        print(f"  {r['team']:4} {r['name']:26} {r['games_missed']:3}{'+' if r['open_ended'] else ' '} "
              f"{str(r['body_part']):10} {r['diagnosis']}  {'' if r['apply'] else '[skip: ' + r['skip_reason'] + ']'}")
    print(f"\nListed for other reasons: {len(non_injury)}", Counter(r["opener_reason"] for r in non_injury).most_common())
    if args.write:
        payload = {
            "version": f"opening_night_injuries_2026_27_{capture.isoformat()}",
            "season": "2026-27",
            "opening_night": OPENING_NIGHT.isoformat(),
            "captured": capture.isoformat(),
            "method": ("Out on opening night: did not play in his team's first 2026-27 game and was on that day's official "
                       "NBA injury report with an injury or illness reason (G League, personal reasons, not with team, "
                       "rest and suspensions are listed under not_injuries and never applied). games_missed counts his "
                       "team's games from the opener to the last game he missed while listed with an injury before his "
                       "first game played. open_ended: still out on the capture date; games already missed plus his "
                       "team's games until ESPN's estimated return date, or the whole season when reported as such. "
                       "apply: false when the player is not on the same team in the game's universe (skip_reason)."),
            "sources": {"box_scores": SUMMARY.replace("{game}", "ID"),
                        "scoreboard": SCOREBOARD.replace("{day}", "YYYYMMDD"),
                        "official_injury_reports": sorted(u for u in report_urls.values() if u),
                        "espn_injury_report": INJURIES, "espn_schedules": SCHEDULE.replace("{team}", "ID")},
            "games_scanned": len(games),
            "injuries": records,
            "not_injuries": sorted(non_injury, key=lambda r: (r["team"], r["name"])),
            "skipped": skipped,
        }
        OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
        print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
