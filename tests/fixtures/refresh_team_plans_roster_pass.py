"""Frozen pre-demand planning refresh; full fresh second construction."""
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
        best = sorted((pid for pid, owner in owners.items() if owner == tid and not players[pid].get('_inactive_player')),
                      key=lambda pid: (-float(values.get(pid, {}).get('on_court_value') or 0), pid))[:INJURY_REVIEW_TOP]
        injured = sorted({h['player_id'] for h in save.get('health_states', [])
                          if h.get('player_id') in core and h.get('player_id') in best
                          and h.get('availability_status') == 'out' and h.get('return_date')
                          and season_days_missed(stamp, h['return_date']) >= INJURY_REVIEW_SEASON_DAYS})
        exception = INJURY_REVIEW if injured else None
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
        if injured:
            entry['injury_review_ids'] = injured
        plans[tid] = entry
    save['team_plan_review_signature'] = signature
    save['team_plan_review_date'] = stamp
    active['team_plans'] = deepcopy(plans)
    active.pop('_strategy_model_version', None)
    from .trade_wants import refresh_ai_wants
    refresh_ai_wants(with_transaction_context(active), save, stamp)
    active['team_trade_wants'] = deepcopy(save['team_trade_wants'])
    return True
