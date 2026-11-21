#!/usr/bin/env python3
"""What the complete public injury records say about the league's injury level (INJURY-ANCHOR, 2026-11-21).

    PYTHONPATH=src .venv/bin/python scripts/research/injury_anchor_measure.py [--model PATH] [--section all|league|bands|illness]

Sources: data/research/injury_history_{2023_24,2024_25,2025_26}.json (Codex; every missed game from official injury
reports and box scores) and the Basketball Index tracker (local only).

1. league: for each season, injury and illness stretches costing a regular-season game, per team and per 1,000
   regular-season appearances, with Codex's choices applied one at a time (injury-management-only stretches set aside,
   stretches already underway at the team's opener set aside), plus trade splits; illness share; length bands in
   regular-season games.
2. bands: the anchor population (the game's real players' seasons in the tracker panel, 10+ games) by minutes and age:
   new in-season injuries and illnesses per 82 games played, the tracker's game-costing entries for the same players,
   and what the model file predicts for those player-seasons (engine hazards, the history a new career starts with,
   times the share of draws that cost a game). Observed over predicted by band tests the minutes and age slopes.
3. illness: does counting a player's illnesses in his injury history predict his next injuries better? Poisson
   log-likelihood of new in-season injuries (illness aside) in the anchor seasons, with each part's level left free.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from nba_gm_data import injury_model as im  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.save import trait_values_by_player  # noqa: E402
import build_injury_model as builder  # noqa: E402

BANDS = ((1, "1"), (5, "2-5"), (10, "6-10"), (20, "11-20"), (10_000, "21+"))
MINUTES = ((10, "under 10"), (20, "10-20"), (30, "20-30"), (float("inf"), "30+"))
AGES = ((23, "under 23"), (26, "23-25"), (29, "26-28"), (32, "29-31"), (float("inf"), "32+"))


def band(value, bands):
    return next(label for upper, label in bands if value <= upper) if bands is BANDS else \
        next(label for upper, label in bands if value < upper)


def load_public():
    out = {}
    for season, path in builder.PUBLIC_HISTORIES.items():
        doc = json.loads(path.read_text())
        out[season] = doc
    return out


def section_league(public):
    print("== 1. Injury and illness stretches costing a regular-season game (all players, complete public records)")
    print("   season   | all  | -mgmt | -opener | -both | -both,-trade split (anchor) | per 1,000 apps (both) | illness % | "
          "1 / 2-5 / 6-10 / 11-20 / 21+ (anchor set, % of stretches)")
    totals = Counter()
    pooled_bands = Counter()
    for season, doc in public.items():
        stretches = doc["stretches"]
        apps = doc["coverage"]["player_games_played_by_phase"]["regular"]
        med = [s for s in stretches if s["reason_category"] in ("injury", "illness")
               and int(s["regular_season_games_missed"]) >= 1]
        all_ = len(med)
        no_mgmt = sum(1 for s in med if not s["injury_management_only"])
        no_open = sum(1 for s in med if not s["at_team_season_start"])
        both = sum(1 for s in med if not s["injury_management_only"] and not s["at_team_season_start"])
        new = builder.new_in_season(stretches)
        anchor = [stretches[i] for i in new]
        illness = sum(1 for s in anchor if s["reason_category"] == "illness")
        bands = Counter(band(int(s["regular_season_games_missed"]), BANDS) for s in anchor)
        pooled_bands.update(bands)
        totals.update({"all": all_, "mgmt": no_mgmt, "open": no_open, "both": both, "anchor": len(anchor),
                       "illness": illness, "apps": apps})
        print(f"   {season}  | {all_ / 30:4.1f} | {no_mgmt / 30:5.1f} | {no_open / 30:7.1f} | {both / 30:5.1f} | "
              f"{len(anchor) / 30:5.1f} | {1000 * both / apps:5.1f} | {100 * illness / len(anchor):4.1f} | "
              + " / ".join(f"{100 * bands[label] / len(anchor):4.1f}" for _, label in BANDS))
    n = len(public) * 30
    print(f"   pooled   | {totals['all'] / n:4.1f} | {totals['mgmt'] / n:5.1f} | {totals['open'] / n:7.1f} | "
          f"{totals['both'] / n:5.1f} | {totals['anchor'] / n:5.1f} | {1000 * totals['both'] / totals['apps']:5.1f} | "
          f"{100 * totals['illness'] / totals['anchor']:4.1f} | "
          + " / ".join(f"{100 * pooled_bands[label] / totals['anchor']:4.1f}" for _, label in BANDS))
    # Injuries alone (illness aside), for the length-band comparison with the engine's injury draws.
    for season, doc in public.items():
        stretches = doc["stretches"]
        new = builder.new_in_season(stretches)
        inj = [stretches[i] for i, part in new.items() if part != "illness"]
        ill = [stretches[i] for i, part in new.items() if part == "illness"]
        b = Counter(band(int(s["regular_season_games_missed"]), BANDS) for s in inj)
        bi = Counter(band(int(s["regular_season_games_missed"]), BANDS) for s in ill)
        lost = sum(int(stretches[i]["regular_season_games_missed"]) for i in new)
        print(f"   {season} games lost per team to the anchor set: {lost / 30:5.1f}; to every injury or illness stretch: "
              f"{sum(int(s['regular_season_games_missed']) for s in stretches if s['reason_category'] in ('injury', 'illness')) / 30:5.1f}")
        print(f"   {season} injuries alone {len(inj) / 30:4.1f}/team: " +
              " / ".join(f"{100 * b[label] / len(inj):4.1f}" for _, label in BANDS) +
              f" | illness {len(ill) / 30:4.1f}/team: " + " / ".join(f"{100 * bi[label] / len(ill):4.1f}" for _, label in BANDS))


def engine_history(tracker, public, team_names):
    """(date, part) injury history as a new career starts with it: tracker injuries plus the public stretches the
    tracker lacks (illness aside). Also the illness history (tracker plus every public illness stretch) for section 3."""
    history, illness = defaultdict(list), defaultdict(list)
    for h in tracker:
        part = builder.part_of(h)
        if part and h.get("player_id") and h.get("start"):
            (illness if part == "illness" else history)[h["player_id"]].append((date.fromisoformat(h["start"][:10]), part))
    for season, path in builder.PUBLIC_HISTORIES.items():
        stretches, status = builder.classify_public_stretches(tracker, team_names, path)
        for pid, entries in builder.public_history_entries(stretches, status).items():
            history[pid].extend((date.fromisoformat(e[0]), e[1]) for e in entries)
        for index, s in enumerate(stretches):
            if status.get(index) == "illness":
                illness[s["player_id"]].append((date.fromisoformat(s["first_game_missed"]), "illness"))
    return history, illness


def panel(canonical, public, tracker):
    """Anchor population: (pid, season, gp, minutes per game, age, player dict) for the game's real players with 10+
    games in the tracker panel, and their new in-season injuries by part."""
    players = {p["id"]: p for p in canonical["players"]}
    rows = []
    for r in builder.rows("injury_player_seasons.json"):
        pid = r.get("player_id")
        if r["season"] not in public or pid not in players or (r.get("gp") or 0) < 10:
            continue
        birth = players[pid].get("birthdate") or players[pid].get("birth_date")
        if not birth:
            continue
        age = (builder.season_start(r["season"]) - date.fromisoformat(str(birth)[:10])).days / 365.25
        rows.append((pid, r["season"], r["gp"], (r.get("poss") or 0) / r["gp"] / im.POSSESSIONS_PER_MINUTE, age))
    keys = {(row[0], row[1]) for row in rows}
    new = defaultdict(Counter)
    for season, doc in public.items():
        stretches = doc["stretches"]
        for index, part in builder.new_in_season(stretches).items():
            key = (stretches[index]["player_id"], season)
            if key in keys:
                new[key][part or "unknown"] += 1
    tracked = Counter((h.get("player_id"), h["season"]) for h in tracker
                      if h.get("cat") in ("injury", "illness") and int(h.get("games") or 0) >= 1)
    return rows, new, tracked


def section_bands(canonical, public, tracker, model):
    print("\n== 2. Anchor population by minutes and age: per 82 games played")
    players = {p["id"]: p for p in canonical["players"]}
    traits = trait_values_by_player(canonical)
    injuries, illness = engine_history(tracker, public, {t["abbrev"]: t["name"] for t in canonical["teams"]})
    history = {pid: injuries.get(pid, []) + illness.get(pid, []) for pid in set(injuries) | set(illness)}
    if not model["rate_fit"].get("illness_in_history"):
        history = injuries   # a model anchored before illness joined the history (the engine then left it out)
    rows, new, tracked = panel(canonical, public, tracker)
    shares = {part: info.get("game_share", 1.0) for part, info in model["parts"].items()}
    for title, index, bands in (("minutes", 3, MINUTES), ("age", 4, AGES)):
        stats = defaultdict(lambda: Counter())
        for pid, season, gp, mpg, age in rows:
            label = band((mpg, age)[index - 3], bands)
            for s in ("all", season):
                key = (s, label)
                stats[key]["games"] += gp
                stats[key]["new"] += sum(new[(pid, season)].values())
                stats[key]["tracker"] += tracked[(pid, season)]
                player = dict(players[pid], age=age)
                h = im.part_hazards(model, player, traits.get(pid, {}), mpg, history.get(pid, []),
                                    builder.season_start(season))
                stats[key]["pred"] += gp * sum(v * shares.get(part, 1.0) for part, v in h.items())
        print(f"   by {title}: complete new (per 82) | tracker game-costing (per 82) | model predicts | observed/predicted"
              f" | per season complete: " + ", ".join(public))
        for _, label in bands:
            a = stats[("all", label)]
            per = lambda c, k: 82 * c[k] / c["games"] if c["games"] else float("nan")  # noqa: E731
            seasons = ", ".join(f"{per(stats[(s, label)], 'new'):.2f}" for s in public)
            print(f"   {label:9s} {a['games']:6d} games | {per(a, 'new'):.2f} | {per(a, 'tracker'):.2f} | {per(a, 'pred'):.2f}"
                  f" | {a['new'] / a['pred']:.2f} | {seasons}")
    total_games = sum(r[2] for r in rows)
    total_new = sum(sum(c.values()) for c in new.values())
    print(f"   anchor population: {len(rows)} player-seasons, {total_games} games, {total_new} new in-season injuries "
          f"and illnesses ({1000 * total_new / total_games:.1f} per 1,000 games)")


def section_illness(canonical, public, tracker, model):
    print("\n== 3. Illness in the injury history: who gets hurt next (injuries only, each part's level free)")
    players = {p["id"]: p for p in canonical["players"]}
    traits = trait_values_by_player(canonical)
    history, illness = engine_history(tracker, public, {t["abbrev"]: t["name"] for t in canonical["teams"]})
    rows, new, _ = panel(canonical, public, tracker)
    for label, with_illness in (("illness left out (now)", False), ("illness counted in the history", True)):
        pred = defaultdict(float)
        obs = defaultdict(float)
        cells = []
        for pid, season, gp, mpg, age in rows:
            h_list = history.get(pid, []) + (illness.get(pid, []) if with_illness else [])
            player = dict(players[pid], age=age)
            h = im.part_hazards(model, player, traits.get(pid, {}), mpg, h_list, builder.season_start(season))
            for part, v in h.items():
                mu = gp * v
                y = new[(pid, season)].get(part, 0)
                cells.append((part, mu, y))
                pred[part] += mu
                obs[part] += y
        ll = Counter()
        for part, mu, y in cells:
            m = mu * obs[part] / pred[part] if pred[part] else mu
            ll["illness" if part == "illness" else "injuries"] += y * math.log(m) - m if m > 0 else 0.0
        print(f"   {label:34s} log-likelihood: next injuries {ll['injuries']:10.1f}, next illnesses {ll['illness']:8.1f}")
    print("   (The slopes were fit with illness counted in the history; the engine has left it out.)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / im.MODEL_FILE))
    ap.add_argument("--section", default="all")
    a = ap.parse_args()
    public = load_public()
    tracker = builder.rows("injury_player_history.json")
    if a.section in ("all", "league"):
        section_league(public)
    if a.section in ("all", "bands", "illness"):
        canonical = load_app_canonical(ROOT)
        model = json.loads(Path(a.model).read_text())
        if a.section in ("all", "bands"):
            section_bands(canonical, public, tracker, model)
        if a.section in ("all", "illness"):
            section_illness(canonical, public, tracker, model)


if __name__ == "__main__":
    main()
