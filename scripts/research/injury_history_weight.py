"""How much should a player's own injury history count? Profile fit of the engine's history weight against what really
happened (TOP30-GAMES, 2026-11-20).

    PYTHONPATH=src .venv/bin/python scripts/research/injury_history_weight.py

For each real player-season 2021-22 to 2024-25 (Basketball Index tracker, local only; 20+ games played), the injury
model's expected tracker entries use his age, body, minutes and injury history before that season, with the history
terms multiplied by a weight w (the engine's HISTORY_WEIGHT). For each w the script reports the Poisson log-likelihood of
what happened (league level left free, so only who gets hurt matters), and what is left over in three directions the
model should already explain: on-ball load (points/1.15 + turnovers per 36, ESPN), age and minutes. It also splits
real/expected by the previous season's Game Score rank (the stars) and age band.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
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
from build_injury_model import poisson_ridge  # noqa: E402
import top30_real_seasons as real  # noqa: E402

WEIGHTS = (0.0, 0.3, 0.55, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5)


def load_rows(model) -> list[dict]:
    c = load_app_canonical(ROOT)
    players = {p["id"]: p for p in c["players"]}
    espn_of = {pid: str(p.get("espn_player_id")) for pid, p in players.items() if p.get("espn_player_id")}
    traits = trait_values_by_player(c)
    hist = defaultdict(list)
    for h in json.loads((ROOT / "data/research/bbi/tools/injury_player_history.json").read_text()):
        if h.get("cat") in ("injury", "illness") and h.get("start") and h.get("player_id"):
            hist[h["player_id"]].append(h)
    ranks = {}
    out = []
    for r in json.loads((ROOT / "data/research/bbi/tools/injury_player_seasons.json").read_text()):
        pid = r.get("player_id")
        if not ("2021-22" <= r["season"] <= "2024-25") or (r.get("gp") or 0) < 20 or pid not in players:
            continue
        p = players[pid]
        st = real.league_stats(real.espn_year(r["season"]), False).get(espn_of.get(pid))
        if not p.get("birthdate") or not st or st.get("avgMinutes", 0) <= 0:
            continue
        if r["season"] not in ranks:
            prior = real.league_stats(real.espn_year(r["season"]) - 1, False)
            order = sorted((k for k, v in prior.items() if v.get("gamesPlayed", 0) >= 30), key=lambda k: -real.game_score(prior[k]))
            ranks[r["season"]] = {k: i + 1 for i, k in enumerate(order)}
        m = st["avgMinutes"]
        start = date(int(r["season"][:4]), 10, 20)
        age = (start - date.fromisoformat(str(p["birthdate"])[:10])).days / 365.25
        past = [(date.fromisoformat(h["start"][:10]), im.event_part({"body_part": h.get("part")}))
                for h in hist[pid] if h.get("cat") == "injury" and h["start"][:10] < start.isoformat()]
        e = {}
        for w in WEIGHTS:
            im.HISTORY_WEIGHT = w
            e[w] = r["gp"] * sum(im.part_hazards(model, {**p, "age": age}, traits.get(pid, {}), m, past, start).values())
        out.append({"e": e, "n": sum(1 for h in hist[pid] if h["season"] == r["season"]),
                    "n1": sum(1 for h in hist[pid] if h["season"] == r["season"] and int(h.get("games") or 0) >= 1),
                    "mpg": m, "age": age, "gp": r["gp"], "rank": ranks[r["season"]].get(espn_of.get(pid), 999),
                    "load": (st.get("avgPoints", 0) / 1.15 + st.get("avgTurnovers", 0)) / m * 36})
    return out


def loglik(rows, w, target):
    n = sum(r[target] for r in rows)
    e = sum(r["e"][w] for r in rows)
    a = math.log(n / e)
    return sum(r[target] * (a + math.log(r["e"][w])) - r["e"][w] * math.exp(a) for r in rows)


def residual_terms(rows, w, target):
    lw = sum(r["gp"] for r in rows)
    mu = sum(r["load"] * r["gp"] for r in rows) / lw
    sd = math.sqrt(sum(r["gp"] * (r["load"] - mu) ** 2 for r in rows) / lw)
    X = [[1.0, (r["load"] - mu) / sd, (r["age"] - 27) / 4, (r["mpg"] - 25) / 7] for r in rows]
    b = poisson_ridge(X, [r[target] for r in rows], [r["e"][w] for r in rows], [0.0], lam=0.0)
    return b[1:]


def main() -> None:
    model = im.load_model(ROOT)
    original = im.HISTORY_WEIGHT
    rows = load_rows(model)
    im.HISTORY_WEIGHT = original
    print(f"player-seasons {len(rows)}, tracker entries {sum(r['n'] for r in rows)}, absences of 1+ games "
          f"{sum(r['n1'] for r in rows)}")
    for target, name in (("n", "all entries"), ("n1", "absences of 1+ games")):
        print(f"\n{name}: history weight | log-likelihood vs best | left over per sd of on-ball load, per 4 years of age, "
              "per 7 minutes")
        lls = {w: loglik(rows, w, target) for w in WEIGHTS}
        best = max(lls.values())
        for w in WEIGHTS:
            b = residual_terms(rows, w, target)
            print(f"   {w:4.2f} | {lls[w] - best:8.1f} | load x{math.exp(b[0]):.3f}  age x{math.exp(b[1]):.3f}  "
                  f"minutes x{math.exp(b[2]):.3f}")
    print("\nreal / expected (league level matched), absences of 1+ games")
    groups = {
        "Game Score rank 1-30 (stars)": lambda r: r["rank"] <= 30,
        "rank 31-120": lambda r: 30 < r["rank"] <= 120,
        "rest": lambda r: r["rank"] > 120,
        "age under 25": lambda r: r["age"] < 25,
        "age 25-28": lambda r: 25 <= r["age"] < 29,
        "age 29-31": lambda r: 29 <= r["age"] < 32,
        "age 32+": lambda r: r["age"] >= 32,
        "on-ball load top third": lambda r: r["load"] >= sorted(x["load"] for x in rows)[2 * len(rows) // 3],
    }
    for w in (0.55, 1.0):
        scale = sum(r["n1"] for r in rows) / sum(r["e"][w] for r in rows)
        print(f"   history weight {w}: " + "; ".join(
            f"{name} {sum(r['n1'] for r in rows if f(r)) / (scale * sum(r['e'][w] for r in rows if f(r))):.2f}"
            for name, f in groups.items()))


if __name__ == "__main__":
    main()
