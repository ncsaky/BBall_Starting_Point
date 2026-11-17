"""Optional counters for frozen and bounded package generators; no save mutation."""
import ast
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import inspect
import json
from unittest.mock import patch
from nba_gm_data import transactions as tx


class CountingPackages(list):
    def __init__(self, metrics):
        super().__init__();self.metrics=metrics;self.seen=set()
    def append(self,row):
        super().append(row)
        self.metrics['generated_packages']+=1
        key=json.dumps({'assets':row[1],'terms':row[2]},sort_keys=True)
        if key not in self.seen:
            self.seen.add(key);self.metrics['unique_packages']+=1
        self.metrics['peak_materialized_packages']=max(self.metrics['peak_materialized_packages'],len(self))
    def extend(self,rows):
        for row in rows:self.append(row)


def legacy_generator(metrics):
    tree=ast.parse(inspect.getsource(tx.buyer_offer_packages_for_value))
    class Instrument(ast.NodeTransformer):
        def visit_For(self,node):
            self.generic_visit(node)
            if isinstance(node.target,ast.Name) and node.target.id=='player_group':
                node.body.insert(0,ast.parse("_metrics['player_groups'] += 1").body[0])
            if isinstance(node.target,ast.Name) and node.target.id=='pick_group' and isinstance(node.iter,ast.Name) and node.iter.id=='pick_variants':
                node.body.insert(0,ast.parse("_metrics['group_variant_pairs'] += 1").body[0])
            return node
        def visit_AnnAssign(self,node):
            if isinstance(node.target,ast.Name) and node.target.id=='packages':
                return ast.parse("_metrics['pick_variants'] += len(pick_variants)\npackages = _CountingPackages(_metrics)").body
            return node
    tree=Instrument().visit(tree)
    func=tree.body[0]
    func.body.insert(0,ast.parse('_metrics = _diagnostic_metrics').body[0])
    func.body.insert(-1,ast.parse("_metrics['shortlisted_packages'] += len(unique_options if return_options else unique)").body[0])
    namespace={**vars(tx),'_CountingPackages':CountingPackages,'_diagnostic_metrics':metrics}
    ast.fix_missing_locations(tree)
    exec(compile(tree,'<instrumented task-2 package generator>','exec'),namespace)
    return namespace[func.name]


@contextmanager
def instrument(metrics, query_log=None, rejection_counts=None):
    with ExitStack() as stack:
        for name in ('pick_asset_value','pick_swap_asset_value','far_future_pick_risk','package_value_for_team','package_value_components'):
            if not hasattr(tx,name):continue
            original=getattr(tx,name)
            def counted(*a,__original=original,__name=name,**kw):
                metrics[__name+'.calls']+=1;return __original(*a,**kw)
            stack.enter_context(patch.object(tx,name,counted))
        generator=tx.buyer_offer_packages_for_value if hasattr(tx,'package_value_components') else legacy_generator(metrics)
        def packages(*a,**kw):
            metrics['generator_calls']+=1
            result=generator(*a,**kw)
            if query_log is not None:
                query_log.append({'buyer':a[1]['id'],'seller':a[2]['id'],'target_value':a[3],
                                  'target_player_ids':sorted(a[6]) if len(a)>6 and a[6] else [],
                                  'packages':deepcopy(result)})
            return result
        stack.enter_context(patch.object(tx,'buyer_offer_packages_for_value',packages))
        evaluation=tx.evaluate_trade_decision
        def evaluate(*a,**kw):
            metrics['full_evaluations_observed']+=1
            result=evaluation(*a,**kw)
            if rejection_counts is not None:
                rejection_counts.update('legality: '+i for i in result.get('legality',{}).get('issues',[]))
                rejection_counts.update('decision: '+e['decision'] for e in result.get('evaluations',[]))
            return result
        stack.enter_context(patch.object(tx,'evaluate_trade_decision',evaluate))
        from nba_gm_data.trade_review import MarketReview
        prepare=MarketReview.prepare
        def prepared(*a,**kw):
            result=prepare(*a,**kw);result['_package_search_diagnostics']=metrics;return result
        stack.enter_context(patch.object(MarketReview,'prepare',prepared))
        yield
