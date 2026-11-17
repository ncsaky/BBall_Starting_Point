"""Read-only retention and game-to-game distribution review of completed careers.

Never advances a save. Fresh ESPN samples, when requested, go only into the
review output, not the game's research inputs or canonical data.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import urllib.request

from nba_gm_data.history_store import load_history_records, validate_save_components
from audit_basketball_accounting import game_errors

ROOT = Path(__file__).resolve().parents[1]
BATCH = Path.home()/'.cache/nba-gm-audits/offense-season-v9-2026-10-27'
OLD = Path.home()/'.cache/nba-gm-audits/rotation-profiles-v8-2026-10-26/runtime/output/comparison/candidate'
FIELDS = ('points', 'rebounds', 'assists', 'turnovers', 'steals', 'blocks',
          'fga', 'fg3a', 'fta', 'fg_pct', 'three_pct', 'ft_pct')


def read(path):
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as handle:
        return json.load(handle)


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def history(path, saved, kind):
    rows = {r['id']: r for r in load_history_records(path, saved, kind, _validated=True)}
    rows.update({r['id']: r for r in saved.get(kind, [])})
    return sorted(rows.values(), key=lambda r: (r.get('date', ''), r['id']))


def with_percentages(row):
    row = dict(row)
    for key, made, attempts in (('fg_pct', 'fgm', 'fga'), ('three_pct', 'fg3m', 'fg3a'), ('ft_pct', 'ftm', 'fta')):
        row[key] = row.get(made, 0)/row[attempts]*100 if row.get(attempts, 0) > 0 else None
    return row


def summary(values):
    values = sorted(v for v in values if v is not None and math.isfinite(v))
    if not values:
        return {'n': 0}
    return {'n': len(values), 'mean': round(statistics.fmean(values), 4),
            'sd': round(statistics.pstdev(values), 4), 'min': round(values[0], 4),
            'p10': round(values[int((len(values)-1)*.1)], 4),
            'p90': round(values[int((len(values)-1)*.9)], 4), 'max': round(values[-1], 4),
            'mode_share': round(Counter(values).most_common(1)[0][1]/len(values), 4)}


def distributions(rows, entity_key, minimum_games=20):
    groups = defaultdict(list)
    for row in rows:
        groups[row[entity_key]].append(row)
    result = {}
    for field in FIELDS:
        within = []
        for group in groups.values():
            values = [r[field] for r in group if r.get(field) is not None]
            if len(values) >= minimum_games:
                within.append(statistics.pstdev(values))
        result[field] = {'all_games': summary(r.get(field) for r in rows),
                         'within_entity_sd': summary(within)}
    return result


def retention_difference(before_ids, after_ids):
    a, b = set(before_ids), set(after_ids)
    return {'v8_only': sorted(a-b), 'v9_only': sorted(b-a)}


def relevant_transactions(rows, pid, endpoint):
    return [r for r in rows if r.get('date', '') <= endpoint
            and pid in json.dumps(r.get('assets', {}))]


def transaction_summary(row):
    contract = row.get('assets', {}).get('contract') or {}
    return {'id': row['id'], 'date': row.get('date'), 'type': row.get('transaction_type'),
            'teams': row.get('teams'), 'annual_salary': contract.get('annual_salary'),
            'years': contract.get('years'), 'notes': row.get('notes')}


def player_trace(pid, snapshots, transactions, markets, endpoint):
    transitions, previous = [], object()
    for snapshot in snapshots:
        if snapshot['date'] > endpoint:
            continue
        row = next((p for p in snapshot['players'] if p['id'] == pid), None)
        marker = (row.get('team_id'), row['rostered']) if row else None
        if marker != previous:
            transitions.append({'date': snapshot['date'], 'player': row})
        previous = marker
    latest = next((p for p in snapshots[-1]['players'] if p['id'] == pid), None)
    exits = {r['id']: r for s in snapshots for r in s.get('league_exit_records', [])
             if r.get('player_id') == pid and r.get('date', '') <= endpoint}
    retirements = {r['id']: r for s in snapshots for r in s.get('retirement_reports', [])
                   if pid in json.dumps(r) and r.get('date', '') <= endpoint}
    offers = {o['id']: o for m in markets for o in m.get('offers', []) if o['player_id'] == pid}
    role_samples = [{'date': s['date'], 'player': p} for s in snapshots if s['date'] <= endpoint
                    for p in s['players'] if p['id'] == pid]
    pre_cut = next((s for s in reversed(snapshots) if s['date'] < endpoint), None)
    context = None
    if pre_cut:
        before = next((p for p in pre_cut['players'] if p['id'] == pid), None)
        if before and before['rostered']:
            tid = before['team_id']
            retained = {p['id'] for p in snapshots[-1]['players'] if p['rostered'] and p['team_id'] == tid}
            roster = [p for p in pre_cut['players'] if p['rostered'] and p['team_id'] == tid]
            context = {'date': pre_cut['date'], 'team_id': tid, 'roster_count_before': len(roster),
                       'roster_count_after': len(retained),
                       'players': [{**p, 'retained_at_endpoint': p['id'] in retained} for p in roster]}
    return {'endpoint': latest, 'transitions': transitions, 'role_samples': role_samples,
            'last_pre_endpoint_roster': context,
            'transactions': [transaction_summary(t) for t in relevant_transactions(transactions, pid, endpoint)],
            'league_exits': list(exits.values()), 'retirement_reports': list(retirements.values()),
            'offers': list(offers.values())}


def summer_signing_cuts(transactions):
    signed = {}
    cuts = []
    for row in transactions:
        date = row.get('date', '')
        pid = row.get('assets', {}).get('player_id')
        if row.get('transaction_type') == 'free_agent_signing' and '2027-07-01' <= date <= '2027-09-30':
            signed[pid] = row
        elif row.get('transaction_type') == 'roster_cut' and date == '2027-10-01' and pid in signed:
            signing = signed[pid]
            # A subsequent trade can change the reason for a cut. Identify
            # same-team signing/cutdown churn separately from traded players.
            cuts.append({'player_id': pid, 'signing': transaction_summary(signing),
                         'cut': transaction_summary(row), 'same_team': signing.get('teams') == row.get('teams')})
    return {'summer_signings': len(signed), 'signed_then_cut_october_1': len(cuts), 'cases': cuts}


def career(directory):
    run = read(directory/'run.json')
    if run.get('status') != 'completed':
        raise ValueError(f'Career is not completed: {directory}')
    path = Path(run['save_path'])
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Only this audit directory may be inspected')
    saved = read(path)
    validate_save_components(path, saved)
    signatures = {str(p): sha(p) for p in (path, path.parent/saved['history_store']['path'])}
    logs = history(path, saved, 'team_game_logs')
    dates = {r['game_id']: r['date'] for r in logs if '2026-10-01' <= r['date'] <= '2027-04-12'}
    games = [r for r in history(path, saved, 'game_results') if r['game_id'] in dates]
    if len(games) != 1230:
        raise ValueError(f'Expected 1230 regular-season games, got {len(games)}')
    teams, players, errors, cross_errors = [], [], Counter(), Counter()
    for game in games:
        errors.update(e[0] for e in game_errors(game))
        for t in game['team_lines']:
            teams.append(with_percentages({**t, 'game_id': game['game_id'], 'date': dates[game['game_id']]}))
            opp = next(o for o in game['team_lines'] if o['team_id'] != t['team_id'])
            cross_errors['assists_above_made_field_goals'] += t['assists'] > t['fgm']
            cross_errors['steals_above_opponent_turnovers'] += t['steals'] > opp['turnovers']
            cross_errors['blocks_above_opponent_missed_shots'] += t['blocks'] > opp['fga']-opp['fgm']
        players.extend(with_percentages({**p, 'game_id': game['game_id'], 'date': dates[game['game_id']]})
                       for p in game['player_lines'] if p['minutes'] > 0)
    snaps = [read(p) for p in sorted((directory/'observations').glob('*.json.gz'))]
    snaps = [s for s in snaps if s['date'] <= '2027-10-01']
    markets = [read(p) for p in sorted((directory/'markets').glob('*.json.gz'))]
    markets = [m for m in markets if m['date'] <= '2027-10-01']
    by_player = defaultdict(list)
    for row in players:
        by_player[row['player_id']].append(row)
    stable_ids = {pid for pid, rows in by_player.items() if len(rows) >= 30
                  and statistics.fmean(r['minutes'] for r in rows) >= 20
                  and statistics.pstdev(r['minutes'] for r in rows) <= 4}
    samples = {}
    for name in ('Nikola Jokic', 'Stephen Curry', 'Zach Edey', 'Jarrett Allen', "Day'Ron Sharpe", 'Deandre Ayton'):
        rows = sorted((r for r in players if r['player_name'] == name), key=lambda r: (r['date'], r['game_id']))
        samples[name] = {'games': len(rows), 'stats': {f: summary(r.get(f) for r in rows) for f in FIELDS},
                         'first_ten': [{k: r.get(k) for k in ('date', 'minutes', *FIELDS)} for r in rows[:10]]}
    result = {'regular_games': len(games), 'accounting_errors': dict(errors),
              'cross_stat_errors': dict(cross_errors), 'team_distributions': distributions(teams, 'team_id'),
              'player_distributions': distributions(players, 'player_id'),
              'stable_role_players': len(stable_ids),
              'stable_role_distributions': distributions([r for r in players if r['player_id'] in stable_ids], 'player_id'),
              'samples': samples, 'source_hashes': signatures}
    transactions = history(path, saved, 'transaction_logs')
    result['summer_signing_cuts'] = summer_signing_cuts(transactions)
    return result, snaps, transactions, markets, saved


def parse_espn_game(raw, date, game_id):
    """Use named stat labels; ESPN now calls its FG field 'FG', not 'FGM-A'."""
    rows = []
    for team in raw['boxscore']['players']:
        for group in team['statistics']:
            labels = group['labels']
            for entry in group['athletes']:
                if entry.get('didNotPlay') or not entry.get('stats'):
                    continue
                stats = dict(zip(labels, entry['stats'], strict=True))
                row = {'player_id': entry['athlete']['id'], 'player_name': entry['athlete']['displayName'],
                       'team_id': team['team']['id'], 'date': date, 'game_id': game_id}
                for label, key in (('PTS', 'points'), ('REB', 'rebounds'), ('AST', 'assists'),
                                   ('TO', 'turnovers'), ('STL', 'steals'), ('BLK', 'blocks'), ('MIN', 'minutes')):
                    row[key] = float(stats[label])
                for label, made, attempts in (('FG', 'fgm', 'fga'), ('3PT', 'fg3m', 'fg3a'), ('FT', 'ftm', 'fta')):
                    row[made], row[attempts] = map(int, stats[label].split('-'))
                if row['points'] != 2*row['fgm']+row['fg3m']+row['ftm']:
                    raise ValueError('Invalid ESPN scoring identity')
                rows.append(row)
    if len({r['team_id'] for r in rows}) != 2:
        raise ValueError('Incomplete ESPN box score')
    return rows


def fetch_reference(out, count):
    cache = out/f'espn-reference-{count}.json'
    if cache.exists():
        return read(cache)
    schedule = [g for g in read(ROOT/'data/research/game_boxscores_2025_26.json')['games']
                if g.get('phase') == 'regular']
    schedule = sorted({g['game_id']: g for g in schedule}.values(), key=lambda g: (g['date'], g['game_id']))
    selected = [schedule[round(i*(len(schedule)-1)/(count-1))] for i in range(count)]
    players, teams, sources, failures = [], [], [], []
    for i, game in enumerate(selected):
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game['game_id']}"
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                raw = json.load(response)
            rows = parse_espn_game(raw, game['date'], game['game_id'])
            actual = {c['team']['id']: int(c['score']) for c in raw['header']['competitions'][0]['competitors']}
            grouped = defaultdict(list)
            for row in rows:
                grouped[row['team_id']].append(row)
            game_teams = []
            for tid, group in grouped.items():
                total = {k: sum(r[k] for r in group) for k in ('points', 'rebounds', 'assists', 'turnovers',
                         'steals', 'blocks', 'fgm', 'fga', 'fg3m', 'fg3a', 'ftm', 'fta')}
                if total['points'] != actual[tid]:
                    raise ValueError('Player points do not match final team score')
                game_teams.append(with_percentages({**total, 'team_id': tid, 'game_id': game['game_id'], 'date': game['date']}))
            teams.extend(game_teams)
            players.extend(with_percentages(r) for r in rows)
            sources.append(url)
        except (ValueError, KeyError, OSError) as exc:
            failures.append({'url': url, 'error': str(exc)})
        if (i+1) % 12 == 0:
            print(f'ESPN reference: {i+1}/{count} inspected', flush=True)
    result = {'scope': 'Evenly spaced cached regular-season game IDs, freshly fetched ESPN box scores. '
                       'Descriptive historical sample, not matched rosters or a tuning target. Turnovers sum player turnovers, excluding team turnovers.',
              'requested_games': count, 'games': len(sources), 'failures': failures, 'sources': sources,
              'team_distributions': distributions(teams, 'team_id', minimum_games=2),
              'player_distributions': distributions(players, 'player_id', minimum_games=2)}
    cache.write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, default=BATCH)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference-games', type=int, default=0)
    parser.add_argument('--reference-cache', type=Path, help='Reuse a prior freshly fetched reference sample')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Preserve previous evidence; choose a new output directory')
    if args.reference_games and args.reference_games < 2:
        parser.error('Reference sample requires at least two games')
    if args.reference_games and args.reference_cache:
        parser.error('Choose either a fresh reference fetch or an existing sample')
    args.output.mkdir(parents=True)
    root = args.batch/'runtime/output/offense-season'
    initial_review = read(args.batch/'review.json')
    report = {'scope': 'Saved first-season evidence only; no game changes or new simulations. '
              'Within-player/team variation is distinct from pooled league variation. '
              'Stable-role players have >=30 games, mean minutes >=20 and minutes SD <=4. '
              'Observation transitions bracket dates; they are not exact decision-time snapshots.', 'cases': {}}
    hashes = {}
    for seed in (29, 913):
        ref = read(root/f'references/v8-{seed}.json.gz')
        analyses, sources = {}, {}
        for label, directory in (('v8', OLD/f'career-{seed}'), ('v9', root/f'career-{seed}')):
            result, snaps, tx, markets, saved = career(directory)
            analyses[label] = result
            hashes.update(result['source_hashes'])
            sources[label] = snaps, tx, markets, saved
            print(f'{seed} {label}: {result["regular_games"]} existing games inspected', flush=True)
        cohort = initial_review['cases'][str(seed)]['retention']['nonspacing_centers']
        # Include every shared starting center lost in either arm, not just the
        # net difference: departures common to both models also need explaining.
        kept_both = set(cohort['v8']['retained_ids']) & set(cohort['v9']['retained_ids'])
        from nba_gm_data.offense import offensive_profile
        canonical = read(root/'canonical.json.gz')
        traits = defaultdict(dict)
        for t in canonical['traits']:
            traits[t['player_id']][t['trait_key']] = t['value']
        ids = set()
        for player in canonical['players']:
            f = offensive_profile(canonical, player, traits[player['id']])
            if str(player.get('position') or '').upper().split('/')[0] == 'C' and f['three_per36'] < 1.5:
                if not (f['post_share'] >= .12 and f['post_creation'] >= 55):
                    ids.add(player['id'])
        ids &= {p['id'] for p in ref['start']['players'] if p['rostered']}
        assert len(ids) == cohort['cohort_size']
        traces = {}
        for pid in sorted(ids-kept_both):
            traces[pid] = {}
            for label, (snaps, tx, markets, saved) in sources.items():
                trace = player_trace(pid, snaps, tx, markets, '2027-10-01')
                # V8 careers end a year later; do not use their final status to
                # infer a first-year retirement or free-agent outcome.
                trace['season_stats'] = next((p for p in initial_review['cases'][str(seed)][label]['players'] if p['id'] == pid), None)
                traces[pid][label] = trace
        report['cases'][str(seed)] = {'comparison': retention_difference(cohort['v8']['retained_ids'], cohort['v9']['retained_ids']),
                                     'retention_traces': traces, 'distributions': analyses}
    if args.reference_games:
        report['reference'] = fetch_reference(args.output, args.reference_games)
    elif args.reference_cache:
        report['reference'] = read(args.reference_cache)
        report['reference_cache_sha256'] = sha(args.reference_cache)
    report['input_hashes_unchanged'] = all(sha(Path(p)) == value for p, value in hashes.items())
    if not report['input_hashes_unchanged']:
        raise RuntimeError('Completed career evidence changed during review')
    (args.output/'review.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Read-only review written to {args.output}/review.json', flush=True)


if __name__ == '__main__':
    main()
