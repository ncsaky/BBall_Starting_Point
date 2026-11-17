"""Reconcile aggregate box scores without changing shooting, minutes or RNG.

Without a play-by-play FT sequence, missed FGA plus missed FTA is only an
upper bound on rebound opportunities: some free throws are not reboundable,
and dead-ball/team rebounds need not appear in player rebound totals.
"""
import math


COUNT_FIELDS = ('points', 'fgm', 'fga', 'fg3m', 'fg3a', 'ftm', 'fta',
                'rebounds', 'assists', 'turnovers', 'steals', 'blocks')


def reduced_counts(values, target, identities):
    """Largest-remainder reduction; never invent events or exceed a capacity."""
    total = sum(values)
    target = max(0, min(int(target), total))
    if total <= target:
        return list(values)
    quotas = [v*target/total for v in values]
    assigned = [math.floor(v) for v in quotas]
    order = sorted(range(len(values)), key=lambda i: (-(quotas[i]-assigned[i]), str(identities[i])))
    for i in order[:target-sum(assigned)]:
        assigned[i] += 1
    return assigned


def reduce_stat(lines, key, limit, capacities=None):
    values = [max(0, int(row.get(key) or 0)) if row.get('minutes', 0) > 0 else 0 for row in lines]
    if capacities is not None:
        values = [min(v, max(0, int(cap))) for v, cap in zip(values, capacities, strict=True)]
    assigned = reduced_counts(values, limit, [r.get('player_id', '') for r in lines])
    for row, value in zip(lines, assigned, strict=True):
        row[key] = value


def missed_shots(team):
    return max(0, team['fga']-team['fgm']) + max(0, team['fta']-team['ftm'])


def reconcile_box_score(player_lines, team_lines):
    if len(team_lines) != 2:
        raise ValueError('Box-score reconciliation requires two teams')
    grouped = [[p for p in player_lines if p['team_id'] == t['team_id']] for t in team_lines]
    for row in player_lines:
        if float(row.get('minutes') or 0) <= 0:
            for key in ('rebounds', 'assists', 'turnovers', 'steals', 'blocks', 'rim_attempts'):
                if key in row:
                    row[key] = 0
    # Work from finalized post-overtime shooting, not stale pre-OT summaries.
    for team, lines in zip(team_lines, grouped, strict=True):
        for key in COUNT_FIELDS:
            team[key] = sum(int(p.get(key) or 0) for p in lines)
    for i, (team, lines) in enumerate(zip(team_lines, grouped, strict=True)):
        opponent = team_lines[1-i]
        reduce_stat(lines, 'assists', team['fgm'], [team['fgm']-p['fgm'] for p in lines])
        reduce_stat(lines, 'steals', opponent['turnovers'])
        reduce_stat(lines, 'blocks', max(0, opponent['fga']-opponent['fgm']))
        for row in lines:
            if 'rim_attempts' in row:
                row['rim_attempts'] = min(max(0, int(row['rim_attempts'])), row['fga']-row['fg3a'])

    offensive = [min(max(0, int(t.get('offensive_rebounds') or 0)), t['rebounds'], missed_shots(t))
                 for t in team_lines]
    defensive = [t['rebounds']-o for t, o in zip(team_lines, offensive, strict=True)]
    # Both sides compete for each shooting team's same pool of misses.
    for i, team in enumerate(team_lines):
        offensive[i], defensive[1-i] = reduced_counts(
            [offensive[i], defensive[1-i]], missed_shots(team),
            [team['team_id'], team_lines[1-i]['team_id']])
    for i, (team, lines) in enumerate(zip(team_lines, grouped, strict=True)):
        reduce_stat(lines, 'rebounds', offensive[i]+defensive[i])
        for key in ('rebounds', 'assists', 'steals', 'blocks'):
            team[key] = sum(row[key] for row in lines)
        team['offensive_rebounds'] = offensive[i]
        team['defensive_rebounds'] = defensive[i]


def opportunity_errors(player_lines, team_lines):
    """Additional basketball constraints beyond arithmetic/scoring identities."""
    errors = []
    if len(team_lines) != 2:
        return [('team_count', 'expected two teams')]
    for team in team_lines:
        opponent = next(t for t in team_lines if t['team_id'] != team['team_id'])
        tid = team['team_id']
        for row in [p for p in player_lines if p['team_id'] == tid]:
            if row['assists'] > team['fgm']-row['fgm']:
                errors.append(('assists_without_teammate_baskets', row['player_id']))
            if row.get('rim_attempts', 0) > row['fga']-row['fg3a']:
                errors.append(('rim_attempts_above_two_point_attempts', row['player_id']))
        for key, limit in (('assists', team['fgm']), ('steals', opponent['turnovers']),
                           ('blocks', opponent['fga']-opponent['fgm'])):
            if team[key] > limit:
                errors.append((f'{key}_above_opportunities', tid))
        if team['offensive_rebounds']+team['defensive_rebounds'] != team['rebounds']:
            errors.append(('rebound_split', tid))
        if team['offensive_rebounds']+opponent['defensive_rebounds'] > missed_shots(team):
            errors.append(('rebounds_above_missed_shots', tid))
    return errors
