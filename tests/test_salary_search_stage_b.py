"""Authoritative classification, immutable facts, and fully approved repair routes."""
import ast
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from nba_gm_data import transactions as tx
from nba_gm_data.trade_finance_search import TradeSearchIntent, classify_movements
from nba_gm_data.trade_review import MarketReview
from test_multi_team_trades import fixture, legs
import test_trade_salary_boundaries as salary


class SalaryAwareSearchTests(unittest.TestCase):
    def basic(self):
        source=salary.TradeSalaryBoundaryTests().fixture()[0]
        source['meta']={'active_season':'2026-27','current_date':'2027-02-03'}
        source['contracts']=[dict(c,_active_season='2026-27') for c in source['contracts']]
        return source

    def category(self,source,config=None):
        config=config or {'salary_matching':{'minimum_roster':0}}
        context=tx.trade_search_context(deepcopy(source))
        intent=TradeSearchIntent('a','b',({'kind':'player','id':'out'},),'2027-02-03',config)
        result=classify_movements(context,intent,[{'kind':'player','id':'in'}])
        proposal=SimpleNamespace(from_team_id='a',to_team_id='b',from_assets=list(intent.target_assets),to_assets=[{'kind':'player','id':'in'}])
        authoritative=tx.trade_salary_legality(source,proposal,config)
        self.assertEqual(tx.trade_salary_legality(context,proposal,config),authoritative)
        self.assertEqual(tx.roster_count_issues(context,proposal,config),tx.roster_count_issues(source,proposal,config))
        return result

    def test_matching_tolerance_floor_and_guaranteed_credit_boundaries(self):
        for amount,guaranteed,expected in ((11_250_000,None,'legal'),(11_250_000.01,None,'repairable'),
                                            (7_500_000,1_000_000,'legal'),(7_500_000.01,1_000_000,'repairable')):
            source=self.basic();tax=tx.cap_lines_for_season('2026-27')['tax_line']
            source['players'].append({'id':'filler','name':'filler','team_id':'a'})
            source['contracts'].append({'player_id':'filler','_active_season':'2026-27','seasons':[{'season':'2026-27','salary':tax+1-5_000_000}]})
            source['contracts'][1]['seasons'][0]['salary']=amount
            if guaranteed is not None:source['contracts'][0]['seasons'][0]['guaranteed_salary']=guaranteed
            self.assertEqual(self.category(source).category,expected,(amount,guaranteed))
        source['contracts'][0]['seasons'][0].update(guarantee_date='2027-02-01')
        self.assertEqual(self.category(source).category,'legal')

    def test_absorption_current_future_cap_and_unresolved_cases(self):
        source=self.basic()
        source['contracts'][1]['seasons'][0]['salary']=40_000_000
        self.assertEqual(self.category(source).category,'legal') # Actual payroll has absorption room.
        source['contracts'][2]['seasons'][0]['salary']=500_000_000
        source['contracts'][0]['seasons'][0]['salary']=80_000_000
        self.assertEqual(self.category(source).category,'repairable')
        for year in ('2027-28','2028-29','2029-30'):
            source=self.basic()
            source['contracts'][2]['seasons'].append({'season':year,'salary':500_000_000})
            source['contracts'][0]['seasons'].append({'season':year,'salary':20_000_000})
            result=self.category(source)
            self.assertEqual(result.category,'repairable')
            self.assertTrue(any(year in issue for issue in result.issues))
        source=self.basic();source['contracts'][0]['seasons'][0]['salary']=None
        self.assertEqual(self.category(source).category,'unresolved')
        source=self.basic();source['waived_salary_obligations']=[{'team_id':'a','seasons':[{'season':'2028-29','salary':None}]}]
        self.assertEqual(self.category(source).category,'unresolved')
        # Existing overages can be reduced; they are not an automatic ban.
        source=self.basic();source['contracts'][0]['seasons'][0]['salary']=2_000_000
        source['contracts'][1]['seasons'][0]['salary']=5_000_000
        source['contracts'][2]['seasons'][0]['salary']=500_000_000
        self.assertEqual(self.category(source).category,'legal')

    def test_roster_limit_and_minimum_require_repair_not_terminal_rejection(self):
        source=self.basic()
        intent=TradeSearchIntent('a','b',({'kind':'player','id':'out'},),'2027-02-03')
        result=classify_movements(tx.trade_search_context(source),intent,[])
        self.assertEqual(result.category,'repairable')
        self.assertTrue(any('minimum' in i for i in result.issues))
        source=fixture();source['players'] += [dict(source['players'][13],id=f'extra{i}') for i in range(12)]
        result=classify_movements(tx.trade_search_context(source),TradeSearchIntent('a','b',({'kind':'player','id':'a0'},),'2027-01-31'),[])
        self.assertEqual(result.category,'repairable')
        self.assertTrue(any('maximum' in i for i in result.issues))

    def test_financial_generator_keeps_pick_only_absorption_at_supported_floor(self):
        for salary_amount, direct_expected in ((7_500_000, True), (7_500_000.01, False)):
            source=fixture()
            source['contracts'][12]['seasons'][0]['salary']=salary_amount
            # Above tax, below hard cap: the authoritative supported floor,
            # rather than the old tax-only construction heuristic, governs.
            tax=tx.cap_lines_for_season('2026-27')['tax_line']
            source['contracts'][15]['seasons'][0]['salary'] += tax+1-tx.team_current_salary_total(source,'b')
            source=tx.trade_search_context(tx.with_transaction_context(source))
            intent=TradeSearchIntent('a','b',({'kind':'player','id':'a12'},),'2027-01-31')
            repairs=[]
            options=tx.buyer_offer_packages_for_value(source,source['teams'][1],source['teams'][0],20,salary_amount,17,
                excluded_player_ids={p['id'] for p in source['players'] if p['team_id']=='b'},
                return_options=True,intent=intent,repair_options=repairs)
            self.assertEqual(bool(options),direct_expected)
            self.assertEqual(bool(repairs),not direct_expected)
            for option in options:
                self.assertTrue(all(a['kind']!='player' for a in option['assets']))
                report=tx.evaluate_trade_decision(source,'A','B',[{'kind':'player','value':'a12'}],option['assets'],
                    context_ready=True,date='2027-01-31')
                self.assertEqual(report['legality']['status'],'legal',report['legality'])

    def test_unresolved_and_terminal_groups_do_not_run_participant_work(self):
        source=fixture();source['contracts'][0]['seasons'][0]['salary']=None
        source=tx.trade_search_context(tx.with_transaction_context(source));source['_search_work_counts']=Counter()
        with patch.object(tx,'evaluate_trade_participants',side_effect=AssertionError('Unresolved candidate evaluated')):
            result=tx.evaluate_trade_decision(source,'A','B',[{'kind':'player','value':'a0'}],[{'kind':'player','value':'b0'}],context_ready=True,search_only=True)
        self.assertFalse(tx.ai_trade_candidate_accepted(source,tx.candidate_from_decision(result)))
        self.assertEqual(result['evaluations'],[])
        self.assertEqual(source['_search_work_counts']['skipped_reports.unresolved'],1)
        source=tx.trade_search_context(fixture())
        source['players'][0]['name']='LeBron James'
        intent=TradeSearchIntent('a','b',({'kind':'player','id':'a0'},),'2027-01-31')
        self.assertEqual(classify_movements(source,intent,[{'kind':'player','id':'b0'}]).category,'terminal')

    def test_financial_facts_and_classifications_are_bounded_and_invalidate(self):
        source=self.basic();review=MarketReview()
        with patch.object(tx,'with_transaction_context',side_effect=lambda c,config=None:c), \
             patch.object(tx,'with_spatial_fit_context',side_effect=lambda c:c):
            first=review.prepare(source);intent=TradeSearchIntent('a','b',({'kind':'player','id':'out'},),'2027-02-03',{'salary_matching':{'minimum_roster':0}})
            expected=classify_movements(first,intent,[{'kind':'player','id':'in'}])
            with patch.object(tx,'_uncached_team_current_salary_total',side_effect=AssertionError('Payroll recomputed')):
                self.assertEqual(classify_movements(first,intent,[{'kind':'player','id':'in'}]),expected)
            for mutate in (lambda:source['contracts'][0]['seasons'][0].update(salary=40_000_000),
                           lambda:source['players'][0].update(team_id='b'),
                           lambda:source.update(player_health_states=[{'player_id':'in','availability_status':'out'}]),
                           lambda:source.update(team_plans={'a':{'core_ids':['out']}}),
                           lambda:source.update(team_trade_wants={'a':[{'kind':'upgrade'}]}),
                           lambda:source.update(draft_picks=[{'id':'pick','current_owner_team_id':'b'}])):
                mutate();later=review.prepare(source)
                self.assertIsNot(later,first)
                self.assertEqual(later['_trade_financial_facts'],{})
                self.assertEqual(later['_trade_movement_classes'],{})
                first=later
            self.assertIsNot(MarketReview().prepare(deepcopy(source)),first)
        review.close();self.assertIsNone(review.active)
        self.assertNotIn('_trade_financial_facts',source)

    def test_illegal_bilateral_seed_reaches_a_genuinely_approved_three_team_offer(self):
        source=fixture();source['trade_block_entries']=[{'player_id':'a0','block_score':100}]
        buyer=source['teams'][1]
        def options(c,b,s,p,seed,**kw):
            self.assertTrue(kw['financial_search'])
            kw['repair_options'].append({'assets':[{'kind':'player','value':'b0'},{'kind':'player','value':'b1'}],'_repair_score':1.})
            return []
        with patch.object(tx,'buyer_teams_for_player',wraps=tx.buyer_teams_for_player) as buyers, \
             patch.object(tx,'buyer_offer_package_options',side_effect=options), \
             patch.object(tx,'evaluate_trade_decision',side_effect=AssertionError('Repair seed fully evaluated')):
            original=buyers.side_effect
            # Only the primary query is forced; facilitator buyers still use real fit.
            full=tx.buyer_teams_for_player._mock_wraps
            buyers.side_effect=lambda c,p:[buyer] if p['id']=='a0' else full(c,p)
            result=tx.simulate_ai_trades(source,'2027-01-31','2027-01-31',seed=1,limit=10,search_depth=2,include_private_targets=False)
        self.assertTrue(result['proposals'],result['search_diagnostics'])
        for candidate in result['proposals']:
            self.assertTrue(candidate['proposal'].get('transfers'))
            self.assertTrue(candidate['accepted_by_all'])
            self.assertEqual(candidate['legality']['status'],'legal')
            self.assertFalse(tx.multi_team_participation_issues(source,candidate))
            self.assertTrue(all(e['accepted'] for e in candidate['evaluations']))
            self.assertIn('value_breakdown',candidate)
        self.assertLessEqual(result['search_diagnostics']['financial_work']['repair_frontier_peak'],16)

    def test_within_proposal_memo_preserves_full_legacy_approval_and_explanations(self):
        from nba_gm_data.multi_team_trades import evaluate_multi_team_trade
        path=Path(__file__).resolve().parents[1]/'tests/fixtures/evaluate_trade_for_team_stage_a.py'
        tree=ast.parse(path.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='evaluate_trade_for_team')
        namespace=dict(vars(tx));exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
        old=namespace[node.name]
        def legacy(*a,**kw):kw.pop('_calculation_cache',None);return old(*a,**kw)
        source=fixture()
        with patch.object(tx,'evaluate_trade_for_team',side_effect=legacy):
            expected=evaluate_multi_team_trade(deepcopy(source),legs(),date='2027-01-31')
        self.assertEqual(evaluate_multi_team_trade(deepcopy(source),legs(),date='2027-01-31'),expected)

    def test_early_rejection_keeps_accepted_custom_thresholds(self):
        rows=[SimpleNamespace(net_value=-12,accepted=True,decision_reasons=[],decision='accept',perspective_team_id=t) for t in ('a','b')]
        with patch.object(tx,'trade_team_flows',return_value=[('a',[],[]),('b',[],[])]), \
             patch.object(tx,'evaluate_trade_for_team',side_effect=rows) as evaluate:
            result=tx.evaluate_trade_participants({},None,{'status':'legal'},1,{},early_reject=True)
        self.assertEqual(result,rows);self.assertEqual(evaluate.call_count,2)

    def test_aggregation_uses_actual_guaranteed_matching_credit(self):
        for amount,expected in ((7_500_000,'legal'),(7_500_000.01,'repairable')):
            source=self.basic();tax=tx.cap_lines_for_season('2026-27')['tax_line']
            source['players'] += [{'id':'extra','name':'extra','team_id':'a'},{'id':'filler','name':'filler','team_id':'a'}]
            source['contracts'] += [{'player_id':'extra','_active_season':'2026-27','seasons':[{'season':'2026-27','salary':10_000_000,'guaranteed_salary':1_000_000}]},
                {'player_id':'filler','_active_season':'2026-27','seasons':[{'season':'2026-27','salary':tax+10_000_000-15_000_000}]}]
            source['contracts'][0]['seasons'][0]['guaranteed_salary']=1_000_000
            source['contracts'][1]['seasons'][0]['salary']=amount
            intent=TradeSearchIntent('a','b',({'kind':'player','id':'out'},{'kind':'player','id':'extra'}),'2027-02-03',{'salary_matching':{'minimum_roster':0}})
            context=tx.trade_search_context(source)
            self.assertEqual(tx.package_matching_credit(context,list(intent.target_assets)),2_000_000)
            self.assertEqual(classify_movements(context,intent,[{'kind':'player','id':'in'}]).category,expected)

    def test_permitted_unresolved_policy_still_requires_participant_approval(self):
        source=tx.with_transaction_context(fixture());source['contracts'][0]['seasons'][0]['salary']=None
        config=tx.default_transaction_model_config();config['decision']['manual_review_blocks_execution']=False
        with patch.object(tx,'evaluate_trade_participants',side_effect=RuntimeError('approval reached')):
            with self.assertRaisesRegex(RuntimeError,'approval reached'):
                tx.evaluate_trade_decision(source,'A','B',[{'kind':'player','value':'a0'}],[{'kind':'player','value':'b0'}],
                    context_ready=True,config=config,search_only=True)

    def test_repair_only_groups_do_not_compile_unused_protection_or_swap_grants(self):
        source=tx.trade_search_context(tx.with_transaction_context(fixture()))
        intent=TradeSearchIntent('a','b',({'kind':'player','id':'a0'},),'2027-01-31')
        repairs=[]
        with patch.object(tx,'trade_salary_legality',return_value={'status':'illegal','issues':['B would move above the hard-cap/apron guardrail.'],'manual_review':[]}), \
             patch.object(tx,'ai_pick_protection_options',side_effect=AssertionError('Unused protection expanded')), \
             patch.object(tx,'ai_pick_swap_grant_options',side_effect=AssertionError('Unused swap expanded')):
            direct=tx.buyer_offer_packages_for_value(source,source['teams'][1],source['teams'][0],90,10_000_000,1,
                max_results=12,return_options=True,allow_new_pick_swaps=True,intent=intent,repair_options=repairs)
        self.assertEqual(direct,[])
        self.assertTrue(repairs)
        self.assertLessEqual(len(repairs),12)

    def test_fact_and_movement_tables_evict_without_changing_answers(self):
        from nba_gm_data.trade_finance_search import financial_fact
        source=tx.trade_search_context(self.basic())
        intent=TradeSearchIntent('a','b',({'kind':'player','id':'out'},),'2027-02-03',{'salary_matching':{'minimum_roster':0}})
        expected=classify_movements(source,intent,[{'kind':'player','id':'in'}])
        for i in range(260):financial_fact(source,('probe',i),lambda:i)
        self.assertLessEqual(len(source['_trade_financial_facts']),256)
        for i in range(2100):classify_movements(source,intent,[{'kind':'player','id':str(i)}])
        self.assertLessEqual(len(source['_trade_movement_classes']),2048)
        self.assertEqual(classify_movements(source,intent,[{'kind':'player','id':'in'}]),expected)

    def test_settlement_does_not_use_stale_search_payroll_facts(self):
        source,saved=salary.TradeSalaryBoundaryTests().fixture()
        context=tx.trade_search_context(source)
        self.assertEqual(tx.team_current_salary_total(context,'b'),22_000_000)
        saved['contract_overrides']['teammate']={'team_id':'b','seasons':[{'season':'2026-27','salary':500_000_000}]}
        before=deepcopy(saved)
        result=tx.apply_trade_to_state(saved,'salary',canonical=context)
        self.assertEqual(result['status'],'not_applied_salary_legality')
        self.assertEqual(saved,before)

    def test_duplicate_player_names_keep_actual_contract_flows(self):
        source=fixture();source['players'][14]['name']=source['players'][13]['name']='Duplicate Name'
        source['contracts'][14]['seasons'][0]['salary']=100_000_000
        source=tx.trade_search_context(tx.with_transaction_context(source))
        intent=TradeSearchIntent('a','b',({'kind':'player','id':'a0'},),'2027-01-31')
        options=tx.buyer_offer_packages_for_value(source,source['teams'][1],source['teams'][0],90,10_000_000,1,
            max_results=128,max_player_options=9,return_options=True,intent=intent,
            excluded_player_ids={p['id'] for p in source['players'] if p['team_id']=='b' and p['id'] not in ('b0','b1')})
        self.assertTrue(any(a['value']=='b0' for o in options for a in o['assets']))
        from nba_gm_data.trade_finance_search import fast_normalize
        for option in options:
            normalized=fast_normalize(source,'b',option['assets'])
            movement=classify_movements(source,intent,normalized)
            self.assertEqual(movement.category,'legal')
            for spec,asset in zip(option['assets'],normalized):
                if spec['kind']=='player':self.assertEqual(asset['id'],tx.resolve_player(source,spec['value'],team_id='b')['id'])
