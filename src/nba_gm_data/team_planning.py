"""League-relative windows and save-owned intent, not permanent source labels."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import math


VERSION = 2
LEGACY_PHASE = {'peak': 'contending', 'entering': 'developing', 'exiting': 'retooling', 'rebuilding': 'rebuilding'}


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
        record = canonical.get('save_team_records', {}).get(state.team_id, {})
        wins, losses = float(record.get('wins') or 0), float(record.get('losses') or 0)
        games = wins+losses
        form = ((wins/games)-.5)*6*min(1, games/40) if games >= 15 else 0
        strength = state.contention_ceiling + form
        rows[state.team_id] = {'strength': strength, 'future_strength': strength+delta,
                               'trend': delta, 'core_candidates': core,
                               'ready_young_core': ready_young_core,
                               'credible_anchors': sum(v.on_court_value >= elite for v in values[:5])}
    if not rows:
        return rows
    best = max(r['strength'] for r in rows.values())
    future_best = max(r['future_strength'] for r in rows.values())
    mass = sum(math.exp((r['strength']-best)/3.5) for r in rows.values())
    for tid, row in rows.items():
        rank = 1 + sum(r['strength'] > row['strength'] for r in rows.values())
        share = math.exp((row['strength']-best)/3.5)/mass
        # One aging star can make near-term strength decline while a capable
        # young foundation is still entering its window. Keep both signals.
        young_window = (rank <= 12 and len(row['ready_young_core']) >= 2
                        and any(age <= 27 and quality >= elite-4 for age, quality in row['ready_young_core']))
        if rank <= 6 and share >= 1.3/len(rows) and best-row['strength'] <= 4.5 and row['strength'] >= 60:
            phase = 'peak'
        elif young_window:
            phase = 'entering'
        elif row['trend'] < -.5 and (rank <= max(12, len(rows)*.65) or row['credible_anchors']):
            phase = 'exiting'
        elif row['credible_anchors'] >= 2 or rank <= 12 or (row['core_candidates'] and row['trend'] > .5 and future_best-row['future_strength'] <= 7):
            phase = 'entering'
        else:
            phase = 'rebuilding'
        row.update(window_phase=phase, league_rank=rank, contender_index=round(share*100, 3))
        row['strength'] = round(row['strength'], 3)
        row['future_strength'] = round(row['future_strength'], 3)
        row['trend'] = round(row['trend'], 3)
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
        front = next((f for f in context.get('front_office_profiles', []) if f['team_id'] == tid), {})
        patience = float(front.get('patience') or 55)
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
