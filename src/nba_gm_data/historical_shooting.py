"""Strict imported-shooting provenance and opt-in legacy quarantine/recovery.

No I/O, cache migration, FGA inference or correction of inconsistent totals.
Legacy raw readers remain compatible; calibration must use this explicit view.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import re

PARSER_VERSION='espn_game_shooting_v2_2026_11_13'
ALIASES={
    'fg':('fieldGoalsMade-fieldGoalsAttempted','fg','FG'),
    'three':('threePointFieldGoalsMade-threePointFieldGoalsAttempted','3PT'),
    'ft':('freeThrowsMade-freeThrowsAttempted','FT'),
}


def strict_pair(value):
    if not isinstance(value,str):return None,None
    match=re.fullmatch(r'\s*(\d+)\s*[-–]\s*(\d+)\s*',value)
    if not match:return None,None
    made,attempted=map(int,match.groups())
    return (made,attempted) if made<=attempted else (None,None)


def observed_pair(row,family,*,dnp=False):
    keys=ALIASES[family];present=[key for key in keys if key in row]
    selected=next((key for key in present if row[key] not in (None,'','--')),present[0] if present else None)
    raw=row[selected] if selected else None
    pair=strict_pair(raw)
    missing=raw in (None,'','--')
    status='dnp' if dnp else 'missing' if missing else 'invalid' if pair[0] is None else 'observed'
    conflicts=[key for key in present if strict_pair(row[key])[0] is not None and pair[0] is not None and strict_pair(row[key])!=pair]
    return ((None,None) if dnp else pair),{'status':status,'source_key':selected,'raw_value':raw,'alias_conflicts':conflicts}


def row_issues(values):
    issues=[]
    fgm,fga,three,three_a,ftm,fta=(values[key] for key in ('fgm','fga','fg3m','fg3a','ftm','fta'))
    if None not in (fgm,three) and three>fgm:issues.append('three_makes_exceed_total_fg')
    if None not in (fga,three_a) and three_a>fga:issues.append('three_attempts_exceed_total_fg')
    if None not in (fgm,fga,three,three_a) and fgm-three>fga-three_a:issues.append('two_makes_exceed_two_attempts')
    points=values.get('points_observed')
    if None not in (points,fgm,three,ftm) and points!=2*fgm+three+ftm:issues.append('scoring_identity_mismatch')
    return issues


def source_identity(data,schedule):
    header=data.get('header',{});competition=(header.get('competitions') or [{}])[0];season=header.get('season',{})
    source={'game_id':str(header['id']) if header.get('id') is not None else None,'date':str(competition.get('date') or '')[:10] or None,
            'season_year':season.get('year'),'season_type':season.get('type')}
    issues=[]
    for key,wanted in [('game_id',str(schedule['externalGameId'])),('date',schedule['gameDate'])]:
        if source[key] is None:issues.append(f'missing_source_{key}')
        elif source[key]!=wanted:issues.append(f'source_{key}_mismatch')
    try:
        day=date.fromisoformat(schedule['gameDate']);ending_year=day.year+(day.month>=7)
        if source['season_year'] is None:issues.append('missing_source_season')
        elif str(source['season_year'])!=str(ending_year):issues.append('source_season_mismatch')
    except (TypeError,ValueError):issues.append('invalid_schedule_date')
    expected_type={'regular':'2','playoffs':'3'}.get(schedule.get('phase'))
    if expected_type and str(source['season_type'])!=expected_type:issues.append('source_phase_mismatch')
    return {'source':source,'issues':issues}


def _count(value):
    return type(value) is int and value>=0


def historical_shooting_view(game,*,allow_reconstructed_fgm=False):
    """Private current-parser or quarantined legacy view; source stays intact.

    Legacy FGM may be conditionally reconstructed from independently validated
    point components AND team FGM in a final game. FGA always remains unknown.
    Even reconstructed FGM is never marked complete shooting/calibration data.
    """
    result=deepcopy(game);fresh=game.get('shooting_parser_version')==PARSER_VERSION
    seen=set();duplicates=set()
    for row in game.get('players',[]):
        key=(row.get('team_abbrev'),str(row.get('espn_player_id')))
        if key in seen:duplicates.add(key)
        seen.add(key)
    team_checks={}
    for team in game.get('teams',[]):
        abbrev=team.get('team_abbrev') or team.get('abbreviation')
        rows=[r for r in game.get('players',[]) if r.get('team_abbrev')==abbrev and not r.get('dnp')]
        pair,_=observed_pair(team.get('stats',{}),'fg')
        derived=[];valid=bool(rows and pair[0] is not None)
        for r in rows:
            parts=[r.get(k) for k in ('points','fg3m','ftm')]
            if not all(_count(v) for v in parts) or (abbrev,str(r.get('espn_player_id'))) in duplicates:
                valid=False;derived.append(None);continue
            numerator=parts[0]-parts[1]-parts[2]
            fgm=numerator//2
            if numerator<0 or numerator%2 or fgm<parts[1]:valid=False
            derived.append(fgm)
        reconstructed=bool(game.get('status')=='STATUS_FINAL' and valid and sum(v for v in derived if v is not None)==pair[0])
        direct=bool(rows and pair[0] is not None and all(_count(r.get('fgm')) and _count(r.get('fga')) for r in rows)
                    and sum(r['fgm'] for r in rows)==pair[0] and sum(r['fga'] for r in rows)==pair[1])
        other_ok=True
        for family,keys in (('three',('fg3m','fg3a')),('ft',('ftm','fta'))):
            counts,_=observed_pair(team.get('stats',{}),family)
            other_ok &= bool(counts[0] is not None and all(_count(r.get(k)) for r in rows for k in keys)
                             and tuple(sum(r[k] for r in rows) for k in keys)==counts)
        team_checks[abbrev]={'reconstructed_fgm_reconciles':reconstructed,'direct_fg_reconciles':direct,'independent_three_ft_reconcile':other_ok}
    for source_row,row in zip(game.get('players',[]),result.get('players',[]),strict=True):
        key=(row.get('team_abbrev'),str(row.get('espn_player_id')));team=team_checks.get(row.get('team_abbrev'),{})
        metadata=row.get('shooting_validation',{})
        numeric=all(_count(row.get(k)) for k in ('points','fgm','fga','fg3m','fg3a','ftm','fta'))
        numeric = numeric and all(row[m]<=row[a] for m,a in (('fgm','fga'),('fg3m','fg3a'),('ftm','fta'))) and not row_issues({**row,'points_observed':row.get('points')})
        identity=bool(row.get('espn_player_id') and row.get('team_abbrev'))
        usable=bool(numeric and identity and fresh and game.get('status')=='STATUS_FINAL' and not game.get('source_identity',{}).get('issues',['unknown_source_identity'])
                    and key not in duplicates and not row.get('dnp') and metadata.get('row_usable') and team.get('direct_fg_reconciles') and team.get('independent_three_ft_reconcile'))
        row['historical_shooting']={'parser_version':game.get('shooting_parser_version'),'usable_complete_shooting':usable,
            'team_checks':dict(team),'status':'current_parsed' if fresh else 'legacy_fg_quarantined','duplicate_identity':key in duplicates}
        if not fresh:
            original=source_row.get('historical_shooting',{}).get('original_fg')
            row['historical_shooting']['original_fg']=deepcopy(original) if original is not None else {'fgm':row.get('fgm'),'fga':row.get('fga')}
            row['fgm']=None;row['fga']=None
            if row.get('dnp'):row['historical_shooting']['status']='dnp_legacy_fg_unknown'
            elif allow_reconstructed_fgm and type(row.get('minutes')) in (int,float) and row['minutes']>0 and team.get('reconstructed_fgm_reconciles'):
                row['fgm']=(row['points']-row['fg3m']-row['ftm'])//2
                row['historical_shooting']['status']='fgm_conditionally_reconstructed_fga_unknown'
    result['historical_shooting_view']={'version':PARSER_VERSION,'source_rewritten':False,'teams':team_checks,
        'complete_shooting_requires':'current source identity, final status, unique row, row invariants and team total-FG makes/attempts reconciliation'}
    return result
