"""Research only: private in-memory trait sensitivities; no save or simulation."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from nba_gm_data.save import player_attribute_summary, player_display_attribute_summary, roster_cut_score
from nba_gm_data.sim import player_feature_vector, defensive_anchor_score, primary_creator_score, invalidate_sim_cache

ROOT = Path(__file__).resolve().parents[3]
CANONICAL = ROOT / 'data/canonical/universe_2026_27_offseason.json'
OUT = Path(__file__).with_name('five_player_calibration_recompute_20261109.json')
source_bytes = CANONICAL.read_bytes()
original = json.loads(source_bytes)
scenarios = {
    'edwards_effort': ('Anthony Edwards', {'defensive_effort': -10}),
    'vassell_previous_versatility': ('Devin Vassell', {'shot_versatility': 1.5}),
    'vassell_shooting': ('Devin Vassell', {'shot_versatility': 4}),
    'vassell_defense': ('Devin Vassell', {'defensive_effort': -6, 'rim_deterrence': -8}),
    'vassell_combined': ('Devin Vassell', {'shot_versatility': 4, 'defensive_effort': -6, 'rim_deterrence': -8}),
    'duren_plateau_sensitivity': ('Jalen Duren', {'rim_deterrence': -6}),
    'duren_rim_target_90': ('Jalen Duren', {'rim_deterrence': -8.99}),
    'coward_previous_passing': ('Cedric Coward', {'passing_reads': 1.5}),
    'coward_defensive_scouting': ('Cedric Coward', {'defensive_effort': 5, 'rim_deterrence': 6, 'scheme_iq': 3}),
    'kawhi_offense': ('Kawhi Leonard', {'shot_versatility': 4, 'handle_pressure': 2}),
    'kawhi_rim': ('Kawhi Leonard', {'rim_deterrence': -15}),
    'kawhi_combined': ('Kawhi Leonard', {'shot_versatility': 4, 'handle_pressure': 2, 'rim_deterrence': -15}),
}

def capture(universe, name):
    player = next(p for p in universe['players'] if p['name'] == name)
    features = player_feature_vector(universe, player).features
    result = {
        'player_id': player['id'], 'minutes_projection': player['minutes_projection'],
        'engine': player_attribute_summary(universe, player['id']),
        'display_crosswalk': player_display_attribute_summary(universe, player['id']),
        'features': features,
        'derived_scores': {
            'defensive_anchor': round(defensive_anchor_score(features), 6),
            'primary_creator': round(primary_creator_score(features), 6),
            'roster_cut_score': round(roster_cut_score(universe, player), 6),
        },
    }
    invalidate_sim_cache(universe)
    return result

result = {
    'scope': 'Canonical fixed-source-minutes crosswalk, not observed runtime card; no season simulation.',
    'baseline_version': original['meta']['starting_data_version'],
    'canonical_sha256_before': sha256(source_bytes).hexdigest(),
    'scenarios': {},
}
for label, (name, deltas) in scenarios.items():
    before = capture(deepcopy(original), name)
    private = deepcopy(original)
    pid = before['player_id']
    changes = {}
    for trait in private['traits']:
        key = trait['trait_key']
        if trait['player_id'] == pid and key in deltas:
            old = trait['value']
            trait['value'] = round(old + deltas[key], 2)
            changes[key] = {'before': old, 'after': trait['value'], 'delta': deltas[key]}
    after = capture(private, name)
    changed_outputs = {}
    for category in ('engine', 'display_crosswalk', 'features', 'derived_scores'):
        changed_outputs[category] = {
            key: {'before': value, 'after': after[category][key],
                  'delta': round(after[category][key] - value, 6)}
            for key, value in before[category].items()
            if after[category].get(key) != value
        }
    result['scenarios'][label] = {
        'player': name, 'trait_changes': changes,
        'before': before, 'after': after, 'changed_outputs': changed_outputs,
    }
result['canonical_sha256_after'] = sha256(CANONICAL.read_bytes()).hexdigest()
result['canonical_file_unchanged'] = result['canonical_sha256_before'] == result['canonical_sha256_after']
OUT.write_text(json.dumps(result, indent=2) + '\n')
for label, row in result['scenarios'].items():
    print(label)
    for category in ('engine', 'display_crosswalk'):
        print(category, {k: (row['before'][category][k], row['after'][category][k])
                         for k in ('overall', 'offense', 'defense', 'rebounding', 'block', 'steal')})
    print('features', {key: value for key, value in row['changed_outputs']['features'].items()
                       if not key.startswith('sp_')})
    print('spatial_fields_changed', sum(key.startswith('sp_')
                                       for key in row['changed_outputs']['features']))
    print('derived_scores', row['changed_outputs']['derived_scores'])
print('canonical_file_unchanged', result['canonical_file_unchanged'])
