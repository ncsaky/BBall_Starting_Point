"""Shared defensive ability semantics, physical controls and scale boundaries."""
from copy import deepcopy
import unittest

from nba_gm_data import defense, save, sim, spatial


def fixture(height=77, rim=80, position='PG', minutes=30, **values):
    p={'id':'controlled','name':'Controlled','team_id':'t','height_inches':height,
       'position':position,'minutes_projection':minutes,'age':27}
    traits={k:70.0 for k in ('defensive_effort','scheme_iq','screen_navigation',
        'foot_speed_lateral_agility','rim_deterrence','shooting_range','shot_versatility',
        'handle_pressure','rim_pressure','passing_reads','portability','playoff_translation',
        'offensive_rebounding','stamina_cardio','release_speed')}
    traits.update(rim_deterrence=rim,**values)
    c={'players':[p],'teams':[{'id':'t'}], 'traits':[
        {'player_id':p['id'],'trait_key':k,'value':v} for k,v in traits.items()]}
    return c,p,traits


class DefensiveAlignmentTests(unittest.TestCase):
    def test_rim_strict_monotonicity_no_top_clip_and_distinct_elite_peers(self):
        xs=[defense.rim_response(i/10) for i in range(10,1101)]
        self.assertTrue(all(x >= 1 for x in xs))
        self.assertTrue(all(b>a for a,b in zip(xs,xs[1:])))
        self.assertEqual(defense.rim_response(-5),1)
        # Rescale, don't clip: values past the old 100 ceiling keep rising (inputs-model traits can exceed 100).
        self.assertGreater(defense.rim_response(100),99)
        self.assertGreater(defense.rim_response(105),defense.rim_response(100)+5)
        self.assertGreater(defense.rim_response(110),defense.rim_response(105))
        # The old shoulder put 96.8, 97.4 and 99.0 within 0.8 points; elite peers are now clearly apart.
        self.assertGreater(defense.rim_response(99.01)-defense.rim_response(96.82),5)

    def test_low_mid_response_and_scarcity_meaning_preserved(self):
        start=defense.response_knots()[0][0]
        self.assertGreater(start,60)
        for i in range(10,int(start*10)+1):
            x=i/10
            self.assertEqual(defense.rim_response(x),sim.nonlinear_high(x,68))
            self.assertEqual(defense.rim_response(x),defense.legacy_rim_response(x))

    def test_evidence_tail_joins_without_jump(self):
        eps=.00001
        start=defense.response_knots()[0][0]
        self.assertAlmostEqual(defense.rim_response(start-eps),defense.rim_response(start+eps),places=3)

    def test_old_shoulder_flattened_the_top(self):
        # The pre-2026-11-18 response squeezed every value above ~90 into 95-99 and ended at slope .25.
        self.assertEqual(defense.legacy_rim_response(105),99)
        self.assertLess(defense.legacy_rim_response(99.01)-defense.legacy_rim_response(96.82),1)

    def test_card_rescales_values_above_99_instead_of_clipping(self):
        shown=[]
        for rim in (98.0,101.0,104.0,106.5):
            c,p,_=fixture(rim=rim,height=84,position='C')
            attrs=save.player_attribute_summary(c,p['id'])
            self.assertEqual(attrs['rim_deterrence'],rim)          # the summary keeps the engine value
            shown.append(save.player_display_attribute_summary(c,p['id'])['rim_deterrence'])
        self.assertEqual(shown[0],98.0)                            # at or below 99: shown unchanged
        self.assertTrue(all(b>a for a,b in zip(shown,shown[1:])),shown)
        self.assertTrue(all(v<100 for v in shown),shown)
        self.assertEqual(save.presentation_rating_value(99),99.0)

    def test_block_rate_rises_with_rim_and_with_choosing_to_jump(self):
        self.assertLess(defense.block_rate_per36(60),defense.block_rate_per36(90))
        self.assertLess(defense.block_rate_per36(90),defense.block_rate_per36(115))
        # Same rim protection, different contest choice: the jumper blocks more shots than the stay-down defender.
        self.assertLess(defense.block_rate_per36(80,.22),defense.block_rate_per36(80,.38))
        self.assertGreater(defense.block_rate_per36(1),0)

    def test_poisson_count_is_a_deterministic_one_draw_count(self):
        self.assertEqual(defense.poisson_count(.5,0),0)
        self.assertEqual(defense.poisson_count(.01,2.0),0)
        draws=[defense.poisson_count(i/2000+.00025,2.5) for i in range(2000)]
        self.assertAlmostEqual(sum(draws)/len(draws),2.5,delta=.05)
        self.assertTrue(all(b>=a for a,b in zip(draws,draws[1:])))

    def test_activity_normalized_and_skill_uses_existing_matchup_mix(self):
        c,p,t=fixture()
        d=defense.defensive_components(t.get)
        self.assertEqual(d.activity,70)
        self.assertEqual(d.skill,d.activity*.6+d.rim*.4)
        f=sim.player_feature_vector(c,p).features
        self.assertEqual(f['defensive_events'],round(d.activity,3))
        self.assertEqual(f['rim_deterrence'],round(d.rim,3))
        self.assertEqual(f['defensive_weak_link'],50)  # targeting, never a skill input

    def test_height_is_not_added_twice_to_effective_rim_ability(self):
        a,pa,_=fixture(height=77);b,pb,_=fixture(height=84)
        fa=sim.player_feature_vector(a,pa).features;fb=sim.player_feature_vector(b,pb).features
        for k in ('rim_deterrence','defensive_events','defensive_weak_link'):
            self.assertEqual(fa[k],fb[k])
        sa=spatial.player_spatial_profile(a,pa);sb=spatial.player_spatial_profile(b,pb)
        self.assertEqual(sa['defense'],sb['defense'])
        self.assertNotEqual(sa['offense'],sb['offense'])  # offense geometry remains

    def test_equal_height_better_rim_improves_only_interior_zone_abilities(self):
        a,pa,_=fixture(rim=50);b,pb,_=fixture(rim=97)
        sa=spatial.player_spatial_profile(a,pa)['defense'];sb=spatial.player_spatial_profile(b,pb)['defense']
        for zone in spatial.ZONE_KEYS:
            if spatial.ZONE_BY_KEY[zone]['group']=='rim':
                self.assertGreater(sb[zone]['contest'],sa[zone]['contest'])
                self.assertGreater(sb[zone]['suppression'],sa[zone]['suppression'])
            else:self.assertEqual(sa[zone],sb[zone])

    def test_position_label_and_player_minutes_do_not_manufacture_defensive_skill(self):
        a,pa,_=fixture();sa=spatial.player_spatial_profile(a,pa)['defense']
        da=save.player_attribute_summary(a,pa['id'])['defense']
        for changes in ({'position':'C'},{'minutes':5}):
            b,pb,_=fixture(**changes)
            self.assertEqual(save.player_attribute_summary(b,pb['id'])['defense'],da)
            self.assertEqual(spatial.player_spatial_profile(b,pb)['defense'],sa)

    def test_scheme_helps_spatial_coverage_without_new_independent_activity_count(self):
        a,pa,_=fixture(scheme_iq=30);b,pb,_=fixture(scheme_iq=90)
        fa=sim.player_feature_vector(a,pa).features;fb=sim.player_feature_vector(b,pb).features
        self.assertEqual(fa['defensive_events'],fb['defensive_events'])
        self.assertGreater(spatial.player_spatial_profile(b,pb)['defense']['short_mid_left']['suppression'],
                           spatial.player_spatial_profile(a,pa)['defense']['short_mid_left']['suppression'])

    def test_card_def_is_shared_skill_with_no_general_display_compression(self):
        c,p,t=fixture();attrs=save.player_attribute_summary(c,p['id']);display=save.player_display_attribute_summary(c,p['id'])
        self.assertEqual(attrs['defense'],round(defense.defensive_components(t.get).skill,1))
        self.assertEqual(display['defense'],attrs['defense'])
        self.assertEqual(display['shooting'],save.presentation_rating_value(attrs['shooting']))

    def test_fresh_trait_views_and_spatial_signature_invalidate_without_mutation(self):
        c,p,_=fixture();before=deepcopy(c)
        a=sim.player_feature_vector(c,p).features;sa=spatial.player_spatial_profile(c,p)
        save.player_display_attribute_summary(c,p['id'])
        self.assertEqual(c,before)
        new=deepcopy(c)
        next(t for t in new['traits'] if t['trait_key']=='rim_deterrence')['value']=99
        b=sim.player_feature_vector(new,new['players'][0]).features
        sb=spatial.player_spatial_profile(new,new['players'][0])
        self.assertNotEqual(sa['input_signature'],sb['input_signature'])
        self.assertGreater(b['rim_deterrence'],a['rim_deterrence'])

    def test_team_minutes_reweight_abilities_without_changing_player_skill(self):
        c,p,_=fixture(rim=99);other={**p,'id':'weak','name':'Weak'};c['players'].append(other)
        c['traits'] += [{**t,'player_id':'weak','value':30} for t in list(c['traits'])]
        a=spatial.team_spatial_profile(c,'t',{'controlled':35,'weak':5})
        b=spatial.team_spatial_profile(c,'t',{'controlled':5,'weak':35})
        self.assertGreater(a['defense']['restricted_area']['suppression'],b['defense']['restricted_area']['suppression'])

    def test_better_rim_reduces_opponent_expected_spatial_shot_quality(self):
        a,pa,_=fixture(rim=30);b,pb,_=fixture(rim=99)
        offense=spatial.player_spatial_profile(a,pa)
        weak=spatial.spatial_matchup_adjustment(offense,spatial.player_spatial_profile(a,pa))
        strong=spatial.spatial_matchup_adjustment(offense,spatial.player_spatial_profile(b,pb))
        self.assertLess(strong['shot_quality_delta'],weak['shot_quality_delta'])

    def test_offensive_reputation_does_not_raise_card_def_and_health_still_matters(self):
        c,p,_=fixture();before=save.player_attribute_summary(c,p['id'])['defense']
        other=deepcopy(c)
        for t in other['traits']:
            if t['trait_key'] in ('shooting_range','shot_versatility','handle_pressure','passing_reads'):
                t['value']=99
        self.assertEqual(save.player_attribute_summary(other,p['id'])['defense'],before)
        features=sim.player_feature_vector(c,p).features
        adjusted=sim.health_adjusted_player_features(features,{'health_fatigue':80,'health_rust':30})
        self.assertLess(adjusted['defensive_events'],features['defensive_events'])
        self.assertLess(adjusted['rim_deterrence'],features['rim_deterrence'])
        self.assertEqual(features,sim.player_feature_vector(c,p).features)

    def test_physical_tools_and_position_still_constrain_deployment(self):
        a,pa,_=fixture(height=77);b,pb,_=fixture(height=84)
        attrs=save.player_attribute_summary(a,pa['id'])
        self.assertLess(save.starting_slot_score(pa,'5',30,attrs),save.starting_slot_score(pb,'5',30,attrs))
        self.assertTrue(save.starting_slot_hard_violation('5',77,['PG']))
        self.assertFalse(save.starting_slot_hard_violation('5',84,['PG']))
        a['meta']={'talent_model_version':2}
        other=deepcopy(a);other['players'][0]['position']='C'
        self.assertEqual(save.player_attribute_summary(a,pa['id'])['defense'],
                         save.player_attribute_summary(other,pa['id'])['defense'])
        self.assertNotEqual(save.player_attribute_summary(a,pa['id'])['overall'],
                            save.player_attribute_summary(other,pa['id'])['overall'])

if __name__=='__main__':unittest.main()
