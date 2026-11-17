from copy import deepcopy
from dataclasses import replace
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data.ingest import build_universe
from nba_gm_data.rotation_profile_calibration import (
    MARKER, RESTORABLE_KEYS, calibrate_rotation_profiles, demonstrated_rotation,
)
from nba_gm_data.save import canonical_with_save, create_league_save, load_save, write_save
from nba_gm_data.schema import Player, TraitValue, to_plain

ROOT = Path(__file__).resolve().parents[1]


class RotationProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(ROOT/'data/canonical/baselines/2026-10-26-imported-skills-v7.json.gz','rt') as handle:
            cls.old = json.load(handle)
        cls.player = Player(**next(p for p in cls.old['players'] if p['name']=='Ryan Nembhard'))

    def fixture(self):
        row = {'season':'2025-26', 'minutes':1600, 'games':60,
               'source_url':f'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{self.player.espn_player_id}/stats'}
        data = {'players':{self.player.espn_player_id:{'espn_player_id':self.player.espn_player_id,'seasons':[row]}}}
        ts = []
        for key in sorted(RESTORABLE_KEYS | {'stamina_cardio','defensive_effort','foot_speed_lateral_agility'}):
            value = 20 if key=='stamina_cardio' else 30
            c = {'components':[60,50,None], 'playtype_count':5,
                 '2026_roster_refresh':{'preserved_value':value},
                 'league_trait_rating_calibration':{'previous_value':60,'final_value':value,'csv_rank':400}}
            ts.append(TraitValue(id=key, player_id=self.player.id,trait_key=key,label=key,value=value,
                confidence=.7,source_kind='inferred',source_ids=[],last_verified='2026-07-28',notes='',components=c))
        return ts, data

    def test_bounded_restoration_preserves_defense_and_physicals_without_mutating(self):
        ts,data = self.fixture()
        before = to_plain(ts),deepcopy(data)
        after,report = calibrate_rotation_profiles([self.player],ts,data,2026)
        self.assertEqual(before,(to_plain(ts),data))
        self.assertEqual(report['adjusted_player_count'],1)
        for a,b in zip(ts,after):
            if a.trait_key in RESTORABLE_KEYS:
                self.assertGreater(b.value,a.value)
                self.assertLessEqual(b.value-a.value,20.000001)
            elif a.trait_key=='stamina_cardio':
                self.assertGreater(b.value,a.value)
                self.assertLessEqual(b.value-a.value,30.000001)
            else:
                self.assertEqual(a,b)
        self.assertEqual(calibrate_rotation_profiles([self.player],after,data,2026)[0],after)

    def test_an_inflated_prior_strength_can_be_lowered_but_not_past_original(self):
        ts,data = self.fixture()
        index = next(i for i,t in enumerate(ts) if t.trait_key=='shooting_range')
        c = deepcopy(ts[index].components)
        c['league_trait_rating_calibration']['previous_value'] = 10
        ts[index] = replace(ts[index],components=c)
        after,_ = calibrate_rotation_profiles([self.player],ts,data,2026)
        self.assertLess(after[index].value,30)
        self.assertGreaterEqual(after[index].value,10)

    def test_manual_rookie_current_class_unproven_and_injured_only_samples_are_protected(self):
        ts,data = self.fixture()
        for marker in ('manual_calibration','imported_rookie_prior'):
            marked = [replace(ts[0],components={**ts[0].components,marker:{}}),*ts[1:]]
            self.assertEqual(calibrate_rotation_profiles([self.player],marked,data,2026)[0],marked)
        rookie = replace(self.player,draft_year=2026)
        self.assertEqual(calibrate_rotation_profiles([rookie],ts,data,2026)[0],ts)
        row = data['players'][self.player.espn_player_id]['seasons'][0]
        for edits in ({'games':20,'minutes':600},{'games':60,'minutes':600},{'season':'2026-27'},
                      {'season':'2024-25'},{'minutes':float('inf')},{'source_url':'college'}):
            trial = deepcopy(data)
            trial['players'][self.player.espn_player_id]['seasons'][0] = {**row,**edits}
            self.assertIsNone(demonstrated_rotation(self.player,trial['players'],2026))
            self.assertEqual(calibrate_rotation_profiles([self.player],ts,trial,2026)[0],ts)

    def test_unreconciled_missing_and_unsupported_source_records_do_not_get_restored(self):
        ts,data = self.fixture()
        for change in ({'final_value':25},{'previous_value':None},{'csv_rank':100},{'previous_value':101}):
            bad = []
            for t in ts:
                c = deepcopy(t.components)
                c['league_trait_rating_calibration'].update(change)
                bad.append(replace(t,components=c))
            after,_ = calibrate_rotation_profiles([self.player],bad,data,2026)
            self.assertTrue(all(a.value==b.value for a,b in zip(bad,after) if a.trait_key!='stamina_cardio'))
        bad = [replace(t,components={**t.components,'components':[None,None,None], 'playtype_count':0}) for t in ts]
        after,_ = calibrate_rotation_profiles([self.player],bad,data,2026)
        self.assertTrue(all(a.value==b.value for a,b in zip(bad,after) if a.trait_key!='stamina_cardio'))

    def test_conditioning_respects_age_and_does_not_reduce_existing_stamina(self):
        ts,data = self.fixture()
        stamina = [t for t in ts if t.trait_key=='stamina_cardio']
        young = calibrate_rotation_profiles([replace(self.player,age=23)],stamina,data,2026)[0][0]
        old = calibrate_rotation_profiles([replace(self.player,age=38)],stamina,data,2026)[0][0]
        self.assertGreater(young.value,old.value)
        strong = [replace(stamina[0],value=65)]
        self.assertEqual(calibrate_rotation_profiles([self.player],strong,data,2026)[0],strong)


class RotationProfileBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(ROOT/'data/canonical/baselines/2026-10-26-imported-skills-v7.json.gz','rt') as handle:
            cls.old = json.load(handle)
        cls.new = to_plain(build_universe(ROOT))

    def test_medicals_finances_players_and_prospects_are_identical(self):
        for key in ('players','contracts','draft_picks','player_health_profiles','player_health_states','injury_events',
                    'draft_classes','draft_prospects','draft_prospect_traits'):
            self.assertEqual(self.old[key],self.new[key],key)

    def test_all_changes_are_reported_or_researched_and_prior_reviews_are_preserved(self):
        old = {(t['player_id'],t['trait_key']):t for t in self.old['traits']}
        new = {(t['player_id'],t['trait_key']):t for t in self.new['traits']}
        names = {p['id']:p['name'] for p in self.old['players']}
        report = self.new['meta']['rotation_profile_report']
        changed = {k for k in old if old[k]['value']!=new[k]['value']}
        automatic = {(p['player_id'],k) for p in report['players'] for k in p['trait_changes']}
        for key in changed-automatic:
            self.assertIn(names[key[0]],{'Amir Coffey','Deandre Ayton'})
            self.assertTrue(new[key]['components']['manual_calibration']['evidence_urls'])
        for key,t in old.items():
            if 'manual_calibration' in t['components']:
                self.assertEqual(t['value'],new[key]['value'],key)
        self.assertGreater(report['adjusted_player_count'],40)
        # NBA participation never implies shooting ability for a nonshooting big.
        for name in ('Jericho Sims','Deandre Ayton'):
            pid = next(p['id'] for p in self.old['players'] if p['name']==name)
            for key in ('shooting_range','release_speed'):
                self.assertEqual(old[pid,key]['value'],new[pid,key]['value'])

    def test_existing_v7_career_keeps_ratings_growth_and_roster_decisions(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'save.json'
            saved = create_league_save(ROOT,deepcopy(self.old),'GSW',path,seed=29)
            pid = next(p['id'] for p in self.old['players'] if p['name']=='Ryan Nembhard')
            saved['development_trait_totals'] = {pid:{'passing_reads':3}}
            saved['roster_overrides'][pid] = 'team_gsw'
            write_save(path,saved)
            before = canonical_with_save(deepcopy(self.old),load_save(path))
            after = canonical_with_save(deepcopy(self.new),load_save(path))
            for key in ('players','traits','contracts','draft_picks','player_health_states'):
                self.assertEqual(before[key],after[key],key)

    def test_build_repeats_exactly(self):
        self.assertEqual(self.new,to_plain(build_universe(ROOT)))


if __name__=='__main__':
    unittest.main()
