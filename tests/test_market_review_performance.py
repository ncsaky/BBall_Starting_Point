"""Review reuse must observe complete state and isolate speculative results."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from nba_gm_data import transactions as tx
from nba_gm_data.trade_review import MarketReview
import test_trade_search_performance as fixtures


class MarketReviewTests(unittest.TestCase):
    def test_review_shares_only_unchanged_inputs_and_releases_context(self):
        source = fixtures.TradeSearchPerformanceTests().fixture()
        source.update(draft_picks=[{'id':'pick', 'owner_team_id':'a'}],
                      team_plans={}, team_trade_wants={}, player_health_states=[])
        review=MarketReview()
        with patch.object(tx, 'with_transaction_context', side_effect=lambda c, config:c), \
             patch.object(tx, 'with_spatial_fit_context', side_effect=lambda c:c):
            current=review.prepare(source)
            current['_trade_search_roles']['probe']={'p0':1}
            self.assertIs(current,review.prepare(source))
            mutations=[lambda:source['players'][0].update(team_id='b'),
                       lambda:source['player_health_states'].append({'player_id':'p1','availability_status':'out'}),
                       lambda:source['contracts'].append({'player_id':'p1','seasons':[{'salary':999}]}),
                       lambda:source['draft_picks'][0].update(owner_team_id='b'),
                       lambda:source['team_plans'].update(a={'core_ids':['p2']}),
                       lambda:source['team_trade_wants'].update(a=[{'kind':'upgrade'}]),
                       lambda:source.update(_human_team_ids=['a']),
                       lambda:source['players'][1].update(current_ability=99)]
            for mutate in mutations:
                mutate()
                next_context=review.prepare(source)
                self.assertIsNot(current,next_context)
                self.assertEqual(next_context['_trade_search_roles'],{})
                current=next_context
            # A reloaded equal source can share within this review; a new review
            # always starts fresh, even at the same date and with identical state.
            self.assertIs(review.prepare(deepcopy(source)),current)
            self.assertIsNot(MarketReview().prepare(deepcopy(source)),current)
        review.close()
        self.assertIsNone(review.active)
        self.assertNotIn('_trade_search_roles',source)

    def test_exact_pick_previews_isolate_annotations_and_nested_previews(self):
        source=fixtures.TradeSearchPerformanceTests().fixture()
        source.update(draft_picks=[{'id':'p','owner_team_id':'a'},
                                  {'id':'unchanged','_obligations':[{'id':'existing'}]}], pick_obligations=[])
        source['_trade_search_pick_previews']={}
        terms=[{'id':'protected','type':'protected_pick','primary_pick_id':'p','receiver_team_id':'b'}]
        def annotate(c):
            c['draft_picks'][0]['_obligations']=deepcopy(c['pick_obligations'])
            c['_nested_entitlements']={'p':{'rights':['a']}}
        with patch.object(tx,'validate_pick_obligation_term',return_value=True), \
             patch.object(tx,'annotate_pick_obligation_context',side_effect=annotate) as calls:
            first=tx.canonical_with_pending_pick_terms(source,terms)
            expected=deepcopy(first)
            first['draft_picks'][0]['_obligations'][0]['receiver_team_id']='corrupt'
            first['_nested_entitlements']['p']['rights'].append('corrupt')
            second=tx.canonical_with_pending_pick_terms(source,terms)
            self.assertEqual(second,expected)
            self.assertEqual(calls.call_count,1)
            second['draft_picks'][1]['_obligations'][0]['id']='corrupt'
            self.assertEqual(source['draft_picks'][1]['_obligations'][0]['id'],'existing')
            self.assertNotIn('_trade_search_pick_previews',second)
            tx.canonical_with_pending_pick_terms(second,terms)
            self.assertEqual(calls.call_count,2)
            changed=deepcopy(terms);changed[0]['type']='pick_swap'
            tx.canonical_with_pending_pick_terms(source,changed)
            self.assertEqual(calls.call_count,3)
            for i in range(80):
                variant=deepcopy(terms);variant[0]['id']=str(i)
                tx.canonical_with_pending_pick_terms(source,variant)
            self.assertLessEqual(len(source['_trade_search_pick_previews']),64)
        self.assertNotIn('_obligations',source['draft_picks'][0])

    def test_roster_results_do_not_leak_mutation_across_player_identical_pick_packages(self):
        from nba_gm_data import trade_roster as tr
        from types import SimpleNamespace
        source=tx.trade_search_context(fixtures.TradeSearchPerformanceTests().fixture())
        with patch.object(tx,'strategic_rotation_view',side_effect=lambda c,t:c), \
             patch('nba_gm_data.sim.team_feature_vector',return_value=SimpleNamespace(features={'impact':70})) as vector:
            first=tr.roster_projection(source,'a',['p0'],['p1'])
            expected=deepcopy(first)
            first['retained_ids'].clear()
            preview={**source,'pick_obligations':[{'type':'pick_swap'}]}
            self.assertEqual(tr.roster_projection(preview,'a',['p0'],['p1']),expected)
            self.assertEqual(vector.call_count,1)

    def test_real_protected_and_swap_compilation_matches_without_cache(self):
        import test_trade_pick_terms as picks
        from nba_gm_data.trade_pick_terms import compile_pick_rules
        fixture=picks.TradePickTermsTests();fixture.setUp()
        for rule in (fixture.protected,fixture.swap,{**fixture.protected,'through':10}):
            source=deepcopy(fixture.data)
            expected=compile_pick_rules(deepcopy(source),[rule],fixture.sides)
            source['_trade_search_pick_previews']={}
            first=compile_pick_rules(source,[rule],fixture.sides)
            second=compile_pick_rules(source,[rule],fixture.sides)
            self.assertEqual(first,expected)
            self.assertEqual(second,expected)
            first[0]['draft_picks'][0]['protection_summary']='corrupt'
            self.assertEqual(compile_pick_rules(source,[rule],fixture.sides),expected)

    def test_player_identical_pick_variations_and_facilitators_keep_fresh_decisions(self):
        from test_multi_team_trades import fixture
        from nba_gm_data.multi_team_trades import facilitator_candidates
        source=fixture()
        fresh=tx.with_transaction_context(deepcopy(source))
        review=MarketReview()
        active=review.prepare(source)
        values=[]
        for pick in ('b2028r1','b2030r1'):
            args=('A','B',[{'kind':'player','value':'a0'}],
                  [{'kind':'player','value':'b0'},{'kind':'pick','value':pick}])
            expected=tx.evaluate_trade_decision(fresh,*args,context_ready=True)
            actual=tx.evaluate_trade_decision(active,*args,context_ready=True)
            self.assertEqual(actual,expected)
            values.append(actual['evaluations'][0]['incoming_value'])
        self.assertNotEqual(*values)
        args=('A','B',[{'kind':'player','value':'a0'}],
              [{'kind':'player','value':'b0'},{'kind':'player','value':'b1'}])
        blocked=tx.evaluate_trade_decision(fresh,*args,context_ready=True)
        expected=facilitator_candidates(fresh,blocked,seed=1,date='2027-01-31')
        self.assertTrue(expected)
        self.assertEqual(facilitator_candidates(active,blocked,seed=1,date='2027-01-31'),expected)
        self.assertEqual(facilitator_candidates(active,blocked,seed=1,date='2027-01-31'),expected)
        review.close()
