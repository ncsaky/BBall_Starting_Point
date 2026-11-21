"""Evidence for folding the public 2025-26 injury stretches into real players' injury history, and for the history
weight with the fuller history (STAR-INJURIES, 2026-11-21).

    PYTHONPATH=src .venv/bin/python scripts/research/injury_history_foldin_check.py [--section all|counts|weight]

Sections:
1. counts: what scripts/build_injury_model.py does with each public stretch (classify_public_stretches), and the
   2025-26 history density per 1,000 regular-season games played against the tracker's 2023-24 and 2024-25.
2. management / openers: why "injury management only" stretches stay out, and which opening-night stretches continue an
   injury the tracker already has.
3. weight: out-of-sample checks of the history weight on 2025-26, a season the weight was not fitted on. Outcomes are
   the public file's new injuries (injury stretches costing a regular-season game, not injury management, not already
   underway at the team's opener, not a trade split), which is complete for that season. Exposure is box-score games
   played and minutes. The league level is left free, so only who gets hurt matters.
   a. whole season: history = the tracker before opening night (the same kind of history the weight was fitted on);
   b. second half (from 2026-01-15): history before that date from (i) the tracker alone, (ii) the tracker plus the
      added public stretches. If (ii) predicts who gets hurt better, the fold-in carries real information, and its
      best weight says how strongly the fuller history should count.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts/research"))
from nba_gm_data import injury_model as im  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.save import trait_values_by_player  # noqa: E402
import build_injury_model as builder  # noqa: E402
import top30_real_seasons as real  # noqa: E402

PUBLIC = ROOT / "data/research/injury_history_2025_26.json"
BOX = ROOT / "data/research/game_boxscores_2025_26.json"
TRACKER = ROOT / "data/research/bbi/tools/injury_player_history.json"
OPENER, CUT, REGULAR_END = date(2025, 10, 21), date(2026, 1, 15), date(2026, 4, 12)
GRID = [round(0.05 * k, 2) for k in range(0, 33)]


def load():
    c = load_app_canonical(ROOT)
    tracker = json.loads(TRACKER.read_text())
    stretches, status = builder.classify_public_stretches(tracker, {t["abbrev"]: t["name"] for t in c["teams"]})
    return c, tracker, stretches, status


def section_counts(c, tracker, stretches, status, doc):
    players = {p["id"] for p in c["players"]}
    print("== 1. What the builder does with the public 2025-26 stretches")
    counts = Counter(status.values())
    for key, n in counts.most_common():
        games = sum(s["games_missed"] for i, s in enumerate(stretches) if status[i] == key)
        print(f"   {key:12s} {n:5d} stretches, {games:6d} games missed")
    gp = doc["coverage"]["player_games_played_by_phase"]["regular"]
    tracked = sum(1 for h in tracker if h["season"] == "2025-26" and h.get("player_id") in players)
    added = sum(1 for i, s in enumerate(stretches) if status[i] == "added" and s["regular_season_games_missed"])
    print(f"   2025-26 entries per 1,000 regular-season games played: tracker {1000 * tracked / gp:.1f}; "
          f"tracker + added {1000 * (tracked + added) / gp:.1f} (tracker 2023-24 50.2, 2024-25 55.3)")
    added_players = Counter(s["player_id"] for i, s in enumerate(stretches) if status[i] == "added")
    print(f"   players gaining history: {len(added_players)}; most: "
          + ", ".join(f"{next(s['player'] for s in stretches if s['player_id'] == pid)} {n}"
                      for pid, n in added_players.most_common(8)))


def section_management(c, tracker, stretches, status):
    print("\n== 2a. Injury-management-only stretches")
    abbrev = {t["name"]: t["abbrev"] for t in c["teams"]}
    abbrev["LA Clippers"] = abbrev.get("Los Angeles Clippers", "LAC")
    days = defaultdict(set)
    for g in json.loads(BOX.read_text())["games"]:
        for t in g["teams"]:
            if t["display_name"] in abbrev:
                days[abbrev[t["display_name"]]].add(g["date"])
    all_games = sum(len(v) for v in days.values())
    second = sum(1 for ds in days.values() for d in ds if (date.fromisoformat(d) - timedelta(days=1)).isoformat() in ds)
    known = defaultdict(list)
    for h in tracker:
        part = builder.part_of(h)
        if part and part != "illness" and h.get("start") and h.get("player_id"):
            known[h["player_id"]].append((date.fromisoformat(h["start"][:10]), part))
    for s in stretches:
        if s["reason_category"] == "injury" and not s["injury_management_only"] and s["body_part"]:
            known[s["player_id"]].append((date.fromisoformat(s["first_game_missed"]), s["body_part"]))
    rows = defaultdict(Counter)
    for i, s in enumerate(stretches):
        if s["reason_category"] != "injury" or s["games_missed"] != 1 or s["at_team_season_start"]:
            continue
        key = "injury management only" if s["injury_management_only"] else "other one-game injuries"
        first = date.fromisoformat(s["first_game_missed"])
        rows[key]["n"] += 1
        rows[key]["second_night"] += (first - timedelta(days=1)).isoformat() in days.get(s["team"], set())
        rows[key]["known"] += any(p == s["body_part"] and 0 < (first - d).days <= 365 for d, p in known[s["player_id"]])
        rows[key]["tracker"] += status[i] == "tracker"
    print(f"   all team games: {second / all_games:.1%} are the second night of a back-to-back")
    for key, r in rows.items():
        print(f"   {key}: {r['n']} one-game stretches; second night of a back-to-back {r['second_night'] / r['n']:.1%}; "
              f"same part hurt in the past year {r['known'] / r['n']:.1%}; logged by the tracker {r['tracker'] / r['n']:.1%}")
    management = [s for i, s in enumerate(stretches) if s["injury_management_only"]]
    per = Counter(s["player"] for s in management)
    print(f"   {len(management)} management-only stretches ({sum(s['games_missed'] for s in management)} games) by "
          f"{len(per)} players; most: " + ", ".join(f"{k} {v}" for k, v in per.most_common(8)))
    print("\n== 2b. Stretches already underway at a team's opening night (injury, not management only)")
    for key in ("carried_in", "added", "tracker"):
        rows = [s for i, s in enumerate(stretches) if status[i] == key and s["at_team_season_start"]
                and s["reason_category"] == "injury"]
        print(f"   {key}: {len(rows)}: " + ", ".join(f"{s['player']} ({s['body_part']}, {s['games_missed']})"
                                                     for s in sorted(rows, key=lambda s: -s["games_missed"])))


def exposure(c):
    """Per canonical player id: list of (date, minutes) for regular-season games played."""
    by_espn = {str(p.get("espn_player_id")): p["id"] for p in c["players"] if p.get("espn_player_id")}
    out = defaultdict(list)
    for g in json.loads(BOX.read_text())["games"]:
        if g.get("phase") != "regular":
            continue
        for line in g["players"]:
            pid = by_espn.get(str(line.get("espn_player_id")))
            if pid and float(line.get("minutes") or 0) > 0:
                out[pid].append((date.fromisoformat(g["date"]), float(line["minutes"])))
    return out


def fresh(s, status_of):
    return (s["reason_category"] == "injury" and s["regular_season_games_missed"] > 0 and status_of in ("added", "tracker")
            and not s["at_team_season_start"] and s["body_part"] in builder.PARTS)


def weight_rows(c, model, history_of, played, outcomes, start, end):
    players = {p["id"]: p for p in c["players"]}
    traits = trait_values_by_player(c)
    prior = real.league_stats(real.espn_year("2025-26") - 1, False)
    order = sorted((k for k, v in prior.items() if v.get("gamesPlayed", 0) >= 30), key=lambda k: -real.game_score(prior[k]))
    stars = {k for k in order[:30]}
    rows = []
    for pid, games in played.items():
        games = [m for d, m in games if start <= d < end]
        p = players.get(pid)
        if len(games) < 10 or not p or not p.get("birthdate"):
            continue
        age = (start - date.fromisoformat(str(p["birthdate"])[:10])).days / 365.25
        minutes = sum(games) / len(games)
        hist = [(d, part) for d, part in history_of(pid) if d < start]
        e = {}
        for w in GRID:
            im.HISTORY_WEIGHT = w
            hz = im.part_hazards(model, {**p, "age": age}, traits.get(pid, {}), minutes, hist, start)
            e[w] = len(games) * sum(v for k, v in hz.items() if k != "illness")
        rows.append({"e": e, "n": outcomes.get(pid, 0), "star": str(p.get("espn_player_id")) in stars, "age": age,
                     "mpg": minutes})
    return rows


def loglik(rows, w):
    n = sum(r["n"] for r in rows)
    e = sum(r["e"][w] for r in rows)
    a = math.log(n / e)
    return sum(r["n"] * (a + math.log(r["e"][w])) - r["e"][w] * math.exp(a) for r in rows)


def profile(name, rows):
    ll = {w: loglik(rows, w) for w in GRID}
    best = max(ll, key=ll.get)
    inside = [w for w in GRID if ll[w] >= ll[best] - 1.353]
    print(f"   {name}: {len(rows)} players, {sum(r['n'] for r in rows)} new injuries; best weight {best:.2f} "
          f"(90% range {min(inside):.2f}-{max(inside):.2f}); log-likelihood vs best: "
          + ", ".join(f"{w:.2f} {ll[w] - ll[best]:+.1f}" for w in (0.0, 0.55, 0.75, 0.95, 1.0, 1.25)))
    for w in (0.55, 0.95):
        scale = sum(r["n"] for r in rows) / sum(r["e"][w] for r in rows)
        groups = {"stars (top 30 by 2024-25 Game Score)": lambda r: r["star"], "others 30+ min": lambda r: not r["star"]
                  and r["mpg"] >= 30, "under 20 min": lambda r: r["mpg"] < 20, "age 29+": lambda r: r["age"] >= 29,
                  "under 25": lambda r: r["age"] < 25}
        print(f"      real / expected at {w}: " + "; ".join(
            f"{k} {sum(r['n'] for r in rows if f(r)) / (scale * sum(r['e'][w] for r in rows if f(r))):.2f}"
            for k, f in groups.items()))
    return ll


def section_weight(c, tracker, stretches, status):
    print("\n== 3. History weight, out of sample on 2025-26")
    model = im.load_model(ROOT)
    original = im.HISTORY_WEIGHT
    played = exposure(c)
    tracked = defaultdict(list)
    for h in tracker:
        part = builder.part_of(h)
        if part and part != "illness" and h.get("start") and h.get("player_id"):
            tracked[h["player_id"]].append((date.fromisoformat(h["start"][:10]), part))
    def public(keep):
        out = defaultdict(list)
        for i, s in enumerate(stretches):
            if status[i] in keep:
                part = "illness" if s["reason_category"] == "illness" else s["body_part"]
                out[s["player_id"]].append((date.fromisoformat(s["first_game_missed"]), part))
        return out

    added = public({"added"})
    management = public({"management"})
    illness = public({"illness"})

    def outcomes(start, end):
        out = Counter()
        for i, s in enumerate(stretches):
            if fresh(s, status[i]) and start <= date.fromisoformat(s["first_game_missed"]) < end:
                out[s["player_id"]] += 1
        return out

    end = REGULAR_END + timedelta(days=1)
    season = weight_rows(c, model, lambda pid: tracked[pid], played, outcomes(OPENER, end), OPENER, end)
    profile("a. whole season, tracker history", season)
    second = outcomes(CUT, end)
    only = weight_rows(c, model, lambda pid: tracked[pid], played, second, CUT, end)
    both = weight_rows(c, model, lambda pid: tracked[pid] + added[pid], played, second, CUT, end)
    ll_only = profile("b(i). second half, tracker history only", only)
    ll_both = profile("b(ii). second half, tracker + added public stretches", both)
    print(f"   fold-in gain in log-likelihood (each at its best weight): {max(ll_both.values()) - max(ll_only.values()):+.1f}; "
          f"at 0.95: {ll_both[0.95] - ll_only[0.95]:+.1f}")
    print("\n   c. what else could go into the history (second half; best weight and log-likelihood vs b(ii) at its best)")
    best_both = max(ll_both.values())
    openers = {(s["player_id"], date.fromisoformat(s["first_game_missed"])) for i, s in enumerate(stretches)
               if status[i] == "added" and s["at_team_season_start"]}
    no_openers = {pid: [(d, p) for d, p in rows if (pid, d) not in openers] for pid, rows in added.items()}
    variants = (("+ injury-management-only stretches", lambda pid: tracked[pid] + added[pid] + management[pid]),
                ("+ illness stretches", lambda pid: tracked[pid] + added[pid] + illness[pid]),
                ("- opening-night stretches with no tracker trace", lambda pid: tracked[pid] + no_openers.get(pid, [])))
    for name, history_of in variants:
        rows = weight_rows(c, model, history_of, played, second, CUT, end)
        ll = {w: loglik(rows, w) for w in GRID}
        best = max(ll, key=ll.get)
        print(f"      {name}: best weight {best:.2f}, log-likelihood {ll[best] - best_both:+.1f}")
    print("\n   d. other cut dates (tracker + added before the cut; new injuries from the cut to the season's end)")
    for cut in (date(2025, 12, 1), date(2026, 3, 1)):
        rows_only = weight_rows(c, model, lambda pid: tracked[pid], played, outcomes(cut, end), cut, end)
        rows_both = weight_rows(c, model, lambda pid: tracked[pid] + added[pid], played, outcomes(cut, end), cut, end)
        for name, rows in (("tracker only", rows_only), ("tracker + added", rows_both)):
            ll = {w: loglik(rows, w) for w in GRID}
            best = max(ll, key=ll.get)
            inside = [w for w in GRID if ll[w] >= ll[best] - 1.353]
            print(f"      from {cut}, {name}: {sum(r['n'] for r in rows)} injuries, best weight {best:.2f} "
                  f"(90% range {min(inside):.2f}-{max(inside):.2f}), log-likelihood {ll[best]:.1f}; at 0.75 "
                  f"{ll[0.75] - ll[best]:+.1f}, at 0.95 {ll[0.95] - ll[best]:+.1f}")
    im.HISTORY_WEIGHT = original


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", default="all", choices=("all", "counts", "weight"))
    a = ap.parse_args()
    c, tracker, stretches, status = load()
    doc = json.loads(PUBLIC.read_text())
    if a.section in ("all", "counts"):
        section_counts(c, tracker, stretches, status, doc)
        section_management(c, tracker, stretches, status)
    if a.section in ("all", "weight"):
        section_weight(c, tracker, stretches, status)


if __name__ == "__main__":
    main()
