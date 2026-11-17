"""Review-owned financial facts and authoritative movement classification."""
from copy import deepcopy
from dataclasses import dataclass, field
import json
from types import SimpleNamespace


@dataclass(frozen=True)
class TradeSearchIntent:
    seller_id: str
    buyer_id: str
    target_assets: tuple
    date: str
    config: dict | None = None
    config_key: str = field(init=False, repr=False)

    def __post_init__(self):
        from . import transactions as tx
        config = deepcopy(self.config) if self.config is not None else tx.default_transaction_model_config()
        object.__setattr__(self,'config',config)
        object.__setattr__(self,'config_key',json.dumps(config,sort_keys=True))


@dataclass(frozen=True)
class MovementClass:
    category: str
    issues: tuple = ()
    manual: tuple = ()


def financial_fact(canonical, key, compute):
    facts = canonical.get('_trade_financial_facts')
    if facts is None:
        return compute()
    if key in facts:
        if canonical.get('_search_work_counts') is not None:
            canonical['_search_work_counts']['financial_fact_hits'] += 1
        return facts[key]
    result = compute()
    # Team/season raw facts only, not participant conclusions or career graphs.
    if len(facts) >= 256:
        facts.clear()
    facts[key] = result
    if canonical.get('_search_work_counts') is not None:
        counts=canonical['_search_work_counts']
        counts['financial_fact_misses'] += 1
        counts['financial_fact_peak'] = max(counts['financial_fact_peak'],len(facts))
    return result


def unavailable_players(canonical, date):
    from . import transactions as tx
    def compute():
        recent = tx.recently_traded_player_ids(canonical, date) | tx.recently_signed_player_ids(canonical, date)
        return frozenset(recent | {p['id'] for p in canonical.get('players', [])
            if tx.goat_exception_player(p) or tx.contract_expired_without_rights(tx.contract_for_player(canonical,p['id']))})
    return financial_fact(canonical, ('unavailable', date), compute)


def classify_movements(canonical, intent, player_assets):
    from . import transactions as tx
    config = intent.config or tx.default_transaction_model_config()
    # Financial rules depend on the actual ordered player flows. Pick ownership,
    # terms, Stepien, strategic purpose and investment remain proposal checks.
    target = [a for a in intent.target_assets if a['kind']=='player']
    incoming = [a for a in player_assets if a['kind']=='player']
    counts = canonical.get('_search_work_counts')
    key=(intent.seller_id,intent.buyer_id,tuple(a['id'] for a in target),tuple(a['id'] for a in incoming),
         intent.date,intent.config_key)
    cache=canonical.get('_trade_movement_classes')
    if cache is not None and key in cache:
        if counts is not None:
            counts['classification_hits'] += 1
            counts['classified_visits.'+cache[key].category] += 1
        return cache[key]
    if counts is not None:counts['classification_misses'] += 1
    blocked=unavailable_players(canonical,intent.date)
    wrong=any((tx.player_by_id(canonical,a['id']) or {}).get('team_id')!=tid
              for tid,assets in ((intent.seller_id,target),(intent.buyer_id,incoming)) for a in assets)
    if wrong or any(a['id'] in blocked for a in target+incoming):
        result=MovementClass('terminal',('Player ownership or trade eligibility blocks this movement.',))
    else:
        proposal=SimpleNamespace(from_team_id=intent.seller_id,to_team_id=intent.buyer_id,
                                 from_assets=target,to_assets=incoming,date=intent.date)
        financial=tx.trade_salary_legality(canonical,proposal,config)
        roster=tx.roster_count_issues(canonical,proposal,config)
        issues=tuple(financial['issues']+roster)
        if financial['manual_review'] or any('unresolved' in i for i in issues):
            result=MovementClass('unresolved',issues,tuple(financial['manual_review']))
        elif issues:
            # Matching and current/future cap or roster violations may be
            # repairable with a third team. Never infer terminal from an overage.
            result=MovementClass('repairable',issues)
        else:
            result=MovementClass('legal')
    if counts is not None:
        counts['classified_groups.'+result.category] += 1
        counts['classified_visits.'+result.category] += 1
    if cache is not None:
        if len(cache)>=2048:
            cache.clear()
            if counts is not None:counts['movement_cache_resets'] += 1
        cache[key]=result
        if counts is not None: counts['movement_cache_peak'] = max(counts['movement_cache_peak'],len(cache))
    return result


def fast_normalize(canonical, team_id, specs):
    from . import transactions as tx
    def unique_names():
        names={};duplicates=set()
        for player in canonical['players']:
            if player.get('team_id')!=team_id:continue
            if player['name'] in names:duplicates.add(player['name'])
            names[player['name']]=player['id']
        return {name:pid for name,pid in names.items() if name not in duplicates}
    names=financial_fact(canonical,('names',team_id),unique_names)
    result=[]
    for asset in specs:
        value=asset.get('id') or asset.get('value')
        if asset['kind']=='player':
            exact=tx.player_by_id(canonical,value)
            pid=exact['id'] if exact and exact.get('team_id')==team_id else names.get(value)
            if pid is None:pid=tx.resolve_player(canonical,str(value),team_id=team_id)['id']
        else:pid=value
        result.append({'kind':asset['kind'],'id':pid,'label':value})
    return result


def repair_record(canonical, intent, option):
    from .utils import stable_id
    from . import transactions as tx
    assets=fast_normalize(canonical,intent.buyer_id,option['assets'])
    proposal={'id':stable_id('repair_seed',intent.date,intent.seller_id,intent.buyer_id,json.dumps(option['assets'],sort_keys=True)),
              'date':intent.date,'from_team_id':intent.seller_id,'to_team_id':intent.buyer_id,
              'from_assets':deepcopy(list(intent.target_assets)),'to_assets':assets}
    movement=classify_movements(canonical,intent,assets)
    supported = any('matching tolerance' in i or 'hard-cap' in i or 'roster hard maximum' in i for i in movement.issues)
    return {'proposal':proposal,'legality':{'status':'illegal','issues':list(movement.issues),'manual_review':list(movement.manual)},
            'evaluations':[], 'accepted_by_all':False,'combined_score':0,
            '_repair_rank':(0 if supported else 1,option['_repair_score'],proposal['id'])}
