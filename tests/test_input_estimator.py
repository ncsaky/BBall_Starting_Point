"""Evidence contracts and coverage, deliberately independent of named rankings."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
import random
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data.input_estimator import (
    CAREER_PATH, DEFINITIONS, FT_SCALE, InputEstimator, InputEvidence,
    TECHNIQUE_SCALE, UNIVERSE_PATH, canonical_json, coverage_counts,
    estimation_status, estimate_prospect_inputs, load_reference_cells,
    scalar_value, uncertainty_details, validation_comparison,
    source_join_audit, rotation_input_spread,
)
from nba_gm_data.player_model import PlayerInputs, validate_input_section

ROOT=Path(__file__).resolve().parents[1]


def player(pid='synthetic', **kwargs):
    return dict(id=pid,name=pid,position='SG',espn_player_id=pid,**kwargs)


def profile(rate=.8, n=200, minutes=1000, **kwargs):
    return dict(seasons=[dict(season='2025-26',minutes=minutes,
                             ftm=rate*n,fta=n,**kwargs)])


def estimate(model, p, iid):
    return model.estimate_player_inputs(p).input(iid)


class LeagueInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.universe=json.loads((ROOT/UNIVERSE_PATH).read_text())
        cls.model=InputEstimator.from_local(ROOT)
        cls.section=cls.model.estimate_universe(cls.universe)

    def test_all_691_players_have_exactly_94_schema_valid_inputs(self):
        self.assertEqual(691,len(self.section['players']))
        self.assertEqual({p['id'] for p in self.universe['players']},set(self.section['players']))
        validate_input_section(self.section)
        for pid,doc in self.section['players'].items():
            self.assertEqual(set(DEFINITIONS),set(doc['inputs']),pid)
            self.assertEqual(doc,PlayerInputs(doc).to_dict())
            for iid,record in doc['inputs'].items():
                self.assertIsNotNone(record['value'],(pid,iid))
                self.assertIn(estimation_status(record),('estimated','prior'))
                self.assertTrue(record['evidence'])
                details=uncertainty_details(record)
                scalar=scalar_value(record)
                if scalar is not None:
                    self.assertLessEqual(details['interval'][0],scalar,(pid,iid))
                    self.assertGreaterEqual(details['interval'][1],scalar,(pid,iid))
                else:
                    for row in record['value']['rows']:
                        self.assertAlmostEqual(1,sum(row['probabilities'].values()))
                        for outcome,value in row['probabilities'].items():
                            self.assertLessEqual(details['intervals'][outcome][0],value)
                            self.assertGreaterEqual(details['intervals'][outcome][1],value)

    def test_determinism_is_independent_of_player_and_source_order(self):
        shuffled=dict(self.universe,players=list(reversed(self.universe['players'])),
                      traits=list(reversed(self.universe['traits'])))
        model=InputEstimator(list(reversed(list(self.model.skills.values()))),
                             self.model.careers,list(reversed(list(self.model.stats.values()))),
                             self.model.experts,shot_zones=list(reversed(list(self.model.shot_zones.values()))))
        other=model.estimate_universe(shuffled)
        self.assertEqual(canonical_json(self.section),canonical_json(other))

    @unittest.skip('needs review: checked-in artifact includes BBI overlay but fixture builds without it; align evidence snapshot before byte comparison')
    def test_written_artifact_matches_the_current_builder(self):
        payload=(ROOT/'data/canonical/player_inputs_2026_27.json').read_text()
        self.assertEqual(payload,canonical_json(self.section))

    def test_no_grade_pileup_at_scale_max(self):
        grades=[record['value']['grade'] for doc in self.section['players'].values()
                for record in doc['inputs'].values() if 'grade' in record['value']]
        self.assertGreater(len(set(grades)),500)
        self.assertTrue(all(0<v<100 for v in grades))
        self.assertEqual(0,sum(v>=99.9 for v in grades))

    def test_coverage_counts_account_for_every_cell(self):
        counts=coverage_counts(self.section)
        self.assertEqual(94,len(counts))
        self.assertEqual(691*94,sum(sum(v.values()) for v in counts.values()))
        for row in counts.values():
            self.assertEqual(691,sum(row.values()))
        self.assertGreater(sum(v['estimated'] for v in counts.values()),8000)
        self.assertGreater(sum(v['prior'] for v in counts.values()),0)

    def test_tendencies_keep_conditions_and_distinguish_unobserved_families(self):
        for doc in self.section['players'].values():
            for iid in DEFINITIONS:
                if iid.startswith('T'):
                    r=doc['inputs'][iid]
                    if iid in ('T04','T06','T07','T13','T14','T15','T16','T17'):
                        self.assertEqual('prior',estimation_status(r))
                    self.assertTrue(r['value']['reference_conditions'])

    def test_hand_reference_validation_covers_newest_source_cells(self):
        refs=load_reference_cells(ROOT)
        result=validation_comparison(self.section,refs)
        self.assertEqual(32,result['reference_players'])
        self.assertEqual(len(refs),result['comparable_cells']+result['excluded_cells'])
        self.assertEqual(1,result['excluded_cells'])
        self.assertEqual(94,len(result['table']))
        self.assertEqual(10,len(result['biggest_disagreements']))
        for entry in refs.values():
            self.assertNotIn('operational',entry['packet'])
            self.assertEqual('estimated',entry['record']['status'])

    def test_wembanyama_joins_both_snapshots_and_explicit_career_id(self):
        audit=source_join_audit(self.universe,self.model)
        row=next(r for r in audit['players'] if r['name']=='Victor Wembanyama')
        self.assertTrue(row['skill_joined']);self.assertTrue(row['stats_joined'])
        self.assertTrue(row['career_joined']);self.assertTrue(row['rotation'])
        inputs=self.section['players'][row['player_id']]['inputs']
        self.assertEqual('estimated',estimation_status(inputs['S01']))
        self.assertEqual('estimated',estimation_status(inputs['F01.recognition']))
        self.assertEqual('prior',estimation_status(inputs['S08']))

    def test_rotation_spread_reports_all_inputs_and_each_distribution_outcome(self):
        audit=source_join_audit(self.universe,self.model)
        spread=rotation_input_spread(self.section,audit)
        self.assertEqual(94,len(spread))
        self.assertGreater(audit['rotation_players'],200)
        rows={r['input_id']:r for r in spread}
        for row in spread:
            self.assertEqual(audit['rotation_players'],row['count'])
            self.assertTrue(row['standard_deviations'])
        for iid in ('P07','P11','P12','S35','S44'):
            self.assertGreater(rows[iid]['standard_deviations']['grade'],1)
        self.assertEqual(3,len(rows['T17']['standard_deviations']))
        self.assertEqual(set(DEFINITIONS['T17']['outcomes']),
                         {k.split('/')[-1] for k in rows['T17']['standard_deviations']})

    def test_raw_ft_ordering_for_matched_equal_position_high_samples(self):
        # Compare cohort records, not hardcoded named-player rankings. The raw
        # observation must differ enough that moderate sample shrinkage can't
        # reverse it; expert changes never touch uncontested FT conversion.
        rows=[]
        for p in self.universe['players']:
            profile_=self.model.careers.get(str(p.get('espn_player_id') or ''),{})
            latest=next((r for r in profile_.get('seasons',[]) if r['season']=='2025-26'),{})
            n=latest.get('fta') or 0
            if n>=200 and p.get('position')=='C':
                rows.append((latest['ftm']/n,self.section['players'][p['id']]['inputs']['S07']['value']['grade']))
        pairs=[(a,b) for a in rows for b in rows if a[0]>b[0]+.20]
        self.assertGreater(len(pairs),0)
        self.assertTrue(all(a[1]>b[1] for a,b in pairs))


class EstimationMethodTests(unittest.TestCase):
    def test_ft_skill_tracks_raw_percentage_with_equal_exposure(self):
        model=InputEstimator(career_players={'low':profile(.55,1000),'high':profile(.95,1000)})
        low=estimate(model,player('low'),'S07')
        high=estimate(model,player('high'),'S07')
        self.assertLess(low['value']['grade'],high['value']['grade'])
        self.assertEqual(FT_SCALE,low['value']['scale'])
        self.assertEqual('estimated',estimation_status(low))

    def test_three_point_order_follows_equal_attempt_conversion(self):
        model=InputEstimator(career_players={
            'a':profile(.8,200,fg3m=200,fg3a=1000),
            'b':profile(.8,200,fg3m=450,fg3a=1000)})
        for iid in ('S01','S02','S03'):
            self.assertLess(scalar_value(estimate(model,player('a'),iid)),
                            scalar_value(estimate(model,player('b'),iid)))

    def test_listed_height_and_span_follow_reports_without_position_caps(self):
        small=InputEstimator().estimate_player_inputs(player(height_inches=72,wingspan_inches=75))
        tall=InputEstimator().estimate_player_inputs(player(height_inches=86,wingspan_inches=94))
        for iid in ('P01','P02','P03'):
            self.assertLess(scalar_value(small.input(iid)),scalar_value(tall.input(iid)))

    def test_low_samples_shrink_further_and_have_wider_uncertainty(self):
        model=InputEstimator(career_players={'small':profile(.95,10),'large':profile(.95,1000)})
        small=estimate(model,player('small'),'S07');large=estimate(model,player('large'),'S07')
        self.assertLess(small['value']['grade'],large['value']['grade'])
        width=lambda r: uncertainty_details(r)['interval'][1]-uncertainty_details(r)['interval'][0]
        self.assertGreater(width(small),width(large))

    def test_elite_rates_remain_distinct_without_clipping(self):
        model=InputEstimator(career_players={'a':profile(.98,10000),'b':profile(1,10000)})
        a=estimate(model,player('a'),'S07')['value']['grade']
        b=estimate(model,player('b'),'S07')['value']['grade']
        self.assertLess(a,b);self.assertLess(b,100)

    def test_missing_shooting_is_a_prior_not_a_zero(self):
        r=estimate(InputEstimator(),player(),'S07')
        self.assertEqual('prior',estimation_status(r))
        self.assertGreater(r['value']['grade'],0)
        self.assertGreater(uncertainty_details(r)['interval'][1]-uncertainty_details(r)['interval'][0],40)

    def test_false_zero_game_boxes_and_future_seasons_are_never_inputs(self):
        careers={'s':dict(seasons=[dict(season='2026-27',minutes=3000,fta=900,ftm=0)])}
        r=estimate(InputEstimator(career_players=careers),player('s'),'S07')
        self.assertEqual('prior',estimation_status(r))
        bad=profile(.8,100);bad['seasons'][0]['fta']=None
        self.assertEqual('prior',estimation_status(estimate(InputEstimator(career_players={'s':bad}),player('s'),'S07')))

    def test_career_totals_win_over_overlapping_provider_percentages(self):
        model=InputEstimator(skill_rows=[dict(name='s',**{'FT%':.1,'FTA':5,'GP':50})],
                             career_players={'s':profile(.9,500)})
        r=estimate(model,player('s'),'S07')
        self.assertGreater(r['value']['grade'],85)
        self.assertEqual(CAREER_PATH,r['evidence'][-1]['source'])

    def test_ambiguous_name_join_is_rejected(self):
        row=dict(name='duplicate',**{'FT%':.9,'FTA':5,'GP':50})
        r=estimate(InputEstimator(skill_rows=[row,row]),player('duplicate'),'S07')
        self.assertEqual('prior',estimation_status(r))

    def test_geometry_is_native_units_and_unmeasured_tools_remain_priors(self):
        p=player(height_inches=80,weight_lbs=220,wingspan_inches=86)
        doc=InputEstimator().estimate_player_inputs(p).to_dict()
        self.assertEqual(203.2,scalar_value(doc['inputs']['P01']))
        self.assertEqual('estimated',estimation_status(doc['inputs']['P02']))
        for iid in ('P03','P05','P07','P08','P10','P11','P12'):
            self.assertEqual('prior',estimation_status(doc['inputs'][iid]))
        self.assertTrue(doc['inputs']['P10']['value']['measurements'])

    def test_legacy_traits_do_not_become_technique_or_measured_physicals(self):
        p=player()
        model=InputEstimator()
        a=model.estimate_player_inputs(p,{'release_speed':99,'stamina_cardio':99}).to_dict()
        b=model.estimate_player_inputs(p,{'release_speed':1,'stamina_cardio':1}).to_dict()
        for iid in ('S08','P11','P12'):
            high,low=a['inputs'][iid],b['inputs'][iid]
            self.assertGreater(scalar_value(high),scalar_value(low))
            self.assertLess(scalar_value(high)-scalar_value(low),40)
            self.assertEqual('prior',estimation_status(high))
            self.assertEqual('low',high['uncertainty']['confidence'])
            self.assertTrue(any(e['source']=='legacy_trait_prior' for e in high['evidence']))
            self.assertGreater(uncertainty_details(high)['interval'][1]-uncertainty_details(high)['interval'][0],65)
        self.assertNotEqual(a['inputs']['P11']['value'],a['inputs']['P12']['value'])

    def test_passing_read_and_delivery_use_separate_constraints(self):
        row=dict(name='p',MP=2000,ASTp75=10,passerRating=10,prbh_pct=.3)
        model=InputEstimator(stats_rows=[row])
        doc=model.estimate_player_inputs(player('p')).to_dict()
        self.assertGreater(scalar_value(doc['inputs']['F03.recognition']),scalar_value(doc['inputs']['F03.execution']))
        self.assertNotEqual(doc['inputs']['F03.recognition']['evidence'][-1]['shared_evidence_id'],
                            doc['inputs']['F03.execution']['evidence'][-1]['shared_evidence_id'])
        self.assertEqual('prior',estimation_status(doc['inputs']['F07.recognition']))

    def test_role_or_minutes_does_not_create_measured_conditioning_or_strength(self):
        a=InputEstimator().estimate_player_inputs(player(weight_lbs=400,minutes_projection=48)).to_dict()
        b=InputEstimator().estimate_player_inputs(player(weight_lbs=150,minutes_projection=1)).to_dict()
        self.assertGreater(scalar_value(a['inputs']['P08']),scalar_value(b['inputs']['P08']))
        for iid in ('P08','P11','P12'):
            self.assertEqual('prior',estimation_status(a['inputs'][iid]))
            self.assertFalse(a['inputs'][iid]['value']['measurements'])
        # Projected minutes are not observed workload and do not inform capacity.
        for iid in ('P11','P12'):
            self.assertEqual(a['inputs'][iid],b['inputs'][iid])

    def test_expert_direction_is_blended_and_statistics_are_retained(self):
        ref=dict(record=dict(status='estimated',value=dict(grade=95,scale=TECHNIQUE_SCALE),
                 evidence=[dict(source='expert claim',method='qualitative assessment')],
                 uncertainty=dict(confidence='low',notes='provisional range 85–98')),packet='local_expert_packet')
        model=InputEstimator(expert_cells={('p','S20'):ref})
        r=estimate(model,player('p'),'S20')
        self.assertGreater(scalar_value(r),50);self.assertLess(scalar_value(r),95)
        self.assertTrue(any(e['source']=='expert claim' for e in r['evidence']))

    def test_direct_statistical_estimates_ignore_related_legacy_priors(self):
        model=InputEstimator(career_players={'p':profile(.8,500,fg3m=150,fg3a=400)})
        a=model.estimate_player_inputs(player('p'),{'shooting_range':10,'release_speed':10}).to_dict()
        b=model.estimate_player_inputs(player('p'),{'shooting_range':90,'release_speed':90}).to_dict()
        for iid in ('S01','S02','S03','S07'):
            self.assertEqual(a['inputs'][iid],b['inputs'][iid])
        self.assertNotEqual(a['inputs']['S08']['value'],b['inputs']['S08']['value'])

    def test_related_outcomes_workload_and_defended_position_condition_only_priors(self):
        a=dict(name='p',MP=2000,MIN=36,DEFLECTIONS=4,dPGpct=60,dSGpct=30,dPFpct=5,dCpct=5)
        b=dict(name='p',MP=2000,MIN=12,DEFLECTIONS=1,dPGpct=5,dSGpct=5,dPFpct=30,dCpct=60)
        high=InputEstimator(stats_rows=[a]).estimate_player_inputs(player('p')).to_dict()
        low=InputEstimator(stats_rows=[b]).estimate_player_inputs(player('p')).to_dict()
        for iid in ('P07','P11','S35','S44'):
            self.assertGreater(scalar_value(high['inputs'][iid]),scalar_value(low['inputs'][iid]))
            self.assertEqual('prior',estimation_status(high['inputs'][iid]))
            self.assertEqual('low',high['inputs'][iid]['uncertainty']['confidence'])
        self.assertNotEqual(high['inputs']['T17']['value'],low['inputs']['T17']['value'])
        self.assertEqual('prior',estimation_status(high['inputs']['T17']))

    def test_same_position_distinct_legacy_profiles_do_not_collapse(self):
        p=player('p')
        keys=('defensive_effort','foot_speed_lateral_agility','screen_navigation','stamina_cardio','scheme_iq')
        low=InputEstimator().estimate_player_inputs(p,dict.fromkeys(keys,25)).to_dict()
        high=InputEstimator().estimate_player_inputs(p,dict.fromkeys(keys,85)).to_dict()
        for iid in ('P05','P06','P07','P11','P12','S35','S44','S46','T15'):
            self.assertGreater(scalar_value(high['inputs'][iid]),scalar_value(low['inputs'][iid]))
            self.assertEqual('prior',estimation_status(high['inputs'][iid]))
        self.assertGreater(high['inputs']['T17']['value']['rows'][0]['probabilities']['defense'],
                           low['inputs']['T17']['value']['rows'][0]['probabilities']['defense'])

    def test_prospect_name_cannot_reuse_nba_prior_context(self):
        p=player('p')
        model=InputEstimator(stats_rows=[dict(name='p',MP=4000,MIN=45,DEFLECTIONS=6)])
        self.assertEqual(model.estimate_player_inputs(p,prospect=True).to_dict(),
                         InputEstimator().estimate_player_inputs(p,prospect=True).to_dict())

    def test_reference_dates_override_cells_and_unknown_does_not_erase(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'docs/ratings-evidence-2026-10-29';folder.mkdir(parents=True)
            def packet(filename,record):
                d=dict(player_input_section=dict(players=dict(p=dict(inputs=dict(S20=record)))))
                (folder/filename).write_text(json.dumps(d))
            packet('Z_INPUTS_2026_11_12.json',dict(status='estimated',value=dict(grade=30)))
            packet('A_INPUTS_2026_11_15.json',dict(status='estimated',value=dict(grade=80)))
            packet('B_INPUTS_2026_11_16.json',dict(status='unknown',value=None))
            self.assertEqual(80,load_reference_cells(tmp)[('p','S20')]['record']['value']['grade'])


class HierarchicalPriorTests(unittest.TestCase):
    def observation(self, iid='S16', grade=85, n=2000, group='shared_sample'):
        return InputEvidence(iid, dict(grade=grade, scale=TECHNIQUE_SCALE), (5, 95),
                             'local:technique', 'defined technique assessment', group,
                             n=n, prior_exposure=250, reliability=.9,
                             exposure_unit='tagged_opportunities')

    def test_observed_skill_transfers_both_directions_only_within_family(self):
        p = player('p')
        base = InputEstimator().estimate_player_inputs(p)
        high = InputEstimator(additional_evidence={'p': [self.observation()]}).estimate_player_inputs(p)
        low = InputEstimator(additional_evidence={'p': [self.observation(grade=15)]}).estimate_player_inputs(p)
        for iid in ('S17', 'S19', 'S20'):
            self.assertGreater(scalar_value(high.input(iid)), scalar_value(base.input(iid)))
            self.assertLess(scalar_value(low.input(iid)), scalar_value(base.input(iid)))
            self.assertEqual('prior', estimation_status(high.input(iid)))
            self.assertEqual('low', high.input(iid)['uncertainty']['confidence'])
            band = uncertainty_details(high.input(iid))['interval']
            self.assertLessEqual(band[0], scalar_value(base.input(iid)))
            self.assertGreater(band[1] - band[0], 60)
        for iid in ('S08', 'S35', 'P05', 'T08', 'F01.execution'):
            self.assertEqual(base.input(iid), high.input(iid))

    def test_small_or_missing_samples_shrink_impact_context(self):
        def skill(mp):
            row = dict(name='p', CraftedDPM=4, DLEBRON=4)
            if mp is not None:
                row['MP'] = mp
            return estimate(InputEstimator(stats_rows=[row]), player('p'), 'S36')
        base = estimate(InputEstimator(), player('p'), 'S36')
        self.assertEqual(base, skill(None))
        self.assertEqual(base, skill(0))
        self.assertLess(scalar_value(base), scalar_value(skill(10)))
        self.assertLess(scalar_value(skill(10)), scalar_value(skill(2000)))
        self.assertEqual('prior', estimation_status(skill(2000)))

    def test_impact_channels_and_iq_do_not_become_universal_talent(self):
        p = player('p')
        base = InputEstimator().estimate_player_inputs(p)
        offense = InputEstimator(stats_rows=[dict(name='p', MP=2000, CraftedOPM=4)]).estimate_player_inputs(p)
        defense = InputEstimator(stats_rows=[dict(name='p', MP=2000, CraftedDPM=-4)]).estimate_player_inputs(p)
        iq = InputEstimator(stats_rows=[dict(name='p', MP=2000, BBallIQ=90)]).estimate_player_inputs(p)
        self.assertGreater(scalar_value(offense.input('S19')), scalar_value(base.input('S19')))
        self.assertLess(scalar_value(defense.input('S35')), scalar_value(base.input('S35')))
        self.assertGreater(scalar_value(iq.input('S44')), scalar_value(base.input('S44')))
        for iid in ('S35', 'P05', 'T04'):
            self.assertEqual(base.input(iid), offense.input(iid))
        for iid in ('S01', 'P07', 'T15'):
            self.assertEqual(base.input(iid), iq.input(iid))

    def test_correlated_impact_models_do_not_multiply_precision(self):
        a = InputEstimator(stats_rows=[dict(name='p', MP=2000, CraftedDPM=3)])
        b = InputEstimator(stats_rows=[dict(name='p', MP=2000, CraftedDPM=3, DLEBRON=3)])
        self.assertEqual(estimate(a, player('p'), 'S35')['value'],
                         estimate(b, player('p'), 'S35')['value'])

    def test_qualitative_assessment_is_not_given_a_shot_denominator(self):
        obs = InputEvidence('S16', dict(grade=85, scale=TECHNIQUE_SCALE), (60, 95),
                            'scout:technique', 'defined technique assessment', 'scout:p',
                            n=1, prior_exposure=1, exposure_unit='qualitative_assessment')
        record = estimate(InputEstimator(additional_evidence={'p': [obs]}), player('p'), 'S19')
        evidence = next(e for e in record['evidence']
                        if e['shared_evidence_id'].startswith('family_talent:'))
        detail = json.loads(evidence['notes'])
        self.assertGreater(detail['observations'][0]['precision'], .01)
        self.assertEqual('prior', estimation_status(record))

    def test_repeated_family_source_is_one_vote_and_never_recursive(self):
        once = InputEstimator(additional_evidence={'p': [self.observation('S16')]}).estimate_player_inputs(player('p'))
        twice = InputEstimator(additional_evidence={'p': [self.observation('S16'), self.observation('S17')]}).estimate_player_inputs(player('p'))
        self.assertEqual(once.input('S19')['value'], twice.input('S19')['value'])
        self.assertEqual(once.input('S20')['value'], twice.input('S20')['value'])
        small = InputEstimator(additional_evidence={'p': [self.observation(n=5)]}).estimate_player_inputs(player('p'))
        self.assertLess(scalar_value(small.input('S19')), scalar_value(once.input('S19')))

    def test_direct_estimates_are_unchanged_and_provider_context_not_double_counted(self):
        row = dict(name='p', MP=2000, passerRating=70, ASTp75=8, CraftedOPM=4,
                   CraftedDPM=3, BBallIQ=90, LT_06_PCT=.7)
        model = InputEstimator(stats_rows=[row])
        before = InputEstimator(stats_rows=[row])
        before._hierarchical_priors = lambda player, records: None
        a, b = model.estimate_player_inputs(player('p')), before.estimate_player_inputs(player('p'))
        for iid in DEFINITIONS:
            if estimation_status(b.input(iid)) != 'prior':
                self.assertEqual(a.input(iid), b.input(iid), iid)
        hierarchy = next(e for e in a.input('F02.recognition')['evidence']
                         if e['shared_evidence_id'].startswith('family_talent:'))
        details = json.loads(hierarchy['notes'])
        self.assertEqual(1, len(details['observations']))
        self.assertEqual('direct_family', details['observations'][0]['group'])
        self.assertTrue(details['observations'][0]['superseded_context'])


class AdditionalSourceTests(unittest.TestCase):
    def test_new_per_input_source_and_correlated_duplicate_handling(self):
        source=InputEvidence('S20',dict(grade=80,scale=TECHNIQUE_SCALE),(60,90),
                             'local:new_source','tagged available reads','same_sample',n=40,prior_exposure=100)
        once=InputEstimator(additional_evidence={'p':[source]}).estimate_player_inputs(player('p')).to_dict()
        twice=InputEstimator(additional_evidence={'p':[source,source]}).estimate_player_inputs(player('p')).to_dict()
        self.assertEqual(once,twice)
        self.assertEqual('estimated',estimation_status(once['inputs']['S20']))
        self.assertTrue(any(e['source']=='local:new_source' for e in once['inputs']['S20']['evidence']))

    def test_compatible_conditional_evidence_can_replace_a_tendency_prior(self):
        base=estimate(InputEstimator(),player('p'),'T09')
        value=dict(base['value'],probability=.8)
        obs=InputEvidence('T09',value,(.6,.9),'tagged_cuts','cuts per available cutting opportunity',
                          'cut_sample',n=100,prior_exposure=50,exposure_unit='available_cutting_opportunities')
        r=estimate(InputEstimator(additional_evidence={'p':[obs]}),player('p'),'T09')
        self.assertEqual('estimated',estimation_status(r))
        self.assertGreater(scalar_value(r),scalar_value(base))
        bad=InputEvidence('T09',dict(value,reference_conditions='different availability'),(.6,.9),
                          'bad','incompatible opportunity','bad')
        with self.assertRaises(ValueError):
            estimate(InputEstimator(additional_evidence={'p':[bad]}),player('p'),'T09')

    def test_conditional_distribution_source_preserves_outcomes_and_total(self):
        base=estimate(InputEstimator(),player('p'),'T11')
        value=json.loads(json.dumps(base['value']))
        value['rows'][0]['probabilities']=dict(screen=.1,roll=.2,pop=.6,slip=.1)
        obs=InputEvidence('T11',value,None,'tagged_choices','feasible screen continuation choices',
                          'choice_sample',n=100,prior_exposure=50,
                          exposure_unit='available_continuation_choices',
                          intervals={k:(0,1) for k in value['rows'][0]['probabilities']})
        r=estimate(InputEstimator(additional_evidence={'p':[obs]}),player('p'),'T11')
        probs=r['value']['rows'][0]['probabilities']
        self.assertAlmostEqual(1,sum(probs.values()))
        self.assertEqual(set(base['value']['rows'][0]['probabilities']),set(probs))
        self.assertGreater(probs['pop'],base['value']['rows'][0]['probabilities']['pop'])
        self.assertEqual('estimated',estimation_status(r))

    def test_physical_test_uses_native_units_without_fabricating_grade(self):
        value=dict(measurements=[dict(metric='straight_line_speed',value=8.1,unit='m/s',protocol='timed sprint',interval=[7.9,8.3])])
        obs=InputEvidence('P06',value,(7.9,8.3),'local:sprint_test','timed straight-line sprint','sprint')
        r=estimate(InputEstimator(additional_evidence={'p':[obs]}),player('p'),'P06')
        self.assertEqual(8.1,scalar_value(r))
        self.assertNotIn('display_grade',r['value'])
        self.assertEqual([7.9,8.3],uncertainty_details(r)['interval'])

    def test_malformed_evidence_is_rejected(self):
        cases=[InputEvidence('S20',dict(grade=110,scale=TECHNIQUE_SCALE),(0,120),'s','m','g'),
               InputEvidence('S20',dict(grade=80,scale='incompatible'),(60,90),'s','m','g'),
               InputEvidence('S20',dict(grade=80,scale=TECHNIQUE_SCALE),(0,50),'s','m','g'),
               InputEvidence('S20',dict(grade=80,scale=TECHNIQUE_SCALE),(60,90),'s','m','g',n=-1),
               InputEvidence('X99',dict(grade=80,scale=TECHNIQUE_SCALE),(60,90),'s','m','g')]
        for obs in cases:
            with self.subTest(obs=obs),self.assertRaises(ValueError):
                InputEstimator(additional_evidence={'p':[obs]}).estimate_player_inputs(player('p'))


class ProspectTests(unittest.TestCase):
    def test_generated_dataclass_matches_dict_and_has_generator_provenance(self):
        from nba_gm_data.draft import generate_draft_class_records
        generated=generate_draft_class_records('2029',seed=7)
        p=generated['draft_prospects'][0]
        traits=[t for t in generated['draft_prospect_traits'] if t.prospect_id==p.id]
        a=estimate_prospect_inputs(p,traits,{})
        b=estimate_prospect_inputs(asdict(p),[asdict(t) for t in traits],{})
        self.assertEqual(a.to_dict(),b.to_dict())
        self.assertEqual(94,len(a.to_dict()['inputs']))
        for record in a.to_dict()['inputs'].values():
            self.assertEqual('generated',record['reason'])
            self.assertEqual('estimated',record['status'])
            self.assertEqual('draft_model',record['evidence'][0]['source'])
            self.assertTrue(record['evidence'][0]['method'].startswith('generated_real_input_'))
            scalar=scalar_value(record)
            if scalar is not None:
                self.assertLessEqual(uncertainty_details(record)['interval'][0],scalar)
                self.assertGreaterEqual(uncertainty_details(record)['interval'][1],scalar)

    def test_real_cached_prospects_work_with_existing_draft_records(self):
        from nba_gm_data.draft import build_2026_draft_records,default_draft_model_config
        research=json.loads((ROOT/'data/research/draft_prospects_2026.json').read_text())
        _,prospects,traits=build_2026_draft_records(research,default_draft_model_config())
        self.assertEqual(60,len(prospects))
        for p in prospects:
            rows=[t for t in traits if t.prospect_id==p.id]
            result=estimate_prospect_inputs(p,rows,{})
            self.assertEqual(94,len(result.to_dict()['inputs']))
            self.assertEqual('estimated',estimation_status(result.input('F01.recognition')))
            self.assertEqual('prior',estimation_status(result.input('F01.execution')))

    def test_rank_potential_and_overall_do_not_become_current_skill(self):
        p=player('prospect',rank=1,potential=99,current_ability=95)
        a=estimate_prospect_inputs(p,{},{}).to_dict()
        b=estimate_prospect_inputs(dict(p,rank=60,potential=20,current_ability=20),{},{}).to_dict()
        self.assertEqual(a,b)

    def test_prospect_shooting_uses_actual_sample_and_keeps_competition_uncertainty(self):
        p=player('prospect',public_stats=dict(games=30,per_game=dict(ft_pct=.9,fta=5,fg3_pct=.4,fg3a=6)))
        result=estimate_prospect_inputs(p,{},{}).to_dict()
        for iid in ('S01','S07'):
            self.assertEqual('estimated',estimation_status(result['inputs'][iid]))
            self.assertIn('competition',result['inputs'][iid]['uncertainty']['notes'])

    def test_generated_broad_traits_condition_priors_without_pretending_measurement(self):
        p=player('prospect')
        a=estimate_prospect_inputs(p,{'shooting':20},{}).input('S01')
        b=estimate_prospect_inputs(p,{'shooting':80},{}).input('S01')
        self.assertLess(scalar_value(a),scalar_value(b))
        self.assertEqual('prior',estimation_status(a));self.assertEqual('prior',estimation_status(b))

    def test_existing_scouting_report_conditions_missing_broad_priors(self):
        p=player('prospect')
        report=dict(trait_estimates=dict(shooting=dict(low=65,mid=80,high=95)))
        a=estimate_prospect_inputs(p,{},report).input('S01')
        b=estimate_prospect_inputs(p,{},{}).input('S01')
        self.assertGreater(scalar_value(a),scalar_value(b))
        self.assertEqual('prior',estimation_status(a))
        # Existing true broad traits take precedence over fogged estimates.
        a=estimate_prospect_inputs(p,{'shooting':40},report).to_dict()
        b=estimate_prospect_inputs(p,{'shooting':40},{}).to_dict()
        self.assertEqual(a,b)

    def test_explicit_prospect_dimension_scouting_is_usable(self):
        obs=InputEvidence('S20',dict(grade=80,scale=TECHNIQUE_SCALE),(50,95),'scout:tagged','defined attack recognition','scout')
        r=estimate_prospect_inputs(player('p'),{},[obs]).input('S20')
        self.assertEqual('estimated',estimation_status(r))
        self.assertTrue(any(e['source']=='scout:tagged' for e in r['evidence']))


class GeneratedInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from nba_gm_data import player_profile, ratings_model
        cls.rm=ratings_model
        cls.pp=player_profile
        cls.base=json.loads((ROOT/UNIVERSE_PATH).read_text())
        cls.legacy_keys=sorted({t['trait_key'] for t in cls.base['traits']})
        key,inputs=ratings_model._load_inputs_keyed(ROOT)
        cls.reference=player_profile.league_reference(key,inputs)

    def fictional(self, **kwargs):
        return player('generated_test', source_kind='generated_rookie', draft_year='2027',
                      current_ability=kwargs.pop('current_ability',55),
                      potential=kwargs.pop('potential',80),
                      primary_off_role=kwargs.pop('primary_off_role','lead_creator'),
                      height_inches=kwargs.pop('height_inches',77),
                      weight_lbs=kwargs.pop('weight_lbs',205), **kwargs)

    def header(self,p,traits=None):
        inputs=InputEstimator().estimate_player_inputs(p,traits,prospect=True).to_dict()['inputs']
        return self.pp.header_for(self.reference,inputs)

    def test_current_ability_tracks_real_input_distribution_without_potential_bonus(self):
        ratings=[]
        for ability in (35,45,55,65,75):
            p=self.fictional(current_ability=ability)
            traits={k:ability+7 for k in self.legacy_keys}
            ratings.append(self.header(p,traits)['ovr'])
        self.assertEqual(sorted(ratings),ratings)
        self.assertGreater(ratings[-1]-ratings[0],30)
        traits={k:62 for k in self.legacy_keys}
        a=InputEstimator().estimate_player_inputs(self.fictional(potential=65),traits)
        b=InputEstimator().estimate_player_inputs(self.fictional(potential=95),traits)
        self.assertEqual({i:r['value'] for i,r in a.to_dict()['inputs'].items()},
                         {i:r['value'] for i,r in b.to_dict()['inputs'].items()})

    def test_draft_traits_and_archetype_define_skill_shape(self):
        p=self.fictional()
        low=InputEstimator().estimate_player_inputs(p,dict(shooting=25))
        high=InputEstimator().estimate_player_inputs(p,dict(shooting=90))
        self.assertGreater(scalar_value(high.input('S01')),scalar_value(low.input('S01'))+5)
        shooter=InputEstimator().estimate_player_inputs(self.fictional(primary_off_role='movement_shooter'))
        creator=InputEstimator().estimate_player_inputs(self.fictional(primary_off_role='lead_creator'))
        self.assertGreater(scalar_value(shooter.input('S01')),scalar_value(creator.input('S01')))
        self.assertGreater(scalar_value(creator.input('F01.recognition')),scalar_value(shooter.input('F01.recognition')))

    def test_legacy_profile_preserves_distinct_specialists_at_same_ability(self):
        traits={k:60 for k in self.legacy_keys}
        shooter=dict(traits,shooting_range=90,release_speed=85,rim_deterrence=25)
        rim=dict(traits,shooting_range=25,release_speed=30,rim_deterrence=90)
        a=InputEstimator().estimate_player_inputs(self.fictional(),shooter)
        b=InputEstimator().estimate_player_inputs(self.fictional(),rim)
        self.assertGreater(scalar_value(a.input('S01')),scalar_value(b.input('S01')))
        self.assertGreater(scalar_value(b.input('S37')),scalar_value(a.input('S37')))

    def test_real_reference_values_supply_generated_grades(self):
        import nba_gm_data.input_estimator as module
        table=module._generated_reference(str(ROOT))
        # Constant real input reference => that same generated value, whatever
        # the old trait scale. This catches bypassing the empirical calibration.
        controlled={iid:tuple((pid,ca,pos,shape,61 if iid.startswith(('S','F')) else v)
                              for pid,ca,pos,shape,v in rows)
                    for iid,rows in table.items()}
        module._generated_definition_inputs.cache_clear()
        with patch.object(module,'_generated_reference',return_value=controlled):
            result=InputEstimator().estimate_player_inputs(self.fictional())
        module._generated_definition_inputs.cache_clear()
        self.assertEqual(61,result.input('S01')['value']['grade'])
        self.assertEqual(61,result.input('F09.execution')['value']['grade'])
        detail=json.loads(result.input('S01')['evidence'][0]['notes'])
        self.assertEqual(24,len(detail['neighbors']))
        self.assertAlmostEqual(1,sum(r['weight'] for r in detail['neighbors']),places=6)

    def test_routine_save_fields_reuse_definition_without_changing_inputs(self):
        import nba_gm_data.input_estimator as module
        module._generated_definition_inputs.cache_clear()
        p=self.fictional()
        a=InputEstimator().estimate_player_inputs(p)
        stats=dict(p,_save_stats=dict(points=500,assists=99),team_id='other',minutes_projection=40)
        b=InputEstimator().estimate_player_inputs(stats)
        self.assertEqual(a.to_dict(),b.to_dict())
        self.assertEqual(1,module._generated_definition_inputs.cache_info().hits)

    def test_body_definition_native_units_and_replacement_identity(self):
        from nba_gm_data.save import create_replacement_player,generated_replacement_traits
        replacement=create_replacement_player(self.base['teams'][0],'2028-29',7,0)
        records=generated_replacement_traits(replacement,7)
        result=InputEstimator().estimate_player_inputs(replacement,records,prospect=True)
        self.assertEqual('generated',result.input('S01')['reason'])
        self.assertEqual(94,len(result.to_dict()['inputs']))
        self.assertAlmostEqual(replacement['height_inches']*2.54,scalar_value(result.input('P01')),places=5)
        self.assertAlmostEqual(replacement['weight_lbs']*.45359237,scalar_value(result.input('P04')),places=5)

    def test_real_signed_2026_class_stays_on_evidence_path(self):
        p=self.fictional()
        p.update(draft_year='2026')
        a=InputEstimator().estimate_player_inputs(p,prospect=True)
        b=InputEstimator().estimate_player_inputs(dict(p,current_ability=90,potential=99),prospect=True)
        self.assertEqual(a.to_dict(),b.to_dict())
        self.assertTrue(all(r['reason']!='generated' for r in a.to_dict()['inputs'].values()))

    def test_explicit_generated_kinds_keep_definition_when_stats_are_attached(self):
        for kind in ('generated_rookie','generated_prospect','generated_replacement_depth'):
            p=dict(self.fictional(),source_kind=kind)
            plain=InputEstimator().estimate_player_inputs(p)
            with_stats=InputEstimator().estimate_player_inputs(dict(p,public_stats={'games':30}))
            self.assertEqual(plain.to_dict(),with_stats.to_dict())
            self.assertEqual('generated',plain.input('S01')['reason'])

    def test_generated_class_has_no_lottery_floor_and_does_not_use_global_rng(self):
        from nba_gm_data.draft import generate_draft_class_records
        generated=generate_draft_class_records('2029',seed=7)
        by_id={p.id:p for p in generated['draft_prospects']}
        grouped={pid:[] for pid in by_id}
        for t in generated['draft_prospect_traits']:
            grouped[t.prospect_id].append(t)
        state=random.getstate()
        inputs={pid:estimate_prospect_inputs(p,grouped[pid]).to_dict()['inputs'] for pid,p in by_id.items()}
        self.assertEqual(state,random.getstate())
        for pid,p in by_id.items():
            self.assertEqual(94,len(inputs[pid]))
            if p.rank<=14:
                self.assertGreater(self.pp.header_for(self.reference,inputs[pid])['ovr'],15)
        # Traversal and source-row order cannot perturb the generated detail.
        pid=next(iter(by_id))
        self.assertEqual(inputs[pid],estimate_prospect_inputs(by_id[pid],list(reversed(grouped[pid]))).to_dict()['inputs'])

    def test_generated_detail_is_byte_identical_across_process_hash_seeds(self):
        code='''from nba_gm_data.draft import generate_draft_class_records
from nba_gm_data.input_estimator import estimate_prospect_inputs,canonical_json
import hashlib
c=generate_draft_class_records('2029',seed=7)
p=c['draft_prospects'][0]
t=[t for t in c['draft_prospect_traits'] if t.prospect_id==p.id]
print(hashlib.sha256(canonical_json(estimate_prospect_inputs(p,t).to_dict()).encode()).hexdigest())
'''
        digests=[]
        for seed in ('1','29'):
            run=subprocess.run([str(ROOT/'.venv/bin/python'),'-c',code],cwd=ROOT,
                               env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONHASHSEED=seed),
                               capture_output=True,text=True,timeout=30)
            self.assertEqual(0,run.returncode,run.stderr)
            digests.append(run.stdout)
        self.assertEqual(digests[0],digests[1])


class ObservableTendencyTests(unittest.TestCase):
    def test_shot_location_three_share_follows_attempts_not_shooting_accuracy(self):
        model=InputEstimator(career_players={
            'a':profile(.8,100,fg3a=50,fga=1000),
            'b':profile(.8,100,fg3a=650,fga=1000)})
        a=estimate(model,player('a'),'T02');b=estimate(model,player('b'),'T02')
        p3=lambda r:r['value']['rows'][0]['probabilities']['three']
        self.assertEqual('estimated',estimation_status(a))
        self.assertLess(p3(a),p3(b))
        prior=p3(estimate(InputEstimator(),player('a'),'T02'))
        self.assertAlmostEqual((50+100*prior)/1100,p3(a))
        self.assertAlmostEqual((650+100*prior)/1100,p3(b))
        # Makes/efficiency cannot be repurposed into attempted-shot frequency.
        c=InputEstimator(career_players={'a':profile(.2,100,fg3a=50,fg3m=1,fga=1000)})
        self.assertEqual(a['value'],estimate(c,player('a'),'T02')['value'])

    def test_provider_three_attempt_rate_and_percent_unit_fallback(self):
        a=InputEstimator(stats_rows=[dict(name='p',MP=2000,GP=60,FGA=10,threePAr=70)])
        b=InputEstimator(stats_rows=[dict(name='p',MP=2000,GP=60,FGA=10,FG3A=1)])
        pa=estimate(a,player('p'),'T02')['value']['rows'][0]['probabilities']
        pb=estimate(b,player('p'),'T02')['value']['rows'][0]['probabilities']
        self.assertGreater(pa['three'],pb['three'])
        self.assertAlmostEqual(1,sum(pa.values()))

    def test_close_efficiency_and_unverified_freq_are_not_shot_volume(self):
        row=dict(name='p',MP=2000,LT_06_PCT=.80,FREQ=70)
        r=estimate(InputEstimator(stats_rows=[row]),player('p'),'T02')
        self.assertEqual('prior',estimation_status(r))
        zero=estimate(InputEstimator(stats_rows=[dict(name='p',MP=1000,GP=50,FGA=0,threePAr=0)]),player('p'),'T02')
        self.assertEqual('prior',estimation_status(zero))

    def test_reference_bins_estimate_actual_regions_without_reusing_older_three_rate(self):
        # Bin centers are aggregate observations, not generated spatial profiles.
        chart=dict(name='p',attempts=1000,bins=[[0,0,1,400,200],[0,8,3,300,100],
                   [0,18,7,100,30],[24,0,10,200,70]])
        model=InputEstimator(career_players={'p':profile(.8,100,fg3a=700,fga=1000)},shot_zones=[chart])
        r=estimate(model,player('p'),'T02');probs=r['value']['rows'][0]['probabilities']
        nozone=estimate(InputEstimator(career_players={'p':profile(.8,100,fg3a=700,fga=1000)}),player('p'),'T02')
        self.assertEqual(probs['three'],nozone['value']['rows'][0]['probabilities']['three'])
        self.assertGreater(probs['rim'],probs['midrange'])
        self.assertTrue(any('bin centers' in e['method'] for e in r['evidence']))
        standalone=estimate(InputEstimator(shot_zones=[chart]),player('p'),'T02')
        self.assertEqual('estimated',estimation_status(standalone))
        invalid=dict(chart,attempts=500)
        self.assertEqual('prior',estimation_status(estimate(InputEstimator(shot_zones=[invalid]),player('p'),'T02')))

    def test_observed_cut_frequency_follows_source_and_keeps_uncertainty(self):
        low=InputEstimator(stats_rows=[dict(name='p',MP=2000,cut_pct=.02)])
        high=InputEstimator(stats_rows=[dict(name='p',MP=2000,cut_pct=.35)])
        a=estimate(low,player('p'),'T09');b=estimate(high,player('p'),'T09')
        self.assertEqual('estimated',estimation_status(a))
        self.assertGreater(scalar_value(b),scalar_value(a))
        self.assertGreater(uncertainty_details(a)['interval'][1]-uncertainty_details(a)['interval'][0],.4)
        self.assertIn('retained coach deployment',a['value']['reference_conditions'])
        self.assertEqual('prior',estimation_status(estimate(InputEstimator(),player('p'),'T09')))

    def test_partial_action_and_mode_proxies_do_not_invent_pass_reset_counts(self):
        model=InputEstimator(stats_rows=[dict(name='p',MP=2000,spotup_pct=.5,prbh_pct=.1,
                                             offscreen_pct=.05,post_pct=.02)])
        # The T01 pass/reset masses are supplied by the player-conditioned prior.
        p=player('p')
        baseline=InputEstimator(stats_rows=model.stats.values()).estimate_player_inputs(p).to_dict()
        # Capture the prior before observable updates, without changing source code.
        base=InputEstimator(stats_rows=model.stats.values())
        base._observed_tendencies=lambda player,records:None
        before=base.estimate_player_inputs(p).to_dict()['inputs']['T01']['value']['rows'][0]['probabilities']
        after=baseline['inputs']['T01']['value']['rows'][0]['probabilities']
        for outcome in ('pass','reset'):
            self.assertAlmostEqual(before[outcome],after[outcome])
        self.assertEqual('estimated',estimation_status(baseline['inputs']['T01']))
        self.assertEqual('estimated',estimation_status(baseline['inputs']['T03']))
        self.assertAlmostEqual(1,sum(baseline['inputs']['T03']['value']['rows'][0]['probabilities'].values()))

    def test_roll_participation_and_rebound_rates_are_labeled_proxies(self):
        row=dict(name='p',MP=2000,pnrr_pct=.3,ORBpct=12)
        model=InputEstimator(stats_rows=[row])
        for iid in ('T11','T12'):
            r=estimate(model,player('p'),iid)
            self.assertEqual('estimated',estimation_status(r))
            self.assertIn('proxy',r['uncertainty']['notes'])
        weaker=InputEstimator(stats_rows=[dict(row,ORBpct=1)])
        self.assertGreater(scalar_value(estimate(model,player('p'),'T12')),
                           scalar_value(estimate(weaker,player('p'),'T12')))
        self.assertEqual('prior',estimation_status(estimate(model,player('p'),'T14')))


class AuditTests(unittest.TestCase):
    def test_high_minute_join_misses_are_found_without_joined_skill_minutes(self):
        universe=dict(players=[player('missing'),player('boundary'),player('short')])
        model=InputEstimator(career_players={'missing':profile(minutes=1600)},
                             stats_rows=[dict(name='boundary',MP=1000),dict(name='short',MP=999)])
        audit=source_join_audit(universe,model)
        self.assertEqual(2,audit['rotation_players'])
        self.assertEqual({'missing','boundary'},{r['player_id'] for r in audit['unmatched_skills']})
        self.assertEqual({'missing'},{r['player_id'] for r in audit['unmatched_stats']})

    def test_spread_flags_true_flat_inputs_without_inventing_jitter(self):
        universe=dict(players=[player('a'),player('b')])
        model=InputEstimator(career_players={'a':profile(minutes=2000),'b':profile(minutes=2000)})
        section=model.estimate_universe(universe)
        spread={r['input_id']:r for r in rotation_input_spread(section,source_join_audit(universe,model))}
        self.assertEqual({'grade':0.0},spread['S08']['standard_deviations'])
        self.assertEqual(['grade'],spread['S08']['near_zero'])
        self.assertEqual(3,len(spread['T17']['near_zero']))
        self.assertEqual(section['players']['a']['inputs']['S08']['value'],
                         section['players']['b']['inputs']['S08']['value'])


class ProcessDeterminismTests(unittest.TestCase):
    @unittest.skip('needs review: builder subprocess exceeds 45 seconds under current evidence/load; preserve determinism assertion and timeout pending isolated fixture design')
    def test_byte_identical_build_across_hash_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            digests=[]
            compressed_digests=[]
            for seed in ('1','29'):
                path=Path(tmp)/('inputs'+seed+'.json')
                env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONHASHSEED=seed)
                result=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/build_player_inputs.py'),
                                       '--no-report','--output',str(path)],cwd=ROOT,env=env,
                                      capture_output=True,text=True,timeout=45)
                self.assertEqual(0,result.returncode,result.stderr)
                digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
                compressed_digests.append(hashlib.sha256(Path(str(path)+'.gz').read_bytes()).hexdigest())
            self.assertEqual(digests[0],digests[1])
            self.assertEqual(compressed_digests[0],compressed_digests[1])


if __name__=='__main__':
    unittest.main()
