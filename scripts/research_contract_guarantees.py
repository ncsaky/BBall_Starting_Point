"""Capture guarantee evidence without publishing a baseline or changing saves."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import urllib.request

from nba_gm_data.utils import normalize_name

URL = 'https://www.basketball-reference.com/contracts/players.html'
ROOT = Path(__file__).resolve().parents[1]


class ContractTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inside = False
        self.row = {}
        self.cell = None
        self.rows = []
        self.labels = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table' and attrs.get('id') == 'player-contracts':
            self.inside = True
        if not self.inside:
            return
        if tag == 'tr':
            self.row = {}
        if tag in ('td', 'th') and attrs.get('data-stat'):
            self.cell = {'key': attrs['data-stat'], 'text': '', 'attrs': attrs}

    def handle_data(self, data):
        if self.inside and self.cell is not None:
            self.cell['text'] += data

    def handle_endtag(self, tag):
        if not self.inside:
            return
        if tag in ('td', 'th') and self.cell is not None:
            self.row[self.cell['key']] = self.cell
            self.cell = None
        if tag == 'tr':
            if self.row.get('player', {}).get('attrs', {}).get('data-append-csv'):
                self.rows.append(self.row)
            else:
                self.labels.update({k: c['text'].strip() for k, c in self.row.items() if k.startswith('y')})
        if tag == 'table':
            self.inside = False


def money(cell):
    raw = cell.get('attrs', {}).get('csk', cell.get('text', '')).strip().replace('$', '').replace(',', '')
    return int(raw) if raw.isdigit() else None


def evidence(page):
    table = ContractTable()
    table.feed(page)
    if len(table.rows) < 100:
        raise ValueError('Incomplete contract table; refusing to publish research')
    rows = []
    for raw in table.rows:
        seasons = []
        for key, label in sorted(table.labels.items()):
            if len(label) != 7 or label[4] != '-' or not label[:4].isdigit():
                continue
            cell = raw.get(key, {})
            salary = money(cell)
            if salary is None:
                continue
            classes = set(cell.get('attrs', {}).get('class', '').split())
            option = 'player_option' if 'salary-pl' in classes else 'team_option' if 'salary-tm' in classes else None
            seasons.append({'season': label, 'salary': salary, 'option_type': option,
                            'guaranteed_salary': None, 'protection_evidence': 'unknown'})
        guaranteed = money(raw.get('remain_gtd', {}))
        fixed = [s for s in seasons if s['option_type'] is None]
        # A remaining-total shortfall cannot identify which year is partially
        # protected. Never spread it over years or call unknown money zero.
        if fixed and guaranteed is not None and guaranteed == sum(s['salary'] for s in fixed):
            for season in fixed:
                season.update(guaranteed_salary=season['salary'], protection_evidence='derived_from_matching_remaining_total')
        for season in seasons:
            if season['option_type']:
                season['protection_evidence'] = 'option_exercise_and_protection_require_review'
        name = raw['player']['text'].strip()
        rows.append({'name': name, 'normalized_name': normalize_name(name),
                     'bref_id': raw['player']['attrs']['data-append-csv'],
                     'team_abbrev': raw['team_id']['text'].strip(),
                     'remaining_guaranteed': guaranteed, 'seasons': seasons})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Preserve previous research; choose a new output path')
    with urllib.request.urlopen(URL, timeout=25) as response:
        page = response.read()
    contracts = evidence(page.decode('utf-8'))
    canonical = json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text())
    by_name = {}
    for player in canonical['players']:
        by_name.setdefault(normalize_name(player['name']), []).append(player['id'])
    for contract in contracts:
        ids = by_name.get(contract['normalized_name'], [])
        contract['candidate_player_id'] = ids[0] if len(ids) == 1 else None
    result = {'schema_version': 1, 'source': {'url': URL, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
               'html_sha256': hashlib.sha256(page).hexdigest()},
              'scope': 'Research only, not published game terms. Name matching is provisional, '
                       'not confirmation of identity, current contract or as-of-start-date applicability. '
                       'Aggregate guarantees do not resolve partial-year protection or activation dates.',
              'contracts': contracts,
              'coverage': {'players': len(contracts), 'unique_name_candidates': sum(bool(c['candidate_player_id']) for c in contracts),
                           'season_evidence': dict(Counter(s['protection_evidence'] for c in contracts for s in c['seasons']))}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True)+'\n')
    print(json.dumps(result['coverage']), flush=True)


if __name__ == '__main__':
    main()
