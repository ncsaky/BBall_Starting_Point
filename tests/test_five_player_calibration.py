from copy import deepcopy
import gzip,json,unittest
from pathlib import Path
from nba_gm_data.schema import Player,TraitValue,to_plain
from nba_gm_data.five_player_calibration import apply_calibration,MARKER
from nba_gm_data.ingest import build_universe
from nba_gm_data import save as sv
ROOT=Path(__file__).resolve().parents[1]
class FivePlayerCalibrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.current=json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text())
  with gzip.open(ROOT/'data/canonical/baselines/2026-10-30-contract-separation-v10.json.gz','rt') as h:cls.old=json.load(h)
  cls.payload=json.loads((ROOT/'data/overrides/five_player_calibration_v11.json').read_text())
 def test_only_exact_targets_and_reviewed_rim_anchor_change_inputs(self):
  old={(t['player_id'],t['trait_key']):t['value'] for t in self.old['traits']};new={(t['player_id'],t['trait_key']):t['value'] for t in self.current['traits']}
  expected={(r['player_id'],k):(v['expected'],v['target']) for r in self.payload['players'] for k,v in r['traits'].items()}
  expected[('player_sas-victor-wembanyama','rim_deterrence')]=(99.0,100.0)
  self.assertEqual({k:(v,new[k]) for k,v in old.items() if new[k]!=v},expected)
  self.assertEqual(self.old['players'],self.current['players']);self.assertEqual(self.old['contracts'],self.current['contracts'])
 def test_absolute_idempotent_and_stale_identity_or_baseline_rejected(self):
  ps=[Player(**p) for p in self.old['players']];ts=[TraitValue(**t) for t in self.old['traits']];once=apply_calibration(ps,ts,self.payload);self.assertEqual(once,apply_calibration(ps,once,self.payload))
  # The later single rim-anchor review is independent of this eleven-target
  # v11 overlay; preserve the overlay's exact arithmetic and guards.
  self.assertEqual([t.value for t in once],[99.0 if (t['player_id'],t['trait_key'])==('player_sas-victor-wembanyama','rim_deterrence') else t['value'] for t in self.current['traits']])
  payload=deepcopy(self.payload);payload['players'][0]['traits']['defensive_effort']['expected']+=1
  with self.assertRaises(ValueError):apply_calibration(ps,ts,payload)
  payload=deepcopy(self.payload);payload['players'][0]['name']='Wrong identity'
  with self.assertRaises(ValueError):apply_calibration(ps,ts,payload)
 def test_final_order_provenance_and_rebuild(self):
  rebuilt=to_plain(build_universe(ROOT));self.assertEqual(rebuilt,self.current)
  for row in self.payload['players']:
   for key in row['traits']:
    t=next(t for t in self.current['traits'] if t['player_id']==row['player_id'] and t['trait_key']==key)
    self.assertEqual(t['components'][MARKER]['review_sha256'],self.payload['review_sha256'])
    self.assertIn('2026_roster_refresh',t['components'])
 def test_existing_version_preserves_traits_development_and_models(self):
  saved={'version':sv.SAVE_VERSION,'meta':{'starting_data_version':self.old['meta']['starting_data_version'],'season':'2026-27','seed':17},'state':{'current_date':'2026-11-01','phase':'regular_season'},'development_events':[],'development_trait_totals':{'player_det-jalen-duren':{'rim_deterrence':2}},'rotation_baselines':{p['id']:p['minutes_projection'] for p in self.old['players']}}
  a=sv.canonical_with_save(self.old,deepcopy(saved));b=sv.canonical_with_save(self.current,deepcopy(saved))
  for key in ['players','traits','contracts']:self.assertEqual(a[key],b[key])
  for key in ['talent_model_version','offense_model_version']:self.assertEqual(a['meta'][key],b['meta'][key])
