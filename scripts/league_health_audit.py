"""Checkpointed, read-only instrumentation around isolated GUI-action saves.

Survey/trajectory results are controlled mechanism probes, not full seasons.
Advance mode never tunes, bypasses decisions, or modifies playable saves.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
import gc
import hashlib
import json
from pathlib import Path
import time

from ten_season_soak import SoakRunner, distribution
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.draft import (
    generate_draft_class_records, rookie_contract_projection,
    rookie_onboarding_record, rookie_player_record, rookie_trait_records,
    default_draft_model_config, simulate_draft,
)
from nba_gm_data.health import advance_development, injury_risk_for_player, load_injury_model_config, simulate_health
from nba_gm_data.history_store import load_history_records
from nba_gm_data.save import (
    apply_development_events_to_traits, canonical_with_save,
    apply_save_rotation_projection,
    player_attribute_summary, player_display_attribute_summary,
    season_start_year_from_date, trade_deadline_date,
    development_months_between,
    draft_completed_for_year,
)
from nba_gm_data.schema import to_plain

ROOT = Path(__file__).resolve().parents[1]


def summarize(rows):
    return {"count": len(rows),
            "engine": distribution(r["engine"] for r in rows),
            "display": distribution(r["display"] for r in rows),
            "fixed24_engine": distribution(r["fixed24_engine"] for r in rows),
            "engine_sum": round(sum(r["engine"] for r in rows), 3),
            "display_threshold_counts": {str(t): sum(r["display"] >= t for r in rows) for t in (60, 70, 80, 90)},
            "fixed24_engine_threshold_counts": {str(t): sum(r["fixed24_engine"] >= t for r in rows) for t in (50, 60, 70, 80)}}


def census(active, save):
    retired = set(save.get("retired_player_ids") or [])
    exits = set(save.get("league_exit_player_ids") or [])
    excluded = retired | exits
    free_agents = set(save.get("free_agent_player_ids") or [])
    neutral = {"players": [{**p, "minutes_projection": 24} for p in active.get("players", [])],
               "traits": active.get("traits", []), "_allow_internal_caches": True,
               "meta": dict(active.get("meta") or {})}
    legacy_neutral = {**neutral, "meta": {}}
    health = {r["player_id"]: r for r in active.get("player_health_states", [])}
    profiles = {r["player_id"]: r for r in active.get("player_health_profiles", [])}
    rows = []
    for player in active.get("players", []):
        pid = player["id"]
        if pid in excluded or player.get("_inactive_player"):
            continue
        state, profile = health.get(pid, {}), profiles.get(pid, {})
        age = player.get("display_age", player.get("age"))
        rows.append({"id": pid, "name": player.get("name"), "age": age,
                     "team_id": player.get("team_id"),
                     "overall_pick": player.get("overall_pick") or player.get("draft_position") or player.get("draft_pick"),
                     "draft_year": player.get("draft_year"), "origin": player.get("source_kind") or "baseline",
                     "rostered": bool(player.get("team_id") and pid not in free_agents),
                     "minutes": player.get("minutes_projection"),
                     "engine": player_attribute_summary(active, pid)["overall"],
                     "display": player_display_attribute_summary(active, pid)["overall"],
                     "fixed24_engine": player_attribute_summary(neutral, pid)["overall"],
                     "legacy_fixed24_engine": player_attribute_summary(legacy_neutral, pid)["overall"],
                     "fatigue": state.get("fatigue"), "rust": state.get("rust"),
                     "games_missed": state.get("games_missed"), "availability": state.get("availability_status"),
                     "durability": profile.get("durability"), "has_health_profile": bool(profile)})
    result = {"observer_schema_version": 3,
              "talent_model_version": (active.get("meta") or {}).get("talent_model_version", 1),
              "date": save.get("state", {}).get("current_date"), "season": save.get("meta", {}).get("season"),
              "phase": save.get("state", {}).get("phase"), "players": rows,
              "retired_count": len(retired - exits),
              "retired_flag_count": len(retired),
              "league_exit_count": len(exits),
              "retired_exit_flag_overlap": len(retired & exits),
              "injury_events_recorded": len(save.get("injury_events") or []),
              "development_months": list(save.get("applied_development_months") or [])}
    result["regular_games"] = sum(int(r.get("wins") or 0) for r in (save.get("team_records") or {}).values())
    result["phase_state"] = {
        "playoffs": (save.get("playoff_state") or {}).get("status"),
        "draft": (save.get("draft_state") or {}).get("status"),
        "draft_index": (save.get("draft_state") or {}).get("current_index"),
        "re_signing": (save.get("free_agency_state") or {}).get("re_signing_status"),
        "market": (save.get("free_agency_state") or {}).get("status"),
        "rookies": len(save.get("incoming_rookies") or []),
    }
    result["transaction_counts"] = dict(Counter(r.get("transaction_type") for r in save.get("transaction_logs", [])))
    counts = Counter(r["team_id"] for r in rows if r["rostered"])
    result["roster_counts_by_team"] = dict(sorted(counts.items()))
    result["regular_season_roster_overflow"] = {team: count for team, count in sorted(counts.items()) if count > 15} if result["phase"] == "regular_season" else {}
    for label, pool in (("active_pool", rows), ("rostered", [r for r in rows if r["rostered"]])):
        by_age, by_class = defaultdict(list), defaultdict(list)
        for row in pool:
            by_age["unknown" if row["age"] is None else str(int(float(row["age"])))].append(row)
            by_class[str(row["draft_year"] or "unknown")].append(row)
        result[label] = {**summarize(pool), "by_age_year": {k: summarize(v) for k, v in sorted(by_age.items())},
                         "by_draft_year": {k: summarize(v) for k, v in sorted(by_class.items())},
                         "health_profile_missing": sum(not r["has_health_profile"] for r in pool),
                         "unavailable": sum(r["availability"] not in {None, "active"} for r in pool)}
    return result


def flow(before, after):
    a = {r["id"]: r for r in before["players"]}
    b = {r["id"]: r for r in after["players"]}
    by_age = defaultdict(list)
    for pid in a.keys() & b.keys():
        age = a[pid]["age"]
        by_age["unknown" if age is None else str(int(float(age)))].append(b[pid]["fixed24_engine"] - a[pid]["fixed24_engine"])
    return {"entrants": [b[p] for p in sorted(b.keys() - a.keys())],
            "departures": [a[p] for p in sorted(a.keys() - b.keys())],
            "fixed24_engine_change_by_start_age": {k: distribution(v) for k, v in sorted(by_age.items())}}


def converted_class(year, seed, team, drafted=None, teams=None, talent_model=False):
    generated = drafted if drafted is not None else to_plain(generate_draft_class_records(str(year), seed=seed, talent_model=talent_model))
    selections = {s["prospect_id"]: s for s in generated.get("selections", [])}
    if drafted is not None:
        slots = [s["overall_pick"] for s in generated["selections"]]
        if len(selections) != len(slots) or len(set(slots)) != len(slots):
            raise ValueError("Draft contains duplicate prospects or selection slots")
    teams_by_id = {t["id"]: t for t in teams or [team]}
    traits = defaultdict(list)
    for row in generated["draft_prospect_traits"]:
        traits[row["prospect_id"]].append(row)
    players, records, metadata = [], [], {}
    for prospect in generated["draft_prospects"]:
        if drafted is not None and prospect["id"] not in selections:
            continue
        selection = selections.get(prospect["id"]) or {"id": prospect["id"], "draft_year": str(year), "prospect_id": prospect["id"],
                                                       "overall_pick": prospect["rank"], "team_id": team["id"]}
        owner = teams_by_id[selection["team_id"]]
        pick = int(selection["overall_pick"])
        contract = rookie_contract_projection(selection, prospect, owner, {"round": 1 if pick <= 30 else 2}, default_draft_model_config(), signed=True)
        player = rookie_player_record(rookie_onboarding_record(selection, prospect, owner, contract, signed=True), prospect, owner, contract)
        players.append(player)
        records.extend(rookie_trait_records(player, prospect, traits[prospect["id"]]))
        metadata[player["id"]] = {"rank": pick, "prospect_rank": prospect["rank"], "ability": prospect["current_ability"], "potential": prospect["potential"]}
    return generated, {"meta": {"talent_model_version": 2} if talent_model else {},
                       "players": players, "traits": records, "_allow_internal_caches": True, "_audit_draft_metadata": metadata}


def survey(canonical, years, seeds, minutes=24):
    classes, trajectories = [], []
    team = canonical["teams"][0]
    for seed in seeds:
        for year in range(2027, 2027 + years):
            generated, context = converted_class(year, seed, team)
            scores = [player_display_attribute_summary(context, p["id"])["overall"] for p in context["players"]]
            classes.append({"year": year, "seed": seed, "class_parameters": generated["draft_classes"][0],
                            "top_pick": scores[0], "top5": distribution(scores[:5]),
                            "lottery": distribution(scores[:14]), "late_first": distribution(scores[14:30]),
                            "second_round": distribution(scores[30:]),
                            "80_plus": sum(v >= 80 for v in scores), "70_plus": sum(v >= 70 for v in scores)})
            # A sample of elite-entry cohorts, at a fixed opportunity level.
            if year < 2030:
                ids = {p["id"] for p in context["players"][:3]}
                probe = {"players": deepcopy(context["players"][:3]),
                         "traits": [deepcopy(t) for t in context["traits"] if t["player_id"] in ids]}
                for player in probe["players"]:
                    player["minutes_projection"] = minutes
                initial_ages = {p["id"]: p["age"] for p in probe["players"]}
                checkpoints = []
                for month in range(121):
                    if month in {0, 12, 36, 60, 120}:
                        checkpoints.append({"months": month, "display_overalls": [player_display_attribute_summary(probe, p["id"])["overall"] for p in probe["players"]]})
                    if month == 120:
                        break
                    for p in probe["players"]:
                        p["age"] = initial_ages[p["id"]] + month // 12
                        p["minutes_projection"] = minutes
                    events = advance_development(probe, f"{year + month // 12}-{month % 12 + 1:02}", seed=seed)
                    apply_development_events_to_traits(probe, events["events"])
                trajectories.append({"year": year, "seed": seed, "checkpoints": checkpoints})
    config = load_injury_model_config(ROOT)
    health_risk = [{"age": age, "per_game_probability": injury_risk_for_player(
        {"age": age}, {"durability": 65}, {"fatigue": 20}, 28, 60, config, {"injury_risk_multiplier": 1})}
        for age in (19, 25, 30, 32, 35, 38, 41)]
    return {"scope": "Generated-class census and controlled development/risk probes; not simulated seasons or an equilibrium forecast.",
            "starting_data_version": canonical.get("meta", {}).get("starting_data_version"),
            "trajectory_conditions": f"Top 3, first 3 classes per seed; {minutes} MPG, neutral staff, healthy; no games, injuries, trades, retirements or roster competition.",
            "classes": classes, "trajectories": trajectories, "controlled_age_injury_risk": health_risk,
            "top_pick_across_classes": distribution(c["top_pick"] for c in classes),
            "top5_mean_across_classes": distribution(c["top5"]["mean"] for c in classes),
            "second_round_mean_across_classes": distribution(c["second_round"]["mean"] for c in classes)}


def rank_band(rank):
    return "1-3" if rank <= 3 else "4-14" if rank <= 14 else "15-30" if rank <= 30 else "31-60"


def health_blind_spots(root):
    """Compare health/development before and after the app's rotation projection."""
    state = {"player_id": "probe", "availability_status": "out", "current_injury_id": "probe_injury",
             "return_date": "2027-01-10", "fatigue": 0, "rust": 25, "games_missed": 0}
    canonical = {"teams": [{"id": "team_atl", "abbrev": "ATL"}],
                 "players": [{"id": "probe", "team_id": "team_atl", "name": "Fictional health probe", "age": 35,
                              "position": "SF", "minutes_projection": 24}],
                 "traits": [], "player_health_states": [state]}
    projected = deepcopy(canonical)
    apply_save_rotation_projection(projected, {"health_states": [state], "rotation_baselines": {"probe": 24}})
    schedule = [{"gameDate": "2027-01-02", "externalGameId": "health_audit_probe", "homeTeamId": "1", "awayTeamId": "2"}]
    reference = simulate_health(root, canonical, "2027-01-01", "2027-01-02", seed=17, schedule=schedule)
    observed = simulate_health(root, projected, "2027-01-01", "2027-01-02", seed=17, schedule=schedule)
    before = next(s["games_missed"] for s in reference["final_states"] if s["player_id"] == "probe")
    after = next(s["games_missed"] for s in observed["final_states"] if s["player_id"] == "probe")
    reference_development = advance_development(canonical, "2027-01", seed=17)["event_count"]
    projected_development = advance_development(projected, "2027-01", seed=17)["event_count"]
    return {"scope": "Single already-injured fictional veteran and one scheduled team game; no save writes.",
            "expected_missed_games": 1, "baseline_minutes": 24,
            "projected_minutes": projected["players"][0]["minutes_projection"],
            "missed_counter_before_projection": before, "missed_counter_after_projection": after,
            "counter_matches_reference": after == before,
            "development_events_before_projection": reference_development,
            "development_events_after_projection": projected_development,
            "injured_veteran_decline_still_processed": projected_development > 0}


def summarize_careers(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[rank_band(row["rank"])].append(row)
    return {
        band: {"count": len(pool),
               "entry": distribution(p["entry"] for p in pool),
               "peak": distribution(p["peak"] for p in pool),
               "peak_gain": distribution(p["peak"] - p["entry"] for p in pool),
               "peak_threshold_counts": {str(t): sum(p["peak"] >= t for p in pool) for t in (70, 80, 85, 90)},
               "under_2_points_peak_gain": sum(p["peak"] - p["entry"] < 2 for p in pool),
               "first_90_months": distribution(p["first_threshold_months"]["90"] for p in pool if p["first_threshold_months"]["90"] is not None),
               "peak_month": distribution(p["peak_month"] for p in pool)}
        for band, pool in sorted(grouped.items())
    }


def add_probe_staff(probe, skill):
    probe["gameplay_staff_slots"] = [
        {"team_id": team, "slot": "development_lead", "skill_traits": {
            "skill_development": skill, "prospect_patience": skill, "feedback_clarity": skill}}
        for team in sorted({p["team_id"] for p in probe["players"] if p.get("team_id")})
    ]


def career_probe(canonical, out, years, seeds, minutes, months, actual_draft=False, staff_skill=60):
    """All-rank mechanism probe; opportunity is held fixed, survival is not modeled."""
    report = {"scope": "Controlled healthy development, not simulated league careers or empirical bust/All-Star rates. Everyone receives the same opportunity and survives the entire probe.",
              "age_policy": "Whole-season age increments; first development month is October of draft year",
              "minutes": minutes, "months": months, "seeds": seeds,
              "development_staff_skill": staff_skill,
              "selection_basis": "Actual AI draft on the fixed starting-team context (not evolving league rosters)" if actual_draft else "Prospect rank used as pick; all signed to one team",
              "input_hashes": input_fingerprint(), "cohorts": [], "players": [], "status": "running"}
    manifest = out / "career_probe.json"
    if manifest.exists():
        raise FileExistsError("Use a new comparison directory; career probes never overwrite evidence")
    out.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        for year in range(2027, 2027 + years):
            if actual_draft:
                draft = simulate_draft(canonical, str(year), seed=seed)
                # The starting universe already contains its first future class;
                # that canonical path returns selections without repeating input rows.
                for table, key in (("draft_classes", "season"), ("draft_prospects", "draft_year")):
                    draft.setdefault(table, [p for p in canonical.get(table, []) if str(p.get(key)) == str(year)])
                ids = {p["id"] for p in draft["draft_prospects"]}
                draft.setdefault("draft_prospect_traits", [t for t in canonical.get("draft_prospect_traits", []) if t["prospect_id"] in ids])
                generated, probe = converted_class(year, seed, canonical["teams"][0], drafted=draft, teams=canonical["teams"])
            else:
                generated, probe = converted_class(year, seed, canonical["teams"][0])
            add_probe_staff(probe, staff_skill)
            prospects = {p["rank"]: p for p in generated["draft_prospects"]}
            initial_ages = {p["id"]: p["age"] for p in probe["players"]}
            rows = []
            for rank, player in enumerate(probe["players"], 1):
                player["minutes_projection"] = minutes
                metadata = probe.get("_audit_draft_metadata", {}).get(player["id"], {})
                rows.append({"id": player["id"], "rank": rank, "seed": seed, "year": year,
                             "entry_age": player["age"], "ability": prospects[rank]["current_ability"],
                             "potential": prospects[rank]["potential"], **metadata, "peak": -1, "checkpoints": {},
                             "first_threshold_months": {str(t): None for t in (70, 80, 85, 90)}})
            for month in range(months + 1):
                for player, row in zip(probe["players"], rows, strict=True):
                    player["age"] = initial_ages[player["id"]] + month // 12
                    score = player_display_attribute_summary(probe, player["id"])["overall"]
                    if month == 0:
                        row["entry"] = score
                    if score > row["peak"]:
                        row["peak"], row["peak_month"] = score, month
                    if month % 12 == 0 or month == months:
                        row["checkpoints"][str(month)] = score
                    for threshold, first in row["first_threshold_months"].items():
                        if first is None and score >= int(threshold):
                            row["first_threshold_months"][threshold] = month
                if month == months:
                    break
                event_year, event_month = divmod(year * 12 + 9 + month, 12)
                events = advance_development(probe, f"{event_year}-{event_month + 1:02}", seed=seed)
                apply_development_events_to_traits(probe, events["events"])
            report["players"].extend(rows)
            report["cohorts"].append({"year": year, "seed": seed, "class": generated["draft_classes"][0], "by_rank": summarize_careers(rows),
                                      "selected": len(rows), "not_selected": len(generated["draft_prospects"]) - len(rows)})
            report["by_rank"] = summarize_careers(report["players"])
            manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            print(json.dumps({"year": year, "seed": seed, "players": len(report["players"]),
                              "90_plus_by_pick_band": {k: v["peak_threshold_counts"]["90"] for k, v in report["cohorts"][-1]["by_rank"].items()}}), flush=True)
    report["status"] = "completed"
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def replacement_probe(canonical, out, years, seed, minutes, staff_skill=60):
    """Optimistic supply diagnostic, deliberately excluding survival/finance friction."""
    manifest = out / "replacement_probe.json"
    if manifest.exists():
        raise FileExistsError("Use a new output directory to preserve the previous evidence")
    out.mkdir(parents=True, exist_ok=True)
    probe = {"players": deepcopy(canonical["players"]), "traits": deepcopy(canonical["traits"]),
             "_allow_internal_caches": True}
    ages = {p["id"]: (float(p.get("age") or 27), 0) for p in probe["players"]}
    baseline = set(ages)
    report = {"scope": "Optimistic mechanism diagnostic, NOT full league simulation or a strict upper bound. All active baseline players and all 60 annual draftees stay healthy, receive fixed minutes and configured staff; removed only at age 42. No roster limits, contracts, trades, injuries or earlier retirement. Rank-as-pick, one drafting team; actual draft ownership can change seeded realization.",
              "age_policy": "Whole-season increments at October; rookies retain entry age in their draft-year season",
              "development_staff_skill": staff_skill,
              "seed": seed, "minutes": minutes, "input_hashes": input_fingerprint(), "snapshots": [], "status": "running"}
    for month in range(years * 12 + 1):
        absolute = 2026 * 12 + 9 + month
        year, zero_month = divmod(absolute, 12)
        label = f"{year}-{zero_month + 1:02}"
        if zero_month == 6:
            _, incoming = converted_class(year, seed, canonical["teams"][0])
            for player in incoming["players"]:
                ages[player["id"]] = (float(player["age"]), year - 2026)
            probe["players"].extend(incoming["players"])
            probe["traits"].extend(incoming["traits"])
            probe.pop("_players_by_id", None)
            probe.pop("_trait_values_by_player", None)
        add_probe_staff(probe, staff_skill)
        for player in probe["players"]:
            entry_age, base_season = ages[player["id"]]
            player["age"] = entry_age + max(0, month // 12 - base_season)
            player.pop("display_age", None)
            player["minutes_projection"] = minutes
            player["_inactive_player"] = player["age"] >= 42
        if month % 12 == 0 or month == years * 12:
            snapshot = census(probe, {"state": {"current_date": label + "-01"}})
            stars = [p for p in snapshot["players"] if p["display"] >= 90]
            snapshot["baseline_stars"] = sum(p["id"] in baseline for p in stars)
            snapshot["generated_stars"] = sum(p["id"] not in baseline for p in stars)
            report["snapshots"].append(snapshot)
            manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            print(json.dumps({"date": label, "active": len(snapshot["players"]), "baseline_stars": snapshot["baseline_stars"], "generated_stars": snapshot["generated_stars"]}), flush=True)
        if month == years * 12:
            break
        events = advance_development(probe, label, seed=seed)
        apply_development_events_to_traits(probe, events["events"])
    report["status"] = "completed"
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def select_advance(save, days):
    current = save["state"]["current_date"]
    target = (date.fromisoformat(current) + timedelta(days=days)).isoformat()
    phase = save["state"]["phase"]
    if phase in {"play_in", "playoffs", "draft_lottery", "draft", "re_signing", "free_agency"}:
        raise RuntimeError(f"Manual audit checkpoint at {phase} on {current}; follow mandatory phase actions before continuing")
    year = season_start_year_from_date(current)
    boundaries = [trade_deadline_date(year), f"{year + 1}-04-12"]
    target = min([target, *[d for d in boundaries if d > current]])
    payload = {"to_date": target}
    if current == trade_deadline_date(year):
        payload["trade_deadline_confirmed"] = current
    return payload


def regular_complete(save):
    records = list((save.get("team_records") or {}).values())
    games = sum(int(row.get("wins") or 0) for row in records)
    if games != 1230:
        raise RuntimeError(f"Refusing postseason/season-complete claim with {games}/1230 regular games")
    losses = sum(int(row.get("losses") or 0) for row in records)
    if len(records) != 30 or losses != 1230 or any(int(r.get("wins") or 0) + int(r.get("losses") or 0) != 82 for r in records):
        raise RuntimeError("Regular-season records must balance: 30 teams, 82 games each, 1230 wins and losses")


def career_action(save, days, team):
    """Explicit hands-off decision policy; never alter state to skip a phase."""
    current = save["state"]["current_date"]
    phase = save["state"]["phase"]
    start = int(save["meta"]["season"][:4])
    end = start + 1
    if phase in {"play_in", "playoffs"}:
        regular_complete(save)
        if (save.get("playoff_state") or {}).get("status") == "completed":
            from nba_gm_data.offseason_calendar import offseason_dates   # FA-REAL slice 2 calendar
            return "advance_save", {"to_date": offseason_dates(end)["offseason_opens"]}
        return "simulate_playoff_all", {}
    if phase == "draft_lottery":
        regular_complete(save)
        return "draft_reveal_lottery", {"year": str(end), "team": team}
    if phase == "draft":
        if draft_completed_for_year(save, end):
            from nba_gm_data.offseason_calendar import offseason_dates
            return "advance_save", {"to_date": offseason_dates(end)["after_draft"]}
        return "draft_sim_all", {"year": str(end), "team": team}
    if phase == "re_signing":
        return "advance_re_signing", {"mode": "open_market", "team": team}
    if phase == "free_agency":
        return "advance_free_agency", {"mode": "end", "team": team}
    if current == f"{end}-04-12":
        regular_complete(save)
        return "advance_save", {"to_date": f"{end}-04-13"}
    if phase == "training_camp" and current[:4] == str(end):
        regular_complete(save)
        return "advance_save", {"next_event": True}
    return "advance_save", select_advance(save, days)


def state_marker(snapshot):
    return snapshot["date"], snapshot["season"], snapshot["phase"], snapshot.get("phase_state")


def calendar_coverage(snapshots, event_months=()):
    observed = set(event_months)
    for snapshot in snapshots:
        observed.update(snapshot.get("development_months", []))
    cycles, gaps = [], []
    first = snapshots[0]
    for before, after in zip(snapshots, snapshots[1:]):
        crossed = development_months_between(before["date"], after["date"])
        missing = sorted(set(crossed) - observed)
        if missing:
            gaps.append({"from": before["date"], "to": after["date"],
                         "from_phase": before["phase"], "to_phase": after["phase"], "missing": missing})
        if after["season"] != first["season"]:
            expected = development_months_between(first["date"], after["date"])
            cycles.append({"season": first["season"], "from": first["date"], "to": after["date"],
                           "expected": expected, "processed": [m for m in expected if m in observed],
                           "missing": [m for m in expected if m not in observed]})
            first = after
    return {"scope": "Monthly-boundary coverage across completed cycles, combining observed applied-month lists and durable/live development events. Presence alone does not prove correct within-month chronology.",
            "completed_cycles": cycles, "date_jump_gaps": gaps}


def input_fingerprint():
    paths = [*sorted((ROOT / "src/nba_gm_data").glob("*.py")),
             *sorted((ROOT / "data/overrides").glob("*.json")),
             *sorted((ROOT / "data/overrides").glob("*.csv")),
             ROOT / "data/canonical/universe_2026_27_offseason.json",
             ROOT / "data/canonical/baselines/registry.json"]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def advance(args):
    out = Path(args.output).resolve()
    if out == ROOT / "saves" or ROOT / "saves" in out.parents:
        raise ValueError("Audit output must not be inside playable saves")
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(out), seed=args.seed, team=args.team))
    manifest = out / "league_health.json"
    if args.resume:
        report = json.loads(manifest.read_text())
        if report["seed"] != args.seed or report["team"] != args.team:
            raise ValueError("Resume seed/team must match the checkpoint")
        runner.payload["save_path"] = report["save_path"]
        if Path(report["save_path"]).resolve().parent != runner.save_dir:
            raise ValueError("Checkpoint save is outside the audit-owned directory")
    else:
        if manifest.exists():
            raise FileExistsError("Audit already exists; use --resume or another output directory")
        created = runner.action("create_save", team=args.team, seed=args.seed, save_name="league_health")
        runner.payload["save_path"] = created["save_path"]
        report = {"seed": args.seed, "team": args.team, "save_path": created["save_path"], "snapshots": [], "actions": []}
    model_hashes = {name: hashlib.sha256((ROOT / "src/nba_gm_data" / name).read_bytes()).hexdigest()
                    for name in ("draft.py", "health.py", "save.py", "ingest.py", "schema.py")}
    if report.get("source_hashes", model_hashes) != model_hashes:
        raise RuntimeError("Model changed since the checkpoint; start a separate comparison run")
    if "source_hashes" not in report:
        report["hashes_first_recorded_after_actions"] = len(report["actions"])
    report["source_hashes"] = model_hashes
    report["starting_data_version"] = runner.canonical.get("meta", {}).get("starting_data_version")
    inputs = input_fingerprint()
    if report.get("input_hashes", inputs) != inputs:
        raise RuntimeError("Simulation inputs changed; use a new comparison directory")
    report.setdefault("input_hashes_first_recorded_after_actions", len(report["actions"]))
    report["input_hashes"] = inputs
    report.setdefault("initial_season_start", int(runner.load()["meta"]["season"][:4]))
    report["decision_policy"] = "Ignore incoming offers; AI draft all; release user expiring rights to open market; no discretionary user FA bids; retain affordable staff else interim; cut lowest legal rotation candidates."
    started = time.monotonic()
    def capture():
        saved = runner.load()
        snapshot = census(canonical_with_save(runner.canonical, saved), saved)
        if report["snapshots"]:
            snapshot["flow"] = flow(report["snapshots"][-1], snapshot)
        report["snapshots"].append(snapshot)
        manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return saved
    saved = capture()
    report["status"] = "running"
    try:
        for _ in range(args.steps):
            if time.monotonic() - started >= args.seconds:
                break
            runner.resolve_user_staff_retention()
            runner.resolve_user_roster_cutdown()
            saved = runner.load()
            for history in saved.get("season_history", []):
                if history.get("team_records"):
                    regular_complete({"team_records": history["team_records"]})
                    season = history["season"]
                    if season not in report.setdefault("verified_regular_seasons", []):
                        report["verified_regular_seasons"].append(season)
            if args.career and int(saved["meta"]["season"][:4]) >= report["initial_season_start"] + args.seasons:
                break
            if args.career and sum(int(r.get("wins") or 0) for r in saved.get("team_records", {}).values()) == 1230:
                regular_complete(saved)
                season = saved["meta"]["season"]
                if season not in report.setdefault("verified_regular_seasons", []):
                    report["verified_regular_seasons"].append(season)
            name, payload = career_action(saved, args.days, args.team) if args.career else ("advance_save", select_advance(saved, args.days))
            before = saved["state"]["current_date"]
            marker = state_marker(report["snapshots"][-1])
            tick = time.monotonic()
            result = runner.action(name, save_path=runner.payload["save_path"], seed=args.seed, **payload)
            report["actions"].append({"action": name, "from": before, "payload": payload, "status": result.get("status"), "seconds": round(time.monotonic()-tick, 3)})
            saved = capture()
            print(json.dumps({"date": saved["state"]["current_date"], "seconds": report["actions"][-1]["seconds"]}), flush=True)
            if state_marker(report["snapshots"][-1]) == marker:
                raise RuntimeError("No calendar/phase progress; preserve the save and inspect the required decision")
        report["status"] = "completed" if args.career and int(saved["meta"]["season"][:4]) >= report["initial_season_start"] + args.seasons else "checkpointed"
    except Exception as exc:
        report["status"] = "needs_attention"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["last_run_seconds"] = round(time.monotonic() - started, 3)
        manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("survey", "advance", "careers", "replacement", "health", "calendar"))
    parser.add_argument("--output", default=str(ROOT / "output/league-health-2026-10-20"))
    parser.add_argument("--years", type=int, default=20)
    parser.add_argument("--seeds", default="17,29,913")
    parser.add_argument("--trajectory-minutes", type=float, default=24)
    parser.add_argument("--staff-skill", type=float, default=60, help="Development staff traits in controlled probes (60 neutral, 100 capped best case)")
    parser.add_argument("--cohort-months", type=int, default=180)
    parser.add_argument("--actual-draft", action="store_true", help="Use actual AI selection slots and drafting teams in controlled career probes")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--team", default="GSW")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--career", action="store_true", help="Follow the explicit hands-off policy through required season phases")
    parser.add_argument("--seasons", type=int, default=1)
    args = parser.parse_args()
    if min(args.days, args.steps, args.seconds, args.years, args.cohort_months) <= 0:
        parser.error("Budgets and intervals must be positive")
    if not 0 <= args.staff_skill <= 100:
        parser.error("Staff skill must be between 0 and 100")
    gc.disable()
    if args.mode == "calendar":
        out = Path(args.output)
        report = json.loads((out / "league_health.json").read_text())
        saved = json.loads(Path(report["save_path"]).read_text())
        events = {e["id"]: e for e in load_history_records(report["save_path"], saved, "development_events")}
        events.update({e["id"]: e for e in saved.get("development_events", [])})
        result = calendar_coverage(report["snapshots"], (e["month"] for e in events.values()))
        result["durable_and_live_event_counts_by_month"] = dict(sorted(Counter(e["month"] for e in events.values()).items()))
        for season in saved.get("season_history", []):
            regular_complete({"team_records": season["team_records"]})
        result["verified_regular_seasons"] = [s["season"] for s in saved.get("season_history", [])]
        current = census(canonical_with_save(load_app_canonical(ROOT), saved), saved)
        (out / "current_census.json").write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        (out / "development_calendar_coverage.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result["completed_cycles"], indent=2))
    elif args.mode == "health":
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        result = {**health_blind_spots(ROOT), "input_hashes": input_fingerprint()}
        (out / "health_blind_spots.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "input_hashes"}, indent=2))
    elif args.mode == "replacement":
        replacement_probe(load_app_canonical(ROOT), Path(args.output), args.years, args.seed, args.trajectory_minutes, args.staff_skill)
    elif args.mode == "careers":
        career_probe(load_app_canonical(ROOT), Path(args.output), args.years,
                     [int(s) for s in args.seeds.split(",")], args.trajectory_minutes, args.cohort_months, args.actual_draft, args.staff_skill)
    elif args.mode == "survey":
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        result = survey(load_app_canonical(ROOT), args.years, [int(s) for s in args.seeds.split(",")], args.trajectory_minutes)
        result["source_hashes"] = {name: hashlib.sha256((ROOT / "src/nba_gm_data" / name).read_bytes()).hexdigest() for name in ("draft.py", "health.py", "save.py", "ingest.py")}
        (out / "draft_survey.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({k: result[k] for k in ("top_pick_across_classes", "top5_mean_across_classes", "second_round_mean_across_classes")}))
    else:
        advance(args)


if __name__ == "__main__":
    main()
