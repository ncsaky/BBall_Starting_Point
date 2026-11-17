"""Exact historical generator and stable bounded-selection regressions."""
import ast
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch
from nba_gm_data import transactions as tx
from nba_gm_data.trade_package_search import PackageShortlist
from test_multi_team_trades import fixture

ROOT=Path(__file__).resolve().parents[1]
def reference_generator():
    path=ROOT/'tests/fixtures/trade_package_generator_task2.py'
    tree=ast.parse(path.read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='buyer_offer_packages_for_value')
    namespace=dict(vars(tx))
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    return namespace[node.name]


class PackageSearchTests(unittest.TestCase):
    def test_bounded_selector_matches_stable_sort_with_ties_and_duplicates(self):
        for seed in range(12):
            rng=random.Random(seed)
            candidates=[(rng.choice([1.,2.,3.,4.]),[{'kind':'pick','value':str(rng.randrange(35))}],
                         [{'protection':rng.randrange(3)}] if rng.randrange(3)==0 else []) for _ in range(300)]
            # Same identity improves after being retained or evicted.
            candidates += [(0.,deepcopy(candidates[0][1]),deepcopy(candidates[0][2]))]
            for include_terms in (False,True):
                for limit in (0,4,12,24):
                    selected=PackageShortlist(limit,include_terms)
                    selected.extend(deepcopy(candidates))
                    expected=[];seen=set()
                    for row in sorted(candidates,key=lambda r:(r[0],json.dumps(r[1],sort_keys=True),json.dumps(r[2],sort_keys=True))):
                        key=json.dumps({'assets':row[1],'terms':row[2]},sort_keys=True)
                        if key in seen:continue
                        seen.add(key)
                        if row[2] and not include_terms:continue
                        expected.append(row)
                        if len(expected)>=max(4,limit):break
                    self.assertEqual(selected.ordered(),expected)
                    self.assertLessEqual(len(selected.entries),max(4,limit))
        only_terms=PackageShortlist(4,False)
        only_terms.append((1,[],[{'type':'protected_pick'}]))
        self.assertTrue(only_terms) # Hidden terms do not enable fallback.
        self.assertEqual(only_terms.ordered(),[])

    def test_exact_lists_across_values_modes_protections_swaps_and_empty_inputs(self):
        reference=reference_generator()
        for target in (0,20,38,59.999,60,69.999,70,90,92,120,1000):
            for options in (False,True):
                source=tx.trade_search_context(tx.with_transaction_context(fixture()))
                args=(source,source['teams'][1],source['teams'][0],target,30_000_000,17)
                kwargs={'max_results':12,'max_player_options':9,'return_options':options,'allow_new_pick_swaps':True}
                expected=reference(*args,**kwargs)
                actual=tx.buyer_offer_packages_for_value(*args,**kwargs)
                self.assertEqual(actual,expected,(target,options))
        for players,picks in (([],[]),([],[{'id':'x','round':2,'season':'2030','current_owner_team_id':'b','original_team_id':'b'}])):
            source=fixture();source['players']=players;source['draft_picks']=picks
            source=tx.with_transaction_context(source)
            args=(source,source['teams'][1],source['teams'][0],92,10_000_000,1)
            self.assertEqual(tx.buyer_offer_packages_for_value(*args),reference(*args))

    def test_float_scores_and_fallback_remain_exact(self):
        reference=reference_generator()
        source=tx.trade_search_context(tx.with_transaction_context(fixture()))
        for index,row in enumerate(source['player_asset_valuations']):
            row['player_value']=float(index%11)+1.000000000000002
            row['on_court_value']=float(index%11)+.3333333333333333
        args=(source,source['teams'][1],source['teams'][0],92,30_000_000,29)
        kwargs={'max_results':24,'max_player_options':12,'return_options':True,'allow_new_pick_swaps':True}
        self.assertEqual(tx.buyer_offer_packages_for_value(*args,**kwargs),reference(*args,**kwargs))
        # Force value-filter exhaustion and preserve the fallback's ordering.
        with patch.object(tx,'package_value_components',return_value=(-1e6,0)), \
             patch.object(tx,'package_value_for_team',return_value=-1e6), \
             patch.object(tx,'ai_pick_protection_options',return_value=[]), \
             patch.object(tx,'ai_pick_swap_grant_options',return_value=[]), \
             patch.object(tx,'team_current_salary_total',return_value=1e12), \
             patch.object(tx,'fallback_trade_packages',return_value=[(3,[{'kind':'player','value':'b0'}])]) as fallback:
            kwargs['allow_new_pick_swaps']=False
            self.assertEqual(tx.buyer_offer_packages_for_value(*args,**kwargs),reference_generator()(*args,**kwargs))
            self.assertEqual(fallback.call_count,2)

    def test_returned_packages_do_not_share_new_pick_asset_dictionaries(self):
        source=tx.with_transaction_context(fixture())
        packages=tx.buyer_offer_packages_for_value(source,source['teams'][1],source['teams'][0],60,15_000_000,1,max_results=24)
        before=deepcopy(packages)
        if packages:
            packages[0][0]['value']='changed'
            self.assertEqual(packages[1:],before[1:])

    def test_entire_generated_score_stream_keeps_float_bits(self):
        import builtins
        from nba_gm_data import trade_package_search as search
        source=tx.trade_search_context(tx.with_transaction_context(fixture()))
        args=(source,source['teams'][1],source['teams'][0],92,30_000_000,17)
        kwargs={'max_results':24,'max_player_options':9,'return_options':True,'allow_new_pick_swaps':True}
        reference=reference_generator();old_rows=[];new_rows=[]
        def record_sort(items,*a,**kw):
            if isinstance(items,list) and items and isinstance(items[0],tuple) and len(items[0])==3 and isinstance(items[0][1],list):
                old_rows.extend(deepcopy(items))
            return builtins.sorted(items,*a,**kw)
        reference.__globals__['sorted']=record_sort
        reference(*args,**kwargs)
        append=search.PackageShortlist.append
        def record_append(self,row):
            new_rows.append(deepcopy(row));return append(self,row)
        with patch.object(search.PackageShortlist,'append',record_append):
            tx.buyer_offer_packages_for_value(*args,**kwargs)
        encode=lambda rows:[(float(score).hex(),assets,terms) for score,assets,terms in rows]
        self.assertTrue(old_rows)
        self.assertEqual(encode(new_rows),encode(old_rows))

    def test_90_and_92_premium_players_cannot_be_bought_with_accumulated_depth(self):
        import test_premium_trade_returns as premium
        for ability in (90,92,96):
            source,outgoing=premium.PremiumTradeReturnTests().fixture()
            source['players'][0].update(overall=ability,current_ability=ability)
            source['player_asset_valuations'][0].update(on_court_value=ability,player_value=110)
            for index in range(3,9):
                player=deepcopy(source['players'][1]);player.update(id=f'depth{index}',name=f'depth{index}')
                value=deepcopy(source['player_asset_valuations'][1]);value['player_id']=player['id']
                source['players'].append(player);source['player_asset_valuations'].append(value)
            for count in (2,4,8):
                incoming=[{'kind':'player','id':f'depth{i}'} for i in range(1,count+1)]
                self.assertIsNotNone(tx.premium_return_issue(source,'a',incoming,outgoing))

    def test_duplicate_protection_and_swap_variants_keep_the_exact_list(self):
        source=tx.trade_search_context(tx.with_transaction_context(fixture()))
        protections,swaps=tx.ai_pick_protection_options,tx.ai_pick_swap_grant_options
        with patch.object(tx,'ai_pick_protection_options',side_effect=lambda *a,**k:protections(*a,**k)*2), \
             patch.object(tx,'ai_pick_swap_grant_options',side_effect=lambda *a,**k:swaps(*a,**k)*2):
            reference=reference_generator()
            args=(source,source['teams'][1],source['teams'][0],92,30_000_000,17)
            kw={'max_results':24,'max_player_options':9,'return_options':True,'allow_new_pick_swaps':True}
            self.assertEqual(tx.buyer_offer_packages_for_value(*args,**kw),reference(*args,**kw))

    def test_pick_only_payment_and_authoritative_salary_absorption_remain_available(self):
        source=tx.trade_search_context(tx.with_transaction_context(fixture()))
        buyer,seller=source['teams'][1],source['teams'][0]
        excluded={p['id'] for p in source['players'] if p['team_id']==buyer['id']}
        args=(source,buyer,seller,20,16_250_000,17)
        packages=tx.buyer_offer_packages_for_value(*args,excluded_player_ids=excluded)
        self.assertEqual(packages,reference_generator()(*args,excluded_player_ids=excluded))
        self.assertTrue(packages)
        self.assertTrue(all(all(a['kind']!='player' for a in package) for package in packages))
        report=tx.evaluate_trade_decision(source,'A','B',[{'kind':'player','value':'a12'}],packages[0],context_ready=True)
        self.assertEqual(report['legality']['status'],'legal',report['legality'])
