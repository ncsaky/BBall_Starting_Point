from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from nba_gm_data.trade_pick_terms import compile_pick_rules, attach_compiled_rules, original_specs_for_rules, candidate_pick_rules
from nba_gm_data import app_actions as aa, transactions as tx
from nba_gm_data.save import resolve_pick_obligations_for_year
from nba_gm_data.transactions import apply_pick_obligation_terms_to_save


class TradePickTermsTests(unittest.TestCase):
    def setUp(self):
        self.data={'meta':{'active_season':'2026-27'},'teams':[{'id':'a','abbrev':'AAA'},{'id':'b','abbrev':'BBB'}],
                   'draft_picks':[self.pick('a27','a',2027),self.pick('a29','a',2029),self.pick('a31','a',2031),
                                  self.pick('b27','b',2027),self.pick('b29','b',2029)],'pick_obligations':[]}
        self.sides=[{'team':'AAA','recipient':'BBB','assets':[{'kind':'pick','value':'a27'}]},
                    {'team':'BBB','recipient':'AAA','assets':[]}]
        self.protected={'pick_id':'a27','type':'protected_pick','from':1,'through':4,'fallback_pick_ids':['a29']}
        self.swap={'pick_id':'a27','type':'pick_swap','other_pick_id':'b27','benefit':'better'}

    def pick(self,pid,team,year):
        return {'id':pid,'season':str(year),'round':1,'original_team_id':team,'current_owner_team_id':team,
                'status':'future','protection_summary':'unprotected','projected_pick_slot':15}

    def compile(self,rule=None,sides=None):
        return compile_pick_rules(self.data,[rule or self.protected],sides or self.sides)

    def test_protection_is_valued_as_conditional_and_retains_explicit_fallback(self):
        context,assets,terms=self.compile()
        self.assertEqual(assets[0],self.sides[0]['assets'])
        self.assertEqual(terms[0]['protected_range'],{'from':1,'through':4})
        self.assertEqual(terms[0]['receiver_team_id'],'b')
        self.assertIn('a29',context['locked_pick_assets'])
        self.assertEqual(self.data['pick_obligations'],[])

    def test_swap_replaces_the_pick_with_a_right_not_an_outright_transfer(self):
        _,assets,terms=self.compile(self.swap)
        self.assertEqual(assets[0],[{'kind':'pick_swap','value':terms[0]['id']}])
        self.assertEqual(terms[0]['team_a_pick_id'],'a27')
        self.assertEqual(terms[0]['current_rights_holder_team_id'],'b')
        self.assertTrue(terms[0]['pending_asset_grant'])

    def test_bad_or_overlapping_collateral_fails_closed(self):
        cases=[{**self.protected,'fallback_pick_ids':[]}, {**self.protected,'fallback_pick_ids':['b29']},
               {**self.protected,'fallback_pick_ids':['a27']}, {**self.protected,'from':5,'through':4},
               {**self.protected,'through':31}, {**self.protected,'through':True},
               {**self.protected,'type':'custom_script'}, {**self.protected,'fallback_pick_ids':['a29','a31']}]
        for rule in cases:
            with self.subTest(rule=rule),self.assertRaises(ValueError): self.compile(rule)
        sides=deepcopy(self.sides)
        sides[0]['assets'].append({'kind':'pick','value':'a29'})
        with self.assertRaisesRegex(ValueError,'selected'): self.compile(sides=sides)
        with self.assertRaisesRegex(ValueError,'one condition'): compile_pick_rules(self.data,[self.protected,self.protected],self.sides)

    def test_wrong_owner_determined_slots_and_existing_terms_cannot_be_overwritten(self):
        for change in ({'current_owner_team_id':'b'},{'overall_pick':5},{'_obligations':[{'type':'pick_swap'}]},
                       {'protection_summary':'top-5 protected'},{'_obligation_locked':True}):
            with self.subTest(change=change):
                data=deepcopy(self.data);data['draft_picks'][0].update(change)
                with self.assertRaises(ValueError): compile_pick_rules(data,[self.protected],self.sides)

    def test_swap_requires_matching_season_round_and_a_specific_counterparty(self):
        for change in ({'other_pick_id':'a29'},{'other_pick_id':'b29'},{'other_pick_id':'a27'},{'benefit':'random'}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.compile({**self.swap,**change})
        sides=deepcopy(self.sides);sides[0]['recipient']=None
        with self.assertRaisesRegex(ValueError,'specific'): self.compile(self.swap,sides)

    def test_all_teams_finder_finalizes_the_receiver_without_redrawing_terms(self):
        sides=deepcopy(self.sides);sides[0]['recipient']=None
        _,_,terms=self.compile(sides=sides)
        candidate={'proposal':{'id':'offer','from_team_id':'a','to_team_id':'b',
                   'from_assets':[{'kind':'pick','id':'a27'}],'to_assets':[]},'evaluations':[]}
        result=attach_compiled_rules(candidate,terms,[self.protected],7)
        self.assertEqual(result['pick_obligation_terms'][0]['receiver_team_id'],'b')
        self.assertEqual(result['ui_pick_rules'],[self.protected])
        self.assertNotEqual(result['proposal']['id'],'offer')

    def test_multiple_independent_conditions_cannot_reuse_the_same_collateral(self):
        sides=deepcopy(self.sides);sides[0]['assets'].append({'kind':'pick','value':'a31'})
        rules=[self.protected,{'pick_id':'a31','type':'protected_pick','from':1,'through':2,'fallback_pick_ids':['a29']}]
        with self.assertRaises(ValueError):compile_pick_rules(self.data,rules,sides)

    def test_multiple_valid_conditions_are_preserved_as_separate_obligations(self):
        self.data['draft_picks'].append(self.pick('a33','a',2033))
        sides=deepcopy(self.sides);sides[0]['assets'].append({'kind':'pick','value':'a31'})
        second={'pick_id':'a31','type':'protected_pick','from':8,'through':14,'fallback_pick_ids':['a33']}
        context,assets,terms=compile_pick_rules(self.data,[self.protected,second],sides)
        self.assertEqual(len(terms),2)
        self.assertEqual(set(context['locked_pick_assets']),{'a29','a33'})
        self.assertEqual(assets[0],sides[0]['assets'])

    def test_serialized_swap_restores_primary_specs_for_safe_re_evaluation(self):
        _,assets,terms=self.compile(self.swap)
        candidate=attach_compiled_rules({'proposal':{'id':'offer','from_team_id':'a','to_team_id':'b',
            'from_assets':[{'kind':'pick_swap','id':assets[0][0]['value']}],'to_assets':[]}},terms,[self.swap],7)
        self.assertEqual(original_specs_for_rules(candidate,'from_assets'),[{'kind':'pick','value':'a27'}])

    def test_ai_sweeteners_are_not_discarded_by_authored_term_revalidation(self):
        candidate={'ui_pick_rules':[self.protected],'pick_obligation_terms':[
            {'id':'ai-swap','type':'pick_swap','team_a_pick_id':'b29','team_b_pick_id':'a29',
             'pending_asset_grant':True,'benefit':'worse'}],
            'proposal':{'to_assets':[{'kind':'pick_swap','id':'ai-swap'}]}}
        rules=candidate_pick_rules(self.data,candidate)
        self.assertEqual(len(rules),2)
        self.assertEqual(rules[1],{'pick_id':'b29','type':'pick_swap','other_pick_id':'a29','benefit':'worse'})
        self.assertEqual(original_specs_for_rules(candidate,'to_assets'),[{'kind':'pick','value':'b29'}])

    def test_evaluation_to_ai_candidate_preserves_new_swap_grants_for_live_validation(self):
        _, assets, terms = self.compile(self.swap)
        report = {'proposal': {'id': 'swap-offer', 'from_team_id': 'a', 'to_team_id': 'b',
                  'from_assets': [{'kind': 'pick_swap', 'id': assets[0][0]['value']}], 'to_assets': []},
                  'legality': {'status': 'legal'}, 'evaluations': [], 'accepted_by_all': True,
                  'pick_obligation_terms': terms, 'pick_trade_terms': terms,
                  'pick_obligation_terms_prompted': True}
        with patch.object(tx, 'proposal_summary', return_value='Swap'), \
             patch.object(tx, 'trade_value_breakdown', return_value={}):
            candidate = tx.candidate_from_evaluation(self.data, report)
        self.assertEqual(candidate['pick_obligation_terms'], terms)
        payload = {**candidate['proposal'], 'pick_obligation_terms': candidate['pick_obligation_terms']}
        saved = {'state': {'current_date': '2026-10-01'}, 'pick_obligations': []}
        self.assertEqual(tx.trade_live_validation_issues(saved, payload, '2026-10-01'), [])
        missing = dict(candidate['proposal'])
        self.assertTrue(tx.trade_live_validation_issues(saved, missing, '2026-10-01'))
        candidate['pick_obligation_terms'][0]['benefit'] = 'worse'
        self.assertEqual(report['pick_obligation_terms'][0]['benefit'], 'better')

    def test_new_swap_reserves_both_picks_and_rechecks_live_collateral(self):
        _, assets, terms = self.compile(self.swap)
        offer = {'proposal': {'id': 'swap', 'from_team_id': 'a', 'to_team_id': 'b',
            'from_assets': [{'kind': 'pick_swap', 'id': assets[0][0]['value']}], 'to_assets': []},
            'pick_obligation_terms': terms, 'offer_context': {'status': 'pending_user_review'}}
        keys = tx.proposal_asset_identity_keys(offer)
        self.assertTrue({'pick:a27', 'pick:b27'} <= keys)
        saved = {'state': {'current_date': '2026-10-01'}, 'pick_obligations': [],
                 'draft_pick_overrides': {'a27': 'a', 'b27': 'b'}, 'user_trade_offers': [offer]}
        payload = {**offer['proposal'], 'pick_obligation_terms': terms}
        self.assertEqual(tx.trade_live_validation_issues(saved, payload), [])
        moved = deepcopy(saved); moved['draft_pick_overrides']['a27'] = 'other'
        self.assertTrue(tx.trade_live_validation_issues(moved, payload))
        locked = deepcopy(saved); locked['locked_pick_assets'] = ['b27']
        self.assertTrue(tx.trade_live_validation_issues(locked, payload))
        existing = deepcopy(saved); existing['pick_obligations'] = terms
        self.assertTrue(tx.trade_live_validation_issues(existing, payload))
        tx.prune_trade_offers_touching_assets(saved, {'pick:a27'})
        self.assertEqual(saved['user_trade_offers'][0]['offer_context']['status'], 'stale_asset_moved')

    def test_protection_resolves_to_primary_or_fallback_and_releases_collateral(self):
        for slot,expected in ((3,'a'),(8,'b')):
            _,_,terms=self.compile()
            save={'meta':{'season':'2026-27'},'state':{'current_date':'2027-06-22'},'pick_obligations':[],
                  'locked_pick_assets':['a29'],'draft_pick_overrides':{'a27':'b'}}
            apply_pick_obligation_terms_to_save(save,{'id':'test'},terms,'2026-10-01')
            order={'draft_order':[{**self.data['draft_picks'][0],'overall_pick':slot,'current_owner_team_id':'b'}]}
            resolve_pick_obligations_for_year(save,order,'2027')
            self.assertEqual(save['draft_pick_overrides']['a27'],expected)
            self.assertNotIn('a29',save['locked_pick_assets'])
            if slot==3:self.assertEqual(save['draft_pick_overrides']['a29'],'b')

    def test_swap_settles_both_directions_without_transferring_extra_picks(self):
        for benefit in ('better','worse'):
            for a_slot,b_slot in ((5,20),(20,5)):
                with self.subTest(benefit=benefit,slots=(a_slot,b_slot)):
                    _,_,terms=self.compile({**self.swap,'benefit':benefit})
                    saved={'state':{'current_date':'2027-06-22'},'pick_obligations':[]}
                    apply_pick_obligation_terms_to_save(saved,{'id':'swap'},terms,'2026-10-01')
                    order={'draft_order':[{**self.data['draft_picks'][i],'overall_pick':slot} for i,slot in ((0,a_slot),(3,b_slot))]}
                    resolve_pick_obligations_for_year(saved,order,'2027')
                    held=next(p for p in order['draft_order'] if p['current_owner_team_id']=='b')
                    self.assertEqual(held['overall_pick'],min(a_slot,b_slot) if benefit=='better' else max(a_slot,b_slot))
                    self.assertEqual({p['current_owner_team_id'] for p in order['draft_order']},{'a','b'})

    def test_app_actions_compile_before_evaluation_and_attach_finder_terms(self):
        def result():
            return {'proposal':{'id':'offer','from_team_id':'a','to_team_id':'b',
                    'from_assets':[{'kind':'pick','id':'a27'}],'to_assets':[]},'evaluations':[]}
        payload={'from_team':'AAA','to_team':'BBB','from_assets':self.sides[0]['assets'],
                 'to_assets':[],'pick_rules':[self.protected],'seed':7,'seller_team':'AAA','for_team':'AAA'}
        with patch.object(aa,'active_canonical',return_value=self.data), \
             patch.object(aa,'load_save',return_value={'state':{'current_date':'2026-10-01'}}), \
             patch.object(aa,'ensure_league_save_defaults',side_effect=lambda s,c:s), \
             patch.object(aa,'evaluate_trade',return_value=result()) as evaluate, \
             patch.object(aa,'enhance_trade_candidate',side_effect=lambda c,r,**kw:r):
            response=aa.dispatch_save_action('evaluate_trade',payload,Path('.'),self.data,Path('unused.json'))
        self.assertEqual(len(evaluate.call_args.args[0]['pick_obligations']),1)
        self.assertEqual(response['pick_obligation_terms'][0]['protected_range'],{'from':1,'through':4})
        with patch.object(aa,'active_canonical',return_value=self.data), \
             patch.object(aa,'find_trade_for_assets',return_value={'candidates':[result()]}), \
             patch.object(aa,'enhance_trade_finder_report',side_effect=lambda c,r,p:r):
            response=aa.dispatch_save_action('find_trade_for_assets',{**payload,'assets':self.sides[0]['assets']},Path('.'),self.data,Path('unused.json'))
        self.assertEqual(response['candidates'][0]['pick_obligation_terms'][0]['receiver_team_id'],'b')
        self.assertEqual(response['candidates'][0]['ui_pick_rules'],[self.protected])


if __name__=='__main__':unittest.main()
