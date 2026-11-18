"""Exactness checks for the month-speed work: every fast path must return what the plain path returns."""
from copy import deepcopy
import unittest

from nba_gm_data import pick_presentation as pp
from nba_gm_data import transactions as tx
from nba_gm_data.trade_review import MarketReview, _Inputs
from nba_gm_data.utils import copy_plain


def pick(pid, team, year, rnd=1, owner=None):
    return {'id': pid, 'season': str(year), 'round': rnd, 'original_team_id': team,
            'current_owner_team_id': owner or team, 'status': 'future'}


def swap(oid, a, b, holder, **extra):
    return {'id': oid, 'type': 'pick_swap', 'status': 'active', 'team_a_pick_id': a, 'team_b_pick_id': b,
            'current_rights_holder_team_id': holder, 'season': '2027', 'round': 1, 'benefit': 'better', **extra}


def league():
    """Three clubs, a two-step swap chain held by A (nested entitlement) and a three-pick allocation pool."""
    teams = [{'id': t, 'abbrev': t.upper() * 3} for t in ('a', 'b', 'c')]
    picks = [pick('a27', 'a', 2027), pick('b27', 'b', 2027), pick('c27', 'c', 2027),
             pick('a28', 'a', 2028), pick('b28', 'b', 2028), pick('c28', 'c', 2028)]
    for p in picks:
        p['_allocation_initial_owner_team_id'] = p['current_owner_team_id']
    terms = [
        swap('pick_obligation_realgm-x-1', 'a27', 'b27', 'a'),
        swap('pick_obligation_realgm-x-2', 'a27', 'c27', 'a', comparison_pool_pick_ids=['a27', 'b27', 'c27'],
             comparison_holder_team_id='a', comparison_counterparty_team_id='c'),
        swap('pool-1', 'a28', 'b28', 'a', season='2028', allocation_comparison=True,
             comparison_pool_pick_ids=['a28', 'b28', 'c28'], comparison_holder_team_id='a',
             comparison_counterparty_team_id='b'),
        swap('pool-2', 'b28', 'c28', 'b', season='2028', allocation_comparison=True,
             comparison_pool_pick_ids=['a28', 'b28', 'c28'], comparison_holder_team_id='b',
             comparison_counterparty_team_id='c'),
        {'id': 'prot-1', 'type': 'protected_pick', 'status': 'active', 'primary_pick_id': 'c28',
         'protected_range': {'from': 1, 'through': 4}, 'round': 1, 'receiver_team_id': 'a', 'sender_team_id': 'c'},
    ]
    return {'meta': {'active_season': '2026-27'}, 'teams': teams, 'draft_picks': picks, 'pick_obligations': terms}


def presentations(canonical):
    return {
        'nested': pp.nested_entitlements(canonical),
        'ranked': pp.ranked_pool_entitlements(canonical),
        'picks': [pp.pick_presentation(canonical, p) for p in canonical['draft_picks']],
        'swaps': [pp.swap_presentation(canonical, t) for t in canonical['pick_obligations'] if t['type'] == 'pick_swap'],
    }


class PickPresentationMemoTests(unittest.TestCase):
    def test_memo_matches_plain_results_and_hands_out_private_copies(self):
        plain = league()
        expected = presentations(plain)
        self.assertTrue(expected['nested'])  # the fixture exercises a real nested chain
        searched = {**league(), '_pick_presentation_memo': {}}
        self.assertEqual(presentations(searched), expected)
        again = presentations(searched)
        self.assertEqual(again, expected)
        again['nested'][next(iter(again['nested']))]['label'] = 'corrupted'
        again['picks'][0] and again['picks'][0].update(label='corrupted')
        self.assertEqual(presentations(searched), expected)

    def test_memo_follows_ownership_and_term_changes(self):
        searched = {**league(), '_pick_presentation_memo': {}}
        presentations(searched)
        for change in (lambda c: c['draft_picks'][1].update(current_owner_team_id='c'),
                       lambda c: c['pick_obligations'][0].update(current_rights_holder_team_id='b'),
                       lambda c: c['pick_obligations'][1].update(status='resolved'),
                       lambda c: c['pick_obligations'][0].update(nested_note='new field'),
                       lambda c: c['pick_obligations'].append(swap('extra', 'b28', 'c28', 'c', season='2028'))):
            change(searched)
            plain = {k: v for k, v in deepcopy(searched).items() if k != '_pick_presentation_memo'}
            self.assertEqual(presentations(searched), presentations(plain))

    def test_rank_annotation_on_the_asked_pick_is_part_of_the_key(self):
        searched = {**league(), '_pick_presentation_memo': {}}
        target = dict(searched['draft_picks'][3])
        first = pp.pick_presentation(searched, target)
        target['_ranked_entitlement'] = {'rank': 2, 'pool_size': 3}
        ranked = pp.pick_presentation(searched, target)
        self.assertEqual(ranked, pp._compute_pick_presentation(searched, target))
        self.assertEqual(ranked['asset_rank'], 2)
        self.assertNotIn('asset_rank', first or {})

    def test_trade_search_context_carries_its_own_memo(self):
        context = tx.trade_search_context({**league(), 'players': [], 'traits': [], 'contracts': []})
        self.assertEqual(context['_pick_presentation_memo'], {})


class CopyAndReviewTests(unittest.TestCase):
    def test_copy_plain_matches_deepcopy_including_shared_references(self):
        shared = {'x': [1, 2.5, None, True]}
        value = {'a': shared, 'b': [shared, (1, 'two')], 'c': {3: 'int key'}}
        copied = copy_plain(value)
        self.assertEqual(copied, deepcopy(value))
        self.assertIs(copied['a'], copied['b'][0])
        self.assertIsNot(copied['a'], shared)
        self.assertIsInstance(copied['b'][1], tuple)

        class Odd:  # pickle refuses local classes; the deepcopy fallback still applies
            pass
        odd = {'o': Odd()}
        self.assertIsInstance(copy_plain(odd)['o'], Odd)

    def test_review_inputs_compare_like_sorted_json(self):
        base = {'b': [1, 2], 'a': {'x': 1.0}}
        earlier = _Inputs([base, None])
        self.assertTrue(_Inputs([{'a': {'x': 1.0}, 'b': [1, 2]}, None]).same_as(earlier))  # reordered keys
        self.assertTrue(_Inputs([{'a': {'x': 1.0}, 'b': (1, 2)}, None]).same_as(earlier))  # tuple vs list
        self.assertFalse(_Inputs([{'a': {'x': 1.5}, 'b': [1, 2]}, None]).same_as(earlier))
        self.assertFalse(_Inputs([{'a': {'x': 1}, 'b': [1, 2]}, None]).same_as(earlier))  # 1 vs 1.0 in JSON

    def test_review_reuses_context_only_for_identical_inputs(self):
        source = {'meta': {'current_date': '2027-02-03'}, 'teams': [{'id': 'a', 'abbrev': 'A'}],
                  'players': [{'id': f'p{i}', 'team_id': 'a', 'age': 25, 'position': 'SG', 'name': str(i),
                               'minutes_projection': 25} for i in range(10)],
                  'traits': [], 'contracts': [], 'player_asset_valuations': [
                      {'player_id': f'p{i}', 'on_court_value': 80 - i, 'player_value': 80 - i} for i in range(10)]}
        review = MarketReview()
        try:
            from unittest.mock import patch
            with patch.object(tx, 'with_transaction_context', side_effect=lambda c, config=None: dict(c)), \
                    patch.object(tx, 'with_spatial_fit_context', side_effect=dict):
                first = review.prepare(source)
                self.assertIs(review.prepare(dict(reversed(list(source.items())))), first)
                source['players'][0]['age'] = 26
                self.assertIsNot(review.prepare(source), first)
            self.assertEqual(review.stats['context_hits'], 1)
            self.assertEqual(review.stats['invalidations'], 1)
        finally:
            review.close()


class RatingsCacheTests(unittest.TestCase):
    def test_trait_input_weights_returns_fresh_dicts(self):
        from nba_gm_data.trait_adapter import LEGACY_TRAITS, trait_input_weights
        first = trait_input_weights(LEGACY_TRAITS[0])
        first.clear()
        self.assertTrue(trait_input_weights(LEGACY_TRAITS[0]))
        with self.assertRaises(KeyError):
            trait_input_weights('not_a_trait')


if __name__ == '__main__':
    unittest.main()
