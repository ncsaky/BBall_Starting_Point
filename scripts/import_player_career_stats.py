"""Cache public ESPN regular-season career stats by stable athlete ID."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import json, time, urllib.request, urllib.error

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/research/espn_career_raw'
OUT = ROOT / 'data/research/player_career_stats.json'
CACHE.mkdir(parents=True, exist_ok=True)
players = json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text())['players']
metadata = json.loads((ROOT/'data/research/espn_nba_player_metadata_2026_10_02.json').read_text())['players']
by_name = {p['normalized_name']: p for p in metadata}
MATCHES = ROOT / 'data/research/player_career_identity_matches.json'
if MATCHES.exists():
    by_name.update(json.loads(MATCHES.read_text()))
else:
    from import_espn_player_metadata import search_player_athlete, fetch_json, PROFILE_URL
    def identify(player):
        try:
            athlete,error=search_player_athlete(player)
            if not athlete: return player.get('normalized_name'),None
            record={'espn_player_id':athlete}
            try:
                profile=fetch_json(PROFILE_URL.format(athlete_id=athlete),retries=1)
                draft=profile.get('draft') or {}
                record.update(draft_year=draft.get('year'),draft_position=draft.get('selection'),draft_status='drafted' if draft.get('selection') else 'undrafted' if profile.get('debutYear') else None)
            except Exception: pass
            return player.get('normalized_name'),record
        except Exception: return player.get('normalized_name'),None
    unmatched=[p for p in players if not p.get('espn_player_id') and not by_name.get(p.get('normalized_name'),{}).get('espn_player_id')]
    matches={}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for key,record in executor.map(identify,unmatched):
            if record: matches[key]=record
    MATCHES.write_text(json.dumps(matches,ensure_ascii=False,indent=2))
    by_name.update(matches)
    print(f'Additional identity matches: {len(matches)}/{len(unmatched)}',flush=True)

def number(value):
    try: return float(str(value).replace(',', ''))
    except (ValueError, TypeError): return None

def pair(value):
    values = str(value or '').split('-')
    return [number(v) for v in values] if len(values)==2 else [None, None]

def fetch(athlete):
    path = CACHE / f'{athlete}.json'
    if path.exists(): return athlete, json.loads(path.read_text()), None
    url = f'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete}/stats?seasontype=2'
    for attempt in range(3):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
            with urllib.request.urlopen(request,timeout=25) as response: data=json.load(response)
            path.write_text(json.dumps(data))
            return athlete,data,None
        except Exception as error:
            if attempt==2 or isinstance(error, urllib.error.HTTPError) and error.code==404: return athlete,None,str(error)
            time.sleep(1+attempt*2)

ids={str(p.get('espn_player_id') or by_name.get(p.get('normalized_name'),{}).get('espn_player_id')) for p in players}
ids.discard('None'); payload={}; errors={}
with ThreadPoolExecutor(max_workers=6) as executor:
    jobs=[executor.submit(fetch,athlete) for athlete in sorted(ids)]
    for index, future in enumerate(as_completed(jobs),1):
        athlete,data,error=future.result()
        if error: errors[athlete]=error
        else: payload[athlete]=data
        if index%40==0: print(f'Fetched {index}/{len(ids)}; errors {len(errors)}',flush=True)

records={}; missing=[]
for player in players:
    meta=by_name.get(player.get('normalized_name'),{})
    athlete=str(player.get('espn_player_id') or meta.get('espn_player_id') or '')
    raw=payload.get(athlete)
    if not raw:
        missing.append({'player_id':player['id'],'name':player['name'],'reason':errors.get(athlete) or 'No matched ESPN NBA athlete ID'})
        continue
    categories={c['name']:c for c in raw.get('categories',[])}
    totals=categories.get('totals',{})
    total_rows={(str(r.get('season',{}).get('displayName')),str(r.get('teamId'))):dict(zip(totals.get('names',[]),r.get('stats',[]))) for r in totals.get('statistics',[])}
    groups={}
    averages=categories.get('averages',{})
    for row in averages.get('statistics',[]):
        year=int(row.get('season',{}).get('year') or 0)
        if not year or year>=2027: continue
        label=row['season']['displayName']; stats=dict(zip(averages.get('names',[]),row.get('stats',[])))
        gp=number(stats.get('gamesPlayed')) or 0
        if gp<=0: continue
        total=total_rows.get((label,str(row.get('teamId'))),{})
        record={'season':label,'games':int(gp),'minutes':(number(stats.get('avgMinutes')) or 0)*gp}
        for source,target in [('points','points'),('totalRebounds','rebounds'),('assists','assists'),('steals','steals'),('blocks','blocks'),('turnovers','turnovers')]:
            record[target]=number(total.get(source))
            if record[target] is None: record[target]=(number(stats.get('avg'+target[0].upper()+target[1:])) or 0)*gp
        for source,avg,made,attempted in [('fieldGoalsMade-fieldGoalsAttempted','avgFieldGoalsMade-avgFieldGoalsAttempted','fgm','fga'),('threePointFieldGoalsMade-threePointFieldGoalsAttempted','avgThreePointFieldGoalsMade-avgThreePointFieldGoalsAttempted','fg3m','fg3a'),('freeThrowsMade-freeThrowsAttempted','avgFreeThrowsMade-avgFreeThrowsAttempted','ftm','fta')]:
            m,a=pair(total.get(source))
            if m is None or a is None:
                m,a=pair(stats.get(avg));m=(m or 0)*gp;a=(a or 0)*gp
            record[made],record[attempted]=m,a
        record['team_id']=str(row.get('teamId') or '')
        record['_season_total']=not row.get('teamId') and 'total' in str(row.get('teamSlug') or row.get('displayName') or '').lower()
        groups.setdefault(label,[]).append(record)
    seasons=[]
    for label,rows in groups.items():
        stint_teams=list(dict.fromkeys(r['team_id'] for r in rows if r['team_id']))
        combined=[r for r in rows if r.get('_season_total')]
        if combined: rows=combined[:1]
        # Aggregate traded seasons from team stints exactly once. ESPN's
        # totals rows supply shooting/rebounding counts; minutes use its
        # published per-game average, so may retain source rounding.
        aggregate={'season':label,'team_games':None,'source':'ESPN regular-season career stats','source_url':f'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete}/stats?seasontype=2'}
        for field in ('games','minutes','points','rebounds','assists','steals','blocks','turnovers','fgm','fga','fg3m','fg3a','ftm','fta'):
            aggregate[field]=sum(r[field] for r in rows)
        aggregate['team_ids']=stint_teams;seasons.append(aggregate)
    records[athlete]={'espn_player_id':athlete,'name':player['name'],'seasons':sorted(seasons,key=lambda r:r['season']), 'draft_year':player.get('draft_year') or meta.get('draft_year'),'draft_position':player.get('draft_position') or meta.get('draft_position'),'draft_status':player.get('draft_status') or meta.get('draft_status')}
# One standings request per year supplies actual team-game denominators,
# including lockouts and pandemic-shortened seasons.
years={int(s['season'].split('-')[0])+1 for r in records.values() for s in r['seasons']}
def team_records(year):
    path=CACHE/f'standings-{year}.json'
    try:
        if path.exists(): data=json.loads(path.read_text())
        else:
            with urllib.request.urlopen(f'https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings?season={year}',timeout=25) as response: data=json.load(response)
            if int(data.get('season',{}).get('year') or 0)!=year: return year,{}
            path.write_text(json.dumps(data))
        result={}
        def walk(group):
            for entry in group.get('standings',{}).get('entries',[]):
                stats={s['name']:s.get('value') for s in entry.get('stats',[])}
                if stats.get('wins') is not None and stats.get('losses') is not None:
                    result[str(entry['team']['id'])]=int(stats['wins']+stats['losses'])
            for child in group.get('children',[]):walk(child)
        walk(data)
        return year,result
    except Exception:return year,{}
with ThreadPoolExecutor(max_workers=6) as executor:
    season_teams=dict(executor.map(team_records,sorted(years)))
for record in records.values():
    for season in record['seasons']:
        teams=season['team_ids']
        counts=season_teams.get(int(season['season'].split('-')[0])+1,{})
        # A traded player's available schedule is not inferable by adding
        # both teams' full-season records; leave it unknown rather than fake it.
        if len(teams)==1:season['team_games']=counts.get(teams[0])
OUT.write_text(json.dumps({'version':1,'retrieved_at':datetime.now(timezone.utc).isoformat(),'source':'ESPN public athlete career statistics','players':records,'coverage':{'game_players':len(players),'matched':len(players)-len(missing),'with_nba_seasons':sum(bool(p['seasons']) for p in records.values()),'missing':missing,'fetch_errors':errors}},ensure_ascii=False,indent=2)+'\n')
print(f'Finished: {len(records)} athlete histories; {len(missing)} unavailable player mappings',flush=True)
