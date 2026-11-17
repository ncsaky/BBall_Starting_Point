"""Local protection pricing retains full compilation and exact reference values."""
from copy import deepcopy
from collections import Counter
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data import transactions as tx
from nba_gm_data.trade_pick_terms import compile_pick_rules
import test_trade_pick_terms as pick_fixtures


class ProtectionQuoteTests(unittest.TestCase):
    def fixture(self):
        source = pick_fixtures.TradePickTermsTests()
        source.setUp()
        return source

    def options(self, data, phase='neutral', **kwargs):
        return tx.ai_pick_protection_options(data, data['teams'][0], data['teams'][1], data['draft_picks'][0], phase, **kwargs)

    def test_validated_terms_only_preserves_terms_assets_and_default_public_view(self):
        fixture = self.fixture()
        full = compile_pick_rules(fixture.data, [fixture.protected], fixture.sides)
        plain = compile_pick_rules(fixture.data, [fixture.protected], fixture.sides, _materialize=False)
        self.assertIs(plain[0], fixture.data)
        self.assertEqual(plain[1:], full[1:])
        self.assertIn('a29', full[0]['locked_pick_assets'])
        for changes in ({'fallback_pick_ids':['b29']}, {'through':True}, {'fallback_pick_ids':[]}):
            with self.assertRaises(ValueError):
                compile_pick_rules(fixture.data, [{**fixture.protected, **changes}], fixture.sides, _materialize=False)

    def test_quote_values_terms_and_float_bits_equal_full_for_phases_dates_and_slots(self):
        for phase in ('neutral','contending','contending_with_future_upside','rebuilding','developing'):
            for season in ('2026-27','2028-29','2036-37'):
                for slot in (None,1,10,30):
                    fixture = self.fixture()
                    data = fixture.data
                    data['meta']['active_season'] = season
                    data['draft_picks'][0]['projected_pick_slot'] = slot
                    before = deepcopy(data)
                    expected = self.options(deepcopy(data),phase,_full_reference=True)
                    actual = self.options(data,phase)
                    self.assertEqual(actual,expected)
                    self.assertEqual([float(o['value']).hex() for o in actual],[float(o['value']).hex() for o in expected])
                    # Existing inventory lookup annotates the same active-season
                    # scalar on source records in both implementations.
                    reference = deepcopy(before)
                    self.options(reference,phase,_full_reference=True)
                    self.assertEqual(data,reference)

    def test_pricing_avoids_league_preview_and_uses_two_owned_picks(self):
        data = self.fixture().data
        data['_market_review_stats'] = Counter()
        annotate = tx.annotate_pick_obligation_context
        sizes = []
        def annotated(view):
            sizes.append(len(view['draft_picks']))
            return annotate(view)
        with patch.object(tx,'canonical_with_pending_pick_terms',side_effect=AssertionError('Unnecessary league preview')), \
             patch.object(tx,'annotate_pick_obligation_context',new=annotated):
            options = self.options(data)
        self.assertEqual(len(options),2)
        self.assertEqual(sizes,[2,2])
        self.assertEqual(data['_market_review_stats']['protection_quote_scoped'],2)
        options[0]['term']['fallback_pick_ids'].clear()
        self.assertEqual(len(self.options(data)[0]['term']['fallback_pick_ids']),1)
        self.assertNotIn('_obligations',data['draft_picks'][0])

    def test_connected_inactive_swap_nested_and_ranked_rights_keep_full_fallback(self):
        for extra in (
            {'id':'old','type':'protected_pick','status':'resolved','primary_pick_id':'a27'},
            {'id':'swap','type':'pick_swap','team_a_pick_id':'a27','team_b_pick_id':'b27','receiver_team_id':'b'},
            {'id':'pool','type':'pick_swap','comparison_pool_pick_ids':['a27','b27']},
            {'id':'nested','type':'pick_swap','nested_input':{'pick_id':'a27'}},
            {'id':'slots','type':'pick_swap','allocation_slot_pick_ids':['a29']},
        ):
            fixture = self.fixture()
            data = fixture.data
            _,_,terms = compile_pick_rules(data,[fixture.protected],fixture.sides,_materialize=False)
            data['pick_obligations'] = [extra]
            # Verify conservative dispatch separately, without inventing a valid
            # public offer from intentionally incomplete graph fixtures.
            with patch.object(tx,'canonical_with_pending_pick_terms',return_value={'full':True}) as full:
                self.assertEqual(tx._protection_quote_view(data,data['draft_picks'][0],terms),{'full':True})
                full.assert_called_once_with(data,terms)

    def test_invalid_and_changed_ownership_and_protection_are_always_recompiled(self):
        for change in ({'current_owner_team_id':'b'},{'overall_pick':4},{'_obligation_locked':True},
                       {'protection_summary':'top-4 protected'},{'_obligations':[{'id':'existing'}]}):
            data = self.fixture().data
            self.assertTrue(self.options(data))
            data['draft_picks'][0].update(change)
            self.assertEqual(self.options(data),self.options(deepcopy(data),_full_reference=True))
            self.assertEqual(self.options(data),[])

    def test_quote_views_release_without_gc_and_no_cache_or_source_owner_is_added(self):
        class Token: pass
        references = []
        original = tx.annotate_pick_obligation_context
        def annotated(view):
            token = Token()
            view['_quote_lifetime_probe'] = token
            references.append(weakref.ref(token))
            return original(view)
        data = self.fixture().data
        keys = set(data)
        with patch.object(tx,'annotate_pick_obligation_context',new=annotated):
            for _ in range(4): self.options(data)
        self.assertEqual(len(references),8)
        self.assertTrue(all(ref() is None for ref in references))
        self.assertEqual(set(data),keys)


if __name__=='__main__': unittest.main()
