"""Measure a real app advance on an isolated export, optionally with cProfile."""
import argparse
import cProfile
import hashlib
import io
import json
from pathlib import Path
import pstats
import time
from contextlib import ExitStack
from unittest.mock import patch
from collections import Counter

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save import load_save
from nba_gm_data.save_recovery import create_export, restore_export
from verify_simulation_consistency import business_state, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', type=Path, required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--count-trade-presentation', action='store_true',
                        help='Count presentation builders separately from decision work.')
    parser.add_argument('--reference-search', action='store_true', help='Disable only the new per-search memoization.')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new disposable output directory.')
    args.output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    before = hashlib.sha256(args.save.read_bytes()).hexdigest()
    path = args.output/'career.json'
    restore_export(path, create_export(args.save))
    canonical = load_app_canonical(root)
    saved = load_save(path)
    profiler = cProfile.Profile() if args.profile else None
    started = time.perf_counter()
    if profiler:
        profiler.enable()
    from nba_gm_data import transactions as tx, sim
    from nba_gm_data import multi_team_trades as mt
    from nba_gm_data.simulation_progress import progress_listener
    frames, kinds = [], Counter()
    presentation_calls = Counter()

    def count_calls(module, names, stack):
        for name in names:
            original = getattr(module, name)

            def counted(*args, __name=name, __original=original, **kwargs):
                presentation_calls[__name] += 1
                return __original(*args, **kwargs)

            stack.enter_context(patch.object(module, name, side_effect=counted))

    def progress(event):
        frames.append(digest(event))
        kinds[event.get('kind', 'unknown')] += 1
    with ExitStack() as reference:
        reference.enter_context(progress_listener(progress))
        if args.count_trade_presentation:
            count_calls(tx, ('trade_evaluation_payload', 'trade_value_breakdown', 'package_value_breakdown',
                             'candidate_from_evaluation', 'proposal_summary', 'evaluation_notes',
                             'trade_headline_from_payload'), reference)
        if args.reference_search:
            reference.enter_context(patch.object(tx, 'trade_search_context', side_effect=lambda c: c))
            full = sim.team_feature_vector
            reference.enter_context(patch.object(sim, 'team_feature_vector', side_effect=lambda c,t,**kw: full(c,t)))
            candidate = tx.candidate_from_evaluation
            reference.enter_context(patch.object(tx, 'candidate_from_evaluation', side_effect=lambda c,r: candidate(c,
                {key: value for key, value in r.items() if key != 'value_breakdown'})))
        result = dispatch_app_action('advance_save', {'save_path': str(path.resolve()), 'to_date': args.target,
            'seed': saved['meta']['seed'], 'checkpoint_days': 31}, root=root, save_dir=args.output.resolve(), canonical=canonical)
    if profiler:
        profiler.disable()
    seconds = time.perf_counter()-started
    final = business_state(load_save(path, include_history=True))
    (args.output/'business.json').write_text(json.dumps(final, sort_keys=True))
    report = {'seconds': seconds, 'profiled': args.profile, 'reference_search': args.reference_search, 'status': result.get('status'),
        'from': saved['state']['current_date'], 'through': final['state']['current_date'], 'digest': digest(final),
        'source_unchanged': before == hashlib.sha256(args.save.read_bytes()).hexdigest()}
    report.update(progress_digest=digest(frames), progress_frames=len(frames), progress_kinds=dict(kinds))
    if args.count_trade_presentation:
        report['presentation_calls'] = dict(sorted(presentation_calls.items()))
    if profiler:
        profiler.dump_stats(str(args.output/'advance.prof'))
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(55)
        (args.output/'profile.txt').write_text(stream.getvalue())
        print(stream.getvalue(), flush=True)
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
