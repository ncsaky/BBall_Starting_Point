"""One grade scale across ratings and requests; presentation stays out of AI ability."""
from copy import deepcopy
import gzip,json
from pathlib import Path
import unittest
from unittest.mock import patch

from nba_gm_data import save as sv,sim,trade_wants as wants,transactions as tx
from nba_gm_data.fantasy_draft import fantasy_growth_outlook
from test_defensive_alignment import fixture
import test_trade_wants
from tests.local_fixtures import needs_local


class RatingScaleConsistencyTests(unittest.TestCase):
    def test_common_low_mid_high_anchors_and_idempotence(self):
        for x in (1,20,40,50,60,70,80,90,95,98,99):
            self.assertEqual(sv.presentation_rating_value(x),x)
        values=[sv.presentation_rating_value(i/10) for i in range(10,991)]
        self.assertTrue(all(b>a for a,b in zip(values,values[1:])))
        self.assertTrue(all(sv.presentation_rating_value(x)==x for x in values))

    def test_every_rating_has_same_units_without_mutating_ability_or_features(self):
        c,p,_=fixture();before=deepcopy(c);engine=sv.player_attribute_summary(c,p['id'])
        f=sim.player_feature_vector(c,p).features
        self.assertEqual(sv.player_display_attribute_summary(c,p['id']),engine)
        self.assertEqual(c,before)
        with patch.object(sv,'presentation_rating_value',return_value=7):
            self.assertEqual(sv.player_attribute_summary(c,p['id']),engine)
            self.assertEqual(sim.player_feature_vector(c,p).features,f)

    def test_finder_style_user_conditions_compare_actual_grade_units(self):
        c,p,_=fixture();c['contracts']=[];c['player_asset_valuations']=[{'player_id':p['id'],'player_value':70}]
        facts=wants.player_facts(c,p)
        self.assertEqual(facts['range'],70)
        self.assertEqual(wants.condition_distance(facts['range'],'>=',70,'range'),0)
        self.assertGreater(wants.condition_distance(facts['range'],'>=',71,'range'),0)
        self.assertEqual(facts['defense'],sv.player_attribute_summary(c,p['id'])['defense'])

    def test_generated_wants_translate_only_old_display_boundaries(self):
        c=test_trade_wants.TradeWantsTests().fixture();c['team_strategic_states'][1].update(window_phase='entering',needs=['shooting'])
        rows=wants.suggested_wants(c,'b')
        youth=next(r for r in rows if r['id']=='ai_youth')
        self.assertIn({'field':'overall','op':'>=','value':56},youth['conditions'])
        skill=next(r for r in rows if r['id']=='ai_skill_range')
        self.assertIn({'field':'range','op':'>=','value':58},skill['conditions'])
        self.assertIn({'field':'overall','op':'>=','value':55},skill['conditions'])
        c['team_strategic_states'][1]['needs']=['point_of_attack_defense']
        skill=next(r for r in wants.suggested_wants(c,'b') if r['id']=='ai_skill_defense')
        self.assertIn({'field':'defense','op':'>=','value':78},skill['conditions'])

    def test_price_calculation_does_not_read_presentation_values(self):
        from test_multi_team_trades import fixture as market_fixture
        c=market_fixture('ab');expected=tx.build_player_asset_valuations(deepcopy(c))
        with patch.object(sv,'presentation_rating_value',side_effect=AssertionError('Display leaked into valuation')):
            self.assertEqual(tx.build_player_asset_valuations(deepcopy(c)),expected)

    def test_growth_preview_converts_once_without_changing_engine_growth(self):
        p={'engine_overall':70,'display_overall':70,'impact':75,'age':23,
           'minutes_projection':28,'development_upside':12}
        direct=fantasy_growth_outlook(p)
        with patch.object(sv,'presentation_rating_value',side_effect=lambda v:v+10):
            shifted=fantasy_growth_outlook({**p,'display_overall':80})
        for key in ('engine_likely_growth','engine_high_end_growth','engine_ceiling_overall'):
            self.assertEqual(direct[key],shifted[key])
        self.assertEqual(direct['ceiling_overall'],direct['engine_ceiling_overall'])

    @needs_local('output/defensive-scale-comparison-2026-11-10/canonical-before.json.gz')
    def test_reviewed_top_rim_anchor_preserves_other_inputs_and_development(self):
        root=Path(__file__).resolve().parents[1]
        with gzip.open(root/'output/defensive-scale-comparison-2026-11-10/canonical-before.json.gz','rt') as f:
            before=json.load(f)
        current=json.loads((root/'data/canonical/universe_2026_27_offseason.json').read_text())
        a={(t['player_id'],t['trait_key']):t for t in before['traits']}
        b={(t['player_id'],t['trait_key']):t for t in current['traits']}
        key=('player_sas-victor-wembanyama','rim_deterrence')
        self.assertEqual({k:(a[k]['value'],b[k]['value']) for k in a if a[k]['value']!=b[k]['value']},
                         {key:(99.0,100.0)})
        self.assertEqual(a[key]['confidence'],b[key]['confidence'])
        for k in a.keys()-{key}:self.assertEqual(a[k],b[k])
        from test_five_player_calibration import filled_measurements
        self.assertEqual(filled_measurements(before['players'],current['players']),current['players'])
        # The stored 2027 draft class (draft_prospects, its traits and scouting reports) was deliberately replaced on
        # 2026-11-19 by real college/high-school/international prospects (docs/agents/tasks/real-prospects.md), so it is
        # no longer part of this rim-anchor comparison; everything else must still be untouched.
        self.assertEqual(before['development_events'],current['development_events'])
        # CONTRACT-TERMS (2026-11-22) rebuilt each real contract's signing season and length from evidence; salaries,
        # seasons and every other contract field must still be untouched.
        from test_five_player_calibration import rebuilt_contract_history
        self.assertEqual(rebuilt_contract_history(before['contracts'],current['contracts']),current['contracts'])
        f=sim.player_feature_vector(current,next(p for p in current['players'] if p['id']==key[0])).features
        gobert=sim.player_feature_vector(current,next(p for p in current['players'] if p['name']=='Rudy Gobert')).features
        # Since the 2026-11-19 ratings audit the rim response is evidence-shaped and no longer clipped at 99, so the
        # best rim protector sits above 99 (rule 3: rescale, never clip).
        self.assertGreater(f['rim_deterrence'],99)
        self.assertGreater(f['rim_deterrence'],gobert['rim_deterrence'])

    def test_extension_projection_starts_at_the_same_grade_as_the_card(self):
        from nba_gm_data.extension_analysis import ability_projection
        c,p,_=fixture()
        projection=ability_projection(c,p,2026,2026)
        self.assertEqual(len(projection),1)
        expected=sv.player_display_attribute_summary(c,p['id'])['overall']
        self.assertEqual(projection[0]['overall'],expected)
        self.assertEqual(projection[0]['low'],expected)
        self.assertEqual(projection[0]['high'],expected)

if __name__=='__main__':unittest.main()
