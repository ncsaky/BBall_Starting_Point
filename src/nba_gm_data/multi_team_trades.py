"""All-party trade graphs: value each roster once and settle on a private copy."""
from copy import deepcopy
import json
from types import SimpleNamespace

from . import transactions as tx
from .schema import CANONICAL_START_DATE, to_plain
from .utils import copy_plain, stable_id


def transfers_for_revalidation(candidate):
    legs = deepcopy(candidate['proposal']['transfers'])
    grants = {t['id']: t for t in candidate.get('pick_obligation_terms', [])
              if t.get('type') == 'pick_swap' and t.get('pending_asset_grant')}
    for leg in legs:
        for index, asset in enumerate(leg['assets']):
            if asset.get('kind') == 'pick_swap' and asset.get('id') in grants:
                leg['assets'][index] = {'kind': 'pick', 'value': grants[asset['id']]['primary_pick_id']}
    return legs


def evaluate_multi_team_trade(canonical, transfers, *, pick_rules=None, seed=1, date=None, config=None, proposal_id=None,
                              include_presentation=True, search_only=False):
    active = tx.with_transaction_context(canonical, config)
    date = date or active.get('meta', {}).get('current_date') or CANONICAL_START_DATE
    config = config or tx.default_transaction_model_config()
    if not isinstance(transfers, list) or not 2 <= len(transfers) <= 20:
        raise ValueError('Use 2-20 directed transfer legs.')
    sides = []
    for leg in transfers:
        sender = tx.resolve_team(active, leg['from_team_id'])
        receiver = tx.resolve_team(active, leg['to_team_id'])
        if sender['id'] == receiver['id'] or not leg.get('assets'):
            raise ValueError('Every leg must send assets to another team.')
        sides.append({'team': sender['id'], 'recipient': receiver['id'], 'assets': leg['assets']})
    ids = sorted({s[k] for s in sides for k in ('team', 'recipient')})
    if not 3 <= len(ids) <= 6:
        raise ValueError('Multi-team settlement supports 3-6 teams.')
    reached = {ids[0]}
    while True:
        more = reached | {s[k] for s in sides if s['team'] in reached or s['recipient'] in reached for k in ('team', 'recipient')}
        if more == reached:
            break
        reached = more
    if set(ids) != reached:
        raise ValueError('The trade must be one connected package.')
    from .trade_pick_terms import compile_pick_rules
    rules = deepcopy(pick_rules or [])
    active, assets, terms = compile_pick_rules(active, rules, sides)
    edges = []
    for side, selected in zip(sides, assets):
        sender, receiver = tx.resolve_team(active, side['team']), tx.resolve_team(active, side['recipient'])
        edges.append({'from_team_id': sender['id'], 'to_team_id': receiver['id'],
                      'from_abbrev': sender['abbrev'], 'to_abbrev': receiver['abbrev'],
                      'assets': tx.normalize_assets(active, sender, selected)})
    signature = [{'from_team_id': e['from_team_id'], 'to_team_id': e['to_team_id'],
                  'assets': [{'kind': a['kind'], 'id': a['id']} for a in e['assets']]} for e in edges]
    proposal = {'id': proposal_id or stable_id('multi_trade', date, json.dumps(signature, sort_keys=True), json.dumps(rules, sort_keys=True)),
                'date': date, 'format': 'multi_team_v1', 'team_ids': ids, 'transfers': edges}
    obj = SimpleNamespace(**proposal)
    legality = tx.trade_legality(active, obj, config)
    counts = active.get('_search_work_counts')
    if search_only and legality['status'] != 'legal':
        participant_evaluations = []
        if counts is not None: counts['skipped_reports.repairable'] += 1
    else:
        if counts is not None: counts['participant_reports.'+('presentation' if include_presentation else 'repairable')] += 1
        if active.get('_package_search_diagnostics') is not None and not include_presentation:
            active['_package_search_diagnostics']['full_evaluations'] += 1
        participant_evaluations = tx.evaluate_trade_participants(
            active, obj, legality, seed, config, include_presentation=include_presentation)
    evaluations = [to_plain(evaluation) for evaluation in participant_evaluations]
    result = {'proposal': proposal, 'legality': legality, 'evaluations': evaluations,
              'accepted_by_all': legality['status'] == 'legal' and all(e['accepted'] for e in evaluations),
              'evaluation_seed': seed, 'pick_rules': rules, 'pick_obligation_terms': terms,
              'pick_trade_terms': terms,
              'search_route': 'multi_team_package', 'combined_score': round(sum(e['net_value'] for e in evaluations), 3)}
    if include_presentation:
        from .trade_wants import asset_matches
        result.update(
            summary=tx.trade_headline_from_payload(proposal),
            value_breakdown=tx.trade_value_breakdown(active, proposal),
            wants_matches=[{'team_id': tid, 'asset_id': asset['id'], **match}
                           for tid, _, incoming in tx.trade_team_flows(proposal) for asset in incoming
                           for match in asset_matches(active, tid, asset)],
        )
    return result


def apply_multi_team_trade_to_state(save, candidate, date, *, canonical, config=None, save_label='in_memory'):
    from .save import canonical_with_save, add_news, add_league_event
    from .pick_presentation import materialize_nested_inputs
    proposal = candidate['proposal']
    pid = proposal['id']
    if canonical is None or save.get('version') != 'league_save_v1':
        return {'status': 'not_applied_rejected', 'notes': 'Multi-team trades require a live league context.'}
    if any(r.get('proposal_id') == pid for r in save.get('transaction_logs', [])):
        return {'status': 'already_applied', 'proposal_id': pid}
    # No authoritative state is touched until every participant passes.
    working = copy_plain(save)
    active = canonical_with_save(canonical, working)
    try:
        fresh = evaluate_multi_team_trade(active, transfers_for_revalidation(candidate), pick_rules=candidate.get('pick_rules'),
            seed=int(candidate.get('evaluation_seed', 1)), date=date, config=config, proposal_id=pid)
    except (ValueError, KeyError, TypeError) as exc:
        return {'status': 'not_applied_stale_assets', 'proposal_id': pid, 'issues': [str(exc)]}
    if fresh['legality']['status'] != 'legal':
        return {'status': 'not_applied_salary_legality', 'proposal_id': pid, 'legality': fresh['legality']}
    participants = fresh['proposal']['team_ids']
    human = set(active.get('_human_team_ids') or []) & set(participants)
    consent = candidate.get('offer_context') or {}
    explicit = {consent.get('override_team_id')} if consent.get('created_by_user') and consent.get('status') == 'user_override_pending_apply' else set()
    if len(human) > 1 or human - explicit:
        return {'status': 'not_applied_rejected', 'notes': 'Every human participant must explicitly approve; shared-human settlement is not supported yet.'}
    if any(not e['accepted'] for e in fresh['evaluations'] if e['perspective_team_id'] not in human):
        return {'status': 'not_applied_rejected', 'proposal_id': pid, 'evaluations': fresh['evaluations']}
    # Each directed leg has its own sender; apply the ordinary stale-right check.
    for edge in fresh['proposal']['transfers']:
        leg = {**edge, 'from_assets': edge['assets'], 'to_assets': [],
               'pick_obligation_terms': fresh['pick_obligation_terms']}
        issues = tx.trade_live_validation_issues(working, leg, date)
        if issues:
            return {'status': 'not_applied_stale_assets', 'proposal_id': pid, 'issues': issues}
    bundles = materialize_nested_inputs(active)
    bundled_ids = {oid for bundle in bundles.values() for oid in bundle['obligation_ids']}
    for edge in proposal['transfers']:
        for asset in edge['assets']:
            expected = asset.get('nested_entitlement') or (asset.get('pick_presentation') or {}).get('nested_entitlement')
            current = bundles.get(asset.get('id')) if asset.get('kind') == 'pick' else None
            if asset.get('kind') == 'pick_swap' and asset.get('id') in bundled_ids:
                return {'status': 'not_applied_stale_assets', 'issues': ['Trade the nested entitlement as one pick asset.']}
            if expected and (not current or expected['obligation_ids'] != current['obligation_ids']):
                return {'status': 'not_applied_stale_assets', 'issues': ['Nested entitlement changed.']}
            if current and current['rights_holder_team_id'] != edge['from_team_id']:
                return {'status': 'not_applied_stale_assets', 'issues': ['Nested entitlement ownership changed.']}
    live_terms = {row['id']: row for row in active.get('pick_obligations', [])}
    for row in working.get('pick_obligations', []):
        for field in ('nested_input', 'nested_other_input', 'nested_other_pick_id', 'nested_anchor_pick_id', 'allocation_slot_pick_ids'):
            if field in live_terms.get(row.get('id'), {}):
                row[field] = deepcopy(live_terms[row['id']][field])
    for edge in fresh['proposal']['transfers']:
        for asset in edge['assets']:
            dest, aid = edge['to_team_id'], asset['id']
            if asset['kind'] == 'player':
                working.setdefault('roster_overrides', {})[aid] = dest
            elif asset['kind'] == 'pick':
                expected = asset.get('nested_entitlement') or (asset.get('pick_presentation') or {}).get('nested_entitlement')
                bundle = bundles.get(aid)
                if expected and (not bundle or expected['obligation_ids'] != bundle['obligation_ids']):
                    return {'status': 'not_applied_stale_assets', 'issues': ['Nested entitlement changed.']}
                working.setdefault('draft_pick_overrides', {})[aid] = dest
                tx.update_retraded_pick_obligation(working, aid, dest, date)
                for oid in (bundle or {}).get('obligation_ids', []):
                    tx.update_retraded_pick_swap_obligation(working, oid, dest, date)
            elif asset['kind'] == 'pick_swap':
                tx.update_retraded_pick_swap_obligation(working, aid, dest, date)
    fresh['proposal']['id'] = pid
    tx.apply_pick_obligation_terms_to_save(working, fresh['proposal'], fresh['pick_obligation_terms'], date)
    for term in fresh['pick_obligation_terms']:
        if not any(o.get('id') == term['id'] for o in working.get('pick_obligations', [])):
            return {'status': 'not_applied_stale_assets', 'issues': ['A conditional right could not be created.']}
    for tid in participants:
        working.setdefault('rotation_snapshots', {}).pop(tid, None)
    log = {'id': stable_id('transaction_log', pid, date), 'date': date, 'transaction_type': 'trade',
           'proposal_id': pid, 'status': 'applied_to_save_ledger', 'teams': participants,
           'assets': {'format': 'multi_team_v1', 'transfers': deepcopy(fresh['proposal']['transfers'])},
           'evaluations': fresh['evaluations'], 'notes': 'Atomic multi-team settlement; all final rosters validated together.'}
    working.setdefault('transaction_logs', []).append(log)
    working['pending_trade_proposals'] = [c for c in working.get('pending_trade_proposals', []) if (c.get('proposal') or c).get('id') != pid]
    keys = tx.proposal_asset_identity_keys({**fresh, 'proposal': fresh['proposal']})
    pruned = tx.prune_trade_offers_touching_assets(working, keys, exclude_proposal_id=pid)
    headline = tx.trade_headline_from_payload(fresh['proposal'])
    add_news(working, 'trade', headline, date_value=date)
    add_league_event(working, 'trade', headline, date_value=date, team_ids=participants,
        player_ids=tx.trade_player_ids(fresh['proposal']), importance=.8, details=tx.trade_event_details_from_payload(fresh['proposal']))
    tx.queue_press_event_if_user_involved(working, 'trade', headline, participants, date)
    save.clear()
    save.update(working)
    return {'status': 'applied', 'save': save_label, 'transaction_log': log, 'pruned': pruned}


def facilitator_return_options(canonical, team_id, recipient, used):
    """Small real rights or expendable players, priced before full-GM review."""
    from .team_planning import core_commitment
    from .trade_pick_terms import pick_rule_lock_reason
    values = tx.player_asset_values_by_id(canonical)
    picks = sorted([p for p in tx.tradeable_picks_for_team(canonical, team_id)
                    if p.get('round') == 2 and f"pick:{p['id']}" not in used],
                   key=lambda p: (tx.pick_asset_value(p, 'neutral'), p['id']))
    options = [{'asset': {'kind': 'pick', 'value': p['id']}, 'rules': [],
                'value': tx.pick_asset_value(p, 'neutral')} for p in picks[:1]]
    swaps = tx.tradeable_pick_swaps_for_team(canonical, team_id)
    options += [{'asset': {'kind': 'pick_swap', 'value': s['id']}, 'rules': [],
                 'value': tx.pick_swap_asset_value(canonical, s)} for s in swaps
                if f"pick_swap:{s['id']}" not in used]
    other = [p for p in tx.tradeable_picks_for_team(canonical, recipient)
             if p.get('round') == 2 and f"pick:{p['id']}" not in used and not pick_rule_lock_reason(p)]
    for primary in picks[:2]:
        if pick_rule_lock_reason(primary):
            continue
        for comparison in other:
            if str(primary['season']) != str(comparison['season']):
                continue
            swap = {'team_a_pick_id': primary['id'], 'team_b_pick_id': comparison['id'], 'benefit': 'better'}
            options.append({'asset': {'kind': 'pick', 'value': primary['id']},
                'rules': [{'type': 'pick_swap', 'pick_id': primary['id'],
                           'other_pick_id': comparison['id'], 'benefit': 'better'}],
                'value': tx.pick_swap_asset_value(canonical, swap)})
    for player in canonical.get('players', []):
        pid = player['id']
        value = values.get(pid, {})
        if (player.get('team_id') == team_id and not player.get('_inactive_player')
                and f'player:{pid}' not in used and not core_commitment(canonical, team_id, pid)
                and not tx.effectively_untouchable(canonical, player)
                and float(value.get('on_court_value') or 0) < 55
                and float(value.get('development_upside') or 0) < 8):
            options.append({'asset': {'kind': 'player', 'value': pid}, 'rules': [],
                            'value': tx.market_trade_target_value(player, value)})
    unique = {}
    for option in sorted(options, key=lambda o: (o['value'], json.dumps(o, sort_keys=True))):
        unique.setdefault(json.dumps(option, sort_keys=True), option)
    return list(unique.values())[:3]


def facilitator_candidates(canonical, blocked, *, seed, date, limit=2, diagnostics=None, include_presentation=True):
    """Redirect a useful matching player; the third GM must want the full cost."""
    from .team_planning import core_commitment
    diag = diagnostics if diagnostics is not None else {}
    proposal = blocked.get('proposal') or {}
    if proposal.get('transfers'):
        return []
    issues = (blocked.get('legality') or {}).get('issues') or []
    if not any('matching tolerance' in issue or 'hard-cap' in issue or 'roster hard maximum' in issue or 'roster minimum' in issue for issue in issues):
        return []
    ids = tx.trade_team_ids(proposal)
    human = set(canonical.get('_human_team_ids') or [])
    base = [deepcopy(t) for t in tx.trade_transfers(proposal) if t['assets']]
    found = []
    attempt_start = diag.get('facilitator_attempts', 0)
    routes = [(index, edge, asset) for index, edge in enumerate(base) for asset in edge['assets']]
    existing = tx.proposal_asset_identity_keys(blocked)
    values = tx.player_asset_values_by_id(canonical)
    # Sometimes the buyer needs to send MORE salary, rather than redirect an
    # existing incoming player. Offer a non-core contract to a genuine buyer.
    for tid in ids:
        extras = [p for p in canonical['players'] if p.get('team_id') == tid
                  and f"player:{p['id']}" not in existing and not tx.effectively_untouchable(canonical, p)
                  and not core_commitment(canonical, tid, p['id'])
                  and float(values.get(p['id'], {}).get('on_court_value') or 0) < 76.5
                  and (tx.current_salary(tx.contract_for_player(canonical, p['id'])) or 0) > 1_000_000]
        extras.sort(key=lambda p: (-(tx.current_salary(tx.contract_for_player(canonical, p['id'])) or 0), p['id']))
        routes += [(None, {'from_team_id': tid, 'to_team_id': next(t for t in ids if t != tid)},
                    {'kind': 'player', 'id': p['id']}) for p in extras[:4]]
    for edge_index, edge, asset in routes:
        if asset['kind'] != 'player':
            continue
        player = tx.player_by_id(canonical, asset['id'])
        value = tx.player_asset_values_by_id(canonical).get(asset['id'], {})
        # Salary filler/rotation players, not diverting the primary star.
        if float(value.get('on_court_value') or 0) >= 76.5 or tx.effectively_untouchable(canonical, player):
            continue
        buyers = tx.buyer_teams_for_player(canonical, player)
        salary = tx.current_salary(tx.contract_for_player(canonical, asset['id']))
        season = str(canonical.get('meta', {}).get('active_season') or tx.CANONICAL_SEASON)
        tax = tx.cap_lines_for_season(season)['tax_line']
        for third in [t for t in buyers if t['id'] not in ids and t['id'] not in human
                      and salary is not None and tx.team_current_salary_total(canonical, t['id'])+salary <= tax][:5]:
            route = deepcopy(base)
            if edge_index is not None:
                route[edge_index]['assets'] = [a for a in route[edge_index]['assets'] if a['id'] != asset['id']]
            route = [t for t in route if t['assets']]
            route.append({'from_team_id': edge['from_team_id'], 'to_team_id': third['id'], 'assets': [asset]})
            probe = SimpleNamespace(transfers=route)
            config = tx.default_transaction_model_config()
            diag['facilitator_route_checks'] = diag.get('facilitator_route_checks', 0)+1
            if tx.trade_salary_legality(canonical, probe, config)['status'] != 'legal' or tx.roster_count_issues(canonical, probe, config):
                continue
            picks = sorted(tx.tradeable_picks_for_team(canonical, third['id']),
                key=lambda p: tx.pick_asset_value(p, 'neutral'))
            # A facilitator can contribute a modest pick for a wanted
            # player, or accept compensation for absorbing bad money.
            target = max(3., float(value.get('player_value') or 0)*.65)
            seconds = [p for p in picks if p.get('round') == 2]
            firsts = sorted([p for p in picks if p.get('round') == 1],
                            key=lambda p: abs(tx.pick_asset_value(p, 'neutral')-target))[:2]
            groups = [(p,) for p in sorted(seconds, key=lambda p: abs(tx.pick_asset_value(p, 'neutral')-target))[:2]+firsts]
            if len(seconds) >= 2:
                groups.append(tuple(seconds[-2:]))
            groups.sort(key=lambda group: abs(sum(tx.pick_asset_value(p, 'neutral') for p in group)-target))
            variants = [(third['id'], recipient, group) for group in groups
                        for recipient in dict.fromkeys((edge['from_team_id'], edge['to_team_id']))]
            payer_picks = [p for p in tx.tradeable_picks_for_team(canonical, edge['from_team_id'])
                           if p.get('round') == 2 and f"pick:{p['id']}" not in tx.proposal_asset_identity_keys(blocked)]
            variants += [(edge['from_team_id'], third['id'], (p,)) for p in payer_picks[:2]]
            for sender, receiver, group in variants:
                if diag.get('facilitator_attempts', 0) >= 64 or diag.get('facilitator_attempts', 0)-attempt_start >= 24:
                    return found
                legs = deepcopy(route)+[{'from_team_id': sender, 'to_team_id': receiver,
                                         'assets': [{'kind': 'pick', 'value': pick['id']} for pick in group]}]
                completions = [([], [])]
                if sender != third['id']:
                    used = tx.proposal_asset_identity_keys({'proposal': {'transfers': legs}})
                    compensation = sum(tx.pick_asset_value(p, 'neutral') for p in group)
                    completions = []
                    for counter in facilitator_return_options(canonical, third['id'], sender, used):
                        spec = counter['asset']
                        returned_salary = (tx.current_salary(tx.contract_for_player(canonical, spec['value']))
                                           if spec['kind'] == 'player' else 0)
                        if counter['value'] >= compensation or returned_salary is None or returned_salary >= salary:
                            continue
                        completions.append(([{'from_team_id': third['id'], 'to_team_id': sender,
                                              'assets': [spec]}], counter['rules']))
                for counter_legs, rules in completions:
                    if diag.get('facilitator_attempts', 0) >= 64 or diag.get('facilitator_attempts', 0)-attempt_start >= 24:
                        return found
                    diag['facilitator_attempts'] = diag.get('facilitator_attempts', 0)+1
                    try:
                        candidate = evaluate_multi_team_trade(canonical, deepcopy(legs)+counter_legs,
                                                             pick_rules=rules, seed=seed, date=date,
                                                             include_presentation=include_presentation,search_only=not include_presentation)
                    except (ValueError, KeyError):
                        continue
                    if candidate['accepted_by_all']:
                        candidate['search_route'] = 'salary_facilitator'
                        candidate['facilitator_team_id'] = third['id']
                        found.append(candidate)
                        diag['facilitator_agreements'] = diag.get('facilitator_agreements', 0)+1
                        if len(found) >= limit:
                            return found
    return found
