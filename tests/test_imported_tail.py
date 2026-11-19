from copy import deepcopy
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data.health import add_game_fatigue
from nba_gm_data.schema import TraitValue
from nba_gm_data.traits import build_traits_for_player, inferred_stamina, repair_preserved_stamina
from nba_gm_data.ingest import build_universe
from nba_gm_data.save import canonical_with_save, create_league_save, load_save, write_save
from nba_gm_data.schema import to_plain


class ImportedTailArithmeticTests(unittest.TestCase):
    def trait(self, **changes):
        row = dict(id="t", player_id="p", trait_key="stamina_cardio", label="Stamina", value=30,
            confidence=.6, source_kind="inferred", source_ids=[], last_verified="2026-07-28", notes="",
            components={"2026_roster_refresh":{"preserved_value":30},"components":[60,30,0]})
        return TraitValue(**{**row, **changes})

    def test_bonus_is_additive_missing_workload_remains_unknown_and_values_bounded(self):
        self.assertEqual(inferred_stamina([60,30],0),45)
        self.assertEqual(inferred_stamina([60,None],8),68)
        self.assertIsNone(inferred_stamina([None,None],8))
        self.assertIsNone(inferred_stamina([float('nan'),float('inf')],0))
        self.assertEqual(inferred_stamina([99,99],8),100)

    def test_builder_default_is_corrected_and_legacy_path_is_explicit(self):
        row = {"minutes":10,"2025minutes":100,"primaryOffRole":"movement shooter"}
        percentiles = {"minutes":{0:60},"2025minutes":{0:30}}
        before = deepcopy(row)
        values = []
        for legacy in (False,True):
            traits = build_traits_for_player(row,0,"p",percentiles,legacy_stamina=legacy)
            values.append(next(t.value for t in traits if t.trait_key=="stamina_cardio"))
        self.assertEqual(values[0],53)
        self.assertAlmostEqual(values[1],98/3,places=2)
        self.assertEqual(row,before)

    def test_preserved_repair_is_bounded_idempotent_and_does_not_mutate(self):
        trait = self.trait()
        original = deepcopy(trait)
        result,report = repair_preserved_stamina([trait])
        self.assertEqual(result[0].value,45)
        self.assertEqual(report['adjusted_trait_count'],1)
        self.assertEqual(trait,original)
        self.assertEqual(repair_preserved_stamina(result)[0],result)

    def test_reviewed_and_nonreconciling_profiles_are_preserved(self):
        for key in ('manual_calibration','roster_alignment','imported_rookie_prior','league_trait_rating_calibration'):
            trait = self.trait()
            trait = replace(trait,components={**trait.components,key:{}})
            self.assertEqual(repair_preserved_stamina([trait])[0],[trait])
        for trait in (self.trait(value=50),self.trait(components={"components":[60,30,0]}),
                      self.trait(trait_key='shooting_range')):
            self.assertEqual(repair_preserved_stamina([trait])[0],[trait])

    def test_fatigue_gain_changes_without_changing_health_formula_or_injury_state(self):
        states = [{"fatigue":10,"availability_status":"active"} for _ in range(2)]
        for state,stamina in zip(states,(30,45)):
            add_game_fatigue(state,{},24,stamina,1,{}, {})
        self.assertGreater(states[0]['fatigue'],states[1]['fatigue'])
        self.assertTrue(all(s['availability_status']=='active' for s in states))


class ImportedTailBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        with gzip.open(cls.root/'data/canonical/baselines/2026-10-23-forward-tuning-v5.json.gz','rt') as handle:
            cls.old = json.load(handle)
        with gzip.open(cls.root/'data/canonical/baselines/2026-10-26-imported-tail-v6.json.gz','rt') as handle:
            cls.new = json.load(handle)

    def test_only_researched_profiles_or_proven_stamina_arithmetic_change_values(self):
        from verify_imported_tail import verify_scope
        scope = verify_scope(self.old,self.new)
        self.assertGreater(scope['changed_trait_count'],29)
        self.assertTrue(scope['initial_medicals_finances_identities_unchanged'])

    def test_v5_earned_growth_trades_and_contracts_survive_v6_entry_and_reload(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'career.json'
            saved = create_league_save(self.root,deepcopy(self.old),'GSW',path,seed=17,ratings_model='legacy_traits')
            player = next(p for p in self.old['players'] if p['name']=='Spencer Jones')
            pid = player['id']
            saved['development_trait_totals'] = {pid:{'passing_reads':2.5}}
            saved['roster_overrides'][pid] = 'team_gsw'
            saved['contract_overrides'][pid] = {'team_id':'team_gsw','seasons':[{'season':'2026-27','salary':3200000}]}
            write_save(path,saved)
            fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
            before = canonical_with_save(deepcopy(self.old),load_save(path))
            after = canonical_with_save(deepcopy(self.new),load_save(path))
            for key in ('players','traits','contracts','draft_picks','player_health_profiles','player_health_states','injury_events'):
                self.assertEqual(before[key],after[key],key)
            value = next(t['value'] for t in after['traits'] if t['player_id']==pid and t['trait_key']=='passing_reads')
            old = next(t['value'] for t in self.old['traits'] if t['player_id']==pid and t['trait_key']=='passing_reads')
            self.assertEqual(value,old+2.5)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),fingerprint)


if __name__ == '__main__':
    unittest.main()
