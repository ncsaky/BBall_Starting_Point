"""Conditional five-player scoring timelines; no feedback into game outcomes."""
import math
import random


FIELDS = ('minutes', 'fgm', 'fg3m', 'ftm')
VERSION = 'lineup_scoring_v1'


def scoring_snapshot(lines):
    return {row['player_id']: {key: row.get(key, 0) for key in FIELDS} for row in lines}


def _apportion(remaining, duration, time_left):
    quotas = {pid: ticks*duration/time_left for pid, ticks in remaining.items()}
    assigned = {pid: math.floor(value) for pid, value in quotas.items()}
    order = sorted(remaining, key=lambda pid: (-(quotas[pid]-assigned[pid]), pid))
    for pid in order[:5*duration-sum(assigned.values())]:
        assigned[pid] += 1
    return assigned


def _minutes(rows, duration):
    ticks = {pid: round(float(row['minutes'])*100) for pid, row in rows.items() if float(row['minutes']) > 0}
    if len(ticks) < 5 or any(t > duration+1 for t in ticks.values()):
        raise ValueError('insufficient_five_player_minutes')
    if abs(sum(ticks.values())-5*duration) > len(ticks):
        raise ValueError('incomplete_team_minutes')
    # Only repair hundredth-minute rounding in the tracking copy.
    ticks = {pid: min(duration, value) for pid, value in ticks.items()}
    difference = 5*duration-sum(ticks.values())
    while difference:
        direction = 1 if difference > 0 else -1
        eligible = [pid for pid in ticks if (ticks[pid] < duration if direction > 0 else ticks[pid] > 1)]
        if not eligible:
            break
        eligible.sort(key=lambda pid: (-direction*(float(rows[pid]['minutes'])*100-ticks[pid]), pid))
        for pid in eligible[:abs(difference)]:
            ticks[pid] += direction
            difference -= direction
    if difference or any(t > duration for t in ticks.values()):
        raise ValueError('infeasible_team_minutes')
    return ticks


def _period_stints(minutes, duration, offset, rng):
    starters = sorted(minutes, key=lambda pid: (-minutes[pid], pid))[:5]
    bench_max = max((v for pid, v in minutes.items() if pid not in starters), default=0)
    reserve = min(100, min(minutes[pid] for pid in starters)//2, (duration-bench_max)//2)
    width = duration-2*reserve
    intervals = []
    for pid in starters:
        if reserve:
            intervals.extend([(0, reserve, pid), (duration-reserve, duration, pid)])
    jobs = [(pid, ticks-(2*reserve if pid in starters else 0)) for pid, ticks in minutes.items()]
    jobs = [job for job in jobs if job[1] > 0]
    rng.shuffle(jobs)
    # Wrap jobs across five equal lanes. Each job is at most one lane long,
    # so its wrapped portions cannot put one player on court twice at once.
    cursor = 0
    for pid, ticks in jobs:
        start = cursor % width
        first = min(ticks, width-start)
        intervals.append((reserve+start, reserve+start+first, pid))
        if ticks > first:
            intervals.append((reserve, reserve+ticks-first, pid))
        cursor += ticks
    boundaries = sorted({0, duration, *(v for start, end, _ in intervals for v in (start, end))})
    result = []
    for start, end in zip(boundaries, boundaries[1:]):
        active = tuple(sorted(pid for lo, hi, pid in intervals if lo <= start < hi))
        if len(active) != 5 or len(set(active)) != 5:
            raise ValueError('infeasible_five_player_stint')
        result.append([offset+start, offset+end, active])
    return result


def _team_stints(rows, duration, offset, rng, regulation):
    remaining = _minutes(rows, duration)
    result = []
    lengths = [1200]*4 if regulation else [duration]
    time_left = duration
    for length in lengths:
        allocation = _apportion(remaining, length, time_left)
        result.extend(_period_stints(allocation, length, offset, rng))
        remaining = {pid: ticks-allocation[pid] for pid, ticks in remaining.items()}
        time_left -= length
        offset += length
    return result


def _combined(first, second):
    boundaries = sorted({v for rows in (first, second) for start, end, _ in rows for v in (start, end)})
    indices = [0, 0]
    output = []
    for start, end in zip(boundaries, boundaries[1:]):
        for i, rows in enumerate((first, second)):
            while rows[indices[i]][1] <= start:
                indices[i] += 1
        lineups = [first[indices[0]][2], second[indices[1]][2]]
        if output and output[-1][2:4] == lineups:
            output[-1][1] = end
        else:
            output.append([start, end, *lineups, 0, 0])
    return output


def _build(lines, teams, seed, snapshots, defense):
    rng = random.Random(seed)
    tids = sorted(t['team_id'] for t in teams)
    ids = sorted(row['player_id'] for row in lines)
    if len(ids) != len(set(ids)) or len(tids) != 2 or len(set(tids)) != 2:
        raise ValueError('invalid_participants')
    by_id = {row['player_id']: row for row in lines}
    if any(row['team_id'] not in tids for row in lines):
        raise ValueError('invalid_participants')
    for row in lines:
        if not math.isfinite(float(row.get('minutes') or 0)) or any(row.get(k) is None for k in ('fgm', 'fg3m', 'ftm')):
            raise ValueError('incomplete_box_score')
        if row['points'] != 2*row['fgm']+row['fg3m']+row['ftm']:
            raise ValueError('inconsistent_scoring')
    periods = int(max(t.get('overtime_periods', 0) for t in teams))
    if periods and (not snapshots or len(snapshots) != periods+1):
        raise ValueError('missing_overtime_scoring')
    frames = snapshots if periods else [scoring_snapshot(lines)]
    stints, event_log = [], []
    previous = {pid: dict.fromkeys(FIELDS, 0) for pid in ids}
    offset = 0
    for part, cumulative in enumerate(frames):
        duration = 4800 if part == 0 else 500
        delta = {pid: {k: cumulative[pid][k]-previous[pid][k] for k in FIELDS} for pid in ids}
        groups = [{pid: delta[pid] for pid in ids if by_id[pid]['team_id'] == tid} for tid in tids]
        rotations = [_team_stints(group, duration, offset, rng, part == 0) for group in groups]
        combined = _combined(*rotations)
        for side, group in enumerate(groups):
            for pid, row in group.items():
                twos, threes, frees = row['fgm']-row['fg3m'], row['fg3m'], row['ftm']
                if min(twos, threes, frees) < 0:
                    raise ValueError('inconsistent_period_scoring')
                makes = [2]*twos+[3]*threes+[1]*frees
                eligible = [i for i, stint in enumerate(combined) if pid in stint[2+side]]
                if makes and not eligible:
                    raise ValueError('scoring_without_minutes')
                weights = []
                for index in eligible:
                    stint = combined[index]
                    opposing = stint[3-side]
                    grade = sum(defense.get(p, 60) for p in opposing)/5
                    ease = max(.65, min(1.5, 1+(60-grade)*.01))
                    weights.append((stint[1]-stint[0])*ease)
                for points in makes:
                    index = rng.choices(eligible, weights, k=1)[0]
                    stint = combined[index]
                    tick = rng.randrange(stint[0], stint[1])
                    stint[4+side] += points
                    event_log.append([tick, pid, points, side])
        stints.extend(combined)
        previous = cumulative
        offset += duration
    if previous != scoring_snapshot(lines):
        raise ValueError('period_totals_mismatch')
    totals = {tid: sum(r['points'] for r in lines if r['team_id'] == tid) for tid in tids}
    if any(totals[t['team_id']] != t['points'] for t in teams):
        raise ValueError('team_score_mismatch')
    scores = [0, 0]
    stats = {pid: [0, 0] for pid in ids}
    for start, end, first, second, p0, p1 in stints:
        scores[0] += p0
        scores[1] += p1
        for side, lineup in enumerate((first, second)):
            for pid in lineup:
                stats[pid][0] += (p0, p1)[side]
                stats[pid][1] += (p1, p0)[side]
    if scores != [totals[tid] for tid in tids]:
        raise ValueError('timeline_score_mismatch')
    indices = {pid: i for i, pid in enumerate(ids)}
    compact = [[a, b, [indices[p] for p in first], [indices[p] for p in second], p0, p1]
               for a, b, first, second, p0, p1 in stints]
    tracking = {'status': 'tracked', 'version': VERSION, 'basis': 'modeled_minutes_and_made_shots',
                'ticks_per_minute': 100, 'duration_ticks': offset, 'team_ids': tids,
                'player_ids': ids, 'stints': compact}
    return stats, tracking, sorted(event_log)


def track_plus_minus(lines, teams, seed, *, snapshots=None, defense=None, include_events=False):
    """Populate new games only; unsupported boxes stay unavailable, never +0."""
    try:
        stats, tracking, events = _build(lines, teams, seed, snapshots, defense or {})
    except ValueError as exc:
        for row in lines:
            row['plus_minus'] = None
            row.pop('on_court_points_for', None)
            row.pop('on_court_points_against', None)
        return {'status': 'unavailable', 'version': VERSION, 'reason': str(exc)}
    for row in lines:
        scored, allowed = stats[row['player_id']]
        row.update(plus_minus=scored-allowed, on_court_points_for=scored, on_court_points_against=allowed)
    if include_events:
        tracking['scoring_events'] = events
    return tracking
