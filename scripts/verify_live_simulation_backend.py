"""Compare real streamed/direct actions and an interrupted display on isolated saves."""
import http.client
import json
from pathlib import Path
import time
import urllib.request
from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save import load_save
from nba_gm_data.save_recovery import restore_export
from verify_simulation_consistency import business_state, digest

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/live-simulation-2026-10-24'


def main():
    directory=OUT/'saves'
    archive=(ROOT/'output/memphis-rotation-fix-2026-10-24/controlled-input.nbagm.zip').read_bytes()
    paths={mode:directory/f'{mode}-{time.time_ns()}.json' for mode in ('streamed','direct','disconnected')}
    for target in paths.values():
        restore_export(target,archive)
    canonical=load_app_canonical(ROOT)
    token=json.load(urllib.request.urlopen('http://127.0.0.1:8777/api/session'))['token']
    headers={'Content-Type':'application/json','X-NBA-GM-Token':token}
    payload={'save_path':str(paths['streamed']),'days':3}
    request=urllib.request.Request('http://127.0.0.1:8777/api/action/stream',data=json.dumps({'action':'advance_save','payload':payload}).encode(),headers=headers)
    events=[]
    with urllib.request.urlopen(request,timeout=120) as response:
        for line in response:
            message=json.loads(line)
            if message['type']=='progress': events.append(message['event'])
            elif message['type']=='error': raise RuntimeError(message['error'])
            elif message['type']=='result': streamed_result=message['result']
    direct=dispatch_app_action('advance_save',{'save_path':str(paths['direct']),'days':3},root=ROOT,save_dir=directory,canonical=canonical)
    a=business_state(load_save(paths['streamed']))
    b=business_state(load_save(paths['direct']))
    assert a==b,'Streaming changed meaningful league state.'
    dates=[event['date'] for event in events if event.get('kind')=='date']
    assert set(('2027-01-31','2027-02-01','2027-02-02')).issubset(dates)
    assert dates==sorted(dates)
    connection=http.client.HTTPConnection('127.0.0.1',8777,timeout=120)
    body=json.dumps({'action':'advance_save','payload':{'save_path':str(paths['disconnected']),'days':1}})
    connection.request('POST','/api/action/stream',body=body,headers=headers)
    response=connection.getresponse()
    assert json.loads(response.readline())['type']=='progress'
    response.close(); connection.close()
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        if load_save(paths['disconnected'])['state']['current_date']=='2027-01-31': break
        time.sleep(.2)
    else: raise AssertionError('Closing the display prevented the simulation from committing.')
    report={'streamed_direct_equal':True,'business_digest':digest(a),
            'dates':dates,'game_events':sum(e.get('kind')=='game' for e in events),
            'through':direct['home']['save']['current_date'],'disconnect_committed':True}
    (OUT/'engine-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
