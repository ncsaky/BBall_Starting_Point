"""Explicit salary protection and save-owned waiver obligations.

Unverified imported money is a disclosed planning reserve, not a declaration
that a real contract is guaranteed. Waivers never overwrite earlier debt.
"""
from copy import deepcopy
from datetime import date, timedelta
from functools import lru_cache
import hashlib
import json
import math

from .utils import normalize_name, stable_id


def guarantee_choice(value=True):
    if type(value) is not bool:
        raise ValueError('Guaranteed salary must be true or false.')
    return value


@lru_cache(maxsize=1)
def research_snapshot():
    from .resource_paths import game_resource_root
    path = game_resource_root()/'data/research/contract_guarantees_2026_10_27.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def initialize_protection(save, canonical):
    if 'contract_protection' in save:
        return
    source = research_snapshot()
    names = {}
    for p in canonical.get('players', []):
        names.setdefault(normalize_name(p.get('name') or ''), []).append(p['id'])
    evidence = {}
    contracts = {c['player_id']: c for c in canonical.get('contracts', [])}
    asof = str(source.get('source', {}).get('retrieved_at') or '')[:10]
    cutoff = f"{int(asof[:4]) if asof and int(asof[5:7]) >= 7 else int(asof[:4])-1}-" if asof else ''
    for row in source.get('contracts', []):
        ids = names.get(row['normalized_name'], [])
        if len(ids) != 1 or ids[0] != row.get('candidate_player_id'):
            continue
        original = contracts.get(ids[0], {})
        signature = {s['season']: s.get('salary') for s in original.get('seasons', []) if s.get('salary') is not None}
        incoming = {s['season']: s['salary'] for s in row['seasons']}
        remaining = {k: v for k, v in signature.items() if k >= cutoff}
        if not remaining or remaining != incoming:
            continue
        evidence[ids[0]] = {'seasons': deepcopy(row['seasons']), 'salary_signature': signature}
    save['contract_protection'] = {'version': 1, 'evidence_as_of': source.get('source', {}).get('retrieved_at', '')[:10],
                                   'source_url': source.get('source', {}).get('url'), 'evidence': evidence}
    save.setdefault('waived_salary_obligations', [])


def apply_imported_protection(canonical, save):
    model = save.get('contract_protection') or {}
    today = str((save.get('state') or {}).get('current_date') or '')
    if not model.get('evidence_as_of') or today < model['evidence_as_of']:
        return
    for contract in canonical.get('contracts', []):
        pid = contract['player_id']
        if pid in (save.get('contract_overrides') or {}):
            continue
        evidence = model.get('evidence', {}).get(pid)
        if not evidence:
            continue
        signature = {s['season']: s.get('salary') for s in contract.get('seasons', []) if s.get('salary') is not None}
        if signature != evidence['salary_signature']:
            continue
        by_year = {s['season']: s for s in evidence['seasons']}
        for season in contract.get('seasons', []):
            proof = by_year.get(season['season'], {})
            if proof.get('guaranteed_salary') is not None and not season.get('option_type'):
                season['guaranteed_salary'] = proof['guaranteed_salary']
                season['protection_basis'] = proof['protection_evidence']


def negotiated_seasons(offer, seasons):
    if 'guaranteed' not in offer:
        return seasons  # Legacy agreements did not record consent to this term.
    guaranteed = guarantee_choice(offer.get('guaranteed', True))
    for row in seasons:
        row['guaranteed_salary'] = row['salary'] if guaranteed else 0
        row['protection_basis'] = 'negotiated'
        if not guaranteed:
            row['guarantee_date'] = f"{int(row['season'][:4])+1}-01-10"
    return seasons


def security_penalty(player, guaranteed):
    if guaranteed:
        return 0.0
    minutes = max(0, float(player.get('minutes_projection') or 0))
    # Strong players have bargaining power; uncertain fringe roles carry
    # greater cut risk. Both prefer protection, for different reasons.
    return round(8 + min(12, minutes*.4) + max(0, 16-minutes)*.3, 2)


def season_window(save, season):
    memo = save.get('_forecast_season_windows')
    if memo is not None:
        cached = memo.get(season)
        if cached is not None:
            return cached
    result = _uncached_season_window(save, season)
    if memo is not None:
        memo[season] = result
    return result


# First/last regular-season date per schedule list (the same list object, unchanged length). Game dates are
# never edited in place; a rebuilt schedule is a new list. Waiver costs ask for this thousands of times a day.
_WINDOW_CACHE: dict[int, tuple] = {}


def _uncached_season_window(save, season):
    games = ((save.get('season_schedules') or {}).get(season) or {}).get('games', [])
    hit = _WINDOW_CACHE.get(id(games))
    if hit is not None and hit[0] is games and hit[1] == len(games):
        return hit[2]
    dates = [g.get('gameDate') or g.get('date') for g in games if g.get('phase') == 'regular' and (g.get('gameDate') or g.get('date'))]
    result = (date.fromisoformat(min(dates)[:10]), date.fromisoformat(max(dates)[:10])) if dates else (None, None)
    if len(_WINDOW_CACHE) >= 16:
        _WINDOW_CACHE.clear()
    _WINDOW_CACHE[id(games)] = (games, len(games), result)
    return result


def waiver_projection(canonical, save, player, team_id, stamp=None):
    from .schema import CANONICAL_START_DATE
    stamp = stamp or save.get('state', {}).get('current_date') or canonical.get('meta', {}).get('current_date') or CANONICAL_START_DATE
    today = date.fromisoformat(stamp)
    clearance = today + timedelta(days=2)
    current_start = today.year if today.month >= 7 else today.year-1
    contract = next((c for c in canonical.get('contracts', []) if c['player_id'] == player['id']), {})
    rows = []
    unquantified = not contract
    health = next((h for h in save.get('health_states', []) if h.get('player_id') == player['id']), {})
    injury_review = health.get('availability_status') == 'out' and (not health.get('return_date') or str(health['return_date']) > stamp)
    for row in contract.get('seasons', []):
        label, salary = str(row.get('season') or ''), row.get('salary')
        if len(label) != 7 or not label[:4].isdigit() or int(label[:4]) < current_start:
            continue
        if row.get('option_type') == 'qualifying_offer':
            continue  # An unaccepted tender is not an executed salary obligation.
        if salary is None:
            unquantified = True
            rows.append({'season': label, 'salary': None, 'protected_salary': None, 'earned_salary': 0, 'unverified_reserve': None})
            continue
        salary = float(salary)
        if not math.isfinite(salary) or salary < 0:
            raise ValueError('Invalid contract salary')
        protected = row.get('guaranteed_salary')
        if protected is None and row.get('guarantee_status') in {'guaranteed', 'fully_guaranteed'}:
            protected = salary
        if protected is None and row.get('guarantee_status') in {'non_guaranteed', 'not_guaranteed'}:
            protected = 0
        if row.get('option_type') == 'team_option' and int(label[:4]) > current_start and not row.get('option_exercised'):
            protected = 0
        guarantee_date = row.get('guarantee_date')
        if guarantee_date and clearance >= date.fromisoformat(guarantee_date):
            protected = salary
        if injury_review and int(label[:4]) == current_start and protected != salary:
            # Lack-of-skill protection is not proof that injury continuation is
            # waived. Do not create free cap room by cutting an injured player.
            protected = None
        earned = 0.0
        clearance_earned = 0.0
        first, last = season_window(save, label)
        if first and clearance >= first:
            clearance_earned = salary*min(1, ((min(clearance, last)-first).days+1)/((last-first).days+1))
        if first and today >= first:
            earned = salary*min(1, ((min(today, last)-first).days+1)/((last-first).days+1))
        elif not first and int(label[:4]) == current_start and today >= date(current_start, 10, 1) and protected != salary:
            # Missing schedule cannot justify deleting already-earned money.
            protected = None
        if protected is not None:
            if not math.isfinite(float(protected)):
                raise ValueError('Invalid protected salary')
            protected = min(salary, max(0.0, float(protected)))
        charge = salary if protected is None else max(protected, earned, clearance_earned)
        rows.append({'season': label, 'salary': round(charge, 2),
                     'protected_salary': protected, 'earned_salary': round(earned, 2),
                     'waiver_clearance_salary': round(max(0, clearance_earned-earned), 2),
                     'injury_protection_requires_review': bool(injury_review and protected is None),
                     'unverified_reserve': round(charge, 2) if protected is None else 0.0})
    if not contract:
        rows.append({'season': f'{current_start}-{str(current_start+1)[-2:]}', 'salary': None,
                     'protected_salary': None, 'earned_salary': 0, 'unverified_reserve': None})
    return {'player_id': player['id'], 'player_name': player.get('name'), 'team_id': team_id,
            'date': stamp, 'clearance_date': clearance.isoformat(), 'seasons': rows, 'unverified': unquantified or any(r['unverified_reserve'] for r in rows),
            'unquantified': unquantified,
            'remaining_cost_millions': round(sum(max(0, (r['salary'] or 0)-r['earned_salary']) for r in rows)/1_000_000, 4)}


def record_waiver(canonical, save, player, team_id, stamp):
    initialize_protection(save, canonical)
    projection = waiver_projection(canonical, save, player, team_id, stamp)
    contract = next((c for c in canonical.get('contracts', []) if c['player_id'] == player['id']), {})
    signature = hashlib.sha256(json.dumps([contract.get('agreement_id'), contract.get('seasons', [])], sort_keys=True).encode()).hexdigest()[:16]
    key = stable_id('waived_salary', team_id, player['id'], stamp, signature)
    ledger = save.setdefault('waived_salary_obligations', [])
    existing = next((r for r in ledger if r['id'] == key), None)
    if existing:
        return existing
    entry = {**projection, 'id': key, 'contract_id': contract.get('id'),
             'relief_status': 'no_claim_buyout_setoff_or_stretch_applied'}
    ledger.append(entry)
    return entry


def waived_total(context, team_id, season):
    return sum(float(s.get('salary') or 0) for r in context.get('waived_salary_obligations', [])
               if r['team_id'] == team_id for s in r['seasons'] if s['season'] == season)


def roster_signing_plan(canonical, save, player, team_id, annual_millions, years):
    """A cheap healthy-rotation counterfactual, not a future-season simulation."""
    from .save import ai_role_targets, ai_roster_retention_score, offer_to_contract_seasons
    # Day resolution shares a prepared skills view. Earlier accepted deals must
    # still change this counterfactual before the next agreement is applied.
    owners = save.get('roster_overrides') or {}
    effective = [dict(p, team_id=owners.get(p['id'], p.get('team_id'))) for p in canonical.get('players', [])]
    contracts = {c['player_id']: c for c in canonical.get('contracts', [])}
    for pid, override in (save.get('contract_overrides') or {}).items():
        if override:
            contracts[pid] = {**contracts.get(pid, {}), 'player_id': pid,
                              'seasons': override.get('seasons') or offer_to_contract_seasons(override)}
    roster = [dict(p, minutes_projection=24) for p in effective
              if p.get('team_id') == team_id and p['id'] != player['id'] and not p.get('_inactive_player')]
    pending = {o['player_id'] for o in save.get('free_agent_offers', [])
               if o.get('team_id') == team_id and o.get('status') == 'active' and o['player_id'] != player['id']}
    existing = {p['id'] for p in roster}
    roster += [dict(p, team_id=team_id, minutes_projection=24) for p in effective if p['id'] in pending-existing]
    newcomer = dict(player, team_id=team_id, minutes_projection=24)
    trial = {k: v for k, v in canonical.items() if not str(k).startswith('_')}
    trial['players'] = roster+[newcomer]
    trial['contracts'] = list(contracts.values())
    trial['_allow_internal_caches'] = True
    # The trial shares the league's trait rows (the same list), so it shares their value index too, as roster
    # forecast views do. Rebuilding it per counterfactual scanned every trait in the league each time.
    from .save import trait_values_by_player
    trial['_trait_values_by_player'] = trait_values_by_player(canonical)
    targets, _ = ai_role_targets(trial, trial['players'], {})
    for p in trial['players']:
        p['minutes_projection'] = targets.get(p['id'], 0)
    # Nothing below changes the trial, the save or a player, so each player's score is computed once
    # (the two rankings and the gain used to score the same players again).
    scores = {}

    def value(p):
        key = id(p)
        if key not in scores:
            scores[key] = (p, ai_roster_retention_score(trial, save, p))
        return scores[key][1]
    ranked = sorted(trial['players'], key=lambda p: (-value(p), p['id']))
    cut = ranked[15:]
    if any(p['id'] == player['id'] for p in cut):
        return {'ok': False, 'reason': 'signing_not_expected_to_survive_cutdown', 'cuts': []}
    if any(p['id'] in pending-existing for p in cut):
        return {'ok': False, 'reason': 'existing_bid_would_lose_final_roster_place', 'cuts': []}
    baseline_cut = {p['id'] for p in sorted(roster, key=lambda p: (-value(p), p['id']))[15:]}
    cuts = [waiver_projection(trial, save, p, team_id) for p in cut
            if p['id'] in existing and p['id'] not in baseline_cut]
    costs = sum(p['remaining_cost_millions'] for p in cuts)
    if any(p['unquantified'] for p in cuts):
        return {'ok': False, 'reason': 'replacement_obligation_requires_salary_review', 'cuts': cuts}
    displaced = next((p for p in cut if p['id'] not in baseline_cut), None)
    gain = value(newcomer)-value(displaced) if displaced else value(newcomer)
    rotation_minutes = targets.get(player['id'], 0)
    strategy = next((s for s in canonical.get('team_strategic_states', []) if s.get('team_id') == team_id), {})
    phase = str(strategy.get('phase') or '')
    # Contenders can spend for a useful upgrade; rebuilders value flexibility.
    cost_weight = .16 if 'contending' in phase else .28 if 'rebuilding' in phase else .22
    threshold = costs*cost_weight
    if cuts and gain < threshold:
        return {'ok': False, 'reason': 'waiver_cost_exceeds_marginal_upgrade', 'cuts': cuts,
                'waiver_cost_millions': round(costs, 3), 'upgrade': round(gain, 3)}
    # Paid zero-minute duplication is not insurance at any price.
    age = float(player.get('display_age', player.get('age')) or 27)
    development_role = age < 25 and float(player.get('potential') or 0)-float(player.get('current_ability') or 0) >= 5
    if rotation_minutes < 4 and not development_role and annual_millions*years > 4 and len(roster) >= 15:
        return {'ok': False, 'reason': 'paid_depth_without_rotation_or_development_role', 'cuts': cuts}
    return {'ok': True, 'reason': 'rotation_or_depth_upgrade', 'cuts': cuts,
            'waiver_cost_millions': round(costs, 3), 'upgrade': round(gain, 3),
            'surplus_player_ids': [p['id'] for p in roster if p['id'] in existing and targets.get(p['id'], 0) < 8],
            'projected_minutes': round(rotation_minutes, 2)}
