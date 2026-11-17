# Frozen Stage-A evaluator: tests approval and explanation compatibility.
def evaluate_trade_for_team(canonical: dict[str, Any], proposal: TradeProposal, perspective_team_id: str, incoming_assets: list[dict[str, Any]], outgoing_assets: list[dict[str, Any]], legality: dict[str, Any], seed: int, config: dict[str, Any], *, plan_roster: bool=True, include_presentation: bool=True) -> TradeEvaluation:
    incoming = package_value_for_team(canonical, incoming_assets, perspective_team_id, outgoing_assets=outgoing_assets)
    outgoing = package_value_for_team(canonical, outgoing_assets, perspective_team_id)
    strategic = strategic_fit_adjustment(canonical, incoming_assets, outgoing_assets, perspective_team_id, config)
    from .trade_wants import package_preference
    wants = package_preference(canonical, perspective_team_id, incoming_assets, outgoing_assets, config=config)
    strategic += wants['adjustment']
    from .roster_space import sale_bonus
    space_bonus = sale_bonus(canonical, perspective_team_id, incoming_assets, outgoing_assets, outgoing)
    strategic += space_bonus
    personality = personality_trade_adjustment(canonical, perspective_team_id, proposal.id, seed)
    net = incoming - outgoing + strategic + personality['total']
    threshold = contextual_acceptance_threshold(canonical, perspective_team_id, config, incoming_assets, outgoing_assets)
    accepted = net >= threshold and legality['status'] == 'legal'
    from .team_planning import core_commitment
    committed = any((a.get('kind') == 'player' and core_commitment(canonical, perspective_team_id, a.get('id')) for a in outgoing_assets))
    commitment_blocked = committed and net < max(12.0, outgoing * 0.2)
    if commitment_blocked:
        accepted = False
    premium_issue = premium_return_issue(canonical, perspective_team_id, incoming_assets, outgoing_assets)
    if premium_issue:
        accepted = False
    outlook = None
    if plan_roster and legality['status'] == 'legal' and (net >= -9) and (not premium_issue) and (not commitment_blocked) and (perspective_team_id not in canonical.get('_human_team_ids', [])):
        from .trade_roster import trade_roster_outlook
        outlook = trade_roster_outlook(canonical, perspective_team_id, incoming_assets, outgoing_assets)
        if outlook:
            strategic += outlook['adjustment']
            net += outlook['adjustment']
            accepted = net >= threshold and (not outlook['issue'])
    decision = 'accept' if accepted else 'reject'
    if outlook and (outlook['issue'] or (outlook['adjustment'] < 0 and net < threshold)):
        decision = 'reject_roster_plan'
    investment = (outlook or {}).get('pick_investment')
    if investment and (net < -investment['loss_limit'] or ((investment['incoming_rotation_minutes'] < 24 or investment['rotation_gain'] < 0.25) and investment['net_draft_value_spent'] > investment['capital_limit'])):
        accepted = False
        decision = 'reject_pick_investment'
    if premium_issue:
        decision = 'reject_premium_return'
    if legality['status'] == 'manual_review_required':
        decision = 'manual_review_required'
    if legality['status'] == 'illegal':
        decision = 'illegal_reject'
    reasons = []
    if commitment_blocked:
        reasons.append('Core commitment: this return does not justify breaking the current trial window.')
    if premium_issue:
        reasons.append(premium_issue)
    if outlook and outlook['issue']:
        reasons.append(outlook['issue'])
    if decision == 'reject_pick_investment':
        reasons.append('Too much draft capital for the projected rotation improvement.')
    if net < threshold:
        reasons.append(f'Net value {net:.2f} is below the required {threshold:.2f}.')
    if legality['status'] != 'legal':
        reasons.extend(legality.get('issues', []) + legality.get('manual_review', []))
    state = next((s for s in canonical.get('team_strategic_states', []) if s.get('team_id') == perspective_team_id), {})
    return TradeEvaluation(id=stable_id('trade_evaluation', proposal.id, perspective_team_id), proposal_id=proposal.id, perspective_team_id=perspective_team_id, accepted=accepted, decision=decision, incoming_value=round(incoming + strategic, 3), outgoing_value=round(outgoing, 3), net_value=round(net, 3), legality_status=legality['status'], legality_issues=list(legality['issues']), personality_adjustments=personality, acceptance_threshold=threshold, window_phase=state.get('window_phase'), incoming_asset_value=round(incoming, 3), strategic_adjustment=round(strategic, 3), decision_reasons=reasons, notes=evaluation_notes(canonical, perspective_team_id, net, threshold, strategic, personality, legality, accepted=accepted) + (' Core commitment: ordinary return does not justify breaking the current trial window.' if commitment_blocked else '') + (f' {premium_issue}' if premium_issue else '') + (f' Roster-space opportunity credit: {space_bonus:.2f}.' if space_bonus else '') + (f" Published wants: {len(wants['matches'])} matching asset(s), additional preference credit {wants['adjustment']:.2f}." if wants['matches'] else '') + (f" Final roster: strength {outlook['strength_delta']:+.2f}; incremental waiver cost ${outlook['waiver_cost_millions']:.2f}M. {outlook['issue'] or ''}" if outlook else '') + (f" Draft investment: {investment['net_draft_value_spent']:.2f} net value spent; marginal-acquisition capital limit {investment['capital_limit']:.2f}; justified value-loss limit {investment['loss_limit']:.2f}." if investment else '') if include_presentation else '')
