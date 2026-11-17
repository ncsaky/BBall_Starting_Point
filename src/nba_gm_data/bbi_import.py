"""Offline Basketball Index capture importer; never fetches or authenticates.

Run: python -m nba_gm_data.bbi_import CAPTURE --metadata batch.json
Only explicit CSV/TSV, JSON rows/columns, and rendered HTML tables are read.
Scripts, Shiny state and hidden network payloads are deliberately not evaluated.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import gzip
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Any

CACHE_PATH = 'data/research/bbi/normalized.json'
SCHEMA_VERSION = 'bbi_capture_v1'


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + '\n'


def number(value: Any) -> float | None:
    """Parse display numbers without changing percent units or interpreting grades."""
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(str(value).strip().replace(',', '').replace('−', '-').rstrip('%'))
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def name_key(value: str) -> str:
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub('[^a-z0-9]', '', value)


def normalize_season(value: Any, convention: str | None = None) -> str:
    text = str(value or '').strip().replace('–', '-').replace('—', '-')
    match = re.fullmatch(r'(\d{4})-(\d{2}|\d{4})', text)
    if match:
        start, end = int(match[1]), int(match[2])
        if end == (start + 1) % 100 or end == start + 1:
            return f'{start}-{(start+1)%100:02d}'
    if re.fullmatch(r'\d{4}', text) and convention in ('ending', 'starting'):
        start = int(text) - (convention == 'ending')
        return f'{start}-{(start+1)%100:02d}'
    raise ValueError(f'Ambiguous/missing season {value!r}; use YYYY-YY or explicit year_convention')


IDENTITY = {
    'name': ('Player', 'Name', 'Player Name', 'player_name', 'player_name_raw', 'name'),
    'espn': ('ESPN ID', 'espn_player_id', 'espn_id'),
    'provider': ('BBI ID', 'bbi_id', 'provider_player_id'),
    'canonical': ('canonical_player_id',),
    'season': ('Season', 'season', 'season_label_raw', 'Year'),
    'team': ('Team(s)', 'Team', 'team', 'team_stint_or_total'),
    'minutes': ('Minutes', 'minutes', 'MP'),
    'games': ('Games', 'games', 'GP'),
}
RESERVED = {key for values in IDENTITY.values() for key in values} | {
    '', '#', 'Rank', 'Age', 'age', 'Birthdate', 'birthdate', 'Season Type', 'season_type',
    'metric_name', 'metric', 'raw_value', 'value_plus', 'percentile', 'grade', 'sample_size',
    'sample_unit', 'units', 'percentile_scale', 'missing_reason',
}


def _first(row: dict, keys: tuple[str, ...], default=None):
    return next((row[k] for k in keys if k in row and row[k] not in (None, '')), default)


class PlayerMatcher:
    """No fuzzy, suffix-stripping, historical-team inference, or NBA/ESPN ID guessing."""
    def __init__(self, players: list[dict], aliases: dict | None = None):
        self.ids = {str(p['id']): p for p in players}
        self.names = defaultdict(list)
        self.espn = defaultdict(list)
        for p in players:
            self.names[name_key(p['name'])].append(str(p['id']))
            if p.get('espn_player_id'):
                self.espn[str(p['espn_player_id'])].append(str(p['id']))
        self.aliases = aliases or {}
        if any(pid not in self.ids for pid in self.aliases.values()):
            raise ValueError('Alias points to a noncanonical player')

    def match(self, row: dict) -> tuple[str | None, str]:
        name = str(_first(row, IDENTITY['name'], ''))
        canonical = _first(row, IDENTITY['canonical'])
        espn = _first(row, IDENTITY['espn'])
        names = self.names.get(name_key(name), [])
        if canonical:
            pid = str(canonical)
            if pid not in self.ids:
                return None, 'unknown_canonical_id'
            if espn and str(self.ids[pid].get('espn_player_id', '')) != str(espn):
                return None, 'conflicting_ids'
            if names and pid not in names:
                return None, 'conflicting_name_and_id'
            return pid, 'explicit_canonical_id'
        if espn:
            matches = self.espn.get(str(espn), [])
            if len(matches) != 1:
                return None, 'unknown_or_ambiguous_espn_id'
            if names and matches[0] not in names:
                return None, 'conflicting_name_and_id'
            return matches[0], 'espn_id'
        if name in self.aliases:
            return self.aliases[name], 'reviewed_alias'
        if len(names) == 1:
            return names[0], 'unique_exact_normalized_name'
        return None, 'ambiguous_name' if names else 'unmatched_name'


class _Tables(HTMLParser):
    """Parse literal table cells only. Ignore scripts, forms and duplicate header filters."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []; self.table = None; self.row = None; self.cell = None
        self.header = False; self.skip = 0; self.in_header = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag in ('thead', 'tfoot'):
            self.in_header = True
        if tag == 'table':
            if self.table is not None:
                raise ValueError('Nested tables need a table-only capture')
            self.table = []
        elif self.table is not None and tag == 'tr':
            self.row = []; self.header = self.in_header
        elif self.row is not None and tag in ('th', 'td'):
            self.cell = []; self.header |= tag == 'th'

    def handle_data(self, data):
        if self.cell is not None and not self.skip:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('thead', 'tfoot'):
            self.in_header = False
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip()); self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append((self.header, self.row)); self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table); self.table = None


def _tabular(columns: list, values: list) -> list[dict]:
    if len(set(columns)) != len(columns):
        raise ValueError('Duplicate headers; disambiguate with a documented column map before import')
    if any(len(row) != len(columns) for row in values):
        raise ValueError('Ragged table: row/header counts differ')
    return [dict(zip(columns, row)) for row in values]


def read_capture(path: str | Path, *, table_index: int | None = None) -> list[dict]:
    path = Path(path); text = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() in ('.csv', '.tsv'):
        rows = [r for r in csv.reader(io.StringIO(text), delimiter='\t' if path.suffix.lower() == '.tsv' else ',') if r]
        return _tabular(rows[0], rows[1:]) if rows else []
    if path.suffix.lower() == '.json':
        data = json.loads(text)
        if isinstance(data, dict) and 'columns' in data:
            return _tabular(data['columns'], data['rows'])
        rows = data.get('rows') if isinstance(data, dict) else data
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError('JSON must contain row objects or explicit columns/rows')
        return rows
    if path.suffix.lower() in ('.html', '.htm'):
        parser = _Tables(); parser.feed(text)
        if not parser.tables:
            raise ValueError('No rendered HTML table; a Shiny loading page is not a data capture')
        if table_index is None and len(parser.tables) != 1:
            raise ValueError('Multiple tables; choose table_index explicitly')
        table = parser.tables[table_index or 0]
        header = next((r for is_header, r in table if is_header and any(r)), None)
        if not header:
            raise ValueError('HTML needs a header row')
        return _tabular(header, [r for is_header, r in table if not is_header])
    raise ValueError('Use CSV, TSV, JSON or rendered table HTML')


def _metric_cells(row: dict, metadata: dict):
    if 'metric_name' in row or 'metric' in row:
        yield str(row.get('metric_name') or row['metric']), {k: row.get(k) for k in
            ('raw_value', 'value_plus', 'percentile', 'grade', 'sample_size', 'sample_unit', 'units', 'percentile_scale', 'missing_reason')}
        return
    grouped = defaultdict(dict)
    suffixes = {'value': 'raw_value', 'raw value': 'raw_value', 'percentile': 'percentile',
                'grade': 'grade', 'value+': 'value_plus', 'sample size': 'sample_size', 'n': 'sample_size'}
    for column, value in row.items():
        if column in RESERVED:
            continue
        spec = metadata.get('column_map', {}).get(column)
        if spec:
            grouped[spec['metric']][spec['representation']] = value
            continue
        match = re.fullmatch(r'(.+?)\s*(?:\(([^()]+)\)|\[([^\[\]]+)\]| - (.+))', column)
        suffix = (next((v for v in match.groups()[1:] if v), '').lower() if match else '')
        if suffix in suffixes:
            grouped[match[1].strip()][suffixes[suffix]] = value
        else:
            mode = metadata.get('representation', 'raw_value')
            if mode not in ('raw_value', 'value_plus', 'percentile', 'grade'):
                raise ValueError('representation must be raw_value, value_plus, percentile or grade')
            grouped[column][mode] = value
    yield from grouped.items()


def iter_records(cache: dict, cache_dir: str | Path):
    """Read one compressed normalized batch at a time; never load every season."""
    for _, batch in sorted(cache['batches'].items()):
        with gzip.open(Path(cache_dir) / batch['normalized_file'], 'rt', encoding='utf-8') as stream:
            yield from json.load(stream)


def import_capture(path: str | Path, metadata: dict, players: list[dict],
                   cache_dir: str | Path = 'data/research/bbi') -> dict:
    """Preserve exact bytes, append a reproducible batch, and rebuild coverage audit.

    Metadata is supplied by the capturing human, never inferred from a login/session.
    Each value retains its batch, source row, original text and query population.
    """
    for key in ('source_url', 'retrieved_at_utc', 'season_type', 'dataset_kind', 'filters', 'capture_method'):
        if key not in metadata:
            raise ValueError('Missing capture metadata: ' + key)
    timestamp = datetime.fromisoformat(metadata['retrieved_at_utc'].replace('Z', '+00:00'))
    if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError('retrieved_at_utc must be a UTC timestamp')
    if metadata['dataset_kind'] not in ('observed', 'historical_demo', 'synthetic', 'forecast'):
        raise ValueError('Unknown dataset_kind')
    rows = read_capture(path, table_index=metadata.get('table_index'))
    if not rows:
        raise ValueError('Empty capture; no data rows')
    content = Path(path).read_bytes(); sha = hashlib.sha256(content).hexdigest()
    batch_id = hashlib.sha256(content + _json(metadata).encode()).hexdigest()
    matcher = PlayerMatcher(players, metadata.get('aliases'))
    records = []; unmatched = []; joins = Counter()
    catalog = metadata.get('metrics', {})
    for index, row in enumerate(rows, 1):
        pid, match_method = matcher.match(row); joins[match_method] += 1
        if pid is None:
            unmatched.append(dict(source_row=index, reason=match_method, row=row))
        raw_season = _first(row, IDENTITY['season'], metadata.get('season'))
        season = normalize_season(raw_season, metadata.get('year_convention'))
        for metric, cells in _metric_cells(row, metadata):
            spec = catalog.get(metric, {})
            raw = cells.get('raw_value')
            sample = number(cells.get('sample_size'))
            if sample is not None and sample < 0:
                raise ValueError('Negative sample size')
            percentile = number(cells.get('percentile'))
            scale = cells.get('percentile_scale') or spec.get('percentile_scale') or metadata.get('percentile_scale')
            if percentile is not None and scale in ('0_100', '0_1'):
                if not 0 <= percentile <= (100 if scale == '0_100' else 1):
                    raise ValueError('Percentile outside declared scale')
            kind = spec.get('evidence_kind', 'unclassified_provider_field')
            if 'lebron' in metric.lower() or metric in ('WAR', 'Offensive Talent', 'Defensive Talent'):
                kind = 'validation_composite'
            records.append(dict(canonical_player_id=pid, match_method=match_method,
                player_name_raw=_first(row, IDENTITY['name']),
                espn_player_id=_first(row, IDENTITY['espn']), provider_player_id=_first(row, IDENTITY['provider']),
                season=season, season_label_raw=raw_season, season_type=metadata['season_type'],
                team_stint_or_total=_first(row, IDENTITY['team']), row_scope=metadata.get('row_scope', 'unknown'),
                metric_name=metric, raw_value=number(raw) if number(raw) is not None else raw,
                percentile=percentile, percentile_scale=scale, grade=cells.get('grade'), value_plus=cells.get('value_plus'),
                sample_size=sample, sample_unit=cells.get('sample_unit') or spec.get('sample_unit'),
                minutes=number(_first(row, IDENTITY['minutes'])), games=number(_first(row, IDENTITY['games'])),
                units=cells.get('units') or spec.get('units', 'unknown'), evidence_kind=kind,
                missing_reason=cells.get('missing_reason') or ('not_shown_or_unavailable' if all(cells.get(k) in (None, '', 'NA', 'N/A', '—') for k in ('raw_value', 'value_plus', 'percentile', 'grade')) else None),
                source_text=cells, batch_id=batch_id, source_row=index,
                retrieved_at_utc=metadata['retrieved_at_utc'], provider_as_of=metadata.get('provider_as_of'),
                dataset_kind=metadata['dataset_kind'], percentile_population=metadata.get('percentile_population', 'unknown')))
    cache_dir = Path(cache_dir); normalized_path = cache_dir / 'normalized.json'
    cache = json.loads(normalized_path.read_text()) if normalized_path.exists() else dict(schema_version=SCHEMA_VERSION, batches={})
    if cache['schema_version'] != SCHEMA_VERSION:
        raise ValueError('Unsupported BBI cache schema')
    if batch_id in cache['batches']:
        return cache
    raw_path = cache_dir / 'raw' / (sha + Path(path).suffix.lower())
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists() and raw_path.read_bytes() != content:
        raise ValueError('Raw file hash conflict')
    raw_path.write_bytes(content)
    expected = metadata.get('displayed_rows')
    batch = dict(metadata=metadata, sha256=sha, raw_file=str(raw_path.relative_to(cache_dir)),
                 source_filename=Path(path).name, captured_rows=len(rows), join_counts=dict(joins),
                 unmatched_rows=unmatched, completeness='unknown' if expected is None else ('complete' if len(rows) == expected else 'partial'))
    # Per-batch compressed JSON avoids rewriting millions of earlier cells on
    # every export. The small normalized.json is the authoritative cache index.
    shard = cache_dir / 'normalized' / (batch_id + '.json.gz')
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard_tmp = shard.with_suffix('.gz.tmp')
    payload = json.dumps(records, sort_keys=True, ensure_ascii=False, allow_nan=False,
                         separators=(',', ':')).encode('utf-8')
    shard_tmp.write_bytes(gzip.compress(payload, mtime=0)); shard_tmp.replace(shard)
    batch['normalized_file'] = str(shard.relative_to(cache_dir))
    batch['record_count'] = len(records)
    counts = defaultdict(Counter)
    for r in records:
        count = counts[(r['season'], r['metric_name'])]
        count['records'] += 1
        count['matched_records'] += r['canonical_player_id'] is not None
        count['raw_values_present'] += r['raw_value'] not in (None, '', 'NA', 'N/A', '—')
        count['percentiles_present'] += r['percentile'] is not None
        count['grades_present'] += r['grade'] not in (None, '', 'NA', 'N/A', '—')
        count['sample_sizes_present'] += r['sample_size'] is not None
        count['sample_units_known'] += r['sample_size'] is not None and bool(r['sample_unit'])
        count['missing_values'] += r['missing_reason'] is not None
    batch['coverage'] = [dict(season=s, metric=m, **count) for (s, m), count in sorted(counts.items())]
    keys = Counter((r['canonical_player_id'] or r['player_name_raw'], r['season'],
                    r['team_stint_or_total'], r['metric_name']) for r in records)
    batch['duplicate_row_groups'] = [dict(key=list(k), count=n) for k, n in keys.items() if n > 1]
    cache['batches'][batch_id] = batch
    coverage = defaultdict(Counter)
    by_hash = defaultdict(list)
    for bid, saved in cache['batches'].items():
        by_hash[saved['sha256']].append(bid)
        for cell in saved['coverage']:
            coverage[(cell['season'], cell['metric'])].update({k:v for k,v in cell.items() if k not in ('season', 'metric')})
    cache['coverage'] = [dict(season=s, metric=m, **count) for (s, m), count in sorted(coverage.items())]
    # Identical bytes with different retrieval/filter metadata are retained and
    # flagged. Other overlapping metric batches remain separate; estimator picks
    # only one strongest current source for each input, never sums duplicates.
    cache['duplicate_groups'] = [dict(sha256=sha, batch_ids=sorted(ids))
                                for sha, ids in sorted(by_hash.items()) if len(ids) > 1]
    temporary = normalized_path.with_suffix('.json.tmp')
    temporary.write_text(_json(cache)); temporary.replace(normalized_path)
    return cache


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--universe', type=Path, default=Path('data/canonical/universe_2026_27_offseason.json'))
    parser.add_argument('--cache-dir', type=Path, default=Path('data/research/bbi'))
    args = parser.parse_args(argv)
    cache = import_capture(args.capture, json.loads(args.metadata.read_text()),
                           json.loads(args.universe.read_text())['players'], args.cache_dir)
    print(_json(dict(batches=len(cache['batches']), records=sum(b['record_count'] for b in cache['batches'].values()),
                     unmatched_rows=sum(len(b['unmatched_rows']) for b in cache['batches'].values()))), end='')


if __name__ == '__main__':
    main()
