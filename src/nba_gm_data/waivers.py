"""Date-driven waivers. Claims transfer contracts; unclaimed releases retain debt."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import math

from .contract_protection import record_waiver, waiver_projection, roster_signing_plan


def minimum_claim_contract(contract):
    """Recognize short minimum deals, not the cheap last years of a long deal."""
    from .save import cap_lines_for_season
    rows = contract.get('seasons') or []
    if not 1 <= len(rows) <= 2 or any(r.get('salary') is None for r in rows):
        return False
    rows = sorted(rows, key=lambda r: r['season'])
    salaries = [float(r['salary']) for r in rows]
    if any(not math.isfinite(s) or s <= 0 for s in salaries):
        return False
    # Existing game-generated minimums use flat $1.9M/$2.25M frameworks.
    if all(abs(s-salaries[0]) <= 1 for s in salaries) and any(abs(salaries[0]-v) <= 1 for v in (1_900_000, 2_250_000)):
        return True
    # Published 2024-25 Exhibit C, scaled to our 2025-26 cap baseline.
    # Matching actual salary signatures avoids guessing service from draft year.
    first_year = (1_157_153, 1_862_265, 2_087_519, 2_162_606, 2_237_691,
                  2_425_403, 2_613_120, 2_800_834, 2_988_550, 3_003_427, 3_303_771)
    second_year = (1_955_377, 2_191_897, 2_270_735, 2_349_578, 2_546_675,
                   2_743_776, 2_940_876, 3_137_977, 3_153_598, 3_468_960, 3_468_960)
    factor = cap_lines_for_season(rows[0]['season'])['growth_factor'] * 1.10
    for first, second in zip(first_year, second_year):
        if all(abs(s-amount*factor) <= 20 for s, amount in zip(salaries, (first, second))):
            return True
    return False


def claim_contract_cost(active, save, player, rows, plan):
    """Price the actual annual schedule, with declining veteran value."""
    from .save import player_attribute_summary, display_minutes_projection, released_free_agent_salary
    profile = next((p for p in active.get('player_contract_market_profiles', []) if p['player_id'] == player['id']), {})
    fair = float(profile.get('expected_aav') or released_free_agent_salary(player, profile, player_attribute_summary(active, player['id'])))
    age = float(player.get('display_age', player.get('age')) or 27)
    start = int(rows[0]['season'][:4])
    excess = 0.0
    for row in rows:
        offset = int(row['season'][:4])-start
        if offset > 0 and row.get('option_type') == 'team_option' and not row.get('option_exercised'):
            continue
        aging = max(.45, 1-max(0, age+offset-30)*.055)
        excess += max(0, float(row['salary'])-fair*aging)/(1.05**offset)
    budget = max(4., float(plan.get('upgrade') or 0)) + min(8., float(plan.get('projected_minutes') or display_minutes_projection(player))*.25)
    return {'remaining_salary_millions': round(sum(float(r['salary']) for r in rows)/1e6, 3),
            'excess_cost_millions': round(excess/1e6, 3), 'worthwhile': excess/1e6*.75 <= budget}


def pending_ids(save):
    return {r['player_id'] for r in save.get('waiver_wire', []) if r['status'] == 'pending'}


def buyout_quote(active, save, player, team_id):
    projection = waiver_projection(active, save, player, team_id)
    # A disclosed game convention, not an NBA-mandated concession. Unknown
    # protection and earned salary are never discounted.
    savings = {}
    for row in projection['seasons']:
        if row['unverified_reserve'] or row['salary'] is None:
            savings[row['season']] = 0
        else:
            floor = row['earned_salary'] + row['waiver_clearance_salary']
            savings[row['season']] = round(max(0, row['salary'] - floor) * .10)
    return {**projection, 'concessions': savings,
            'savings_millions': round(sum(savings.values()) / 1e6, 4),
            'payout_millions': round(projection['remaining_cost_millions'] - sum(savings.values()) / 1e6, 4),
            'policy': 'Simplified buyout: 10% of verified unearned protected salary is surrendered only if waivers clear. Unknown protection is reserved in full.',
            'cap_charges': [{'season': r['season'], 'salary': None if r['salary'] is None else r['salary'] - savings[r['season']]} for r in projection['seasons']]}


def request_waiver(active, save, player, team_id, stamp, *, buyout=False):
    existing = next((r for r in save.get('waiver_wire', []) if r['player_id'] == player['id'] and r['status'] == 'pending'), None)
    if existing:
        return existing
    if player.get('team_id') != team_id:
        raise ValueError('Only the current team can release this player.')
    obligation = record_waiver(active, save, player, team_id, stamp)
    contract = deepcopy(next((c for c in active.get('contracts', []) if c['player_id'] == player['id']), {}))
    entry = {**deepcopy(obligation), 'id': obligation['id'], 'player_id': player['id'], 'player_name': player.get('name'),
             'team_id': team_id, 'date': stamp, 'clearance_date': obligation['clearance_date'],
             'status': 'pending', 'contract': contract, 'claims': [],
             'buyout': buyout_quote(active, save, player, team_id) if buyout else None}
    save.setdefault('waiver_wire', []).append(entry)
    save.setdefault('roster_overrides', {})[player['id']] = None
    save['free_agent_player_ids'] = sorted(set(save.get('free_agent_player_ids', [])) - {player['id']})
    save.setdefault('released_free_agents', {})[player['id']] = {
        'player_id': player['id'], 'player_name': player.get('name'), 'waived_by_team_id': team_id,
        'release_date': stamp, 'status': 'on_waivers', 'clearance_date': entry['clearance_date']}
    save.setdefault('rotation_recommendations', {}).pop(player['id'], None)
    save.setdefault('rotation_snapshots', {}).pop(team_id, None)
    save.setdefault('starting_lineups', {}).pop(team_id, None)
    for bid in save.get('free_agent_offers', []):
        if bid.get('player_id') == player['id'] and bid.get('status') == 'active':
            bid['status'] = 'unavailable_on_waivers'
    return entry


def claim_plan(active, save, entry, team_id, *, cut_id=None, ai=False):
    from .save import team_cap_summary, save_active_contract_season, cap_lines_for_season
    if team_id == entry['team_id']:
        return {'ok': False, 'reason': 'The releasing team cannot claim its own player.'}
    player = next((p for p in active.get('players', []) if p['id'] == entry['player_id']), None)
    if not player or player.get('team_id') or player.get('_inactive_player'):
        return {'ok': False, 'reason': 'Player is no longer on waivers.'}
    roster = [p for p in active.get('players', []) if p.get('team_id') == team_id and not p.get('_inactive_player')]
    season = save_active_contract_season(save)
    rows = [r for r in entry['contract'].get('seasons', []) if r['season'] >= season]
    if not rows or any(r.get('salary') is None for r in rows):
        return {'ok': False, 'reason': 'Existing contract salary requires review.'}
    today = date.fromisoformat(str(save.get('state', {}).get('current_date') or entry['date']))
    from .release_planning import reacquisition_blocked
    if reacquisition_blocked(save, team_id, entry['player_id'], today.isoformat()):
        return {'ok': False, 'reason': 'A stretched player cannot be reacquired before the original contract ends.'}
    for log in save.get('transaction_logs', []):
        teams, assets = log.get('teams') or [], log.get('assets') or {}
        if log.get('transaction_type') != 'trade' or team_id not in teams:
            continue
        from .transactions import transaction_log_flows
        sent = next((outgoing for tid, outgoing, _ in transaction_log_flows(log) if tid == team_id), [])
        if not any(a.get('kind') == 'player' and a.get('id') == entry['player_id'] for a in sent):
            continue
        traded = date.fromisoformat(log['date'])
        final_year = max(int(r['season'].split('-')[0]) for r in rows)
        unlock = min(traded + timedelta(days=365), date(final_year + 1, 7, 1))
        if traded <= today < unlock:
            return {'ok': False, 'reason': 'A recently traded player cannot be claimed back by the team that traded him.'}
    if ai:
        plan = roster_signing_plan(active, save, player, team_id, float(rows[0]['salary']) / 1e6, len(rows))
        if not plan.get('ok') or (len(roster) >= 15 and float(plan.get('upgrade') or 0) < 2):
            return {'ok': False, 'reason': 'No worthwhile final-roster upgrade.'}
        cut_id = next((r['player_id'] for r in plan.get('cuts', [])), None)
        cost = claim_contract_cost(active, save, player, rows, plan)
        if not cost['worthwhile']:
            return {'ok': False, 'reason': 'Remaining contract cost exceeds the roster upgrade.', 'contract_cost': cost}
    if len(roster) >= 15 and not cut_id:
        return {'ok': False, 'reason': 'Choose a player to waive for the roster spot.'}
    cut = next((p for p in roster if p['id'] == cut_id), None) if cut_id else None
    if cut_id and not cut:
        return {'ok': False, 'reason': 'Replacement player is no longer on this roster.'}
    if len(roster) - bool(cut) >= 15:
        return {'ok': False, 'reason': 'Resolve existing roster overflow before claiming.'}
    cut_projection = waiver_projection(active, save, cut, team_id) if cut else None
    contracts = {c['player_id']: c for c in active.get('contracts', [])}
    payment = None
    for row in rows:
        if row['season'] > season and row.get('option_type') == 'team_option' and not row.get('option_exercised'):
            continue
        cap = team_cap_summary(active, save, team_id, season=row['season'])
        if cap['unresolved_contract_count']:
            return {'ok': False, 'reason': 'Team salary requires review.'}
        total = cap['salary_total'] + row['salary']
        if cut:
            old = next((r.get('salary') for r in contracts.get(cut_id, {}).get('seasons', []) if r['season'] == row['season']), 0)
            debt = next((r.get('salary') for r in cut_projection['seasons'] if r['season'] == row['season']), 0)
            if old is None or debt is None:
                return {'ok': False, 'reason': 'Replacement salary requires review.'}
            total += debt - old
        if row['season'] == season:
            # FA-REAL: a claim is paid like a signing (cap_ledger): room, the minimum for a minimum contract, or the
            # full or room mid-level or the bi-annual, never past a hard cap the team has triggered. Only this
            # season's books decide (later seasons are the owner's concern, below).
            from .cap_ledger import absorb_route
            # AI front offices keep their mid-level for free agents (claims by room or the minimum, as before);
            # the user may spend an exception on a claim, as the rules allow.
            paid = absorb_route(active, save, team_id, float(row['salary']), total - cap['salary_total'], len(rows),
                                minimum=minimum_claim_contract(entry['contract']), season=season, exceptions=not ai)
            if not paid['ok']:
                return {'ok': False, 'reason': paid['reason']}
            payment = paid['payment']
        if ai and row['season'] == season:
            # Payroll discipline (TRADE-VOLUME): an AI claim must fit the owner's tax plan for this season, and a team
            # under the line never claims its way over it after the trade deadline (Atlanta, Feb 2028).
            from .payroll_plan import payroll_check, plain_words
            from .save import display_minutes_projection
            check = payroll_check(active, save, team_id, season, add_salary=total - cap['salary_total'],
                                  roster_delta=0 if cut else 1, minutes=display_minutes_projection(player),
                                  kind='waiver_claim')
            if not check['ok']:
                return {'ok': False, 'reason': plain_words(check), 'tax_plan': check}
    return {'ok': True, 'cut_player_id': cut_id, 'contract': entry['contract'], 'payment': payment,
            'cut_cost_millions': (cut_projection or {}).get('remaining_cost_millions', 0)}


def submit_claim(active, save, waiver_id, team_id, *, cut_id=None):
    entry = next((r for r in save.get('waiver_wire', []) if r['id'] == waiver_id and r['status'] == 'pending'), None)
    today = save.get('state', {}).get('current_date')
    if not entry or today >= entry['clearance_date']:
        raise ValueError('This waiver claim window has closed.')
    existing = next((c for c in entry['claims'] if c['team_id'] == team_id), None)
    if existing:
        return existing
    plan = claim_plan(active, save, entry, team_id, cut_id=cut_id)
    if not plan['ok']:
        raise ValueError(plan['reason'])
    claim = {'team_id': team_id, 'date': today, 'cut_player_id': plan['cut_player_id']}
    entry['claims'].append(claim)
    return claim


def priority(active, save, stamp):
    day = date.fromisoformat(stamp)
    history = save.get('season_history') or []
    previous = history[-1].get('team_records', {}) if history else {}
    records = previous if 7 <= day.month <= 11 else save.get('team_records', {})
    # Imported opening standings remain a fallback only when no played season exists.
    if not records:
        records = save.get('team_records', {})
    seed = save.get('meta', {}).get('seed', 1)
    def key(team):
        record = records.get(team['id'], {})
        games = int(record.get('wins') or 0) + int(record.get('losses') or 0)
        pct = int(record.get('wins') or 0) / games if games else .5
        tie = hashlib.sha256(f"{seed}:{day.year}:waiver-priority:{team['id']}".encode()).hexdigest()
        return pct, tie
    return [t['id'] for t in sorted(active.get('teams', []), key=key)]


def process_waivers(canonical, save, stamp):
    from .save import canonical_with_save, human_controlled_team_ids, add_news
    resolved = []
    due = sorted((r for r in save.get('waiver_wire', []) if r['status'] == 'pending' and r['clearance_date'] <= stamp), key=lambda r: (r['clearance_date'], r['id']))
    for entry in due:
        active = canonical_with_save(canonical, save)
        day = entry['clearance_date']
        human = human_controlled_team_ids(save)
        claims = {c['team_id']: c for c in entry['claims']}
        for tid in priority(active, save, day):
            if tid in human or tid in claims:
                continue
            plan = claim_plan(active, save, entry, tid, ai=True)
            if plan['ok']:
                claims[tid] = {'team_id': tid, 'date': day, 'cut_player_id': plan['cut_player_id'], 'source': 'ai'}
        entry['claims'] = sorted(claims.values(), key=lambda c: c['team_id'])
        winner = None
        winning_plan = None
        for tid in priority(active, save, day):
            claim = claims.get(tid)
            if not claim:
                continue
            plan = claim_plan(active, save, entry, tid, cut_id=claim.get('cut_player_id'))
            if plan['ok']:
                winner, winning_plan = claim, plan
                break
        debt = next(r for r in save['waived_salary_obligations'] if r['id'] == entry['id'])
        if winner:
            tid = winner['team_id']
            if winner.get('cut_player_id'):
                cut = next(p for p in active['players'] if p['id'] == winner['cut_player_id'])
                request_waiver(active, save, cut, tid, day)
            save.setdefault('roster_overrides', {})[entry['player_id']] = tid
            contract = deepcopy(entry['contract'])
            contract['team_id'] = tid
            save.setdefault('contract_overrides', {})[entry['player_id']] = contract
            if (winning_plan or {}).get('payment'):
                from .cap_ledger import commit
                commit(save, tid, entry['player_id'], winning_plan['payment'], day)
            for row in debt['seasons']:
                row['salary_before_claim'] = row['salary']
                row['salary'] = 0
                row['unverified_reserve'] = 0
            debt['unquantified'] = False
            debt['relief_status'] = 'existing_contract_assumed_by_claimant'
            entry.update(status='claimed', claimed_by_team_id=tid)
            save.setdefault('released_free_agents', {})[entry['player_id']]['status'] = 'claimed'
            save.setdefault('rotation_snapshots', {}).pop(tid, None)
            save.setdefault('starting_lineups', {}).pop(tid, None)
            headline = f"{entry['player_name']} claimed on waivers. Existing contract transferred."
        else:
            if entry['buyout']:
                for row in debt['seasons']:
                    row['salary_before_buyout'] = row['salary']
                    if row['salary'] is not None:
                        row['salary'] -= entry['buyout']['concessions'].get(row['season'], 0)
                debt['relief_status'] = 'fixed_buyout_applied_after_clearance'
            entry['status'] = 'cleared'
            save['free_agent_player_ids'] = sorted(set(save.get('free_agent_player_ids', [])) | {entry['player_id']})
            save.setdefault('released_free_agents', {})[entry['player_id']].update(status='available', cleared_date=day)
            headline = f"{entry['player_name']} cleared waivers and is a free agent."
        entry['resolved_date'] = day
        save.setdefault('transaction_logs', []).append({'id': entry['id'] + ':resolved', 'date': day,
            'transaction_type': 'waiver_claim' if winner else 'waiver_clearance', 'status': 'applied_to_save_ledger',
            'teams': [entry['team_id']] + ([winner['team_id']] if winner else []),
            'assets': {'player_id': entry['player_id']}, 'waiver_id': entry['id']})
        add_news(save, 'waivers', headline, date_value=day)
        resolved.append(entry)
    return resolved
