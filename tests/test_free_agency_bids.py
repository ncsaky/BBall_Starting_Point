from contextlib import ExitStack
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from nba_gm_data import play


class FreeAgencyBidTests(unittest.TestCase):
    def setUp(self):
        self.player={'id':'p','name':'Starter','age':23,'position':'SG','minutes_projection':25,'team_id':None}
        self.data={'players':[self.player], 'teams':[{'id':f't{i}','abbrev':f'T{i}'} for i in range(5)]}
        self.save={'meta':{'user_team_id':'human','season':'2026-27'},'state':{'current_date':'2027-07-05'},
                   'free_agent_player_ids':['p'],'free_agent_offers':[], 'free_agency_state':{
                       'season':'2026-27','day':5,'status':'active','player_asks_millions':{'p':20},'ai_days_processed':['2026-27:5']}}
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for name,value in (('canonical_with_save',self.data),('with_transaction_context',self.data)):
            self.stack.enter_context(patch.object(play,name,return_value=value))
        self.stack.enter_context(patch.object(play,'canonical_free_agent_market_by_id',return_value={}))
        self.stack.enter_context(patch.object(play,'free_agency_player_priority',return_value=100))
        self.stack.enter_context(patch.object(play,'ai_free_agency_suitors',side_effect=lambda c,s,p,teams,*args:teams))
        self.stack.enter_context(patch.object(play,'desired_ai_offer_count',return_value=2))
        self.stack.enter_context(patch.object(play,'extension_safe_year_limit',return_value=4))
        self.stack.enter_context(patch.object(play,'build_free_agency_offer_record',side_effect=self.offer))

    def offer(self,c,s,p,t,years,aav,ask,seed,source):
        return {'id':f"{s['free_agency_state']['day']}:{p['id']}:{t['id']}",'player_id':p['id'],'team_id':t['id'],
                'years':years,'aav_millions':aav,'source':source,'status':'active','interest_score':90,'season':'2026-27'}

    def process(self):
        return play.process_ai_free_agency_offers_for_day_state(self.data,self.save,'HUMAN',7)

    @staticmethod
    def funded(rule):
        """A stand-in for the cap ledger's bid check (FA-REAL): ``rule(team, aav, save)`` says if the team can pay."""
        def fake(active, save, team, player, aav, years, lower, bird):
            if not rule(team, aav, save):
                return None
            return {'aav': aav, 'years': years,
                    'quote': {'payment': {'route': 'cap_room', 'amount': aav * 1e6, 'season': '2027-28'}}}
        return fake

    def test_unfunded_first_choices_do_not_consume_offer_slots(self):
        with patch.object(play,'ai_bid_payment',side_effect=self.funded(lambda t,a,s:t['abbrev'] in {'T3','T4'})):
            result=self.process()
        self.assertEqual(result['created_count'],2)
        self.assertEqual({o['team_id'] for o in self.save['free_agent_offers']},{'t3','t4'})

    def test_legacy_day_catch_up_is_once_only_across_serialized_reload(self):
        with patch.object(play,'signing_cap_check',return_value={'ok':True}):
            self.assertEqual(self.process()['created_count'],2)
            before=deepcopy(self.save);self.save=json.loads(json.dumps(self.save))
            self.assertEqual(self.process(),{'created_count':0,'_changed':False})
            self.assertEqual(self.save,before)
        self.assertEqual(self.save['free_agency_state']['ai_days_processed'],['2026-27:5'])

    def test_existing_active_bids_count_towards_the_quota_without_duplicates(self):
        self.save['free_agent_offers']=[self.offer(self.data,self.save,self.player,self.data['teams'][3],4,20,20,7,'ai')]
        with patch.object(play,'ai_bid_payment',side_effect=self.funded(lambda t,a,s:t['abbrev'] in {'T3','T4'})):
            self.assertEqual(self.process()['created_count'],1)
        self.assertEqual(len(self.save['free_agent_offers']),2)

    def test_no_offer_is_invented_when_every_team_is_unfunded(self):
        with patch.object(play,'ai_bid_payment',return_value=None):
            self.assertEqual(self.process()['created_count'],0)
        self.assertEqual(self.save['free_agent_offers'],[])

    def test_active_bids_reserve_cap_for_other_players(self):
        second={**self.player,'id':'q'};self.data['players'].append(second)
        self.save['free_agent_player_ids'].append('q');self.save['free_agency_state']['player_asks_millions']['q']=20
        def room(team, aav, save):   # the team's live bids hold their money (cap_ledger.reservations)
            held = sum(o['aav_millions'] for o in save['free_agent_offers']
                       if o['team_id'] == team['id'] and o['status'] == 'active')
            return held + aav <= 25
        with patch.object(play,'ai_bid_payment',side_effect=self.funded(room)):
            self.process()
        for team in self.data['teams']:
            self.assertLessEqual(sum(o['aav_millions'] for o in self.save['free_agent_offers'] if o['team_id']==team['id']),25)

    def test_full_rosters_and_pending_minimum_bids_reserve_offseason_slots(self):
        self.data['players'] += [{'id':f'r{i}','team_id':'t0'} for i in range(20)]
        self.save['free_agent_offers'].append({'id':'reserve','player_id':'q','team_id':'t0','status':'active','source':'ai','aav_millions':1.9,'years':1})
        with patch.object(play,'signing_cap_check',return_value={'ok':True}):self.process()
        self.assertFalse(any(o['player_id']=='p' and o['team_id']=='t0' for o in self.save['free_agent_offers']))

    def test_ai_does_not_bid_on_human_controlled_teams(self):
        self.save['meta']['user_team_id']='t0'
        with patch.object(play,'signing_cap_check',return_value={'ok':True}):self.process()
        self.assertNotIn('t0',{o['team_id'] for o in self.save['free_agent_offers']})

    def test_veterans_get_shorter_terms_and_ai_bids_respect_the_minimum(self):
        self.assertEqual(play.free_agency_preferred_years(self.player,24),4)
        self.assertEqual(play.free_agency_preferred_years({**self.player,'age':36},24),2)
        self.player['age']=38;self.save['free_agency_state']['player_asks_millions']['p']=1.6
        with patch.object(play,'signing_cap_check',return_value={'ok':True}):self.process()
        self.assertTrue(all(o['years']==1 and o['aav_millions']>=play.league_minimum_aav_millions() for o in self.save['free_agent_offers']))

    def test_ai_bids_use_the_fitted_ask_and_salary_bounds(self):
        self.player.update(age=30, draft_year=2020, minutes_projection=12)
        self.data["player_asset_valuations"] = [
            {"player_id": "p", "player_value": 25, "on_court_value": 10},
        ]
        self.save["state"]["phase"] = "free_agency"
        state = self.save["free_agency_state"]
        state["player_asks_millions"].clear()
        with patch("nba_gm_data.sim.player_feature_vector") as features, \
             patch.object(play, "signing_cap_check", return_value={"ok": True}):
            features.return_value.features = {}
            self.assertEqual(self.process()["created_count"], 2)
        ask = state["player_asks_millions"]["p"]
        lower, upper = play.free_agency_fitted_bounds(self.save, "p")
        self.assertEqual(ask, lower)
        for call in play.build_free_agency_offer_record.call_args_list:
            aav, market_ask = call.args[5:7]
            self.assertEqual(market_ask, ask)
            self.assertLessEqual(lower, aav)
            self.assertLessEqual(aav, upper)

    def test_current_quality_can_draw_competition_despite_a_small_previous_role(self):
        player={**self.player,'minutes_projection':10}
        # The process fixture mocks demand; exercise the real helper separately.
        self.stack.close()
        self.assertGreaterEqual(play.desired_ai_offer_count(player,17.6,5,7,quality=68),2)
        self.assertGreaterEqual(play.desired_ai_offer_count(player,24,1,7,quality=68),3)
        self.assertLess(play.desired_ai_offer_count(player,3,1,7,quality=40),2)

    def test_live_team_fit_overrides_stale_market_suitors(self):
        self.stack.close()
        valuation={'player_id':'p','player_value':75}
        self.data.update({'team_strategic_states':[{'team_id':'t0'}],
                          'front_office_profiles':[{'team_id':'t0'}],
                          'player_asset_valuations':[valuation]})
        teams=self.data['teams'][:2]
        with patch('nba_gm_data.contract_ai.signing_fit_score',
                   side_effect=lambda c,t,p,v:10 if t=='t0' else 90) as fit:
            suitors=play.ai_free_agency_suitors(self.data,self.save,self.player,teams,
                                             {'likely_suitors':['t0'],'team_fit_score':99},7,5)
        self.assertEqual(suitors[0]['id'],'t1')
        self.assertEqual(fit.call_count,2)
        self.assertTrue(all(call.args[3] is valuation for call in fit.call_args_list))

    def test_blocked_best_offer_falls_back_to_an_executable_runner_up(self):
        self.save['free_agent_offers']=[{'id':'best','player_id':'p','team_id':'t0','source':'ai','status':'active','interest_score':95,'aav_millions':22,'years':3},
                                      {'id':'second','player_id':'p','team_id':'t1','source':'ai','status':'active','interest_score':90,'aav_millions':21,'years':3}]
        with patch.object(play,'apply_free_agency_offer_state',side_effect=[{'status':'blocked'},{'status':'applied'}]) as apply:
            result=play.resolve_free_agency_day_state(self.data,self.save,7)
        self.assertEqual([call.args[2] for call in apply.call_args_list],['best','second'])
        self.assertEqual(result['accepted_count'],1)
        self.assertEqual(result['accepted_offers'][0]['team_id'],'t1')

    def test_failed_best_offer_does_not_force_acceptance_of_an_unwanted_bid(self):
        self.save['free_agent_offers']=[
            {'id':'best','player_id':'p','team_id':'t0','source':'ai','status':'active',
             'interest_score':95,'aav_millions':22,'years':3},
            {'id':'unwanted','player_id':'p','team_id':'t1','source':'ai','status':'active',
             'interest_score':1,'aav_millions':2,'years':1}]
        with patch.object(play,'apply_free_agency_offer_state',return_value={'status':'blocked'}) as apply:
            result=play.resolve_free_agency_day_state(self.data,self.save,7)
        self.assertEqual([call.args[2] for call in apply.call_args_list],['best'])
        self.assertEqual(result['accepted_count'],0)


if __name__=='__main__':unittest.main()
