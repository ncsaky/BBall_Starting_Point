"""Offline BBI import, identity, provenance, and additive estimator contracts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from nba_gm_data.bbi_import import (
    CACHE_PATH, PlayerMatcher, import_capture, iter_records, normalize_season, read_capture,
)
from nba_gm_data.input_estimator import (
    BBI_METRIC_INPUTS, CAREER_PATH, InputEstimator, load_bbi_evidence,
    SKILL_PATH, STATS_PATH, UNIVERSE_PATH, SHOT_ZONE_PATH, canonical_json,
)

ROOT = Path(__file__).resolve().parents[1]
PLAYERS = [dict(id='player_a', name='Luka Dončić', espn_player_id='3945274', position='PG'),
           dict(id='player_b', name='Alex Caruso', espn_player_id='2991350', position='SG')]
METRIC = 'Ball Screen Navigation'


def metadata(**updates):
    # Test-only model of an observed export; no claim that paid fields were acquired.
    result = dict(source_url='https://www.bball-index.com/skills-application/',
        retrieved_at_utc='2026-11-17T02:00:00Z', provider_as_of=None,
        season='2025-26', season_type='regular', dataset_kind='observed',
        row_scope='season_total', filters={'minimum_minutes': 0},
        capture_method='synthetic test fixture', displayed_rows=1,
        percentile_population='season_all_players', percentile_scale='0_100',
        metrics={METRIC: dict(evidence_kind='provider_model', units='provider model score',
                            sample_unit='possessions', percentile_higher_is_better=True)})
    result.update(updates)
    return result


class BBIImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.cache = self.root / 'data/research/bbi'

    def capture(self, text, suffix='.csv', meta=None):
        source = self.root / ('capture' + suffix); source.write_text(text)
        cache = import_capture(source, meta or metadata(), PLAYERS, self.cache)
        return source, dict(cache, records=list(iter_records(cache, self.cache)))

    def observation(self, **updates):
        row = dict(Player='Alex Caruso', Season='2025-26', Minutes=1000,
                   metric_name=METRIC, raw_value=1.5, percentile=95, grade='A', sample_size=1000)
        row.update(updates)
        return row

    def write_observation(self, row=None, meta=None):
        return self.capture(json.dumps([row or self.observation()]), '.json', meta)

    def test_wide_csv_separates_representations_and_preserves_bytes(self):
        source, cache = self.capture('Player,Season,Team,Minutes,Ball Screen Navigation (Value),Ball Screen Navigation (Percentile),Ball Screen Navigation (Grade),Ball Screen Navigation (N)\nAlex Caruso,2025-26,TOT,1500,1.5,95,A,800\n')
        record = cache['records'][0]; batch = next(iter(cache['batches'].values()))
        self.assertEqual('player_b', record['canonical_player_id'])
        self.assertEqual((1.5, 95, 'A', 800), tuple(record[k] for k in ('raw_value','percentile','grade','sample_size')))
        self.assertEqual('possessions', record['sample_unit'])
        self.assertEqual('provider_model', record['evidence_kind'])
        self.assertEqual(source.read_bytes(), (self.cache / batch['raw_file']).read_bytes())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), batch['sha256'])
        self.assertEqual('2026-11-17T02:00:00Z', record['retrieved_at_utc'])
        self.assertIsNone(record['provider_as_of'])
        self.assertEqual('complete', batch['completeness'])
        coverage=cache['coverage'][0]
        self.assertEqual(1,coverage['percentiles_present'])
        self.assertEqual(1,coverage['sample_sizes_present'])
        self.assertEqual(1,coverage['matched_records'])

    def test_public_rendered_demo_end_to_end(self):
        capture = ROOT / 'data/research/bbi/captures/skills-demo-defense.html'
        meta = json.loads(capture.with_suffix('.metadata.json').read_text())
        players = json.loads((ROOT / UNIVERSE_PATH).read_text())['players']
        cache = import_capture(capture, meta, players, self.cache)
        cache['records'] = list(iter_records(cache, self.cache))
        batch = next(iter(cache['batches'].values()))
        self.assertEqual(40, batch['captured_rows'])
        self.assertEqual(280, len(cache['records']))
        davis = next(r for r in cache['records'] if r['player_name_raw'] == 'Anthony Davis' and r['metric_name'] == METRIC)
        self.assertEqual(-.5, davis['raw_value'])
        self.assertEqual('2019-20', davis['season'])
        self.assertIsNone(davis['sample_size'])
        self.assertEqual(25, len(batch['unmatched_rows']))  # historical players outside current universe
        self.assertEqual({}, load_bbi_evidence(self.root))

    def test_json_rows_columns_and_tsv(self):
        for suffix, text in [('.json', json.dumps(dict(columns=['Player','Season',METRIC], rows=[['Alex Caruso','2025-26','0']]))),
                             ('.tsv', f'Player\tSeason\t{METRIC}\nAlex Caruso\t2025-26\t0\n')]:
            with self.subTest(suffix=suffix):
                _, cache = self.capture(text, suffix)
                self.assertEqual(0, cache['records'][-1]['raw_value'])

    def test_blank_does_not_become_zero_or_a_sample(self):
        _, cache = self.write_observation(self.observation(raw_value='',percentile='',grade='',sample_size=''))
        row = cache['records'][0]
        self.assertIsNone(row['sample_size']); self.assertIsNone(row['percentile'])
        self.assertEqual('not_shown_or_unavailable',row['missing_reason'])
        self.assertEqual({},load_bbi_evidence(self.root))

    def test_idempotent_and_conflicts_retained(self):
        source, cache = self.write_observation()
        meta = metadata()
        repeated=import_capture(source,meta,PLAYERS,self.cache)
        self.assertEqual(cache['records'],list(iter_records(repeated,self.cache)))
        self.assertEqual(cache['batches'],repeated['batches'])
        meta['retrieved_at_utc'] = '2026-11-17T03:00:00Z'
        newer = import_capture(source,meta,PLAYERS,self.cache)
        self.assertEqual(2,len(list(iter_records(newer,self.cache)))); self.assertEqual(1,len(newer['duplicate_groups']))
        evidence = load_bbi_evidence(self.root)['player_b']
        self.assertEqual(1,len(evidence))

    def test_matching_and_unmatched_audit(self):
        matcher = PlayerMatcher(PLAYERS)
        self.assertEqual(('player_a','unique_exact_normalized_name'),matcher.match({'Player':'Luka Doncic'}))
        self.assertEqual(('player_a','espn_id'),matcher.match({'Player':'Luka D.','ESPN ID':'3945274'}))
        self.assertEqual((None,'unknown_or_ambiguous_espn_id'),matcher.match({'Player':'Alex Caruso','ESPN ID':'wrong'}))
        self.assertEqual((None,'conflicting_name_and_id'),matcher.match({'Player':'Alex Caruso','ESPN ID':'3945274'}))
        self.assertIsNone(matcher.match({'Player':'Luka Doncic Jr.'})[0])
        duplicated = PlayerMatcher([*PLAYERS,dict(id='other',name='Alex Caruso')])
        self.assertEqual((None,'ambiguous_name'),duplicated.match({'Player':'Alex Caruso'}))
        self.assertEqual(('player_a','reviewed_alias'),PlayerMatcher(PLAYERS,{'Luka D.':'player_a'}).match({'Player':'Luka D.'}))
        _, cache = self.write_observation(self.observation(Player='Not in our league'))
        self.assertEqual('unmatched_name',next(iter(cache['batches'].values()))['unmatched_rows'][0]['reason'])
        self.assertIsNone(cache['records'][0]['canonical_player_id'])

    def test_year_convention_explicit(self):
        self.assertEqual('2025-26',normalize_season('2026','ending'))
        self.assertEqual('2025-26',normalize_season('2025–2026'))
        for bad in ('2026','2025-27',None):
            with self.assertRaises(ValueError):normalize_season(bad)

    def test_loading_shell_and_ragged_tables_rejected(self):
        for text,suffix in [('<script>secretData=[]</script><h3>Please wait</h3>','.html'),
                            ('Player,Season\nAlex Caruso,2025-26,extra\n','.csv'),
                            ('Player,Player\na,b\n','.csv')]:
            with self.subTest(text=text),self.assertRaises(ValueError):self.capture(text,suffix)

    def test_multiple_html_tables_require_selection(self):
        table='<table><thead><tr><th>Player</th><th>Season</th><th>X</th></tr><tr><td><input></td><td></td><td></td></tr></thead><tbody><tr><td>Alex Caruso</td><td>2025-26</td><td>1</td></tr></tbody></table>'
        with self.assertRaises(ValueError):self.capture(table+table,'.html')
        _,cache=self.capture(table+table,'.html',metadata(table_index=1))
        self.assertEqual(1,len(cache['records']))

    def test_incomplete_capture_not_estimator_evidence(self):
        _,cache=self.write_observation(meta=metadata(displayed_rows=500))
        self.assertEqual('partial',next(iter(cache['batches'].values()))['completeness'])
        self.assertEqual({},load_bbi_evidence(self.root))

    def test_composites_roles_and_rate_counts_do_not_grant_raw_skills(self):
        _,cache=self.capture('Player,Season,LEBRON,Offensive Role,Cuts Per 75 Possessions,Movement Speed Rating\nAlex Caruso,2025-26,5,Creator,2,1.4\n')
        lebron=next(r for r in cache['records'] if r['metric_name']=='LEBRON')
        self.assertEqual('validation_composite',lebron['evidence_kind'])
        self.assertEqual({},load_bbi_evidence(self.root))
        self.assertTrue(all(i.startswith('S') for ids in BBI_METRIC_INPUTS.values() for i in ids))

    def test_unclear_units_not_inferred_or_percent_rescaled(self):
        _,cache=self.write_observation(self.observation(raw_value='43.2%',percentile='.95',percentile_scale='0_1'))
        self.assertEqual(43.2,cache['records'][0]['raw_value'])
        self.assertEqual(.95,cache['records'][0]['percentile'])
        self.assertEqual('43.2%',cache['records'][0]['source_text']['raw_value'])
        self.assertAlmostEqual(67.90744675497561,load_bbi_evidence(self.root)['player_b'][0].value['grade'])

    def test_explicit_column_map_and_value_plus(self):
        _,cache=self.capture('Player,nav_pct,nav_plus\nAlex Caruso,95,1.2\n',meta=metadata(column_map={'nav_pct':{'metric':METRIC,'representation':'percentile'},'nav_plus':{'metric':METRIC,'representation':'value_plus'}}))
        self.assertEqual(95,cache['records'][0]['percentile'])
        self.assertEqual('1.2',cache['records'][0]['value_plus'])

    def test_negative_sample_bad_percentile_and_missing_provenance_rejected(self):
        for row,meta in [(self.observation(sample_size=-1),metadata()),
                         (self.observation(percentile=105),metadata()),
                         (self.observation(),metadata(retrieved_at_utc='2026-11-16T22:00:00'))]:
            with self.subTest(row=row,meta=meta),self.assertRaises(ValueError):self.write_observation(row,meta)
        meta=metadata();del meta['filters']
        with self.assertRaises(ValueError):self.write_observation(meta=meta)

    def test_sample_size_weighting_and_minutes_fallback(self):
        self.write_observation(self.observation(sample_size=10))
        small=load_bbi_evidence(self.root)['player_b'][0]
        self.write_observation(self.observation(sample_size=2000))
        large=load_bbi_evidence(self.root)['player_b'][0]
        weight=lambda obs:obs.reliability*obs.n/(obs.n+obs.prior_exposure)
        self.assertGreater(weight(large),weight(small))
        self.assertEqual('possessions',large.exposure_unit)
        self.write_observation(self.observation(sample_size=None))
        # New root isolates fallback from the stronger observation above.
        other=self.root/'other';other.mkdir();source=other/'row.json';source.write_text(json.dumps([self.observation(sample_size=None)]))
        import_capture(source,metadata(),PLAYERS,other/'data/research/bbi')
        obs=load_bbi_evidence(other)['player_b'][0]
        self.assertEqual('minutes',obs.exposure_unit);self.assertEqual(1000,obs.n)
        self.assertEqual(.2,obs.reliability)

    def test_unsafe_populations_kinds_seasons_and_zero_exposure_excluded(self):
        cases=[({'dataset_kind':'historical_demo'},{}),({'dataset_kind':'synthetic'},{}),
               ({'dataset_kind':'forecast'},{}),({'season_type':'playoffs'},{}),
               ({'percentile_population':'custom_subset'},{}),({'row_scope':'team_stint'},{}),
               ({},{'Season':'2026-27'}),({},{'Season':'2019-20'}),({},{'sample_size':0}),
               ({},{'sample_size':None,'Minutes':0})]
        for index,(meta,row) in enumerate(cases):
            with self.subTest(meta=meta,row=row):
                root=self.root/str(index);root.mkdir();p=root/'row.json';p.write_text(json.dumps([self.observation(**row)]))
                import_capture(p,metadata(**meta),PLAYERS,root/'data/research/bbi')
                self.assertEqual({},load_bbi_evidence(root))

    def test_unknown_percentile_direction_is_not_guessed(self):
        meta=metadata();del meta['metrics'][METRIC]['percentile_higher_is_better']
        self.write_observation(meta=meta);self.assertEqual({},load_bbi_evidence(self.root))

    def test_raw_only_and_letter_grade_only_are_preserved_not_rescaled(self):
        self.write_observation(self.observation(percentile=None,grade='A+'))
        self.assertEqual({},load_bbi_evidence(self.root))
        cache=json.loads((self.cache/'normalized.json').read_text());self.assertEqual('A+',next(iter_records(cache,self.cache))['grade'])

    def test_correlated_metrics_and_representation_duplicates_count_once(self):
        meta=metadata(displayed_rows=2);meta['metrics']['Off-Ball Chaser Defense']=deepcopy(meta['metrics'][METRIC])
        self.capture(json.dumps([self.observation(),self.observation(metric_name='Off-Ball Chaser Defense')]),'.json',meta)
        evidence=load_bbi_evidence(self.root)['player_b'];self.assertEqual(1,len(evidence))
        model=InputEstimator(additional_evidence={'player_b':evidence});doc=model.estimate_player_inputs(PLAYERS[1]).to_dict()
        self.assertEqual(94,len(doc['inputs']))
        bbi=[r for r in doc['inputs']['S35']['evidence'] if 'bbi' in r['source']]
        self.assertEqual(1,len(bbi));self.assertIn('not measured raw technique',bbi[0]['method'])

    def test_newest_season_and_explicit_percentile_direction(self):
        self.write_observation(self.observation(Season='2024-25',sample_size=10000,percentile=5))
        self.write_observation(self.observation(Season='2025-26',sample_size=10,percentile=95))
        obs=load_bbi_evidence(self.root)['player_b'][0]
        self.assertIn('season=2025-26',obs.method)
        self.assertGreater(obs.value['grade'],50)
        meta=metadata();meta['metrics'][METRIC]['percentile_higher_is_better']=False
        other=self.root/'inverted';other.mkdir();source=other/'row.json';source.write_text(json.dumps([self.observation()]))
        import_capture(source,meta,PLAYERS,other/'data/research/bbi')
        self.assertLess(load_bbi_evidence(other)['player_b'][0].value['grade'],50)

    def test_missing_exposure_is_explicitly_qualitative(self):
        self.write_observation(self.observation(sample_size=None,Minutes=None))
        obs=load_bbi_evidence(self.root)['player_b'][0]
        self.assertEqual('qualitative_assessment',obs.exposure_unit)
        self.assertEqual((1,4,.15),(obs.n,obs.prior_exposure,obs.reliability))

    def test_broken_cache_fails_visibly(self):
        self.write_observation()
        index=self.cache/'normalized.json';cache=json.loads(index.read_text())
        shard=self.cache/next(iter(cache['batches'].values()))['normalized_file']
        shard.unlink()
        with self.assertRaises(FileNotFoundError):load_bbi_evidence(self.root)
        cache['schema_version']='future_unknown';index.write_text(json.dumps(cache))
        with self.assertRaises(ValueError):load_bbi_evidence(self.root)

    def local_sources(self):
        payloads={SKILL_PATH:{'players':[]},CAREER_PATH:{'players':{}},STATS_PATH:{'rows':[]},
                  UNIVERSE_PATH:{'players':PLAYERS,'traits':[]},SHOT_ZONE_PATH:{'profiles':[]}}
        for path,data in payloads.items():
            target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(data))

    def test_absent_cache_from_local_is_byte_identical(self):
        self.local_sources()
        universe={'players':PLAYERS,'traits':[]}
        before=canonical_json(InputEstimator().estimate_universe(universe)).encode()
        after=canonical_json(InputEstimator.from_local(self.root,use_expert=False).estimate_universe(universe)).encode()
        self.assertEqual(before,after)
        self.assertFalse(self.cache.exists())

    def test_from_local_automatically_uses_observed_cache_only(self):
        self.local_sources()
        before=InputEstimator.from_local(self.root,use_expert=False).estimate_player_inputs(PLAYERS[1]).to_dict()
        self.write_observation()
        after=InputEstimator.from_local(self.root,use_expert=False).estimate_player_inputs(PLAYERS[1]).to_dict()
        self.assertNotEqual(before['inputs']['S35'],after['inputs']['S35'])
        self.assertEqual({k:v for k,v in before['inputs'].items() if k!='S35'},
                         {k:v for k,v in after['inputs'].items() if k!='S35'})


if __name__ == '__main__':
    unittest.main()
