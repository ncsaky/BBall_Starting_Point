"""Prospects and signed rookies share one conversion and presentation scale."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from nba_gm_data import app_actions as aa, draft, play
from nba_gm_data.prospect_cards import prospect_rating_projection
from nba_gm_data.save import player_display_attribute_summary
from nba_gm_data.schema import DraftPickDecision, to_plain


class ProspectRatingParityTests(unittest.TestCase):
    def context(self, seed=17, modeled=True):
        generated = to_plain(draft.generate_draft_class_records('2030', seed, talent_model=modeled))
        return {'meta': {'talent_model_version':2} if modeled else {}, **generated}

    def signed(self, context, prospect, slot=None):
        slot = slot or prospect['rank']
        selection = {'id':f"selection:{prospect['id']}", 'pick_id':f'pick:{slot}', 'overall_pick':slot,
                     'team_id':'team_test', 'prospect_id':prospect['id'], 'draft_year':'2030'}
        pending = {'id':selection['id'], 'selection':selection, 'prospect':prospect,
                   'team':{'id':'team_test','abbrev':'TST'}}
        save = {'version':'league_save_v1', 'pending_draft_selections':[pending],
                'draft_state':{'draft':context}, 'state':{'current_date':'2030-06-25'}}
        result = draft.apply_draft_selection_to_save_state(save, selection['id'], date='2030-06-25', sign_rookie=True)
        self.assertEqual(result['status'],'applied')
        player = save['generated_players'][0]
        active = {'meta':context['meta'], 'players':[player], 'traits':save['generated_traits']}
        return save, player_display_attribute_summary(active, player['id'])

    def test_fully_scouted_profiles_match_real_draft_application_across_classes_and_models(self):
        for modeled in (False, True):
            for seed in (17,29,913):
                context = self.context(seed, modeled)
                before = deepcopy(context)
                for index in (0,2,9,29,44,59):
                    prospect = context['draft_prospects'][index]
                    save, actual = self.signed(context, prospect)
                    projection = prospect_rating_projection(context,prospect,{},100)
                    self.assertEqual(projection['ratings'],actual)
                    self.assertEqual(projection['now'],actual['overall'])
                    # A reload and an actual selection at another slot use the
                    # resulting rookie role, not a stale rank-based projection.
                    moved_save, moved = self.signed(context, prospect, slot=40)
                    reloaded = json.loads(json.dumps(moved_save))
                    self.assertEqual(prospect_rating_projection(context,prospect,{},100,reloaded)['ratings'],moved)
                self.assertEqual(context,before)

    def test_board_card_and_scouting_display_use_the_same_projected_values(self):
        context = self.context()
        prospect = context['draft_prospects'][0]
        report = {'estimated_current':{'mid':prospect['current_ability']-2},
                  'estimated_potential':{'mid':prospect['potential']+2},
                  'trait_estimates':{row['trait_key']:{'mid':row['value']-3} for row in context['draft_prospect_traits']
                                     if row['prospect_id']==prospect['id']}}
        board = {'year':'2030','entries':[draft.board_entry_payload({'board_rank':1},prospect)]}
        save = {'meta':{'season':'2029-30'},'state':{'current_date':'2030-06-25'}}
        for coverage in (0,50,100):
            with patch.object(play,'scouting_report_for',return_value={**report,'coverage':coverage}):
                scout = play.prospect_scout_display(context,prospect,'team_test',save)
                enriched = aa.enrich_draft_board_scouting(context,save,'team_test',deepcopy(board))
            visible = aa.prospect_card_ratings(prospect,scout,report)
            displayed = enriched['entries'][0]['scout_display']
            self.assertEqual(displayed['now'],scout['now'])
            self.assertEqual(displayed['potential'],scout['potential'])
            self.assertEqual(displayed['ratings'],visible['ratings'])
            self.assertTrue(all(value==scout['ratings'][key] for key,value in visible['ratings'].items()))
            if coverage==0:
                self.assertEqual(visible['ratings'],{})
            elif coverage==100:
                # Full coverage shows the scouts' report, never the hidden truth (draft-boards plan, step 1). The
                # conversion is the signed rookie's: the report's numbers give the report's ratings.
                _, actual = self.signed(context,prospect)
                self.assertNotEqual(scout['ratings'],actual)
                self.assertEqual(scout['ratings'],prospect_rating_projection(context,prospect,report,100)['ratings'])

    def test_in_progress_legacy_class_takes_precedence_over_new_generated_previews(self):
        old = self.context(seed=7)
        prospect = old['draft_prospects'][0]
        active = {'meta':{'talent_model_version':2,'draft_class_seed':913},'teams':[{'id':'team_test','abbrev':'TST'}]}
        save = {'meta':{'user_team_abbrev':'TST'},'draft_state':{'draft':old}}
        context = {'save':save,'active':active}
        with patch.object(aa,'dashboard_read_context',return_value=context), \
             patch.object(aa,'transaction_read_active',return_value=active), \
             patch.object(aa,'user_team_abbrev',return_value='TST'), \
             patch.object(play,'prospect_scouted_pct',return_value=100), \
             patch('nba_gm_data.spatial.prospect_spatial_profile',return_value={}):
            card = aa.prospect_card_payload(active,Path('unused.json'),prospect['id'],'2030')
        _, actual = self.signed(old,prospect)
        self.assertEqual(card['overall'],actual['overall'])
        self.assertEqual(card['ratings'],{key:actual[key] for key in aa.PROSPECT_CARD_RATING_DEPENDENCIES})

    def test_future_preview_and_draft_share_class_seed_without_tying_selection_rng(self):
        canonical = {'meta':{'draft_class_seed':913,'talent_model_version':2}, '_allow_internal_caches':True,
                     'teams':[{'id':'team_test','abbrev':'TST'}], 'players':[], 'traits':[], 'contracts':[],
                     'team_strategic_states':[{'team_id':'team_test','phase':'developing','salary_posture':'below_cap'}]}
        first = draft.generated_class_for_context(canonical,'2031',1)
        second = draft.generated_class_for_context(canonical,'2031',7)
        self.assertIs(first,second)
        class_records = draft.draft_scouting.class_records(canonical,'2031')
        board = {'entries':[{'prospect':p} for p in class_records[0]]}
        with patch.object(draft,'generate_draft_order',return_value={'draft_order':[],'lottery':{}}), \
             patch.object(draft,'with_draft_context',side_effect=lambda c,config=None: c):
            result = draft.simulate_draft(canonical,'2031',7)
        self.assertEqual(result['seed'],7)
        self.assertEqual(result['draft_prospects'],first['draft_prospects'])
        self.assertEqual({row['prospect']['id'] for row in board['entries']},{p['id'] for p in result['draft_prospects']})
        prospect = board['entries'][0]['prospect']
        actual_context = {'meta':canonical['meta'],**first}
        _, actual = self.signed(actual_context,prospect)
        self.assertEqual(prospect_rating_projection(canonical,prospect,{},100)['ratings'],actual)

    def test_canonical_class_keeps_its_skill_records_in_the_live_draft_payload(self):
        context = self.context()
        # The preview projects minutes from the board rank, so draft the rank-1 prospect at pick 1. (Classes are
        # numbered by public grade since 2026-11-17, so list order is no longer rank order.)
        prospect = min(context['draft_prospects'], key=lambda p: int(p.get('rank') or 99))
        team = {'id':'team_test','abbrev':'TST'}
        pick = {'id':'pick:1','overall_pick':1,'round':1,'current_owner_team_id':team['id']}
        context.update(teams=[team],draft_picks=[],draft_board_entries=[{'team_id':team['id'],'prospect_id':prospect['id']}])
        context['draft_classes'][0]['season']='2030'
        decision = DraftPickDecision('decision',pick['id'],team['id'],prospect['id'],'select',1,1,0,[],[],'fixture')
        with patch.object(draft,'with_draft_context',return_value=context), \
             patch.object(draft,'generate_draft_order',return_value={'draft_order':[pick],'lottery':{}}), \
             patch.object(draft,'team_by_id',return_value=team), \
             patch.object(draft,'gm_rows',return_value=[{'prospect_id':prospect['id']}]), \
             patch.object(draft,'gm_decision',return_value=decision):
            result = draft.simulate_draft(context,'2030',7)
        self.assertEqual(result['draft_prospect_traits'],context['draft_prospect_traits'])
        self.assertEqual(result['draft_prospects'],context['draft_prospects'])
        save = {'version':'league_save_v1','draft_state':{'draft':result},'pending_draft_selections':result['pending_draft_selections']}
        draft.apply_draft_selection_to_save_state(save,result['pending_draft_selections'][0]['id'],sign_rookie=True)
        player = save['generated_players'][0]
        ratings = player_display_attribute_summary({'meta':context['meta'],'players':[player],'traits':save['generated_traits']},player['id'])
        self.assertEqual(prospect_rating_projection(context,prospect,{},100)['ratings'],ratings)

    def test_existing_signed_player_is_not_recreated_from_missing_legacy_traits(self):
        context = self.context()
        prospect = context['draft_prospects'][0]
        legacy = {**context,'draft_prospect_traits':[]}
        save, actual = self.signed(legacy,prospect)
        context.update(players=save['generated_players'],traits=save['generated_traits'])
        before = deepcopy(save)
        self.assertEqual(prospect_rating_projection(context,prospect,{},100,save)['ratings'],actual)
        self.assertEqual(save,before)

    def test_legacy_unfinished_draft_backfills_skills_once_without_touching_signed_players(self):
        context = self.context()
        prospect = context['draft_prospects'][0]
        saved = {'draft_state':{'year':'2030','status':'in_progress','draft':{
            'pending_draft_selections':[{'prospect':prospect}]}},'generated_players':[{'id':'already-signed'}]}
        with patch.object(play,'load_save',return_value=saved), \
             patch.object(play,'ensure_league_save_defaults',side_effect=lambda s,c:s), \
             patch.object(play,'materialize_draft_order_pick_assets',return_value=False), \
             patch.object(play,'sync_live_draft_state_to_saved_order',return_value=False), \
             patch.object(play,'refresh_live_draft_state_ownership',return_value=False), \
             patch.object(play,'write_save') as write:
            state = play.ensure_live_draft_state(context,Path('unused.json'),'2030',7)
            self.assertEqual(len(state['draft']['draft_prospect_traits']),12)
            self.assertEqual(saved['generated_players'],[{'id':'already-signed'}])
            write.assert_called_once()
            play.ensure_live_draft_state(context,Path('unused.json'),'2030',7)
            write.assert_called_once()


if __name__=='__main__':
    unittest.main()
