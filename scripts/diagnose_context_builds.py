"""Attribute actual context builds and capture bounded replayable input snapshots."""
from collections import Counter
from contextlib import ExitStack
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import runpy
import sys
import time
from unittest.mock import patch
from nba_gm_data import transactions as tx, save, team_planning as planning

output = Path(sys.argv[sys.argv.index('--output') + 1])
inputs = output.parent / (output.name + '-inputs')
inputs.mkdir(parents=True, exist_ok=False)
records, active, loose = [], [], []
derived = {'front_office_profiles', 'player_asset_valuations', 'team_strategic_states', 'trade_block_entries'}


class Observed(dict):
    def __init__(self, value, record):
        super().__init__(value)
        self.record = record

    def get(self, key, default=None):
        if key in derived:
            self.record['observed_reads'][key] += 1
        return super().get(key, default)

    def __getitem__(self, key):
        if key in derived:
            self.record['observed_reads'][key] += 1
        return super().__getitem__(key)


with ExitStack() as patches:
    builder, attach = tx.build_transaction_context, tx.with_transaction_context

    def building(canonical, *a, **kw):
        assert len(records) < 24
        state = {k: v for k, v in canonical.items() if not k.startswith('_') or
                 k in ('_human_team_ids', '_trade_planning_save', '_strategy_model_version')}
        payload = json.dumps(state, sort_keys=True, separators=(',', ':')).encode()
        fingerprint = hashlib.sha256(payload).hexdigest()
        path = inputs / (fingerprint + '.json.gz')
        if not path.exists():
            with gzip.open(path, 'wb') as stream:
                stream.write(payload)
        del payload, state
        frames = inspect.stack(context=0)
        callers = [f'{Path(f.filename).name}:{f.function}:{f.lineno}' for f in frames[1:10]]
        del frames
        record = {'number': len(records)+1, 'callers': callers, 'input_sha256': fingerprint,
                  'input_path': str(path), 'components_seconds': Counter(), 'component_calls': Counter(),
                  'observed_reads': Counter(), 'requested': kw}
        records.append(record)
        active.append(record)
        started = time.perf_counter()
        try:
            result = builder(canonical, *a, **kw)
        finally:
            active.pop()
            record['build_seconds'] = time.perf_counter()-started
        record['outputs'] = {k: len(v) if isinstance(v, list) else str(v)[:80] for k, v in result.items()}
        return result

    def attaching(*a, **kw):
        before = len(records)
        result = attach(*a, **kw)
        return Observed(result, records[-1]) if len(records) > before else result
    patches.enter_context(patch.object(tx, 'build_transaction_context', building))
    patches.enter_context(patch.object(tx, 'with_transaction_context', attaching))
    for module, name in ((tx, 'build_player_asset_valuations'), (tx, 'build_team_strategic_states'),
                         (tx, 'build_trade_block_entries'), (tx, 'team_needs_and_excesses'),
                         (planning, 'window_assessments'), (save, 'canonical_with_save'),
                         (save, '_copy_runtime_tree')):
        original = getattr(module, name)

        def measured(*a, __original=original, __name=name, **kw):
            started = time.perf_counter()
            try:
                return __original(*a, **kw)
            finally:
                seconds = time.perf_counter()-started
                if active:
                    active[-1]['components_seconds'][__name] += seconds
                    active[-1]['component_calls'][__name] += 1
                elif __name in ('canonical_with_save', '_copy_runtime_tree'):
                    caller = inspect.currentframe().f_back.f_code.co_name
                    loose.append({'function': __name, 'caller': caller, 'seconds': seconds})
        patches.enter_context(patch.object(module, name, measured))
    runpy.run_path(str(Path(__file__).with_name('benchmark_advance_speed.py')), run_name='__main__')
(output / 'context-builds.json').write_text(json.dumps({'builds': records, 'overlay_and_copy': loose}, indent=2)+'\n')
print(json.dumps({'builds': len(records), 'build_seconds': [r['build_seconds'] for r in records]}))
