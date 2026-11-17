"""Isolated HTTP latency observer. Monkeypatches live only in this process."""
import argparse
from collections import Counter
from contextvars import ContextVar
from contextlib import contextmanager
import functools
import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil
import sys
import time
import traceback

from nba_gm_data import app_actions as aa, app_server as http, save, transactions as tx, history_store

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--port', type=int, default=8792)
parser.add_argument('--wall-only', action='store_true', help='Disable attribution wrappers for browser wall-time controls.')
parser.add_argument('--gui-snapshot', type=Path, help='Serve an existing frozen GUI copy.')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
base = args.output.resolve(); base.mkdir(parents=True, exist_ok=True)
saves = base/'saves'; saves.mkdir(exist_ok=True)
assert not list(saves.glob('*.json')), 'Use a new isolated directory'
gui = args.gui_snapshot.resolve() if args.gui_snapshot else base/'gui'
if not gui.exists():
    def copy(source, target):
        if Path(source).suffix in ('.js','.css','.html'):
            return shutil.copy2(source,target)
        os.link(source,target)
        return target
    shutil.copytree(http.GUI_DIR,gui,copy_function=copy)
http.GUI_DIR = gui
current = ContextVar('latency_observer', default=None)


class Trace:
    def __init__(self, ident):
        self.ident=ident; self.start=time.perf_counter(); self.epoch=time.time()
        self.phase='load_materialize_overlay'; self.last=self.start; self.times=Counter()
        self.spans=[]; self.events=[]; self.marks={}; self.overlays=[]
        self.hash_inputs=ident.startswith('diag-')
        self.source_shapes={}
    def tick(self):
        now=time.perf_counter(); self.times[self.phase]+=now-self.last; self.last=now
    @contextmanager
    def owner(self, phase):
        self.tick(); old=self.phase; self.phase=phase
        try:yield
        finally:self.tick(); self.phase=old
    def mark(self,name):self.marks[name]=time.perf_counter()-self.start


def install(original, wrapped):
    # Replace existing import aliases, including app_actions' from-save seams.
    for module in list(sys.modules.values()):
        if module is not None and getattr(module,'__name__','').startswith('nba_gm_data'):
            for name,value in list(vars(module).items()):
                if value is original:setattr(module,name,wrapped)


def observe(module,name,phase=None,mark=None):
    if args.wall_only:return
    original=getattr(module,name)
    @functools.wraps(original)
    def call(*a,**kw):
        trace=current.get()
        if trace is None:return original(*a,**kw)
        if name=='canonical_with_save':
            item={'at':time.perf_counter()-trace.start,'owner':trace.phase,'source_id':id(a[0]),'save_id':id(a[1]),
                  'date':a[1].get('state',{}).get('current_date')}
            if trace.hash_inputs:
                with trace.owner('diagnostic_overhead'):
                    public={k:v for k,v in a[0].items() if not k.startswith('_')}
                    encoded=pickle.dumps((public,a[1]),protocol=5)
                    item['complete_input_sha256']=hashlib.sha256(encoded).hexdigest()
                    item['serialized_input_bytes']=len(encoded)
                    item['callers']=[f'{Path(s.filename).name}:{s.name}:{s.lineno}' for s in traceback.extract_stack(limit=7)[:-1]]
                    if str(id(a[0])) not in trace.source_shapes:
                        trace.source_shapes[str(id(a[0]))]={k:{'serialized_bytes':len(pickle.dumps(v,protocol=5)),
                            'items':len(v) if isinstance(v,(dict,list,tuple)) else None} for k,v in public.items()}
            trace.overlays.append(item)
        start=time.perf_counter(); owner=trace.phase
        if phase:
            with trace.owner(phase):result=original(*a,**kw)
        else:result=original(*a,**kw)
        end=time.perf_counter()
        trace.spans.append({'name':name,'owner':owner,'start':start-trace.start,'end':end-trace.start})
        if mark:trace.mark(mark)
        return result
    install(original,call)


# Owner phases are exclusive. Overlay/materialization inside a market,
# settlement or dashboard belongs to that owner; nested spans expose its cost.
observe(aa,'advance_action')
observe(save,'advance_save','lifecycle_games', 'advance_return')
observe(save,'advance_save_day','lifecycle_games','last_day_compute_complete')
observe(save,'queue_ai_recommendations','market_search')
observe(save,'process_ai_actions_in_memory','transaction_settlement')
observe(save,'write_save','persistence')
observe(aa,'dashboard_snapshot_payload','response_dashboard')
for module,names in ((save,('load_save','canonical_with_save','refresh_active_runtime_state','_copy_runtime_tree',
                           'advance_lifecycle_to','simulation_live_card_progress','sim_game_with_context')),
                     (tx,('build_transaction_context','simulate_ai_trades','apply_trade_to_state')),
                     (history_store,('hydrate_save_history','archive_save_history')),
                     (aa,('normalized_read_save',))):
    for name in names:observe(module,name)
from nba_gm_data import sim
for name in ('load_sim_context','build_sim_indices','load_reference_json'):
    observe(sim,name)
for name in ('simulate_health','refresh_team_plans','process_development_months','reassess_ai_roles'):
    if hasattr(save,name):observe(save,name)

original_dispatch=http.dispatch_app_action
def dispatch(action,*a,**kw):
    trace=current.get()
    if trace and action=='advance_save':trace.mark('dispatch_start')
    result=original_dispatch(action,*a,**kw)
    if trace and action=='advance_save':
        trace.mark('backend_result_prepared')
        trace.tick()
        trace.phase='response_dashboard'
        trace.result={'status':result.get('status'),'through':(result.get('result') or {}).get('through_date'),
                      'games':(result.get('result') or {}).get('games_simulated')}
    return result
http.dispatch_app_action=dispatch


class Writer:
    def __init__(self, target, trace):self.target=target; self.trace=trace
    def __getattr__(self,name):return getattr(self.target,name)
    def write(self,data):
        trace=self.trace
        if data.startswith(b'{"type": "progress"'):
            message=json.loads(data);e=message['event']
            trace.events.append({'at':time.perf_counter()-trace.start,'kind':e.get('kind'),
                                 'date':e.get('date'),'game_id':(e.get('game') or {}).get('game_id'), 'bytes':len(data)})
        elif data.startswith(b'{"type": "result"'):
            trace.mark('result_serialized_write_start');trace.result_bytes=len(data)
        with trace.owner('stream_transport'):return self.target.write(data)
    def flush(self):
        with self.trace.owner('stream_transport'):return self.target.flush()


original_stream=http.GuiRequestHandler.stream_simulation
def streaming(self,payload,ident):
    if args.wall_only:return original_stream(self,payload,ident)
    trace=Trace(str(ident)); token=current.set(trace); target=self.wfile
    self.wfile=Writer(target,trace)
    try:return original_stream(self,payload,ident)
    finally:
        trace.tick();trace.mark('stream_handler_complete');self.wfile=target;current.reset(token)
        report={'simulation_id':ident,'epoch_start':trace.epoch,'exclusive_phases_seconds':dict(trace.times),
                'marks':trace.marks,'progress':trace.events,'nested_spans':trace.spans,'overlays':trace.overlays,
                'result':getattr(trace,'result',{}),'result_bytes':getattr(trace,'result_bytes',0),
                'hash_inputs_diagnostic':trace.hash_inputs}
        report['source_shapes']=trace.source_shapes
        (base/(str(ident)+'.json')).write_text(json.dumps(report,indent=2)+'\n')
http.GuiRequestHandler.stream_simulation=streaming
server=http.make_gui_server(root=root,save_dir=saves,port=args.port)
(base/'server.json').write_text(json.dumps({'pid':os.getpid(),'url':f'http://127.0.0.1:{args.port}/','save_dir':str(saves),
    'wall_only':args.wall_only,'backend_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'src/nba_gm_data').glob('*.py')},
    'gui_snapshot':str(gui),'gui_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in gui.iterdir() if p.suffix in ('.js','.css','.html')}},indent=2))
print(f'Isolated diagnostic server http://127.0.0.1:{args.port}/',flush=True)
try:server.serve_forever()
finally:server.server_close()
