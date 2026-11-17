"""Evidence resolutions for known team-aggregated salary source records."""
from copy import deepcopy

from .schema import to_plain
from .utils import stable_id

RESOLUTIONS_FILE = "data/overrides/contract_import_resolutions.json"


def resolve_contract_imports(players, teams, research, resolutions):
    """Resolve explicit source signatures, never infer net set-off or other aggregates."""
    research = deepcopy(research or {})
    players = {player["id"]: player for player in to_plain(players)}
    teams = {team["abbrev"]: team["id"] for team in to_plain(teams)}
    obligations, reports = [], []
    for spec in resolutions.get("resolutions", []):
        player = players.get(spec["player_id"])
        if player is None:
            continue
        if research.get("source", {}).get("id") != spec["source_id"]:
            raise ValueError("Contract resolution source changed; review " + spec["id"])
        rows = [row for row in research.get("contracts", [])
                if row.get("normalized_name") == spec["normalized_name"]]
        by_team = lambda row: row.get("team_abbrev", "")
        if sorted(rows, key=by_team) != sorted(spec["expected_aggregate_rows"], key=by_team):
            raise ValueError("Contract aggregate signature changed; review " + spec["id"])
        # Preserve aggregate source semantics but exclude those rows from active
        # matching. The separately sourced component is the only active contract.
        for row in rows:
            row["record_kind"] = "resolved_aggregate_source"
            row["resolution_id"] = spec["id"]
        active = deepcopy(spec["active_contract"])
        active.update(normalized_name=spec["normalized_name"], record_kind="resolved_active_contract")
        research["contracts"].append(active)
        for item in spec.get("former_team_obligations", []):
            team_id = teams[item["former_team_abbrev"]]
            schedule = deepcopy(item["original_stretch_schedule"])
            obligations.append({
                **deepcopy(item),
                "id": stable_id("imported_waived_salary", spec["id"], team_id,
                                schedule[0]["season"], schedule[-1]["season"]),
                "team_id": team_id, "player_id": player["id"], "player_name": player["name"],
                "contract_id": stable_id("former_contract", spec["id"], team_id),
                "source_ids": [spec["id"]], "unverified": True, "unquantified": False,
                "relief_status": "gross_stretch_reserve_pending_verified_setoff",
                "seasons": [{"season": row["season"], "salary": row["gross_salary"],
                             "gross_salary": row["gross_salary"], "net_salary": None,
                             "setoff_amount": None, "unverified_reserve": row["gross_salary"]}
                            for row in schedule],
            })
        reports.append({"resolution_id": spec["id"], "source_id": spec["source_id"],
                        "source_rows": deepcopy(rows), "component_artifact": spec["component_artifact"]})
    return research, obligations, reports


def initialize_imported_obligations(save, canonical):
    """Creation only: never called from load/repair, nor overwrite later relief."""
    meta = save.setdefault("meta", {})
    if meta.get("imported_waived_salary_initialized"):
        return
    if meta.get("starting_data_version") != canonical.get("meta", {}).get("starting_data_version"):
        raise ValueError("Cannot initialize imported obligations across career baselines.")
    ledger = save.setdefault("waived_salary_obligations", [])
    ids = {row["id"] for row in ledger}
    season = str(meta["season"])
    for row in canonical.get("waived_salary_obligations", []):
        if row["id"] in ids:
            continue
        entry = deepcopy(row)
        entry["seasons"] = [term for term in entry["seasons"] if term["season"] >= season]
        if entry["seasons"]:
            ledger.append(entry)
            ids.add(entry["id"])
    meta["imported_waived_salary_initialized"] = True
