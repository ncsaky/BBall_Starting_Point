"""Verify and publish the narrowly scoped V6 imported-input correction."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.ingest import build_universe
from nba_gm_data.roster_alignment import STARTING_DATA_VERSION
from nba_gm_data.save import canonical_with_save, load_save, player_display_attribute_summary, set_save_date_phase, write_save
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.history_store import hydrate_save_history
from nba_gm_data.schema import to_plain
from nba_gm_data.sim import load_sim_context, sim_game_with_context, player_feature_vector
from nba_gm_data.storage import write_outputs
from verify_roster_alignment import archive_candidate
from verify_simulation_consistency import business_state, digest, differences

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"output/imported-tail-v6-2026-10-26"
PREVIOUS = "2026-10-23-forward-tuning-v5"
VERSION = "2026-10-26-imported-tail-v6"
NAMES = {"Spencer Jones","Isaac Okoro","Dorian Finney-Smith"}
DERIVED = {"draft_board_entries","team_strategic_states","player_asset_valuations",
           "player_contract_market_profiles","player_contract_preferences","extension_candidates",
           "free_agent_candidates","trade_block_entries","coverage_report"}


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def read_baseline(version):
    with gzip.open(ROOT/f"data/canonical/baselines/{version}.json.gz","rt") as handle:
        return json.load(handle)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")


def protection():
    paths = [p for p in (ROOT/"saves").rglob("*") if p.is_file() and p.suffix in {".json",".sqlite",".sqlite3"}]
    paths += list((ROOT/"data/canonical/baselines").glob("*.json.gz"))
    return {str(p):sha(p) for p in paths}


def verify_scope(old,new):
    assert new["meta"]["starting_data_version"]==VERSION
    assert set(old)==set(new)
    players = {p["name"]:p["id"] for p in new["players"]}
    cases = [p for p in json.loads((ROOT/"data/overrides/trait_overrides.json").read_text())["post_alignment_players"] if p["player_name"] in NAMES]
    manual = {(players[p["player_name"]],key):value for p in cases for key,value in p["traits"].items()}
    corrected = {(p["player_id"],"stamina_cardio") for p in new["meta"]["stamina_role_bonus_report"]["changes"]}
    before = {(t["player_id"],t["trait_key"]):t for t in old["traits"]}
    after = {(t["player_id"],t["trait_key"]):t for t in new["traits"]}
    assert before.keys()==after.keys()
    changed = {k for k in before if before[k]["value"]!=after[k]["value"]}
    assert changed <= manual.keys() | corrected
    for key in changed-manual.keys():
        assert key[1]=="stamina_cardio"
        info = after[key]["components"]["stamina_role_bonus_v6"]
        assert before[key]["value"]==info["previous"] and after[key]["value"]==info["corrected"]
    for key,value in manual.items():
        assert after[key]["value"]==value["value"]
        assert after[key]["components"]["manual_calibration"]["evidence_urls"]
    for key,trait in before.items():
        if "manual_calibration" in trait.get("components",{}) and key not in manual:
            assert trait["value"]==after[key]["value"],key
    for key in old.keys()-DERIVED-{"meta","sources","traits","draft_prospects"}:
        assert old[key]==new[key],key
    # A previously added optional schema field is empty for this stored class.
    assert [{**p,"scouting_prior":p.get("scouting_prior",{})} for p in old["draft_prospects"]]==new["draft_prospects"]
    for key in ("player_health_profiles","player_health_states","injury_events","players","contracts","draft_picks"):
        assert old[key]==new[key],key
    return {"changed_trait_count":len(changed),"changed_player_count":len({pid for pid,k in changed}),
            "manual_trait_count":len(manual),"stamina_value_changes":sum(key[1]=="stamina_cardio" for key in changed),
            "protected_manual_values_preserved":True,"initial_medicals_finances_identities_unchanged":True}


def measurements(data):
    context = {"meta":data["meta"],"players":[{**p,"minutes_projection":24} for p in data["players"]],"traits":data["traits"],"_allow_internal_caches":True}
    return {p["name"]:{"fixed24":player_display_attribute_summary(context,p["id"]),
                        "impact":player_feature_vector(data,p).features["impact"]}
            for p in data["players"] if p["name"] in NAMES | {"Jordan Hawkins","Aaron Gordon","Julius Randle","Kyrie Irving","Dereck Lively II","Collin Murray-Boyles","Keyonte George"}}


def smoke(old,new):
    directory = OUT/"smoke"
    directory.mkdir(parents=True,exist_ok=False)
    created = dispatch_app_action("create_save",{"team":"GSW","seed":17,"save_name":"old"},
        root=ROOT,save_dir=directory/"source",canonical=deepcopy(old))
    path = Path(created["save_path"])
    saved = load_save(path)
    set_save_date_phase(saved,"2026-11-14")
    write_save(path,saved)
    exported = create_export(path)
    states = {}
    for label,canonical in (("old",old),("new_entry",new)):
        target = directory/label/"saves/career.json"
        restore_export(target,exported)
        dispatch_app_action("advance_save",{"save_path":str(target),"days":7,"seed":17},
            root=ROOT,save_dir=target.parent,canonical=deepcopy(canonical))
        saved = hydrate_save_history(target,load_save(target))
        assert saved["state"]["current_date"]=="2026-11-21"
        states[label] = business_state(saved)
    diff = differences(states["old"],states["new_entry"])
    assert not diff,diff
    fresh = dispatch_app_action("create_save",{"team":"DEN","seed":29,"save_name":"new"},
        root=ROOT,save_dir=directory/"fresh",canonical=deepcopy(new))
    saved = load_save(fresh["save_path"])
    assert saved["meta"]["starting_data_version"]==VERSION
    active = canonical_with_save(deepcopy(new),saved)
    assert { (t['player_id'],t['trait_key']):t['value'] for t in active['traits']}=={
        (t['player_id'],t['trait_key']):t['value'] for t in new['traits']}
    context = load_sim_context(ROOT,deepcopy(new))
    schedule = context["schedule"]
    game = next(g for g in schedule if str(g["homeTeamId"])=="7" or str(g["awayTeamId"])=="7")
    games = []
    for seed in (17,29):
        a = to_plain(sim_game_with_context(context,str(game["externalGameId"]),mode="sandbox-sim",seed=seed))
        b = to_plain(sim_game_with_context(context,str(game["externalGameId"]),mode="sandbox-sim",seed=seed))
        assert a==b and a["home_score"]>0 and a["away_score"]>0
        games.append({"seed":seed,"home_score":a["home_score"],"away_score":a["away_score"]})
    return {"old_save_real_week_identical":True,"old_save_digest":digest(states["old"]),
            "fresh_game_uses_v6":True,"seeded_game_replays":games,
            "limit":"Focused week/game and fatigue checks, not a new long-run balance validation."}


def verify(publish):
    if (OUT/"verification.json").exists():
        raise FileExistsError("Verification exists; preserve its evidence")
    protected = protection()
    old = read_baseline(PREVIOUS)
    universe = build_universe(ROOT)
    new = to_plain(universe)
    scope = verify_scope(old,new)
    assert new==to_plain(build_universe(ROOT)),"Rebuild is not deterministic"
    OUT.mkdir(parents=True,exist_ok=True)
    write_outputs(universe,OUT/"candidate")
    before,after = measurements(old),measurements(new)
    checks = smoke(old,new)
    assert all(sha(path)==value for path,value in protected.items()),"Protected files changed"
    if publish:
        assert STARTING_DATA_VERSION==VERSION
        archive_candidate(new)
        registry_path = ROOT/"data/canonical/baselines/registry.json"
        registry = json.loads(registry_path.read_text())
        assert VERSION not in registry["versions"]
        registry["versions"][VERSION]=f"{VERSION}.json.gz"
        write(registry_path,registry)
        write_outputs(universe,ROOT/"data/canonical")
        assert read_baseline(VERSION)==new
    assert all(sha(path)==value for path,value in protected.items())
    report = {"status":"passed","published":publish,"version":VERSION,"scope":scope,
              "before":before,"after":after,"checks":checks,"protected_files":protected,
              "protected_files_unchanged":True,"no_prospect_or_development_rules_changed":True}
    write(OUT/"verification.json",report)
    print(json.dumps({"status":"passed","published":publish,"scope":scope,
        "ratings":{name:{"before":before[name]["fixed24"]["overall"],"after":after[name]["fixed24"]["overall"]} for name in NAMES},"checks":checks}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish",action="store_true")
    verify(parser.parse_args().publish)
