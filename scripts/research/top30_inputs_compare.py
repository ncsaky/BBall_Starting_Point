"""Who are the stars, and what does the injury model see? Real top-30 player-seasons 2021-22 to 2024-25 against the
game's 2026-27 top 30 (TOP30-GAMES, 2026-11-20).

    PYTHONPATH=src .venv/bin/python scripts/research/top30_inputs_compare.py SIM_PREFIX

For each group: age, minutes, the model's per-82 injury chance (all tracker-style entries) at the group's own minutes and
at 33 minutes, and the decayed injury-history count the model reads at the season start. The sim's stars start
2026-27 with the tracker's 2025-26 season, which logged about a third as many entries per game as 2023-24 and 2024-25.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import json
import math
from pathlib import Path
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/research"))
from nba_gm_data import injury_model as im  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.save import trait_values_by_player  # noqa: E402
import top30_real_seasons as real  # noqa: E402


def decayed(history, on, years):
    return sum(math.exp(-((on - d).days / 365.25) / years) for d, *_ in history if d < on)


def main() -> None:
    prefix = sys.argv[1]
    c = load_app_canonical(ROOT)
    players = {p["id"]: p for p in c["players"]}
    by_espn = {str(p.get("espn_player_id")): p for p in players.values() if p.get("espn_player_id")}
    traits = trait_values_by_player(c)
    model = im.load_model(ROOT)
    years = float(model.get("history_decay_years") or 1.5)
    hist = defaultdict(list)
    for h in json.loads((ROOT / "data/research/bbi/tools/injury_player_history.json").read_text()):
        if h.get("cat") == "injury" and h.get("start") and h.get("player_id"):
            hist[h["player_id"]].append((date.fromisoformat(h["start"][:10]), im.event_part({"body_part": h.get("part")})))
    rows = []
    for season in real.SEASONS[:-1]:
        stats = real.league_stats(real.espn_year(season), False)
        start = date(int(season[:4]), 10, 20)
        for espn in real.pick_top30(season, False, "prior"):
            p = by_espn.get(espn)
            if not p or not p.get("birthdate"):
                continue
            m = (stats.get(espn) or {}).get("avgMinutes") or 33.0
            age = (start - date.fromisoformat(str(p["birthdate"])[:10])).days / 365.25
            past = [x for x in hist[p["id"]] if x[0] < start]
            rows.append({"age": age, "mpg": m, "hist": decayed(past, start, years),
                         "hz": 82 * sum(im.part_hazards(model, {**p, "age": age}, traits.get(p["id"], {}), m, past, start).values()),
                         "hz33": 82 * sum(im.part_hazards(model, {**p, "age": age}, traits.get(p["id"], {}), 33.0, past, start).values())})
    meta = json.loads(Path(prefix + "_players.json").read_text())
    tgs = json.loads(Path(prefix + "_teamgames.json").read_text())
    gp, mins = Counter(), defaultdict(float)
    for t in tgs:
        for pid, mn in t["players"]:
            gp[pid] += 1
            mins[pid] += mn
    on = date(2026, 10, 20)
    sim = []
    for pid in meta["top30"]:
        p = players[pid]
        past = im.player_history(model, pid, [])
        m = mins[pid] / max(1, gp[pid])
        sim.append({"age": float(p.get("age") or 27), "mpg": m, "hist": decayed(past, on, years),
                    "hz": 82 * sum(im.part_hazards(model, p, traits.get(pid, {}), m, past, on).values()),
                    "hz33": 82 * sum(im.part_hazards(model, p, traits.get(pid, {}), 33.0, past, on).values())})
    # The same 30 a year later (2027-28 start, a year older), with the simulated season's injuries in their history: the
    # game's own seasons log every absence, so the tracker's thin 2025-26 matters less.
    events = json.loads(Path(prefix + "_events.json").read_text())
    later = date(2027, 10, 20)
    sim2 = []
    for pid in meta["top30"]:
        p = {**players[pid], "age": float(players[pid].get("age") or 27) + 1}
        past = im.player_history(model, pid, events)
        sim2.append({"age": p["age"], "mpg": mins[pid] / max(1, gp[pid]), "hist": decayed(past, later, years),
                     "hz": 82 * sum(im.part_hazards(model, p, traits.get(pid, {}), mins[pid] / max(1, gp[pid]), past, later).values()),
                     "hz33": 82 * sum(im.part_hazards(model, p, traits.get(pid, {}), 33.0, past, later).values())})
    for name, group in (("real top 30, 2021-22 to 2024-25", rows), ("game's top 30, 2026-27", sim),
                        ("same 30 at the 2027-28 start", sim2)):
        print(f"{name:34} n {len(group):3}  age {mean(r['age'] for r in group):4.1f}  minutes {mean(r['mpg'] for r in group):4.1f}"
              f"  decayed injury history {mean(r['hist'] for r in group):4.2f}  model chance per 82: own minutes "
              f"{mean(r['hz'] for r in group):4.2f}, at 33 minutes {mean(r['hz33'] for r in group):4.2f}")


if __name__ == "__main__":
    main()
