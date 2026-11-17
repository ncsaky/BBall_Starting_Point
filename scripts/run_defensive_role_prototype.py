"""Offline experiment: current inputs/engine, optional trial inputs, role contexts.

No writes to canonical data, saves, production modules or UI. Run with
PYTHONPATH=src:. .venv/bin/python scripts/run_defensive_role_prototype.py --output DIR
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import time
import tracemalloc

from experiments.defensive_roles.model import (
    VERSION, JOBS, KEYS, RECIPES, CRITICAL, Context, Player, Trait, assign, estimate, summarize,
)
from nba_gm_data.defense import defensive_components

FOCUS = ('Victor Wembanyama', 'Rudy Gobert', 'Derrick White', 'Stephon Castle',
         'Scottie Barnes', 'Evan Mobley', 'Bam Adebayo', 'Alex Caruso',
         'Stephen Curry', 'Luka Dončić', 'Nick Richards', 'Isaiah Stewart',
         'Clint Capela', 'Jay Huff', 'Brook Lopez', 'Myles Turner')
CONTEXTS = (
    Context('balanced', tuple(zip(JOBS, (1, .7, .8, 1, .6, .9))), 80),
    Context('movement_shooting', tuple(zip(JOBS, (.8, 1.5, .7, 1, .7, .3))), 78),
    Context('interior_pressure', tuple(zip(JOBS, (.7, .3, .7, 1, .8, 1.5))), 82),
    Context('large_wing_switching', tuple(zip(JOBS, (1, .3, 1.5, .8, 1.1, .3))), 83),
)


def current_engine(p):
    traits = {key: t.value for key, t in p.traits}
    # Same established missing default as the engine summary, ONLY for the
    # separately labelled current-engine reference. Role missing prior is 35.
    c = defensive_components(lambda key: traits.get(key, 50.0))
    return dict(zip(('activity', 'effective_rim', 'defense'), c))


def load_players(canonical, observations):
    by_id = {}
    for t in canonical['traits']:
        if t['trait_key'] not in KEYS.values(): continue
        components = t.get('components') or {}
        provenance = 'manual' if components.get('manual_calibration') else 'inferred/calibrated proxy'
        by_id.setdefault(t['player_id'], []).append((t['trait_key'], Trait(
            t['value'], t.get('confidence', 0), provenance)))
    return [Player(p['id'], p['name'], tuple(sorted(by_id.get(p['id'], []))),
                   p.get('height_inches'), tuple(observations.get(p['name'], {}).get('jobs', [])),
                   observations.get(p['name'], {}).get('note',
                     f"Imported primary_def_role={p.get('primary_def_role')!r}; unverified source label, not observed matchup shares or talent."))
            for p in canonical['players']]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--canonical', type=Path, default=Path('data/canonical/universe_2026_27_offseason.json'))
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--observations', type=Path)
    ap.add_argument('--trial-inputs', type=Path, help='Private name -> trait -> value experiment, never applied to production')
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = args.canonical.read_bytes(); c = json.loads(raw)
    observations = json.loads(args.observations.read_text()) if args.observations else {}
    original = load_players(c, observations)
    trial = json.loads(args.trial_inputs.read_text()) if args.trial_inputs else {}
    unknown = set(trial) - {p.name for p in original}
    if unknown: raise ValueError(f'Unknown trial players: {unknown}')
    players = []
    changes = []
    for p in original:
        edits = trial.get(p.name, {})
        if set(edits) - set(KEYS.values()): raise ValueError('Unsupported trial trait')
        traits = dict(p.traits)
        for key, value in edits.items():
            changes.append({'player': p.name, 'trait': key, 'before': traits.get(key).value if key in traits else None, 'after': value})
            traits[key] = Trait(value, 0, 'private sensitivity; NOT a production input')
        players.append(replace(p, traits=tuple(sorted(traits.items()))))
    by_name = {p.name: p for p in players}
    by_id = {p.id: p for p in original}
    estimates = []
    for p in players:
        row = estimate(p)
        row['original_inputs_current_engine'] = current_engine(by_id[p.id])
        row['trial_inputs_current_engine'] = current_engine(p)
        row['production_def'] = round(row['original_inputs_current_engine']['defense'], 1)
        row['input_provenance'] = {key: {'value': t.value, 'confidence': t.confidence, 'provenance': t.provenance} for key, t in p.traits}
        row['sensitivity_bottleneck_10_20_30'] = {str(a): {j: r['score'] for j, r in estimate(p, bottleneck_allowance=a)['roles'].items()} for a in (10, 20, 30)}
        row['sensitivity_uniform_weight_blend'] = {str(a): {j: r['score'] for j, r in estimate(p, uniform_weight_blend=a)['roles'].items()} for a in (0, .5, 1)}
        estimates.append(row)
    # Same four teammates/context: identity affects only disclosed wing contact
    # mismatch; defensive-input-only replacement controls below hold it fixed.
    base = [by_name[n] for n in ('Derrick White', 'Stephen Curry', 'Stephon Castle', 'Scottie Barnes', 'Rudy Gobert')]
    lineups = {}
    for name, lineup in (
        ('mixed_Gobert', base),
        ('mixed_Wembanyama', [*base[:4], by_name['Victor Wembanyama']]),
        ('mixed_Mobley', [*base[:4], by_name['Evan Mobley']]),
        ('five_anchors', [by_name[n] for n in ('Rudy Gobert', 'Nick Richards', 'Clint Capela', 'Jay Huff', 'Brook Lopez')]),
        ('perimeter_without_anchor', [by_name[n] for n in ('Derrick White', 'Stephen Curry', 'Stephon Castle', 'Alex Caruso', 'Luka Dončić')]),
    ):
        lineups[name] = {}
        for context in CONTEXTS:
            shares = assign(lineup, context)
            lineups[name][context.name] = summarize(lineup, context, shares)
        all_shelter = {p.id: {'sheltered': 1.0} for p in lineup}
        all_anchor = {p.id: {'anchor_big': 1.0} for p in lineup}
        lineups[name]['all_sheltered_counterexample'] = summarize(lineup, CONTEXTS[0], all_shelter)
        lineups[name]['all_anchor_counterexample'] = summarize(lineup, CONTEXTS[0], all_anchor)
    controls = {}
    held_identity = base[-1]
    for name in FOCUS:
        source = by_name[name]
        replacement = replace(held_identity, traits=source.traits, observed_jobs=(), observation_note='Controlled defensive-input replacement')
        lineup = [*base[:4], replacement]
        controls[name] = {context.name: summarize(lineup, context, assign(lineup, context)) for context in CONTEXTS}
    # A separate unavailable-player scenario; factor is hypothetical and is not
    # offered as a replacement for the production health/fatigue calculations.
    hurt = replace(CONTEXTS[0], name='diagnostic_half_availability_anchor', availability=((base[-1].id, .5),))
    lineups['mixed_Gobert'][hurt.name] = summarize(base, hurt, assign(base, hurt))
    times = []
    for _ in range(7):
        start = time.perf_counter()
        for p in players: estimate(p)
        times.append(time.perf_counter() - start)
    assignment_times = []
    for _ in range(7):
        start = time.perf_counter()
        summarize(base, CONTEXTS[0], assign(base, CONTEXTS[0]))
        assignment_times.append(time.perf_counter() - start)
    # Allocation tracing separately; drop each output immediately.
    tracemalloc.start()
    for _ in range(3):
        for p in players: estimate(p)
    retained, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    tracemalloc.start()
    batch = [estimate(p) for p in players]
    batch_retained, batch_peak = tracemalloc.get_traced_memory()
    del batch
    after_batch_release, _ = tracemalloc.get_traced_memory(); tracemalloc.stop()
    result = {
        'status': 'OFFLINE PROTOTYPE; no production inputs or behavior changed',
        'prototype_version': VERSION,
        'canonical_sha256': hashlib.sha256(raw).hexdigest(), 'players': estimates,
        'trial_input_changes': changes, 'recipes': {j: dict(v) for j, v in RECIPES.items()},
        'critical_channels': dict(CRITICAL), 'lineups': lineups, 'same_identity_controls': controls,
        'role_anchors': {'0': 'modeled inability', '25': 'weak', '50': 'functional neutral reference',
                         '75': 'strong', '90': 'exceptional hypothesis', '100': 'ideal endpoint'},
        'anchor_limit': 'Interpretive model anchors, not empirically calibrated or peer percentiles.',
        'timing': {'all_players': len(players), 'samples': times, 'median_seconds': statistics.median(times),
                   'range_seconds': [min(times), max(times)], 'scope': 'estimate only; offline/no game runtime overhead'},
        'allocation_diagnostic': {'three_sweeps_retained_bytes': retained, 'peak_bytes': peak,
                                  'scope': 'scores only, no output accumulation; excludes inputs and retained reports; not a whole-app memory study'},
        'batch_output_allocations': {'retained_691_outputs_bytes': batch_retained, 'peak_bytes': batch_peak,
                                     'after_explicit_batch_release_bytes': after_batch_release},
        'lineup_assignment_and_summary_timing': {'samples': assignment_times,
            'median_seconds': statistics.median(assignment_times),
            'range_seconds': [min(assignment_times), max(assignment_times)]},
    }
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    rows = {r['name']: r for r in estimates}
    table = ['| Player | POA | Chaser | Wing | Helper | Mobile | Anchor | Current DEF | Suggested jobs |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for name in FOCUS:
        r = rows[name]
        values = ' | '.join(f"{r['roles'][j]['score']:.1f}" for j in JOBS)
        table.append(f"| {name} | {values} | {r['trial_inputs_current_engine']['defense']:.1f} | {r['suggested_primary']} / {r['suggested_secondary']} |")
    (args.output / 'scores.md').write_text('\n'.join(table) + '\n')
    print(json.dumps({'output': str(args.output), 'players': len(players), 'trial_changes': changes,
                      'timing': result['timing'], 'allocation_diagnostic': result['allocation_diagnostic']}, indent=2))

if __name__ == '__main__': main()
