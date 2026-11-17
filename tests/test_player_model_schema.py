"""Dormant model contracts: catalogue, ownership, strict values and real storage."""
import copy
import dataclasses
import json
import tempfile
import unittest
import weakref
from pathlib import Path

from nba_gm_data.player_model import (
    INPUT_VERSION, SAVE_SECTION, PlayerInputs, get_player_inputs,
    put_player_inputs, validate_input_section,
)
from nba_gm_data.player_model_registry import REGISTRY_VERSION, definition_registry, validate_registry
from nba_gm_data.save import load_save, validate_save_document, write_save
from nba_gm_data.history_store import SaveValidationError
from nba_gm_data.save_recovery import create_export, restore_export


def unknown():
    return {"status": "unknown", "value": None, "reason": "No defensible estimate yet", "evidence": [],
            "uncertainty": {"confidence": "unknown", "notes": "Missing evidence is not low ability"}}


def known(value):
    return {"status": "estimated", "value": value,
            "evidence": [{"source": "synthetic schema fixture", "method": "test only; not calibrated", "as_of": "2026-11-12", "sample_size": 4, "shared_evidence_id": "fixture-shared"}],
            "uncertainty": {"confidence": "low", "notes": "Synthetic test, no player estimate"}}


def example_value(d):
    if d['kind'] == 'grade':
        return {"grade": 71.25, "scale": "synthetic_test_anchors_v1"}
    if d['kind'] == 'physical':
        return {"measurements": [{"metric": "protocol_specific_observation", "value": 12.5, "unit": d['units'][0], "protocol": "synthetic protocol", "interval": [12, 13]}], "display_grade": {"grade": 70, "scale": "synthetic display only"}}
    if d['kind'] == 'propensity':
        return {"probability": .4, "reference_conditions": "synthetic reference opportunity"}
    outcomes = d['outcomes'] or ['region_left', 'region_right']
    result = {"reference_conditions": "synthetic reference opportunity", "rows": [{"condition": "all available", "probabilities": {key: 1/len(outcomes) for key in outcomes}}]}
    if d['id'] == 'T02': result['spatial_reference'] = 'synthetic court regions; not a league map'
    return result


def document(inputs=None):
    return {"version": INPUT_VERSION, "registry_version": REGISTRY_VERSION, "player_id": "fixture_player", "inputs": inputs or {}}


class PlayerModelSchemaTests(unittest.TestCase):
    def test_catalogue_counts_and_complete_ids(self):
        reg = definition_registry(); validate_registry(reg)
        ids = {d['id'] for d in reg['inputs']}
        expected = {f'{p}{i:02d}' for p,n in [('P',12),('S',46),('T',18)] for i in range(1,n+1)}
        expected |= {f'F{i:02d}.{part}' for i in range(1,10) for part in ('recognition','execution')}
        self.assertEqual(ids, expected)
        self.assertEqual(len(ids), 94)
        self.assertEqual(sum(d['kind']=='grade' for d in reg['inputs']), 64)
        self.assertEqual(len(reg['outputs']), 59)
        self.assertFalse(any(d['gameplay_active'] for d in reg['inputs']+reg['outputs']))

    def test_each_passing_dimension_retains_independent_value_and_evidence(self):
        records = {}
        for i in range(1,10):
            for part,score in [('recognition', i),('execution',100-i)]:
                records[f'F{i:02d}.{part}'] = known({'grade':score,'scale':'test anchors'})
        parsed = PlayerInputs(document(records))
        self.assertEqual(parsed.to_dict(), document(records))
        for i in range(1,10):
            self.assertNotEqual(parsed.input(f'F{i:02d}.recognition'), parsed.input(f'F{i:02d}.execution'))
        with self.assertRaises(ValueError): PlayerInputs(document({'F01': unknown()}))

    def test_all_94_unknown_and_known_representations(self):
        definitions=definition_registry()['inputs']
        for rows in ({d['id']:unknown() for d in definitions}, {d['id']:known(example_value(d)) for d in definitions}):
            value=PlayerInputs(document(rows))
            self.assertEqual(value.to_dict(), json.loads(json.dumps(document(rows))))

    def test_sparse_unknown_is_never_filled_or_zero(self):
        p=PlayerInputs(document({'S36':unknown()}))
        self.assertIsNone(p.input('S37'))
        self.assertIsNone(p.input('S36')['value'])
        self.assertEqual(set(p.to_dict()['inputs']), {'S36'})
        for value in (0,50,{},[]):
            row=unknown(); row['value']=value
            with self.assertRaises(ValueError): PlayerInputs(document({'S36':row}))
        row=unknown(); del row['reason']
        with self.assertRaises(ValueError): PlayerInputs(document({'S36':row}))

    def test_grades_types_ranges_finite_and_scales(self):
        for number in (-1,101,True,None,'70',float('nan'),float('inf'),float('-inf')):
            with self.subTest(number=number),self.assertRaises(ValueError):
                PlayerInputs(document({'S37':known({'grade':number,'scale':'test'})}))
        with self.assertRaises(ValueError): PlayerInputs(document({'S37':known({'grade':70,'scale':''})}))

    def test_units_protocols_and_separate_physical_grade(self):
        p=definition_registry()['inputs'][0]; value=example_value(p)
        original=copy.deepcopy(value)
        snapshot=PlayerInputs(document({'P01':known(value)}))
        self.assertEqual(snapshot.input('P01')['value'], original)
        for transform in (lambda v:v['measurements'][0].update(unit='inches'),lambda v:v['measurements'][0].update(value=-1), lambda v:v['measurements'][0].update(value=float('nan')),lambda v:v['measurements'][0].update(protocol=''),lambda v:v['measurements'][0].update(interval=[20,30]),lambda v:v['measurements'].append(copy.deepcopy(v['measurements'][0]))):
            v=copy.deepcopy(original); transform(v)
            with self.assertRaises(ValueError): PlayerInputs(document({'P01':known(v)}))
        value['display_grade']['grade']=1
        self.assertEqual(snapshot.input('P01')['value']['measurements'][0]['value'],12.5)
        # Multiple lateral/COD observations remain within one approved family.
        lateral={'measurements':[{'metric':'lateral_speed','value':3,'unit':'m/s','protocol':'without ball'}, {'metric':'redirection_time','value':.7,'unit':'s','protocol':'without ball'}]}
        self.assertEqual(len(PlayerInputs(document({'P07':known(lateral)})).input('P07')['value']['measurements']),2)

    def test_conditional_distributions_and_spatial_reference(self):
        d=next(x for x in definition_registry()['inputs'] if x['id']=='T01')
        value=example_value(d)
        value['rows'].append({'condition':'late clock','probabilities':{'shoot':1,'drive':0,'pass':0,'post':0,'reset':0}})
        self.assertEqual(PlayerInputs(document({'T01':known(value)})).input('T01')['value'],value)
        for transform in (lambda v:v['rows'][0]['probabilities'].update(shoot=.8),lambda v:v['rows'][0]['probabilities'].update(shoot=-.2),lambda v:v['rows'][0]['probabilities'].update(shoot=True),lambda v:v['rows'][0]['probabilities'].update(unknown_action=0),lambda v:v['rows'].append(copy.deepcopy(v['rows'][0]))):
            v=copy.deepcopy(value);transform(v)
            with self.assertRaises(ValueError): PlayerInputs(document({'T01':known(v)}))
        spatial=example_value(next(x for x in definition_registry()['inputs'] if x['id']=='T02'));del spatial['spatial_reference']
        with self.assertRaises(ValueError):PlayerInputs(document({'T02':known(spatial)}))

    def test_provenance_and_uncertainty_are_required_and_preserved(self):
        original=known({'grade':75,'scale':'test'})
        for transform in (lambda r:r.update(evidence=[]),lambda r:r['evidence'][0].update(method=''),lambda r:r['evidence'][0].update(as_of='2026-13-02'),lambda r:r['evidence'][0].update(sample_size=True),lambda r:r['evidence'][0].update(exposure={'value':float('nan'),'unit':'minutes'}),lambda r:r['uncertainty'].update(confidence='certain'),lambda r:r['uncertainty'].update(notes='')):
            row=copy.deepcopy(original);transform(row)
            with self.assertRaises(ValueError):PlayerInputs(document({'S36':row}))
        self.assertEqual(PlayerInputs(document({'S36':original})).input('S36'),original)

    def test_serialization_versions_and_strict_non_input_fields(self):
        for transform in (lambda d:d.update(version='future'),lambda d:d.update(registry_version='future'),lambda d:d.update(coach_instructions={}),lambda d:d.update(player_id=''),lambda d:d['inputs'].update(C27=unknown()),lambda d:d['inputs'].update(R18=unknown()),lambda d:d['inputs'].update(old_rim_protection=unknown())):
            d=document();transform(d)
            with self.assertRaises(ValueError):PlayerInputs(d)
        for malformed in (None,[],{'version':INPUT_VERSION}):
            with self.assertRaises(ValueError):PlayerInputs(malformed)

    def test_mutation_isolation_for_registry_records_and_save_helpers(self):
        d=document({'S36':known({'grade':70,'scale':'test'})}); p=PlayerInputs(d)
        d['inputs']['S36']['value']['grade']=0
        returned=p.to_dict();returned['inputs']['S36']['value']['grade']=1
        self.assertEqual(p.input('S36')['value']['grade'],70)
        with self.assertRaises(dataclasses.FrozenInstanceError):p._json='bad'
        reg=definition_registry();reg['inputs'][0]['units'].clear()
        self.assertEqual(definition_registry()['inputs'][0]['units'],['cm'])
        save={};put_player_inputs(save,p); loaded=get_player_inputs(save,'fixture_player')
        save[SAVE_SECTION]['players']['fixture_player']['inputs']['S36']['value']['grade']=2
        self.assertEqual(loaded.input('S36')['value']['grade'],70)
        self.assertIsNone(get_player_inputs({},'fixture_player'))
        self.assertEqual(get_player_inputs({},'fixture_player'),None)

    def test_dependency_contract_cycles_unknowns_summary_feedback_and_nontrainability(self):
        validate_registry()
        original=definition_registry()
        for mutate in (lambda r:r['outputs'][0]['dependencies'].append('bad'),lambda r:r['outputs'][0]['dependencies'].append('C31'),lambda r:r['outputs'][0]['dependencies'].append('C36'),lambda r:r['outputs'][0].update(trainable=True)):
            reg=copy.deepcopy(original);mutate(reg)
            with self.assertRaises(ValueError):validate_registry(reg)
        outputs={d['id']:d for d in original['outputs']}
        self.assertNotIn('C36',outputs['R18']['dependencies'])
        self.assertEqual(outputs['C36']['dependencies'],['C27','C32'])
        self.assertNotIn('C04',outputs['C31']['dependencies'])
        self.assertIn('C04',outputs['R21']['dependencies'])
        self.assertEqual(len([k for k in outputs['C33']['dependencies'] if k.startswith('F')]),9)
        self.assertTrue(all(k.endswith('recognition') for k in outputs['C33']['dependencies'] if k.startswith('F')))

    def test_optional_save_validation_roundtrip_export_restore_and_rejection_atomicity(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json'; restored=Path(folder)/'restored.json'
            save={'version':'league_save_v1','meta':{'id':'fixture','season':'2025-26'}}
            validate_save_document(save);self.assertNotIn(SAVE_SECTION,save)
            put_player_inputs(save,PlayerInputs(document({'S36':unknown()})))
            write_save(path,save); expected=get_player_inputs(save,'fixture_player').to_dict()
            self.assertEqual(get_player_inputs(load_save(path),'fixture_player').to_dict(),expected)
            restore_export(restored,create_export(path))
            self.assertEqual(get_player_inputs(load_save(restored),'fixture_player').to_dict(),expected)
            before=path.read_bytes(); bad=copy.deepcopy(save);bad[SAVE_SECTION]['version']='future'
            with self.assertRaises(SaveValidationError):write_save(path,bad)
            self.assertEqual(path.read_bytes(),before)
            path.write_text(json.dumps(bad))
            with self.assertRaises(SaveValidationError):load_save(path)

    def test_snapshot_releases_without_save_or_global_ownership(self):
        save={}
        snapshot=PlayerInputs(document({'S36':unknown()}))
        reference=weakref.ref(snapshot)
        put_player_inputs(save,snapshot)
        del snapshot
        self.assertIsNone(reference())
        self.assertEqual(get_player_inputs(save,'fixture_player').input('S36'),unknown())

    def test_unsupported_sections_and_malformed_player_keys(self):
        section={'version':INPUT_VERSION,'registry_version':REGISTRY_VERSION,'players':{'fixture_player':document()}}
        for mutate in (lambda v:v.update(version='future'),lambda v:v.update(registry_version='future'),lambda v:v.update(players=[]),lambda v:v.update(extra=1),lambda v:v['players'].update(fixture_player=None)):
            value=copy.deepcopy(section);mutate(value)
            with self.assertRaises(ValueError):validate_input_section(value)
        for key in ('C27','R18','missing'):
            with self.assertRaises(ValueError):PlayerInputs(document()).input(key)

    def test_physical_zero_dimensions_nonfinite_and_unknown_units(self):
        for value in (0,True,float('inf'),10**1000):
            physical={'measurements':[{'metric':'height','value':value,'unit':'cm','protocol':'test'}]}
            with self.assertRaises(ValueError):PlayerInputs(document({'P01':known(physical)}))
        for physical in ({'measurements':[]},{'measurements':[],'display_grade':{'grade':70,'scale':'test'}},{'measurements':[{'metric':'height','value':190,'unit':'grade_0_100','protocol':'test'}]}):
            with self.assertRaises(ValueError):PlayerInputs(document({'P01':known(physical)}))

    def test_section_player_identity_and_atomic_attach(self):
        section={'version':INPUT_VERSION,'registry_version':REGISTRY_VERSION,'players':{'other':document()}}
        with self.assertRaises(ValueError):validate_input_section(section)
        bad={SAVE_SECTION:section};before=copy.deepcopy(bad)
        with self.assertRaises(ValueError):put_player_inputs(bad,PlayerInputs(document()))
        self.assertEqual(before,bad)


if __name__=='__main__':unittest.main()
