"""Independent evidence-ledger validation; no backend, simulation or save calls."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[4]
R=ROOT/'docs/ratings-evidence-2026-10-29'
D=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from nba_gm_data.player_model_registry import definition_registry

p=json.loads((R/'PASS_RECOVERY_EVIDENCE_2026_11_16.json').read_text())
v=json.loads((D/'validation.json').read_text())
ids={x['id'] for x in definition_registry()['inputs']}
assert len(ids)==94 and sum(k.startswith('F') for k in ids)==18
assert len({c['id'] for c in p['claims']})==len(p['claims'])==10
assert len({c['id'] for c in p['constraints']})==len(p['constraints'])==6
for c in p['claims']:
 assert c['source_id'] in p['sources']
 assert c['locator'] and c['cannot_establish'] and c['candidate_engine_implication']
 assert c['uncertainty'] and set(c['input_ids'])<=ids
 source=p['sources'][c['source_id']]
 assert c['source_date']==source['date']
 if source.get('path'):
  raw=(R/source['path']).read_text()
  for minute in re.findall(r'(\d\d:\d\d):\d\d[–-]',c['locator']):
   assert minute+':' in raw
for c in p['constraints']:
 assert all(k in p['sources'] for k in c['source_ids'])
 assert 'denominator' in c and 'derivation' in c and c['limits']
 assert not c['applicable_to_clean_awkward_loss_probabilities']
 if c['kind'].startswith('observed_numeric'):
  assert c['numerator'] is not None and c['denominator']['value']>0
pc={c['id']:c for c in p['constraints']}
assert pc['PC02']['derived']['turnovers_per_game']==255/64
assert pc['PC02']['denominator']['unit']=='games played'
assert pc['PC03']['denominator'] is None and pc['PC03']['derivation'] is None
f=json.loads((D/'reviewed_gamebook_facts.json').read_text())
assert sum(f['player_turnovers_INDs'])==f['summed_individual_turnovers']['IND']==24
assert sum(f['player_turnovers_OKCs'])==f['summed_individual_turnovers']['OKC']==6
for team in ['IND','OKC']:
 assert f['team_turnovers'][team]-f['summed_individual_turnovers'][team]==f['team_events_by_difference'][team]==1
checks={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in p['source_hashes'].items()}
assert all(checks.values())
for s in p['sources'].values():
 if 'path' in s: assert (R/s['path']).exists()
 if 'repo_path' in s: assert (ROOT/s['repo_path']).exists()
report=R/'PASS_RECOVERY_EVIDENCE_2026_11_16.md'
links=0
for link in re.findall(r'\]\(([^)]+)\)',report.read_text()):
 if not link.startswith('https://'):
  assert (report.parent/link.split('#')[0]).exists(),link
  links+=1
assert not p['player_updates'] and not p['operational_completions']
assert not p['conditional_probability_estimates'] and not p['speculative_numeric_ranges']
assert len({s['id'] for s in p['proposed_observation_states']})==6
assert p['calibration_finding']['conditional_clean_awkward_loss_rate_found'] is False
assert p['calibration_finding']['observed_numeric_aggregate_constraints_found'] is True
assert p['independence']['simulations']==0 and not p['independence']['new_backend_outcomes_inspected']
v['independent_delivery_validation']={'status':'PASS','local_links_resolved':links,'claim_source_and_registry_refs_valid':True,'retained_timestamp_starting_minutes_present':True,'numeric_denominators_and_derivations_explicit':True,'gamebook_player_team_arithmetic_recomputed':True,'no_cross_window_rate_computed':True,'eleven_source_hashes_unchanged':len(checks)==11 and all(checks.values()),'no_player_updates_or_probability_proposals':True,'scope':'Ledger/reference/accounting validation only; selected source facts checked, not complete game coding or calibration.'}
(D/'validation.json').write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':'PASS','claims':10,'constraints':6,'links':links,'conditional_rates':0,'source_hashes':len(checks)}))
