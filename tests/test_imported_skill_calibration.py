from copy import deepcopy
from dataclasses import replace
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data.imported_skill_calibration import (
    MARKER, calibrate_imported_skills, observed_skill, recent_nba_sample,
)
from nba_gm_data.ingest import build_universe
from nba_gm_data.save import canonical_with_save, create_league_save, load_save, write_save
from nba_gm_data.schema import Player, TraitValue, to_plain
from nba_gm_data.sim import player_feature_vector

ROOT = Path(__file__).resolve().parents[1]


class ImportedSkillEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(ROOT/'data/canonical/baselines/2026-10-26-imported-tail-v6.json.gz', 'rt') as handle:
            cls.old = json.load(handle)
        cls.player = Player(**next(p for p in cls.old['players'] if p['name'] == 'Tre Jones'))

    def row(self, **changes):
        return {**dict(season='2025-26', minutes=1600, games=60, assists=320, turnovers=80,
                       fg3a=200, fg3m=80, source_url=f'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{self.player.espn_player_id}/stats'), **changes}

    def trait(self, key='passing_reads', value=25, **changes):
        return TraitValue(**{**dict(id='t', player_id=self.player.id, trait_key=key, label=key,
            value=value, confidence=.7, source_kind='inferred', source_ids=[], last_verified='2026-07-28',
            notes='', components={}), **changes})

    def data(self, rows):
        return {'players': {self.player.espn_player_id: {'espn_player_id': self.player.espn_player_id, 'seasons': rows}}}

    def test_only_matching_nba_completed_seasons_and_valid_samples_count(self):
        rows = [self.row(), self.row(season='2026-27'), self.row(source_url='college'),
                self.row(minutes=float('inf')), self.row(minutes=-1), self.row(games=1), self.row(season='2023-24')]
        self.assertEqual(recent_nba_sample(self.player, self.data(rows)['players'], 2026), [rows[0]])
        bad = self.data([self.row()])
        bad['players'][self.player.espn_player_id]['espn_player_id'] = 'other'
        self.assertEqual(recent_nba_sample(self.player, bad['players'], 2026), [])

    def test_missing_stats_are_not_zero_and_absent_latest_is_downweighted(self):
        self.assertIsNone(observed_skill([self.row(turnovers=None)], 'passing_reads', 2026))
        self.assertIsNone(observed_skill([self.row(assists=float('nan'))], 'passing_reads', 2026))
        self.assertIsNone(observed_skill([self.row(season='2024-25')], 'passing_reads', 2026))
        sample = observed_skill([self.row(minutes=2200, season='2024-25')], 'passing_reads', 2026)
        self.assertEqual(sample['weighted_minutes'], 1100)

    def test_nonshooters_poor_shooters_tiny_samples_and_low_assist_rates_not_promoted(self):
        for changes in ({'fg3a': 20, 'fg3m': 8}, {'fg3m': 40}, {'fg3m': 250}, {'minutes': 200}, {'fg3a': None}):
            self.assertIsNone(observed_skill([self.row(**changes)], 'shooting_range', 2026))
        self.assertIsNone(observed_skill([self.row(assists=10)], 'passing_reads', 2026))

    def test_correction_is_bounded_idempotent_and_keeps_other_traits_and_inputs(self):
        ts = [self.trait(), self.trait('shooting_range'), self.trait('rim_deterrence', 5)]
        data = self.data([self.row()])
        before = to_plain(ts), deepcopy(data)
        after, report = calibrate_imported_skills([self.player], ts, data, 2026)
        self.assertEqual((to_plain(ts), data), before)
        self.assertEqual(after[-1], ts[-1])
        self.assertEqual(report['adjusted_trait_count'], 2)
        for a, b in zip(ts[:2], after[:2]):
            self.assertGreater(b.value, a.value)
            self.assertLessEqual(b.value-a.value, 10)
            self.assertIn(MARKER, b.components)
        self.assertEqual(calibrate_imported_skills([self.player], after, data, 2026)[0], after)

    def test_current_rookies_manual_profiles_and_strong_skills_are_protected(self):
        for player, ts in ((replace(self.player, draft_year=2026), [self.trait()]),
                           (self.player, [self.trait(components={'manual_calibration': {}}), self.trait('shooting_range')]),
                           (self.player, [self.trait(components={'imported_rookie_prior': {}})]),
                           (self.player, [self.trait(value=90)])):
            self.assertEqual(calibrate_imported_skills([player], ts, self.data([self.row()]), 2026)[0], ts)

    def test_sparse_proxy_shrinks_both_directions_but_reviewed_and_empty_inputs_do_not(self):
        for value, direction in ((5, 1), (90, -1)):
            trait = self.trait('screen_navigation', value, components={'components': [None, None, 30, None]})
            after, _ = calibrate_imported_skills([self.player], [trait], self.data([self.row()]), 2026)
            self.assertGreater((after[0].value-value)*direction, 0)
            self.assertLessEqual(abs(after[0].value-value), 8)
        for components in ({'components': [None, None]}, {'components': [30, 40]},
                           {'components': [None, 30, None], 'league_trait_rating_calibration': {}},
                           {'components': [None, 30, None], 'roster_alignment': {}}):
            trait = self.trait('scheme_iq', 5, components=components)
            self.assertEqual(calibrate_imported_skills([self.player], [trait], self.data([self.row()]), 2026)[0], [trait])


class ImportedSkillBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(ROOT/'data/canonical/baselines/2026-10-26-imported-tail-v6.json.gz', 'rt') as handle:
            cls.old = json.load(handle)
        with gzip.open(ROOT/'data/canonical/baselines/2026-10-26-imported-skills-v7.json.gz', 'rt') as handle:
            cls.new = json.load(handle)

    def test_scope_matches_report_and_preserves_medicals_contracts_and_all_reviewed_profiles(self):
        old = {(t['player_id'], t['trait_key']): t for t in self.old['traits']}
        new = {(t['player_id'], t['trait_key']): t for t in self.new['traits']}
        changes = {k for k in old if old[k]['value'] != new[k]['value']}
        report = self.new['meta']['imported_skill_report']
        self.assertEqual(report['examined_players'], len(self.new['players']))
        self.assertEqual(changes, {(r['player_id'], k) for r in report['players'] for k in r['trait_changes']})
        self.assertGreaterEqual(report['adjusted_player_count'], 15)
        for key in ('players', 'contracts', 'draft_picks', 'player_health_profiles', 'player_health_states', 'injury_events', 'draft_prospect_traits'):
            self.assertEqual(self.old[key], self.new[key], key)
        protected = {pid for (pid, _), t in old.items() if 'manual_calibration' in t['components'] or 'imported_rookie_prior' in t['components']}
        self.assertFalse(protected & {pid for pid, _ in changes})
        for key in changes:
            self.assertIn(MARKER, new[key]['components'])
            self.assertLessEqual(abs(new[key]['value']-old[key]['value']), 10.000001)

    def test_v6_save_with_development_and_rotation_overrides_is_not_rerated(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'save.json'
            saved = create_league_save(ROOT, deepcopy(self.old), 'GSW', path, seed=29)
            player = next(p for p in self.old['players'] if p['name'] == 'Tre Jones')
            saved['development_trait_totals'] = {player['id']: {'passing_reads': 2.5}}
            saved['rotation_overrides'] = {player['id']: 27}
            write_save(path, saved)
            before = canonical_with_save(deepcopy(self.old), load_save(path))
            after = canonical_with_save(deepcopy(self.new), load_save(path))
            for key in ('players', 'traits', 'contracts', 'draft_picks', 'player_health_states'):
                self.assertEqual(before[key], after[key], key)

    def test_build_is_deterministic(self):
        self.assertEqual(to_plain(build_universe(ROOT)), to_plain(build_universe(ROOT)))

    def test_skill_changes_reach_simulation_features_not_only_display_overalls(self):
        for name, feature in (('Amir Coffey', 'spacing'), ('Jamal Shead', 'passing'), ('Georges Niang', 'defensive_events')):
            player = next(p for p in self.new['players'] if p['name'] == name)
            old = player_feature_vector(self.old, player).features
            new = player_feature_vector(self.new, player).features
            self.assertGreater(new[feature], old[feature], name)
            self.assertGreater(new['impact'], old['impact'], name)


if __name__ == '__main__':
    unittest.main()
