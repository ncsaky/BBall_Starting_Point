"""Exact settlement ownership/normalization parity against the full fallback."""
from copy import deepcopy
import gc
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data import save as sv, transactions as tx, trade_roster as tr

ROOT=Path(__file__).resolve().parents[1]
INPUTS=ROOT/'output/settlement-materialization-pass/inputs'


class SettlementMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.load(gzip.open(INPUTS/'canonical.json.gz','rt'))
        cls.cases=[json.load(gzip.open(p,'rt')) for p in sorted(INPUTS.glob('settlement-*.json.gz'))]
        assert len(cls.cases)==5

    def offer(self, saved, case):
        return next(o for o in saved['pending_trade_proposals']
                    if (o.get('proposal') or o)['id']==case['args'][0])

    def pair(self, saved, case=None, source=None):
        case=case or self.cases[0];source=self.source if source is None else source
        old,new=deepcopy(saved),deepcopy(saved)
        expected=tx.apply_trade_to_state(old,*case['args'],canonical=source,**case['kwargs'],_full_reference=True)
        actual=tx.apply_trade_to_state(new,*case['args'],canonical=source,**case['kwargs'])
        self.assertEqual(actual,expected)
        self.assertEqual(new,old)
        return actual,new

    def test_all_five_real_settlements_protections_swaps_and_exact_saved_effects(self):
        self.assertTrue(self.offer(self.cases[0]['saved'],self.cases[0])['pick_obligation_terms'])
        self.assertTrue(any(t['type']=='pick_swap' for t in self.offer(self.cases[4]['saved'],self.cases[4])['pick_obligation_terms']))
        for case in self.cases:
            with self.subTest(proposal=case['args'][0]):
                with patch.object(sv,'canonical_with_save',wraps=sv.canonical_with_save) as overlay:
                    result,saved=self.pair(case['saved'],case)
                # These are historical inputs, not permanent approval grants.
                # Later model changes may veto an archived offer. pair() must
                # still match the full fresh reference, including every write.
                # TRADE-VOLUME: the trade code now uses the real $200.4M tax line and $221.7M hard cap, so an
                # archived offer may also fail today's salary legality (Minnesota / Phoenix, DiVincenzo).
                self.assertIn(result['status'],('applied','not_applied_roster_plan','not_applied_salary_legality'))
                if result['status']=='applied':
                    self.assertEqual(overlay.call_count,4)  # Three reference + one shared.
                else:
                    self.assertTrue(result['issues'])
                    self.assertEqual(saved,case['saved'])
                    # No entitlement overlay after a roster veto; a salary-legality veto comes before the roster overlay.
                    self.assertEqual(overlay.call_count,2 if result["status"]=="not_applied_salary_legality" else 3)
                self.assertFalse(any(k.startswith('_') for k in saved))

    def test_sequential_settlements_rebuild_after_each_preceding_trade(self):
        old,new=deepcopy(self.cases[0]['saved']),deepcopy(self.cases[0]['saved'])
        created=[];applied=0;kind=tx._BilateralSettlementMaterialization
        def materialize(c,s):
            obj=kind(c,s);created.append(weakref.ref(obj));return obj
        for case in self.cases:
            # The queue inserts each selected proposal immediately before
            # settlement, after preceding transfers have already applied.
            for saved in (old,new):
                if not any((o.get('proposal') or o)['id']==case['args'][0] for o in saved['pending_trade_proposals']):
                    saved['pending_trade_proposals'].append(deepcopy(self.offer(case['saved'],case)))
            before=deepcopy(new)
            expected=tx.apply_trade_to_state(old,*case['args'],canonical=self.source,**case['kwargs'],_full_reference=True)
            with patch.object(tx,'_BilateralSettlementMaterialization',new=materialize):
                actual=tx.apply_trade_to_state(new,*case['args'],canonical=self.source,**case['kwargs'])
            self.assertEqual(actual,expected);self.assertEqual(new,old)
            self.assertIn(actual['status'],('applied','not_applied_roster_plan','not_applied_salary_legality'))
            if actual['status']=='applied':
                applied+=1
            else:
                self.assertTrue(actual['issues'])
                self.assertEqual(new,before)
            self.assertTrue(all(ref() is None for ref in created))
        self.assertEqual(len(created),5)
        self.assertGreaterEqual(applied,2)  # Must exercise sequential successful settlements.
        before=deepcopy(new)
        result=tx.apply_trade_to_state(new,*self.cases[0]['args'],canonical=self.source)
        self.assertEqual(result['status'],'not_found');self.assertEqual(new,before)

    def test_changed_health_contract_ownership_plans_wants_and_human_rotations(self):
        case=self.cases[0];saved=case['saved'];proposal=self.offer(saved,case)['proposal']
        pid=proposal['from_assets'][0]['id'];tid=proposal['from_team_id']
        def injury(s):
            row=next(h for h in s['health_states'] if h['player_id']==pid)
            row.update(availability_status='out',return_date='2027-08-01',days_left=180)
        changes=[injury,
            lambda s:s.setdefault('contract_overrides',{}).update({pid:{'team_id':tid,'seasons':[{'season':'2026-27','salary':500_000_000}]}}),
            lambda s:s.setdefault('contract_overrides',{}).update({pid:{'team_id':tid,'seasons':[{'season':'2026-27','salary':None}]}}),
            lambda s:s.setdefault('roster_overrides',{}).update({pid:'team_gsw'}),
            lambda s:s.setdefault('team_plans',{}).update({tid:{'route':'review_core_ceiling_and_retool_alternatives','review_exception':'serious_core_injury_review'}}),
            lambda s:s.setdefault('team_trade_wants',{}).update({tid:{'revision':83,'entries':[{'id':'want','kind':'picks','round':1}]}}),
            lambda s:s['waived_salary_obligations'].append({'player_id':'dead','team_id':tid,'seasons':[{'season':'2026-27','salary':40_000_000}]}),
            lambda s:s['meta'].update(human_team_ids=[tid]),
            lambda s:s.setdefault('rotation_overrides',{}).update({tid:{pid:42}})]
        for number,change in enumerate(changes):
            with self.subTest(change=number):
                value=deepcopy(saved);change(value);self.pair(value)
        source=deepcopy(self.source)
        outsider=next(t['id'] for t in source['teams'] if t['id'] not in (proposal['from_team_id'],proposal['to_team_id']))
        ids={p['id'] for p in source['players'] if p.get('team_id')==outsider}
        for trait in source['traits']:
            if trait['player_id'] in ids:trait['value']=95
        self.pair(saved,source=source)

    def test_stale_salary_and_roster_rejections_do_not_publish_normalization(self):
        case=self.cases[0];saved=deepcopy(case['saved']);proposal=self.offer(saved,case)['proposal']
        for key in ('rotation_snapshots','rotation_baselines','generated_health_profiles'):saved.pop(key,None)
        with patch.object(tr,'live_roster_issues',return_value=['Fresh roster veto']):
            result,new=self.pair(saved)
        self.assertEqual(result['status'],'not_applied_roster_plan');self.assertEqual(new,saved)
        pid=proposal['from_assets'][0]['id']
        saved['contract_overrides'][pid]={'team_id':proposal['from_team_id'],'seasons':[{'season':'2026-27','salary':None}]}
        result,new=self.pair(saved)
        self.assertEqual(result['status'],'not_applied_salary_legality');self.assertEqual(new,saved)
        saved['roster_overrides'][pid]='team_gsw'
        with patch.object(tx,'_BilateralSettlementMaterialization',side_effect=AssertionError('Stale offer materialized')):
            result,new=self.pair(saved)
        self.assertEqual(result['status'],'not_applied_stale_assets');self.assertEqual(new,saved)

    def test_entitlement_rejection_publishes_only_the_old_normalization_effects(self):
        case=self.cases[0];saved=deepcopy(case['saved']);offer=self.offer(saved,case)
        for key in ('rotation_snapshots','rotation_baselines','generated_health_profiles'):saved.pop(key,None)
        pick=next(a for side in ('from_assets','to_assets') for a in offer['proposal'][side] if a['kind']=='pick')
        pick['nested_entitlement']={'obligation_ids':['stale-entitlement']}
        # Isolate the entitlement check from the live roster check that runs before it: with the real tax line
        # (TRADE-VOLUME) and this test's dropped rotation projections, Cleveland's draft-spending check vetoes first.
        with patch('nba_gm_data.trade_roster.live_roster_issues', return_value=[]):
            result,new=self.pair(saved)
        self.assertEqual(result['status'],'not_applied_stale_assets')
        changed={k for k in saved.keys()|new.keys() if saved.get(k)!=new.get(k)}
        self.assertTrue(changed)
        self.assertTrue(changed<=set(tx._BilateralSettlementMaterialization._NORMALIZATION_FIELDS))

    def test_generated_injured_rookie_normalization_is_private_then_committed_exactly(self):
        case=self.cases[0];saved=deepcopy(case['saved'])
        rookie={**self.source['players'][0],'id':'generated-medical-test','team_id':'team_gsw','medical_profile':{
            'durability':40,'current_injury':{'start_date':'2027-02-01','return_date':'2027-04-01','body_area':'knee'}}}
        saved.setdefault('generated_players',[]).append(rookie)
        for key in ('generated_health_profiles','rotation_snapshots','rotation_baselines'):saved.pop(key,None)
        before=deepcopy(saved);expected_save=deepcopy(saved)
        expected=sv.canonical_with_save(self.source,expected_save)
        owner=tx._BilateralSettlementMaterialization(self.source,saved)
        actual=owner.active();self.assertEqual(saved,before)
        public=lambda c:{k:v for k,v in c.items() if not k.startswith('_')}
        self.assertEqual(public(actual),public(expected))
        all_writes={k for k in before.keys()|expected_save.keys() if k not in before or before.get(k)!=expected_save.get(k)}
        self.assertTrue(all_writes<=set(owner._NORMALIZATION_FIELDS))
        owner.entitlement_active();self.assertEqual(saved,expected_save)
        actual['player_health_states'][0]['rust']=-999
        self.assertEqual(saved,expected_save)

    def test_salary_roster_and_pending_terms_do_not_change_shared_public_inputs(self):
        for case in (self.cases[0],self.cases[4]):
            saved=deepcopy(case['saved']);offer=self.offer(saved,case)
            owner=tx._BilateralSettlementMaterialization(self.source,saved);active=owner.active()
            public=lambda c:{k:deepcopy(v) for k,v in c.items() if not k.startswith('_')}
            before=public(active)
            expected_salary=tx.saved_trade_salary_legality(saved,offer['proposal'],self.source)
            self.assertEqual(tx.saved_trade_salary_legality(saved,offer['proposal'],self.source,_materialization=owner),expected_salary)
            expected_roster=tr.live_roster_issues(self.source,saved,offer['proposal'],candidate=offer)
            self.assertEqual(tr.live_roster_issues(self.source,saved,offer['proposal'],candidate=offer,_materialization=owner),expected_roster)
            self.assertEqual(public(active),before)

    def test_multi_team_application_keeps_the_full_fallback(self):
        saved=deepcopy(self.cases[0]['saved']);offer=self.offer(saved,self.cases[0]);offer['proposal']['transfers']=[{'from_team_id':'a','to_team_id':'b','assets':[]}]
        with patch('nba_gm_data.multi_team_trades.apply_multi_team_trade_to_state',return_value={'status':'multi'}) as full, \
             patch.object(tx,'_BilateralSettlementMaterialization',side_effect=AssertionError('Multi-team reused bilateral snapshot')):
            result=tx.apply_trade_to_state(saved,*self.cases[0]['args'],canonical=self.source)
        self.assertEqual(result,{'status':'multi'});full.assert_called_once()

    def test_pick_only_protected_and_new_swap_settlements_keep_lazy_financial_path(self):
        from test_trade_pick_terms import TradePickTermsTests
        fixture=TradePickTermsTests();fixture.setUp()
        for rule in (fixture.protected,fixture.swap):
            context,assets,terms=fixture.compile(rule)
            offer={'proposal':{'id':'pick-only','date':'2026-10-01','from_team_id':'a','to_team_id':'b',
                'from_assets':[{'kind':a['kind'],'id':a['value']} for a in assets[0]],'to_assets':[]},
                'accepted_by_all':True,'legality':{'status':'legal'},'pick_obligation_terms':terms,'evaluations':[]}
            saved={'version':'league_save_v1','meta':{'season':'2026-27','seed':17,'user_team_id':'a'},
                   'state':{'current_date':'2026-10-01'},'pending_trade_proposals':[offer],
                   'draft_pick_overrides':{p['id']:p['current_owner_team_id'] for p in fixture.data['draft_picks']}}
            with patch.object(tx,'trade_salary_legality',side_effect=AssertionError('Pick-only salary evaluated')):
                result,new=self.pair(saved,{'args':['pick-only'],'kwargs':{'date':'2026-10-01'}},fixture.data)
            self.assertEqual(result['status'],'applied')
            self.assertEqual(new['pick_obligations'][0]['type'],rule['type'])

    def test_materialization_and_trial_graphs_release_after_applied_and_rejected_settlement(self):
        original=tx._BilateralSettlementMaterialization;refs=[]
        def record(*a):
            owner=original(*a);refs.append(weakref.ref(owner));return owner
        for veto in (False,True):
            saved=deepcopy(self.cases[0]['saved'])
            with patch.object(tx,'_BilateralSettlementMaterialization',new=record):
                if veto:
                    with patch.object(tr,'live_roster_issues',new=lambda *a,**kw:['Fresh veto']):
                        result=tx.apply_trade_to_state(saved,*self.cases[0]['args'],canonical=self.source)
                else:result=tx.apply_trade_to_state(saved,*self.cases[0]['args'],canonical=self.source)
            self.assertFalse(any('_materialization' in str(k) for k in result))
            self.assertTrue(all(ref() is None for ref in refs))
        gc.collect();self.assertTrue(all(ref() is None for ref in refs))
