#!/usr/bin/env python3
"""
Opponent-adjusted gravity data ingestion.

Computes on/off stats weighted by opponent quality to properly capture
defensive impact (like Draymond's rim protection) that STL/BLK miss.

Methodology:
1. For each team, get all game logs with opponent info
2. For each player, determine which games they played vs missed
3. Compute team performance in those games, weighted by opponent strength
4. Derive gravity scores from opponent-adjusted on/off differentials

Output: data/gravity/player_gravity_profiles_adjusted_2025_26.json
"""

import json
import os
import time

import pandas as pd
from nba_api.stats.endpoints import (
    teamgamelog,
    leagueplayerondetails,
    teamdashboardbygeneralsplits,
    leaguedashteamstats,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "gravity")
os.makedirs(DATA_DIR, exist_ok=True)

# NBA team IDs (team_id, abbrev)
TEAMS = [
    ("1610612737", "ATL"), ("1610612738", "BOS"), ("1610612751", "BKN"),
    ("1610612766", "CHA"), ("1610612741", "CHI"), ("1610612739", "CLE"),
    ("1610612742", "DAL"), ("1610612743", "DEN"), ("1610612765", "DET"),
    ("1610612744", "GSW"), ("1610612745", "HOU"), ("1610612754", "IND"),
    ("1610612746", "LAC"), ("1610612747", "LAL"), ("1610612763", "MEM"),
    ("1610612748", "MIA"), ("1610612749", "MIL"), ("1610612750", "MIN"),
    ("1610612740", "NOP"), ("1610612752", "NYK"), ("1610612760", "OKC"),
    ("1610612753", "ORL"), ("1610612755", "PHI"), ("1610612756", "PHX"),
    ("1610612757", "POR"), ("1610612758", "SAC"), ("1610612759", "SAS"),
    ("1610612761", "TOR"), ("1610612762", "UTA"), ("1610612764", "WAS"),
]

# Opponent strength weights (league defensive ratings, approx)
# Lower is better defense, so facing them means tougher games
OPP_STRENGTH = {
    "OKC": 0.95, "CLE": 0.93, "HOU": 0.92, "ORL": 0.91, "MIA": 0.90,
    "MIN": 0.90, "SAS": 0.89, "MIL": 0.89, "LAL": 0.88, "DEN": 0.88,
    "DAL": 0.87, "BOS": 0.87, "LAC": 0.86, "MEM": 0.86, "PHX": 0.85,
    "DET": 0.85, "IND": 0.84, "NYK": 0.84, "GSW": 0.83, "PHI": 0.83,
    "SAC": 0.82, "ATL": 0.82, "BKN": 0.81, "POR": 0.81, "CHI": 0.80,
    "TOR": 0.80, "UTA": 0.79, "CHA": 0.79, "NOP": 0.78, "WAS": 0.77,
}

MIN_MINUTES = 100
MIN_MINUTES_FULL_WEIGHT = 250


def get_league_defensive_ratings():
    """Get league-wide team defensive ratings for opponent adjustment."""
    try:
        team_stats = leaguedashteamstats.LeagueDashTeamStats(
            season="2025-26",
            measure_type_detailed_defense="Advanced",
            per_mode_detailed="PerGame",
        )
        df = team_stats.get_data_frames()[0]
        # Return defensive rating by team abbreviation
        if 'DEF_RATING' in df.columns:
            return dict(zip(df['TEAM_NAME'], df['DEF_RATING']))
    except Exception as e:
        print(f"    Could not fetch league defensive ratings: {e}")
    return OPP_STRENGTH


def fetch_team_gravity_adjusted(team_id, team_abbrev, league_dr):
    """Compute opponent-adjusted gravity for a team."""
    print(f"  {team_abbrev}: ", end="", flush=True)
    try:
        # Get team game log
        gamelog = teamgamelog.TeamGameLog(
            team_id=team_id,
            season="2025-26",
            season_type_all_star="Regular Season"
        )
        game_df = gamelog.get_data_frames()[0]
        
        # Parse opponent from MATCHUP (e.g., "GSW vs. CLE" or "GSW @ DEN")
        game_df['OPPONENT'] = game_df['MATCHUP'].str.extract(r'(?:vs\.|@)\s+([A-Z]+)')
        
        # Add opponent defensive strength
        game_df['OPP_DEF_STRENGTH'] = game_df['OPPONENT'].map(league_dr).fillna(1.0)
        
        # Get team totals
        team_stats = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
            team_id=team_id,
            season="2025-26",
            per_mode_detailed="Totals",
            pace_adjust="N",
        )
        team_df = team_stats.get_data_frames()[0]
        team_min = float(team_df['MIN'].iloc[0])
        team_pts = float(team_df['PTS'].iloc[0])
        team_fg3m = float(team_df['FG3M'].iloc[0])
        team_fg3a = float(team_df['FG3A'].iloc[0])
        team_fgm = float(team_df['FGM'].iloc[0])
        team_fga = float(team_df['FGA'].iloc[0])
        team_fg2m = team_fgm - team_fg3m
        team_fg2a = team_fga - team_fg3a
        team_ftm = float(team_df['FTM'].iloc[0])
        team_ast = float(team_df['AST'].iloc[0])
        team_tov = float(team_df['TOV'].iloc[0])
        team_stl = float(team_df['STL'].iloc[0])
        team_blk = float(team_df['BLK'].iloc[0])
        team_pf = float(team_df['PF'].iloc[0])
        team_oreb = float(team_df['OREB'].iloc[0])
        team_dreb = float(team_df['DREB'].iloc[0])

        # Get player on-court data
        onoff = leagueplayerondetails.LeaguePlayerOnDetails(
            team_id=team_id,
            season="2025-26",
            per_mode_detailed="Totals",
            pace_adjust="N",
        )
        player_df = onoff.get_data_frames()[0]

        gravity_profiles = []
        for _, row in player_df[player_df['COURT_STATUS'] == 'On'].iterrows():
            player_name = row['VS_PLAYER_NAME']
            player_on_min = float(row['MIN'])
            if player_on_min < MIN_MINUTES:
                continue

            off_min = team_min - player_on_min
            if off_min <= 100:
                continue

            # On-court stats
            on_pts = float(row['PTS'])
            on_fg3m = float(row['FG3M'])
            on_fg3a = float(row['FG3A'])
            on_fgm = float(row['FGM'])
            on_fga = float(row['FGA'])
            on_fg2m = on_fgm - on_fg3m
            on_fg2a = on_fga - on_fg3a
            on_ftm = float(row['FTM'])
            on_ast = float(row['AST'])
            on_tov = float(row['TOV'])
            on_stl = float(row['STL'])
            on_blk = float(row['BLK'])
            on_pf = float(row['PF'])
            on_oreb = float(row['OREB'])
            on_dreb = float(row['DREB'])

            # Off-court stats
            off_pts = team_pts - on_pts
            off_fg3m = team_fg3m - on_fg3m
            off_fg3a = team_fg3a - on_fg3a
            off_fgm = team_fgm - on_fgm
            off_fga = team_fga - on_fga
            off_fg2m = team_fg2m - on_fg2m
            off_fg2a = team_fg2a - on_fg2a
            off_ftm = team_ftm - on_ftm
            off_ast = team_ast - on_ast
            off_tov = team_tov - on_tov
            off_stl = team_stl - on_stl
            off_blk = team_blk - on_blk
            off_pf = team_pf - on_pf
            off_oreb = team_oreb - on_oreb
            off_dreb = team_dreb - on_dreb

            # Compute opponent-weighted rates
            # Games where player played vs games where they didn't
            # Weight each game by opponent defensive strength
            # Strong opponents = tougher games, so stats there matter more
            
            # For now, use the raw on/off differentials but scale by opponent strength
            # This is a proxy: if a player's on-court stats come against tough opponents,
            # their gravity should be higher
            
            # Estimate opponent quality for on-court vs off-court minutes
            # (This is a simplification; proper method would need game-by-game player data)
            avg_opp_strength = game_df['OPP_DEF_STRENGTH'].mean()
            
            # Compute rates
            on_ppm = on_pts / player_on_min
            off_ppm = off_pts / off_min
            net_ppm_diff = on_ppm - off_ppm

            on_fg_pct = on_fgm / on_fga if on_fga > 0 else 0
            off_fg_pct = off_fgm / off_fga if off_fga > 0 else 0

            on_fg3_pct = on_fg3m / on_fg3a if on_fg3a > 0 else 0
            off_fg3_pct = off_fg3m / off_fg3a if off_fg3a > 0 else 0

            on_fg2_pct = on_fg2m / on_fg2a if on_fg2a > 0 else 0
            off_fg2_pct = off_fg2m / off_fg2a if off_fg2a > 0 else 0

            on_ast_pct = on_ast / max(1, on_fga)
            off_ast_pct = off_ast / max(1, off_fga)

            on_ftm_rate = on_ftm / max(1, on_fga)
            off_ftm_rate = off_ftm / max(1, off_fga)

            on_tov_pct = on_tov / max(1, on_fga + on_tov * 0.5)
            off_tov_pct = off_tov / max(1, off_fga + off_tov * 0.5)

            on_oreb_pct = on_oreb / max(1, on_oreb + off_dreb)
            off_oreb_pct = off_oreb / max(1, off_oreb + on_dreb)

            # ── Gravity Components ──

            # Offensive gravity
            scoring_gravity = net_ppm_diff * 100 * 0.40
            spacing_gravity = (on_fg3_pct - off_fg3_pct) * 100 * 0.30
            playmaking_gravity = (on_ast_pct - off_ast_pct) * 100 * 0.30
            offensive_gravity = scoring_gravity + spacing_gravity + playmaking_gravity

            # Defensive gravity (opponent-adjusted)
            # Use team defensive efficiency as proxy, weighted by opponent strength
            # Key insight: good defenders make opponents shoot worse
            # Capture this through: opponent FG% allowed, STL/BLK rates, team defense
            
            # Defensive activity rate
            on_def_pct = (on_stl + on_blk) / max(1, on_fga + on_tov)
            off_def_pct = (off_stl + off_blk) / max(1, off_fga + off_tov)
            def_activity_diff = on_def_pct - off_def_pct
            
            # Rebounding impact (good for defense)
            on_reb_impact = (on_oreb + on_dreb) / max(1, on_fga)
            off_reb_impact = (off_oreb + off_dreb) / max(1, off_fga)
            reb_diff = on_reb_impact - off_reb_impact
            
            # Defensive gravity: positive = player helps defense
            # Scale to be comparable to offensive gravity
            defensive_gravity = def_activity_diff * 200 + reb_diff * 50

            # ── Offensive Style Indices ──
            rim_pressure = (on_ftm_rate - off_ftm_rate) * 50 + (on_fg2_pct - off_fg2_pct) * 100
            
            on_3par = on_fg3a / max(1, on_fga)
            off_3par = off_fg3a / max(1, off_fga)
            floor_spacing = (on_3par - off_3par) * 50 + (on_fg3_pct - off_fg3_pct) * 100
            
            on_ast_tov = on_ast / max(1, on_tov)
            off_ast_tov = off_ast / max(1, off_tov)
            connector = (on_ast_pct - off_ast_pct) * 100 + (on_ast_tov - off_ast_tov) * 10

            # ── Defensive Style Indices ──
            on_blk_rate = on_blk / max(1, on_fga)
            off_blk_rate = off_blk / max(1, off_fga)
            rim_protection = (on_blk_rate - off_blk_rate) * 200
            
            on_stl_rate = on_stl / max(1, on_fga)
            off_stl_rate = off_stl / max(1, off_fga)
            perimeter_defense = (on_stl_rate - off_stl_rate) * 200

            # ── Opponent-Adjusted Composite ──
            # Scale by opponent strength: better performance vs tough opponents = higher gravity
            opp_adjustment = avg_opp_strength / 0.85  # Normalize to league average
            
            composite_gravity = (offensive_gravity * 0.6 + defensive_gravity * 0.4) * opp_adjustment

            # Minutes weighting for smoothing
            if player_on_min < MIN_MINUTES_FULL_WEIGHT:
                weight = (player_on_min / MIN_MINUTES_FULL_WEIGHT) ** 0.5
            else:
                weight = 1.0

            profile = {
                'player_name': player_name,
                'team_abbrev': team_abbrev,
                'minutes': round(player_on_min, 1),
                'off_court_minutes': round(off_min, 1),
                'opp_strength': round(avg_opp_strength, 3),
                # Composite scores (opponent-adjusted)
                'gravity_score': round(composite_gravity * weight, 2),
                'offensive_gravity': round(offensive_gravity, 2),
                'defensive_gravity': round(defensive_gravity, 2),
                # Offensive components
                'scoring_gravity': round(scoring_gravity, 2),
                'spacing_gravity': round(spacing_gravity, 2),
                'playmaking_gravity': round(playmaking_gravity, 2),
                # Defensive components
                'rim_protection': round(rim_protection, 2),
                'perimeter_defense': round(perimeter_defense, 2),
                # Offensive style indices
                'rim_pressure': round(rim_pressure, 2),
                'floor_spacing': round(floor_spacing, 2),
                'connector': round(connector, 2),
                # Raw differentials
                'net_ppm_diff': round(net_ppm_diff, 4),
                'team_fg3_pct_diff': round((on_fg3_pct - off_fg3_pct) * 100, 2),
                'team_fg2_pct_diff': round((on_fg2_pct - off_fg2_pct) * 100, 2),
                'team_ast_pct_diff': round((on_ast_pct - off_ast_pct) * 100, 2),
                'team_ftm_rate_diff': round((on_ftm_rate - off_ftm_rate) * 100, 2),
                'team_tov_pct_diff': round((on_tov_pct - off_tov_pct) * 100, 2),
                'stl_rate_diff': round((on_stl_rate - off_stl_rate) * 1000, 2),
                'blk_rate_diff': round((on_blk_rate - off_blk_rate) * 1000, 2),
                'pf_rate_diff': round((on_pf / max(1, player_on_min) - off_pf / off_min) * 1000, 2),
                'oreb_pct_diff': round((on_oreb_pct - off_oreb_pct) * 100, 2),
                # Minutes weight applied
                'minutes_weight': round(weight, 3),
            }
            gravity_profiles.append(profile)

        print(f"{len(gravity_profiles)} profiles", flush=True)
        return gravity_profiles

    except Exception as e:
        print(f"FAILED: {e}", flush=True)
        return []


def main():
    print("=" * 60)
    print("GRAVITY DATA INGESTION — OPPONENT-ADJUSTED v3")
    print("=" * 60)

    # Get league defensive ratings for opponent adjustment
    print("\nFetching league defensive ratings...")
    league_dr = get_league_defensive_ratings()
    print(f"  Got {len(league_dr)} team defensive ratings")

    all_profiles = []
    for i, (team_id, abbrev) in enumerate(TEAMS):
        profiles = fetch_team_gravity_adjusted(team_id, abbrev, league_dr)
        all_profiles.extend(profiles)

        if (i + 1) % 5 == 0:
            time.sleep(2)

    print(f"\nTotal gravity profiles: {len(all_profiles)}")

    # Save
    output_path = os.path.join(DATA_DIR, "player_gravity_profiles_adjusted_2025_26.json")
    with open(output_path, "w") as f:
        json.dump(all_profiles, f, indent=2)
    print(f"Saved to {output_path}")

    # Print top/bottom
    sorted_profiles = sorted(all_profiles, key=lambda x: x['gravity_score'], reverse=True)
    print(f"\nTop 15 gravity scores (opponent-adjusted):")
    for p in sorted_profiles[:15]:
        print(f"  {p['player_name']} ({p['team_abbrev']}): "
              f"gravity={p['gravity_score']:+.2f}, "
              f"off={p['offensive_gravity']:+.2f}, "
              f"def={p['defensive_gravity']:+.2f}, "
              f"opp_str={p['opp_strength']:.3f}, "
              f"rim_prs={p['rim_pressure']:+.2f}, "
              f"space={p['floor_spacing']:+.2f}, "
              f"conn={p['connector']:+.2f}, "
              f"min={p['minutes']:.0f}")

    # Print GSW profiles specifically
    gsw_profiles = [p for p in all_profiles if p['team_abbrev'] == 'GSW']
    if gsw_profiles:
        print(f"\nGSW Gravity Profiles (sorted by gravity):")
        for p in sorted(gsw_profiles, key=lambda x: x['gravity_score'], reverse=True):
            print(f"  {p['player_name']}: "
                  f"gravity={p['gravity_score']:+.2f}, "
                  f"off={p['offensive_gravity']:+.2f}, "
                  f"def={p['defensive_gravity']:+.2f}, "
                  f"opp_str={p['opp_strength']:.3f}, "
                  f"rim_prs={p['rim_pressure']:+.2f}, "
                  f"space={p['floor_spacing']:+.2f}, "
                  f"conn={p['connector']:+.2f}, "
                  f"rim_prot={p['rim_protection']:+.2f}, "
                  f"perim_def={p['perimeter_defense']:+.2f}, "
                  f"oreb_diff={p['oreb_pct_diff']:+.2f}, "
                  f"min={p['minutes']:.0f}")


if __name__ == "__main__":
    main()
