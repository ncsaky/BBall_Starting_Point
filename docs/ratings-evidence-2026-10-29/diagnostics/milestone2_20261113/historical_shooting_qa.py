"""Read-only source audit; writes only this research diagnostic folder. No production fixes."""
import json,hashlib,collections,urllib.request,urllib.error,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
ALLOW_FETCH='--fetch-samples' in sys.argv
SRC=ROOT/'data/research/game_boxscores_2025_26.json'
b=json.loads(SRC.read_text());games=b['games']
selected=[games[0],next(g for g in games if g.get('phase')=='regular' and g['date']>='2026-02-01'),games[-1],next(g for g in games if g.get('phase')=='playoffs')]
fetches=[];comparisons=[]
for g in selected:
 gid=g['game_id'];path=OUT/f'espn_summary_{gid}.json';url=f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={gid}'
 try:
  failure_path=OUT/f'espn_summary_{gid}_failure.json'
  if failure_path.exists():
   fetches.append(json.loads(failure_path.read_text()));continue
  if not path.exists():
   if not ALLOW_FETCH:raise RuntimeError('No retained raw sample; network disabled unless --fetch-samples is explicitly supplied')
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as r:
    raw=r.read(2000000);status=r.status
   path.write_bytes(raw)
  else:status='retained_this_task'
  d=json.loads(path.read_text());fetches.append({'game_id':gid,'url':url,'http_status':status,'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'raw_sample_saved_at_utc':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),'source_header_id':d.get('header',{}).get('id'),'source_season':d.get('header',{}).get('season'),'source_date':d.get('header',{}).get('competitions',[{}])[0].get('date'),'retained_schedule_date':g['date'],'retained_phase':g['phase']})
  old={(str(x.get('espn_player_id')),x.get('team_abbrev')):x for x in g['players']}
  for team in d.get('boxscore',{}).get('players',[]):
   abbrev=team.get('team',{}).get('abbreviation')
   for group in team.get('statistics',[]):
    keys=group.get('keys') or group.get('names') or []
    for a in group.get('athletes',[]):
     row=dict(zip(keys,a.get('stats',[])));pid=str(a.get('athlete',{}).get('id'));o=old.get((pid,abbrev));fg=row.get('fieldGoalsMade-fieldGoalsAttempted');legacy=row.get('fg') or row.get('FG');three=row.get('threePointFieldGoalsMade-threePointFieldGoalsAttempted') or row.get('3PT');ft=row.get('freeThrowsMade-freeThrowsAttempted') or row.get('FT')
     comparisons.append({'game_id':gid,'pid':pid,'name':a.get('athlete',{}).get('displayName'),'team':abbrev,'joined_on_id_team':o is not None,'source_keys':keys,'source_FG':fg,'legacy_FG_alias_value':legacy,'source_3PT':three,'source_FT':ft,'source_points':row.get('points') or row.get('PTS'),'source_minutes':row.get('minutes') or row.get('MIN'),'retained':{k:o.get(k) for k in ['fgm','fga','fg3m','fg3a','ftm','fta','points','minutes']} if o else None})
 except Exception as e:
  failure={'game_id':gid,'url':url,'error':type(e).__name__+': '+str(e),'retry':False};fetches.append(failure)
  if isinstance(e,urllib.error.HTTPError):(OUT/f'espn_summary_{gid}_failure.json').write_text(json.dumps(failure))
  if isinstance(e,urllib.error.HTTPError) and e.code==429:break

def ma(v):
 try:
  a,c=str(v).split('-');return int(a),int(c)
 except:return None
counts=collections.Counter();teams=collections.Counter();elig=[];samples=[];dates=collections.Counter();pidduplicates=0
for g in games:
 seen=set();by=collections.defaultdict(list)
 for r in g['players']:
  key=(str(r.get('espn_player_id')),r.get('team_abbrev'))
  if key in seen:pidduplicates+=1
  seen.add(key);by[r.get('team_abbrev')].append(r)
 for t in g.get('teams',[]):
  ab=t.get('abbreviation') or t.get('team_abbrev');rs=by.get(ab,[]);st=t.get('stats',{});fg=ma(st.get('fieldGoalsMade-fieldGoalsAttempted'));th=ma(st.get('threePointFieldGoalsMade-threePointFieldGoalsAttempted'));ft=ma(st.get('freeThrowsMade-freeThrowsAttempted'))
  vals=[];valid=True
  for r in rs:
   n=(r.get('points') or 0)-(r.get('fg3m') or 0)-(r.get('ftm') or 0)
   if n<0 or n%2:valid=False
   val=n/2
   if val<(r.get('fg3m') or 0):valid=False
   vals.append(val)
  ok=bool(g.get('status')=='STATUS_FINAL' and rs and fg and valid and sum(vals)==fg[0]);teams['teams_total']+=1
  if ok:teams['derived_FGM_sum_equals_source_team_FGM']+=1
  if th and sum((r.get('fg3m') or 0) for r in rs)==th[0]:teams['three_makes_match']+=1
  if th and sum((r.get('fg3a') or 0) for r in rs)==th[1]:teams['three_attempts_match']+=1
  if ft and sum((r.get('ftm') or 0) for r in rs)==ft[0]:teams['ft_makes_match']+=1
  if ft and sum((r.get('fta') or 0) for r in rs)==ft[1]:teams['ft_attempts_match']+=1
  for r,val in zip(rs,vals):
   row={'game_id':g['game_id'],'date':g['date'],'phase':g.get('phase'),'player_id':str(r.get('espn_player_id')),'team':ab,'raw_fgm':r.get('fgm'),'raw_fga':r.get('fga'),'derived_total_fgm':int(val) if valid else None,'fga':None,'usable_derived_fgm':ok,'method':'(points - three_point_makes - free_throw_makes)/2; require integer/nonnegative/FGM>=3PM and independent retained team-FGM reconciliation','raw_file_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest() if False else None}
   row.pop('raw_file_sha256');elig.append(row)
 for r in g['players']:
  counts['rows']+=1
  if (r.get('minutes') or 0)>0:counts['positive_minute_rows']+=1
  if (r.get('fg3m') or 0)>(r.get('fgm') or 0):counts['3PM_gt_FGM']+=1
  if (r.get('fgm') or 0)>0:counts['positive_FGM']+=1
  if (r.get('fga') or 0)>0:counts['positive_FGA']+=1
 dates[g.get('phase','unknown')]+=1
# Direct authoritative-source normalization for matched sample rows only; no broad request campaign.
normalized=[];samplecounts=collections.Counter()
for c in comparisons:
 fg=ma(c['source_FG']);th=ma(c['source_3PT']);ft=ma(c['source_FT']);o=c['retained']
 if not (o and fg and th and ft):continue
 samplecounts['matched_full_shooting_rows']+=1
 if c['legacy_FG_alias_value'] is None:samplecounts['FG_long_key_without_old_alias']+=1
 checks={k:o[k]==v for k,v in [('fg3m',th[0]),('fg3a',th[1]),('ftm',ft[0]),('fta',ft[1])]}
 try:checks['points']=o['points']==int(c['source_points'])
 except:checks['points']=False
 if all(checks.values()):samplecounts['nonFG_scoring_fields_match_source']+=1
 formula=(o['points']-o['fg3m']-o['ftm'])/2
 if formula==fg[0]:samplecounts['derived_total_FGM_equals_source']+=1
 normalized.append({'game_id':c['game_id'],'pid':c['pid'],'name':c['name'],'team':c['team'],'fgm':fg[0],'fga':fg[1],'fg3m':th[0],'fg3a':th[1],'ftm':ft[0],'fta':ft[1],'source_FG_key':'fieldGoalsMade-fieldGoalsAttempted','retained_other_checks':checks,'FGM_is_2PM_hypothesis_matches':o['fgm']==fg[0]-th[0]})
report={'date':'2026-11-13','source_hash':hashlib.sha256(SRC.read_bytes()).hexdigest(),'source_metadata':b['source'],'source_capture_warning':'aggregate fetched_at is not per-game acquisition time; file contains preserved413 games plus later refresh; do not infer timestamp error from newest scheduled date alone','counts':{**dict(counts),'positive_FGM':counts.get('positive_FGM',0),'positive_FGA':counts.get('positive_FGA',0)},'game_phase_counts':dict(dates),'duplicate_game_team_player_keys':pidduplicates,'retained_team_reconciliation':dict(teams),'authoritative_samples':fetches,'sample_counts':dict(samplecounts),'sample_rows':comparisons,'direct_normalized_samples':normalized,'normalization_rule':'parse fieldGoalsMade-fieldGoalsAttempted as total FG before legacy fg/FG aliases; preserve absent/invalid as missing, never0 default. Not implemented in production.','derived_recovery_rule':'total FGM is algebraically recoverable when scoring components and independent teamFGM reconcile; FGA remains unknown outside direct source samples. No clamp, no2PM reinterpretation.','generated_boxscore_boundary':'this is imported historical cache/parser evidence; no generated game boxscore defect inferred.'}
(OUT/'historical_shooting_qa_results.json').write_text(json.dumps(report,indent=2));(OUT/'historical_total_fgm_derived.json').write_text(json.dumps({'method':report['derived_recovery_rule'],'source_sha256':report['source_hash'],'records':elig},indent=2))
print(json.dumps({'counts':dict(counts),'team_checks':dict(teams),'sample_checks':dict(samplecounts),'requests':[{k:v for k,v in f.items() if k in ['game_id','http_status','error','source_season','source_date','retained_schedule_date']} for f in fetches],'derived_records':len(elig),'derived_usable':sum(x['usable_derived_fgm'] for x in elig)},indent=2))
