# Frozen task-2 generator: exact-result oracle for package construction.
def buyer_offer_packages_for_value(canonical: dict[str, Any], buyer: dict[str, Any], seller: dict[str, Any], target_value: float, target_salary: float | None, seed: int, excluded_player_ids: set[str] | None=None, max_results: int=18, max_player_options: int=9, return_options: bool=False, allow_new_pick_swaps: bool=False) -> list[list[dict[str, Any]]] | list[dict[str, Any]]:
    as_of_date = (canonical.get('meta') or {}).get('current_date') or CANONICAL_START_DATE
    excluded_player_ids = set(excluded_player_ids or set()) | recently_traded_player_ids(canonical, as_of_date)
    valuations = player_asset_values_by_id(canonical)
    buyer_players = [player for player in canonical['players'] if player['team_id'] == buyer['id']]
    salary_by_player = {player['id']: current_salary(contract_for_player(canonical, player['id'])) or 0.0 for player in buyer_players}
    block = {entry['player_id']: entry for entry in canonical['trade_block_entries'] if entry['team_id'] == buyer['id']}
    from .trade_wants import search_priority
    candidates = sorted([player for player in buyer_players if player['id'] not in excluded_player_ids], key=lambda player: (block.get(player['id'], {}).get('block_score', 0) + 8 * search_priority(canonical, seller['id'], {'kind': 'player', 'id': player['id']}), -abs(valuations.get(player['id'], fallback_asset_valuation(player))['player_value'] - target_value * 0.72), -abs(salary_by_player.get(player['id'], 0.0) - (target_salary or 0)) / 1000000, player['name']), reverse=True)
    tradable_players = []
    buyer_state = next((item for item in canonical.get('team_strategic_states', []) if item.get('team_id') == buyer['id']), {})
    for player in candidates:
        valuation = valuations.get(player['id'], fallback_asset_valuation(player))
        value = float(valuation['player_value'])
        block_score = float(block.get(player['id'], {}).get('block_score') or 0.0)
        if value >= 72 and target_value < 70:
            continue
        if value >= 58 and block_score < 55 and (target_value < 68):
            continue
        if value >= 62 and block_score < 62 and (team_fit_for_player(player, valuation, buyer_state, canonical) >= 7.0) and (target_value < value + 12.0):
            continue
        if value > target_value * (1.08 if target_value >= 70 else 1.24):
            continue
        tradable_players.append(player)
    tradable_players = tradable_players[:max(3, int(max_player_options))]
    picks = sorted(tradeable_picks_for_team(canonical, buyer['id']), key=lambda pick: pick_offer_preference_score(pick, buyer_state.get('phase', 'balanced'), target_value) + 8 * search_priority(canonical, seller['id'], {'kind': 'pick', 'id': pick['id']}), reverse=True)[:9]
    firsts = [pick for pick in picks if int(pick.get('round') or 2) == 1]
    seconds = [pick for pick in picks if int(pick.get('round') or 2) == 2]
    protection_options = {p['id']: ai_pick_protection_options(canonical, buyer, seller, p, buyer_state.get('phase', 'neutral')) for p in firsts[:3]} if return_options else {}
    swaps = sorted(tradeable_pick_swaps_for_team(canonical, buyer['id']), key=lambda swap: pick_swap_asset_value(canonical, swap, buyer_state.get('phase', 'neutral')), reverse=True)[:3]
    new_swap_options = ai_pick_swap_grant_options(canonical, buyer, seller, target_value, seed, buyer_state.get('phase', 'neutral')) if allow_new_pick_swaps else []
    pick_variants = [()]
    pick_variants.extend(((pick,) for pick in seconds[:4]))
    pick_variants.extend(((swap,) for swap in swaps))
    if len(seconds) >= 2:
        pick_variants.extend(combinations(seconds[:4], 2))
    if len(seconds) >= 3:
        pick_variants.append(tuple(seconds[:3]))
    if target_value >= 38:
        pick_variants.extend(((pick,) for pick in firsts[:3]))
        if target_value >= 70 and len(firsts) >= 2:
            pick_variants.extend(combinations(firsts[:5], 2))
        for first in firsts[:2]:
            for second in seconds[:3]:
                pick_variants.append((first, second))
    elif not seconds and firsts:
        pick_variants.append((firsts[0],))
    packages: list[tuple[float, list[dict[str, Any]], list[dict[str, Any]]]] = []
    max_player_count = 3 if target_value >= 60 and int(max_player_options) > 5 else 2
    rough_value_by_player = {player['id']: offer_player_rough_value(canonical, player, target_value, target_salary, valuations) for player in tradable_players}
    for player_count in range(1, min(max_player_count, len(tradable_players)) + 1):
        for player_group in combinations(tradable_players, player_count):
            player_assets = [{'kind': 'player', 'value': player['name']} for player in player_group]
            player_salary = sum((salary_by_player.get(player['id'], 0.0) for player in player_group))
            for pick_group in pick_variants:
                if len(player_assets) + len(pick_group) > 4:
                    continue
                assets = [*player_assets, *[{'kind': pick.get('kind', 'pick'), 'value': pick['id']} for pick in pick_group]]
                rough_value = sum((rough_value_by_player[player['id']] for player in player_group))
                rough_value += sum((pick_swap_asset_value(canonical, pick, buyer_state.get('phase', 'neutral')) if pick.get('kind') == 'pick_swap' else pick_asset_value(pick, buyer_state.get('phase', 'neutral')) for pick in pick_group))
                distant_risk = sum((far_future_pick_risk(pick) for pick in pick_group))
                candidate_variants: list[tuple[list[dict[str, Any]], list[dict[str, Any]], float, float]] = [(assets, [], rough_value, distant_risk)]
                selected_ids = {p['id'] for p in pick_group}
                for pick in pick_group:
                    for option in protection_options.get(pick['id'], []):
                        if selected_ids.intersection(option['term']['fallback_pick_ids']):
                            continue
                        protected_value = rough_value - pick_asset_value(pick, buyer_state.get('phase', 'neutral')) + option['value']
                        candidate_variants.append((assets, [option['term']], protected_value, distant_risk + 0.3))
                if new_swap_options and len(assets) < 4 and (target_value >= 34):
                    for swap_option in new_swap_options[:4]:
                        swap_asset = {'kind': 'pick_swap', 'value': swap_option['id']}
                        swap_value = float(swap_option.get('value') or 0.0)
                        if swap_value <= 1.5:
                            continue
                        improved_gap = abs(rough_value + swap_value - target_value) <= abs(rough_value - target_value) + 1.15
                        if not improved_gap and rough_value >= target_value * 0.88:
                            continue
                        candidate_variants.append(([*assets, swap_asset], [swap_option['term']], rough_value + swap_value, distant_risk + float(swap_option.get('risk') or 0.0)))
                for variant_assets, terms, variant_value, variant_risk in candidate_variants:
                    search_value = variant_value
                    if target_value >= 70 and (not terms):
                        normalized_assets = [*[{'kind': 'player', 'id': player['id'], 'label': player['name']} for player in player_group], *[{'kind': pick.get('kind', 'pick'), 'id': pick['id'], 'label': pick.get('label') or pick.get('id')} for pick in pick_group]]
                        search_value = package_value_for_team(canonical, normalized_assets, seller['id'])
                    if search_value < target_value * (0.34 if target_value >= 56 else 0.38) or search_value > target_value * 1.48 + 14:
                        continue
                    salary_gap = abs(player_salary - (target_salary or player_salary)) / 1000000
                    complexity_cost = max(0, len(variant_assets) - 2) * (0.1 if target_value >= 56 else 0.32)
                    if terms:
                        complexity_cost += 0.22
                    packages.append((abs(search_value - target_value) + salary_gap * 0.22 + complexity_cost + variant_risk, variant_assets, terms))
    season = str(canonical.get('meta', {}).get('active_season') or CANONICAL_SEASON)
    if target_salary is not None and team_current_salary_total(canonical, buyer['id']) + target_salary <= cap_lines_for_season(season)['tax_line']:
        for group in pick_variants:
            if not group:
                continue
            assets = [{'kind': p.get('kind', 'pick'), 'value': p['id']} for p in group]
            value = sum((pick_swap_asset_value(canonical, p, buyer_state.get('phase', 'neutral')) if p.get('kind') == 'pick_swap' else pick_asset_value(p, buyer_state.get('phase', 'neutral')) for p in group))
            if target_value * 0.38 <= value <= target_value * 1.48 + 14:
                packages.append((abs(value - target_value) + sum((far_future_pick_risk(p) for p in group)), assets, []))
    if not packages:
        fallback = fallback_trade_packages(canonical, buyer, seller, tradable_players, seconds, firsts, target_value, target_salary, valuations)
        packages.extend(((score, assets, []) for score, assets in fallback))
    unique: list[list[dict[str, Any]]] = []
    unique_options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, assets, terms in sorted(packages, key=lambda item: (item[0], json.dumps(item[1], sort_keys=True), json.dumps(item[2], sort_keys=True))):
        key = json.dumps({'assets': assets, 'terms': terms}, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        if return_options:
            option = {'assets': assets}
            if terms:
                option['pick_obligation_terms'] = terms
            unique_options.append(option)
            if len(unique_options) >= max(4, int(max_results)):
                break
            continue
        if terms:
            continue
        unique.append(assets)
        if len(unique) >= max(4, int(max_results)):
            break
    return unique_options if return_options else unique
