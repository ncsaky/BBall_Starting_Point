"""Preserve pre-trade contexts by replaying audit-owned checkpoints only."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import gzip
import json
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import play, transactions as tx
from nba_gm_data.save import canonical_with_save
from verify_trade_year import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, choices=(17, 29), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root/'output/full-year-market-2026-10-27'/f'seed{args.seed}'
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Use a new audit output directory.')
    output.mkdir(parents=True)
    names = ('trae-young', 'pascal-siakam', 'kawhi-leonard') if args.seed == 17 else ('kawhi-leonard',)
    expected = {e['proposal_id']: e for line in (source/'market-events.jsonl').read_text().splitlines()
                for e in [json.loads(line)] if e.get('kind') == 'trade' and e['date'].startswith('2027')
                and any(name in e['proposal_id'] for name in names)}
    original_apply = tx.apply_trade_to_state
    original_phase = play.maybe_run_free_agency_ai_trades_state
    original_queue = play.queue_summer_trade_offers
    original_fallback = play.free_agency_fallback_trade_candidates
    captured = []

    def apply(saved, pid, *pos, **kwargs):
        active = candidate = None
        if pid in expected:
            candidate = deepcopy(next(r for r in saved['pending_trade_proposals'] if r['proposal']['id'] == pid))
            active = tx.with_transaction_context(canonical_with_save(kwargs['canonical'], deepcopy(saved)))
        result = original_apply(saved, pid, *pos, **kwargs)
        if active is not None and result.get('status') == 'applied':
            keep = {'_strategy_model_version', '_human_team_ids'}
            active = {k: v for k, v in active.items() if not k.startswith('_') or k in keep}
            index = len(captured)
            filename = f'context-{index}.json.gz'
            with gzip.open(output/filename, 'wt') as handle:
                json.dump({'canonical': active, 'candidate': candidate, 'original_event': expected[pid]}, handle)
            captured.append({'file': filename, 'proposal_id': pid, 'date': expected[pid]['date']})
            (output/'contexts.json').write_text(json.dumps(captured, indent=2)+'\n')
            print(json.dumps({'captured': pid, 'file': filename}), flush=True)
        return result

    def old_general(active, saved, human, seed, *, max_results=1):
        current = saved['state']['current_date']
        day = int(saved['free_agency_state'].get('day') or 1)
        payload = tx.simulate_ai_trades(active, current, current, seed=seed+day*17, limit=12)
        candidates = []
        for c in payload.get('proposals', []):
            p = c.get('proposal') or {}
            if human in {p.get('from_team_id'), p.get('to_team_id')}:
                continue
            if c.get('accepted_by_all') and c.get('legality', {}).get('status') == 'legal':
                c['free_agency_context'] = {'kind': 'general_market_trade'}
                candidates.append(c)
        return candidates[:1]

    def old_summer(canonical, saved, active, human, seed, *, phase):
        if phase != 'post_resolution':
            return original_phase(canonical, saved, active, human, seed, phase=phase)
        state = saved['free_agency_state']
        key = f"{state.get('season')}:{int(state.get('day') or 1)}:{phase}"
        if key in state.get('ai_trade_days_processed', []) or state.get('status') == 'completed':
            return original_phase(canonical, saved, active, human, seed, phase=phase)
        # Reproduce the annual evidence's old summer search policy only inside
        # this disposable replay, not in production or the new market tests.
        original_queue(active, saved, seed)
        fallback = original_fallback(active, saved, play.resolve_team(canonical, human)['id'], seed)
        slots = int(not fallback and int(state.get('ai_general_trade_count') or 0) < 3)
        with patch.object(play, 'queue_summer_trade_offers'), \
             patch.object(play, 'free_agency_fallback_trade_candidates', return_value=fallback), \
             patch.object(play, 'free_agency_general_trade_candidates', side_effect=old_general), \
             patch('nba_gm_data.trade_calendar.summer_offer_slots', return_value=slots):
            return original_phase(canonical, saved, active, human, seed, phase=phase)

    with ExitStack() as stack:
        stack.enter_context(patch.object(tx, 'apply_trade_to_state', side_effect=apply))
        stack.enter_context(patch.object(play, 'apply_trade_to_state', side_effect=apply))
        stack.enter_context(patch.object(play, 'maybe_run_free_agency_ai_trades_state', side_effect=old_summer))
        run(argparse.Namespace(output=output, seed=args.seed, observer_directory_created=True, resume=False,
            from_save=source/'phase_saves/summer_before.json', seconds=1500,
            end_date='2027-12-18' if args.seed == 17 else '2027-09-01'))
    missing = sorted(set(expected)-{r['proposal_id'] for r in captured})
    (output/'capture-status.json').write_text(json.dumps({'captured': captured, 'missing': missing}, indent=2)+'\n')
    return int(bool(missing))


if __name__ == '__main__':
    raise SystemExit(main())
