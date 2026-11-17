"""Bounded registry/coverage export and disposable real app-action storage probe.

No day advancement, server changes, gameplay input population or canonical edits.
Run: PYTHONPATH=src .venv/bin/python scripts/verify_player_model_schema.py
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path

from nba_gm_data import app_actions
from nba_gm_data.player_model import INPUT_VERSION, SAVE_SECTION, PlayerInputs, get_player_inputs, put_player_inputs
from nba_gm_data.player_model_registry import REGISTRY_VERSION, definition_registry, validate_registry
from nba_gm_data.save import load_save, write_save


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('output/player-model-schema-2026-11-12'))
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    registry=definition_registry(); validate_registry(registry)
    nodes={row['id']:row for row in registry['inputs']+registry['outputs']}

    def ancestors(key):
        result=set()
        for dep in nodes[key].get('dependencies',[]):
            result.add(dep);result.update(ancestors(dep))
        return result

    coverage=[]
    for definition in registry['inputs']:
        key=definition['id']
        coverage.append({
            'id':key,'family':definition['family'],'name':definition['name'],
            'definition':'implemented_versioned','evidence_estimation':'unpopulated_unknown; research ledger separate',
            'storage':f'{SAVE_SECTION}.players[<player_id>].inputs["{key}"]',
            'storage_status':'optional_validated_dormant',
            'planned_capability_consumers':[row['id'] for row in registry['outputs'] if row['id'].startswith('C') and key in row['dependencies']],
            'planned_role_outputs':[row['id'] for row in registry['outputs'] if row['id'].startswith('R') and key in ancestors(row['id'])],
            'actual_gameplay_consumers':[],'gameplay_status':'dormant_unimplemented',
            'planned_presentation':'inspectable raw input with evidence/uncertainty; derived profiles/roles once calibrated',
            'actual_presentation_consumers':[],'presentation_status':'unimplemented',
            'verification':['test_catalogue_counts_and_complete_ids','test_all_94_unknown_and_known_representations','test_optional_save_validation_roundtrip_export_restore_and_rejection_atomicity'],
            'consumer_verification':'not_applicable_until_activation',
            'complete':False,
        })
    output_status=[{**row,'definition_status':'registered_pending_technical_verification','storage_status':'not_independently_stored','actual_gameplay_consumers':[],'presentation_status':'unimplemented'} for row in registry['outputs']]
    (args.output/'registry.json').write_text(json.dumps(registry,indent=2)+'\n')
    (args.output/'coverage.json').write_text(json.dumps({'registry_version':REGISTRY_VERSION,'inputs':{row['id']:row for row in coverage},'derived_and_roles':{row['id']:row for row in output_status}},indent=2)+'\n')
    canonical=app_actions.load_app_canonical(root)
    with tempfile.TemporaryDirectory(prefix='player-model-schema-probe-') as directory:
        directory=Path(directory)
        def action(name,**payload):
            return app_actions.dispatch_app_action(name,payload,root=root,save_dir=directory,canonical=canonical)
        created=action('create_save',save_name='schema_probe',team='GSW',seed=17)
        path=Path(created['save_path'])
        save=load_save(path)
        assert SAVE_SECTION not in save
        player_id=next(p['id'] for p in canonical['players'] if 'Stephen Curry'==p['name'])
        before_card=copy.deepcopy(action('player_card',save_name=path.name,player_id=player_id))
        before_state=copy.deepcopy(save['state'])
        record={'version':INPUT_VERSION,'registry_version':REGISTRY_VERSION,'player_id':player_id,'inputs':{
            'S36':{'status':'unknown','value':None,'reason':'Probe: no estimate supplied','evidence':[],
                   'uncertainty':{'confidence':'unknown','notes':'Not populated or used by gameplay'}},
            'F01.recognition':{'status':'estimated','value':{'grade':23,'scale':'synthetic_probe_only_not_calibrated'},
                   'evidence':[{'source':'synthetic disposable persistence probe','method':'serialization test only'}],
                   'uncertainty':{'confidence':'low','notes':'Not a real player estimate'}},
            'F01.execution':{'status':'unknown','value':None,'reason':'Probe: keep passing dimensions distinct','evidence':[],
                   'uncertainty':{'confidence':'unknown','notes':'Not a default of zero or 50'}},
        }}
        put_player_inputs(save,PlayerInputs(record));write_save(path,save)
        app_actions.invalidate_read_cache(path)
        persisted=get_player_inputs(load_save(path),player_id).to_dict()
        assert persisted==record
        after_card=action('player_card',save_name=path.name,player_id=player_id)
        assert before_card==after_card
        settings=copy.deepcopy(save.get('game_settings',{}))
        action('update_game_settings',save_name=path.name,settings=settings)
        after_mutation=load_save(path)
        assert get_player_inputs(after_mutation,player_id).to_dict()==record
        # Legal actions may be refreshed by the normal settings action; date and phase cannot advance.
        assert after_mutation['state']['current_date']==before_state['current_date']
        assert after_mutation['state']['phase']==before_state['phase']
        exported=action('export_save',save_name=path.name)
        action('restore_save',save_name='schema_restored',archive_base64=exported['archive_base64'])
        restored_path=directory/'schema_restored.json'
        restored=load_save(restored_path)
        assert get_player_inputs(restored,player_id).to_dict()==record
        restored_card=action('player_card',save_name=restored_path.name,player_id=player_id)
        assert restored_card==before_card
        app_actions.invalidate_read_cache(path);app_actions.invalidate_read_cache(restored_path)
        result={'counts':{'inputs':94,'skills':64,'physical_families':12,'tendency_families':18,'capabilities':37,'roles_outputs':22},
                'actions':['create_save','player_card before','write_save with private synthetic inputs','player_card after','update_game_settings','export_save','restore_save','player_card restored'],
                'player_id':player_id,'date':before_state['current_date'],'input_roundtrip_equal':True,'settings_action_preserves_inputs':True,
                'full_player_cards_equal':True,'card_digest':digest(before_card),'input_digest':digest(record),
                'synthetic_input_bytes':len(json.dumps(record).encode()),'canonical_digest_after':digest(canonical),
                'saved_probe_files_retained':False,'gameplay_activated':False,'preview_restarted':False}
    (args.output/'action-probe.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
