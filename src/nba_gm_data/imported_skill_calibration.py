"""Conservative, versioned evidence checks for imported NBA skills only."""
from collections import defaultdict
from dataclasses import replace
import math
from typing import Any

from .schema import Player, TraitValue
from .utils import clamp, maybe_float

SOURCE_ID = "src_imported_skill_evidence_v7"
MARKER = "imported_skill_evidence_v7"
PROXY_KEYS = {"defensive_effort", "scheme_iq", "screen_navigation", "portability"}


def number(value: Any) -> float | None:
    value = maybe_float(value)
    return value if value is not None and math.isfinite(value) and value >= 0 else None


def recent_nba_sample(player: Player, records: dict[str, Any], start_year: int) -> list[dict[str, Any]]:
    record = records.get(str(player.espn_player_id), {})
    if str(record.get("espn_player_id")) != str(player.espn_player_id):
        return []
    rows = []
    for row in record.get("seasons", []):
        season = str(row.get("season", ""))
        url = str(row.get("source_url", ""))
        if not season[:4].isdigit() or not start_year-2 <= int(season[:4]) < start_year:
            continue
        if f"/basketball/nba/athletes/{player.espn_player_id}/" not in url:
            continue
        minutes = number(row.get("minutes"))
        games = number(row.get("games"))
        if minutes is None or minutes <= 0 or games is None or games <= 0 or minutes > games*60:
            continue
        rows.append(row)
    return sorted(rows, key=lambda row: row["season"], reverse=True)


def observed_skill(rows: list[dict[str, Any]], key: str, start_year: int) -> dict[str, Any] | None:
    required = ("fg3a", "fg3m") if key == "shooting_range" else ("assists", "turnovers")
    usable = [row for row in rows if all(number(row.get(k)) is not None for k in required)]
    if key == "shooting_range":
        usable = [row for row in usable if float(row["fg3m"]) <= float(row["fg3a"])]
    if not usable:
        return None
    # Calendar-year weights do not promote an old season when the latest is absent.
    weights = [1.0 if int(row["season"][:4]) == start_year-1 else .5 for row in usable]
    minutes = sum(float(row["minutes"])*w for row, w in zip(usable, weights))
    if minutes < 1000:
        return None
    totals = {k: sum(float(row[k])*w for row, w in zip(usable, weights)) for k in required}
    if key == "shooting_range":
        attempts = totals["fg3a"]
        volume = attempts*36/minutes
        if attempts < 80 or volume < 1.5 or totals["fg3m"]/attempts < .34:
            return None
        accuracy = (totals["fg3m"]+80*.35)/(attempts+80)
        target = clamp(35+(accuracy-.30)*140+min(15, volume*2.5), 20, 78)
        detail = {"attempts": attempts, "makes": totals["fg3m"], "attempts_per36": volume,
                  "shrunk_accuracy": accuracy}
    else:
        assists = totals["assists"]*36/minutes
        if assists < 1.5:
            return None
        ratio = (totals["assists"]+50*2)/(totals["turnovers"]+50)
        target = clamp(12+7.5*assists+clamp((ratio-2)*4, -6, 8), 12, 90)
        detail = {"assists_per36": assists, "shrunk_assist_turnover_ratio": ratio}
    return {"target": target, "weighted_minutes": minutes, **detail,
            "sample_seasons": [row["season"] for row in usable],
            "source_urls": sorted({row["source_url"] for row in usable})}


def calibrate_imported_skills(
    players: list[Player], traits: list[TraitValue], career_data: dict[str, Any], start_year: int,
) -> tuple[list[TraitValue], dict[str, Any]]:
    by_player: dict[str, list[TraitValue]] = defaultdict(list)
    for trait in traits:
        by_player[trait.player_id].append(trait)
    replacements = {}
    report: dict[str, Any] = {"policy": MARKER, "examined_players": len(players), "players": [],
        "notes": "Modeled, bounded skill priors, not measured ratings. No overall floor or career migration."}
    records = career_data.get("players", {})
    for player in players:
        existing = by_player[player.id]
        # A reviewed profile is a coherent whole, not fifteen independent overrides.
        if (player.draft_year or 0) >= start_year or any(
            "manual_calibration" in t.components or "imported_rookie_prior" in t.components for t in existing
        ):
            continue
        rows = recent_nba_sample(player, records, start_year)
        nba_minutes = sum(float(row["minutes"])*(1 if int(row["season"][:4]) == start_year-1 else .5)
                          for row in rows)
        changes = {}
        for trait in existing:
            components = trait.components
            if MARKER in components:
                continue
            key, target, reason, detail = trait.trait_key, trait.value, None, {}
            if key in {"shooting_range", "passing_reads"} and trait.value <= 65:
                observed = observed_skill(rows, key, start_year)
                if observed and observed["target"]-trait.value >= 12:
                    weight = min(.65, observed["weighted_minutes"]/(observed["weighted_minutes"]+800))
                    delta = min(10, (observed["target"]-trait.value)*weight)
                    target, reason, detail = trait.value+delta, "sampled_nba_skill_conflict", observed
            elif key in PROXY_KEYS and nba_minutes >= 500 and not any(
                k in components for k in ("league_trait_rating_calibration", "roster_alignment")
            ):
                pieces = components.get("components")
                if isinstance(pieces, list) and pieces and all(v is None or number(v) is not None for v in pieces):
                    count = sum(v is not None for v in pieces)
                    if 0 < count <= len(pieces)/2:
                        weight = min(.35, .5*(1-count/len(pieces)))
                        # The importer's existing missing-data prior is 50. A
                        # partial proxy should not imply certainty at either extreme.
                        target = trait.value+clamp((50-trait.value)*weight, -8, 8)
                        reason = "sparse_unreviewed_proxy_shrinkage"
                        detail = {"observed_components": count, "expected_components": len(pieces),
                                  "neutral_prior": 50, "weight": weight, "weighted_minutes": nba_minutes,
                                  "source_urls": sorted({row["source_url"] for row in rows})}
            target = round(clamp(target), 2)
            if abs(target-trait.value) < 1:
                continue
            info = {"previous": trait.value, "corrected": target, "delta": round(target-trait.value, 2),
                    "reason": reason, **detail}
            replacements[(player.id, key)] = replace(
                trait, value=target, confidence=min(trait.confidence, .6 if key not in PROXY_KEYS else .45),
                source_kind=f"{trait.source_kind}_skill_evidence_v7",
                source_ids=list(dict.fromkeys([*trait.source_ids, SOURCE_ID])),
                notes=f"{trait.notes} V7 bounded NBA evidence/uncertainty calibration; not a measured skill rating.",
                components={**components, MARKER: info})
            changes[key] = info
        if changes:
            report["players"].append({"player_id": player.id, "name": player.name, "trait_changes": changes})
    report["adjusted_player_count"] = len(report["players"])
    report["adjusted_trait_count"] = len(replacements)
    return [replacements.get((t.player_id, t.trait_key), t) for t in traits], report
