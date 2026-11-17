"""Translate point-and-click draft terms into existing engine obligations."""
from copy import deepcopy
import json

from .transactions import (
    canonical_with_pending_pick_terms, clean_pick_protection_summary,
    pick_obligation_validation_errors, protected_pick_fallback_is_distinct,
    resolve_team, trade_result_with_pick_terms, tradeable_picks_for_team,
)
from .utils import stable_id


def pick_rule_lock_reason(pick):
    if pick.get('overall_pick') or pick.get('lottery_slot'):
        return 'The draft position is already known.'
    if pick.get('_obligation_locked') or pick.get('_obligations'):
        return 'Existing draft obligations cannot be overwritten.'
    protection = clean_pick_protection_summary(pick).lower().strip('. ')
    if protection not in {'', 'unprotected', 'unprotected; no additional conditions'}:
        return 'This pick already has conditions.'
    return ''


def compile_pick_rules(canonical, rules, sides, *, _materialize=True):
    """Sides contain owner, recipient (possibly unknown), and selected specs.

    Ownership and collateral are resolved on the server, never from labels or
    rights-holder IDs supplied by the browser. No saved state is changed here.
    """
    if not isinstance(rules, list) or len(rules) > 12:
        raise ValueError('Use at most 12 draft conditions.')
    output = [deepcopy(side['assets']) for side in sides]
    if not rules:
        return canonical, output, []
    picks = {p['id']:p for p in canonical.get('draft_picks', [])}
    selected = {str(a.get('value') or a.get('id')) for side in sides for a in side['assets'] if a.get('kind') == 'pick'}
    reserved, primary_ids, terms = set(selected), set(), []
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError('Draft conditions must be structured selections.')
        primary_id = rule.get('pick_id')
        if primary_id in primary_ids:
            raise ValueError('Use one condition per primary pick.')
        primary_ids.add(primary_id)
        matches = [(index,side) for index,side in enumerate(sides) if any(
            a.get('kind') == 'pick' and (a.get('value') or a.get('id')) == primary_id for a in side['assets'])]
        if len(matches) != 1 or primary_id not in picks:
            raise ValueError('Every draft condition must refer to one selected pick.')
        index, side = matches[0]
        sender = resolve_team(canonical,side['team'])['id']
        receiver = resolve_team(canonical,side['recipient'])['id'] if side.get('recipient') else None
        owned = {p['id'] for p in tradeable_picks_for_team(canonical,sender)}
        primary = picks[primary_id]
        if primary_id not in owned or primary.get('current_owner_team_id') != sender:
            raise ValueError('The offering team no longer owns this pick.')
        reason = pick_rule_lock_reason(primary)
        if reason:
            raise ValueError(reason)
        term = {'primary_pick_id':primary_id,'sender_team_id':sender,'receiver_team_id':receiver,
                'season':primary['season'],'round':int(primary['round'])}
        if rule.get('type') == 'protected_pick':
            low, high = rule.get('from'), rule.get('through')
            if any(isinstance(n,bool) or not isinstance(n,int) for n in (low,high)):
                raise ValueError('Choose a numeric protected range.')
            fallback = rule.get('fallback_pick_ids')
            if not isinstance(fallback,list) or len(fallback) != 1:
                raise ValueError('Select one replacement pick.')
            for identifier in fallback:
                pick = picks.get(identifier)
                if identifier not in owned or not pick or pick.get('current_owner_team_id') != sender:
                    raise ValueError('Replacement picks must belong to the offering team.')
                if identifier in reserved or pick_rule_lock_reason(pick):
                    raise ValueError('A replacement pick is already selected, reserved, or conditional.')
                if not protected_pick_fallback_is_distinct(primary,pick):
                    raise ValueError('A replacement must be a different underlying pick.')
                reserved.add(identifier)
            term.update(type='protected_pick',primary_round=int(primary['round']),protected_range={'from':low,'through':high},
                        fallback_pick_ids=fallback,fallback_rounds=[int(picks[p]['round']) for p in fallback],
                        receiver_pending=receiver is None,label=f'picks {low}-{high} protected')
        elif rule.get('type') == 'pick_swap':
            if not receiver or receiver == sender:
                raise ValueError('Select a specific receiving team before creating a swap.')
            other_id = rule.get('other_pick_id')
            other = picks.get(other_id)
            receiver_owned = {p['id'] for p in tradeable_picks_for_team(canonical,receiver)}
            if not other or other_id not in receiver_owned or other.get('current_owner_team_id') != receiver:
                raise ValueError('The other swap pick must belong to the receiving team.')
            if other_id in reserved or pick_rule_lock_reason(other):
                raise ValueError('The other swap pick is already selected, reserved, or conditional.')
            if not protected_pick_fallback_is_distinct(primary,other):
                raise ValueError('A swap requires two distinct underlying picks.')
            if rule.get('benefit') not in {'better','worse'}:
                raise ValueError('Choose the more or less favorable swap direction.')
            reserved.add(other_id)
            term.update(type='pick_swap',team_a_pick_id=primary_id,team_b_pick_id=other_id,
                        current_rights_holder_team_id=receiver,original_rights_holder_team_id=receiver,
                        counterparty_team_id=sender,benefit=rule['benefit'],pending_asset_grant=True,
                        label='pick swap right' if rule['benefit']=='better' else 'less favorable swap obligation')
        else:
            raise ValueError('Unsupported draft condition.')
        errors = pick_obligation_validation_errors(canonical,None,term)
        if errors:
            raise ValueError('; '.join(errors))
        term['id'] = stable_id('ui_pick_term',json.dumps(term,sort_keys=True))
        if term['type'] == 'pick_swap':
            output[index] = [{'kind':'pick_swap','value':term['id']} if a.get('kind')=='pick' and (a.get('value') or a.get('id'))==primary_id else a for a in output[index]]
        terms.append(term)
    # Internal quote callers need validated terms, not a league entitlement
    # graph. Public callers keep the fully prepared view by default.
    return (canonical_with_pending_pick_terms(canonical,terms) if _materialize else canonical), output, terms


def attach_compiled_rules(candidate, terms, rules, seed):
    from .play import finalize_pick_terms_for_proposal

    combined = {term['id']:term for term in [*(candidate.get('pick_obligation_terms') or []),*terms]}
    finalized = finalize_pick_terms_for_proposal(list(combined.values()),candidate.get('proposal') or {})
    result = trade_result_with_pick_terms(candidate,finalized)
    result['ui_pick_rules'] = deepcopy(rules)
    result['ui_pick_rule_seed'] = seed
    return result


def original_specs_for_rules(candidate, side):
    swaps = {t['id']:t.get('primary_pick_id') or t.get('team_a_pick_id') for t in candidate.get('pick_obligation_terms', [])
             if t.get('pending_asset_grant') and (t.get('primary_pick_id') or t.get('team_a_pick_id'))}
    return [{'kind':'pick','value':swaps[a['id']]} if a.get('kind')=='pick_swap' and a.get('id') in swaps
            else {'kind':a['kind'],'value':a['id']} for a in candidate['proposal'].get(side,[])]


def candidate_pick_rules(canonical,candidate):
    """Retain new AI sweeteners when a finder offer also has authored terms."""
    rules=deepcopy(candidate.get('ui_pick_rules') or [])
    primaries={r['pick_id'] for r in rules}
    existing={t.get('id') for t in canonical.get('pick_obligations',[])}
    for term in candidate.get('pick_obligation_terms',[]):
        primary=term.get('primary_pick_id') or term.get('team_a_pick_id')
        if term.get('id') in existing or primary in primaries:
            continue
        if term.get('type')=='protected_pick':
            protected=term.get('protected_range') or {'from':1,'through':term.get('protected_top_n')}
            rules.append({'pick_id':primary,'type':'protected_pick',**protected,'fallback_pick_ids':term.get('fallback_pick_ids') or []})
        elif term.get('type')=='pick_swap' and term.get('pending_asset_grant'):
            rules.append({'pick_id':primary,'type':'pick_swap','other_pick_id':term.get('team_b_pick_id'),'benefit':term.get('benefit','better')})
        primaries.add(primary)
    return rules
