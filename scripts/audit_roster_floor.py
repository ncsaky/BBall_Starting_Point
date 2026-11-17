"""Attribute fixed-minute roster-rating changes without simulating or editing saves."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean

from nba_gm_data.save import presentation_rating_value


def roster(snapshot):
    rows = [row for row in snapshot["players"] if row["rostered"]]
    result = {row["id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate roster identity in census")
    if not result:
        raise ValueError("Cannot decompose an empty roster")
    return result


def rating(row):
    return presentation_rating_value(row["fixed24_engine"])


def summary(rows):
    values = [rating(row) for row in rows]
    return {"count": len(values), "mean": mean(values) if values else None,
            "below70": sum(value < 70 for value in values),
            "80_plus": sum(value >= 80 for value in values),
            "90_plus": sum(value >= 90 for value in values)}


def decompose(before, after):
    old, new = roster(before), roster(after)
    common = sorted(old.keys() & new.keys())
    entries, exits = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    initial_mean = mean(rating(row) for row in old.values())
    final_mean = mean(rating(row) for row in new.values())
    # Center turnover on the old mean; this remains exact if roster size changes.
    development = sum(rating(new[pid]) - rating(old[pid]) for pid in common) / len(new)
    turnover = (sum(rating(new[pid]) - initial_mean for pid in entries)
                - sum(rating(old[pid]) - initial_mean for pid in exits)) / len(new)
    age_deltas = defaultdict(list)
    for pid in common:
        age = old[pid].get("age")
        age_deltas[str(int(age)) if age is not None else "unknown"].append(
            rating(new[pid]) - rating(old[pid]))
    crossings_up = sum(rating(old[pid]) < 70 <= rating(new[pid]) for pid in common)
    crossings_down = sum(rating(new[pid]) < 70 <= rating(old[pid]) for pid in common)
    entrants_below = sum(rating(new[pid]) < 70 for pid in entries)
    exits_below = sum(rating(old[pid]) < 70 for pid in exits)
    residual = final_mean - initial_mean - development - turnover
    if abs(residual) > 1e-9:
        raise AssertionError("Decomposition does not reconcile")
    return {
        "from": before["date"], "to": after["date"],
        "before": summary(old.values()), "after": summary(new.values()),
        "mean_change": final_mean - initial_mean,
        "continuing_players_contribution": development,
        "turnover_contribution": turnover, "residual": residual,
        "continuing_players": len(common),
        "entrants_at_end": summary(new[pid] for pid in entries),
        "departures_at_start": summary(old[pid] for pid in exits),
        "entrants_already_in_starting_active_pool": sum(
            pid in {row["id"] for row in before["players"]} for pid in entries),
        "incumbent_change_by_start_age": {
            age: {"count": len(values), "mean_delta": mean(values)}
            for age, values in sorted(age_deltas.items())},
        "below70_count_change": {"incumbents_crossing_up": crossings_up,
                                 "incumbents_crossing_down": crossings_down,
                                 "entrants_below70": entrants_below,
                                 "departures_below70": exits_below,
                                 "net": crossings_down - crossings_up + entrants_below - exits_below},
        "limits": "Endpoint accounting, not causal identification. Entrant ratings include growth before the endpoint; intermediate exits and returns are not observable here. Existing censuses retain their original model/version.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    print(json.dumps(decompose(json.loads(args.before.read_text()),
                               json.loads(args.after.read_text())), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
