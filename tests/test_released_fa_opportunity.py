"""Released-player replacements must earn their role on the destination roster."""
from copy import deepcopy
import json
import unittest
import weakref
from unittest.mock import patch

from nba_gm_data import health, save as sv
import test_ai_roles as fixtures


def opportunity_fixture(incoming_quality=50, prior_minutes=42, cut_salary=1_900_000):
    data, saved = fixtures.AiRoleTests().fixture()
    data['meta'] = {'active_season': '2036-37'}
    saved.update(version=sv.SAVE_VERSION, free_agent_player_ids=['human00'],
                 released_free_agents={'human00': {'status': 'available', 'waived_by_team_id': 'human'}})
    saved['meta']['seed'] = 17
    saved['state'] = {'current_date': '2036-12-01', 'phase': 'regular_season'}
    for p in data['players']:
        p['age_base_start_year'] = 2036
        if p['id'] == 'human00':
            p.update(team_id=None, minutes_projection=prior_minutes)
            saved['rotation_baselines'][p['id']] = prior_minutes
    for t in data['traits']:
        if t['player_id'].startswith('ai'):
            t['value'] = 50 if t['player_id'] == 'ai14' else 75
        elif t['player_id'] == 'human00':
            t['value'] = incoming_quality
    data['contracts'] = [
        {'id': 'c-' + p['id'], 'player_id': p['id'], 'team_id': p['team_id'],
         'seasons': [{'season': s, 'salary': cut_salary if p['id'] == 'ai14' else 1_900_000,
                      'guaranteed_salary': cut_salary if p['id'] == 'ai14' else 1_900_000}
                     for s in ('2036-37', '2037-38')]}
        for p in data['players'] if p['team_id']]
    data['player_contract_market_profiles'] = [
        {'player_id': 'human00', 'role_tier': 'starter', 'expected_aav': 1_900_000,
         'asking_aav': 1_900_000}]
    return data, saved, next(p for p in data['players'] if p['id'] == 'human00')


class ReleasedFreeAgentOpportunityTests(unittest.TestCase):
    def destination(self, data, saved, player, **kwargs):
        return sv.released_free_agent_destination(data, saved, player,
                    saved['released_free_agents'][player['id']], 1_900_000, 17, '2036-12-01', **kwargs)

    def test_same_skills_cannot_buy_an_upgrade_with_previous_team_minutes(self):
        for mpg in (0, 30, 42):
            with self.subTest(prior_mpg=mpg):
                data, saved, player = opportunity_fixture(prior_minutes=mpg)
                original = deepcopy((data, saved))
                self.assertIsNone(self.destination(data, saved, player))
                self.assertEqual((data, saved), original)

    def test_real_upgrade_remains_eligible_at_every_prior_workload(self):
        for mpg in (0, 30, 42):
            with self.subTest(prior_mpg=mpg):
                data, saved, player = opportunity_fixture(96, mpg)
                result = self.destination(data, saved, player)
                self.assertIsNotNone(result)
                self.assertEqual(result['cut_player']['id'], 'ai14')

    def test_injury_cover_does_not_cut_the_out_starter(self):
        data, saved, player = opportunity_fixture(80, 0)
        saved['health_states'] = [{**health.default_state_dict('ai00', '2036-12-01'),
                                  'availability_status': 'out', 'return_date': '2037-02-01'}]
        original_health = deepcopy(saved['health_states'])
        result = self.destination(data, saved, player)
        self.assertIsNotNone(result)
        self.assertEqual(result['cut_player']['id'], 'ai14')
        self.assertEqual(saved['health_states'], original_health)

    def test_guaranteed_cut_cost_can_decline_an_otherwise_real_upgrade(self):
        data, saved, player = opportunity_fixture(65, 0)
        self.assertIsNotNone(self.destination(data, saved, player))
        data, saved, player = opportunity_fixture(65, 0, cut_salary=100_000_000)
        self.assertIsNone(self.destination(data, saved, player))

    def test_upside_and_core_priorities_still_protect_close_depth_choices(self):
        data, saved, player = opportunity_fixture(96, 0)
        for t in data['traits']:
            if t['player_id'] == 'ai13':
                t['value'] = 50
        project = next(p for p in data['players'] if p['id'] == 'ai14')
        project.update(age=20, current_ability=45, potential=95)
        saved['team_plans'] = {'ai': {'core_ids': ['ai14']}}
        result = self.destination(data, saved, player)
        self.assertEqual(result['cut_player']['id'], 'ai13')

    def test_old_employer_contract_does_not_supply_incoming_retention_credit(self):
        data, saved, player = opportunity_fixture(50, 42)
        data['contracts'].append({'player_id': player['id'], 'team_id': 'old', 'seasons': [
            {'season': '2036-37', 'salary': 100_000_000, 'guaranteed_salary': 100_000_000}]})
        self.assertIsNone(self.destination(data, saved, player))

    def test_real_full_roster_signing_waives_depth_and_preserves_dead_salary(self):
        for mpg in (0, 30, 42):
            with self.subTest(prior_mpg=mpg):
                data, saved, player = opportunity_fixture(96, mpg)
                saved['rotation_overrides'] = {'human': {'human01': 32}}
                human = deepcopy(saved['rotation_overrides'])
                before = sv.team_cap_summary(data, saved, 'ai')['salary_total']
                preview = sv.canonical_with_save(data, deepcopy(saved))
                active_player = next(p for p in preview['players'] if p['id'] == player['id'])
                salary = sv.released_free_agent_salary(active_player, {}, sv.player_attribute_summary(preview, player['id']))
                signed = sv.process_inseason_released_free_agent_signings(data, saved, 17, '2036-12-01')
                self.assertEqual(signed, {'human00'})
                self.assertEqual(saved['roster_overrides']['human00'], 'ai')
                self.assertIsNone(saved['roster_overrides']['ai14'])
                self.assertNotIn('human00', saved['free_agent_player_ids'])
                self.assertNotIn('ai14', saved['free_agent_player_ids'])
                self.assertEqual(saved['contract_overrides']['human00']['seasons'][0]['guaranteed_salary'], salary)
                self.assertEqual(saved['waiver_wire'][0]['player_id'], 'ai14')
                self.assertEqual(saved['waiver_wire'][0]['status'], 'pending')
                self.assertEqual(saved['waived_salary_obligations'][0]['remaining_cost_millions'], 3.8)
                active = sv.canonical_with_save(data, saved)
                self.assertEqual(sum(p['team_id'] == 'ai' for p in active['players']), 15)
                self.assertEqual(sv.team_cap_summary(active, saved, 'ai')['salary_total'], before + salary)
                self.assertEqual(saved['rotation_overrides'], human)
                logs = deepcopy(saved['transaction_logs'])
                self.assertEqual(sv.process_inseason_released_free_agent_signings(data, saved, 17, '2036-12-01'), set())
                self.assertEqual(saved['transaction_logs'], logs)

    def test_real_path_rejects_redundant_player_without_cut_or_signing(self):
        for mpg in (0, 30, 42):
            with self.subTest(prior_mpg=mpg):
                data, saved, _ = opportunity_fixture(50, mpg)
                saved['released_free_agents']['human00']['buyout_market_interest'] = True
                self.assertEqual(sv.process_inseason_released_free_agent_signings(data, saved, 17, '2036-12-01'), set())
                self.assertFalse(saved.get('transaction_logs'))
                self.assertFalse(saved.get('waived_salary_obligations'))
                self.assertFalse(saved.get('roster_overrides'))

    def test_second_real_signing_sees_first_cut_and_rebuilds_forecasts(self):
        data, saved, _ = opportunity_fixture(96, 0)
        second = next(p for p in data['players'] if p['id'] == 'human01')
        second.update(team_id=None, minutes_projection=30)
        saved['rotation_baselines'][second['id']] = 30
        saved['free_agent_player_ids'].append(second['id'])
        saved['released_free_agents'][second['id']] = {'status': 'available', 'waived_by_team_id': 'human'}
        data['contracts'] = [c for c in data['contracts'] if c['player_id'] != second['id']]
        for trait in data['traits']:
            if trait['player_id'] == second['id']:
                trait['value'] = 96
        builds = []
        original = sv.roster_retention_context

        def observe(*args, **kwargs):
            context = original(*args, **kwargs)
            builds.append({p['id'] for p in context['players'] if p.get('team_id') == 'ai'})
            return context

        with patch.object(sv, 'roster_retention_context', observe):
            signed = sv.process_inseason_released_free_agent_signings(data, saved, 17, '2036-12-01')
        self.assertEqual(signed, {'human00', 'human01'})
        self.assertEqual(len(builds), 2)
        self.assertIn('ai14', builds[0])
        self.assertNotIn('ai14', builds[1])
        cuts = [r['player_id'] for r in saved['waiver_wire']]
        self.assertEqual(len(set(cuts)), 2)
        active = sv.canonical_with_save(data, saved)
        self.assertEqual(sum(p['team_id'] == 'ai' for p in active['players']), 15)
        self.assertTrue({'human00', 'human01'} <= {p['id'] for p in active['players'] if p['team_id'] == 'ai'})

    def test_destination_baseline_is_shared_only_until_settlement(self):
        data, saved, player = opportunity_fixture(50, 42)
        context = sv.roster_retention_context(data, saved, prepared_active=True)
        with patch.object(sv, 'ai_role_targets', wraps=sv.ai_role_targets) as roles:
            for _ in range(3):
                self.assertIsNone(self.destination(data, saved, player, retention_context_factory=lambda: context))
        # One before roster, one after roster per inspected proposal.
        self.assertEqual(roles.call_count, 4)
        data['traits'] = [{**t, 'value': 96} if t['player_id'] == player['id'] else t for t in data['traits']]
        fresh = sv.roster_retention_context(data, saved, prepared_active=True)
        self.assertIsNotNone(self.destination(data, saved, player, retention_context_factory=lambda: fresh))

    def test_private_forecasts_release_and_never_enter_the_save(self):
        data, saved, _ = opportunity_fixture(96, 0)
        refs = []
        original = sv.released_free_agent_rotation_view

        def observe(context, roster):
            view = original(context, roster)
            refs.append(weakref.ref(context['_released_fa_forecast']))
            return view

        # A recording Mock would itself retain the context in call_args_list.
        with patch.object(sv, 'released_free_agent_rotation_view', observe):
            self.assertEqual(sv.process_inseason_released_free_agent_signings(data, saved, 17, '2036-12-01'), {'human00'})
        self.assertTrue(refs)
        self.assertTrue(all(ref() is None for ref in refs))
        json.dumps(saved)  # A ForecastSnapshot itself is not serializable.

        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        self.assertFalse({'_released_fa_forecast', '_released_fa_before_rosters'} & set(keys(saved)))


if __name__ == '__main__':
    unittest.main()
