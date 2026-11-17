"""Read-only partial legacy-consumer probes. No economy cutover or approvals.

The bridge is explicitly provisional and NOT a new DEF/OVR/R18 calibration.
Full legacy impact, scarcity, comps, plans and retention remain unconverted.
"""
from nba_gm_data.interior_defense import clamp, reference_report


def consumer_probe(canonical,profile):
    from nba_gm_data import contract_ai as contracts, save, sim, transactions
    player_id=profile.inputs.player_id
    player=next(p for p in canonical['players'] if p['id']==player_id)
    team=next(t for t in canonical['teams'] if t['id']==player['team_id'])
    before=dict(sim.player_feature_vector(canonical,player,include_spatial=False).features)
    report=reference_report(profile)
    # Diagnostic scale: 50 conversion points prevented/100 reference rim FGA
    # maps to 100. It is an arbitrary declared bridge for dependency inspection.
    bridge=clamp(report['C36']['conversion_points_prevented_per_100_rim_fga']/50, .01,.99)*100
    after={**before,'rim_deterrence':bridge}
    raw={r['trait_key']:float(r['value']) for r in canonical['traits'] if r['player_id']==player['id']}
    portability=raw['portability']
    old_value=transactions.player_on_court_value(before,portability)
    new_value=transactions.player_on_court_value(after,portability)
    valuation=next(r for r in canonical['player_asset_valuations'] if r['player_id']==player['id'])
    contract=transactions.contract_for_player(canonical,player['id']) or {}
    config=contracts.default_contract_market_config()
    prices=[];quotes=[]
    base_market=next(r for r in canonical['player_contract_market_profiles'] if r['player_id']==player['id'])
    for feature,value in ((before,old_value),(after,new_value)):
        val={**valuation,'on_court_value':value}
        tier=contracts.contract_role_tier(player,val,feature)
        uncapped=contracts.model_expected_aav(player,val,feature,contract,tier,config)
        price=contracts.clamp_salary_to_role(uncapped,tier,config)
        prices.append({'role_tier':tier,'model_aav':price,'uncapped_model_aav':uncapped,'on_court_value':value})
        market={**base_market,'expected_aav':price,'asking_aav':price*(base_market['asking_aav']/base_market['expected_aav'])}
        # Private plain views only. Full market comp rebuilding is not reached.
        view={k:v for k,v in canonical.items() if not str(k).startswith('_')}
        view['player_asset_valuations']=[val if r['player_id']==player['id'] else r for r in canonical['player_asset_valuations']]
        view['player_contract_market_profiles']=[market if r['player_id']==player['id'] else r for r in canonical['player_contract_market_profiles']]
        offer=contracts.contract_offer('interior_probe',team['id'],player['id'],'extension',1,2,base_market['expected_aav'],'starter','diagnostic_only','No application or approval')
        pscore,reasons=contracts.player_offer_score(view,player,team,offer,17,config)
        tscore=contracts.team_offer_score(view,player,team,offer,'extension',17,config)
        quotes.append({'same_offer_aav':offer.annual_salary,'player_score':pscore,'team_score':tscore,'reasons':reasons})
    career={'version':'league_save_v1','meta':{'season':'2026-27','active_season':'2026-27'},'team_plans':{}}
    retention_before=save.ai_roster_retention_score(canonical,career,player)
    from nba_gm_data.player_model import put_player_inputs
    put_player_inputs(career,profile.inputs)
    retention_after=save.ai_roster_retention_score(canonical,career,player)
    return {'player_id':player['id'],'input_revision':profile.revision,'scope':'diagnostic scalar bridge only, no production decisions/settlement',
        'bridge':{'C36_conditional_conversion_readout':report['C36'],'legacy_rim_feature_before':before['rim_deterrence'],'legacy_rim_feature_after':bridge,'declared_scale':'50 conversion points prevented/100 rim FGA = 100; NOT calibrated'},
        'on_court_before_after':[old_value,new_value],'contract_before_after':prices,'negotiation_quote_before_after':quotes,
        'retention_before_after':[retention_before,retention_after],
        'unwired':['live profile/valuation generation','legacy impact composites and scarcity','full market comps and league-relative state','actual negotiation/app actions/settlements','retention/card DEF/OVR','development/prospects'],
        'retention_new_inputs_alone_change':retention_after-retention_before}
