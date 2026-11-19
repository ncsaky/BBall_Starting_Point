"""Healthy final-roster consequences, separate from headline asset prices."""
from copy import deepcopy
from .utils import copy_plain


def planning_save(canonical):
    meta = canonical.get('meta') or {}
    saved = canonical.get('_trade_planning_save') or {
        'meta': {'season': meta.get('active_season') or '2026-27'},
        'state': {'current_date': meta.get('current_date') or '2026-10-01'},
        'team_plans': canonical.get('team_plans') or {},
        'health_states': canonical.get('player_health_states') or [],
    }
    forecast = canonical.get('_roster_forecast_snapshot')
    return {**saved, '_forecast_season_windows': forecast.season_windows} if forecast is not None else saved


def roster_projection(canonical, team_id, outgoing_ids=(), incoming_ids=()):
    from . import transactions as tx
    from .save import ai_role_targets, ai_roster_retention_score, ROSTER_SEASON_MAXIMUM
    outgoing_ids, incoming_ids = set(outgoing_ids), set(incoming_ids)
    batch_cache = canonical.get('_trade_search_rosters')
    batch_key = (team_id, tuple(sorted(outgoing_ids)), tuple(sorted(incoming_ids)))
    if batch_cache is not None and batch_key in batch_cache:
        return copy_plain(batch_cache[batch_key])
    forecast = canonical.get('_roster_forecast_snapshot')
    if forecast is not None:
        roster = forecast.roster(team_id, outgoing_ids, incoming_ids)
    else:
        roster = [dict(p, team_id=team_id, minutes_projection=24) for p in canonical.get('players', [])
                  if not p.get('_inactive_player') and p['id'] not in outgoing_ids
                  and (p.get('team_id') == team_id or p['id'] in incoming_ids)]
    saved = planning_save(canonical)
    values = tx.player_asset_values_by_id(canonical)
    contracts = forecast.contracts if forecast is not None else {c['player_id']: c for c in canonical.get('contracts', [])}
    roster_ids = {p['id'] for p in roster}
    roster_traits = (forecast.selected_rows(forecast.traits, roster_ids) if forecast is not None else
                     [t for t in canonical.get('traits', []) if t.get('player_id') in roster_ids])
    skills = tuple((t.get('player_id'), t.get('trait_key'), t.get('value'))
                   for t in roster_traits)
    roster_health = (forecast.selected_rows(forecast.health, roster_ids) if forecast is not None else
                     [h for h in saved.get('health_states', []) if h.get('player_id') in roster_ids])
    health = tuple((h.get('player_id'), h.get('availability_status'), h.get('return_date')) for h in roster_health)
    signature = (team_id, saved['state'].get('current_date'), skills, health,
        tuple(sorted((saved.get('team_plans', {}).get(team_id) or {}).get('core_ids', []))),
        tuple(sorted((p['id'], p.get('position'), p.get('display_age', p.get('age')),
            p.get('potential'), p.get('current_ability'), p.get('rotation_priority'),
            values.get(p['id'], {}).get('on_court_value'), values.get(p['id'], {}).get('health_risk'),
            tuple(tuple(sorted((k, str(v)) for k, v in s.items()))
                  for s in contracts.get(p['id'], {}).get('seasons', []))) for p in roster)))
    cache = canonical.setdefault('_trade_roster_projection_cache', {}) if canonical.get('_allow_internal_caches') else {}
    if signature in cache:
        return copy_plain(cache[signature])
    if forecast is None:
        from .roster_forecast import ForecastSnapshot
        forecast = ForecastSnapshot(canonical)
    saved = {**saved, '_forecast_season_windows': forecast.season_windows}
    trial = forecast.view(canonical, roster, traits=roster_traits)
    cuts, kept = [], roster
    if len(roster) > ROSTER_SEASON_MAXIMUM:
        targets, _ = ai_role_targets(trial, roster, {})
        for p in roster:
            p['minutes_projection'] = targets.get(p['id'], 0)
        ordered = sorted(roster, key=lambda p: (-ai_roster_retention_score(trial, saved, p), p['id']))
        cuts, kept = ordered[ROSTER_SEASON_MAXIMUM:], ordered[:ROSTER_SEASON_MAXIMUM]
    trial['players'] = kept
    trial['_players_by_id'] = {p['id']: p for p in kept}
    rotation = tx.strategic_rotation_view(trial, team_id)
    rotation = constrain_center_opportunity(canonical, rotation)
    from .sim import team_feature_vector
    # When the center constraint left the chosen view untouched, its strength was just computed (same view, same team).
    strength = rotation.get('_strategic_contention')
    if strength is None:
        strength = tx.contention_from_features(team_feature_vector(rotation, tx.team_by_id(canonical, team_id), include_spatial=False).features)
    result = {'strength': round(strength, 4), 'cuts': cuts,
              'rotation': {p['id']: p['minutes_projection'] for p in rotation['players']},
              'retained_ids': [p['id'] for p in kept]}
    # A prepared context is disposable; bound speculative search memory too.
    if len(cache) >= 128:
        cache.clear()
    cache[signature] = copy_plain(result)
    if batch_cache is not None:
        if len(batch_cache) >= 1024:
            # Retain the inexpensive, frequently reused baseline for each club.
            baselines = {key: value for key, value in batch_cache.items() if not key[1] and not key[2]}
            batch_cache.clear()
            batch_cache.update(baselines)
        batch_cache[batch_key] = cache[signature]
    return result


def constrain_center_opportunity(canonical, rotation):
    """Pure forecast adjustment; never write the coach's actual rotation."""
    from .save import player_position_tokens
    from .trade_wants import player_facts
    players = [dict(p) for p in rotation['players']]
    centers = [p for p in players if set(player_position_tokens(p)) == {'C'}
               and player_facts(canonical, p).get('spacing', 100) < 65]
    total = sum(float(p.get('minutes_projection') or 0) for p in centers)
    if total <= 48:
        return rotation
    center_ids = {p['id'] for p in centers}
    freed = total-48
    others = [p for p in players if p['id'] not in center_ids]
    room = sum(max(0, 42-float(p.get('minutes_projection') or 0)) for p in others)
    if room < freed:
        return rotation  # Incomplete legacy fixtures cannot supply a legal alternative.
    for player in centers:
        player['minutes_projection'] = float(player['minutes_projection'])*48/total
    for player in others:
        space = max(0, 42-float(player.get('minutes_projection') or 0))
        player['minutes_projection'] += freed*space/room
    forecast = rotation.get('_roster_forecast_snapshot')
    if forecast is not None:
        view = forecast.view(rotation, players)
    else:
        view = {key: value for key, value in rotation.items() if not str(key).startswith('_')}
        view.update(players=players, _allow_internal_caches=True)
    return view


def long_absences(canonical, saved):
    """(player id, days out) for each health row that is out for at least 14 more days, in row order.

    Inside one trade search the planning save never changes, so the list is kept per search (with the rows it
    was built from) instead of re-reading every league health row for each priced package."""
    from . import transactions as tx
    rows = saved.get('health_states', [])
    stamp = saved['state'].get('current_date')
    memo = canonical.get('_trade_search_exact_memo')
    cached = memo.get('long_absences') if memo is not None else None
    if cached is not None and cached[0] is rows and cached[1] == stamp:
        return cached[2]
    today = tx.parse_iso_date(stamp)
    found = []
    for health in rows:
        end = tx.parse_iso_date(health.get('return_date'))
        days = (end-today).days if today and end else 0
        if health.get('availability_status') == 'out' and days >= 14:
            found.append((health.get('player_id'), days))
    if memo is not None:
        memo['long_absences'] = (rows, stamp, found)
    return found


def pick_investment_outlook(canonical, team_id, incoming, outgoing, before, after, waiver_cost=0):
    """Allow price disagreement for an actual purpose, not just a pick sweetener."""
    from . import transactions as tx
    draft_in = [a for a in incoming if a.get('kind') in {'pick', 'pick_swap'}]
    draft_out = [a for a in outgoing if a.get('kind') in {'pick', 'pick_swap'}]
    if not draft_in and not draft_out:
        return None
    spend = tx.package_value_for_team(canonical, draft_out, team_id) - tx.package_value_for_team(canonical, draft_in, team_id)
    if spend <= 1.5:
        return None
    values = tx.player_asset_values_by_id(canonical)
    retained = set(after['retained_ids'])

    def young_upside(assets, eligible=None):
        total = 0.
        for asset in assets:
            if asset.get('kind') != 'player' or (eligible is not None and asset['id'] not in eligible):
                continue
            player = tx.player_by_id(canonical, asset['id']) or {}
            value = values.get(asset['id'], {})
            if float(player.get('display_age', player.get('age')) or 99) <= 25:
                total += max(0., float(value.get('development_upside') or 0)) * min(1., max(0., float(value.get('player_value') or 0))/50)
        return total

    growth = max(0., young_upside(incoming, retained)-young_upside(outgoing))
    strength = max(0., after['strength']-before['strength'])
    from .save import player_position_tokens
    players = {p['id']: p for p in canonical.get('players', [])}

    def backup_quality(projection, position):
        candidates = [float(values.get(pid, {}).get('on_court_value') or 0)
                      for pid in projection['retained_ids']
                      if position in player_position_tokens(players.get(pid, {}))]
        return sorted(candidates, reverse=True)[1] if len(candidates) >= 2 else 0.

    # Use the strongest positional backup gain, not five credits for one
    # multi-position player. Rotation impact already rewards starting quality.
    depth = max(0., max(backup_quality(after, p)-backup_quality(before, p) for p in ('PG', 'SG', 'SF', 'PF', 'C')))
    incoming_minutes = max((after['rotation'].get(a['id'], 0) for a in incoming if a.get('kind') == 'player'), default=0)
    salary_out, salary_in = tx.package_salary(canonical, outgoing), tx.package_salary(canonical, incoming)
    relief = max(0., (salary_out-salary_in)/1e6-waiver_cost) if salary_out is not None and salary_in is not None else 0.
    saved = planning_save(canonical)
    injured, absence = set(), 0
    for pid, days in long_absences(canonical, saved):
        if before['rotation'].get(pid, 0) >= 12:
            injured.add(pid)
            absence = max(absence, days)
    cover = 0.
    if injured:
        outgoing_ids = {a['id'] for a in outgoing if a.get('kind') == 'player'}
        incoming_ids = {a['id'] for a in incoming if a.get('kind') == 'player'}
        before_cut = {p['id'] for p in before['cuts']}
        after_cut = {p['id'] for p in after['cuts']}
        hurt_before = roster_projection(canonical, team_id, injured | before_cut)
        hurt_after = roster_projection(canonical, team_id, outgoing_ids | injured | after_cut, incoming_ids)
        cover = max(0., hurt_after['strength']-hurt_before['strength']-strength) * min(1., absence/60)
    limit = min(9., 1.5+strength*6+growth*.2+cover*6+(relief*.25 if relief >= 5 else 0))
    capital_limit = 8+strength*30+depth*.6+growth*1.5+cover*30+(relief*2 if relief >= 5 else 0)
    # Trade step 4: picks paid to shed salary buy luxury-tax savings, not a rotation upgrade. Real tax teams paid one
    # to three seconds for it (Finney-Smith, LeVert, Saric); the tax saved (trade_tax, AI teams only) is a purpose.
    from .trade_tax import tax_value
    tax_saving = max(0., tax_value(canonical, team_id, incoming, outgoing))
    capital_limit += tax_saving
    limit = min(9., limit+tax_saving*.25)
    return {'net_draft_value_spent': round(spend, 4), 'loss_limit': round(limit, 4),
            'rotation_gain': round(strength, 4), 'young_upside_gain': round(growth, 4),
            'injury_cover_gain': round(cover, 4), 'net_salary_relief_millions': round(relief, 4),
            'backup_quality_gain': round(depth, 4), 'incoming_rotation_minutes': incoming_minutes,
            'capital_limit': round(capital_limit, 4)}


def role_opportunity_outlook(canonical, team_id, incoming_ids, outgoing_ids, before, after):
    """Price a second non-spacing center as a shared role, not two full starters."""
    from .save import player_position_tokens
    from .trade_wants import player_facts
    players = {p['id']: p for p in canonical.get('players', [])}
    saved = planning_save(canonical)
    unavailable = {h.get('player_id') for h in saved.get('health_states', [])
                   if h.get('availability_status') == 'out' and h.get('return_date', '') > saved['state'].get('current_date', '')}
    def center(pid):
        player = players.get(pid, {})
        if 'C' not in player_position_tokens(player):
            return False
        facts = player_facts(canonical, player)
        return facts.get('spacing') is not None and facts['spacing'] < 65
    adjustment, conflicts = 0., []
    retained = set(before['retained_ids']) & set(after['retained_ids']) - outgoing_ids - unavailable
    for pid in sorted(incoming_ids - unavailable):
        if not center(pid) or pid not in after['retained_ids']:
            continue
        alternatives = [other for other in retained if center(other) and before['rotation'].get(other, 0) >= 20]
        if not alternatives:
            continue
        best = max(alternatives, key=lambda other: player_facts(canonical, players[other]).get('overall', 0))
        gain = player_facts(canonical, players[pid]).get('overall', 0)-player_facts(canonical, players[best]).get('overall', 0)
        minutes = after['rotation'].get(pid, 0)
        overlap = max(0, min(minutes, after['rotation'].get(best, 0)))
        penalty = min(4., overlap*.14) * max(0., 1-max(0., gain)/12)
        lost = sum(before['rotation'].get(other, 0) for other in outgoing_ids
                   if other in players and 'C' not in player_position_tokens(players[other]))
        if lost >= 20 and after['strength']-before['strength'] < .5:
            penalty += min(1., lost/32)
        adjustment -= penalty
        conflicts.append({'incoming_id': pid, 'incumbent_id': best, 'incoming_minutes': minutes,
                          'incumbent_minutes': after['rotation'].get(best, 0), 'quality_gain': round(gain, 2),
                          'complementary_minutes_lost': lost})
    return {'adjustment': round(max(-5., adjustment), 4), 'conflicts': conflicts}


def trade_roster_outlook(canonical, team_id, incoming, outgoing):
    from . import transactions as tx
    from .contract_protection import waiver_projection
    incoming_ids = {a['id'] for a in incoming if a.get('kind') == 'player'}
    outgoing_ids = {a['id'] for a in outgoing if a.get('kind') == 'player'}
    roster = [p for p in canonical.get('players', []) if p.get('team_id') == team_id and not p.get('_inactive_player')]
    # Legacy unit/CLI projections may contain only the traded players.
    if len(roster) < 5 or not incoming_ids | outgoing_ids:
        return None
    before = roster_projection(canonical, team_id)
    after = roster_projection(canonical, team_id, outgoing_ids, incoming_ids)
    baseline_cut_ids = {p['id'] for p in before['cuts']}
    incremental_cuts = [p for p in after['cuts'] if p['id'] not in baseline_cut_ids]
    discarded = incoming_ids & {p['id'] for p in after['cuts']}
    retained_incoming = [a for a in incoming if a.get('kind') != 'player' or a['id'] not in discarded]
    lost_credit = max(0., tx.package_value_for_team(canonical, incoming, team_id, outgoing)
                      - tx.package_value_for_team(canonical, retained_incoming, team_id, outgoing)) if discarded else 0.
    lost_owned = [{'kind': 'player', 'id': p['id']} for p in incremental_cuts if p['id'] not in incoming_ids]
    if lost_owned:
        lost_credit += max(0., tx.package_value_for_team(canonical, lost_owned, team_id))
    saved = planning_save(canonical)
    debts = [waiver_projection(canonical, saved, p, team_id) for p in incremental_cuts]
    cost = sum(d['remaining_cost_millions'] for d in debts)
    state = next((s for s in canonical.get('team_strategic_states', []) if s.get('team_id') == team_id), {})
    phase = state.get('window_phase')
    competitive = phase in {'peak', 'entering'} or state.get('phase') in {'contending', 'contending_with_future_upside'}
    delta = after['strength']-before['strength']
    adjustment = delta*(4 if competitive else 1) - lost_credit - cost*(.16 if competitive else .28)
    role_opportunity = role_opportunity_outlook(canonical, team_id, incoming_ids, outgoing_ids, before, after)
    adjustment += role_opportunity['adjustment']
    plan = canonical.get('team_plans', {}).get(team_id, {})
    reviewing = bool(plan.get('review_exception') or plan.get('route') == 'review_core_ceiling_and_retool_alternatives')
    values = tx.player_asset_values_by_id(canonical)
    best_departing = max((float(values.get(pid, {}).get('on_court_value') or 0) for pid in outgoing_ids), default=0)
    principal_ids = [pid for pid in outgoing_ids if float(values.get(pid, {}).get('on_court_value') or 0) >= best_departing-4]
    burdened = bool(principal_ids) and all(float(values.get(pid, {}).get('contract_surplus') or 0) <= -16
                   or float(values.get(pid, {}).get('health_risk') or 0) >= 30 for pid in principal_ids)
    salary_relief = (tx.package_salary(canonical, outgoing) or 0)-(tx.package_salary(canonical, incoming) or 0)
    financial_exit = burdened and salary_relief >= 5_000_000
    departure_price = max((float(values.get(pid, {}).get('player_value') or 0) for pid in principal_ids), default=0)
    credible_young_return = False
    for pid in incoming_ids:
        player, value = tx.player_by_id(canonical, pid), values.get(pid, {})
        if (player and float(player.get('display_age', player.get('age')) or 99) <= 25
                and float(value.get('on_court_value') or 0) >= max(60, best_departing-18)
                and float(value.get('development_upside') or 0) >= 12
                and float(value.get('player_value') or 0) >= departure_price*.6):
            credible_young_return = True
    timeline_exchange = phase == 'entering' and credible_young_return
    issue = None
    if competitive and delta < -.75 and not reviewing and not financial_exit and not timeline_exchange:
        issue = 'Trade materially weakens the competing rotation without an injury, core-review or costly-contract exit.'
    elif any(d['unquantified'] for d in debts):
        issue = 'Required final-roster cuts have unresolved salary obligations.'
    investment = pick_investment_outlook(canonical, team_id, incoming, outgoing, before, after, cost)
    if (investment and (investment['incoming_rotation_minutes'] < 24 or investment['rotation_gain'] < .25)
            and investment['net_draft_value_spent'] > investment['capital_limit']):
        issue = issue or 'Draft spending exceeds the rotation, depth, upside, injury-cover and salary benefits of this marginal acquisition.'
    return {'before_strength': before['strength'], 'after_strength': after['strength'],
            'strength_delta': round(delta, 4), 'adjustment': round(adjustment, 4), 'issue': issue,
            'cuts': deepcopy(debts), 'discarded_incoming_ids': sorted(discarded),
            'lost_asset_credit': round(lost_credit, 4), 'waiver_cost_millions': round(cost, 4),
            'before_rotation': before['rotation'], 'after_rotation': after['rotation'],
            'role_opportunity': role_opportunity,
            'pick_investment': investment}


def live_roster_issues(canonical, saved, proposal, *, candidate=None, config=None, _materialization=None):
    from . import transactions as tx
    from .save import canonical_with_save, human_controlled_team_ids
    canonical = tx.canonical_mapping(canonical)
    participants = set(tx.trade_team_ids(proposal))-human_controlled_team_ids(saved)
    if not participants or not any(sum(p.get('team_id') == tid for p in canonical.get('players', [])) >= 5 for tid in participants):
        return []
    active = tx.with_transaction_context(
        _materialization.active() if _materialization is not None
        else canonical_with_save(canonical, copy_plain(saved)))
    candidate = candidate or {}
    active = tx.canonical_with_pending_pick_terms(active, candidate.get('pick_obligation_terms'))
    # Fresh league-wide valuations/ranks/pick context above remain mandatory.
    # Share only forecasts inside this validation, never a search approval or
    # an index from before this (or a preceding) transaction.
    from .roster_forecast import ForecastSnapshot
    active['_roster_forecast_snapshot'] = ForecastSnapshot(active)
    issues = []
    for tid, outgoing, incoming in tx.trade_team_flows(proposal):
        if tid not in participants:
            continue
        outlook = trade_roster_outlook(active, tid, incoming, outgoing)
        if outlook and outlook['issue']:
            issues.append(f"{tx.team_by_id(active, tid)['abbrev']}: {outlook['issue']}")
        elif outlook and outlook.get('pick_investment'):
            from types import SimpleNamespace
            evaluation = tx.evaluate_trade_for_team(active,
                SimpleNamespace(**{**proposal, 'id': candidate.get('evaluation_proposal_id') or proposal['id']}), tid, incoming, outgoing,
                {'status': 'legal', 'issues': [], 'manual_review': []},
                candidate.get('evaluation_seed', 1), config or tx.default_transaction_model_config())
            if evaluation.decision == 'reject_pick_investment':
                issues.append(f"{tx.team_by_id(active, tid)['abbrev']}: Draft-asset overpayment is not justified by this roster's benefits.")
    return issues
