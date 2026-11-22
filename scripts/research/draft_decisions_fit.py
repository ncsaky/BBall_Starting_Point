"""Build NBA draft decision evidence from the checked-in source extracts.

Run from this checkout with:

    PYTHONPATH=src nice -n 10 .venv/bin/python scripts/research/draft_decisions_fit.py

The default build is offline. --refresh-game runs the selector and replaces the
compact game fixture. Source details are in data/research/draft_boards/cache.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date
from itertools import combinations
import json
from pathlib import Path
import re
from statistics import mean, median
import unicodedata


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "data" / "research"
CACHE = RESEARCH / "draft_boards" / "cache"
SPLITS = {"fit": range(2012, 2022), "held_out": range(2022, 2026)}
BANDS = ((1, 5, "1–5"), (6, 14, "6–14"), (15, 30, "15–30"), (31, 60, "second round"))
DRAFT_DATES = {
    2012: "06-28", 2013: "06-27", 2014: "06-26", 2015: "06-25",
    2016: "06-23", 2017: "06-22", 2018: "06-21", 2019: "06-20",
    2020: "11-18", 2021: "07-29", 2022: "06-23", 2023: "06-22",
    2024: "06-26", 2025: "06-25", 2026: "06-23",
}
TEAM_ALIASES = {"BKN": "BRK", "CHO": "CHA", "NJN": "BRK", "NOH": "NOP", "PHX": "PHO", "WSH": "WAS", "UTAH": "UTA"}
COLLEGE_YEARS = {
    "fr": 1, "freshman": 1, "so": 2, "sophomore": 2,
    "jr": 3, "junior": 3, "sr": 4, "senior": 4,
}
NAME_ALIASES = {
    "michealkiddgilchrist": "michaelkiddgilchrist", "nerlennoels": "nerlensnoel",
    "karltowns": "karlanthonytowns", "timotheluwawu": "timotheluwawucabarrot",
    "juanhernangomez": "juanchohernangomez", "guillermohernangomez": "willyhernangomez",
    "alexsarr": "alexandresarr", "carltoncarrington": "bubcarrington",
    "terenceshannon": "terrenceshannon",
    "moeharkless": "mauriceharkless", "dennisschroeder": "dennisschroder",
    "erikgreen": "erickgreen", "roydevynmarble": "devynmarble",
    "josephyoung": "joeyoung", "danieldiez": "danidiez", "patmccaw": "patrickmccaw",
    "wesleyiwundu": "wesiwundu", "aleksandarvezenkov": "sashavezenkov", "mohamedbamba": "mobamba",
    "nahshonhyland": "boneshyland", "nahshonboneshyland": "boneshyland", "santiagoaldama": "santialdama",
    "gregoryjackson": "ggjackson", "jordanbachynskicarizonastate": "jordanbachynski",
}


def name_key(value):
    text = unicodedata.normalize("NFKD", value.casefold()).encode("ascii", "ignore").decode()
    text = re.sub(r"\b(?:jr|sr|ii|iii|iv)\.?$", "", text.strip(" ,.*#~‡†"))
    key = re.sub(r"[^a-z0-9]", "", text)
    return NAME_ALIASES.get(key, key)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def number(value):
    return None if value in ("NA", "", None) else float(value)


def average(values):
    values = [v for v in values if v is not None]
    return round(mean(values), 5) if values else None


def rate(numerator, denominator):
    return round(numerator / denominator, 5) if denominator else None


def draft_age(birth, year):
    if birth in ("NA", "", None):
        return None
    return (date.fromisoformat(f"{year}-{DRAFT_DATES[year]}") - date.fromisoformat(birth)).days / 365.2425


def pick_band(pick):
    return next(label for low, high, label in BANDS if low <= pick <= high)


def team_key(team):
    return TEAM_ALIASES.get(team, team)


def position_group(position):
    primary = re.split(r"[-/ ,]", (position or "").upper())[0]
    if primary in {"PG", "SG", "G", "GUARD", "CG", "COMBO"}:
        return "guard"
    if primary in {"SF", "F", "FORWARD", "W", "WING", "GF"}:
        return "wing"
    if primary in {"PF", "C", "BIG", "CENTER", "FC"}:
        return "big"
    return None


def team_context():
    minutes = defaultdict(Counter)
    for row in read_csv(CACHE / "roster_minutes.csv"):
        position = position_group(row["position"])
        if position:
            minutes[int(row["year"]), team_key(row["team"])][position] += int(row["minutes"])
    shares = {
        key: {position: 100 * counts[position] / counts.total() for position in ("guard", "wing", "big")}
        for key, counts in minutes.items()
    }
    baselines = {
        (year, pos): mean(share[pos] for (y, _), share in shares.items() if y == year)
        for year in DRAFT_DATES for pos in ("guard", "wing", "big")
        if any(y == year for y, _ in shares)
    }
    teams = {}
    for row in read_csv(CACHE / "standings.csv"):
        year, team = int(row["year"]), team_key(row["team"])
        wins, losses = int(row["wins"]), int(row["losses"])
        pct = wins / (wins + losses)
        playoffs = row["playoffs"] == "TRUE"
        group = "contender" if playoffs and pct >= 0.60 else "rebuilding" if not playoffs and pct <= 0.42 else "middle"
        deficit = {pos: baselines[year, pos] - share for pos, share in shares[year, team].items()}
        teams[year, team] = {"wins": wins, "losses": losses, "win_pct": pct, "playoffs": playoffs,
                             "group": group, "deficit": deficit}
    assert all(sum(y == year for y, _ in teams) == 30 for year in DRAFT_DATES)
    return teams


@dataclass(frozen=True)
class Prospect:
    name: str
    rank: int | None = None
    player_id: str | None = None
    age: float | None = None
    college_years: int | None = None
    college_bpm: float | None = None
    college_ppg: float | None = None
    position: str | None = None
    public_votes: int | None = None
    scout_current: float | None = None
    scout_room: float | None = None


def official_boards():
    by_year = defaultdict(list)
    for board in read_json(CACHE / "public_boards.json"):
        by_year[board["year"]].append(board)
    legacy = defaultdict(list)
    for row in read_csv(RESEARCH / "draft_boards" / "real_board_vs_pick_2015_2025.csv"):
        legacy[int(row["year"])].append(row)
    # The older file stores only the first 30. It also supplies an independent 2016 board.
    rows = legacy[2016]
    by_year[2016].append({
        "id": "legacy2016", "year": 2016, "publisher": rows[0]["source_name"],
        "published": "2016-06-22", "url": rows[0]["source_url"],
        "ranks": [[int(row["board_rank"]), row["player"]] for row in rows],
    })
    for year in (*SPLITS["fit"], *SPLITS["held_out"]):
        assert 2 <= len(by_year[year]) <= 3, year
        for board in by_year[year]:
            assert date.fromisoformat(board["published"]) <= date.fromisoformat(f"{year}-{DRAFT_DATES[year]}")
            assert len(board["ranks"]) >= 10
    return by_year, legacy


def consensus(boards, aliases):
    votes = defaultdict(dict)
    names = {}
    depths = []
    for i, board in enumerate(boards):
        depths.append(max(rank for rank, _ in board["ranks"]))
        for rank, name in board["ranks"]:
            key = aliases.get(name_key(name), name_key(name))
            votes[key].setdefault(i, rank)
            names.setdefault(key, name)

    def sort_key(key):
        seen = list(votes[key].values())
        observed_mean = mean(seen)
        # A list ending at 30 cannot distinguish ranks below 30. Its absence cannot improve
        # the observed average, and it imposes at least a rank of 31 when one board ranks a longshot high.
        value = mean(votes[key].get(i, max(depth + 1, observed_mean)) for i, depth in enumerate(depths))
        return value, -len(seen), min(seen), key

    return {
        key: Prospect(names[key], rank, public_votes=len(votes[key]))
        for rank, key in enumerate(sorted(votes, key=sort_key), 1)
    }


def prospect_data(drafts, boards, year, college, people, combine):
    aliases = {}
    for row in drafts:
        aliases[name_key(row["wiki_name"])] = name_key(row["name"])
    prospects = consensus(boards, aliases)
    for row in drafts:
        key = name_key(row["name"])
        original = prospects.get(key, Prospect(row["name"]))
        prospects[key] = replace(original, name=row["name"], player_id=row["player_id"])
    for key, player in prospects.items():
        row = next((r for r in drafts if name_key(r["name"]) == key), {})
        other_key = name_key(row.get("wiki_name", player.name))
        birth_row = people.get(player.player_id) or people.get(key) or {}
        college_row = college.get((year, key)) or college.get((year, other_key)) or {}
        if not college_row and row.get("college_class"):
            slot = college.get((year, int(row["pick"])), {})
            # Pick number alone is insufficient. A different draft year's player can occur in the college table.
            if name_key(slot.get("name", "")) in {key, other_key}:
                college_row = slot
        position = (
            position_group(row.get("position"))
            or combine.get((year, key))
            or position_group(birth_row.get("position"))
        )
        age = draft_age(birth_row.get("birth_date"), year) or draft_age(college_row.get("birth_date"), year)
        school_year = college_row.get("class_year") or row.get("college_class", "")
        years = COLLEGE_YEARS.get(school_year.strip(".").lower())
        prospects[key] = replace(
            player,
            player_id=player.player_id or birth_row.get("player_id"),
            position=position,
            age=age,
            college_years=years,
            college_bpm=number(college_row.get("college_bpm")),
            college_ppg=number(college_row.get("points_per_game")),
        )
    return prospects


def real_drafts():
    sources, legacy = official_boards()
    years = defaultdict(list)
    for row in read_csv(CACHE / "draft_results.csv"):
        years[int(row["year"])].append(row)
    people = {}
    for row in read_csv(CACHE / "birth_positions.csv"):
        people[row["player_id"]] = row
        people.setdefault(name_key(row["name"]), row)
    college = {}
    draft_slots = {}
    for row in read_csv(CACHE / "college.csv"):
        year = int(row["year"])
        college.setdefault((year, name_key(row["name"])), row)
        if row["eventual_pick"].isdigit():
            draft_slots.setdefault((year, int(row["eventual_pick"])), row)
    college.update(draft_slots)
    combine = {}
    for row in read_json(RESEARCH / "draft_combine_2000_2025.json")["players"]:
        combine[row["year"], name_key(row["name"])] = position_group(row["position"])
    result = {}
    for year, draft in sorted(years.items()):
        data = prospect_data(draft, sources[year], year, college, people, combine)
        ordered = sorted(draft, key=lambda row: int(row["pick"]))
        expected = {2022: 58, 2023: 58, 2024: 58, 2025: 59}.get(year, 60)
        assert [int(row["pick"]) for row in ordered] == list(range(1, expected + 1)), year
        assert len({name_key(row["name"]) for row in ordered}) == expected
        result[year] = {
            "board": data,
            "picks": [(int(row["pick"]), name_key(row["name"]), row["decision_team"]) for row in ordered],
            "traded_picks": [int(row["pick"]) for row in ordered if row["changed_draft_day"] == "1"],
            "legacy_source": legacy[year][0]["source_url"] if year in legacy else None,
            "legacy_rank_deltas": [
                data[name_key(row["player"])].rank - int(row["board_rank"])
                for row in legacy[year]
                if name_key(row["player"]) in data and data[name_key(row["player"])].rank is not None
            ],
        }
    return result, sources


def selection_rows(draft, teams, team_year):
    board = draft["board"]
    ranked = sorted((p.rank, key) for key, p in board.items() if p.rank is not None)
    available = dict.fromkeys(key for _, key in ranked)
    phases = draft.get("engine_phases", {})
    events = []
    for slot, key, team in draft["picks"]:
        selection = board[key]
        fallback_key = next(iter(available), None)
        alternative = board[fallback_key] if fallback_key else None
        context = teams[team_year, team_key(team)]
        deficits = context["deficit"]
        weakest = max(deficits, key=deficits.__getitem__)
        if alternative and selection.position and alternative.position:
            positional = {
                "need_delta": deficits[selection.position] - deficits[alternative.position],
                "pick_fills_weakest": int(selection.position == weakest),
                "board_fills_weakest": int(alternative.position == weakest),
            }
        else:
            positional = {"need_delta": None, "pick_fills_weakest": None, "board_fills_weakest": None}
        events.append({
            "pick": slot, "team": team, "group": context["group"], "engine_phase": phases.get(team),
            "playoffs": context["playoffs"],
            "win_pct": context["win_pct"], "name": selection.name, "rank": selection.rank,
            "best_available": alternative.name if alternative else None,
            "best_available_rank": alternative.rank if alternative else None,
            "gap": selection.rank - slot if selection.rank is not None else None,
            "gap_lower_bound": (ranked[-1][0] + 1 - slot) if selection.rank is None else selection.rank - slot,
            "passed_over": selection.rank - alternative.rank if alternative and selection.rank is not None else None,
            "picked_best": key == fallback_key,
            "age_at_draft": selection.age, "class_years_of_pick": selection.college_years,
            "college_bpm_of_pick": selection.college_bpm, "college_ppg_of_pick": selection.college_ppg,
            **{attr: difference(selection, alternative, attr) for attr in (
                "age", "college_years", "college_bpm", "college_ppg", "scout_current", "scout_room"
            )},
            **positional,
        })
        available.pop(key, None)
    return events


def difference(left, right, attr):
    a, b = getattr(left, attr), getattr(right, attr, None)
    return a - b if a is not None and b is not None else None


def range_summaries(rows):
    result = {}
    for low, high, label in BANDS:
        picks = [r for r in rows if low <= r["pick"] <= high]
        gaps = [r["gap"] for r in picks if r["gap"] is not None]
        need = [r for r in picks if r["need_delta"] is not None]
        result[label] = {
            "picks": len(picks),
            "ranked_picks": len(gaps),
            "median_signed_gap": median(gaps) if gaps else None,
            "median_absolute_gap": median(map(abs, gaps)) if gaps else None,
            "mean_absolute_gap": average(map(abs, gaps)),
            "reach_5_count_lower_bound": sum(r["gap_lower_bound"] >= 5 for r in picks),
            "reach_10_count_lower_bound": sum(r["gap_lower_bound"] >= 10 for r in picks),
            "reach_5_rate_lower_bound": rate(sum(r["gap_lower_bound"] >= 5 for r in picks), len(picks)),
            "reach_10_rate_lower_bound": rate(sum(r["gap_lower_bound"] >= 10 for r in picks), len(picks)),
            "best_available_rate": rate(sum(r["picked_best"] for r in picks), len(picks)),
            "need_comparisons": len(need),
            "need_delta_pct_points": average(r["need_delta"] for r in need),
            "picked_weakest_position": sum(r["pick_fills_weakest"] for r in need),
            "board_weakest_position": sum(r["board_fills_weakest"] for r in need),
            "weakest_position_delta": average(r["pick_fills_weakest"] - r["board_fills_weakest"] for r in need),
        }
    return result


def slide_summary(drafts):
    slides = []
    for draft in drafts:
        rank_to_pick = {key: slot for slot, key, _ in draft["picks"]}
        slides.extend(
            (p.rank, rank_to_pick.get(key, 61))
            for key, p in draft["board"].items() if p.rank is not None and p.rank <= 10
        )
    total = len(slides)
    return {"top_10": total, "slid_5": sum(p - r >= 5 for r, p in slides),
            "slid_10": sum(p - r >= 10 for r, p in slides), "past_10": sum(p > 10 for _, p in slides),
            "past_14": sum(p > 14 for _, p in slides), "undrafted": sum(p > 60 for _, p in slides)}


def matched_effect(rows, metric, left, right, bucket):
    # Compare groups only where both appear at the same pick (or in the same band for the sensitivity check).
    cells = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r[metric] is not None:
            cells[bucket(r)][r["group"]].append(r[metric])
    usable = [(c[left], c[right]) for c in cells.values() if c[left] and c[right]]
    weights = [len(a) * len(b) / (len(a) + len(b)) for a, b in usable]
    delta = sum(w * (mean(a) - mean(b)) for w, (a, b) in zip(weights, usable)) / sum(weights) if weights else None
    return {"delta": round(delta, 5) if delta is not None else None, "shared_slots": len(usable),
            "left_n": sum(len(a) for a, _ in usable), "right_n": sum(len(b) for _, b in usable)}


def readiness_summary(rows):
    result = {}
    actual_fields = {"age": "age_at_draft", "college_years": "class_years_of_pick",
                     "college_bpm": "college_bpm_of_pick", "college_ppg": "college_ppg_of_pick"}
    for metric in ("age", "college_years", "college_bpm", "college_ppg", "passed_over", "scout_current", "scout_room"):
        actual_field = actual_fields.get(metric)
        groups = {}
        for group in ("contender", "rebuilding", "middle"):
            values = [r[metric] for r in rows if r["group"] == group and r[metric] is not None]
            groups[group] = {"n": len(values), "above_best_available": average(values)}
            if actual_field:
                actual = [r[actual_field] for r in rows if r["group"] == group and r[actual_field] is not None]
                groups[group].update(actual_n=len(actual), actual_mean=average(actual))
        result[metric] = {
            "groups": groups,
            "contender_minus_rebuilder_same_pick": matched_effect(rows, metric, "contender", "rebuilding", lambda r: r["pick"]),
            "contender_minus_rebuilder_same_range": matched_effect(rows, metric, "contender", "rebuilding", lambda r: pick_band(r["pick"])),
        }
    return result


def outcomes_index():
    public = read_json(RESEARCH / "development_evidence.json")["public_inputs"]["seasons"]
    index = {(year, pid): (minutes, bpm, vorp) for year, pid, _, _, minutes, bpm, vorp in public if year < 2020}
    for row in read_csv(CACHE / "recent_outcomes.csv"):
        index[int(row["year"]), row["player_id"]] = tuple(number(row[key]) for key in ("minutes", "bpm", "vorp"))
    return index


def career_outcome(index, pid, draft_year, horizon):
    zero = (0, None, 0)
    seasons = [index.get((y, pid), zero) for y in range(draft_year + 1, draft_year + horizon + 1)]
    return {
        f"minutes_through_year_{horizon}": sum(r[0] or 0 for r in seasons),
        f"vorp_through_year_{horizon}": sum(r[2] or 0 for r in seasons),
        f"bpm_year_{horizon}": seasons[-1][1],
    } | ({"minutes_year_4": seasons[-1][0]} if horizon == 4 else {})


def outcome_checks(drafts, outcomes, horizon=4):
    comparisons = defaultdict(list)
    orders = {}
    for year, draft in drafts.items():
        if year + horizon > 2026:
            continue
        matches = []
        for pick, key, _ in draft["picks"]:
            prospect = draft["board"][key]
            if prospect.rank is not None:
                matches.append((pick, prospect.rank, career_outcome(outcomes, prospect.player_id, year, horizon)))
        board_order = sorted(matches, key=lambda r: r[1])
        orders[year] = {"common_pool_size": len(matches)}
        for metric in matches[0][2]:
            def concordance(order):
                comparisons = [(left[2][metric], right[2][metric]) for left, right in combinations(order, 2)
                               if left[2][metric] is not None and right[2][metric] is not None]
                scores = [(a > b) + 0.5 * (a == b) for a, b in comparisons]
                return average(scores)

            orders[year][metric] = {
                "actual_order_concordance": concordance(matches),
                "board_order_concordance": concordance(board_order),
                "actual_top_14_on_common_pool": average(r[2][metric] for r in matches[:14]),
                "board_top_14_on_common_pool": average(r[2][metric] for r in board_order[:14]),
            }
        for slot, rank, stat in matches:
            band = pick_band(slot)
            group = "reach_5" if rank - slot >= 5 else "slide_5" if slot - rank >= 5 else "within_4"
            comparisons[band, group].append(stat)
    grouped = {
        f"{band} / {group}": {
            "n": len(rows), **{metric: average(row[metric] for row in rows) for metric in rows[0]},
            f"year_{horizon}_bpm_n": sum(row[f"bpm_year_{horizon}"] is not None for row in rows),
        }
        for (band, group), rows in comparisons.items()
    }
    order_comparison = {
        m: {
            "actual_mean_concordance": average(r[m]["actual_order_concordance"] for r in orders.values()),
            "board_mean_concordance": average(r[m]["board_order_concordance"] for r in orders.values()),
            "actual_mean_top_14": average(r[m]["actual_top_14_on_common_pool"] for r in orders.values()),
            "board_mean_top_14": average(r[m]["board_top_14_on_common_pool"] for r in orders.values()),
        }
        for m in next(iter(comparisons.values()))[0]
    } if comparisons else {}
    return {"complete_classes": list(orders), "by_class": orders,
            "by_actual_pick_band_and_board_gap": grouped, "actual_vs_board": order_comparison}


def summary(drafts, teams, game=False):
    events = {year: selection_rows(draft, teams, 2026 if game else year) for year, draft in drafts.items()}
    rows = [r for draft in events.values() for r in draft]
    payload = {"by_pick_range": range_summaries(rows), "top_10_slides": slide_summary(drafts.values()),
               "readiness": readiness_summary(rows), "per_class": {
                   year: {"by_pick_range": range_summaries(picks), "top_10_slides": slide_summary([drafts[year]]),
                          "readiness": readiness_summary(picks)}
                   for year, picks in events.items()
               }}
    if not game:
        payload["draft_day_changes"] = {
            "by_class": {year: draft["traded_picks"] for year, draft in drafts.items()},
            "by_pick_range": {label: sum(low <= p <= high for d in drafts.values() for p in d["traded_picks"])
                              for low, high, label in BANDS},
        }
        payload["outcomes"] = outcome_checks(drafts, outcomes_index())
    return payload, events


def historical_game_class(base, config, draft):
    from nba_gm_data import draft as engine
    from nba_gm_data.schema import to_plain
    classes, players, traits = engine.build_2026_draft_records(draft, config)
    teams = {team_key(t["abbrev"]): t["id"] for t in base["teams"]}
    picks = []
    for row in read_json(RESEARCH / "draft_picks_espn_2026.json")["picks"]:
        owner = teams[team_key(row["owner_team_abbrev"])]
        picks.append({
            "id": f"draft_research_2026_{row['overall']}", "season": "2026",
            "round": row["round"], "overall_pick": row["overall"], "team_id": owner,
            "current_owner_team_id": owner, "original_team_id": teams[team_key(row["original_team_abbrev"])],
        })
    return {**base, "draft_classes": to_plain(classes), "draft_prospects": to_plain(players),
            "draft_prospect_traits": to_plain(traits), "draft_picks": [*base["draft_picks"], *picks]}


def game_inputs(base, year, seed, config, real_ages):
    from nba_gm_data import draft as engine, draft_scouting as scouts

    canonical = {**base, "meta": {**base["meta"], "draft_class_seed": seed}}
    result = engine.simulate_draft(canonical, str(year), seed=seed, config=config)
    expected_slots = {int(row["overall_pick"]) for row in result.get("draft_order", [])} or set(range(1, 61))
    assert {int(row["overall_pick"]) for row in result["selections"]} == expected_slots
    assert len(result["selections"]) == len(expected_slots)
    report = scouts.class_scouting(canonical, str(year), scouts.DRAFT_MONTH)
    team_names = {t["id"]: team_key(t["abbrev"]) for t in canonical["teams"]}
    picks = [(int(row["overall_pick"]), row["prospect_id"], team_names[row["team_id"]]) for row in result["selections"]]
    board = {}
    for pid, r in report["consensus"].items():
        p = report["prospects"][pid]
        if year != 2026:
            assert p["league"] == "generated", (year, p["league"])
        ppg = (p.get("public_stats", {}).get("per_game") or {}).get("pts")
        bpm = (p.get("public_stats", {}).get("advanced") or {}).get("bpm")
        age = real_ages.get(name_key(p["name"]), p["age"]) if year == 2026 else p["age"]
        board[pid] = Prospect(p["name"], r["rank"], age=age, position=position_group(p["position"]),
                              college_years=COLLEGE_YEARS.get((p.get("class_year") or "").lower()),
                              college_bpm=bpm, college_ppg=ppg, scout_current=r["current"],
                              scout_room=r["potential"] - r["current"])

    by_team = {}
    phases = {}
    for sel in result["selections"]:
        team = sel["team_id"]
        if team_names[team] in by_team:
            continue
        phase = engine.team_state(canonical, team).get("phase")
        phases[team_names[team]] = phase
        candidates = []
        for pid, entry in report["reports"][team].items():
            current = entry["estimated_current"]["mid"]
            potential = entry["estimated_potential"]["mid"]
            fit = engine.gm_need_fit(canonical, team, report["prospects"][pid])
            candidates.append((
                pid, entry["scouted_grade"],
                potential - current - engine.GM_TYPICAL_ROOM if phase in engine.REBUILD_PHASES else 0,
                current - engine.GM_TYPICAL_CURRENT if phase in engine.CONTEND_PHASES else 0,
                entry["risk"]["volatility"] if phase in engine.CONTEND_PHASES else 0,
                fit - 50.0, float(engine._slot_value(engine.PROFILE_POTENTIAL, board[pid].rank)),
            ))
        by_team[team_names[team]] = candidates
    return {"year": year, "seed": seed, "picks": picks, "board": board,
            "by_team": by_team, "engine_phases": phases,
            "slot_values": {slot: engine._slot_value(engine.PROFILE_POTENTIAL, slot) for slot, _, _ in picks}}


def game_replay(draft, weights):
    pool = set(draft["board"])
    slots = []
    for slot, _, team in draft["picks"]:
        need = weights["need"][next(i for i, (_, high, _) in enumerate(BANDS) if slot <= high)]
        slot_value = draft["slot_values"][slot]
        scored = []
        for pid, grade, upside, ready, risk, fit, prospect_value in draft["by_team"][team]:
            if pid in pool:
                phase = weights["upside"] * upside + weights["ready"] * ready - weights["risk"] * risk
                reach = weights["reach"] * max(0, slot_value - prospect_value - weights["tolerance"])
                score = round(grade + phase + need * fit - reach, 4)
                scored.append((-score, draft["board"][pid].rank, pid))
        selected = min(scored)[2]
        slots.append((slot, selected, team))
        pool.remove(selected)
    return {**draft, "picks": slots}


def reach_error(game, real):
    return average(
        abs(game[b][metric] - real[b][metric]) / scale
        for _, _, b in BANDS
        for metric, scale in (("median_absolute_gap", 4), ("reach_5_rate_lower_bound", 0.15),
                              ("reach_10_rate_lower_bound", 0.10))
    )


def tuning(stock, drafts, teams, historical):
    targets = {split: historical[split]["by_pick_range"] for split in SPLITS}
    grid = []
    # Reach weights operate in slot-value points. Shape comes from the game; the historical
    # target consists of rank distances and reach rates. Fit on two generated snapshots.
    for reach in (0.0, 0.15, stock["reach"], 0.40, 0.60, 0.85, 1.10):
        for tolerance in (0.0, stock["tolerance"], 4.0):
            if reach == 0 and tolerance != stock["tolerance"]:
                continue
            weights = {**stock, "reach": reach, "tolerance": tolerance}
            ranges, slides = [], []
            for group in (drafts[1:3], drafts[3:]):
                replays = [game_replay(d, weights) for d in group]
                rows = [r for d in replays for r in selection_rows(d, teams, 2026)]
                ranges.append(range_summaries(rows))
                slides.append(slide_summary(replays))
            grid.append({"weights": weights, "fit": ranges[0], "held_out": ranges[1],
                         "top_10_slides": dict(zip(("fit", "held_out"), slides)),
                         "fit_error": reach_error(ranges[0], targets["fit"]),
                         "held_out_error": reach_error(ranges[1], targets["held_out"])})
    best = min(grid, key=lambda r: (r["fit_error"], abs(r["weights"]["reach"] - stock["reach"]),
                                   abs(r["weights"]["tolerance"] - stock["tolerance"])))
    base_weights = best["weights"]
    other = []
    for label, values in (
        ("need_multiplier", (0, 0.5, 1, 1.5, 2)),
        ("ready", (0, 0.07, stock["ready"], 0.28)),
        ("upside", (0, 0.05, stock["upside"], 0.20)),
        ("risk", (0, stock["risk"], 0.06)),
    ):
        for value in values:
            weights = {**base_weights}
            if label == "need_multiplier":
                weights["need"] = [round(x * value, 4) for x in stock["need"]]
            else:
                weights[label] = value
            checks = []
            for group in (drafts[1:3], drafts[3:], drafts[:1]):
                rows = [r for d in group for r in selection_rows(game_replay(d, weights), teams, 2026)]
                checks.append({
                    "by_pick_range": range_summaries(rows),
                    "readiness": readiness_summary(rows),
                })
            other.append({"lever": label, "value": value, "fit": checks[0], "held_out": checks[1], "class_2026": checks[2]})
    return {
        "method": "Reach grid minimizes equal-weight differences in median absolute gap / 4, reach-5 rate / 0.15, "
                  "and reach-10 rate / 0.10 in the four pick bands. Historical fit years and two generated classes "
                  "choose a candidate; 2022–2025 and the third generated class are a separate check. Other weights "
                  "are one-at-a-time sensitivity checks around the best reach-grid setting.",
        "reach_grid_best": best, "reach_grid": grid, "other_weight_sensitivity": other,
    }


def refresh_game(teams, historical):
    from nba_gm_data import draft as engine
    from nba_gm_data.app_actions import load_app_canonical

    base = engine.with_draft_context(load_app_canonical(ROOT))
    config = engine.default_draft_model_config()
    draft = read_json(RESEARCH / "draft_prospects_2026.json")
    game_2026 = historical_game_class(base, config, draft)
    ages = {name_key(r["player"]): r["age"] for r in draft["prospects"]}
    stock = {
        "reach": engine.GM_REACH_WEIGHT, "tolerance": engine.GM_REACH_TOLERANCE,
        "need": [weight for _, weight in engine.GM_NEED_WEIGHTS], "upside": engine.GM_PHASE_UPSIDE,
        "ready": engine.GM_PHASE_READY, "risk": engine.GM_CONTENDER_RISK,
    }
    game = []
    for year, seed in ((2026, 17), (2031, 17), (2032, 23), (2033, 31)):
        canonical = game_2026 if year == 2026 else base
        item = game_inputs(canonical, year, seed, config, ages)
        assert item["picks"] == game_replay(item, stock)["picks"], f"Stock replay differs in {year}"
        game.append(item)
        print(f"Simulated {year} with seed {seed}", flush=True)
    fixture = {
        "setup": "Stock selection-only AI. The 2026 public prospect cache and pre-draft ESPN order were restored "
                 "in memory on the fresh post-draft league snapshot. Future classes use projected draft order and "
                 "the same starting team strategy and rosters. Evaluation uses 2025–26 standings and roster minutes "
                 "for all four assignments. No season or trade execution is simulated.",
        "engine_phase_groups": {"contender": sorted(engine.CONTEND_PHASES), "rebuilding": sorted(engine.REBUILD_PHASES)},
        "weights": stock, "classes": {
            item["year"]: {"seed": item["seed"], "picks": item["picks"], "engine_phases": item["engine_phases"], "board": {
                key: vars(value) for key, value in item["board"].items()
            }} for item in game
        },
        "tuning": tuning(stock, game, teams, historical),
    }
    write_json(CACHE / "game_probe.json", fixture)


def source_manifest(boards):
    return {
        "boards": {year: [{k: v for k, v in row.items() if k != "ranks"} | {"ranks_captured": len(row["ranks"])}
                          for row in rows] for year, rows in sorted(boards.items())},
        **read_json(CACHE / "sources.json"),
    }


def compact_events(events):
    """Only the fields needed to inspect per-pick joins and spot-check the aggregates."""
    columns = list(next(iter(events.values()))[0])
    return {"columns": columns, "by_class": {
        year: [[round(r[c], 5) if isinstance(r[c], float) else r[c] for c in columns] for r in rows]
        for year, rows in events.items()
    }}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-game", action="store_true", help="Run the read-only seeded game probe")
    parser.add_argument("--output", type=Path, default=RESEARCH / "draft_decisions_evidence.json")
    args = parser.parse_args()

    teams = team_context()
    drafts, boards = real_drafts()
    historical = {}
    real_events = {}
    for split, years in SPLITS.items():
        split_drafts = {year: drafts[year] for year in years}
        historical[split], events = summary(split_drafts, teams)
        if split == "held_out":
            historical[split]["equal_one_year_outcome_check"] = outcome_checks(split_drafts, outcomes_index(), horizon=1)
        real_events.update(events)
    if args.refresh_game:
        refresh_game(teams, historical)
    game_fixture = read_json(CACHE / "game_probe.json")
    game = {
        int(year): {**draft, "board": {key: Prospect(**row) for key, row in draft["board"].items()}}
        for year, draft in game_fixture["classes"].items()
    }
    game_result, game_events = summary(game, teams, game=True)
    game_result["future_only"], _ = summary({y: d for y, d in game.items() if y > 2026}, teams, game=True)
    game_result["setup"] = game_fixture["setup"]
    game_result["stock_weights"] = game_fixture["weights"]
    stock = game_fixture["weights"]
    game_result["suggested_weight_trial"] = {
        "GM_PHASE_UPSIDE": stock["upside"], "GM_PHASE_READY": stock["ready"],
        "GM_CONTENDER_RISK": stock["risk"], "GM_NEED_WEIGHTS": stock["need"],
        "GM_REACH_WEIGHT": game_fixture["tuning"]["reach_grid_best"]["weights"]["reach"],
        "GM_REACH_TOLERANCE": stock["tolerance"],
    }
    game_result["tuning"] = game_fixture["tuning"]
    game_result["seeds"] = {year: d["seed"] for year, d in game.items()}
    game_result["missing_pick_slots"] = {
        year: sorted(set(range(1, 61)) - {slot for slot, _, _ in draft["picks"]}) for year, draft in game.items()
    }
    phases = {phase: group for group, names in game_fixture["engine_phase_groups"].items() for phase in names}
    game_result["readiness_with_game_phase_labels"] = readiness_summary([
        {**row, "group": phases.get(row["engine_phase"], "middle")}
        for rows in game_events.values() for row in rows
    ])
    board_coverage = {
        year: {"union_depth": sum(p.rank is not None for p in d["board"].values()),
               "picks_missing_from_every_board": [p["name"] for p in real_events[year] if p["rank"] is None],
               "legacy_source": d["legacy_source"], "legacy_names_matched": len(d["legacy_rank_deltas"]),
               "legacy_mean_absolute_rank_difference": average(map(abs, d["legacy_rank_deltas"]))}
        for year, d in drafts.items()
    }
    write_json(args.output, {
        "as_of": "2026-11-22",
        "definitions": {
            "choice": "The actual selection versus the highest-ranked prospect left on the public board at that exact turn.",
            "reach": "Consensus rank minus pick is positive for reaches. Unranked selections contribute only a "
                     "conservative lower bound to reach counts and are omitted from typical gaps.",
            "team_situation": "Contenders won at least 60% and made the playoffs. Rebuilders won at most 42% and missed them. "
                              "Shared-slot estimates weight each exact pick by the harmonic share of observations on both sides.",
            "positional_need": "A team's prior regular-season minutes by listed primary guard, wing or big compared to "
                               "the same season's 30-team average for that position. Positive pick-minus-board deficit "
                               "means the pick addresses a larger relative minutes deficit.",
            "college": "College class standing approximates years of college experience. Production uses final-year "
                       "T-Rank college box plus-minus and points per game. Unknowns stay missing.",
            "outcomes": "Four NBA seasons from the draft, including zero minutes and zero value over replacement for "
                        "seasons absent from the panel. Year-four box plus-minus requires NBA minutes. An order's "
                        "concordance is its fraction of pairwise outcomes in the right order with half credit for ties.",
            "trade": "Count unique current-draft picks, not transactions. Use documented draft-day changes in rights "
                     "with the date corrections in the source notes. Subsequent formal approval can occur later.",
        },
        "split_years": {split: list(years) for split, years in SPLITS.items()},
        "sources": source_manifest(boards),
        "board_coverage": board_coverage,
        "real_nba": historical,
        "game": game_result,
        "real_picks": compact_events(real_events),
        "game_picks": compact_events(game_events),
    })
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
