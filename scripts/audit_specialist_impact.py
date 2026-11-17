"""Read-only saved-career review and bounded, health-neutral specialist probes."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import statistics
import time

from nba_gm_data.play import derived_trait_attributes
from nba_gm_data.save import ai_roster_retention_score, player_display_attribute_summary
from nba_gm_data.sim import (
    distribute_player_lines, lineup_feature_vector, player_feature_vector,
    scoring_expectations_with_caps, scoring_weight, simulate_team_line,
)
from nba_gm_data.transactions import build_player_asset_valuations
from nba_gm_data.utils import normalize_name

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BATCH = Path.home() / '.cache/nba-gm-audits/rotation-profiles-v8-2026-10-26'
CENTERS = ('Zach Edey', 'Deandre Ayton', 'Jarrett Allen', 'Rudy Gobert', 'Ivica Zubac',
           'Dereck Lively II', 'Alperen Sengun', 'Domantas Sabonis', 'Nikola Jokic', 'Myles Turner')
GUARDS = ('Jamal Shead', 'Tre Jones', 'Collin Gillespie', 'Tyrese Haliburton', 'Jalen Brunson')
SUPPORT = ('Desmond Bane', 'Mikal Bridges', 'Tobias Harris', 'Tyus Jones',
           'Grayson Allen', "Royce O'Neale", 'Isaiah Stewart')
STATS = ('points', 'assists', 'rebounds', 'fg3a', 'fg3m', 'fga', 'fgm', 'fta', 'ftm')
HOME = {'id': 'audit_home', 'abbrev': 'AUH'}
AWAY = {'id': 'audit_away', 'abbrev': 'AUA'}


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read(path):
    with path.open() as handle:
        return json.load(handle)


def by_name(canonical, name):
    matches = [p for p in canonical['players'] if normalize_name(p['name']) == normalize_name(name)]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one player named {name!r}; found {len(matches)}')
    return matches[0]


def make_lineup(canonical, target, *, guard=False, overrides=None, target_minutes=30):
    """Same teammates/minutes; age 27, no fatigue, injuries, coaches or manifestos."""
    names = [target, 'Jarrett Allen' if guard else 'Tyrese Haliburton', *SUPPORT]
    if not 6 <= target_minutes <= 42:
        raise ValueError('Target minutes must leave a legal 6-42 minute backup-center role')
    if guard and target_minutes != 30:
        raise ValueError('Minute sensitivity currently supports centers only')
    minutes = [target_minutes, 30, 30, 30, 30, 24, 24, 24, 48-target_minutes]
    players = [deepcopy(by_name(canonical, name)) for name in names]
    ids = {p['id'] for p in players}
    if len(ids) != len(players):
        raise ValueError('Probe lineup repeats a player')
    for p, mpg in zip(players, minutes, strict=True):
        p.update(team_id=HOME['id'], team_abbrev=HOME['abbrev'], minutes_projection=mpg,
                 age=27, rotation_priority='rotation')
    traits = [deepcopy(t) for t in canonical['traits'] if t['player_id'] in ids]
    for t in traits:
        name = next(p['name'] for p in players if p['id'] == t['player_id'])
        if t['trait_key'] in (overrides or {}).get(name, {}):
            t['value'] = overrides[name][t['trait_key']]
    local = {'meta': deepcopy(canonical.get('meta', {})), 'players': players, 'traits': traits,
             'teams': [HOME, AWAY], 'player_health_states': [], '_allow_internal_caches': True}
    pool = [{'player': p, 'minutes': mpg} for p, mpg in zip(players, minutes, strict=True)]
    return local, pool


def per36(totals):
    minutes = float(totals.get('minutes') or 0)
    if minutes <= 0:
        return None
    result = {k: round(float(totals[k])*36/minutes, 3) if totals.get(k) is not None else None
              for k in STATS}
    result['fg_pct'] = round(totals['fgm']/totals['fga'], 4) if totals.get('fga') and totals.get('fgm') is not None else None
    return result


def means(rows, keys):
    return {k: round(statistics.fmean(float(r[k]) for r in rows), 4) for k in keys}


def probe(canonical, target, trials, *, guard=False, overrides=None, target_minutes=30):
    if trials < 2:
        raise ValueError('At least two paired trials required')
    local, pool = make_lineup(canonical, target, guard=guard, overrides=overrides,
                              target_minutes=target_minutes)
    features = lineup_feature_vector(local, pool)
    # The opposing lineup is identical in every case, including center/guard probes.
    opp, opp_pool = make_lineup(canonical, 'Jarrett Allen')
    opp_features = lineup_feature_vector(opp, opp_pool)
    target_id = pool[0]['player']['id']
    p_features = {i['player']['id']: player_feature_vector(local, i['player']).features for i in pool}
    from nba_gm_data.offense import support_passing
    weights = [scoring_weight(i, p_features[i['player']['id']],
               feeder=support_passing(pool, p_features, i['player']['id'])
               if p_features[i['player']['id']].get('offense_model_version') else 50) for i in pool]
    expectations = scoring_expectations_with_caps(pool, p_features, 114, weights)
    fixed, team_lines, opponent_lines = [], [], []
    for seed in range(trials):
        lines = distribute_player_lines(local, HOME, pool, 114, 100, random.Random(f'fixed:{seed}'))
        fixed.append(next(line for line in lines if line['player_id'] == target_id))
        _, team_line = simulate_team_line(local, HOME, AWAY, pool, features, opp_features,
                                          None, None, random.Random(f'game:{seed}'))
        _, opp_line = simulate_team_line(opp, AWAY, HOME, opp_pool, opp_features, features,
                                         None, None, random.Random(f'opponent:{seed}'))
        team_lines.append(team_line)
        opponent_lines.append(opp_line)
    off = [row['off_rating'] for row in team_lines]
    defense = [row['off_rating'] for row in opponent_lines]
    ratings = derived_trait_attributes(player_display_attribute_summary(local, target_id))
    return {
        'target': pool[0]['player']['name'], 'minutes': target_minutes, 'trials': trials,
        'fixed_114_points': means(fixed, STATS),
        'expected_points_before_noise': round(expectations[0], 4),
        'scoring_weight': round(weights[0], 4),
        'team_off_rating': round(statistics.fmean(off), 4),
        'opponent_off_rating': round(statistics.fmean(defense), 4),
        'net_rating': round(statistics.fmean(a-b for a, b in zip(off, defense)), 4),
        'off_rating_standard_error': round(statistics.stdev(off)/trials**.5, 4),
        'display_ratings': {k: ratings[k] for k in ('overall', 'offense', 'shooting', 'creation', 'passing', 'rebounding')},
        'raw_features': p_features[target_id], 'team_features': features,
        'lineup': [{'name': i['player']['name'], 'minutes': i['minutes']} for i in pool],
    }


def career_review(canonical, paths):
    ids = {p['id']: p for p in canonical['players']}
    selected = {by_name(canonical, name)['id'] for name in (*CENTERS, *GUARDS)}
    results = []
    for path in paths:
        saved = read(path)
        seasons = []
        for history in saved['season_history']:
            stats = history['player_season_stats']
            rows = []
            for pid in sorted(selected):
                s = stats.get(pid, {})
                games = int(s.get('games') or 0)
                rows.append({'name': ids[pid]['name'], 'games': games,
                             'mpg': round(float(s.get('minutes') or 0)/games, 3) if games else 0,
                             'per36': per36(s)})
            # No hand-selected player filter for the center shooting-profile check.
            centers = [s for pid, s in stats.items() if pid in ids and ids[pid].get('position') == 'C'
                       and float(s.get('minutes') or 0) >= 500]
            seasons.append({'season': history['season'], 'players': rows,
                            'centers_500_minutes': len(centers),
                            'center_3pa_per36': per36({'minutes': sum(s['minutes'] for s in centers),
                                                     'fg3a': sum(s.get('fg3a', 0) for s in centers)})['fg3a'] if centers else None})
        results.append({'path': str(path), 'seasons': seasons})
    return results


def observed_samples(canonical, career_data, raw_input):
    source = {normalize_name(p['name']): p for p in raw_input['players']}
    result = []
    for name in (*CENTERS, *GUARDS):
        player = by_name(canonical, name)
        espn_id = str(player.get('espn_player_id'))
        record = career_data['players'].get(espn_id, {})
        if str(record.get('espn_player_id')) != espn_id:
            raise ValueError(f'Career identity mismatch: {name}')
        rows = []
        for season in record.get('seasons', []):
            if season.get('season') not in {'2024-25', '2025-26'}:
                continue
            if f'/basketball/nba/athletes/{espn_id}/' not in season.get('source_url', ''):
                raise ValueError(f'Career source mismatch: {name}')
            rows.append({'season': season['season'], 'games': season['games'],
                         'minutes': season['minutes'], 'per36': per36(season),
                         'source_url': season['source_url']})
        raw = source.get(normalize_name(name), {})
        result.append({'name': player['name'], 'nba_seasons': rows,
                       'input_playtypes': {k: raw.get(k) for k in ('Post%', 'PostPPP', 'Pnrr%', 'PnrrPPP', 'Cut%', 'CutPPP', 'Putback%', 'PutbackPPP')},
                       'input_caveat': 'Mixed source snapshot; possession counts absent. PPP is not a complete measure of skill or impact.'})
    return result


def run_audit(root, batch, trials):
    canonical_path = root/'data/canonical/universe_2026_27_offseason.json'
    career_path = root/'data/research/player_career_stats.json'
    raw_path = root/'Player Stats/player_skill_input_2025_26.json'
    paths = []
    missing = []
    for arm in ('control', 'candidate'):
        for seed in (29, 913):
            run_path = batch/f'runtime/output/comparison/{arm}/career-{seed}/run.json'
            if run_path.exists():
                paths.append(Path(read(run_path)['save_path']))
            else:
                missing.append(str(run_path))
    engine_paths = [root/f'src/nba_gm_data/{name}.py'
                    for name in ('sim', 'spatial', 'save', 'play', 'transactions', 'traits', 'talent')]
    inputs = [canonical_path, career_path, raw_path, *paths, *engine_paths]
    before = {str(p): sha(p) for p in inputs}
    canonical = read(canonical_path)
    # Caches are owned only by disposable copies, never the canonical file.
    canonical['_allow_internal_caches'] = True
    probes = [probe(canonical, n, trials) for n in CENTERS]
    probes.extend(probe(canonical, n, trials, guard=True) for n in GUARDS)
    sensitivity = []
    for target, guard, key in (('Zach Edey', False, 'offensive_rebounding'),
                                ('Jamal Shead', True, 'scheme_iq'),
                                ('Jamal Shead', True, 'passing_reads')):
        pair = [probe(canonical, target, trials, guard=guard, overrides={target: {key: value}})
                for value in (20, 80)]
        sensitivity.append({'target': target, 'only_trait_changed': key, 'values': [20, 80],
                            'low': pair[0], 'high': pair[1],
                            'caveat': 'Synthetic mechanism test, not an appropriate rating assignment.'})
    # This shifts the feeder, not the finisher. The finisher scoring weight has
    # no teammate input; changes in share can only come through the denominator.
    feeder = [probe(canonical, 'Zach Edey', trials,
                    overrides={'Tyrese Haliburton': {'passing_reads': value}}) for value in (20, 80)]
    minute_sensitivity = [probe(canonical, target, trials, target_minutes=minutes)
                          for target in ('Zach Edey', 'Deandre Ayton') for minutes in (12, 18, 24, 36)]
    valuations = {v.player_id: v for v in build_player_asset_valuations(canonical)}
    consumers = []
    for n in (*CENTERS, *GUARDS):
        p = by_name(canonical, n)
        v = valuations[p['id']]
        consumers.append({'name': p['name'], 'on_court_value_raw': v.on_court_value,
                          'asset_value_raw': v.player_value, 'salary': v.current_salary,
                          'retention_score_raw': ai_roster_retention_score(canonical,
                              {'meta': {'season': '2026-27'}, 'state': {'current_date': '2026-10-01'}}, p),
                          'caveat': 'Original roster, age, contract and role; not the age-neutral fixed-minute probe.'})
    result = {'baseline': canonical.get('meta', {}).get('starting_data_version'),
              'trials_per_case': trials, 'probe_cases': len(probes)+2*len(sensitivity)+2+len(minute_sensitivity),
              'method': {'points_allocation': '114 points, 100 possessions, same teammates and RNG seeds; target 30 minutes, rotation 240.',
                         'team_impact': 'Real simulate_team_line in both directions against one fixed opponent; no coaches, injuries, fatigue, manifestos or home advantage.',
                         'scale': 'Display OFF uses derived_trait_attributes 35/32/18/15 on display composites. Some app tables instead use 30/30/20/20. Raw impact/AI values are not displayed ratings.',
                         'uncertainty': 'Paired trials cancel team scoring noise for rating differences; these are mechanism tests, not observed causal NBA effects.',
                         'scope': 'No simulation dates advanced, no engine/rating/UI changes, no career migrations.'},
              'observed': observed_samples(canonical, read(career_path), read(raw_path)),
              'saved_careers': career_review(canonical, paths), 'missing_career_inputs': missing,
              'controlled_probes': probes, 'synthetic_sensitivity': sensitivity,
              'feeder_sensitivity': {'values': [20, 80], 'low': feeder[0], 'high': feeder[1]},
              'minute_sensitivity': minute_sensitivity,
              'ai_consumers': consumers, 'input_hashes': before}
    after = {str(p): sha(p) for p in inputs}
    if before != after:
        raise RuntimeError('An audit input changed while it was being read; rerun against stable inputs.')
    result['inputs_unchanged'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--batch', type=Path, default=DEFAULT_BATCH)
    parser.add_argument('--trials', type=int, default=256)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    start = time.monotonic()
    result = run_audit(args.root, args.batch, args.trials)
    result['elapsed_seconds'] = round(time.monotonic()-start, 3)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
    else:
        print(json.dumps(result, indent=2))
    print(f"Completed {result['probe_cases']} cases x {args.trials} trials in {result['elapsed_seconds']}s; "
          f"reviewed {len(result['saved_careers'])} saved careers; inputs unchanged.")


if __name__ == '__main__':
    main()
