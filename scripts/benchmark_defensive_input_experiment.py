"""Short offline candidate timings and separate allocation ownership diagnostic."""
import argparse,hashlib,json,resource,statistics,time,tracemalloc
from pathlib import Path
from experiments.defensive_inputs.model import experiment

ap=argparse.ArgumentParser();ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
ap.add_argument('--rows',type=Path,help='Recorded evaluated source rows after explicit roster physical overlay')
a=ap.parse_args()
rows=json.loads(a.rows.read_text()) if a.rows else json.loads(Path('Player Stats/player_skill_input_2025_26.json').read_text())['players']
reference=json.loads(a.reference.read_text());timings=[]
# No tracing during wall samples; no retained result batches in timings.
for _ in range(7):
 start=time.perf_counter()
 for row in rows:experiment(row,reference)
 timings.append(time.perf_counter()-start)
tracemalloc.start()
batch=[experiment(row,reference) for row in rows]
live,peak=tracemalloc.get_traced_memory();del batch
after,_=tracemalloc.get_traced_memory()
tracemalloc.stop()
result={'scope':f'Offline A+B calculations for {len(rows)} source rows, same frozen reference; not real-action latency or production improvement',
 'evaluated_rows_artifact':str(a.rows) if a.rows else 'original March raw rows',
 'samples_seconds':timings,'median_seconds':statistics.median(timings),'range_seconds':[min(timings),max(timings)],
 'traced_batch_live_bytes':live,'traced_peak_bytes':peak,'after_batch_release_bytes':after,
 'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
 'gc':'No forced GC used','reference_sha256':hashlib.sha256(a.reference.read_bytes()).hexdigest()}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
