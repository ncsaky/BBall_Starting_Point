"""Four seasons of injuries in a row (health only, fixed rosters, ages fixed), so a player's own simulated injuries feed
his later risk. Checks that the league rate stays steady from season to season and how the 30 best-rated players'
risk moves (TOP30-GAMES, 2026-11-20).

    PYTHONPATH=src .venv/bin/python scripts/research/injury_multiseason_check.py [--seed 17] [--model PATH --weight W]
        [--sim-weight W] [--evidence PATH]

--model/--weight compare another model file and real-history weight (a model file is anchored to one weight, so pass
the matching file). --sim-weight sets the weight for the game's own draws (injury_model.SIMULATED_HISTORY_WEIGHT,
STAR-INJURIES); --evidence another per-player evidence file.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from pathlib import Path
from statistics import mean
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from nba_gm_data import health, save  # noqa: E402
from nba_gm_data import injury_model as im  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.save import trait_values_by_player  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--model")
    ap.add_argument("--weight", type=float, help="history weight for real recorded injuries")
    ap.add_argument("--sim-weight", type=float, help="history weight for the game's own draws (default: --weight)")
    ap.add_argument("--seasons", type=int, default=4)
    ap.add_argument("--evidence", help="per-player evidence file (default: the engine's)")
    a = ap.parse_args()
    if a.model:
        im.MODEL_FILE = str(Path(a.model).resolve().relative_to(ROOT))
    if a.evidence:
        im.EVIDENCE_FILE = str(Path(a.evidence).resolve().relative_to(ROOT))
    if a.weight is not None:
        im.HISTORY_WEIGHT = a.weight
        if a.sim_weight is None:
            im.SIMULATED_HISTORY_WEIGHT = a.weight
    if a.sim_weight is not None:
        im.SIMULATED_HISTORY_WEIGHT = a.sim_weight
    canonical = load_app_canonical(ROOT)
    canonical["player_health_states"] = []
    canonical["injury_events"] = []
    players = {p["id"]: p for p in canonical["players"]}
    traits = trait_values_by_player(canonical)
    overall = {pid: save.player_attribute_summary(canonical, pid)["overall"] for pid, p in players.items()
               if p.get("team_id") and not p.get("_inactive_player")}
    top30 = sorted(overall, key=lambda pid: -overall[pid])[:30]
    teams = len({p["team_id"] for p in players.values() if p.get("team_id")})
    model = im.load_model(ROOT)
    events_all: list[dict] = []
    print(f"history weight {im.HISTORY_WEIGHT}, game's own draws {im.SIMULATED_HISTORY_WEIGHT}, model {im.MODEL_FILE}, "
          f"evidence {im.EVIDENCE_FILE}")
    for k in range(a.seasons):
        year = 2026 + k
        season = f"{year}-{str(year + 1)[2:]}"
        games = save.generate_future_schedule(ROOT, season, year)["games"]
        on = date(year, 10, 20)
        chance = mean(82 * sum(im.part_hazards(model, players[pid], traits.get(pid, {}), 33.0,
                                               im.player_history(model, pid, events_all), on).values()) for pid in top30)
        t0 = perf_counter()
        r = health.simulate_health(ROOT, canonical, games[0]["gameDate"], games[-1]["gameDate"], seed=a.seed + k,
                                   schedule=games, season_schedule=games)
        secs = perf_counter() - t0
        ev = [e for e in r["events"] if int(e.get("expected_games_missed") or 0) >= 1]
        events_all.extend(r["events"])
        canonical["injury_events"] = list(events_all)
        # Next season starts fresh except injuries that run past opening night (fixed rosters, nobody ages).
        canonical["player_health_states"] = r["final_states"]
        top_ev = [e for e in ev if e["player_id"] in top30]
        print(f"{season}: spells costing a game {len(ev) / teams:5.1f} per team | top 30: model chance per 82 at 33 "
              f"minutes {chance:4.2f} at the start, spells {len(top_ev) / 30:4.2f} each, games {sum(int(e['expected_games_missed']) for e in top_ev) / 30:5.1f} each"
              f" | {secs:4.1f} s")


if __name__ == "__main__":
    main()
