#!/usr/bin/env python3
"""Rebuild NBA missed-game stretches for 2023–24 through 2025–26.

Run with --write to update the public-source JSON. Use --compare-tracker for
local aggregate comparisons. Downloads reuse each season’s local cache.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from opening_night_injuries import (
    BASE, NBA_REPORT, ROOT, SCOREBOARD, SUMMARY, UNIVERSE,
    fetch, fetch_bytes, norm, our_abbrev, part_of, report_rows,
)
from injury_history_sources import SEASONS, cached_request, capture_summaries, espn_events, is_final

BOX = ROOT / "data/research/game_boxscores_2025_26.json"
TRACKER = ROOT / "data/research/bbi/tools"
TRADES = ROOT / "data/research/real_trades/trades_2025_2027.json"
DEFAULT_SEASON = SEASONS["2025-26"]
EASTERN = ZoneInfo("America/New_York")
NBA_BOX_FALLBACK = {
    "2025-26": {"401873343": "https://www.nba.com/game/nyk-vs-cle-0042500303/box-score"},
}
HALIBURTON_UPDATE = "https://www.nba.com/pacers/news/indiana-pacers-medical-update-tyrese-haliburton-250623"
OFF_ROSTER_INTERVALS = (
    ("Yuki Kawamura", "CHI", "2025-10-17", "2026-01-06",
     "https://www.nba.com/gamenotes/bulls.pdf?tid=1736569615503"),
    ("CJ Huntley", "PHX", "2025-11-17", "2026-03-02",
     "https://www.nba.com/gamenotes/suns.pdf?id=444788"),
    ("Kobe Bufkin", "LAL", "2026-01-23", "2026-02-08",
     "https://www.nba.com/lakers/news/lakers-sign-guard-kobe-bufkin"),
)
OFFICIAL_STATUSES = {"Out", "Doubtful", "Questionable", "Probable"}
MEDICAL = {"injury", "illness"}
NAME_ALIASES = {
    "hansen yang": "yang hansen",
    "kenyon martin": "kj martin",
    "nathan mensah": "nate mensah",
    "alexandre sarr": "alex sarr",
    "carlton carrington": "bub carrington",
    "cui yongxi": "yongxi cui",
    "david jones": "david jones garcia",
}
# ESPN identifies these players in historical boxes even when they are
# report-only in the season being built. Keep their ID stable across years.
HISTORICAL_ESPN_IDS = {
    "bojan bogdanovic": "3593",
    "charles bediako": "4565203",
    "cody zeller": "2579258",
    "damion lee": "2595209",
    "jalen crutcher": "4278352",
    "kendall brown": "4433254",
    "vlatko cancar": "4230557",
}
PART_ALIASES = {
    "sciatic": "back", "cervical": "back", "thoracic": "back", "sacral": "back",
    "costochondral": "back", "trunk": "back", "patellofemoral": "knee",
    "scaphoid": "wrist", "ulnar styloid": "wrist", "metacarpal": "hand",
    "midfoot": "foot", "metatarsal": "foot", "retrocalcaneal": "foot",
    "ac joint": "shoulder", "triceps": "shoulder", "biceps": "shoulder",
    "nasal": "head", "mtp": "toe", "glut": "hip", "lower left leg": "calf",
    "lower right leg": "calf", "upper trap": "back", "midfront": "foot",
}
TRACKER_PARTS = {
    "heel": "foot", "finger": "hand", "elbow": "shoulder", "forearm": "wrist",
    "arm": "shoulder", "leg": "calf", "shin": "calf", "neck": "back",
    "abdomen": "back", "ribs": "back", "chest": "back", "tailbone": "back",
    "eye": "head", "dental": "head",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def espn(path, filename, cache_only, season):
    cached = season.espn_cache / filename
    if cache_only:
        return read(cached)
    data = cached_request(fetch, BASE + path, cached, throttle=season.historical)
    if not data:
        raise RuntimeError(f"ESPN data missing for {path}")
    return data


def nba_box(url, cache_only, season):
    path = season.espn_cache / ("ih_nba_" + url.split("/")[-2].rsplit("-", 1)[-1] + ".html")
    raw = path.read_bytes() if cache_only else cached_request(fetch_bytes, url, path)
    state = re.search(rb'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', raw)
    game = json.loads(state[1])["props"]["pageProps"]["game"]
    return [{
        "espn_player_id": None, "player_name": p["firstName"] + " " + p["familyName"],
        "team_abbrev": game[side]["teamTricode"], "comment": p["comment"],
        "played": bool(p["statistics"]["minutes"]), "box_score_url": url,
    } for side in ("homeTeam", "awayTeam") for p in game[side]["players"]]


def load_schedule(season, cache_only):
    events = espn_events(season, lambda path, filename: espn(path, filename, cache_only, season))
    final = {gid: (event, phase) for gid, (event, phase) in events.items() if is_final(event)}
    actual = Counter(phase for _, phase in final.values())
    expected = {"regular": 1230, "cup_final": 1, "play_in": 6, "playoffs": season.playoff_games}
    if actual != expected:
        raise ValueError(f"{season.label} game count: expected {expected}, got {dict(actual)}")
    return final


def load_games(box_games, cache_only, season):
    """Use ET dates and final status from ESPN, plus the six play-ins."""
    events = load_schedule(season, cache_only)
    fallback = NBA_BOX_FALLBACK.get(season.label, {})
    if season.historical and not cache_only:
        capture_summaries(season, [gid for gid in events if gid not in fallback])

    games, supplemental = [], []
    teams_by_name = {}
    for gid, (event, phase) in events.items():
        competition = event["competitions"][0]
        game_date = datetime.fromisoformat(event["date"].replace("Z", "+00:00")).astimezone(EASTERN)
        teams = {}
        for competitor in competition["competitors"]:
            team = competitor["team"]
            abbrev = our_abbrev(team["abbreviation"])
            teams[competitor["homeAway"]] = abbrev
            teams_by_name[team["displayName"]] = abbrev
        box = box_games.get(gid)
        if box and not box["players"]:
            box = None
        ambiguous = box and any(p["espn_player_id"] and not p["dnp"] and not p["minutes"]
                                for p in box["players"])
        if gid in fallback:
            supplemental.append(gid)
            players = nba_box(fallback[gid], cache_only, season)
        elif not box or ambiguous:
            if not box:
                supplemental.append(gid)
            summary = espn(f"/summary?event={gid}", f"sum_{gid}.json", cache_only, season)
            players = []
            for team in summary["boxscore"]["players"]:
                for group in team["statistics"]:
                    for row in group["athletes"]:
                        person = row.get("athlete") or {}
                        stats = row.get("stats") or []
                        if season.historical and stats and stats[0] == "--" and not row.get("didNotPlay"):
                            # ESPN carries roster placeholders with no minutes
                            # and without the flag it uses for actual scratches.
                            continue
                        if person.get("id"):
                            players.append({
                                "espn_player_id": person["id"], "player_name": person["displayName"],
                                "team_abbrev": team["team"]["abbreviation"], "comment": row.get("reason"),
                                "played": bool(stats) and not row.get("didNotPlay"),
                            })
        else:
            players = [p | {"played": bool(p["minutes"]) and not p["dnp"]} for p in box["players"]]
        teams_with_appearances = {our_abbrev(p["team_abbrev"]) for p in players if p["played"]}
        if teams_with_appearances != set(teams.values()):
            raise ValueError(f"Incomplete box score for {season.label} game {gid}: {teams_with_appearances}")
        games.append({"id": gid, "date": game_date.date().isoformat(), "phase": phase,
                      "teams": tuple(teams.values()), "players": players})
    assert set(Counter(team for g in games if g["phase"] == "regular" for team in g["teams"]).values()) == {82}
    return sorted(games, key=lambda g: (g["date"], g["id"])), teams_by_name, supplemental


def name_key(name):
    key = norm(name or "")
    return NAME_ALIASES.get(key, key)


def nba_report(day, cache_only, season):
    # Older filenames omit the minutes. As of December 22, use the late
    # evening snapshot and fall back to earlier reports when necessary.
    if day < "2025-12-22":
        stamps = ("11PM", "10PM", "09PM", "08PM", "07PM", "06PM", "05PM", "01PM", "09AM")
    else:
        stamps = ("09_30PM", "09_00PM", "08_30PM", "08_00PM", "07_30PM", "07_00PM",
                  "06_30PM", "06_00PM", "05_30PM", "05_00PM", "01_30PM", "12_00PM")
    first_url = None
    for stamp in stamps:
        url = NBA_REPORT.format(day=day, time=stamp)
        path = season.pdf_cache / f"{day}_{stamp}.pdf"
        raw = (path.read_bytes() if path.exists() else None) if cache_only else cached_request(fetch_bytes, url, path)
        if raw:
            first_url = first_url or url
            rows = [r for r in report_rows(raw) if r["date"] == day]
            if rows:
                return rows, url
    return [], first_url


def observations(games, players, teams_by_name, cache_only, season):
    by_id = {str(p["espn_player_id"]): p["id"] for p in players.values() if p.get("espn_player_id")}
    by_name = {name_key(p["name"]): p["id"] for p in players.values()}
    names = dict(by_name)
    box, reports, urls, report_teams = {}, {}, {}, set()
    teams_on_day = defaultdict(set)
    for game in games:
        teams_on_day[game["date"]].update(game["teams"])
        for p in game["players"]:
            espn_id = str(p["espn_player_id"])
            name = name_key(p["player_name"])
            pid = by_id.get(espn_id) or by_name.get(name)
            if season.historical and not pid and p["espn_player_id"]:
                pid = f"espn_{espn_id}"
                players[pid] = {"id": pid, "name": p["player_name"], "espn_player_id": espn_id}
                by_id[espn_id] = pid
            if pid and (p["espn_player_id"] or p.get("box_score_url")):
                team = our_abbrev(p["team_abbrev"])
                names.setdefault(name, pid)
                key = game["id"], team, pid
                if key not in box or p["played"]:
                    box[key] = p
    for day, teams in sorted(teams_on_day.items()):
        rows, url = nba_report(day, cache_only, season)
        if url:
            urls[day] = url
        for r in rows:
            report_team = r["team"]
            if season.historical and report_team == "Los Angeles Clippers":
                report_team = "LA Clippers"
            team = teams_by_name.get(report_team)
            if team not in teams:
                continue
            report_teams.add((day, team))
            last, comma, first = r["player"].partition(",")
            key_name = name_key(f"{first} {last}") if comma else None
            pid = names.get(key_name)
            if season.historical and key_name and not pid and r["status"] in OFFICIAL_STATUSES | {"Available"}:
                espn_id = HISTORICAL_ESPN_IDS.get(key_name)
                pid = f"espn_{espn_id}" if espn_id else "nba_report_" + key_name.replace(" ", "-")
                players[pid] = {"id": pid, "name": f"{first.strip()} {last.strip()}", "espn_player_id": espn_id}
                names[key_name] = pid
            if pid:
                key = day, team, pid
                if key in reports and reports[key] != r:
                    raise ValueError(f"Conflicting report rows for {key}: {reports[key]} / {r}")
                reports[key] = r
    return box, reports, urls, report_teams, names


def season_roster_corrections(season):
    if season.label == "2023-24":
        return (
            ("Taze Moore", "POR", "2024-01-30", "2024-04-14",
             "https://www.nba.com/blazers/news/trail-blazers-sign-taze-moore-to-two-way-contract"),
            ("DaQuan Jeffries", "NYK", "2023-12-30", "2024-02-22",
             "https://westchester.gleague.nba.com/news/westchester-knicks-acquire-daquan-jeffries"),
            ("Duane Washington Jr.", "NYK", "2023-11-27", "2024-01-03",
             "https://www.nba.com/player/1630613"),
        )
    if season.label == "2024-25":
        return (
            ("Skal Labissiere", "SAC", "2024-10-18", "2025-03-03",
             "https://www.nba.com/kings/news/kings-announce-roster-moves-2"),
            ("Kevon Harris", "ATL", "2024-10-18", "2025-03-01",
             "https://gleague.nba.com/news/atlanta-hawks-sign-kevon-harris-to-10-day-contract"),
            ("Kevon Harris", "ATL", "2025-03-04", None, "https://www.nba.com/game/0022400884"),
        )
    return OFF_ROSTER_INTERVALS


def off_roster(day, left, joined):
    return day >= left and (joined is None or day < joined)


def roster_moves(names, cache_only, season):
    """Use signings, trades and waivers to bound time between game records."""
    moves = defaultdict(set)
    starts = ("Signed", "Re-signed", "Claimed", "Acquired", "Received", "Converted", "Waived", "Released")
    split = r"(?<=\.)\s+(?=(?:" + "|".join(starts) + r")\b)"
    urls = []
    year = season.year
    day_before_opener = date.fromisoformat(season.opener) - timedelta(days=1)
    move_ranges = ((f"{year - 1}0701", day_before_opener.strftime("%Y%m%d")),
                   (season.opener.replace("-", ""), f"{year}0131"),
                   (f"{year}0201", season.end.replace("-", "")))
    for start, end in move_ranges:
        path = f"/transactions?dates={start}-{end}&limit=1000"
        payload = espn(path, f"ih_moves_{start}_{end}.json", cache_only, season)
        assert payload["pageCount"] == 1
        urls.append(BASE + path)
        for move in payload["transactions"]:
            day = move["date"][:10]
            team = our_abbrev(move["team"]["abbreviation"])
            for clause in re.split(split, move["description"]):
                verb, _, detail = clause.partition(" ")
                if verb not in starts or "extension" in detail.lower():
                    continue
                subject = re.split(r"\b(?:from|in exchange|for|to a|to an|to standard|off waivers|the draft rights)\b",
                                   detail, maxsplit=1, flags=re.I)[0]
                subject = f" {norm(subject)} "
                if verb in ("Waived", "Released"):
                    action = "exit"
                elif verb in ("Acquired", "Received"):
                    action = "trade_in"
                else:
                    action = "ten_day" if "10-day" in detail else "sign"
                for key, pid in names.items():
                    if key and f" {key} " in subject:
                        moves[pid].add((day, action, team))
    # Structured trade edges also give the receiving and sending teams on the
    # same day when the transaction feed omits one side of a deal.
    for trade in read(TRADES)["trades"]:
        if season.opener <= trade["date"] <= season.end:
            for asset in trade["assets"]:
                pid = names.get(name_key(asset["name_or_desc"])) if asset["kind"] == "player" else None
                if pid:
                    moves[pid].add((trade["date"], "exit", asset["from"]))
                    moves[pid].add((trade["date"], "trade_in", asset["to"]))
    for name, team, left, joined, _ in season_roster_corrections(season):
        pid = names.get(name_key(name))
        if pid:
            moves[pid] = {m for m in moves[pid] if m[2] != team or not off_roster(m[0], left, joined)}
            moves[pid].add((left, "exit", team))
            if joined:
                moves[pid].add((joined, "sign", team))
    return moves, urls


def roster_stints(games, box, reports, moves, assignments):
    """Bound inferred roster membership by observations or dated transactions."""
    schedule = defaultdict(list)
    games_by_id = {}
    evidence = defaultdict(set)
    for g in games:
        games_by_id[g["id"]] = g
        for team in g["teams"]:
            schedule[team].append(g["date"])
    for gid, team, pid in box:
        day = games_by_id[gid]["date"]
        if assignments.get((pid, day), team) == team:
            evidence[pid].add((day, "seen", team))
    for day, team, pid in reports:
        if assignments.get((pid, day), team) == team:
            evidence[pid].add((day, "seen", team))

    stints = defaultdict(list)
    order = {"exit": 0, "trade_in": 1, "sign": 2, "ten_day": 3, "seen": 4}
    for pid, seen in evidence.items():
        team = start = last = expiry = None
        events = sorted(seen | moves[pid], key=lambda e: (e[0], order[e[1]], e[2]))
        for day, action, club in events:
            if expiry and day >= expiry:
                stints[pid].append((team, start, expiry))
                team = expiry = None
            if action == "exit":
                if team == club:
                    stints[pid].append((team, start, day))
                    team = expiry = None
                continue
            if team != club:
                if team:
                    stop = day if action == "trade_in" else (date.fromisoformat(last) + timedelta(days=1)).isoformat()
                    stints[pid].append((team, start, stop))
                team, start, expiry = club, day, None
            last = day
            if action == "ten_day":
                third_game = [d for d in schedule[club] if d >= day][:3]
                length = (date.fromisoformat(day) + timedelta(days=10)).isoformat()
                if len(third_game) == 3:
                    length = max(length, (date.fromisoformat(third_game[-1]) + timedelta(days=1)).isoformat())
                expiry = length
            elif action == "sign":
                expiry = None
        if team:
            # An uncapped stint ends at the last evidence, including players
            # whose team made the playoffs but whose eligibility is uncertain.
            stop = expiry or (date.fromisoformat(last) + timedelta(days=1)).isoformat()
            stints[pid].append((team, start, stop))
    return stints


def medical_part(site, diagnosis):
    text = f"{site or ''} {diagnosis or ''}".lower()
    primary = part_of(site)
    if primary and primary != "illness":
        return primary
    return next((part for alias, part in PART_ALIASES.items() if re.search(rf"\b{alias}", text)),
                part_of(text))


def reason_fields(reason):
    """Keep the published diagnosis and its body site, plus a model body part."""
    reason = reason or ""
    text = reason.strip().lower()
    categories = (
        (("rest",), "rest"),
        (("personal", "bereavement", "family"), "personal"),
        (("g league", "g-league", "two-way"), "g_league"),
        (("suspend", "suspension"), "suspension"),
        (("not with team", "not with the team", "leave of absence"), "not_with_team"),
        (("trade",), "trade"),
        (("coach's decision", "coachs decision"), "coach_decision"),
        (("reconditioning", "return to competition"), "reconditioning"),
    )
    official_medical = text.startswith("injury/illness")
    if not official_medical:
        for terms, category in categories:
            if any(term in text for term in terms):
                return category, None, None, None
    detail = re.sub(r"^injury/illness\s*-?\s*", "", reason, flags=re.I).strip()
    site, sep, diagnosis = detail.partition(";")
    if not sep:
        site, diagnosis = (detail, "") if official_medical else ("", detail)
    site, diagnosis = site.strip(), diagnosis.strip()
    if site.lower() in ("", "n/a", "na", "general", "-"):
        site = None
    if diagnosis in ("", "-", "."):
        diagnosis = None
    if not diagnosis and site and site.lower().endswith("sciatica"):
        diagnosis = "Sciatica"
    part = medical_part(site, diagnosis)
    illness = re.search(r"\b(illness|sick|flu|virus|viral|covid|migraine|gastroenteritis)\b",
                        f"{site or ''} {diagnosis or ''}", re.I)
    if illness and (not part or part == "illness" or (diagnosis or "").lower() == "illness"):
        return "illness", "illness", site, diagnosis or site
    if official_medical or part or re.search(r"\b(injur\w*|sprain\w*|fractur\w*|surgery)\b", text):
        return "injury", part if part != "illness" else None, site, diagnosis
    return "unknown", None, None, None


def missed_game(game, team, box, report, report_url):
    box_reason = (box or {}).get("comment")
    box_fields = reason_fields(box_reason)
    official = report and report["status"] in OFFICIAL_STATUSES and report["reason"] not in ("", "-")
    evidence = {"game_id": game["id"], "date": game["date"], "phase": game["phase"],
                "roster_evidence": "box_score" if box else "nba_report" if report else "inferred_stint"}
    if box_reason:
        evidence["box_score_reason"] = box_reason
    if box and box.get("box_score_url"):
        evidence["box_score_url"] = box["box_score_url"]
    if report:
        evidence["nba_report"] = {"url": report_url, "status": report["status"], "reason": report["reason"]}
    if official and (report["status"] == "Out" or box_fields[0] in ("coach_decision", "unknown")):
        reason = report["reason"]
        evidence["reason_source"] = "nba_report"
        if (game["date"] == "2026-03-23" and team == "IND" and report["player"] == "Haliburton, Tyrese"
                and reason == "Injury/Illness - Right ACL; Tear"):
            reason = "Injury/Illness - Right Achilles Tendon; Tear"
            evidence["reason_correction"] = {"url": HALIBURTON_UPDATE, "reason": reason}
        fields = reason_fields(reason)
    else:
        evidence["reason_source"] = "box_score" if box_fields[0] != "unknown" else None
        fields = box_fields
    category, part, site, diagnosis = fields
    side = re.search(r"\b(left|right|bilateral)\b", site or diagnosis or "", re.I)
    return (category, part, side[1].lower() if side and category == "injury" else None,
            site, diagnosis), evidence


def transfer_day_teams(box, reports, moves, game_dates, season):
    """Prefer the club a player played for, then the incoming roster on transfer day."""
    clubs = defaultdict(set)
    active = {}
    for (gid, team, pid), row in box.items():
        key = pid, game_dates[gid]
        clubs[key].add(team)
        if row["played"]:
            active[key] = team
    for day, team, pid in reports:
        clubs[pid, day].add(team)
    assignments = {}
    for (pid, day), teams in clubs.items():
        if len(teams) == 1:
            assignments[pid, day] = next(iter(teams))
            continue
        incoming = {t for d, act, t in moves[pid] if d == day and act == "trade_in"} & teams
        if (pid, day) in active:
            assignments[pid, day] = active[pid, day]
        elif len(incoming) == 1:
            assignments[pid, day] = next(iter(incoming))
        elif season.historical:
            # An updated incoming team's listing can coexist with a pending
            # trade on the old team's report even after the deal is official.
            reported = {t: reports.get((day, t, pid), {}).get("reason", "").lower() for t in teams}
            received = {t for t, reason in reported.items() if reason == "not with team"}
            if len(received) != 1 or {reported[t] for t in teams - received} != {"trade pending"}:
                raise ValueError(f"Unresolved overlap for {pid}, {day}, {sorted(teams)}: {reported}")
            assignments[pid, day] = next(iter(received))
        else:
            raise ValueError(f"Unresolved overlap for {pid}, {day}, {sorted(teams)}")
    return assignments


def make_stretches(games, players, box, reports, urls, stints, assignments):
    records, pending = [], {}
    played = Counter()
    by_team = defaultdict(set)
    for pid, spans in stints.items():
        for team, start, stop in spans:
            by_team[team].add(pid)
    openers = {}
    for g in games:
        day = g["date"]
        for team in sorted(g["teams"]):
            if g["phase"] == "regular":
                openers.setdefault(team, g["id"])
            for pid in sorted(by_team[team]):
                key = team, pid
                line = box.get((g["id"], team, pid))
                report = reports.get((day, team, pid))
                eligible = g["phase"] in ("regular", "cup_final")
                rostered = assignments.get((pid, day), team) == team and (
                    line or report or (eligible and any(t == team and start <= day < stop for t, start, stop in stints[pid]))
                )
                if not rostered or (line and line["played"]):
                    pending.pop(key, None)
                    if line and line["played"]:
                        played[pid, g["phase"]] += 1
                    continue
                fields, evidence = missed_game(g, team, line, report, urls.get(day))
                category, part, side, site, diagnosis = fields
                # Status changes and reworded diagnoses for the same side and
                # risk part do not start another absence without a return.
                signature = category, part or (site or "").lower(), side
                if key not in pending or pending[key][0] != signature:
                    record = {"player_id": pid, "player": players[pid]["name"], "team": team,
                              "reason_category": category, "body_part": part, "side": side,
                              "reported_body_parts": [], "diagnoses": [], "sources": []}
                    records.append(record)
                    pending[key] = signature, record
                record = pending[key][1]
                for field, value in (("reported_body_parts", site), ("diagnoses", diagnosis)):
                    if value and value not in record[field]:
                        record[field].append(value)
                record["sources"].append(evidence)
    for r in records:
        r["first_game_missed"] = r["sources"][0]["date"]
        r["last_game_missed"] = r["sources"][-1]["date"]
        r["games_missed"] = len(r["sources"])
        r["regular_season_games_missed"] = sum(s["phase"] == "regular" for s in r["sources"])
        r["at_team_season_start"] = r["sources"][0]["game_id"] == openers[r["team"]]
        r["injury_management_only"] = bool(r["reason_category"] == "injury" and r["diagnoses"] and
                                           all("management" in d.lower() for d in r["diagnoses"]))
    return sorted(records, key=lambda r: (r["player_id"], r["first_game_missed"], r["team"])), played


def match_tracker(entry, candidates):
    """Find the corresponding public absence by player, club, date and injury site."""
    start = date.fromisoformat(entry["start"][:10])
    end = date.fromisoformat(entry["end"][:10]) if entry.get("end") else start
    tracker_part = TRACKER_PARTS.get(entry["part"], entry["part"])
    side = (entry.get("side") or "").lower()
    choices = []
    for index, r in candidates:
        if entry["team"] and not (r["team_name"].endswith(entry["team"]) or r["team"] == entry["team"]):
            continue
        if r["reason_category"] != entry["cat"]:
            continue
        part = r["body_part"]
        if tracker_part and part and tracker_part != part:
            continue
        if side in ("left", "right") and r["side"] in ("left", "right") and side != r["side"]:
            continue
        first = date.fromisoformat(r["first_game_missed"])
        last = date.fromisoformat(r["last_game_missed"])
        distance = abs((start - first).days)
        overlap = (min(end, last) - max(start, first)).days >= 0
        # The tracker uses first missed game or an injury date. Give a known
        # compatible site a three-day margin for the schedule between them.
        if distance <= (3 if part and tracker_part == part else 1) or (overlap and entry["games"]):
            choices.append((distance, not overlap, index))
    return min(choices)[2] if choices else None


def compare_tracker(records, players, names, played, teams_by_name, season):
    history = read(TRACKER / "injury_player_history.json")
    player_seasons = read(TRACKER / "injury_player_seasons.json")
    for label in SEASONS:
        rows = [h for h in history if h["season"] == label]
        gp = sum(r["gp"] for r in player_seasons if r["season"] == label)
        rate = len(rows) * 1000 / gp
        missed = sum(bool(h["games"]) and h["cat"] in MEDICAL for h in rows)
        print(f"Tracker {label}: {len(rows)} entries / {gp} GP = {rate:.2f}; "
              f"{missed} medical entries with misses = {missed * 1000 / gp:.2f}")
    entries = [h for h in history if h["season"] == season.label]
    team_names = {abbrev: name for name, abbrev in teams_by_name.items()}
    candidates = defaultdict(list)
    for index, r in enumerate(records):
        if r["reason_category"] in MEDICAL:
            candidates[r["player_id"]].append((index, r | {"team_name": team_names[r["team"]]}))
    matched = set()
    counts = Counter()
    by_player = defaultdict(Counter)
    counts["tracker_all_entries"] = len(entries)
    for entry in entries:
        pid = entry.get("player_id")
        if pid not in players:
            pid = names.get(name_key(entry["player"]))
        if pid not in players:
            counts["tracker_entries_unlinked"] += 1
            continue
        player_counts = by_player[pid]
        counts["tracker_entries"] += 1
        player_counts["tracker_entries"] += 1
        if entry["cat"] in MEDICAL:
            counts["tracker_medical"] += 1
            player_counts["tracker_medical"] += 1
            if entry["games"]:
                counts["tracker_medical_with_missed_games"] += 1
            index = match_tracker(entry, candidates[pid]) if entry.get("start") else None
            if index is not None:
                matched.add(index)
                counts["tracker_medical_entries_matched"] += 1
                player_counts["matched"] += 1
                if records[index]["regular_season_games_missed"]:
                    counts["tracker_entries_matched_to_regular_season_absences"] += 1
                if entry["games"]:
                    counts["tracker_positive_game_entries_matched"] += 1
                if not entry["games"]:
                    counts["tracker_zero_game_entries_matched"] += 1
    counts["matched_public_medical_stretches"] = len(matched)
    for pid, rows in candidates.items():
        for index, r in rows:
            if index not in matched:
                counts["new_medical_stretches"] += 1
                counts[f"new_{r['reason_category']}_stretches"] += 1
                by_player[pid]["new"] += 1
                if r["regular_season_games_missed"]:
                    counts["new_medical_stretches_with_regular_season_misses"] += 1
                    counts[f"new_{r['reason_category']}_stretches_with_regular_season_misses"] += 1
                    if r["injury_management_only"]:
                        counts["new_regular_season_injury_management_only"] += 1
                    elif r["at_team_season_start"]:
                        counts["new_regular_season_non_management_opening_stretches"] += 1
            by_player[pid]["public_medical"] += 1
            by_player[pid]["public_medical_games_missed"] += r["regular_season_games_missed"]
    gp = sum(count for (_, phase), count in played.items() if phase == "regular")
    counts["regular_season_games_played"] = gp
    counts["tracker_plus_new_entries"] = counts["tracker_entries"] + counts["new_medical_stretches"]
    regular_additions = counts["new_medical_stretches_with_regular_season_misses"]
    management = counts["new_regular_season_injury_management_only"]
    opening = counts["new_regular_season_non_management_opening_stretches"]
    rates = {
        "tracker_entries_per_1000": counts["tracker_entries"] * 1000 / gp,
        "tracker_plus_new_per_1000": counts["tracker_plus_new_entries"] * 1000 / gp,
        "tracker_plus_new_regular_season_per_1000": (counts["tracker_entries"] + regular_additions) * 1000 / gp,
        "tracker_plus_new_excluding_management_additions_per_1000":
            (counts["tracker_entries"] + regular_additions - management) * 1000 / gp,
        "tracker_plus_new_excluding_management_and_opening_additions_per_1000":
            (counts["tracker_entries"] + regular_additions - management - opening) * 1000 / gp,
    }
    for category in ("medical", "injury"):
        baseline = [h for h in entries if h["games"] and h["cat"] in (MEDICAL if category == "medical" else {"injury"})]
        public = [r for r in records if r["regular_season_games_missed"]
                  and r["reason_category"] in (MEDICAL if category == "medical" else {"injury"})]
        counts[f"tracker_game_costing_{category}"] = len(baseline)
        counts[f"public_game_costing_{category}"] = len(public)
        counts[f"public_non_management_{category}"] = sum(not r["injury_management_only"] for r in public)
        counts[f"public_non_opening_{category}"] = sum(not r["at_team_season_start"] for r in public)
        counts[f"public_non_management_non_opening_{category}"] = sum(
            not r["at_team_season_start"] and not r["injury_management_only"] for r in public)
        rates[f"tracker_game_costing_{category}_per_1000_box_score_gp"] = len(baseline) * 1000 / gp
        for key in ("game_costing", "non_management", "non_opening", "non_management_non_opening"):
            rates[f"public_{key}_{category}_per_1000"] = counts[f"public_{key}_{category}"] * 1000 / gp
    print(json.dumps(dict(counts) | rates, indent=2))
    for pid, c in sorted(by_player.items()):
        if players[pid]["name"] in ("Stephen Curry", "LeBron James", "Nikola Jokić", "Nikola Jokic",
                                     "Tyrese Haliburton", "Jayson Tatum", "Luka Dončić", "Luka Doncic"):
            print(players[pid]["name"], dict(c))


def build(cache_only, season=DEFAULT_SEASON):
    box_games = {} if season.historical else {str(g["game_id"]): g for g in read(BOX)["games"]}
    players = {p["id"]: p for p in read(UNIVERSE)["players"]}
    games, teams, supplemental = load_games(box_games, cache_only, season)
    box, reports, urls, report_teams, names = observations(games, players, teams, cache_only, season)
    moves, move_urls = roster_moves(names, cache_only, season)
    game_dates = {g["id"]: g["date"] for g in games}
    # Box scores occasionally carry old roster lines even when a player
    # is under no NBA contract. The dated team release takes precedence.
    for name, team, left, joined, _ in season_roster_corrections(season):
        pid = names.get(name_key(name))
        for key in [k for k in box if k[1:] == (team, pid) and off_roster(game_dates[k[0]], left, joined)]:
            assert not box[key]["played"], f"Appearance during off-roster interval for {name}"
            del box[key]
        for key in [k for k in reports if k[1:] == (team, pid) and off_roster(k[0], left, joined)]:
            del reports[key]
    assignments = transfer_day_teams(box, reports, moves, game_dates, season)
    stints = roster_stints(games, box, reports, moves, assignments)
    records, played = make_stretches(games, players, box, reports, urls, stints, assignments)
    coverage = {
        "games_by_phase": dict(sorted(Counter(g["phase"] for g in games).items())),
        "box_score_game_ids_added": sorted(supplemental),
        "box_score_game_ids_excluded": sorted(box_games.keys() - {g["id"] for g in games}),
        "pool_players": len(players),
        "players_with_roster_evidence": len(stints),
        "players_with_a_regular_season_appearance": sum(phase == "regular" for _, phase in played),
        "player_games_played_by_phase": {phase: sum(n for (_, p), n in played.items() if p == phase)
                                        for phase in ("regular", "cup_final", "play_in", "playoffs")},
        "players_with_at_least_one_miss": len({r["player_id"] for r in records}),
        "game_days": len({g["date"] for g in games}),
        "game_days_with_nba_reports": len(urls),
        "game_days_without_nba_reports": sorted({g["date"] for g in games} - urls.keys()),
        "game_days_without_same_day_player_report_rows": sorted({g["date"] for g in games} - {d for d, _ in report_teams}),
        "team_games_with_player_report_rows": len(report_teams),
        "missed_games_with_inferred_roster_membership": sum(s["roster_evidence"] == "inferred_stint"
                                                            for r in records for s in r["sources"]),
        "stretches_by_reason": dict(sorted(Counter(r["reason_category"] for r in records).items())),
        "games_missed_by_reason": {category: sum(r["games_missed"] for r in records
                                                if r["reason_category"] == category)
                                   for category in sorted({r["reason_category"] for r in records})},
    }
    if season.historical:
        coverage["historical_players_outside_canonical_pool"] = sum(
            p.startswith(("espn_", "nba_report_")) for p in stints)
        coverage["historical_players_identified_by_report_name_only"] = sum(
            p.startswith("nba_report_") for p in stints)
    return {
        "schema_version": 1,
        "season": season.label,
        "sources": {
            "box_scores": SUMMARY if season.historical else str(BOX.relative_to(ROOT)),
            "espn_game_summary": SUMMARY,
            "nba_box_score_fallback": NBA_BOX_FALLBACK.get(season.label, {}),
            "espn_team_schedule": BASE + f"/teams/{{team}}/schedule?season={season.year}&seasontype={{stage}}",
            "espn_play_in_scoreboard": SCOREBOARD,
            "espn_transactions": move_urls,
            "trade_dates": str(TRADES.relative_to(ROOT)),
            "team_transaction_corrections": [
                {"player": name, "team": team, "off_roster_from": left, "rejoined": joined, "url": url}
                for name, team, left, joined, url in season_roster_corrections(season)
            ],
            "player_pool": str(UNIVERSE.relative_to(ROOT)),
            "nba_game_day_reports": urls,
        },
        "coverage": coverage,
        "players_without_roster_evidence": sorted(set(players) - stints.keys()),
        "stretches": records,
    }, players, teams, names, played


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", choices=SEASONS, default=DEFAULT_SEASON.label)
    parser.add_argument("--write", action="store_true", help="write the public-source JSON")
    parser.add_argument("--cache-only", action="store_true", help="avoid network calls")
    parser.add_argument("--compare-tracker", action="store_true", help="print aggregate comparison from the local tracker")
    args = parser.parse_args()
    season = SEASONS[args.season]
    dataset, players, teams, names, played = build(args.cache_only, season)
    print(json.dumps(dataset["coverage"], indent=2))
    if args.compare_tracker:
        compare_tracker(dataset["stretches"], players, names, played, teams, season)
    if args.write:
        # One stretch per line makes season-wide diffs easy to inspect.
        records = dataset.pop("stretches")
        header = json.dumps(dataset, ensure_ascii=False, indent=2)
        out = ROOT / f"data/research/injury_history_{season.label.replace('-', '_')}.json"
        pending = out.with_suffix(".json.tmp")
        with pending.open("w", encoding="utf-8") as stream:
            stream.write(header[:-2] + ',\n  "stretches": [\n')
            stream.write(",\n".join("    " + json.dumps(r, ensure_ascii=False) for r in records))
            stream.write("\n  ]\n}\n")
        pending.replace(out)
        print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
