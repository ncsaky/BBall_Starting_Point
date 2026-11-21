"""League-relative windows and save-owned intent, not permanent source labels."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import math


VERSION = 2
LEGACY_PHASE = {'peak': 'contending', 'entering': 'developing', 'exiting': 'retooling', 'rebuilding': 'rebuilding'}

# How much the season's results move a team's strength (trade 2b). A team's strength was its roster rating plus at most
# +-3 points for its record, so a 29-18 team could stay "rebuilding" and a 15-34 team "on the rise" all season. Now the
# record (point margin and winning percentage, as league z-scores) is blended with the roster rating. The record's
# weight grows with games played: 0.85 * games / (games + 15), so 0.42 after 15 games, 0.62 after 40, 0.69 at the
# deadline and 0.72 at season end (the roster still counts: injuries heal, trades change it). In the NBA, team point
# margin settles quickly (game-to-game noise about 12.5 points against a true-talent spread of about 4.5, so roughly
# 8 games give a half-reliable read); 15 is deliberately slower because the sim's roster rating is itself informative.
# The first two-season test with a lighter weight (at most 0.75, half at 20 games) still had Charlotte "rebuilding"
# at 35-17 on the deadline: the game's roster rating predicts its own results only loosely.
RECORD_WEIGHT_MAX = 0.85
RECORD_WEIGHT_GAMES = 15.0
# And a plain guard from the standings, after RECORD_GUARD_GAMES games in season: a team with a top-third record is
# never labelled rebuilding, and a team with a bottom-third record is never labelled contending or on the rise (it is
# rebuilding, or retooling if its core is aging).
RECORD_GUARD_GAMES = 25
# From July to September the records on file are last season's and the rosters have changed: they count for at most
# this much. Through the playoffs and the draft (to June) the finished season's record still describes the roster.
OFFSEASON_RECORD_WEIGHT = 0.3
# Labels do not flip on small moves: a team keeps its previous label unless the new one still holds with its
# strength moved 1 point (and its trend 0.3) back toward the old label.
HYSTERESIS_STRENGTH = 1.0
HYSTERESIS_TREND = 0.3
# Distance from contending, 0 to 1: how far the team's strength sits below the contender tier (the 4th-best team),
# 0 within 1 point of it and 1 at 6 points or more below. Peak teams are 0. Used to scale how much a team still values
# a veteran's current production (transactions.veteran_present_factor).
CONTEND_LINE_RANK = 4
CONTEND_GAP_FREE = 1.0
CONTEND_GAP_FULL = 6.0


def _record_strengths(canonical, rows):
    """Each team's strength implied by its record (league z-scores of point margin and win share mapped onto the
    roster-strength scale) and the weight that record gets."""
    records = canonical.get('save_team_records') or {}
    today = str((canonical.get('meta') or {}).get('current_date') or '')
    month = int(today[5:7]) if len(today) >= 7 and today[5:7].isdigit() else 0
    facts = {}
    for tid in rows:
        record = records.get(tid) or {}
        wins, losses = float(record.get('wins') or 0), float(record.get('losses') or 0)
        games = wins + losses
        if games < 1:
            continue
        margin = (float(record.get('points_for') or 0) - float(record.get('points_against') or 0)) / games
        facts[tid] = (games, wins / games, margin)
    if len(facts) < 4:
        return {}
    def z_scores(index, floor):
        values = [f[index] for f in facts.values()]
        mean = sum(values) / len(values)
        spread = max(floor, (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5)
        return {tid: (f[index] - mean) / spread for tid, f in facts.items()}
    z_win, z_margin = z_scores(1, 0.08), z_scores(2, 2.5)
    strengths = [row['strength'] for row in rows.values()]
    mean_s = sum(strengths) / len(strengths)
    sd_s = max(1.0, (sum((s - mean_s) ** 2 for s in strengths) / len(strengths)) ** 0.5)
    out = {}
    for tid, (games, _, _) in facts.items():
        weight = RECORD_WEIGHT_MAX * games / (games + RECORD_WEIGHT_GAMES)
        if 7 <= month <= 9:
            weight = min(weight, OFFSEASON_RECORD_WEIGHT)
        z = 0.6 * z_margin[tid] + 0.4 * z_win[tid]
        out[tid] = (mean_s + z * sd_s, weight, z, games if not 7 <= month <= 9 else 0.0)
    return out


def _classify_window(row, rank, share, n_teams, best, future_best):
    """The window label from a team's strength, rank, trend and core (unchanged rules; see window_assessments)."""
    young_window = (rank <= 12 and len(row['ready_young_core']) >= 2
                    and any(age <= 27 and quality >= row['_elite']-4 for age, quality in row['ready_young_core']))
    if rank <= 6 and share >= 1.3/n_teams and best-row['strength'] <= 4.5 and row['strength'] >= 60:
        return 'peak'
    if young_window:
        return 'entering'
    if row['trend'] < -.5 and (rank <= max(12, n_teams*.65) or row['credible_anchors']):
        return 'exiting'
    if row['credible_anchors'] >= 2 or rank <= 12 or (row['core_candidates'] and row['trend'] > .5 and future_best-row['future_strength'] <= 7):
        return 'entering'
    return 'rebuilding'


def window_assessments(canonical, states, valuations):
    players = {p['id']: p for p in canonical.get('players', [])}
    team_ids = {s.team_id for s in states}
    by_team = {}
    for v in valuations:
        if players.get(v.player_id, {}).get('team_id') in team_ids and not players[v.player_id].get('_inactive_player'):
            by_team.setdefault(v.team_id, []).append(v)
    league_quality = sorted(v.on_court_value for v in valuations
                            if players.get(v.player_id, {}).get('team_id') in team_ids
                            and not players[v.player_id].get('_inactive_player'))
    elite = league_quality[int((len(league_quality)-1)*.90)] if league_quality else 70
    rows = {}
    for state in states:
        values = sorted(by_team.get(state.team_id, []), key=lambda v: (-v.on_court_value, v.player_id))
        core = []
        future_deltas = []
        ready_young_core = []
        for v in values:
            p = players.get(v.player_id, {})
            age = float(p.get('display_age', p.get('age')) or 27)
            credible_project = age <= 25 and v.development_upside >= 10 and v.on_court_value >= elite-12
            if v.on_court_value >= elite-4 or credible_project:
                core.append(v.player_id)
            if age <= 28 and v.on_court_value >= elite-5:
                ready_young_core.append((age, v.on_court_value))
            if len(future_deltas) < 5 and (p.get('minutes_projection') != 0 or p.get('_trade_value_unavailable')):
                growth = min(5, v.development_upside*.20) if age <= 26 else 0
                decline = max(0, age-29)*.65 + max(0, v.health_risk-12)*.08
                future_deltas.append(growth-decline)
        # A strong ordinary starter isn't automatically a franchise foundation.
        delta = sum(future_deltas)/len(future_deltas) if future_deltas else -3
        rows[state.team_id] = {'strength': state.contention_ceiling, 'roster_strength': state.contention_ceiling,
                               'trend': delta, 'core_candidates': core,
                               'ready_young_core': ready_young_core,
                               'credible_anchors': sum(v.on_court_value >= elite for v in values[:5]),
                               '_elite': elite}
    if not rows:
        return rows
    # The season's results (trade 2b): blend the record-implied strength into the roster rating.
    record_facts = _record_strengths(canonical, rows)
    standing = {tid: 1 + sum(f[2] > fact[2] for f in record_facts.values()) for tid, fact in record_facts.items()}
    for tid, (record_strength, weight, _, _) in record_facts.items():
        row = rows[tid]
        row['strength'] = (1 - weight) * row['roster_strength'] + weight * record_strength
        row['record_weight'] = round(weight, 3)
    for row in rows.values():
        row['future_strength'] = row['strength'] + row['trend']
    plans = canonical.get('team_plans') or {}
    best = max(r['strength'] for r in rows.values())
    future_best = max(r['future_strength'] for r in rows.values())
    mass = sum(math.exp((r['strength']-best)/3.5) for r in rows.values())
    ordered = sorted((r['strength'] for r in rows.values()), reverse=True)
    contend_line = ordered[min(CONTEND_LINE_RANK, len(ordered)) - 1]
    n_teams = len(rows)

    def classify(row, strength, trend):
        trial = dict(row, strength=strength, trend=trend, future_strength=strength + trend)
        rank = 1 + sum(r['strength'] > strength for t, r in rows.items() if r is not row)
        share = math.exp((strength-best)/3.5)/mass
        return _classify_window(trial, rank, share, n_teams, best, future_best), rank, share

    for tid, row in rows.items():
        # One aging star can make near-term strength decline while a capable
        # young foundation is still entering its window. Keep both signals.
        phase, rank, share = classify(row, row['strength'], row['trend'])
        previous = (plans.get(tid) or {}).get('window_phase')
        if previous and previous != phase and previous in LEGACY_PHASE and len(rows) >= 4:
            if any(classify(row, row['strength'] + s * HYSTERESIS_STRENGTH, row['trend'] + t * HYSTERESIS_TREND)[0] == previous
                   for s in (-1, 0, 1) for t in (-1, 0, 1)):
                phase = previous
        fact = record_facts.get(tid)
        if fact and fact[3] >= RECORD_GUARD_GAMES:
            if standing[tid] <= n_teams / 3 and phase == 'rebuilding':
                phase = 'exiting' if row['trend'] < -.5 else 'entering'
            elif standing[tid] > n_teams * 2 / 3 and phase in {'peak', 'entering'}:
                phase = 'exiting' if row['trend'] < -.5 else 'rebuilding'
        gap = contend_line - row['strength']
        distance = 0.0 if phase == 'peak' else min(1.0, max(0.0, (gap - CONTEND_GAP_FREE) / (CONTEND_GAP_FULL - CONTEND_GAP_FREE)))
        row.update(window_phase=phase, league_rank=rank, contender_index=round(share*100, 3),
                   contend_distance=round(distance, 3))
        row['strength'] = round(row['strength'], 3)
        row['roster_strength'] = round(row['roster_strength'], 3)
        row['future_strength'] = round(row['future_strength'], 3)
        row['trend'] = round(row['trend'], 3)
        row.pop('_elite', None)
    return rows


def core_commitment(canonical, team_id, player_id):
    if team_id in canonical.get('_human_team_ids', []):
        return False
    plan = canonical.get('team_plans', {}).get(team_id, {})
    today = str(canonical.get('meta', {}).get('current_date') or '')
    return bool(player_id in plan.get('core_ids', []) and today and today <= plan.get('commit_until', '')
                and not plan.get('review_exception'))


def acquisition_date(canonical, team_id, core_ids, values):
    from .transactions import transaction_log_flows
    found = ''
    for log in canonical.get('transaction_logs', []):
        if log.get('transaction_type') != 'trade' or log.get('status') not in {'applied', 'applied_to_save_ledger'}:
            continue
        if str(log.get('date') or '') > str(canonical.get('meta', {}).get('current_date') or ''):
            continue
        flows = next((r for r in transaction_log_flows(log) if r[0] == team_id), None)
        if flows is None:
            continue
        _, outgoing, incoming = flows
        premium_arrival = any(a.get('kind') == 'player' and a.get('id') in core_ids
                              and float(values.get(a['id'], {}).get('player_value') or 0) >= 60 for a in incoming)
        investment = any(a.get('kind') in {'pick', 'pick_swap'} or
                         float(values.get(a.get('id'), {}).get('player_value') or 0) >= 35 for a in outgoing)
        if premium_arrival and investment:
            found = max(found, str(log.get('date') or ''))
    return found


def refresh_team_plans(active, save, stamp):
    """Review on date/roster/injury milestones; never from dashboard reads."""
    from .transactions import with_transaction_context
    if save.get('team_plan_review_date', '') > stamp:
        return False
    signature = hashlib.sha256(json.dumps([
        VERSION, stamp[:7], sorted((p['id'], p.get('team_id')) for p in active.get('players', [])),
        sorted((h.get('player_id'), h.get('return_date')) for h in save.get('health_states', [])
               if h.get('availability_status') == 'out' and h.get('return_date')
               and (date.fromisoformat(h['return_date'])-date.fromisoformat(stamp)).days >= 90),
        save.get('ai_trade_pressure_player_ids', []),
        (save.get('playoff_state') or {}).get('status'),
        len(save.get('transaction_logs', [])),
    ], sort_keys=True).encode()).hexdigest()
    if save.get('team_plan_review_signature') == signature:
        return False
    context = with_transaction_context(active)
    values = {v['player_id']: v for v in context.get('player_asset_valuations', [])}
    owners = {p['id']: p.get('team_id') for p in active.get('players', [])}
    players = {p['id']: p for p in active.get('players', [])}
    plans = save.setdefault('team_plans', {})
    for state in context.get('team_strategic_states', []):
        tid = state['team_id']
        previous = plans.get(tid, {})
        candidates = list(state.get('core_candidates') or [])
        old_core = [pid for pid in previous.get('core_ids', []) if owners.get(pid) == tid]
        # Continuity has slack; a small rating fluctuation cannot erase a core.
        core = sorted(set(candidates) | {pid for pid in old_core if float(values.get(pid, {}).get('on_court_value') or 0) >= 52})
        acquired = max(acquisition_date(context, tid, core, values), previous.get('major_acquisition_date', ''))
        until = previous.get('commit_until')
        if not previous:
            start_year = int(stamp[:4]) if int(stamp[5:7]) >= 7 else int(stamp[:4])-1
            until = f'{start_year+1}-06-30'
        if acquired and acquired > previous.get('major_acquisition_date', ''):
            until = max(until or '', (date.fromisoformat(acquired)+timedelta(days=365)).isoformat())
        exception = None
        for h in save.get('health_states', []):
            if h.get('player_id') in core and h.get('availability_status') == 'out' and h.get('return_date'):
                if (date.fromisoformat(h['return_date'])-date.fromisoformat(stamp)).days >= 90:
                    exception = 'serious_core_injury_review'
        if any(pid in set(save.get('ai_trade_pressure_player_ids') or []) for pid in core):
            exception = 'core_trade_pressure_review'
        overlap = len(set(old_core) & set(core))/max(1, len(old_core))
        outcomes = deepcopy(previous.get('postseason_outcomes', [])) if overlap >= .5 else []
        postseason = save.get('playoff_state') or {}
        year = str(postseason.get('year') or '')
        if postseason.get('status') == 'completed' and year and not any(o['year'] == year for o in outcomes):
            rounds = sum(s.get('winner_team_id') == tid for s in postseason.get('series', []))
            outcomes.append({'year': year, 'rounds_won': rounds, 'core_ids': core})
        # TRADE-FOLLOWUPS: the front office's visible patience (front_office.py), not the old hidden profile field.
        from .front_office import traits_view
        patience = float((traits_view(save).get(tid) or {}).get('patience') or 55)
        required = 3 if patience >= 65 else 2
        stalled = len(outcomes) >= required and all(o['rounds_won'] <= 1 for o in outcomes[-required:])
        phase = state.get('window_phase') or 'rebuilding'
        route = {'peak': 'extend_peak', 'entering': 'patient_growth_then_selective_upgrade',
                 'exiting': 'retool_before_teardown', 'rebuilding': 'acquire_and_develop_foundations'}[phase]
        if stalled and phase != 'peak' and float(state.get('window_trend') or 0) <= .5 and stamp > (until or ''):
            route = 'review_core_ceiling_and_retool_alternatives'
        retool = None
        if len(core) > 1 and stamp > (until or '') and (route == 'review_core_ceiling_and_retool_alternatives' or phase == 'exiting'):
            eligible = [pid for pid in core if route.startswith('review_') or
                        float(players[pid].get('display_age', players[pid].get('age')) or 27) >= 30]
            if eligible:
                retool = max(eligible, key=lambda pid: (
                    float(players[pid].get('display_age', players[pid].get('age')) or 27)
                    + float(values.get(pid, {}).get('health_risk') or 0)*.15
                    - float(values.get(pid, {}).get('on_court_value') or 0)*.12, pid))
        entry = {'version': VERSION, 'reviewed_on': stamp, 'core_ids': core,
                 'window_phase': phase, 'league_rank': state.get('league_rank'),
                 'contender_index': state.get('contender_index'), 'window_trend': state.get('window_trend'),
                 'commit_until': until, 'major_acquisition_date': acquired,
                 'review_exception': exception, 'route': route, 'postseason_outcomes': outcomes[-4:],
                 'retool_candidate_id': retool,
                 'assessment_note': 'Relative fit/strength and bounded development scenario; not calibrated championship odds.'}
        plans[tid] = entry
    save['team_plan_review_signature'] = signature
    save['team_plan_review_date'] = stamp
    active['team_plans'] = deepcopy(plans)
    active.pop('_strategy_model_version', None)
    from .trade_wants import refresh_ai_wants
    # Only intent changed above: roster/traits/health/contracts/records/picks
    # and every valuation/league assessment input are unchanged. Wants consume
    # the fresh plans plus the already-built values/states, not trade blocks.
    # Keep active invalidated so a subsequent market search still rebuilds its
    # block with the new commitments. No approval is reused at settlement.
    refresh_ai_wants({**context, 'team_plans': active['team_plans']}, save, stamp)
    active['team_trade_wants'] = deepcopy(save['team_trade_wants'])
    return True
