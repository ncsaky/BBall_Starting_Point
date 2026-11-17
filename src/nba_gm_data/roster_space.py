"""Recover modest value for planned cuts, without inventing willing buyers."""


def remember_target(save, team_id, player_id, aav, years, plan):
    if not plan.get('cuts') or float(plan.get('upgrade') or 0) <= 0:
        return
    if not plan.get('ok') and plan.get('reason') != 'waiver_cost_exceeds_marginal_upgrade':
        return
    state = save.setdefault('free_agency_state', {})
    targets = state.setdefault('roster_space_targets', {})
    day = int(state.get('day') or 1)
    old = targets.get(team_id, {})
    if old.get('day') == day and float(old.get('upgrade') or 0) >= float(plan['upgrade']):
        return
    targets[team_id] = {'team_id': team_id, 'player_id': player_id, 'day': day,
                        'aav_millions': aav, 'years': years, 'upgrade': plan['upgrade']}


def sale_bonus(canonical, team_id, incoming_assets, outgoing_assets, outgoing_value):
    intent = canonical.get('_roster_space_sale') or {}
    outgoing_ids = [a.get('id') for a in outgoing_assets if a.get('kind') == 'player']
    if (intent.get('team_id') != team_id or outgoing_ids != [intent.get('sell_player_id')]
            or len(outgoing_assets) != 1 or not incoming_assets
            or any(a.get('kind') not in {'pick', 'pick_swap'} for a in incoming_assets)):
        return 0.0
    if outgoing_ids[0] in canonical.get('team_plans', {}).get(team_id, {}).get('core_ids', []):
        return 0.0
    return min(8.0, outgoing_value*.30, max(0, float(intent.get('upgrade') or 0))*.5)


def sale_candidates(active, save, user_team_id, seed, *, diagnostics=None):
    from itertools import combinations
    from . import play as pl
    from .contract_protection import roster_signing_plan
    from .save import phase_for_date
    from .transactions import evaluate_trade, recently_traded_player_ids, recently_signed_player_ids, tradeable_picks_for_team, candidate_from_evaluation, package_value_for_team
    today = str(save.get('state', {}).get('current_date') or '')
    phase = save.get('state', {}).get('phase') or phase_for_date(today)
    # This route funds an AVAILABLE summer target, not a speculative signing
    # next summer. Never price lost in-season depth as though the gap is free.
    if phase != 'free_agency' or not '07-01' <= today[5:] <= '07-15':
        return []
    players = {p['id']: p for p in active.get('players', [])}
    values = {v['player_id']: v for v in active.get('player_asset_valuations', [])}
    day = int(save.get('free_agency_state', {}).get('day') or 1)
    human = pl.human_controlled_team_ids(save) | {user_team_id}
    locked = recently_traded_player_ids(active, today) | recently_signed_player_ids(active, today)
    pool = set(save.get('free_agent_player_ids') or [])
    evaluations = 0
    for tid, target in sorted(save.get('free_agency_state', {}).get('roster_space_targets', {}).items()):
        if tid in human or target['day'] != day or target['player_id'] not in pool:
            continue
        player = players.get(target['player_id'])
        if not player or player.get('team_id'):
            continue
        team = pl.team_by_id(active, tid)
        preview = pl.build_free_agency_offer_record(active, save, player, team, target['years'], target['aav_millions'],
            float(save['free_agency_state'].get('player_asks_millions', {}).get(player['id']) or target['aav_millions']), seed, 'ai')
        rivals = [float(o.get('interest_score') or 0) for o in pl.active_offers_for_player(save, player['id']) if o.get('team_id') != tid]
        if preview['interest_score'] < pl.free_agency_accept_threshold(player, day) or (rivals and max(rivals) > preview['interest_score']+3):
            if diagnostics is not None:
                diagnostics.setdefault('target_uncompetitive', []).append({'team': tid, 'target': player['id'],
                    'interest': preview['interest_score'], 'threshold': pl.free_agency_accept_threshold(player, day), 'rivals': rivals})
            continue
        plan = roster_signing_plan(active, save, player, tid, target['aav_millions'], target['years'])
        surplus = list(dict.fromkeys([cut['player_id'] for cut in plan.get('cuts', [])] + plan.get('surplus_player_ids', [])))
        surplus.sort(key=lambda pid: (-float(values.get(pid, {}).get('player_value') or 0), pid))
        for pid in surplus[:5]:
            outgoing = players.get(pid)
            if not outgoing or outgoing.get('team_id') != tid or pid in locked:
                continue
            if pid in active.get('team_plans', {}).get(tid, {}).get('core_ids', []):
                continue
            value = float(values.get(pid, {}).get('player_value') or 0)
            if not 1 <= value <= 65:
                continue
            after_sale = {**active, 'players': [dict(p, team_id=None) if p['id'] == pid else p for p in active.get('players', [])]}
            after_save = {**save, 'roster_overrides': {**save.get('roster_overrides', {}), pid: None}}
            reserved = pl.active_bid_commitment(save, tid, exclude_player_id=player['id'])
            if not pl.signing_cap_check(after_sale, after_save, team['abbrev'], target['aav_millions'], reserved_millions=reserved).get('ok'):
                continue
            after_plan = roster_signing_plan(after_sale, after_save, player, tid, target['aav_millions'], target['years'])
            if not after_plan.get('ok'):
                continue
            context = {**active, '_roster_space_sale': {**target, 'sell_player_id': pid}}
            player_evaluations = 0
            buyers = []
            for buyer in sorted(active.get('teams', []), key=lambda t: t['id']):
                if buyer['id'] in human | {tid}:
                    continue
                salary = float(pl.current_salary(pl.contract_for_player(active, pid)) or 0)/1_000_000
                buyer_plan = roster_signing_plan(active, save, outgoing, buyer['id'], salary, 1)
                if not buyer_plan.get('ok'):
                    continue
                buyers.append((buyer, buyer_plan))
            # Search genuine fits first rather than spending the entire budget
            # on the first four team IDs. A single second cannot buy every
            # useful reserve; also try small bundles, with normal buyer vetoes.
            buyers.sort(key=lambda item: (-package_value_for_team(active, [{'kind': 'player', 'id': pid}], item[0]['id'])
                        if active.get('team_strategic_states') else -float(item[1].get('upgrade') or 0), item[0]['id']))
            for buyer, buyer_plan in buyers[:6]:
                picks = [p for p in tradeable_picks_for_team(active, buyer['id']) if int(p.get('round') or 0) == 2]
                picks = sorted(picks, key=lambda p: (package_value_for_team(active, [{'kind': 'pick', 'id': p['id']}], buyer['id'])
                               if active.get('team_strategic_states') else 0, p['id']))[:3]
                packages = [list(combo) for count in (1, 2, 3) for combo in combinations(picks, count)]
                for package in packages:
                    if evaluations >= 64:
                        return []
                    if player_evaluations >= 12:
                        break
                    evaluations += 1
                    player_evaluations += 1
                    try:
                        report = evaluate_trade(context, team['abbrev'], buyer['abbrev'],
                            [{'kind': 'player', 'value': pid}], [{'kind': 'pick', 'value': pick['id']} for pick in package], seed=seed, date=today)
                    except ValueError:
                        continue
                    if not report.get('accepted_by_all') or report.get('legality', {}).get('status') != 'legal':
                        if diagnostics is not None:
                            diagnostics.setdefault('rejections', []).append({'seller': tid, 'buyer': buyer['id'], 'player': pid,
                                'picks': len(package), 'legality': report.get('legality'), 'evaluations': report.get('evaluations')})
                        continue
                    # Discount, not dumping a valuable player for nothing.
                    proposal = report['proposal']
                    recovered = package_value_for_team(active, proposal['to_assets'], tid, outgoing_assets=proposal['from_assets'])
                    surrendered = package_value_for_team(active, proposal['from_assets'], tid)
                    if recovered < surrendered*(.85 if value >= 50 else .70):
                        continue
                    candidate = candidate_from_evaluation(active, report)
                    candidate['free_agency_context'] = {'kind': 'roster_space_sale', 'target': target,
                                                        'sold_player_id': pid, 'reason': 'recover_value_before_planned_cut'}
                    return [candidate]
    return []


def activate_target(canonical, save, target, seed):
    from . import play as pl
    from .contract_protection import roster_signing_plan
    active = pl.canonical_with_save(canonical, save)
    player = next((p for p in active.get('players', []) if p['id'] == target['player_id']), None)
    if not player or player.get('team_id') or player['id'] not in set(save.get('free_agent_player_ids') or []):
        return False
    tid = target['team_id']
    if pl.active_offer_exists(save, player['id'], tid):
        save.setdefault('free_agency_state', {}).setdefault('roster_space_pursuits', {})[tid] = {
            **target, 'status': 'existing_active_bid', 'date': save.get('state', {}).get('current_date')}
        return False
    team = pl.team_by_id(active, tid)
    reserved = pl.active_bid_commitment(save, tid, exclude_player_id=player['id'])
    if not pl.signing_cap_check(active, save, team['abbrev'], target['aav_millions'], reserved_millions=reserved).get('ok'):
        return False
    plan = roster_signing_plan(active, save, player, tid, target['aav_millions'], target['years'])
    if not plan.get('ok'):
        return False
    ask = float(save.get('free_agency_state', {}).get('player_asks_millions', {}).get(player['id']) or target['aav_millions'])
    offer = pl.build_free_agency_offer_record(active, save, player, team, target['years'], target['aav_millions'], ask, seed, 'ai')
    offer['roster_plan'] = plan
    save.setdefault('free_agent_offers', []).append(offer)
    save.setdefault('free_agency_state', {}).setdefault('roster_space_pursuits', {})[tid] = {
        **target, 'status': 'bid_submitted', 'offer_id': offer['id'], 'date': save.get('state', {}).get('current_date')}
    return True
