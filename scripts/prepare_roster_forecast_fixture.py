"""Extract roster dependencies from the archived pretty-JSON 2036 checkpoint.

No career advancement. Stream past game/history payloads; fold hot development
events into archived totals in exactly the original per-event addition order.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=Path('output/simulation-memory-2026-10-24/after-final/mature-17/business.json'))
parser.add_argument('--output', type=Path, default=Path('output/roster-forecast-pass/fixtures/mature2036.json'))
args = parser.parse_args()
keys = set('''version meta state generated_players generated_traits generated_health_profiles incoming_rookies
retired_player_ids roster_overrides draft_pick_overrides generated_draft_picks draft_orders pick_obligations
locked_pick_assets contract_overrides waived_salary_obligations waiver_wire team_plans team_trade_wants
team_trade_blocks team_records ai_trade_pressure_player_ids player_season_stats staff_slots health_states
injury_events development_trait_totals rotation_baselines rotation_snapshots rotation_overrides
rotation_recommendations rotation_starting_fives season_schedules'''.split())
with args.source.open('rb') as stream:
    source_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
blocks, keep = [], False
with args.source.open() as stream:
    for line in stream:
        match = re.match(r'^  "([^"\\]+)":', line)
        if match:
            keep = match[1] in keys
        elif line == '}\n':
            keep = False
        if keep:
            blocks.append(line)
saved = json.loads('{' + ''.join(blocks).rstrip().rstrip(',') + '}')
totals = {str(pid): {str(key): float(value or 0) for key, value in values.items()}
          for pid, values in saved.get('development_trait_totals', {}).items()}
inside, event, count = False, [], 0
with args.source.open() as stream:
    for line in stream:
        if line.startswith('  "development_events": ['):
            inside = True
            continue
        if not inside:
            continue
        if line.startswith('  ]'):
            break
        event.append(line)
        if line.startswith('    }'):
            row = json.loads(''.join(event).rstrip().rstrip(','))
            pid = str(row.get('player_id') or '')
            if pid:
                target = totals.setdefault(pid, {})
                for key, delta in (row.get('trait_deltas') or {}).items():
                    target[str(key)] = float(target.get(str(key)) or 0) + float(delta or 0)
            count += 1
            event = []
assert not event
saved['development_trait_totals'] = totals
saved['development_events'] = []  # Hot deltas above are already folded exactly.
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(saved))
with args.source.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == source_hash
report = {'source': str(args.source), 'source_sha256': source_hash, 'date': saved['state']['current_date'],
          'selected_fields': sorted(saved), 'hot_development_events_folded': count,
          'generated_players': len(saved.get('generated_players', [])), 'bytes': args.output.stat().st_size,
          'advance_actions': 0}
args.output.with_name(args.output.stem + '-source.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
