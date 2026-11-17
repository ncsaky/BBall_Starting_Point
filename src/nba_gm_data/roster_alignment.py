"""Versioned input calibration, never a migration of an existing career."""
from collections import defaultdict
from dataclasses import replace
import math
from typing import Any

from .draft import infer_prospect_archetype, infer_trait_values, rookie_trait_records
from .schema import Player, TraitValue, to_plain
from .utils import clamp, maybe_float, normalize_name

STARTING_DATA_VERSION = "2026-11-10-five-player-scouting-v11"
SOURCE_ID = "src_imported_roster_alignment_v1"


def nonnegative(value: Any) -> float:
    parsed = maybe_float(value)
    return parsed if parsed is not None and math.isfinite(parsed) and parsed >= 0 else 0.0


def career_evidence(player: Player, records: dict[str, Any], start_year: int) -> dict[str, Any]:
    record = records.get(str(player.espn_player_id)) or {}
    if not record:
        record = next((r for r in records.values()
                       if normalize_name(r.get("name", "")) == player.normalized_name), {})
    seasons = []
    for row in record.get("seasons", []):
        label = str(row.get("season", ""))
        if label[:4].isdigit() and int(label[:4]) < start_year and nonnegative(row.get("minutes")) > 0:
            seasons.append(row)
    recent = sorted((r for r in seasons if int(r["season"][:4]) >= start_year-2),
                    key=lambda row: row["season"],reverse=True)
    if not recent:
        return {}
    evidence = {"season":recent[0]["season"],
                "source_urls":list(dict.fromkeys(r["source_url"] for r in recent if r.get("source_url")))}
    # An injury-shortened latest season must not erase the preceding NBA sample.
    for key in ("minutes","games","points","rebounds","assists","steals","blocks","fga","fta","fg3a","fg3m"):
        evidence[key] = sum(nonnegative(row.get(key))*(1 if i==0 else .5)
                            for i,row in enumerate(recent))
    evidence["sample_seasons"] = [row["season"] for row in recent]
    return evidence


def nba_prior(player: Player, evidence: dict[str, Any], elapsed: int) -> tuple[dict[str, float], float]:
    minutes = max(0.0, maybe_float(evidence.get("minutes")) or 0.0)
    games = max(1.0, maybe_float(evidence.get("games")) or 1.0)
    mpg = minutes / games if minutes else clamp(player.minutes_projection, 0, 36)
    reliability = clamp(minutes / 800, 0, 1)
    per36 = {}
    for key, source, neutral in (("pts","points",14), ("reb","rebounds",5),
                                 ("ast","assists",2), ("stl","steals",.8), ("blk","blocks",.5)):
        measured = (maybe_float(evidence.get(source)) or 0) * 36 / max(1, minutes)
        per36[key] = neutral + reliability * (measured-neutral)
    fga = maybe_float(evidence.get("fga")) or 0
    fta = maybe_float(evidence.get("fta")) or 0
    denominator = 2*(fga+.44*fta)
    ts = (maybe_float(evidence.get("points")) or 0)/denominator if denominator else .55
    # Impact/usage estimates are not present in the career table: neutral priors,
    # not invented measured BPM or usage statistics.
    stats = {"per_36":per36, "advanced":{"tspct":.55+reliability*(clamp(ts,.35,.75)-.55),
                                            "bpm":0, "dbpm":0, "usg":20}}
    archetype = infer_prospect_archetype(player.position or "", stats)
    values = infer_trait_values(player.position or "", archetype, stats, player.height_inches)
    attempts = maybe_float(evidence.get("fg3a"))
    if attempts is not None and minutes:
        made = maybe_float(evidence.get("fg3m")) or 0
        shooting = (45 + (made/attempts-.33)*100 + min(10,attempts*36/minutes*1.5)) if attempts >= 40 else 32
        values["shooting"] += reliability * (clamp(shooting,25,85)-values["shooting"])
    slot = player.draft_position or 60
    entry = 55 if slot <= 3 else 51 if slot <= 14 else 45 if slot <= 30 else 41
    role = clamp((mpg-18)*.24,-4,3)
    production = clamp((per36["pts"]-16)*.16,-2,2) * reliability
    current = clamp(entry + min(3,elapsed*.7) + role + production,35,65)
    prospect = {"position":player.position, "archetype":archetype,
                "current_ability":current, "potential":current+12}
    draft_traits = [{"trait_key":key,"value":value} for key,value in values.items()]
    converted = {t["trait_key"]:t["value"] for t in rookie_trait_records(to_plain(player),prospect,draft_traits)}
    converted["stamina_cardio"] = clamp(45+mpg*.7,45,73)
    return converted, reliability


def align_imported_roster(
    players: list[Player], traits: list[TraitValue], career_data: dict[str, Any], start_year: int,
) -> tuple[list[Player], list[TraitValue], dict[str, Any]]:
    """Shrink uncertain recent-player inputs toward shared NBA-ready priors.

    Observed strengths, manual calibrations, current rookies and future classes
    retain their existing models. Remaining upside is age/evidence limited.
    """
    by_player: dict[str, list[TraitValue]] = defaultdict(list)
    for trait in traits:
        by_player[trait.player_id].append(trait)
    replacements = {}
    updated_players = []
    report: dict[str, Any] = {"policy":"imported_roster_alignment_v1", "players":[],
                             "career_cutoff":f"{start_year}-07-01",
                             "notes":"Modeled uncertainty calibration, not measured NBA ratings or guaranteed development."}
    records = career_data.get("players", {})
    for player in players:
        elapsed = start_year-int(player.draft_year or 0)
        young = 1 <= elapsed <= 4 and player.age is not None and player.age <= 26
        evidence = career_evidence(player,records,start_year)
        existing = by_player[player.id]
        values = {t.trait_key:t.value for t in existing}
        recent_evidence = evidence and int(evidence["season"][:4]) >= start_year-2
        if not existing or (not young and not recent_evidence):
            updated_players.append(player)
            continue
        prior,reliability = nba_prior(player,evidence,max(0,elapsed) if young else 0)
        deltas = {}
        mean = sum(values.values())/len(values)
        prior_mean = sum(prior.values())/len(prior)
        # Successful existing profiles are not re-grown from their draft slot.
        profile_weight = .55 if young and mean < prior_mean-1 else 0.0
        for trait in existing:
            if any(key in trait.components for key in ("manual_calibration", "imported_rookie_prior", "roster_alignment")):
                continue
            non_shooter = ((evidence.get("minutes") or 0) >= 300
                           and (evidence.get("fg3a") or 0)*36/max(1,evidence["minutes"]) < 1.5)
            if non_shooter and trait.trait_key in {"shooting_range","release_speed"}:
                continue
            target = trait.value
            reason = None
            missing_playtypes = (trait.trait_key == "shot_versatility" and trait.value == 0
                                 and trait.components.get("playtype_count") == 0)
            missing_stamina = (trait.trait_key == "stamina_cardio" and trait.value == 0
                               and not player.prior_minutes)
            if missing_playtypes or missing_stamina:
                target,reason = prior[trait.trait_key],"missing_evidence_not_zero_ability"
            elif trait.value == 0:
                continue
            elif young and trait.trait_key == "stamina_cardio" and reliability > 0 and trait.value < 45:
                target = trait.value + min(18,max(0,prior[trait.trait_key]-trait.value)*.65*reliability)
                reason = "observed_workload_prior"
            elif profile_weight:
                # Keep elite/specialist strengths and cap each uncertain correction.
                delta = max(0,prior[trait.trait_key]-trait.value)
                target = trait.value + min(10,delta*profile_weight)
                reason = "recent_player_nba_prior"
            target = round(clamp(target,0,100),2)
            if target == trait.value:
                continue
            info = {"previous":trait.value,"prior":round(prior[trait.trait_key],2),
                    "delta":round(target-trait.value,2),"reason":reason,
                    "career_season":evidence.get("season"),"career_minutes":evidence.get("minutes"),
                    "prior_minutes_input":player.prior_minutes}
            replacements[(player.id,trait.trait_key)] = replace(
                trait,value=target,confidence=min(trait.confidence,.58) if reason != "observed_workload_prior" else trait.confidence,
                source_kind=f"{trait.source_kind}_roster_alignment_v1",
                source_ids=list(dict.fromkeys([*trait.source_ids,SOURCE_ID])),
                notes=f"{trait.notes} Versioned NBA-role prior; uncertainty is not zero ability.",
                components={**trait.components,"roster_alignment":info})
            deltas[trait.trait_key] = info
        upside = None
        updated = player
        if young and player.current_ability is None and player.potential is None:
            corrected = [replacements.get((player.id,t.trait_key),t).value for t in existing]
            ability = clamp(sum(corrected)/len(corrected)-7,25,90)
            age_room = clamp((27-float(player.age))/8,0,1)
            # Draft expectations fade behind actual NBA opportunity with experience.
            slot = player.draft_position or 60
            draft_room = 20 if slot <= 3 else 16 if slot <= 14 else 12 if slot <= 30 else 9
            evidence_mpg = (maybe_float(evidence.get("minutes")) or 0)/max(1,maybe_float(evidence.get("games")) or 1)
            opportunity = .6 + .4*clamp(evidence_mpg/24,0,1) if evidence else .7
            remaining = (draft_room + 2)*age_room*opportunity
            potential = clamp(ability+remaining,ability,92)
            updated = replace(player,current_ability=round(ability,2),potential=round(potential,2))
            upside = {"current_ability":updated.current_ability,"potential":updated.potential,
                      "remaining_upside":round(remaining,2),"age":player.age,
                      "notes":"Remaining development only; existing seeded realization and health still apply."}
        updated_players.append(updated)
        if deltas or upside:
            report["players"].append({"player_id":player.id,"name":player.name,
                                      "draft_year":player.draft_year,"trait_changes":deltas,"remaining_upside":upside})
    report["adjusted_trait_count"] = len(replacements)
    report["adjusted_player_count"] = sum(bool(p["trait_changes"]) for p in report["players"])
    report["upside_player_count"] = sum(p["remaining_upside"] is not None for p in report["players"])
    return updated_players,[replacements.get((t.player_id,t.trait_key),t) for t in traits],report
