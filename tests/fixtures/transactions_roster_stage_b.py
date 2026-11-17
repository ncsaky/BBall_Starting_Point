"""Frozen pre-pass Stage B functions, loaded with original module dependencies."""

def build_transaction_context(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = canonical_mapping(canonical)
    config = config or default_transaction_model_config()
    front_offices = canonical.get("front_office_profiles") or to_plain(build_front_office_profiles(canonical.get("teams", []), canonical.get("team_profiles", []), {}))
    working = {**canonical, "front_office_profiles": front_offices}
    valuations = build_player_asset_valuations(working, config)
    working["player_asset_valuations"] = [to_plain(value) for value in valuations]
    states = build_team_strategic_states(working, valuations, config)
    working["team_strategic_states"] = [to_plain(state) for state in states]
    trade_block = build_trade_block_entries(working, states, valuations, config)
    return {
        "_strategy_model_version": STRATEGY_MODEL_VERSION,
        "front_office_profiles": front_offices,
        "team_strategic_states": [to_plain(state) for state in states],
        "player_asset_valuations": [to_plain(value) for value in valuations],
        "trade_block_entries": [to_plain(entry) for entry in trade_block],
    }

def build_team_strategic_states(canonical: dict[str, Any] | Any, valuations: list[PlayerAssetValuation] | None = None, config: dict[str, Any] | None = None) -> list[TeamStrategicState]:
    canonical = canonical_mapping(canonical)
    config = config or default_transaction_model_config()
    if valuations is None:
        valuations = build_player_asset_valuations(canonical, config)
    values_by_team: dict[str, list[PlayerAssetValuation]] = {}
    for valuation in valuations:
        values_by_team.setdefault(valuation.team_id, []).append(valuation)
    profiles = {profile["team_id"]: profile for profile in canonical.get("team_profiles", [])}
    front_offices = {profile["team_id"]: profile for profile in canonical.get("front_office_profiles", [])}
    output: list[TeamStrategicState] = []
    for team in canonical.get("teams", []):
        team_values = sorted(values_by_team.get(team["id"], []), key=lambda item: item.player_value, reverse=True)
        players = [player for player in canonical.get("players", []) if player["team_id"] == team["id"]]
        top_players = [player_by_id(canonical, value.player_id) for value in
                       sorted(team_values, key=lambda v: (-v.on_court_value, v.player_id))[:5]]
        top_ages = [float(player.get("display_age", player.get("age"))) for player in top_players
                    if player and player.get("display_age", player.get("age")) is not None]
        core_age = sum(top_ages[:3]) / len(top_ages[:3]) if top_ages[:3] else None
        ceiling = contention_ceiling(canonical, team, team_values)
        youth = youth_pipeline_score(players, team_values)
        pick_inventory = team_pick_inventory(canonical, team["id"])
        health_risk = team_health_risk(canonical, team_values[:6])
        salary = salary_posture(canonical, team["id"])
        profile = profiles.get(team["id"], {})
        front_office = front_offices.get(team["id"], {})
        phase = classify_team_phase(profile, ceiling, core_age, youth, pick_inventory, config)
        needs, excesses = team_needs_and_excesses(canonical, team, players, phase)
        pressure = strategic_pressure(profile, front_office, phase, core_age)
        output.append(
            TeamStrategicState(
                id=stable_id("team_strategy", team["id"]),
                team_id=team["id"],
                phase=phase,
                timeline=phase,
                contention_ceiling=round(ceiling, 2),
                core_age=round(core_age, 2) if core_age is not None else None,
                health_risk=round(health_risk, 3),
                salary_posture=salary["posture"],
                youth_pipeline=round(youth, 2),
                pick_inventory=pick_inventory,
                needs=needs,
                excesses=excesses,
                pressure=round(pressure, 2),
                confidence=round(0.52 + min(0.18, float(profile.get("confidence") or 0) * 0.15), 3),
                source_ids=["src_transaction_model_config_v1", "src_trait_method_v1", *list(profile.get("source_ids") or [])],
                notes="Live roster strategy from player values, age, health, salary, needs and picks. Imported research timelines do not override the phase.",
            )
        )
    from .team_planning import window_assessments, LEGACY_PHASE
    assessments = window_assessments(canonical, output, valuations)
    if len(output) >= 4:
        revised = []
        for state in output:
            row = assessments[state.team_id]
            phase = LEGACY_PHASE[row['window_phase']]
            if phase == 'contending' and state.youth_pipeline >= 45:
                phase = 'contending_with_future_upside'
            needs, excesses = team_needs_and_excesses(canonical, team_by_id(canonical, state.team_id),
                [p for p in canonical.get('players', []) if p.get('team_id') == state.team_id], phase)
            revised.append(replace(state, phase=phase, timeline=phase, needs=needs, excesses=excesses,
                window_phase=row['window_phase'], league_rank=row['league_rank'], contender_index=row['contender_index'],
                window_trend=row['trend'], core_candidates=row['core_candidates']))
        return revised
    return output

def trade_search_context(canonical: dict[str, Any]) -> dict[str, Any]:
    """One immutable search's player-only forecasts; never retain across settlements."""
    return {**canonical, '_trade_search_roles': {}, '_trade_search_rosters': {},
            '_trade_financial_facts': {}, '_trade_movement_classes': {}}

def with_transaction_context(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach reusable transaction projections, rebuilding only when stale.

    Callers may evaluate many packages against this object. Cache signatures
    must therefore include every season, record, ownership, and obligation
    input that can alter a projected value.
    """
    if isinstance(canonical, dict) and canonical.get("_allow_internal_caches") and transaction_context_ready(canonical):
        return canonical
    if isinstance(canonical, dict) and canonical.get("_allow_internal_caches") and transaction_context_is_complete(canonical):
        ensure_future_second_round_scaffolds(canonical)
        simplify_unsupported_pick_conditions(canonical)
        ensure_pick_value_context(canonical)
        annotate_pick_obligation_context(canonical)
        mark_pick_value_context_current(canonical)
        return canonical
    if isinstance(canonical, dict):
        # Pick projection helpers annotate their inputs. Isolate only those
        # comparatively small mutable structures instead of recursively
        # cloning a mature league, including years of read-only history.
        canonical = dict(canonical)
        if canonical.get('_strategy_model_version') != STRATEGY_MODEL_VERSION:
            for key in ('player_contract_market_profiles', 'player_contract_preferences',
                        'extension_candidates', 'free_agent_candidates'):
                canonical.pop(key, None)
        canonical["meta"] = dict(canonical.get("meta") or {})
        canonical["draft_picks"] = deepcopy(canonical.get("draft_picks") or [])
        canonical["pick_obligations"] = deepcopy(canonical.get("pick_obligations") or [])
        canonical["locked_pick_assets"] = list(canonical.get("locked_pick_assets") or [])
        canonical.pop("_transaction_pick_context_signature", None)
    else:
        canonical = to_plain(canonical)
    canonical["_allow_internal_caches"] = True
    ensure_future_second_round_scaffolds(canonical)
    simplify_unsupported_pick_conditions(canonical)
    if transaction_context_is_complete(canonical):
        ensure_pick_value_context(canonical)
        annotate_pick_obligation_context(canonical)
        mark_pick_value_context_current(canonical)
        return canonical
    context = build_transaction_context(canonical, config)
    enriched = {**canonical, **context}
    ensure_pick_value_context(enriched)
    annotate_pick_obligation_context(enriched)
    mark_pick_value_context_current(enriched)
    return enriched

def strategic_rotation_view(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    """Forecast a healthy two-deep roster, not minutes carried from old teams."""
    from .save import ai_role_targets, bounded_minutes_allocation, player_attribute_summary, round_minutes_to_total
    from .sim import team_feature_vector
    roster = [dict(p, minutes_projection=24) for p in canonical.get('players', [])
              if p.get('team_id') == team_id and not p.get('_inactive_player')]
    # Cached player/roster indexes belong to the source view, not this trial.
    trial = {k: v for k, v in canonical.items() if not str(k).startswith('_')}
    trial['players'] = roster
    trial['_allow_internal_caches'] = True
    if not roster:
        return trial
    targets, selected = ai_role_targets(trial, roster, {})
    backups = sorted(selected[5:], key=lambda pid: (-player_attribute_summary(trial, pid)['overall'], pid))
    order = selected[:5]+backups
    base = {k: v for k, v in trial.items() if not str(k).startswith('_')}
    team = team_by_id(canonical, team_id) or {'id': team_id}
    candidates = []
    # A coach may use a tighter rotation; signing a weak reserve does not
    # obligate a competitive roster to dilute its strongest minutes.
    for count in sorted({min(len(order), n) for n in (8, 9, 10)}):
        ids = set(order[:count])
        allocation = bounded_minutes_allocation([
            {'player_id': p['id'], 'desired': targets[p['id']], 'minimum': 0,
             'maximum': 48 if len(ids) <= 5 else 42} for p in roster if p['id'] in ids], 240)
        allocation = round_minutes_to_total(allocation, 240)
        view = {**base, 'players': [dict(p, minutes_projection=allocation[p['id']])
                                  for p in roster if p['id'] in ids], '_allow_internal_caches': True}
        score = contention_from_features(team_feature_vector(view, team, include_spatial=False).features)
        candidates.append((score, count, view))
    return max(candidates, key=lambda row: (row[0], row[1]))[2]

