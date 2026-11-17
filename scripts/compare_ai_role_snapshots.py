"""Health-neutral before/after roles in the five untouched year-ten careers."""
from collections import defaultdict
import json
from pathlib import Path

from long_term_health import OUT, canonical, check_inputs, check_protection, sha, write
from nba_gm_data import save as sv
from remeasure_ai_roles import DEST, group, snapshot
from ten_season_soak import distribution


def summarize(rows, user):
    pools = defaultdict(list)
    selected = [p for p in rows if p["rostered"] and p["team_id"] != user]
    for player in selected:
        pools[group(player)].append(player)
    return {key: {"count": len(pool), "minutes": distribution(p["minutes"] for p in pool),
                  "at_least12": sum(p["minutes"] >= 12 for p in pool)} for key, pool in sorted(pools.items())}


def main():
    source = canonical()
    batch = json.loads((OUT / "overnight/status.json").read_text())
    report = {"scope": "One reassessment at existing year-ten snapshots; all players healthy for comparable role projections. No games, skills or rosters changed. Excludes human teams. Not a season outcome or new-player equilibrium estimate.", "careers": {}}
    for seed, job in sorted(batch["jobs"].items()):
        if job["status"] != "completed":
            continue
        path = json.loads((OUT / f"career-{seed}/run.json").read_text())["save_path"]
        digest = sha(path)
        saved = sv.load_save(path)
        saved["health_states"] = []
        user = saved["meta"]["user_team_id"]
        active = sv.canonical_with_save(source, saved)
        before = snapshot(active, saved)
        traits = json.dumps(active["traits"], sort_keys=True)
        sv.reassess_ai_roles(active, saved, saved["state"]["current_date"])
        sv.apply_save_rotation_projection(active, saved)
        after = snapshot(active, saved)
        assert json.dumps(active["traits"], sort_keys=True) == traits
        first, second = {p["id"]: p for p in before["players"]}, {p["id"]: p for p in after["players"]}
        assert all(first[pid]["fixed24_engine"] == second[pid]["fixed24_engine"] for pid in first)
        humans = [pid for pid in first if first[pid]["team_id"] == user]
        assert all(first[pid]["minutes"] == second[pid]["minutes"] for pid in humans)
        totals = defaultdict(float)
        for player in after["players"]:
            if player["rostered"] and player["team_id"] != user:
                totals[player["team_id"]] += player["minutes"]
        assert all(abs(total - 240) < .15 for total in totals.values()), totals
        report["careers"][seed] = {"before": summarize(before["players"], user),
                                  "after": summarize(after["players"], user),
                                  "rows": [{"id": pid, "name": first[pid]["name"], "group": group(first[pid]),
                                            "before": first[pid]["minutes"], "after": second[pid]["minutes"]}
                                           for pid in first if first[pid]["rostered"] and first[pid]["team_id"] != user],
                                  "human_minutes_unchanged": True, "traits_unchanged": True}
        assert sha(path) == digest
        print(seed, json.dumps({"before": report["careers"][seed]["before"], "after": report["careers"][seed]["after"]}), flush=True)
    check_protection()
    check_inputs()
    write(DEST / "snapshot-comparison.json", report)


if __name__ == "__main__":
    main()
