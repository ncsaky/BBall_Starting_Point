"""Explicit, hash-pinned evidence proposals; no in-progress or implicit reads."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from nba_gm_data.experimental_inputs import InterpretedInputs
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from experiments.player_input_pilot.pilot import export_layer

VERSION='pilot_targeted_input_overlay_2026_11_14_v1'


def apply_overlay(pilot,path,expected_sha256):
    raw=Path(path).read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if not expected_sha256 or digest!=expected_sha256:raise ValueError('Explicit pinned overlay SHA256 mismatch')
    overlay=json.loads(raw)
    if overlay['version']!=VERSION:raise ValueError('Unsupported evidence overlay version')
    base=Path(__file__).resolve().parents[2]/overlay['base_artifact']
    if hashlib.sha256(base.read_bytes()).hexdigest()!=overlay['base_sha256']:raise ValueError('Evidence overlay baseline hash conflict')
    baseline=json.loads(base.read_text());current=export_layer(pilot)
    if overlay['source_section']!=current['source_section']:raise ValueError('Evidence overlay changed original source records')
    if overlay['contract']!=asdict(pilot['contract']) or overlay['contract_revision']!=pilot['contract'].revision:raise ValueError('Evidence cannot silently change interpretation')
    for key in ('source_section','pilot_section'):validate_input_section(overlay[key])
    if baseline['source_section']!=overlay['source_section']:raise ValueError('Pinned source archive conflict')
    documents={pid:view.to_dict() for pid,view in pilot['views'].items()};changes=deepcopy(pilot.get('overrides',[]));seen=set();applied=[];skipped=[]
    for update in overlay['overrides']:
        pid,key=update['player_id'],update['design_id']
        if (pid,key) in seen:raise ValueError('Duplicate overlay field')
        seen.add((pid,key))
        if baseline['pilot_section']['players'][pid]['inputs'][key]!=update['baseline_record']:raise ValueError('Overlay expected prior conflicts with pinned baseline')
        if overlay['source_section']['players'][pid]['inputs'][key]!=update['source_record']:raise ValueError('Overlay source record conflict')
        before=documents[pid]['inputs'][key];after=update['scenario_record']
        if before==after:skipped.append([pid,key]);continue
        if before!=update['baseline_record']:raise ValueError(f'Explicit rebase needed for {pid}/{key}')
        documents[pid]['inputs'][key]=deepcopy(after)
        changes.append({**deepcopy(update),'evidence_overlay_sha256':digest,'evidence_update':True})
        applied.append([pid,key])
    # The complete proposed section must equal the declared per-field changes.
    if documents!=overlay['pilot_section']['players']:raise ValueError('Undeclared proposed-section changes or incompatible rebasing')
    result={**pilot,'documents':documents,'views':{pid:InterpretedInputs(PlayerInputs(doc),pilot['contract']) for pid,doc in documents.items()},
        'overrides':changes,'scenario':overlay['scenario'],'targeted_evidence_sha256':digest}
    result['overlay_audit']={'version':VERSION,'sha256':digest,'base_sha256':overlay['base_sha256'],
        'applied_fields':applied,'already_identical_fields':skipped,'source_records_preserved':True,
        'new_targeted_records':overlay['new_targeted_record_count'],'inherited_records':overlay['inherited_record_count'],
        'range_records':[{k:deepcopy(u[k]) for k in ('player_id','design_id','range','origin','shared_evidence_group')} for u in overlay['overrides']]}
    return result,overlay


def selected_fields(base,proposed,keys,label):
    """Explicit attribution controls, never an implicit partial evidence update."""
    docs={pid:view.to_dict() for pid,view in base['views'].items()}
    chosen=[deepcopy(u) for u in proposed['overrides'] if (u['player_id'],u['design_id']) in keys]
    for u in chosen:docs[u['player_id']]['inputs'][u['design_id']]=deepcopy(u['scenario_record'])
    return {**base,'documents':docs,'views':{pid:InterpretedInputs(PlayerInputs(doc),base['contract']) for pid,doc in docs.items()},
        'overrides':chosen,'scenario':label,'targeted_evidence_sha256':proposed['targeted_evidence_sha256']}
