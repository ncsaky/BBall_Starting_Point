"""Count dated official NBA tracker entries without copying article prose."""
import argparse
from collections import Counter
from datetime import date
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen


class NextData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reading, self.raw = False, ''

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == '__NEXT_DATA__':
            self.reading = True

    def handle_data(self, text):
        if self.reading:
            self.raw += text

    def handle_endtag(self, tag):
        if tag == 'script':
            self.reading = False


def article(url):
    raw = urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read()
    parser = NextData()
    parser.feed(raw.decode())
    return json.loads(parser.raw)['props']['pageProps']['article'], hashlib.sha256(raw).hexdigest()


def calendar_years(snapshot):
    entries = {(r['date'], r['entry_id']) for source in snapshot['sources'] for r in source['entries']}
    return {str(year): {f'{year}-{month:02}': sum(stamp.startswith(f'{year}-{month:02}') for stamp, _ in entries)
                       for month in range(1, 13)} for year in (2024, 2025)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, help='Recalculate whole-year counts offline from an existing source snapshot.')
    args = parser.parse_args()
    if args.snapshot:
        result = json.loads(args.snapshot.read_text())
        result['calendar_years'] = calendar_years(result)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result['calendar_years'], indent=2))
        return
    result = {'retrieved': date.today().isoformat(), 'count_unit': 'dated tracker block, not players or team participations',
              'limits': ['Tracker omissions and grouped multi-team reporting mean these are a consistent sample, not a complete transaction census.',
                         'Report/approval dates can differ. Rescinded entries excluded. Pure pick trades included.',
                         '2024-25 tracker has one undated Porter Jr. trade; counted separately with Feb. 6 official confirmation.'],
              'sources': []}
    months = {'Jan': 1, 'Feb': 2, 'Jun': 6, 'June': 6, 'Jul': 7, 'July': 7,
              'Aug': 8, 'Sep': 9, 'Sept': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
    for start in (2023, 2024, 2025):
        for offseason in (True, False):
            end = str(start + 1)[-2:]
            url = f'https://www.nba.com/news/{start}-offseason-trade-tracker' if offseason else f'https://www.nba.com/news/{start}-{end}-nba-trade-tracker'
            data, signature = article(url)
            rows, rescinded = [], 0
            for line in data['contentText'].splitlines():
                match = re.search(r'\((Jan|Feb|June?|July?|Aug|Sept?|Oct|Nov|Dec)\.?\s*(\d{1,2})\)', line)
                if not match:
                    continue
                if 'rescinded' in line.lower():
                    rescinded += 1
                    continue
                month, day = months[match[1]], int(match[2])
                year = start if offseason or month >= 7 else start + 1
                rows.append({'date': date(year, month, day).isoformat(),
                             'entry_id': hashlib.sha256(line.strip().encode()).hexdigest()[:16]})
            if start == 2024 and not offseason and 'Bucks get Porter Jr.' in data['contentText']:
                rows.append({'date': '2025-02-06', 'entry_id': 'undated-porter-jr', 'date_override': True,
                             'date_override_source_url': 'https://twitter.com/ClippersPR/status/1887928690777956820'})
            deadline = {2023: '2024-02-08', 2024: '2025-02-06', 2025: '2026-02-05'}[start]
            through = date.fromisoformat(deadline)
            row = {'season': f'{start}-{end}', 'period': 'offseason' if offseason else 'in_season',
                   'url': url, 'retrieval_sha256': signature, 'entries': rows, 'rescinded_excluded': rescinded,
                   'monthly_counts': dict(sorted(Counter(r['date'][:7] for r in rows).items())),
                   'deadline_day': sum(r['date'] == deadline for r in rows),
                   'deadline_week': sum(0 <= (through - date.fromisoformat(r['date'])).days <= 6 for r in rows)}
            result['sources'].append(row)
            print(json.dumps({k: v for k, v in row.items() if k not in {'entries', 'retrieval_sha256'}}), flush=True)
    result['calendar_years'] = calendar_years(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
