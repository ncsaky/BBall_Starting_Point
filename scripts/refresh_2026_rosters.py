#!/usr/bin/env python3
"""Fetch all official team rosters; fail closed if any team is unavailable."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import update_2026_offseason_snapshot as snapshot

DATE = "2026-10-13"
ROOT = Path(__file__).resolve().parents[1]

def main():
    urls = [snapshot.NBA_TEAM_URL.format(team_id=i, slug=s) for i, s in snapshot.TEAMS.values()]
    with ThreadPoolExecutor(max_workers=6) as pool:
        pages = dict(zip(urls, pool.map(snapshot.fetch, urls)))
    snapshot.fetch = pages.__getitem__
    snapshot.SNAPSHOT_DATE = DATE
    result = snapshot.official_rosters()
    result["source"]["id"] = "src_nba_official_rosters_2026_10_13"
    assert result["team_count"] == 30
    assert not result["duplicate_cross_team_rows"], result["duplicate_cross_team_rows"]
    assert all(team["roster"] for team in result["teams"])
    path = ROOT / "data/research/nba_official_rosters_2026_10_13.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"teams": result["team_count"], "players": result["player_count"], "path": str(path)}))

if __name__ == "__main__":
    main()
