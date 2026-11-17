"""Offline pipeline equations, fixed references, independent channels and purity."""
from copy import deepcopy
import math,random,unittest
from nba_gm_data.traits import build_traits_for_player
from nba_gm_data.utils import percentile_maps
from experiments.defensive_inputs.model import (KEYS,FIELDS,finite,infer,tail_scale,
    freeze_reference,fixed_lookup,experiment,reapply_overrides,source_overlap)


def row(name='test',**edits):
    r={f:50 for f in FIELDS};r.update(name=name,primaryOffRole='Connector',primaryDefRole='Rim Protector',position='C',minutes=20)
    r.update(edits);return r


class DefensiveInputReconstructionTests(unittest.TestCase):
    def test_uncapped_values_recovered_from_actual_formula_not_final_100(self):
        r=row();got=infer(r,lambda f:100)
        self.assertEqual(got['rim_deterrence']['preclip'],116)
        self.assertEqual(got['rim_deterrence']['capped'],100)
        r2=row(primaryDefRole='None',primaryOffRole='None')
        self.assertEqual(infer(r2,lambda f:100)['rim_deterrence']['preclip'],100)
        self.assertNotEqual(tail_scale(103),tail_scale(108))

    def test_exact_equations_match_authoritative_builder_missing_roles_and_zero(self):
        rows=[row('a'),row('b',primaryDefRole='Versatile Stopper',position='PG'),
              row('c',primaryDefRole='Mobile Forward',primaryOffRole='Primary Ball Handler'),
              row('d',**{f:None for f in FIELDS}),row('e',**{f:0 for f in FIELDS})]
        for i,r in enumerate(rows):
            maps={f:{i:v} for f in FIELDS if (v:=finite(r.get(f))) is not None}
            got=infer(r,lambda f:maps.get(f,{}).get(i))
            for t in build_traits_for_player(r,i,str(i),maps):
                if t.trait_key in KEYS:self.assertEqual(t.value,got[t.trait_key]['capped'])

    def test_fallback_zero_is_explicit_not_silently_mistaken_for_missing(self):
        got=infer(row(),lambda f:0)
        self.assertTrue(got['rim_deterrence']['known_zero_replaced_by_50'])
        self.assertEqual(got['rim_deterrence']['preclip'],56)
        self.assertFalse(infer(row(),lambda f:None)['rim_deterrence']['known_zero_replaced_by_50'])

    def test_fixed_scale_anchors_monotonicity_and_headroom(self):
        for a,b in ((0,0),(50,50),(80,80),(100,90),(120,95),(140,97.5)):
            self.assertAlmostEqual(tail_scale(a),b)
        ys=[tail_scale(i/10) for i in range(2001)]
        self.assertTrue(all(a<b for a,b in zip(ys,ys[1:])))
        self.assertTrue(all(0<=v<100 for v in ys))
        self.assertEqual(tail_scale(-10),0)
        with self.assertRaises(ValueError):tail_scale(float('inf'))
        with self.assertRaises(ValueError):tail_scale(float('nan'))

    def test_fixed_lookup_equal_raw_values_have_equal_grades_and_tail_headroom(self):
        ref=freeze_reference([row(str(i),BLKpct=v) for i,v in enumerate((0,0,1,2,10))],'frozen')
        self.assertEqual(fixed_lookup(ref,'BLKpct',0),13.25)
        xs=[fixed_lookup(ref,'BLKpct',v) for v in (-10,-1,0,.5,1,2,10,11,100)]
        self.assertTrue(all(a<b for a,b in zip(xs,xs[1:])))
        self.assertIsNone(fixed_lookup(ref,'BLKpct',None))
        self.assertIsNone(fixed_lookup(ref,'BLKpct',float('nan')))

    def test_membership_outliers_import_order_and_repeat_cannot_change_reference(self):
        rows=[row(str(i),BLKpct=i,STLpct=i/10,HeightSocks=70+i) for i in range(12)]
        ref=freeze_reference(rows,'frozen');before=deepcopy(ref);expected=[experiment(r,ref) for r in rows]
        self.assertEqual(list(reversed([experiment(r,ref) for r in reversed(rows)])),expected)
        self.assertEqual([experiment(r,ref) for r in rows[::3]],expected[::3])
        experiment(row('outlier',**{f:1e9 for f in FIELDS}),ref)
        self.assertEqual([experiment(r,ref) for r in rows],expected)
        self.assertEqual(ref,before)

    def test_tail_joins_are_continuous_even_with_tied_extreme_observations(self):
        ref=freeze_reference([row(str(i),BLKpct=v) for i,v in enumerate((0,0,1,2,2))],'frozen')
        for edge in (0,2):
            at=fixed_lookup(ref,'BLKpct',edge)
            self.assertAlmostEqual(at,fixed_lookup(ref,'BLKpct',edge-1e-9),places=6)
            self.assertAlmostEqual(at,fixed_lookup(ref,'BLKpct',edge+1e-9),places=6)
        single=freeze_reference([row()],'frozen')
        self.assertEqual(fixed_lookup(single,'BLKpct',50),50)
        self.assertLess(fixed_lookup(single,'BLKpct',49),50)
        self.assertGreater(fixed_lookup(single,'BLKpct',51),50)

    def test_original_ordinal_percentiles_split_identical_values_by_input_order(self):
        rows=[row('a',BLKpct=0),row('b',BLKpct=0),row('c',BLKpct=1)]
        m=percentile_maps(rows,['BLKpct'])
        self.assertNotEqual(m['BLKpct'][0],m['BLKpct'][1])
        ref=freeze_reference(rows,'frozen')
        self.assertEqual(experiment(rows[0],ref)['A_fixed_reference'],experiment(rows[1],ref)['A_fixed_reference'])

    def test_official_physical_overlay_is_distinct_from_original_defensive_evidence(self):
        from nba_gm_data.ingest import update_player_row_from_official
        original=row(HeightSocks=78,position='SG',BLKpct=2);updated=deepcopy(original)
        update_player_row_from_official(updated,{'position':'C','height':'7-0'},'AAA')
        self.assertEqual(original['HeightSocks'],78)
        self.assertEqual(updated['HeightSocks'],84)
        self.assertEqual(updated['BLKpct'],original['BLKpct'])
        ref=freeze_reference([row('a',HeightSocks=72),row('b',HeightSocks=84)],'frozen')
        self.assertNotEqual(experiment(original,ref)['B_rim_hypothesis'],experiment(updated,ref)['B_rim_hypothesis'])

    def test_evidence_alternative_is_not_role_label_or_generic_impact_recycling(self):
        rows=[row(str(i),**{f:i for f in FIELDS}) for i in range(100)]
        ref=freeze_reference(rows,'frozen');r=rows[50];a=experiment(r,ref)
        b=experiment({**r,'CraftedDPM':99,'DARKO':99,'primaryDefRole':'Rim Protector','primaryOffRole':'Versatile Stopper'},ref)
        self.assertEqual(a['B_rim_hypothesis'],b['B_rim_hypothesis'])
        self.assertEqual(a['B_channels']['event_disruption_proxy'],b['B_channels']['event_disruption_proxy'])
        self.assertNotEqual(a['B_channels']['general_defensive_impact_context'],b['B_channels']['general_defensive_impact_context'])
        for k in ('containment','screen_technique','help_execution','sample_reliability'):
            self.assertIsNone(a['B_channels'][k])

    def test_same_protection_evidence_uses_same_scale_across_positions_and_roles(self):
        ref=freeze_reference([row(str(i),**{f:i for f in FIELDS}) for i in range(100)],'frozen')
        base=row(**{f:75 for f in FIELDS});expected=experiment(base,ref)['B_rim_hypothesis']
        for pos,role in (('PG','Hidden'),('SG','On-Ball Guard'),('SF','Mobile Forward'),('C','Rim Protector')):
            self.assertEqual(experiment({**base,'position':pos,'primaryDefRole':role},ref)['B_rim_hypothesis'],expected)

    def test_normal_source_increases_remain_monotone_without_endpoint_pileup(self):
        ref=freeze_reference([row(str(i),**{f:i for f in FIELDS}) for i in range(100)],'frozen')
        values=[experiment(row(BLKpct=x,HeightSocks=85),ref)['B_rim_hypothesis'] for x in range(201)]
        self.assertTrue(all(a<b for a,b in zip(values,values[1:])))
        self.assertTrue(all(v<100 for v in values))

    def test_missing_block_evidence_cannot_be_replaced_by_height_or_role(self):
        ref=freeze_reference([row('a'),row('b',BLKpct=100)],'frozen')
        r=experiment(row(BLKpct=None,HeightSocks=100),ref)
        self.assertIsNone(r['B_rim_hypothesis'])
        self.assertIsNone(r['B_channels']['protection_proxy'])

    def test_reviewed_overrides_reapplied_and_missing_estimates_held_explicitly(self):
        current={k:80 for k in KEYS};candidate={k:50 for k in KEYS};candidate['scheme_iq']=None
        a,status=reapply_overrides(candidate,current,{'rim_deterrence'})
        self.assertEqual(a['rim_deterrence'],80);self.assertEqual(a['scheme_iq'],80)
        self.assertEqual(a['screen_navigation'],50)
        self.assertIn('override',status['rim_deterrence']);self.assertIn('held',status['scheme_iq'])
        self.assertEqual(current,{k:80 for k in KEYS})

    def test_shared_dependency_mass_is_structural_and_tracks_near_duplicate_channels(self):
        weights={k:v['normalized_source_weights'] for k,v in infer(row(),lambda f:50).items()}
        overlap=source_overlap(weights)
        self.assertAlmostEqual(overlap['foot_speed_lateral_agility']['screen_navigation'],.98)
        self.assertAlmostEqual(overlap['defensive_effort']['foot_speed_lateral_agility'],.78)
        self.assertAlmostEqual(overlap['rim_deterrence']['defensive_effort'],.15)

    def test_role_bonuses_can_depend_on_offensive_label_and_size_threshold(self):
        none=row(primaryDefRole='Unknown',primaryOffRole='Unknown')
        p=lambda f:50
        a=infer(none,p);b=infer({**none,'primaryOffRole':'Primary Ball Handler'},p)
        self.assertEqual(b['scheme_iq']['preclip']-a['scheme_iq']['preclip'],8)
        r=row();lo=infer(r,lambda f:81.99);hi=infer(r,lambda f:82)
        self.assertEqual(lo['rim_deterrence']['role_bonus'],6)
        self.assertEqual(hi['rim_deterrence']['role_bonus'],16)

    def test_output_mutation_and_rng_purity(self):
        rows=[row('a'),row('b',BLKpct=70)];ref=freeze_reference(rows,'frozen')
        state=random.getstate();before=deepcopy((rows,ref));a=experiment(rows[0],ref)
        a['A_uncapped']['rim_deterrence']['source_contributions']['BLKpct']=-999
        self.assertEqual((rows,ref),before);self.assertEqual(state,random.getstate())
        self.assertNotEqual(a,experiment(rows[0],ref))

if __name__=='__main__':unittest.main()
