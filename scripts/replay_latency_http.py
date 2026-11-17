"""Separate HTTP attribution replays; never use hashing runs as wall-time results."""
import argparse,base64,json,time,urllib.request
from pathlib import Path
from nba_gm_data.save import load_save
from verify_simulation_consistency import business_state,digest

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--url',default='http://127.0.0.1:8793')
p.add_argument('--output',type=Path,required=True)
p.add_argument('--cases',type=Path,default=Path('output/end-to-end-latency/cases.json'))
p.add_argument('--names',default='busy,month')
args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
cases=json.loads(args.cases.read_text())
token=json.load(urllib.request.urlopen(args.url+'/api/session'))['token']
headers={'Content-Type':'application/json','Origin':args.url,'X-NBA-GM-Token':token,'X-NBA-GM-Backup-Upload':'1'}

def request(path,payload):
    return urllib.request.urlopen(urllib.request.Request(args.url+path,json.dumps(payload).encode(),headers),timeout=180)

for index,name in enumerate(args.names.split(',')):
    c=cases[name]
    with request('/api/action',{'action':'restore_save','payload':{
        'archive_base64':base64.b64encode(Path(c['archive']).read_bytes()).decode(),
        'save_name':f'latency_diag_{time.time_ns()}_{name}'}}) as r:
        restored=json.load(r)['result']
    path=restored['save_path'];seed=load_save(path)['meta']['seed']
    events=[];start=time.perf_counter();epoch=time.time();result=None
    ident=f'diag-{name}-{index}'
    with request('/api/action/stream',{'action':'advance_save','simulation_id':ident,
        'payload':{'save_path':path,'to_date':c['target'],'seed':seed,'checkpoint_days':31}}) as r:
        for line in r:
            message=json.loads(line)
            if message['type']=='progress':events.append({'at':time.perf_counter()-start,'digest':digest(message['event']),'kind':message['event']['kind']})
            elif message['type']=='result':result=message['result'];received=time.perf_counter()-start
            else:raise RuntimeError(message)
    assert result and result['home']['save']['current_date']==c['target']
    report={'case':name,'simulation_id':ident,'epoch_start':epoch,'seconds':received,'save_path':path,
            'state_digest':digest(business_state(load_save(path,include_history=True))),
            'progress':events,'progress_digest':digest([e['digest'] for e in events if e['kind']!='start'])}
    (args.output/(ident+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('progress',)}),flush=True)
