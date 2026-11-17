"""Offline role experiment: model controls, finite budgets, no production coupling."""
from copy import deepcopy
from dataclasses import replace
import itertools
import json
import random
import unittest
import weakref

from experiments.defensive_roles.model import (
    JOBS, KEYS, RECIPES, Context, Player, Trait, assign, deployment_scores, estimate, summarize,
)


def player(i='p', value=50, **edits):
    values = {key: value for key in KEYS.values()}; values.update(edits)
    return Player(i, i, tuple((k, Trait(v, .8, 'controlled')) for k, v in values.items()), 80)


def context():
    return Context('equal', tuple((job, 1) for job in JOBS))


class DefensiveRolePrototypeTests(unittest.TestCase):
    def test_weights_and_uniform_neutral_anchors(self):
        for recipe in RECIPES.values(): self.assertAlmostEqual(sum(w for _, w in recipe), 1)
        scores = estimate(player())['roles']
        self.assertTrue(all(r['score'] == 50 for r in scores.values()))
        for value in (0, 25, 50, 75, 90, 100):
            self.assertTrue(all(0 <= r['score'] <= 100 for r in estimate(player(value=value))['roles'].values()))

    def test_missing_inputs_are_disclosed_and_never_excellent(self):
        result = estimate(Player('x', 'Unknown', ()))
        for row in result['roles'].values():
            self.assertEqual(row['score'], 35)
            self.assertEqual(row['input_coverage'], 0)
            self.assertEqual(row['source_confidence'], 0)
            self.assertTrue(row['missing_inputs'])
            self.assertEqual(row['direct_job_measurement_coverage'], 0)

    def test_missing_critical_channel_cannot_hide_behind_other_elite_inputs(self):
        p = player(value=99)
        for job, key in (('poa','foot_speed_lateral_agility'), ('chaser','screen_navigation'),
                         ('helper','scheme_iq'), ('anchor_big','rim_deterrence')):
            unknown = replace(p,traits=tuple((k,t) for k,t in p.traits if k != key))
            self.assertLessEqual(estimate(unknown)['roles'][job]['score'],55)

    def test_cardio_workload_proxy_does_not_manufacture_intrinsic_role_talent(self):
        self.assertEqual(estimate(player(stamina_cardio=10))['roles'],
                         estimate(player(stamina_cardio=99))['roles'])

    def test_weight_and_bottleneck_uncertainty_stays_visible_and_bounded(self):
        p = player(value=90,foot_speed_lateral_agility=30)
        strict = estimate(p,bottleneck_allowance=10)
        loose = estimate(p,bottleneck_allowance=30)
        self.assertLess(strict['roles']['poa']['score'],loose['roles']['poa']['score'])
        equal = estimate(p,uniform_weight_blend=1)
        self.assertNotEqual(equal['roles']['wing_stopper']['uncapped_blend'],
                            estimate(p)['roles']['wing_stopper']['uncapped_blend'])
        self.assertEqual(equal['roles']['wing_stopper']['score'],50)  # same binding weakness
        with self.assertRaises(ValueError):estimate(p,uniform_weight_blend=-1)

    def test_role_label_observation_identity_and_height_cannot_grant_skill(self):
        p = player(); a = estimate(p)['roles']
        for change in ({'name': 'Star'}, {'height': 88}, {'observed_jobs': ('anchor_big',)}):
            self.assertEqual(a, estimate(replace(p, **change))['roles'])
        self.assertIsNone(estimate(p)['sheltered']['score'])

    def test_selective_components_and_bottlenecks(self):
        a = estimate(player())['roles']; b = estimate(player(rim_deterrence=100))['roles']
        self.assertEqual(a['poa'], b['poa']); self.assertEqual(a['chaser'], b['chaser'])
        self.assertGreater(b['anchor_big']['score'], a['anchor_big']['score'])
        bad_feet = estimate(player(value=99, foot_speed_lateral_agility=10))['roles']
        self.assertLessEqual(bad_feet['poa']['score'], 30)
        self.assertLessEqual(bad_feet['mobile_big']['score'], 30)
        self.assertTrue(bad_feet['poa']['bottleneck']['binding'])

    def test_all_six_components_monotone_without_rim_plateau(self):
        for key in KEYS.values():
            last = None
            for v in (0, 25, 50, 75, 90, 99, 100):
                rows = estimate(player(**{key: v}))['roles']
                if last:
                    for job in JOBS: self.assertGreaterEqual(rows[job]['score'], last[job]['score'])
                last = rows
        low = estimate(player(value=90, rim_deterrence=99))['roles']
        high = estimate(player(value=90, rim_deterrence=100))['roles']
        self.assertGreater(high['anchor_big']['score'], low['anchor_big']['score'])

    def test_deterministic_no_rng_and_no_output_alias_or_input_mutation(self):
        p = player(); lineup = [player(str(i)) for i in range(5)]
        before = deepcopy(lineup); state = random.getstate()
        a = estimate(p); b = estimate(p); self.assertEqual(a, b)
        a['roles']['poa']['limitations'].append('poison')
        self.assertEqual(b, estimate(p))
        shares = assign(lineup, context()); report = summarize(lineup, context(), shares)
        report['players'][0]['shares']['poa'] = 900
        self.assertEqual(shares, assign(lineup, context()))
        self.assertEqual(lineup, before); self.assertEqual(random.getstate(), state)
        self.assertEqual(json.dumps(estimate(p), sort_keys=True), json.dumps(b, sort_keys=True))

    def test_completed_outputs_do_not_keep_private_input_snapshots_alive(self):
        p = player(); ref = weakref.ref(p); output = estimate(p)
        del p
        self.assertIsNone(ref())
        self.assertEqual(output['roles']['poa']['score'],50)

    def test_assignment_meets_capacity_and_context_budgets_with_hybrids(self):
        lineup = [player(str(i), value=40+i*10) for i in range(5)]
        ctx = Context('hybrid', tuple(zip(JOBS, (1, .7, .8, 1, .6, .9))))
        shares = assign(lineup, ctx)
        self.assertTrue(any(sum(v > 0 for v in row.values()) > 1 for row in shares.values()))
        for row in shares.values(): self.assertAlmostEqual(sum(row.values()), 1)
        result = summarize(lineup, ctx, shares)
        self.assertEqual(result['covered_responsibility_share'], 1)
        self.assertAlmostEqual(result['usage_mean_reference'], result['coverage_adjusted_index'], places=3)

    def test_optimizer_matches_exhaustive_integer_assignment(self):
        # Five one-player role demands. Transportation optimum can be taken at
        # an integer vertex; compare every feasible 5! pure assignment.
        ctx = Context('five', tuple((j, 0 if j == 'helper' else 1) for j in JOBS))
        lineup = [player(str(i), value=30+i*10, **{
            list(KEYS.values())[i]: 95}) for i in range(5)]
        jobs = [j for j in JOBS if j != 'helper']; scores = deployment_scores(lineup, ctx)
        best = max(sum(scores[p.id][j] for p,j in zip(lineup, perm))/5 for perm in itertools.permutations(jobs))
        result = summarize(lineup, ctx, assign(lineup, ctx))
        self.assertAlmostEqual(result['usage_mean_reference'], best, places=4)

    def test_shelter_and_duplicate_credit_cannot_inflate_a_lineup(self):
        lineup = [player(str(i), value=75) for i in range(5)]; ctx = context()
        normal = summarize(lineup, ctx, assign(lineup, ctx))
        sheltered = summarize(lineup, ctx, {p.id: {'sheltered': 1} for p in lineup})
        easy = summarize(lineup, ctx, {p.id: {'anchor_big': 1} for p in lineup})
        self.assertEqual(sheltered['coverage_adjusted_index'], 0)
        self.assertEqual(sheltered['usage_mean_reference'], 0)
        self.assertLess(easy['coverage_adjusted_index'], normal['coverage_adjusted_index'])
        self.assertGreater(easy['jobs']['anchor_big']['excess_no_credit'], 0)
        self.assertAlmostEqual(easy['covered_responsibility_share'], 1/6, places=5)

    def test_teammates_and_opponent_requirements_change_fit_not_base_skill(self):
        base = [player(str(i), value=60) for i in range(5)]
        base[-1] = player('4', value=60, rim_deterrence=100, scheme_iq=90)
        a = Context('rim', tuple((j, 6 if j == 'anchor_big' else 1) for j in JOBS))
        b = Context('movement', tuple((j, 6 if j == 'chaser' else 1) for j in JOBS))
        before = estimate(base[-1])
        self.assertNotEqual(assign(base, a), assign(base, b))
        self.assertEqual(before, estimate(base[-1]))
        weak = [*base[:-1], player('4', value=20)]
        self.assertGreater(summarize(base, a, assign(base,a))['coverage_adjusted_index'],
                           summarize(weak,a,assign(weak,a))['coverage_adjusted_index'])

    def test_physical_fit_is_soft_separate_and_never_duplicates_rim_size(self):
        small = player('s', value=80); tall = replace(small, id='t', height=88)
        ctx = replace(context(), target_wing_height=90)
        scores = deployment_scores([small,tall], ctx)
        self.assertEqual(scores['s']['anchor_big'], scores['t']['anchor_big'])
        self.assertLess(scores['s']['wing_stopper'], scores['t']['wing_stopper'])
        self.assertGreaterEqual(scores['s']['wing_stopper'], .7*80)
        self.assertEqual(estimate(small)['roles'], estimate(tall)['roles'])
        unknown = replace(small, height=None)
        self.assertEqual(deployment_scores([unknown],ctx)['s']['wing_stopper'], 80)

    def test_availability_changes_deployment_only_and_sequential_inputs_stay_fresh(self):
        p = player(); before = estimate(p)
        ctx = replace(context(), availability=((p.id,.5),))
        self.assertEqual(deployment_scores([p],ctx)[p.id]['poa'], 25)
        self.assertEqual(before, estimate(p))
        updated = player(rim_deterrence=95)
        self.assertNotEqual(estimate(updated)['roles']['anchor_big'], before['roles']['anchor_big'])
        self.assertEqual(estimate(p), before)

    def test_reject_invalid_floats_duplicate_ids_and_unfunded_assignments(self):
        with self.assertRaises(ValueError): estimate(player(rim_deterrence=float('nan')))
        with self.assertRaises(ValueError): estimate(player(stamina_cardio=float('inf')))
        with self.assertRaises(ValueError): assign([player()]*5, context())
        lineup = [player(str(i)) for i in range(5)]
        with self.assertRaises(ValueError): summarize(lineup, context(), {p.id:{'poa':.5} for p in lineup})
        with self.assertRaises(ValueError): summarize(lineup, context(), {p.id:{'poa':2,'sheltered':-1} for p in lineup})
        with self.assertRaises(ValueError): deployment_scores(lineup,replace(context(),availability=(('0',1.5),)))
        with self.assertRaises(ValueError): assign(lineup,replace(context(),demand=(('poa',-1),)))

if __name__ == '__main__': unittest.main()
