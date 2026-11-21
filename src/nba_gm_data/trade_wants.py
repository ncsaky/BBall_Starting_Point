"""Published return preferences; strategy and trade safety remain authoritative."""
from copy import deepcopy
from datetime import date
import hashlib
import json
import math

VERSION = 1
KINDS = {'player', 'picks', 'upgrade'}
FIELDS = {
    'age': (16, 50), 'height_inches': (60, 100), 'overall': (0, 100),
    'offense': (0, 100), 'defense': (0, 100), 'upside_remaining': (0, 5),
    'health_risk': (0, 100), 'salary_millions': (0, 150), 'contract_years': (0, 7),
    **{key: (0, 100) for key in ('shooting', 'creation', 'spacing', 'passing',
        'rebounding', 'rim_deterrence', 'athleticism', 'release', 'range', 'handle',
        'rim_pressure', 'def_effort', 'screen_nav', 'lateral_agility', 'stamina', 'iq')},
}
OPS = {'>=', '>', '<=', '<', '='}
POSITIONS = {'PG', 'SG', 'SF', 'PF', 'C'}


def normalize_wants(rows, roster_ids):
    if not isinstance(rows, list) or len(rows) > 6:
        raise ValueError('Choose up to six wants.')
    result = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not isinstance(raw.get('kind'), str) or raw['kind'] not in KINDS:
            raise ValueError('Choose a player profile, draft capital or roster upgrade.')
        kind = raw['kind']
        row = {'id': str(raw.get('id') or f'want_{i+1}')[:80], 'kind': kind}
        if not row['id'] or any(r['id'] == row['id'] for r in result):
            raise ValueError('Want IDs must be different.')
        if kind == 'picks':
            try:
                numbers = [raw.get('round', 1), raw.get('from', 1), raw.get('through', 3)]
                if any(isinstance(n, bool) or not math.isfinite(float(n)) or float(n) != int(n) for n in numbers):
                    raise ValueError('Draft years and rounds must be integers.')
                rnd, first, last = int(raw.get('round', 1)), int(raw.get('from', 1)), int(raw.get('through', 3))
            except (TypeError, ValueError):
                raise ValueError('Choose valid draft rounds and years.') from None
            protection, quality = raw.get('protection', 'any'), raw.get('quality', 'any')
            if rnd not in {1, 2} or not 1 <= first <= last <= 7 or not isinstance(protection, str) or not isinstance(quality, str) or protection not in {'any', 'light', 'unprotected'} or quality not in {'any', 'premium'}:
                raise ValueError('Invalid pick preference.')
            row.update(round=rnd, **{'from': first, 'through': last}, protection=protection, quality=quality)
        else:
            positions = raw.get('positions', [])
            conditions = raw.get('conditions', [])
            if not isinstance(positions, list) or any(not isinstance(p, str) for p in positions) or not set(positions) <= POSITIONS or len(set(positions)) != len(positions):
                raise ValueError('Choose valid positions.')
            if not isinstance(conditions, list) or len(conditions) > 8:
                raise ValueError('Choose up to eight attribute conditions per profile.')
            row.update(positions=positions, conditions=[])
            for condition in conditions:
                if not isinstance(condition, dict) or not isinstance(condition.get('field'), str) or not isinstance(condition.get('op'), str) or condition['field'] not in FIELDS or condition['op'] not in OPS:
                    raise ValueError('Invalid player condition.')
                try:
                    value = float(condition.get('value'))
                except (TypeError, ValueError):
                    raise ValueError('Attribute conditions need a number.') from None
                lo, hi = FIELDS[condition['field']]
                if isinstance(condition.get('value'), bool) or not math.isfinite(value) or not lo <= value <= hi:
                    raise ValueError(f"{condition['field']} must be between {lo} and {hi}.")
                row['conditions'].append({'field': condition['field'], 'op': condition['op'], 'value': value})
            if kind == 'upgrade':
                pid = raw.get('target_player_id')
                # Existing stale targets are allowed by the action, but cannot be newly forged.
                if not isinstance(pid, str) or pid not in roster_ids:
                    raise ValueError('Choose an upgrade target on your roster.')
                row['target_player_id'] = pid
        result.append(row)
    return result


def wants_for_team(canonical, team_id):
    record = (canonical.get('team_trade_wants') or {}).get(team_id)
    if record is not None:
        return record.get('entries', [])
    if team_id in canonical.get('_human_team_ids', []):
        return []
    cache = canonical.setdefault('_wants_generated', {}) if canonical.get('_allow_internal_caches') else {}
    if team_id not in cache:
        cache[team_id] = suggested_wants(canonical, team_id)
    return cache[team_id]


def player_facts(canonical, player):
    from .save import player_engine_attribute_summary
    from .transactions import current_salary, player_asset_values_by_id
    pid = player['id']
    cache = canonical.setdefault('_wants_player_facts', {}) if canonical.get('_allow_internal_caches') else {}
    if pid in cache:
        return cache[pid]
    # The AI's own scale: every want threshold (AI-written and user-entered) is stored and matched on it. The app
    # converts OVR/OFF/DEF thresholds to and from the display scale at the screen (OVERALL-SCALE, 2026-11-21).
    attrs = player_engine_attribute_summary(canonical, pid)
    value = player_asset_values_by_id(canonical).get(pid, {})
    contract = next((c for c in canonical.get('contracts', []) if c.get('player_id') == pid), {})
    salary = current_salary(contract)
    active_season = str(canonical.get('meta', {}).get('active_season') or '2026-27')
    seasons = [s for s in contract.get('seasons', []) if float(s.get('salary') or 0) > 0 and str(s.get('season') or '') >= active_season]
    facts = {**attrs, 'age': player.get('display_age', player.get('age')),
             'height_inches': player.get('height_inches'),
             'upside_remaining': max(0, min(5, float(value['development_upside'])/22*5)) if value.get('development_upside') is not None else None,
             'health_risk': value.get('health_risk'),
             'salary_millions': salary/1e6 if salary is not None else None,
             'contract_years': len(seasons) if seasons else None}
    cache[pid] = facts
    return facts


def condition_distance(actual, op, target, field):
    if actual is None or not isinstance(actual, (int, float)) or not math.isfinite(actual):
        return None
    ok = {'>=': actual >= target, '>': actual > target, '<=': actual <= target,
          '<': actual < target, '=': actual == target}[op]
    if ok:
        return 0.
    tolerance = {'age': 1, 'height_inches': 1, 'upside_remaining': .3,
                 'salary_millions': 2, 'contract_years': 1}.get(field, 3)
    return max(.01, abs(actual-target)/tolerance)


def next_draft_year(canonical):
    today = date.fromisoformat(str((canonical.get('meta') or {}).get('current_date') or '2026-10-01')[:10])
    return today.year + (today.month > 6)


def match_want(canonical, team_id, want, asset, *, acquired=False):
    from . import transactions as tx
    from .save import player_position_tokens
    base = {'want_id': want['id'], 'status': 'none', 'score': 0., 'reasons': []}
    if want['kind'] == 'picks':
        if asset.get('kind') != 'pick':
            return base  # A swap is not ownership of an unencumbered pick.
        pick = tx.pick_by_id(canonical, asset['id'])
        if not pick:
            return base
        from .pick_presentation import pick_presentation
        terms = pick_presentation(canonical, pick) or {}
        year = int(str(pick.get('season') or 0)[:4])
        first = next_draft_year(canonical)
        if int(pick.get('round') or 0) != want['round'] or not first+want['from']-1 <= year <= first+want['through']-1:
            return base
        protection = str(pick.get('protection_summary') or pick.get('protections') or '').strip().lower().rstrip('. ')
        obligations = [r for r in canonical.get('pick_obligations', [])
                       if r.get('status') not in {'resolved', 'expired', 'cancelled'}
                       and pick['id'] in {r.get('primary_pick_id'), r.get('fallback_pick_id')}]
        protected = bool(obligations or terms or pick.get('_obligation_locked') or
                         (protection and protection not in {'none', 'unprotected', 'unprotected; no additional conditions'}))
        if want.get('protection') == 'unprotected' and protected:
            return {**base, 'reasons': ['Pick is protected or conditional.']}
        if want.get('protection') == 'light' and protected:
            from .pick_rules import protection_bounds
            # Do not infer lightly protected from ambiguous imported prose.
            try:
                light = bool(obligations) and not terms and all(protection_bounds(r)[1] <= 4 for r in obligations)
            except ValueError:
                light = False
            if not light:
                return base
        quality = tx.pick_asset_value(pick, 'neutral')
        if want.get('quality') == 'premium' and quality < (75 if want['round'] == 1 else 20):
            return base
        return {**base, 'status': 'exact', 'score': 1., 'reasons': ['Matches draft year, round and rights requirements.']}
    if asset.get('kind') != 'player':
        return base
    player = tx.player_by_id(canonical, asset['id'])
    if not player or player.get('_inactive_player'):
        return base
    if want.get('positions') and not set(player_position_tokens(player)) & set(want['positions']):
        return base
    facts = player_facts(canonical, player)
    distances = []
    reasons = []
    for c in want.get('conditions', []):
        distance = condition_distance(facts.get(c['field']), c['op'], c['value'], c['field'])
        if distance is None:
            return {**base, 'reasons': [f"{c['field']} unavailable."]}
        distances.append(distance)
        if distance:
            reasons.append(f"{c['field']} {facts[c['field']]:g}; requested {c['op']} {c['value']:g}")
    if want['kind'] == 'upgrade':
        target = tx.player_by_id(canonical, want.get('target_player_id'))
        stale = not target or target.get('team_id') != team_id
        snapshot = want.get('target_snapshot') if acquired and stale else None
        if (stale and not snapshot) or (target and target['id'] == player['id']):
            return {**base, 'reasons': ['Upgrade target is no longer on this roster.']}
        positions = snapshot['positions'] if snapshot else player_position_tokens(target)
        if not set(positions) & set(player_position_tokens(player)):
            return base
        target_facts = snapshot['facts'] if snapshot else player_facts(canonical, target)
        if facts.get('overall') is None or target_facts.get('overall') is None or facts['overall'] < target_facts['overall']+1:
            return base
        reasons.append('Candidate role upgrade; complete roster impact still required.')
    if any(d > 1 for d in distances) or sum(d > 0 for d in distances) > 1:
        return base
    near = any(distances)
    return {**base, 'status': 'near' if near else 'exact', 'score': .5 if near else 1.,
            'reasons': reasons or ['Matches all requested conditions.']}


def _entries_json(canonical, entries):
    """json.dumps(entries, sort_keys=True), kept per wants list inside one trade search (whose league,
    including every team's wants, is never edited while the search runs)."""
    memo = canonical.get('_trade_search_exact_memo')
    if memo is None:
        return json.dumps(entries, sort_keys=True)
    table = memo.setdefault('wants_json', {})
    cached = table.get(id(entries))
    if cached is not None and cached[0] is entries:
        return cached[1]
    text = json.dumps(entries, sort_keys=True)
    if len(table) >= 256:
        table.clear()
    table[id(entries)] = (entries, text)  # the entry keeps the list alive, so its id stays unique
    return text


def asset_matches(canonical, team_id, asset):
    entries = wants_for_team(canonical, team_id)
    if not entries:
        return []
    cache = canonical.setdefault('_trade_wants_match_cache', {}) if canonical.get('_allow_internal_caches') else {}
    signature = (team_id, asset.get('kind'), asset.get('id'), _entries_json(canonical, entries),
                 (canonical.get('meta') or {}).get('current_date'))
    if signature not in cache:
        result = []
        for priority, want in enumerate(entries):
            match = match_want(canonical, team_id, want, asset)
            if match['score']:
                result.append({**match, 'priority': priority, 'score': match['score']*(1-priority*.06)})
        if len(cache) >= 2048:
            cache.clear()
        cache[signature] = result
    return cache[signature]


def search_priority(canonical, team_id, asset):
    return max((m['score'] for m in asset_matches(canonical, team_id, asset)), default=0.)*4


def package_preference(canonical, team_id, incoming, outgoing=(), config=None):
    """One capped buyer surplus, not a bonus on every appearance of a profile."""
    from . import transactions as tx
    decision = (config or tx.default_transaction_model_config()).get('decision', {})
    state = next((s for s in canonical.get('team_strategic_states', []) if s['team_id'] == team_id), {})
    values = tx.player_asset_values_by_id(canonical)
    total, details, seen = 0., [], set()
    for asset in incoming:
        key = (asset.get('kind'), asset.get('id'))
        if key in seen:
            continue
        seen.add(key)
        matches = asset_matches(canonical, team_id, asset)
        if not matches:
            continue
        match = max(matches, key=lambda m: m['score'])
        overlap = 0.
        if asset['kind'] == 'player':
            player = tx.player_by_id(canonical, asset['id'])
            value = tx.valuation_or_fallback(values, asset['id'], player)
            neutral = tx.market_trade_target_value(player, value)
            overlap = max(0., tx.team_fit_for_player(player, value, state, canonical, include_spatial=False)) if state else 0.
            if state.get('phase') in {'contending', 'contending_with_future_upside'} and float(value.get('playoff_value') or 0) >= 64:
                overlap += float(decision.get('contender_need_bonus', 5.5))
            if any(w.get('id') == match['want_id'] and w.get('kind') == 'upgrade'
                   for w in wants_for_team(canonical, team_id)):
                from .trade_roster import roster_projection
                out = {a['id'] for a in outgoing if a.get('kind') == 'player'}
                after = roster_projection(canonical, team_id, out, {a['id'] for a in incoming if a.get('kind') == 'player'})
                before = roster_projection(canonical, team_id)
                if after['strength'] <= before['strength'] or after['rotation'].get(player['id'], 0) < 18:
                    continue
        elif asset['kind'] == 'pick':
            neutral = tx.pick_asset_value(tx.pick_by_id(canonical, asset['id']), 'neutral')
            overlap = max(0., tx.pick_asset_value(tx.pick_by_id(canonical, asset['id']), state.get('phase', 'neutral'))-neutral)
            if state.get('phase') in {'rebuilding', 'developing'}:
                overlap += tx.rebuilder_draft_bonus(canonical, asset, state.get('phase', 'neutral'), {'decision': decision})
        else:
            continue
        credit = max(0., max(0., neutral)*.05*match['score']-overlap)
        total += credit
        details.append({**match, 'asset_id': asset['id'], 'credit': round(credit, 4)})
    return {'adjustment': round(min(4., total), 4), 'matches': details}


def suggested_wants(canonical, team_id):
    from .save import player_position_tokens
    from .transactions import player_asset_values_by_id
    state = next((s for s in canonical.get('team_strategic_states', []) if s['team_id'] == team_id), {})
    plan = (canonical.get('team_plans') or {}).get(team_id, {})
    phase = plan.get('window_phase') or state.get('window_phase') or 'rebuilding'
    roster = [p for p in canonical.get('players', []) if p.get('team_id') == team_id and not p.get('_inactive_player')]
    if not roster:
        return []
    values = player_asset_values_by_id(canonical)
    output = []
    if phase in {'rebuilding', 'exiting'}:
        output.append({'id': 'ai_draft', 'kind': 'picks', 'round': 1, 'from': 1, 'through': 4,
                       'quality': 'premium' if state.get('pick_inventory', {}).get('first_round_count', 0) < 3 else 'any',
                       'protection': 'any', 'reason': 'Add future foundations.' if phase == 'rebuilding' else 'Preserve a route to retool the core.'})
    core = set(plan.get('core_ids') or state.get('core_candidates') or [])
    anchors = [p for p in roster if p['id'] in core]
    occupied = {pos for p in anchors for pos in player_position_tokens(p)}
    open_positions = [pos for pos in ('PG', 'SF', 'C', 'SG', 'PF') if pos not in occupied]
    if phase in {'rebuilding', 'entering', 'exiting'}:
        output.append({'id': 'ai_youth', 'kind': 'player', 'positions': open_positions[:2],
            'conditions': [{'field': 'age', 'op': '<=', 'value': 24},
                           # Old displayed 72/76 corresponded to engine 52/56.
                           {'field': 'overall', 'op': '>=', 'value': 52 if phase == 'rebuilding' else 56},
                           {'field': 'upside_remaining', 'op': '>=', 'value': 1}],
            'reason': 'Develop a complementary young piece around the core.'})
    needs = state.get('needs') or []
    skill = next((key for label, key in [('shooting', 'range'), ('passing', 'passing'),
             ('point_of_attack_defense', 'defense'), ('rim_protection', 'rim_deterrence'),
             ('rebounding', 'rebounding'), ('primary_creation', 'creation')] if label in needs), None)
    if phase != 'rebuilding' and skill:
        output.append({'id': f'ai_skill_{skill}', 'kind': 'player', 'positions': [],
            # DEF was already direct; other old displayed 78s meant grade58.
            'conditions': [{'field': skill, 'op': '>=', 'value': 78 if skill == 'defense' else 58},
                           {'field': 'overall', 'op': '>=', 'value': 55}],
            'reason': f'Improve {skill.replace("_", " ")} without dismantling the core.'})
    if phase == 'peak' and len(output) < 3:
        candidates = [p for p in roster if p['id'] not in core]
        candidates.sort(key=lambda p: (-float(p.get('minutes_projection') or 0), p['id']))
        if candidates:
            output.append({'id': 'ai_upgrade', 'kind': 'upgrade', 'target_player_id': candidates[0]['id'],
                'positions': [], 'conditions': [], 'reason': 'Upgrade a complementary rotation role.'})
    injuries = {h.get('player_id') for h in canonical.get('player_health_states', []) if h.get('availability_status') == 'out'}
    hurt = [p for p in roster if p['id'] in injuries and float(p.get('_trade_value_minutes_projection', p.get('minutes_projection')) or 0) >= 20]
    if hurt:
        output.insert(0, {'id': 'ai_injury', 'kind': 'player', 'positions': player_position_tokens(hurt[0]),
            'conditions': [{'field': 'overall', 'op': '>=', 'value': 53}, {'field': 'health_risk', 'op': '<=', 'value': 15}],
            'reason': 'Cover an unavailable rotation player.'})
    # Affordability is relative to assets the club might actually trade, not its best committed star.
    budget = max((float(values.get(p['id'], {}).get('player_value') or 0) for p in roster if p['id'] not in core), default=25)
    for row in output:
        if row['kind'] == 'player' and budget < 35:
            row['conditions'] = [c for c in row['conditions'] if c['field'] != 'overall'] + [{'field': 'overall', 'op': '>=', 'value': 50}]
    return output[:3]


def refresh_ai_wants(canonical, saved, stamp):
    from .save import human_controlled_team_ids
    human = human_controlled_team_ids(saved)
    records = saved.setdefault('team_trade_wants', {})
    for team in canonical.get('teams', []):
        tid = team['id']
        if tid in human:
            continue
        rows = suggested_wants(canonical, tid)
        previous = records.get(tid, {})
        # Stable IDs preserve the priority of needs that survive this review.
        old_order = {w['id']: n for n, w in enumerate(previous.get('entries', []))}
        rows.sort(key=lambda w: old_order.get(w['id'], 99))
        records[tid] = {'version': VERSION, 'revision': previous.get('revision', 0)+(rows != previous.get('entries')),
                        'entries': rows, 'reviewed_on': stamp}
    canonical['team_trade_wants'] = deepcopy(records)
    clear_wants_cache(canonical)


def clear_wants_cache(canonical):
    for key in ('_trade_wants_match_cache', '_wants_player_facts', '_wants_generated'):
        canonical.pop(key, None)


def owned_assets(canonical, team_id):
    return ([{'kind': 'player', 'id': p['id']} for p in canonical.get('players', [])
             if p.get('team_id') == team_id and not p.get('_inactive_player')]
            + [{'kind': 'pick', 'id': p['id']} for p in canonical.get('draft_picks', [])
               if p.get('current_owner_team_id') == team_id and p.get('status') not in {'used_draft_pick', 'expired_draft_pick'}])


def ownership_keys(canonical, team_id):
    return sorted(f"{a['kind']}:{a['id']}" for a in owned_assets(canonical, team_id))


def wants_payload(canonical, saved, team_id):
    from . import transactions as tx
    record = (saved.get('team_trade_wants') or {}).get(team_id, {})
    players = {p['id']: p for p in canonical.get('players', [])}
    entries = []
    for want in wants_for_team(canonical, team_id):
        target = players.get(want.get('target_player_id'), {})
        active = want['kind'] != 'upgrade' or target.get('team_id') == team_id
        entries.append({**deepcopy(want), 'active': active, 'target_name': target.get('name'),
                        'draft_years': list(range(next_draft_year(canonical)+want.get('from', 1)-1,
                                                   next_draft_year(canonical)+want.get('through', 3))) if want['kind'] == 'picks' else []})
    reminder = []
    seen = set(record.get('reminder_seen', []))
    if team_id in canonical.get('_human_team_ids', []) and record.get('entries'):
        reminder_ids = set()
        for asset in owned_assets(canonical, team_id):
            key = f"{asset['kind']}:{asset['id']}"
            if key in seen or key in reminder_ids:
                continue
            reminder_ids.add(key)
            if asset['kind'] == 'pick' and (tx.pick_by_id(canonical, asset['id']) or {}).get('_obligation_locked'):
                continue
            matches = [match_want(canonical, team_id, want, asset, acquired=True)
                       for want in record['entries']]
            matches = [m for m in matches if m['score']]
            if matches:
                obj = players.get(asset['id'], {}) if asset['kind'] == 'player' else tx.pick_by_id(canonical, asset['id']) or {}
                label = obj.get('name') or f"{obj.get('season')} R{obj.get('round')} pick"
                reminder.append({'asset': asset, 'name': label, 'matches': matches})
    token = hashlib.sha256(json.dumps([record.get('revision', 0), reminder], sort_keys=True).encode()).hexdigest()[:20]
    return {'version': VERSION, 'team_id': team_id, 'revision': record.get('revision', 0),
            'entries': entries, 'suggestions': suggested_wants(canonical, team_id),
            'reminder': reminder, 'reminder_token': token, 'fields': list(FIELDS),
            'roster': [{'id': p['id'], 'name': p.get('name'), 'position': p.get('position')} for p in players.values() if p.get('team_id') == team_id]}
