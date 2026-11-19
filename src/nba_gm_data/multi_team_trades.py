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
    joiners = set(candidate.get('joiner_team_ids') or [])
    if joiners and not human:
        # Trade step 4: an AI-only deal built with joining teams is re-checked under the same rule it was made with
        # (main teams within the two-team negotiation bounds, joining teams outright).
        if not bounded_multi_team_accept(active, fresh, joiners):
            return {'status': 'not_applied_rejected', 'proposal_id': pid, 'evaluations': fresh['evaluations']}
        fresh = mark_multi_team_accepted(fresh, joiners)
    elif any(not e['accepted'] for e in fresh['evaluations'] if e['perspective_team_id'] not in human):
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
    if candidate.get('trade_reasons'):
        log['trade_reasons'] = deepcopy(candidate['trade_reasons'])  # every team's reason in plain words (step 4)
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
                    if not candidate['accepted_by_all'] and not human & set(tx.trade_team_ids(candidate)) and \
                            bounded_multi_team_accept(canonical, candidate, {third['id']}):
                        # Trade step 4: the two main teams under the two-team negotiation bounds, the third team
                        # (which receives a player it wants) outright.
                        candidate = mark_multi_team_accepted(candidate, {third['id']})
                    if candidate['accepted_by_all']:
                        candidate['search_route'] = 'salary_facilitator'
                        candidate['facilitator_team_id'] = third['id']
                        found.append(candidate)
                        diag['facilitator_agreements'] = diag.get('facilitator_agreements', 0)+1
                        if len(found) >= limit:
                            return found
    return found


# ===================================================================================================================
# Trade step 4: three- and four-team trades built from near-misses of the target search
# (docs/agents/tasks/trade-step4-multi-team-plan.md; report docs/agents/tasks/trade-step4-multi-team.md).
#
# Real multi-team trades (data/research/real_trades/trades_2025_2027.json) join a third team for a stated reason,
# most often tax or apron pressure: a team that must shed salary, and a team with room that takes it and is paid in
# second-round picks (Cleveland / Sacramento / Chicago and Detroit / Chicago / Minnesota at the 2026 deadline, Minnesota
# / Brooklyn / Chicago on draft night). This stage starts from two-team deals the target search almost made (one team
# a little short of its price, every other check passed) and asks whether a third team fixes the remaining problem:
#
# 1. **Reroute** a player the short team does not want (salary it would absorb for nothing, or a contract that runs
#    past its plans) to a team with room under the tax that takes him for picks. The team that sent him pays, since it
#    needed his salary out to match.
# 2. **Shed**: the short team adds one of its own contracts it can spare, which a team with room absorbs for picks;
#    the tax it saves (trade 2b) closes the gap. This is the Cleveland-saves-$40M pattern.
#
# A fourth team joins only when a three-team version is still short and a second absorber fixes it. Every team must
# pass its own acceptance check: the two main teams under the same bounded negotiation as two-team AI trades, the
# absorber strictly (it joins only because it is paid to). Each team's reason is stated in plain words.
#
# The human team is never an absorber in AI-to-AI deals. When an AI-only absorber cannot be found, the same route is
# offered to the human team as an incoming offer ("X pays you two seconds to absorb this contract"), which the user
# accepts or declines in the existing offers flow (user decision, 2026-11-19); it is never executed automatically.
#
# Draft-night chains are not built here (another agent is rebuilding draft night). The hook for them is the same
# near-miss shape: a pick-for-pick deal where the team trading down wants a second pick from a third team.
# ===================================================================================================================
MAX_TEAMS = 4
NEAR_MISSES_KEPT = {1: 10, 2: 24}       # near-miss two-team deals considered per market day
REPAIR_EVALUATIONS = {1: 16, 2: 48}     # full multi-team acceptance checks per market day
ABSORBERS_PER_PLAYER = 3
NEAR_MISS_GAP = 45.0                    # a main team may be this far below its price before a repair is tried
REPAIR_MIN_GAIN = 2.0                   # a reroute or shed must improve the short team's price by at least this
ABSORB_MIN_SALARY = 2_500_000
ABSORB_MAX_SECONDS = 3
ROSTER_LIMIT = 15
SPARE_MAX_SALARY = 3_000_000


def bounded_multi_team_accept(canonical, candidate, joiner_ids) -> bool:
    """Acceptance for an AI-only multi-team deal: the main teams under the same bounded negotiation as two-team AI
    trades (each at most 9 short of even, all main teams' nets summing to at least -2, no team giving up most of a
    small asset for little), every joining team strictly (net at or above its own threshold)."""
    if (candidate.get('legality') or {}).get('status') != 'legal':
        return False
    if tx.multi_team_participation_issues(canonical, candidate):
        return False
    evaluations = candidate.get('evaluations') or []
    ids = set(tx.trade_team_ids(candidate))
    if {e.get('perspective_team_id') for e in evaluations} != ids:
        return False
    if any(e.get('decision') in {'reject_premium_return', 'reject_roster_plan', 'reject_pick_investment'}
           for e in evaluations):
        return False
    human = set(canonical.get('_human_team_ids') or [])
    core_nets = []
    for e in evaluations:
        tid = e.get('perspective_team_id')
        if tid in human:
            continue
        net = float(e.get('net_value') or 0.0)
        if any(str(r).startswith('Core commitment:') for r in e.get('decision_reasons') or []):
            return False
        if tid in joiner_ids:
            if not e.get('accepted'):
                return False
            continue
        if e.get('accepted'):
            core_nets.append(net)
            continue
        outgoing = float(e.get('outgoing_value') or 0.0)
        if net < -9.0 or (outgoing > 0 and net < -max(1.5, outgoing * .5)):
            return False
        core_nets.append(net)
    return sum(core_nets) >= -2.0


def mark_multi_team_accepted(candidate, joiner_ids):
    """Record the bounded acceptance of the main teams (the joiners already accepted outright)."""
    updated = json.loads(json.dumps(candidate))
    updated['accepted_by_all'] = True
    updated['joiner_team_ids'] = sorted(joiner_ids)
    if not all(e.get('accepted') for e in updated.get('evaluations', [])):
        updated['ai_acceptance_override'] = {
            'status': 'accepted_by_bounded_ai_discretion',
            'notes': 'The main teams accept within the two-team negotiation bounds; every joining team accepts outright.'}
        for evaluation in updated.get('evaluations', []):
            if not evaluation.get('accepted') and float(evaluation.get('net_value') or 0.0) >= -9.0:
                evaluation['accepted'] = True
                evaluation['decision'] = 'accept_bounded_ai_discretion'
                evaluation.setdefault('reasons', []).append('bounded_ai_discretion')
    return updated


def legs_from_candidate(candidate):
    """Directed legs ({from_team_id, to_team_id, assets: [{kind, value}]}) for a two- or multi-team candidate."""
    proposal = candidate.get('proposal') or candidate
    legs = []
    for transfer in tx.trade_transfers(proposal):
        if transfer['assets']:
            legs.append({'from_team_id': transfer['from_team_id'], 'to_team_id': transfer['to_team_id'],
                         'assets': [{'kind': a['kind'], 'value': a['id']} for a in transfer['assets']]})
    return legs


def _flows(legs):
    """team id -> (incoming asset dicts, outgoing asset dicts) in the {kind, id} shape the value functions read."""
    flows = {}
    for leg in legs:
        out = flows.setdefault(leg['from_team_id'], ([], []))[1]
        inc = flows.setdefault(leg['to_team_id'], ([], []))[0]
        for spec in leg['assets']:
            asset = {'kind': spec['kind'], 'id': spec.get('value', spec.get('id'))}
            out.append(asset)
            inc.append(asset)
    return flows


def _short_teams(candidate, human):
    """Main teams below their own price, most short first: (team id, net - threshold)."""
    rows = []
    for e in candidate.get('evaluations') or []:
        tid = e.get('perspective_team_id')
        if tid in human:
            continue
        gap = float(e.get('net_value') or 0.0) - float(e.get('acceptance_threshold') or 0.0)
        if gap < 0:
            rows.append((tid, gap))
    return sorted(rows, key=lambda r: (r[1], r[0]))


def near_miss(canonical, candidate) -> bool:
    """A legal deal every team would make if one or two of them were a little less short (no hard rule broken)."""
    if (candidate.get('legality') or {}).get('status') != 'legal':
        return False
    if (candidate.get('pick_obligation_terms') or candidate.get('pick_trade_terms')):
        return False
    evaluations = candidate.get('evaluations') or []
    if any(e.get('decision') in {'reject_premium_return', 'reject_pick_investment'} for e in evaluations):
        return False
    if any(str(r).startswith('Core commitment:') for e in evaluations for r in e.get('decision_reasons') or []):
        return False
    shorts = _short_teams(candidate, set(canonical.get('_human_team_ids') or []))
    return bool(shorts) and shorts[0][1] >= -NEAR_MISS_GAP


def _unmovable(canonical):
    """Players who cannot be traded today (traded or signed too recently); memoized per league state."""
    memo = canonical.get('_multi_team_unmovable')
    date = (canonical.get('meta') or {}).get('current_date')
    if memo is None or memo[0] is not canonical.get('players') or memo[1] != date:
        ids = set(tx.recently_traded_player_ids(canonical, date)) | set(tx.recently_signed_player_ids(canonical, date))
        memo = (canonical.get('players'), date, ids)
        canonical['_multi_team_unmovable'] = memo
    return memo[2]


def _season_payroll(canonical, team_id):
    return tx.team_current_salary_total(canonical, team_id)


def _team_players(canonical, team_id):
    return [p for p in canonical.get('players', []) if p.get('team_id') == team_id and not p.get('_inactive_player')]


def absorber_return(canonical, absorber_id, payer_id, used, payment_value):
    """What a team taking salary sends back: a nominal second-round swap or its cheapest second (worth less than it
    is paid), or, when its roster is full, its least valuable minimum-salary player outside the rotation."""
    from .team_planning import core_commitment
    values = tx.player_asset_values_by_id(canonical)
    players = _team_players(canonical, absorber_id)
    if len(players) >= ROSTER_LIMIT:
        spare = [p for p in players if f"player:{p['id']}" not in used
                 and (tx.current_salary(tx.contract_for_player(canonical, p['id'])) or 0) <= SPARE_MAX_SALARY
                 and tx.display_minutes_projection(p) < 10.0 and not core_commitment(canonical, absorber_id, p['id'])
                 and not tx.effectively_untouchable(canonical, p)]
        if not spare:
            return None
        player = min(spare, key=lambda p: (float(tx.valuation_or_fallback(values, p['id'], p).get('player_value') or 0), p['id']))
        return {'asset': {'kind': 'player', 'value': player['id']}, 'rules': []}
    for option in facilitator_return_options(canonical, absorber_id, payer_id, used):
        if option['asset']['kind'] != 'player' and option['value'] < payment_value:
            return option
    return None


def absorber_teams(canonical, player_id, exclude, *, human_ok=False):
    """Teams that could take the player's salary: under the tax line after taking it, not in the deal."""
    salary = tx.current_salary(tx.contract_for_player(canonical, player_id)) or 0.0
    season = str(canonical.get('meta', {}).get('active_season') or tx.CANONICAL_SEASON)
    lines = tx.cap_lines_for_season(season)
    human = set(canonical.get('_human_team_ids') or [])
    out = []
    for team in sorted(canonical.get('teams', []), key=lambda t: t['id']):
        tid = team['id']
        if tid in exclude or (tid in human) != human_ok:
            continue
        if _season_payroll(canonical, tid) + salary > lines['tax_line']:
            continue
        out.append(tid)
    return out


def absorber_price(canonical, absorber_id, player_id, back, config, *, as_ai=False):
    """Points the absorber needs to be paid to take the player (its own quick price, plus its threshold)."""
    from . import trade_targets as tt
    from .trade_tax import absorb_cost
    incoming = [{'kind': 'player', 'id': player_id}]
    outgoing = [{'kind': b['kind'], 'id': b['value']} for b in back]
    if as_ai:  # the human team's price, as an AI team in its place would see it (for offers it may decline)
        human_ids = canonical.get('_human_team_ids')
        canonical['_human_team_ids'] = [t for t in (human_ids or []) if t != absorber_id]
        try:
            cost = absorb_cost(canonical, absorber_id, incoming, outgoing)
        finally:
            canonical['_human_team_ids'] = human_ids
        return max(0.0, -cost)  # the user judges the player himself; the payment covers the dead money
    net = tt.quick_net(canonical, absorber_id, incoming, outgoing, config)
    return max(0.0, tx.acceptance_threshold(canonical, absorber_id, config) - net)


def payment_picks(canonical, payer_id, absorber_id, need, used, *, allow_first):
    """The payer's cheapest second-round picks (then its cheapest first) that the absorber values at ``need``."""
    picks = [p for p in tx.tradeable_picks_for_team(canonical, payer_id) if f"pick:{p['id']}" not in used]
    state = next((s for s in canonical.get('team_strategic_states', []) if s.get('team_id') == absorber_id), {})
    phase = state.get('phase', 'balanced')
    config = tx.default_transaction_model_config()

    def worth(pick):
        asset = {'kind': 'pick', 'id': pick['id']}
        return tx.pick_asset_value(pick, phase) + tx.strategic_fit_adjustment(canonical, [asset], [], absorber_id, config)

    seconds = sorted((p for p in picks if int(p.get('round') or 0) == 2), key=lambda p: (tx.pick_asset_value(p, 'neutral'), p['id']))
    if need <= 0:
        return []
    chosen, total = [], 0.0
    for pick in seconds[:ABSORB_MAX_SECONDS]:
        chosen.append(pick)
        total += worth(pick)
        if total >= need:
            return chosen
    if allow_first:
        firsts = sorted((p for p in picks if int(p.get('round') or 0) == 1), key=lambda p: (tx.pick_asset_value(p, 'neutral'), p['id']))
        for pick in firsts:
            if worth(pick) >= need:
                return [pick]
    return None


def _evaluate(canonical, legs, rules, seed, date, diag):
    diag['multi_team_evaluations'] = diag.get('multi_team_evaluations', 0) + 1
    try:
        return evaluate_multi_team_trade(canonical, deepcopy(legs), pick_rules=rules, seed=seed, date=date,
                                         include_presentation=False, search_only=True)
    except (ValueError, KeyError, TypeError):
        return None


def _absorb_route(canonical, legs, mover_id, sender_id, absorber_id, payer_id, config, *, human_absorber=False):
    """Legs with ``mover_id`` sent by ``sender_id`` to ``absorber_id``, paid by ``payer_id`` in picks, and the
    absorber's nominal return to the payer. None when no payment or return works."""
    new = deepcopy(legs)
    for leg in new:
        leg['assets'] = [a for a in leg['assets'] if not (a['kind'] == 'player' and a['value'] == mover_id)]
    new = [leg for leg in new if leg['assets']]
    used = tx.proposal_asset_identity_keys({'proposal': {'transfers': [
        {**leg, 'assets': [{'kind': a['kind'], 'id': a['value']} for a in leg['assets']]} for leg in legs]}})
    probe_back = []
    need = absorber_price(canonical, absorber_id, mover_id, probe_back, config, as_ai=human_absorber)
    if human_absorber:
        need = max(need, 1.0)  # a user is always offered at least a second for taking salary
    picks = payment_picks(canonical, payer_id, absorber_id, need + 1.0, used, allow_first=need >= 30.0)
    if picks is None:
        return None
    used |= {f"pick:{p['id']}" for p in picks}
    payment_value = sum(tx.pick_asset_value(p, 'neutral') for p in picks)
    back = absorber_return(canonical, absorber_id, payer_id, used, payment_value if picks else 99.0)
    if back is None:
        return None
    if back['asset']['kind'] == 'player' and not human_absorber:
        # A returned player changes the absorber's own price; reprice with him going out.
        need = absorber_price(canonical, absorber_id, mover_id, [back['asset']], config)
        picks = payment_picks(canonical, payer_id, absorber_id, need + 1.0, used - {f"pick:{p['id']}" for p in picks},
                              allow_first=need >= 30.0)
        if picks is None:
            return None
    to_absorber = [{'kind': 'player', 'value': mover_id}]
    if sender_id == payer_id:
        to_absorber += [{'kind': 'pick', 'value': p['id']} for p in picks]
        new.append({'from_team_id': sender_id, 'to_team_id': absorber_id, 'assets': to_absorber})
    else:
        new.append({'from_team_id': sender_id, 'to_team_id': absorber_id, 'assets': to_absorber})
        if picks:
            new.append({'from_team_id': payer_id, 'to_team_id': absorber_id,
                        'assets': [{'kind': 'pick', 'value': p['id']} for p in picks]})
    new.append({'from_team_id': absorber_id, 'to_team_id': payer_id, 'assets': [back['asset']]})
    return {'legs': new, 'rules': back['rules'], 'picks': picks, 'absorber_id': absorber_id, 'payer_id': payer_id,
            'mover_id': mover_id, 'sender_id': sender_id, 'returned': back['asset']}


def repair_routes(canonical, candidate, config, *, human_absorber=False, joiners=None, excluded=None):
    """Ways a third team could fix the most-short main team, best first (quick prices only). ``joiners``: teams that
    already joined as absorbers (they must stay above their price); ``excluded``: players that cannot move today."""
    from . import trade_targets as tt
    from .team_planning import core_commitment
    human = set(canonical.get('_human_team_ids') or [])
    excluded = excluded if excluded is not None else _unmovable(canonical)
    legs = legs_from_candidate(candidate)
    teams = {leg[k] for leg in legs for k in ('from_team_id', 'to_team_id')}
    if len(teams) >= MAX_TEAMS:
        return []
    shorts = _short_teams(candidate, human)
    if not shorts:
        return []
    short_id, gap = shorts[0]
    flows = _flows(legs)
    incoming, outgoing = flows[short_id]
    base = tt.quick_net(canonical, short_id, incoming, outgoing, config)
    moves = []
    # 1. Reroute a player the short team would rather not take.
    for asset in incoming:
        if asset['kind'] != 'player':
            continue
        salary = tx.current_salary(tx.contract_for_player(canonical, asset['id'])) or 0.0
        if salary < ABSORB_MIN_SALARY:
            continue
        rest = [a for a in incoming if a is not asset]
        if not any(a['kind'] == 'player' or a['kind'] == 'pick' for a in rest):
            continue
        gain = tt.quick_net(canonical, short_id, rest, outgoing, config) - base
        if gain >= REPAIR_MIN_GAIN:
            sender = next(leg['from_team_id'] for leg in legs if leg['to_team_id'] == short_id
                          and any(a['kind'] == 'player' and a['value'] == asset['id'] for a in leg['assets']))
            moves.append((gain, 'reroute', asset['id'], sender, sender))
    # 2. Shed one of the short team's own spare contracts.
    plan = (canonical.get('team_plans') or {}).get(short_id) or {}
    core = set(plan.get('core_ids') or [])
    out_ids = {a['id'] for a in outgoing}
    from .trade_tax import tax_value
    for player in _team_players(canonical, short_id):
        pid = player['id']
        if (pid in out_ids or pid in core or pid in excluded or core_commitment(canonical, short_id, pid)
                or tx.effectively_untouchable(canonical, player)):
            continue
        salary = tx.current_salary(tx.contract_for_player(canonical, pid)) or 0.0
        if salary < ABSORB_MIN_SALARY:
            continue
        age = tx.maybe_float(player.get('display_age', player.get('age'))) or 27.0
        if age < 24.0:
            continue
        shed = outgoing + [{'kind': 'player', 'id': pid}]
        if tax_value(canonical, short_id, incoming, shed) - tax_value(canonical, short_id, incoming, outgoing) <= 1.0:
            continue  # only a tax saving justifies adding a contract to the deal
        gain = tt.quick_net(canonical, short_id, incoming, shed, config) - base
        if gain >= REPAIR_MIN_GAIN:
            moves.append((gain, 'shed', pid, short_id, short_id))
    moves.sort(key=lambda m: (-m[0], m[1], m[2]))
    routes = []
    proposal = candidate.get('proposal') or {}
    if not human_absorber and not proposal.get('transfers') and short_id == proposal.get('from_team_id'):
        # The seller of a two-team deal is short: a third team may have the piece it wants.
        routes += piece_routes(canonical, legs, short_id, gap, config, excluded, joiners)
    for gain, kind, mover, sender, payer in moves[:4]:
        for absorber_id in absorber_teams(canonical, mover, teams, human_ok=human_absorber)[:12]:
            route = _absorb_route(canonical, legs, mover, sender, absorber_id, payer, config, human_absorber=human_absorber)
            if route is None:
                continue
            route.update(kind=kind, gain=gain, short_id=short_id)
            # Quick prices for every AI team in the new deal: the absorber must clear its own price, the main teams
            # the two-team negotiation bounds (with the same margin the two-team prescreen allows).
            quick = {}
            for tid, (inc, out) in _flows(route['legs']).items():
                if tid in human:
                    continue
                quick[tid] = tt.quick_net(canonical, tid, inc, out, config) - tx.acceptance_threshold(canonical, tid, config)
            main = [v for tid, v in quick.items() if tid != absorber_id and tid not in (joiners or ())]
            if (quick.get(absorber_id, 0.0) < -tt.PRESCREEN_TOLERANCE
                    or any(quick.get(j, 0.0) < -tt.PRESCREEN_TOLERANCE for j in (joiners or ()))
                    or (main and (min(main) < -9.0 - tt.PRESCREEN_TOLERANCE or sum(main) < -2.0 - tt.PRESCREEN_TOLERANCE))):
                continue
            route['quick'] = quick
            route['absorber_quick'] = quick.get(absorber_id, 0.0)
            route['score'] = min(main) if main else 0.0
            routes.append(route)
            if len([r for r in routes if r['mover_id'] == mover]) >= ABSORBERS_PER_PLAYER:
                break
    routes.sort(key=lambda r: (-(r['score'] + min(r.get('absorber_quick', 0.0), 6.0)), r['absorber_id'], r['mover_id']))
    return routes


PIECE_CANDIDATES = 4


def piece_routes(canonical, legs, short_id, gap, config, excluded, joiners):
    """The missing piece: a third team sends the short team a player it is looking for, and the other main team pays
    the third team in picks (Detroit / Chicago / Minnesota, 2026: Chicago turned Huerter into the younger Ivey while
    Minnesota paid to clear salary). The piece must fit one of the short team's own targets (trade step 2), and the
    third team must be willing: he is not a young player it builds around, and it is paid at least its own price."""
    from . import trade_targets as tt
    from .team_planning import core_commitment
    human = set(canonical.get('_human_team_ids') or [])
    teams = {leg[k] for leg in legs for k in ('from_team_id', 'to_team_id')}
    payers = sorted({leg['from_team_id'] for leg in legs if leg['to_team_id'] == short_id} - {short_id})
    if len(payers) != 1:
        return []
    payer_id = payers[0]
    flows = _flows(legs)
    incoming, outgoing = flows[short_id]
    base = tt.quick_net(canonical, short_id, incoming, outgoing, config)
    targets = tt.team_trade_targets(canonical, short_id)
    if not targets:
        return []
    season = str(canonical.get('meta', {}).get('active_season') or tx.CANONICAL_SEASON)
    room = tx.cap_lines_for_season(season)['tax_line'] - _season_payroll(canonical, short_id)
    options = []
    for row in tt.player_rows(canonical).values():
        third = row['team_id']
        if third in teams or third in human or row['id'] in excluded or row['salary'] > max(room, 0.0) + 1.0:
            continue
        if not any(tt.target_match(t, row) is not None for t in targets):
            continue
        stance = tt.team_stance(tt._state(canonical, third))
        reasons = tt.team_sell_reasons(canonical, third).get(row['id'], [])
        if (core_commitment(canonical, third, row['id']) or tx.effectively_untouchable(canonical, row['player'])
                or (tt.young_piece_kept(row, stance) and not tt.exposing_reasons(reasons))):
            continue
        gain = tt.quick_net(canonical, short_id, incoming + [{'kind': 'player', 'id': row['id']}], outgoing, config) - base
        if gain < -gap:
            continue
        ask = tt.asking_price(canonical, third, row['id'], config)['ask']
        options.append((ask - gain, row, gain, ask))
    options.sort(key=lambda o: (o[0], o[1]['id']))
    used = tx.proposal_asset_identity_keys({'proposal': {'transfers': [
        {**leg, 'assets': [{'kind': a['kind'], 'id': a['value']} for a in leg['assets']]} for leg in legs]}})
    routes = []
    for _, row, gain, ask in options[:PIECE_CANDIDATES]:
        picks = payment_picks(canonical, payer_id, row['team_id'], max(ask, 1.0), used, allow_first=ask >= 25.0)
        if not picks:
            continue
        new = deepcopy(legs) + [
            {'from_team_id': row['team_id'], 'to_team_id': short_id, 'assets': [{'kind': 'player', 'value': row['id']}]},
            {'from_team_id': payer_id, 'to_team_id': row['team_id'], 'assets': [{'kind': 'pick', 'value': p['id']} for p in picks]}]
        quick = {tid: tt.quick_net(canonical, tid, inc, out, config) - tx.acceptance_threshold(canonical, tid, config)
                 for tid, (inc, out) in _flows(new).items() if tid not in human}
        main = [v for tid, v in quick.items() if tid != row['team_id'] and tid not in (joiners or ())]
        if (quick[row['team_id']] < -tt.PRESCREEN_TOLERANCE
                or any(quick.get(j, 0.0) < -tt.PRESCREEN_TOLERANCE for j in (joiners or ()))
                or min(main) < -9.0 - tt.PRESCREEN_TOLERANCE or sum(main) < -2.0 - tt.PRESCREEN_TOLERANCE):
            continue
        routes.append({'legs': new, 'rules': [], 'picks': picks, 'absorber_id': row['team_id'], 'payer_id': payer_id,
                       'mover_id': row['id'], 'sender_id': row['team_id'], 'returned': None, 'kind': 'piece',
                       'gain': gain, 'short_id': short_id, 'quick': quick, 'absorber_quick': quick[row['team_id']],
                       'score': min(main)})
    return routes


def multi_team_reasons(canonical, route, base_reasons):
    """Plain-language reasons for every team in a multi-team deal built by ``repair_routes``."""
    from . import trade_targets as tt
    ab = lambda tid: tx.team_by_id(canonical, tid)['abbrev']
    mover = tx.player_by_id(canonical, route['mover_id']) or {}
    salary = tx.current_salary(tx.contract_for_player(canonical, route['mover_id'])) or 0.0
    picks = route.get('picks') or []
    rounds = [int(p.get('round') or 2) for p in picks]
    paid = []
    if rounds.count(1):
        paid.append('a first-round pick')
    if rounds.count(2):
        paid.append(f"{rounds.count(2)} second-round pick{'s' if rounds.count(2) > 1 else ''}")
    paid_text = ' and '.join(paid) if paid else 'nothing'
    absorber = route['absorber_id']
    stance = tt.stance_words(canonical, absorber)
    if route['kind'] == 'piece':
        age = tx.maybe_float(mover.get('display_age', mover.get('age'))) or 0
        why = (f"{ab(route['short_id'])} wanted more than {ab(route['payer_id'])} had to offer, so {ab(absorber)} "
               f"({stance}) sent it {mover.get('name')} ({age:.0f}) and {ab(route['payer_id'])} paid {ab(absorber)} "
               f"{paid_text}")
    elif route['kind'] == 'reroute':
        why = (f"{ab(route['short_id'])} did not want {mover.get('name')}'s ${salary / 1e6:.1f}M in the deal, so "
               f"{ab(absorber)} ({stance}) took it with room under the tax, paid {paid_text} by {ab(route['payer_id'])}")
    else:
        from .trade_tax import tax_saved
        flows = _flows(route['legs'])
        inc, out = flows[route['short_id']]
        saved = tax_saved(canonical, route['short_id'], inc, out)['saved']
        cut = f", bringing its luxury-tax saving in the whole deal to about ${saved / 1e6:.1f}M" if saved > 0 else ''
        why = (f"{ab(route['short_id'])} also moved {mover.get('name')} (${salary / 1e6:.1f}M) to close the gap{cut}; "
               f"{ab(absorber)} ({stance}) had room under the tax and took him for {paid_text}")
    text = (base_reasons or {}).get('text') or ''
    text = (text.rstrip('.') + '; ' if text else '') + why + '.'
    role = (f"sold {mover.get('name')} for {paid_text}" if route['kind'] == 'piece'
            else f"absorbed salary for {paid_text}")
    teams = {**((base_reasons or {}).get('teams') or {}), ab(absorber): role}
    key = 'four_team' if len({leg[k] for leg in route['legs'] for k in ('from_team_id', 'to_team_id')}) >= 4 else {
        'reroute': 'three_team_absorber', 'shed': 'three_team_tax_shed', 'piece': 'three_team_piece'}[route['kind']]
    return {**(base_reasons or {}), 'text': text, 'teams': teams, 'target_key': key,
            'base_target_key': (base_reasons or {}).get('target_key'), 'absorber_team_id': absorber,
            'absorbed_player_id': route['mover_id'], 'absorber_payment': [p['id'] for p in picks]}


def multi_team_repairs(canonical, near_misses, *, seed, date, config, depth, diagnostics, reserved, limit):
    """Third (and fourth) teams for the day's near-miss two-team deals. Returns accepted AI-only candidates."""
    found = []
    budget = REPAIR_EVALUATIONS[2 if depth > 1 else 1]
    tried, seen_deals, kept = set(), set(), 0
    for item in near_misses:
        if (len(found) >= limit or kept >= NEAR_MISSES_KEPT[2 if depth > 1 else 1]
                or diagnostics.get('multi_team_evaluations', 0) >= budget):
            break
        candidate, reasons = item['candidate'], item.get('trade_reasons')
        deal = tuple(sorted(tx.proposal_asset_identity_keys(candidate)))
        if deal in seen_deals or set(deal) & reserved:
            continue
        seen_deals.add(deal)
        kept += 1
        frontier = [(candidate, reasons, None)]
        while frontier and len(found) < limit and diagnostics.get('multi_team_evaluations', 0) < budget:
            current, current_reasons, joiners = frontier.pop(0)
            for route in repair_routes(canonical, current, config, joiners=joiners)[:3]:
                if diagnostics.get('multi_team_evaluations', 0) >= budget:
                    break
                keys = tx.proposal_asset_identity_keys({'proposal': {'transfers': [
                    {**leg, 'assets': [{'kind': a['kind'], 'id': a['value']} for a in leg['assets']]} for leg in route['legs']]}})
                signature = tuple(sorted(keys))
                if signature in tried or keys & reserved:
                    continue
                tried.add(signature)
                result = _evaluate(canonical, route['legs'], route['rules'], seed, date, diagnostics)
                if result is None:
                    continue
                joined = set(joiners or ()) | {route['absorber_id']}
                why = multi_team_reasons(canonical, route, current_reasons)
                if bounded_multi_team_accept(canonical, result, joined):
                    accepted = mark_multi_team_accepted(result, joined)
                    accepted['search_route'] = 'multi_team_' + route['kind']
                    accepted['target_source'] = 'multi_team'
                    accepted['trade_reasons'] = why
                    found.append(accepted)
                    diagnostics['multi_team_agreements'] = diagnostics.get('multi_team_agreements', 0) + 1
                    reserved |= keys
                    frontier = []
                    break
                # Still short, but the absorber is happy: a fourth team may fix what remains (at most 4 teams).
                if (len(set(tx.trade_team_ids(result))) < MAX_TEAMS and near_miss(canonical, result)
                        and all(e.get('accepted') for e in result['evaluations'] if e['perspective_team_id'] in joined)):
                    frontier.append((result, why, joined))
    return found


def user_absorber_offers(canonical, near_misses, *, seed, date, config, limit=2, diagnostics=None):
    """Incoming offers for the human team to take salary in a deal two AI teams almost made (user decision
    2026-11-19: offered, never automatic). The AI teams must both accept outright; the human team is paid what an AI
    team in its place would ask, at least one second-round pick."""
    diag = diagnostics if diagnostics is not None else {}
    human = list(canonical.get('_human_team_ids') or [])
    if not human:
        return []
    offers, seen = [], set()
    for item in near_misses:
        if len(offers) >= limit or diag.get('user_absorber_evaluations', 0) >= 8:
            break
        for route in repair_routes(canonical, item['candidate'], config, human_absorber=True)[:2]:
            diag['user_absorber_evaluations'] = diag.get('user_absorber_evaluations', 0) + 1
            if route['mover_id'] in seen:
                continue
            result = _evaluate(canonical, route['legs'], route['rules'], seed, date, diag)
            if result is None or (result.get('legality') or {}).get('status') != 'legal':
                continue
            if tx.multi_team_participation_issues(canonical, result):
                continue
            ai_evals = [e for e in result['evaluations'] if e['perspective_team_id'] not in human]
            if not ai_evals or not all(e.get('accepted') for e in ai_evals):
                continue
            result = json.loads(json.dumps(result))
            result['search_route'] = 'multi_team_user_absorber'
            result['target_source'] = 'multi_team_user_absorber'
            result['trade_reasons'] = multi_team_reasons(canonical, route, item.get('trade_reasons'))
            result['offer_context'] = {'kind': 'absorb_salary_for_picks', 'absorbed_player_id': route['mover_id'],
                                       'payment_pick_ids': [p['id'] for p in route['picks']],
                                       'payer_team_id': route['payer_id']}
            offers.append(result)
            seen.add(route['mover_id'])
            break
    return offers
