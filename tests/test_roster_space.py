from copy import deepcopy
import unittest
from unittest.mock import patch

from nba_gm_data import roster_space as rs, play, transactions as tx


class RosterSpaceTests(unittest.TestCase):
    def test_intents_require_a_real_upgrade_and_an_identified_cut(self):
        saved = {'free_agency_state': {'day':2}}
        for plan in ({'ok':False,'reason':'signing_not_expected_to_survive_cutdown','cuts':[]},
                     {'ok':True,'cuts':[],'upgrade':20}):
            rs.remember_target(saved,'a','fa',10,2,plan)
        self.assertNotIn('roster_space_targets',saved['free_agency_state'])
        rs.remember_target(saved,'a','fa',10,2,{'ok':False,'reason':'waiver_cost_exceeds_marginal_upgrade',
                                             'cuts':[{'player_id':'depth'}],'upgrade':6})
        self.assertEqual(saved['free_agency_state']['roster_space_targets']['a']['player_id'],'fa')

    def test_sale_credit_is_bounded_seller_only_and_cannot_discount_core(self):
        data = {'_roster_space_sale': {'team_id':'a','sell_player_id':'depth','upgrade':20}}
        incoming,outgoing = [{'kind':'pick','id':'second'}],[{'kind':'player','id':'depth'}]
        self.assertEqual(rs.sale_bonus(data,'a',incoming,outgoing,20),6)
        self.assertEqual(rs.sale_bonus(data,'b',incoming,outgoing,20),0)
        self.assertEqual(rs.sale_bonus(data,'a',[],outgoing,20),0)
        data['team_plans'] = {'a':{'core_ids':['depth']}}
        self.assertEqual(rs.sale_bonus(data,'a',incoming,outgoing,20),0)

    def fixture(self):
        data = {'players':[{'id':'fa','name':'Target','team_id':None}, {'id':'depth','name':'Depth','team_id':'a'}],
                'teams':[{'id':t,'abbrev':t.upper()} for t in ('a','b','human')],
                'player_asset_valuations':[{'player_id':'depth','player_value':20}],
                'contracts':[], 'team_plans':{}}
        saved = {'meta':{'user_team_id':'human'},'state':{'current_date':'2027-07-02'},
                 'free_agent_player_ids':['fa'],'free_agency_state':{'day':2,'roster_space_targets':{
                     'a':{'team_id':'a','day':2,'player_id':'fa','aav_millions':10,'years':2,'upgrade':10}}}}
        return data,saved

    def test_no_buyer_acceptance_is_ever_fabricated(self):
        data,saved = self.fixture()
        before = deepcopy(saved)
        plan = lambda c,s,p,t,*a: {'ok':True,'upgrade':10,'cuts':[{'player_id':'depth'}] if t=='a' else []}
        with patch('nba_gm_data.contract_protection.roster_signing_plan',side_effect=plan), \
             patch.object(play,'build_free_agency_offer_record',return_value={'interest_score':99}), \
             patch.object(play,'free_agency_accept_threshold',return_value=70), \
             patch.object(tx,'tradeable_picks_for_team',return_value=[{'id':'second','round':2,'season':'2028'}]), \
             patch.object(tx,'evaluate_trade',return_value={'accepted_by_all':False,'legality':{'status':'legal'}}) as evaluate:
            self.assertEqual(rs.sale_candidates(data,saved,'human',17),[])
            self.assertEqual(evaluate.call_count,1)
        self.assertEqual(saved,before)

    def test_a_lost_free_agent_target_cancels_the_liquidation(self):
        data,saved = self.fixture();saved['free_agent_player_ids']=[]
        with patch.object(tx,'evaluate_trade') as evaluate:
            self.assertEqual(rs.sale_candidates(data,saved,'human',17),[])
            evaluate.assert_not_called()

    def test_approved_sale_still_requires_a_substantial_real_return(self):
        data,saved = self.fixture()
        plan = lambda c,s,p,t,*a: {'ok':True,'upgrade':10,'cuts':[{'player_id':'depth'}] if t=='a' else []}
        report = {'accepted_by_all':True,'legality':{'status':'legal'},'evaluations':[],
                  'proposal':{'from_assets':[{'kind':'player','id':'depth'}], 'to_assets':[{'kind':'pick','id':'second'}]}}
        with patch('nba_gm_data.contract_protection.roster_signing_plan',side_effect=plan), \
             patch.object(play,'build_free_agency_offer_record',return_value={'interest_score':99}), \
             patch.object(play,'free_agency_accept_threshold',return_value=70), \
             patch.object(tx,'tradeable_picks_for_team',return_value=[{'id':'second','round':2,'season':'2028'}]), \
             patch.object(tx,'evaluate_trade',return_value=report), \
             patch.object(tx,'candidate_from_evaluation',side_effect=lambda c,r:deepcopy(r)), \
             patch.object(tx,'package_value_for_team',side_effect=[5,20]):
            self.assertEqual(rs.sale_candidates(data,saved,'human',17),[])
        with patch('nba_gm_data.contract_protection.roster_signing_plan',side_effect=plan), \
             patch.object(play,'build_free_agency_offer_record',return_value={'interest_score':99}), \
             patch.object(play,'free_agency_accept_threshold',return_value=70), \
             patch.object(tx,'tradeable_picks_for_team',return_value=[{'id':'second','round':2,'season':'2028'}]), \
             patch.object(tx,'evaluate_trade',return_value=report), \
             patch.object(tx,'candidate_from_evaluation',side_effect=lambda c,r:deepcopy(r)), \
             patch.object(tx,'package_value_for_team',side_effect=[16,20]):
            candidates = rs.sale_candidates(data,saved,'human',17)
            self.assertEqual(len(candidates),1)
            self.assertTrue(candidates[0]['accepted_by_all'])

    def test_shared_automatic_trade_route_does_not_overwrite_refusal(self):
        data,saved = self.fixture()
        rejected = {'accepted_by_all':False,'legality':{'status':'legal'},'proposal':{'id':'rejected','from_team_id':'a','to_team_id':'b'}}
        with patch.object(rs,'sale_candidates',return_value=[rejected]), \
             patch.object(play,'free_agency_cap_dump_candidates',return_value=[]), \
             patch.object(play,'apply_trade_to_state') as apply:
            result = play.maybe_run_free_agency_ai_trades_state(data,saved,data,'HUMAN',17,phase='pre_resolution')
        self.assertEqual(result['applied_count'],0)
        apply.assert_not_called()

    def test_selling_depth_does_not_guarantee_a_signing_or_duplicate_a_bid(self):
        data,saved = self.fixture()
        saved['free_agent_offers']=[{'player_id':'fa','team_id':'a','status':'active'}]
        with patch.object(play,'canonical_with_save',return_value=data):
            self.assertFalse(rs.activate_target(data,saved,saved['free_agency_state']['roster_space_targets']['a'],17))
        self.assertEqual(len(saved['free_agent_offers']),1)


if __name__ == '__main__': unittest.main()
