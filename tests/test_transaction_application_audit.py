"""Regression cases for consent and failure atomicity at the application boundary."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from nba_gm_data.contract_ai import apply_contract_to_save, apply_contract_to_save_state
from nba_gm_data.transactions import apply_trade_to_save, apply_trade_to_state
from nba_gm_data.save import load_save, write_save
from nba_gm_data.history_store import SaveValidationError


def contract(kind='extension'):
    offer={'id':'o','player_id':'p','team_id':'team_a','annual_salary':8_000_000,'years':2,'status':'accepted'}
    return {'negotiation':{'id':'n','player_id':'p','team_id':'team_a','negotiation_type':kind,'status':'agreement','offers':[offer],
                           'current_contract_seasons':[{'season':'2026-27','salary':5_000_000}]},
            'decision':{'accepted':True,'accepted_offer':offer},'accepted':True}


def league(pending):
    return {'version':'league_save_v1','meta':{'user_team_id':'team_z'},'pending_contract_negotiations':[pending],
            'roster_overrides':{},'contract_overrides':{},'free_agent_player_ids':[], 'transaction_logs':[]}


def trade():
    return {'proposal':{'id':'t','from_team_id':'team_a','to_team_id':'team_b',
                        'from_assets':[{'kind':'player','id':'p','label':'Player'}],'to_assets':[]},
            'accepted_by_all':True,'legality':{'status':'legal'},'evaluations':[]}


def payroll_canonical():
    """Known payroll for the synthetic player used by successful trade fixtures."""
    return {'meta':{},'teams':[{'id':'team_a','abbrev':'A'},{'id':'team_b','abbrev':'B'}],
            'players':[{'id':'p','name':'Player','team_id':'team_a','team_abbrev':'A','position':'G',
                        'age':25,'minutes_projection':18}],
            'contracts':[{'player_id':'p','team_id':'team_a','seasons':[{'season':'2026-27','salary':5_000_000}]}],
            'draft_picks':[],'traits':[]}


class ContractApplicationAuditTests(unittest.TestCase):
    def assert_blocked_unchanged(self, save):
        save['contract_overrides'].setdefault('p', {'annual_salary':5_000_000,'years':1})
        before=deepcopy(save)
        self.assertEqual(apply_contract_to_save_state(save,'n','2026-10-01')['status'],'not_applied')
        self.assertEqual(save,before)

    def test_ineligible_negotiation_cannot_erase_contract(self):
        n=contract();n['decision']=None;n['accepted']=False;n['negotiation'].update(status='not_in_extension_window',offers=[])
        s=league(n);s['contract_overrides']['p']={'annual_salary':5_000_000,'years':1}
        self.assert_blocked_unchanged(s)

    def test_opening_offer_is_not_consent(self):
        n=contract();n.pop('decision');n.pop('accepted');n['negotiation']['status']='no_agreement';n['negotiation']['offers'][0]['status']='opening_offer'
        self.assert_blocked_unchanged(league(n))

    def test_accepted_decision_without_offer_cannot_fall_back_to_counter(self):
        n=contract();n['decision']['accepted_offer']=None
        self.assert_blocked_unchanged(league(n))

    def test_explicit_rejection_wins_over_offer_label(self):
        n=contract();n['decision']['accepted']=False
        self.assert_blocked_unchanged(league(n))

    def test_invalid_terms_and_mismatched_identity(self):
        for field,value in [('annual_salary',0),('annual_salary',float('nan')),('annual_salary',float('inf')),
                            ('years',0),('years',1.5),('years',6),('team_id','team_b'),('player_id','another')]:
            with self.subTest(field=field,value=value):
                n=contract();n['decision']['accepted_offer'][field]=value
                self.assert_blocked_unchanged(league(n))

    def test_stale_extension_cannot_follow_player_to_new_team(self):
        s=league(contract());s['roster_overrides']['p']='team_b';self.assert_blocked_unchanged(s)

    def test_retired_or_departed_player_cannot_sign(self):
        for field in ['retired_player_ids','league_exit_player_ids']:
            s=league(contract());s[field]=['p'];self.assert_blocked_unchanged(s)

    def test_two_accepted_offers_cannot_sign_same_free_agent_twice(self):
        n=contract('free_agent_signing');second=deepcopy(n);second['negotiation']['id']='n2';second['negotiation']['team_id']='team_b'
        second['decision']['accepted_offer']['team_id']='team_b'
        s=league(n);s['free_agent_player_ids']=['p'];s['roster_overrides']['p']=None;s['pending_contract_negotiations'].append(second)
        self.assertEqual(apply_contract_to_save_state(s,'n','2026-10-01')['status'],'applied')
        before=deepcopy(s)
        self.assertEqual(apply_contract_to_save_state(s,'n2','2026-10-01')['status'],'not_applied')
        self.assertEqual(s,before)
        self.assertEqual(s['roster_overrides']['p'],'team_a')

    def test_success_keeps_existing_season_and_replayed_agreement_fails(self):
        n=contract();s=league(n)
        self.assertEqual(apply_contract_to_save_state(s,'n','2026-10-01')['status'],'applied')
        self.assertEqual(s['contract_overrides']['p']['seasons'][0]['salary'],5_000_000)
        s['pending_contract_negotiations']=[n];self.assert_blocked_unchanged(s)

    def test_explicit_legacy_agreement_still_applies(self):
        n=contract();n.pop('decision')
        self.assertEqual(apply_contract_to_save_state(league(n),'n','2026-10-01')['status'],'applied')

    def test_failed_file_application_preserves_bytes_and_creates_no_file(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';n=contract();n['decision']=None;n['negotiation']['status']='no_agreement'
            path.write_text(json.dumps(league(n)));before=path.read_bytes()
            self.assertEqual(apply_contract_to_save(path,'n')['status'],'not_applied');self.assertEqual(path.read_bytes(),before)
            absent=Path(td)/'absent.json';self.assertEqual(apply_contract_to_save(absent,'n')['status'],'not_found');self.assertFalse(absent.exists())


class TradeFailureAtomicityTests(unittest.TestCase):
    def test_stale_assets_leave_all_offers_and_ledgers_unchanged(self):
        for field,assets,value in [('roster_overrides',[{'kind':'player','id':'p'}],'team_c'),
                                   ('roster_overrides',[{'kind':'player','id':'p'}],None),
                                   ('draft_pick_overrides',[{'kind':'pick','id':'p'}],'team_c')]:
            with self.subTest(field=field):
                n=trade();n['proposal']['from_assets']=assets
                s={'version':'league_save_v1','pending_trade_proposals':[n],'user_trade_offers':[deepcopy(n)],field:{'p':value}}
                before=deepcopy(s)
                self.assertEqual(apply_trade_to_state(s,'t')['status'],'not_applied_stale_assets');self.assertEqual(s,before)

    def test_rejected_missing_and_stale_file_apply_do_not_rewrite(self):
        with tempfile.TemporaryDirectory() as td:
            for mode in ['rejected','missing','stale']:
                with self.subTest(mode=mode):
                    n=trade();s={'version':'league_save_v1','pending_trade_proposals':[n]}
                    if mode=='rejected':n['accepted_by_all']=False
                    if mode=='missing':s['pending_trade_proposals']=[]
                    if mode=='stale':s['roster_overrides']={'p':'team_c'}
                    path=Path(td)/f'{mode}.json';path.write_text(json.dumps(s));before=path.read_bytes();mtime=path.stat().st_mtime_ns
                    self.assertNotEqual(apply_trade_to_save(path,'t')['status'],'applied')
                    self.assertEqual(path.read_bytes(),before);self.assertEqual(path.stat().st_mtime_ns,mtime)
            absent=Path(td)/'absent.json';apply_trade_to_save(absent,'t');self.assertFalse(absent.exists())

    def test_success_still_prunes_competing_offers(self):
        n=trade();other=deepcopy(n);other['proposal']['id']='other';other['offer_context']={'status':'pending_user_review'}
        s={'version':'league_save_v1','meta':{'user_team_id':'team_z'},'pending_trade_proposals':[n,other],'user_trade_offers':[deepcopy(other)]}
        self.assertEqual(apply_trade_to_state(s,'t',canonical=payroll_canonical())['status'],'applied')
        self.assertEqual(s['roster_overrides']['p'],'team_b');self.assertEqual(s['pending_trade_proposals'],[])
        self.assertEqual(s['user_trade_offers'][0]['offer_context']['status'],'stale_asset_moved')
        before=deepcopy(s);self.assertEqual(apply_trade_to_state(s,'t')['status'],'not_found');self.assertEqual(s,before)


class TransactionPersistenceAuditTests(unittest.TestCase):
    def test_valid_contracts_persist_and_replay_is_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            for kind in ['extension','free_agent_signing']:
                with self.subTest(kind=kind):
                    path=Path(td)/f'{kind}.json';s=league(contract(kind))
                    if kind=='free_agent_signing':
                        s['free_agent_player_ids']=['p'];s['roster_overrides']['p']=None
                    write_save(path,s)
                    self.assertEqual(apply_contract_to_save(path,'n','2026-10-01')['status'],'applied')
                    saved=load_save(path,include_history=True)
                    if kind=='extension':
                        self.assertEqual(saved['contract_overrides']['p']['seasons'][0]['salary'],5_000_000)
                    else:
                        self.assertEqual(saved['roster_overrides']['p'],'team_a')
                        self.assertNotIn('p',saved['free_agent_player_ids'])
                    self.assertEqual(saved['contract_overrides']['p']['annual_salary'],8_000_000)
                    self.assertEqual(len(saved['transaction_logs']),1)
                    self.assertEqual(saved['pending_contract_negotiations'],[])
                    before=path.read_bytes()
                    self.assertEqual(apply_contract_to_save(path,'n','2026-10-01')['status'],'not_found')
                    self.assertEqual(path.read_bytes(),before)

    def test_valid_trade_persists_player_and_pick_ownership_and_replay_is_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';n=trade()
            n['proposal']['to_assets']=[{'kind':'pick','id':'pick_b','label':'Future pick'}]
            s=league(contract());s['pending_contract_negotiations']=[]
            s.update(pending_trade_proposals=[n],roster_overrides={'p':'team_a'},draft_pick_overrides={'pick_b':'team_b'})
            write_save(path,s)
            self.assertEqual(apply_trade_to_save(path,'t','2026-10-01',canonical=payroll_canonical())['status'],'applied')
            saved=load_save(path,include_history=True)
            self.assertEqual(saved['roster_overrides']['p'],'team_b')
            self.assertEqual(saved['draft_pick_overrides']['pick_b'],'team_a')
            self.assertEqual(len(saved['transaction_logs']),1)
            self.assertEqual(saved['pending_trade_proposals'],[])
            before=path.read_bytes()
            self.assertEqual(apply_trade_to_save(path,'t','2026-10-01')['status'],'not_found')
            self.assertEqual(path.read_bytes(),before)

    def test_stale_save_object_is_still_rejected_without_rewriting(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'save.json';write_save(path,league(contract()))
            stale=load_save(path);fresh=load_save(path)
            fresh['pending_contract_negotiations']=[];write_save(path,fresh)
            before=path.read_bytes()
            with self.assertRaisesRegex(SaveValidationError,'changed while it was open'):
                write_save(path,stale)
            self.assertEqual(path.read_bytes(),before)
