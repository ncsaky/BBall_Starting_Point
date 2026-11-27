"""Historical NBA seasons plus save-owned seasons; never alters ownership."""
from functools import lru_cache
import json
from pathlib import Path
from .resource_paths import game_resource_root
from .research import ESPN_TEAM_ID_TO_ABBREV

@lru_cache(maxsize=4)
def _records(path: str, modified: int):
    data=json.loads(Path(path).read_text())
    records=data.get('players',{})
    names={str(row.get('name','')).casefold():row for row in records.values()}
    return records,names

def career_record(player):
    path=game_resource_root()/'data/research/player_career_stats.json'
    if not path.exists(): return {}
    records,names=_records(str(path),path.stat().st_mtime_ns)
    return records.get(str(player.get('espn_player_id'))) or names.get(str(player.get('name','')).casefold()) or {}

def season_summary(totals, season, team_games=None):
    games=int(totals.get('games') or 0); divisor=max(1,games)
    result={'season':season,'games':games,'team_games':team_games}
    result['team_abbrevs']=list(dict.fromkeys([
        *totals.get('team_abbrevs', []),
        *[ESPN_TEAM_ID_TO_ABBREV[str(team)] for team in totals.get('team_ids', []) if str(team) in ESPN_TEAM_ID_TO_ABBREV],
        *([totals['team_abbrev']] if totals.get('team_abbrev') else []),
    ]))
    for key,source in [('mpg','minutes'),('ppg','points'),('rpg','rebounds'),('apg','assists'),('spg','steals'),('bpg','blocks'),('topg','turnovers'),('fga_per_game','fga'),('fg3m_per_game','fg3m'),('fg3a_per_game','fg3a'),('fta_per_game','fta')]:
        result[key]=round(float(totals.get(source) or 0)/divisor,1)
    for key,made,attempts in [('fg_pct','fgm','fga'),('fg3_pct','fg3m','fg3a'),('ft_pct','ftm','fta')]:
        result[key]=round(float(totals.get(made) or 0)/float(totals[attempts])*100,1) if totals.get(attempts) else None
    return result

def playoff_summary(totals, season, playoff_state):
    """A player's line for one postseason (None when he did not appear in it)."""
    if not totals or not int(totals.get('games') or 0): return None
    team=totals.get('team_id')
    played=sum(1 for game in (playoff_state or {}).get('games',[]) if team and team in (game.get('home_team_id'),game.get('away_team_id')))
    return season_summary(totals,season,played or None)

def player_career_seasons(player, save, current, save_path=None):
    """Season rows, newest first. A season the save played carries that postseason's line under ``playoffs``."""
    from .season_archive import full_season_history
    # Seasons older than last season keep their player totals in the season archive files (SEASON-ARCHIVE).
    history=full_season_history(save_path, save)
    current_label=str(save.get('meta',{}).get('season') or current.get('season') or '')
    starts=[int(str(row['season']).split('-')[0]) for row in history if str(row.get('season','')).split('-')[0].isdigit()]
    if current_label.split('-')[0].isdigit(): starts.append(int(current_label.split('-')[0]))
    cutoff=min(starts) if starts else 2026
    rows={}
    for row in career_record(player).get('seasons',[]):
        if int(row['season'].split('-')[0])<cutoff:
            rows[row['season']]=season_summary(row,row['season'],row.get('team_games'))
    # Existing rollover snapshots already preserve every simulated season.
    # Read those immutable totals instead of creating duplicate history data.
    for snapshot in history:
        totals=(snapshot.get('player_season_stats') or {}).get(player['id'])
        playoffs=playoff_summary((snapshot.get('playoff_player_stats') or {}).get(player['id']),snapshot['season'],snapshot.get('playoff_state'))
        if totals is None and playoffs is None: continue
        counts=[int(r.get('wins') or 0)+int(r.get('losses') or 0) for r in (snapshot.get('team_records') or {}).values()]
        rows[snapshot['season']]=season_summary(totals or {},snapshot['season'],max(counts,default=None))
        if playoffs: rows[snapshot['season']]['playoffs']=playoffs
    totals=(save.get('player_season_stats') or {}).get(player['id'], {})
    teams=season_summary(totals,current_label)['team_abbrevs']
    rows[current_label]={**current,'season':current_label,'team_abbrevs':teams or current.get('team_abbrevs', [])}
    playoffs=playoff_summary((save.get('playoff_player_stats') or {}).get(player['id']),current_label,save.get('playoff_state'))
    if playoffs: rows[current_label]['playoffs']=playoffs
    return sorted(rows.values(),key=lambda row:row['season'],reverse=True)
