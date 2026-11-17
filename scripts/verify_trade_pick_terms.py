"""Exercise the real app actions against disposable protected/swap careers."""
import json
from pathlib import Path
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/trade-pick-terms-2026-10-25'
BASE='http://127.0.0.1:8777'


def main():
    token=json.load(urllib.request.urlopen(BASE+'/api/session'))['token']
    def action(name,payload):
        request=urllib.request.Request(BASE+'/api/action',data=json.dumps({'action':name,'payload':payload}).encode(),
            headers={'Content-Type':'application/json','X-NBA-GM-Token':token})
        try:
            with urllib.request.urlopen(request,timeout=180) as response: result=json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read().decode()) from error
        assert result['ok'],result
        return result['result']
    report={}
    for mode in ('protected','swap'):
        path=OUT/'saves'/f'{mode}.json'
        payload={'save_path':str(path)}
        own=action('team_assets',{**payload,'team':'MEM'})
        other=action('team_assets',{**payload,'team':'ATL'})
        available=[p for p in own['picks'] if p.get('terms_editable') and int(p['round'])==2]
        if mode=='protected':
            primary=next(p for p in available if any(int(f['season'])>int(p['season']) for f in available))
            fallback=next(p for p in available if int(p['season'])>int(primary['season']))
            rule={'pick_id':primary['id'],'type':'protected_pick','from':31,'through':35,'fallback_pick_ids':[fallback['id']]}
        else:
            primary,counter=next((a,b) for a in available for b in other['picks'] if b.get('terms_editable')
                                 and str(a['season'])==str(b['season']) and int(b['round'])==2)
            rule={'pick_id':primary['id'],'type':'pick_swap','other_pick_id':counter['id'],'benefit':'better'}
        request={**payload,'from_team':'MEM','to_team':'ATL','from_assets':[{'kind':'pick','value':primary['id']}],
                 'to_assets':[],'pick_rules':[rule],'seed':7}
        candidate=action('evaluate_trade',request)
        assert candidate.get('pick_obligation_terms'),candidate
        assert candidate['legality']['status']=='legal',candidate['legality']
        assert any(e.get('accepted') and e['perspective_team_id']!=own['team']['id'] for e in candidate['evaluations']),candidate['evaluations']
        if mode=='protected':
            # Exact terms must survive a league-wide search, not only builder evaluation.
            found=action('find_trade_for_assets',{**payload,'seller_team':'MEM','for_team':'MEM','buyer_team':'ATL',
                         'assets':[{'kind':'pick','value':primary['id']}],'pick_rules':[rule],'limit':3,'seed':7})
            assert all(c['pick_obligation_terms'][0]['protected_range']=={'from':31,'through':35} for c in found['candidates'])
            report['finder_candidates']=found['candidate_count']
        applied=action('apply_trade_candidate',{**payload,'candidate':candidate,'source':'builder'})
        assert applied['status']=='applied',applied
        saved=json.loads(path.read_text())
        term=next(t for t in saved['pick_obligations'] if t['id']==candidate['pick_obligation_terms'][0]['id'])
        assert term['status']=='active'
        if mode=='protected':
            assert fallback['id'] in saved['locked_pick_assets']
            assert saved['draft_pick_overrides'][primary['id']]==other['team']['id']
        else:
            assert saved['draft_pick_overrides'].get(primary['id'],own['team']['id'])==own['team']['id']
            assert term['current_rights_holder_team_id']==other['team']['id']
        report[mode]={'primary':primary['label'],'rule':rule,'legal':candidate['legality']['status'],
                      'applied':applied['status'],'obligation_type':term['type']}
        print(mode,'evaluated and applied',flush=True)
    (OUT/'engine-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
