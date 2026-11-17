"""Swap only historical minute priors in throwaway rotation calculations."""
import json
from pathlib import Path
import re

from audit_roster_floor import rating
from long_term_health import OUT, annual_snapshots, canonical, check_protection, sha, write
from nba_gm_data.save import canonical_with_save, load_save, team_rotation_projection

DEST = Path(__file__).resolve().parents[1] / "output/development-retention-diagnosis-2026-10-24"


def positions(player):
    return set(re.split(r"[\s/,-]+", str(player.get("position") or "").upper())) - {""}


def main():
    source = canonical()
    batch = json.loads((OUT / "overnight/status.json").read_text())
    report = {"scope": "Static, health-neutral rotations; fixed-24-minute rating inputs. Excludes the human team. Swap only two saved baseline-minute numbers, preserving skills, ages, positions, contracts and recommendations. These are diagnostic counterfactuals, not a proposed rotation policy or live save edit.", "careers": {}}
    for seed, job in sorted(batch["jobs"].items()):
        if job["status"] != "completed":
            continue
        directory = OUT / f"career-{seed}"
        path = json.loads((directory / "run.json").read_text())["save_path"]
        digest = sha(path)
        saved = load_save(path)
        final = [p for p in annual_snapshots(directory)[-1]["players"] if p["rostered"]]
        active = canonical_with_save(source, saved)
        active["players"] = [{**p, "minutes_projection": 24} for p in active["players"]]
        players = {p["id"]: p for p in active["players"]}
        probe = {**saved, "health_states": [], "rotation_baselines": dict(saved["rotation_baselines"])}
        pairs = []
        observed = {}
        teams = {p["team_id"] for p in final} - {saved["meta"].get("user_team_id")}
        for team in sorted(teams):
            before = team_rotation_projection(active, probe, team)
            eligible = [(old, young) for old in final for young in final
                        if old["team_id"] == young["team_id"] == team and old["age"] >= 35 and young["age"] <= 27
                        and rating(young) >= rating(old) + 3
                        and before.get(old["id"], 0) >= before.get(young["id"], 0) + 8
                        and positions(players[old["id"]]) & positions(players[young["id"]])]
            observed[team] = len(eligible)
            if not eligible:
                continue
            old, young = max(eligible, key=lambda pair: rating(pair[1]) - rating(pair[0]))
            baselines = dict(probe["rotation_baselines"])
            old_base = baselines.get(old["id"], 24)
            young_base = baselines.get(young["id"], 24)
            baselines[old["id"]], baselines[young["id"]] = young_base, old_base
            after = team_rotation_projection(active, {**probe, "rotation_baselines": baselines}, team)
            assert abs(sum(before.values()) - 240) < .1, (seed, team, "before", sum(before.values()))
            assert abs(sum(after.values()) - 240) < .1, (seed, team, "after", sum(after.values()))
            pairs.append({"team": team, "old": {"name": old["name"], "age": old["age"], "overall": rating(old),
                                                "prior": old_base, "before_minutes": before[old["id"]], "after_minutes": after[old["id"]]},
                          "young": {"name": young["name"], "age": young["age"], "overall": rating(young),
                                    "pick": young.get("overall_pick"), "prior": young_base,
                                    "before_minutes": before[young["id"]], "after_minutes": after[young["id"]]}})
        report["careers"][seed] = {"same_position_conflicting_pairs": sum(observed.values()), "selected_team_probes": pairs}
        assert sha(path) == digest
        print(seed, "pairs", sum(observed.values()), "team probes", len(pairs), flush=True)
    check_protection()
    write(DEST / "rotation-prior-probe.json", report)


if __name__ == "__main__":
    main()
