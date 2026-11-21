"""Why do the best players miss more games than the injury model gives them? (TOP30-GAMES, 2026-11-20)

    PYTHONPATH=src .venv/bin/python scripts/research/top30_causes.py

Uses the Basketball Index injury tracker (local only) for 2021-22 to 2025-26 and ESPN's league stats (cached by
top30_real_seasons.py). Stars each season: the top 30 by the previous season's Game Score per game, as in
top30_real_seasons.py. Comparison groups: every other player, and other heavy-minute players (28+ minutes a game that
season).

(a) Length on the same diagnosis: within each tracker diagnosis, stars' days out against others' (logged returns only).
(b) How often they get hurt: tracker absences of 1+ games per 82 games played, against the injury model's own prediction
    for the same player-seasons (their ages, bodies, minutes and injury histories).
(c) Short multi-game stretches: how stars' absences split by length against others'.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
import math
from pathlib import Path
import random
from statistics import mean, median
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/research"))
from nba_gm_data import injury_model as im  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.save import trait_values_by_player  # noqa: E402
import top30_real_seasons as real  # noqa: E402

SEASONS = real.SEASONS
HEAVY_MPG = 28.0


def rows(name: str) -> list[dict]:
    return json.loads((ROOT / "data/research/bbi/tools" / name).read_text())


def load():
    canonical = load_app_canonical(ROOT)
    players = {p["id"]: p for p in canonical["players"]}
    espn_of = {pid: str(p.get("espn_player_id")) for pid, p in players.items() if p.get("espn_player_id")}
    stars, mpg, gscore = {}, {}, {}
    for season in SEASONS:
        stars[season] = set(real.pick_top30(season, False, "prior"))
        stats = real.league_stats(real.espn_year(season), False)
        mpg[season] = {pid: r.get("avgMinutes", 0.0) for pid, r in stats.items()}
        gscore[season] = {pid: real.game_score(r) for pid, r in stats.items() if r.get("gamesPlayed", 0) >= 20}
    return canonical, players, espn_of, stars, mpg, gscore


def group_of(espn: str | None, season: str, stars, mpg) -> str:
    if not espn:
        return "unknown"
    if espn in stars[season]:
        return "star"
    return "heavy" if mpg[season].get(espn, 0.0) >= HEAVY_MPG else "other"


def logged(h: dict) -> bool:
    return "censored" not in str(h.get("flags") or "") and int(h.get("days") or 0) >= 1


def within_label(entries: list[dict], a: str, b: str) -> dict:
    """Mean log(days) difference, a against b, within diagnoses that both have; weights n_a*n_b/(n_a+n_b)."""
    by = defaultdict(lambda: defaultdict(list))
    for e in entries:
        by[e["label"]][e["group"]].append(math.log(max(1, e["days"])))
    num = den = 0.0
    labels = 0
    na = 0
    for label, g in by.items():
        xa, xb = g.get(a, []), g.get(b, [])
        if not xa or not xb:
            continue
        w = len(xa) * len(xb) / (len(xa) + len(xb))
        num += w * (mean(xa) - mean(xb))
        den += w
        labels += 1
        na += len(xa)
    return {"ratio": math.exp(num / den) if den else None, "labels": labels, "n": na}


def boot(entries: list[dict], a: str, b: str, reps: int = 400) -> tuple[float, float]:
    by_player = defaultdict(list)
    for e in entries:
        by_player[e["pid"]].append(e)
    keys = sorted(by_player)
    rng = random.Random(7)
    vals = []
    for _ in range(reps):
        sample = [e for k in (rng.choice(keys) for _ in keys) for e in by_player[k]]
        r = within_label(sample, a, b)["ratio"]
        if r:
            vals.append(r)
    vals.sort()
    return vals[int(0.05 * len(vals))], vals[int(0.95 * len(vals))]


def main() -> None:
    canonical, players, espn_of, stars, mpg, gscore = load()
    history = rows("injury_player_history.json")
    # ---- (a) days out on the same diagnosis -------------------------------------------------------------------------
    entries = []
    for h in history:
        if (h.get("cat") != "injury" or not h.get("player_id") or not ("2021-22" <= h["season"] <= "2025-26")
                or not logged(h)):
            continue
        g = group_of(espn_of.get(h.get("player_id")), h["season"], stars, mpg)
        entries.append({"pid": h["player_id"], "label": h.get("label") or h.get("part"), "part": h.get("part"),
                        "days": int(h["days"]), "games": int(h.get("games") or 0), "group": g, "season": h["season"]})
    print("(a) Days out on the same diagnosis, logged returns 2021-22 to 2025-26 (injuries, not illness)")
    for grp in ("star", "heavy", "other"):
        xs = [e["days"] for e in entries if e["group"] == grp]
        print(f"   {grp:6} entries {len(xs):5}  median days {median(xs)}  mean {mean(xs):.1f}  "
              f"share 1 game {sum(1 for x in xs if x // 2 == 1) / len(xs):.0%}  2-10 games "
              f"{sum(1 for x in xs if 2 <= x // 2 <= 10) / len(xs):.0%}  11+ {sum(1 for x in xs if x // 2 > 10) / len(xs):.0%}")
    for a, b in (("star", "heavy"), ("star", "other"), ("heavy", "other")):
        r = within_label(entries, a, b)
        lo, hi = boot(entries, a, b)
        print(f"   {a} vs {b}: same-diagnosis ratio of days x{r['ratio']:.2f} (90% {lo:.2f}-{hi:.2f}), "
              f"{r['labels']} diagnoses, {r['n']} {a} entries")
    # Same, entries that cost at least one game only (the sim's recovery pool includes 0-game entries too).
    costly = [e for e in entries if e["days"] >= 2]
    for a, b in (("star", "heavy"), ("star", "other")):
        r = within_label(costly, a, b)
        lo, hi = boot(costly, a, b)
        print(f"   1+ game entries, {a} vs {b}: x{r['ratio']:.2f} (90% {lo:.2f}-{hi:.2f}), {r['n']} {a} entries")
    # Star-ness as a continuous rank: top 10 / 11-30 / 31-60.
    rank = {}
    for season in SEASONS:
        prior = real.league_stats(real.espn_year(season) - 1, False)
        ranked = sorted((pid for pid, r in prior.items() if r.get("gamesPlayed", 0) >= 30),
                        key=lambda pid: -real.game_score(prior[pid]))
        rank[season] = {pid: i + 1 for i, pid in enumerate(ranked)}
    for e in entries:
        espn = espn_of.get(e["pid"])
        k = rank[e["season"]].get(espn, 999)
        e["tier"] = "top10" if k <= 10 else "11-30" if k <= 30 else "31-60" if k <= 60 else "61-120" if k <= 120 else "rest"
    tiers = [dict(e, group=e["tier"]) for e in entries]
    for t in ("top10", "11-30", "31-60", "61-120"):
        r = within_label(tiers, t, "rest")
        print(f"   tier {t:6} vs players ranked 121+: x{r['ratio']:.2f} ({r['n']} entries)")
    # By part (pooled labels within part).
    print("   by part, stars vs heavy (same diagnosis):")
    for part in ("ankle", "knee", "foot", "back", "hamstring", "calf", "hip", "achilles"):
        sub = [e for e in entries if e["part"] == part]
        r = within_label(sub, "star", "heavy")
        if r["ratio"]:
            print(f"      {part:10} x{r['ratio']:.2f} ({r['n']} star entries)")
    # The model's per-player recovery speed for stars.
    model = im.load_model(ROOT)
    pct = model.get("player_recovery_pct") or {}
    for season in SEASONS[-1:]:
        star_ids = [pid for pid, e in espn_of.items() if e in stars[season]]
        print(f"   model's per-player recovery % (Basketball Index), {season} stars: mean "
              f"{mean(pct.get(p, 0.0) for p in star_ids):+.1f}%, heavy others "
              f"{mean(pct.get(p, 0.0) for p, e in espn_of.items() if group_of(e, season, stars, mpg) == 'heavy'):+.1f}%")

    # ---- (b) how often they get hurt --------------------------------------------------------------------------------
    traits = trait_values_by_player(canonical)
    hist = defaultdict(list)
    for h in history:
        if h.get("cat") in ("injury", "illness") and h.get("start"):
            hist[h.get("player_id")].append(h)
    ps_rows, rank_prior = [], {}
    agg = defaultdict(lambda: [0, 0, 0.0, 0.0])   # group -> games, absences 1+ games, model expected 1+ games, minutes
    for r in rows("injury_player_seasons.json"):
        pid = r.get("player_id")
        if not ("2021-22" <= r["season"] <= "2024-25") or (r.get("gp") or 0) < 20 or pid not in players:
            continue
        p = players[pid]
        if not p.get("birthdate"):
            continue
        espn = espn_of.get(pid)
        m = mpg[r["season"]].get(espn) or (r.get("poss") or 0) / r["gp"] / im.POSSESSIONS_PER_MINUTE
        grp = group_of(espn, r["season"], stars, mpg)
        if grp == "other" and m < 20:
            grp = "under 20"
        start = date(int(r["season"][:4]), 10, 20)
        age = (start - date.fromisoformat(str(p["birthdate"])[:10])).days / 365.25
        t = traits.get(pid, {})
        past = [(date.fromisoformat(h["start"][:10]), im.event_part({"body_part": h.get("part")}))
                for h in hist.get(pid, []) if h.get("cat") == "injury" and h["start"][:10] < start.isoformat()]
        hz = sum(im.part_hazards(model, {**p, "age": age}, t, m, past, start).values())
        a = agg[grp]
        a[0] += r["gp"]
        mine = [int(h.get("games") or 0) for h in hist.get(pid, []) if h["season"] == r["season"]]
        a[1] += sum(1 for x in mine if x >= 1)
        a[2] += r["gp"] * hz * im.LEAGUE_RATE_SCALE
        a[3] += m * r["gp"]
        st = real.league_stats(real.espn_year(r["season"]), False).get(espn) or {}
        onball = (st.get("avgFieldGoalsAttempted", 0) + 0.44 * st.get("avgFreeThrowsAttempted", 0)
                + st.get("avgTurnovers", 0)) / max(1.0, m) * 36
        prior = real.league_stats(real.espn_year(r["season"]) - 1, False)
        ranked_prior = rank_prior.setdefault(r["season"], {k: i + 1 for i, k in enumerate(sorted(
            (k for k, v in prior.items() if v.get("gamesPlayed", 0) >= 30), key=lambda k: -real.game_score(prior[k])))})
        ps_rows.append({"group": grp, "mpg": m, "gp": r["gp"], "exp": r["gp"] * hz, "load36": onball,
                        "rank": ranked_prior.get(espn, 999), "n1": sum(1 for x in mine if x == 1),
                        "n2_10": sum(1 for x in mine if 2 <= x <= 10), "n11": sum(1 for x in mine if x >= 11),
                        "g2_10": sum(x for x in mine if 2 <= x <= 10), "g11": sum(x for x in mine if x >= 11)})
    print("\n(b) Absences of 1+ games per 82 games played, tracker 2021-22 to 2024-25, against the model's prediction")
    for grp in ("star", "heavy", "other", "under 20"):
        g, n, exp, mins = agg[grp]
        if g:
            print(f"   {grp:8} games {g:6}  mpg {mins / g:4.1f}  real {82 * n / g:.2f}  model {82 * exp / g:.2f}  "
                  f"real/model {n / exp:.2f}")

    def show(label, sub):
        g = sum(x["gp"] for x in sub)
        e = sum(x["exp"] for x in sub)
        if not g:
            return
        n = sum(x["n1"] + x["n2_10"] + x["n11"] for x in sub)
        print(f"   {label:34} seasons {len(sub):4} games {g:6} | per 82 played: 1-game {82 * sum(x['n1'] for x in sub) / g:.2f}"
              f"  2-10 {82 * sum(x['n2_10'] for x in sub) / g:.2f} ({82 * sum(x['g2_10'] for x in sub) / g:.1f} games)"
              f"  11+ {82 * sum(x['n11'] for x in sub) / g:.2f} ({82 * sum(x['g11'] for x in sub) / g:.1f} games)"
              f" | all / model {n / e:.2f}")
    print("   By group and absence length (games missed per 82 played in brackets):")
    for grp in ("star", "heavy", "other", "under 20"):
        show(grp, [x for x in ps_rows if x["group"] == grp])
    print("   Same minutes, star or not (28+ minutes a game):")
    for lo, hi in ((28, 32), (32, 35), (35, 50)):
        for s in (True, False):
            show(f"{lo}-{hi} min, {'star' if s else 'not star'}",
                 [x for x in ps_rows if lo <= x["mpg"] < hi and (x["group"] == "star") == s])
    print("   Players at 28+ minutes by previous-season Game Score rank:")
    for lo, hi in ((1, 10), (11, 30), (31, 60), (61, 120), (121, 999), (999, 10_000)):
        show(f"rank {lo}-{hi if hi < 999 else 'unranked' if lo == 999 else '+'}",
             [x for x in ps_rows if x["mpg"] >= 28 and lo <= x["rank"] <= hi])
    print("   Players at 28+ minutes by on-ball load (shots, free-throw trips and turnovers per 36 minutes), terciles:")
    heavy_rows = sorted((x for x in ps_rows if x["mpg"] >= 28), key=lambda x: x["load36"])
    k = len(heavy_rows) // 3
    for name, sub in (("low load", heavy_rows[:k]), ("middle load", heavy_rows[k:2 * k]), ("high load", heavy_rows[2 * k:])):
        show(f"{name} ({mean(x['load36'] for x in sub):.1f}/36)", sub)
        show(f"   {name}, stars excluded", [x for x in sub if x["group"] != "star"])

    # ---- (c) absence lengths for stars --------------------------------------------------------------------------------
    print("\n(c) Tracker absences of 1+ games by length, share (injury and illness, logged or not)")
    for grp in ("star", "heavy", "other"):
        xs = [int(h.get("games") or 0) for h in history if h.get("cat") in ("injury", "illness")
              and "2021-22" <= h["season"] <= "2024-25"
              and group_of(espn_of.get(h.get("player_id")), h["season"], stars, mpg) == grp and int(h.get("games") or 0) >= 1]
        print(f"   {grp:6} n {len(xs):5}  1: {sum(x == 1 for x in xs) / len(xs):.0%}  2-5: "
              f"{sum(2 <= x <= 5 for x in xs) / len(xs):.0%}  6-10: {sum(6 <= x <= 10 for x in xs) / len(xs):.0%}  "
              f"11-20: {sum(11 <= x <= 20 for x in xs) / len(xs):.0%}  21+: {sum(x > 20 for x in xs) / len(xs):.0%}")


if __name__ == "__main__":
    main()
