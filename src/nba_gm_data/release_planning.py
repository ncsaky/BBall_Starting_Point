"""Rare release decisions and explicit, one-time salary-cap stretch elections."""
from copy import deepcopy
from datetime import date, timedelta


def reacquisition_blocked(context, team_id, player_id, stamp):
    return any(r['team_id'] == team_id and r['player_id'] == player_id
               and r.get('stretch') and stamp < r['stretch']['reacquire_on']
               for r in context.get('waived_salary_obligations', []))


def stretch_quote(active, save, waiver_id, stamp):
    from .save import cap_lines_for_season, season_label_from_start
    entry = next((r for r in save.get('waiver_wire', []) if r['id'] == waiver_id), {})
    debt = next((r for r in save.get('waived_salary_obligations', []) if r['id'] == waiver_id), {})
    if entry.get('status') != 'cleared' or not debt or debt.get('stretch'):
        return {'ok': False, 'reason': 'Only an unclaimed, unstretched release can be stretched.'}
    today = date.fromisoformat(stamp)
    if stamp < str(save.get('state', {}).get('current_date') or ''):
        return {'ok': False, 'reason': 'A stretch election cannot be backdated.'}
    original = [r for r in entry.get('contract', {}).get('seasons', [])
                if r.get('option_type') != 'qualifying_offer'
                and not (r.get('option_type') == 'team_option' and not r.get('option_exercised')
                         and int(r['season'][:4]) > int(entry['date'][:4])-(int(entry['date'][5:7]) < 7))]
    if not original:
        return {'ok': False, 'reason': 'Original contract term is unknown.'}
    final = max(int(r['season'][:4]) for r in original)
    # Article VII 7(d)(6): both termination and election must precede
    # September 1 before the original final season. Current-season money is
    # untouched for an in-season election.
    if stamp < entry['clearance_date'] or stamp >= f'{final}-09-01' or entry['clearance_date'] >= f'{final}-09-01':
        return {'ok': False, 'reason': 'The original contract stretch-election deadline has passed.'}
    start = today.year if today.month >= 7 else today.year-1
    first = start if today.month in (7, 8) else start+1
    if first > final or debt.get('unverified') or debt.get('unquantified'):
        return {'ok': False, 'reason': 'No verified future protected salary is eligible.'}
    owners = save.get('roster_overrides') or {}
    if any(owners.get(p['id'], p.get('team_id')) == debt['team_id'] and p['id'] == debt['player_id'] for p in active.get('players', [])):
        return {'ok': False, 'reason': 'The releasing team has reacquired this player.'}
    def contains_player(assets):
        from .transactions import trade_assets
        return (assets.get('player_id') == debt['player_id'] or any(
            a.get('kind') == 'player' and a.get('id') == debt['player_id']
            for a in trade_assets(assets)))
    if any(r.get('transaction_type') in {'free_agent_signing', 'waiver_claim', 'trade'}
           and r.get('date', '') > entry['clearance_date'] and debt['team_id'] in r.get('teams', [])
           and contains_player(r.get('assets') or {}) for r in save.get('transaction_logs', [])):
        return {'ok': False, 'reason': 'A reacquired player cannot have the earlier contract stretched.'}
    rows = debt['seasons']
    future = [r for r in rows if int(r['season'][:4]) >= first]
    if not future or any(r.get('salary') is None for r in future):
        return {'ok': False, 'reason': 'Future salary requires review.'}
    amount = round(sum(float(r['salary']) for r in future), 2)
    count = 2*(final-first+1)+1
    if amount <= 0:
        return {'ok': False, 'reason': 'There is no remaining salary to stretch.'}
    annual = round(amount/count, 2)
    schedule = [{'season': season_label_from_start(first+i), 'salary': annual,
                 'unverified_reserve': 0, 'earned_salary': 0} for i in range(count)]
    schedule[-1]['salary'] = round(amount-annual*(count-1), 2)
    cap = 154_647_000*cap_lines_for_season(season_label_from_start(start))['growth_factor']
    for row in schedule:
        other = [s for r in save.get('waived_salary_obligations', [])
                 if r['team_id'] == debt['team_id'] and r['id'] != debt['id']
                 for s in r['seasons'] if s['season'] == row['season']]
        if any(s.get('salary') is None for s in other) or sum(float(s['salary']) for s in other)+row['salary'] > cap*.15:
            return {'ok': False, 'reason': 'Total waived salary would exceed the 15%-of-cap stretch limit.'}
    return {'ok': True, 'date': stamp, 'waiver_id': waiver_id, 'total': amount,
            'years': count, 'cap_charges': [deepcopy(r) for r in rows if int(r['season'][:4]) < first]+schedule,
            'reacquire_on': f"{max(int(r['season'][:4]) for r in entry['contract']['seasons'])+1}-07-01", 'cash_obligation_unchanged': True}


def elect_stretch(active, save, waiver_id, stamp):
    quote = stretch_quote(active, save, waiver_id, stamp)
    if not quote['ok']:
        return quote
    debt = next(r for r in save['waived_salary_obligations'] if r['id'] == waiver_id)
    debt['pre_stretch_seasons'] = deepcopy(debt['seasons'])
    debt['seasons'] = deepcopy(quote['cap_charges'])
    debt['stretch'] = {k: v for k, v in quote.items() if k != 'cap_charges'}
    debt['relief_status'] = 'cap_stretched_total_obligation_preserved'
    save.setdefault('transaction_logs', []).append({'id': waiver_id+':stretch', 'date': stamp,
        'transaction_type': 'salary_stretch', 'teams': [debt['team_id']],
        'status': 'applied_to_save_ledger', 'assets': {'player_id': debt['player_id']}, 'waiver_id': waiver_id})
    return quote


def review_ai_releases(canonical, save, stamp, seed):
    from .save import (canonical_with_save, human_controlled_team_ids, display_minutes_projection,
                       released_free_agent_destination, released_free_agent_salary,
                       player_attribute_summary, add_news, trade_deadline_date, season_start_year_from_date)
    from .transactions import recently_signed_player_ids
    from .waivers import buyout_quote, request_waiver
    today = date.fromisoformat(stamp)
    deadline = date.fromisoformat(trade_deadline_date(season_start_year_from_date(stamp)))
    if not (deadline+timedelta(days=2) <= today <= date(deadline.year, 3, 1)
            and (today-deadline).days % 7 == 2):
        return []
    if save.get('state', {}).get('phase') != 'regular_season':
        return []
    reviewed = save.setdefault('ai_release_review_dates', [])
    if stamp in reviewed:
        return []
    reviewed.append(stamp)
    active = canonical_with_save(canonical, save)
    human = human_controlled_team_ids(save)
    done = []
    health = {r['player_id']: r for r in save.get('health_states', [])}
    recent_signings = recently_signed_player_ids(active, stamp)
    for player in sorted(active.get('players', []), key=lambda p: p['id']):
        tid = player.get('team_id')
        roster = [p for p in active['players'] if p.get('team_id') == tid and not p.get('_inactive_player')]
        core = save.get('team_plans', {}).get(tid, {}).get('core_ids', [])
        if (not tid or tid in human or tid in done or len(roster) < 15 or player['id'] in core
                or player['id'] in recent_signings
                or float(player.get('display_age', player.get('age')) or 27) < 29
                or display_minutes_projection(player) >= 8
                or health.get(player['id'], {}).get('availability_status') not in (None, 'active')):
            continue
        same_position = [p for p in roster if p['id'] != player['id'] and p.get('position') == player.get('position')
                         and health.get(p['id'], {}).get('availability_status') in (None, 'active')]
        if len(same_position) < 2:
            continue
        quote = buyout_quote(active, save, player, tid)
        start = today.year-1
        if quote['unverified'] or quote['unquantified'] or any(int(r['season'][:4]) > start and (r['salary'] or 0) > 0 for r in quote['seasons']):
            continue
        if quote['savings_millions'] < .05:
            continue
        # Consent is plausible only with an actual interested destination and
        # enough potential new earnings to cover this game's fixed concession.
        profile = next((p for p in active.get('player_contract_market_profiles', []) if p['player_id'] == player['id']), {})
        salary = released_free_agent_salary(player, profile, player_attribute_summary(active, player['id']))
        destination = released_free_agent_destination(active, save, player, {'waived_by_team_id': tid}, salary, seed, stamp)
        if not destination or quote['savings_millions'] > 1.9*.4:
            continue
        entry = request_waiver(active, save, player, tid, stamp, buyout=True)
        entry['ai_release_reason'] = 'expiring_surplus_veteran_with_external_role_and_covered_position'
        entry['prospective_team_id'] = destination['team']['id']
        save['released_free_agents'][player['id']]['buyout_market_interest'] = {
            'team_id': destination['team']['id'], 'date': stamp}
        save.setdefault('transaction_logs', []).append({'id': entry['id']+':buyout', 'date': stamp,
            'transaction_type': 'buyout_agreement', 'status': 'applied_to_save_ledger',
            'teams': [tid], 'assets': {'player_id': player['id']}, 'waiver_id': entry['id']})
        add_news(save, 'waivers', f"{player.get('name')} agrees to a buyout to pursue a new role; salary obligations remain.", date_value=stamp)
        done.append(tid)
        active = canonical_with_save(canonical, save)
    return done


def review_ai_stretches(canonical, save, stamp):
    """Only stretch existing debt to fund a real, competitive summer bid."""
    from .save import canonical_with_save, human_controlled_team_ids
    from . import play
    from .roster_space import activate_target
    if not '07-01' <= stamp[5:] <= '08-31':
        return []
    active = canonical_with_save(canonical, save)
    done = []
    state = save.get('free_agency_state', {})
    targets = state.get('roster_space_targets', {})
    for debt in list(save.get('waived_salary_obligations', [])):
        tid = debt['team_id']
        target = targets.get(tid, {})
        if tid in human_controlled_team_ids(save) or target.get('day') != state.get('day'):
            continue
        if target.get('player_id') not in set(save.get('free_agent_player_ids', [])):
            continue
        team = play.team_by_id(active, tid)
        reserved = play.active_bid_commitment(save, tid, exclude_player_id=target['player_id'])
        if play.signing_cap_check(active, save, team['abbrev'], target['aav_millions'], reserved_millions=reserved).get('ok'):
            continue
        quote = stretch_quote(active, save, debt['id'], stamp)
        if not quote['ok']:
            continue
        season = f'{stamp[:4]}-{str(int(stamp[:4])+1)[-2:]}'
        old = sum(float(r.get('salary') or 0) for r in debt['seasons'] if r['season'] == season)
        new = sum(r['salary'] for r in quote['cap_charges'] if r['season'] == season)
        if old-new < 2_000_000 or float(target.get('upgrade') or 0) < 8:
            continue
        # Run the actual bid, rival-interest, financial and final-roster checks
        # on a disposable counterfactual before committing the extra debt years.
        trial = deepcopy(save)
        if not elect_stretch(active, trial, debt['id'], stamp)['ok']:
            continue
        if not activate_target(canonical, trial, target, save.get('meta', {}).get('seed', 1)):
            continue
        offers = play.active_offers_for_player(trial, target['player_id'])
        own = next((o for o in offers if o['team_id'] == tid), {})
        player = next(p for p in active['players'] if p['id'] == target['player_id'])
        if (not own or float(own.get('interest_score') or 0) < play.free_agency_accept_threshold(player, int(state.get('day') or 1))
                or any(float(o.get('interest_score') or 0) > float(own.get('interest_score') or 0)+3 for o in offers)):
            continue
        # Avoid extending debt into a forecast building window merely to fill
        # the end of a rebuilding roster.
        if save.get('team_plans', {}).get(tid, {}).get('window_phase') not in {'peak', 'entering'}:
            continue
        original_end = max(int(r['season'][:4]) for r in debt['seasons'])
        tail = sum(r['salary'] for r in quote['cap_charges'] if int(r['season'][:4]) > original_end)/1e6
        if float(target.get('upgrade') or 0) < tail*.22:
            continue
        save['waived_salary_obligations'] = trial['waived_salary_obligations']
        save['transaction_logs'] = trial['transaction_logs']
        save['free_agent_offers'] = trial['free_agent_offers']
        save['free_agency_state'] = trial['free_agency_state']
        done.append(tid)
        active = canonical_with_save(canonical, save)
    return done
