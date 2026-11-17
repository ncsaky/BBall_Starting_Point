"""Read-only chart census; writes only its own report and rendering fixtures."""
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean

from nba_gm_data.shot_chart import chart_model
from nba_gm_data.spatial import player_spatial_profile, team_spatial_profile
from nba_gm_data.utils import normalize_name

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/heatmap-audit-2026-10-24"
BASELINE = ROOT / "data/canonical/baselines/2026-10-23-forward-tuning-v5.json.gz"


def summarize(profile):
    chart = profile["shot_chart"]
    output = {}
    for side, field, density in [("offense", "delta_pp", 3), ("defense", "suppression_delta_pp", 4)]:
        regions = {r["id"]: r for r in chart["regions"]}
        visible = [c for c in chart["cells"] if c[density] >= .000025]
        mass = sum(c[density] for c in visible) or 1
        gray = lambda c, threshold: abs(regions[c[2]][field]) <= threshold
        output[side] = {
            "old_gray_cell_fraction": mean(gray(c, 3) for c in visible),
            "old_gray_density_fraction": sum(c[density] for c in visible if gray(c, 3)) / mass,
            "within_half_pp_density_fraction": sum(c[density] for c in visible if gray(c, .5)) / mass,
            "min_delta_pp": min(r[field] for r in regions.values()),
            "max_delta_pp": max(r[field] for r in regions.values()),
            "density_sum": sum(c[density] for c in chart["cells"]),
        }
    output["three_share"] = sum(r["frequency"] for r in chart["regions"] if 10 <= r["id"] <= 14)
    output["comparables"] = chart.get("comparables", [])
    return output


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(BASELINE.read_bytes()).hexdigest()
    with gzip.open(BASELINE, "rt") as handle:
        canonical = json.load(handle)
    canonical["_allow_internal_caches"] = True
    selected = {normalize_name(name) for name in ("Michael Porter Jr.", "Stephen Curry", "Rudy Gobert", "Nikola Jokic", "Giannis Antetokounmpo", "Duncan Robinson", "Keyonte George", "Victor Wembanyama")}
    rows, fixtures = [], []
    for player in canonical["players"]:
        profile = player_spatial_profile(canonical, player, include_chart=True)
        rows.append({"name": player["name"], "id": player["id"], **summarize(profile)})
        if normalize_name(player["name"]) in selected:
            fixtures.append({"name": player["name"], "profile": profile})
    teams = []
    for team in canonical["teams"]:
        abbrev = team.get("abbrev") or team.get("id")
        profile = team_spatial_profile(canonical, team["id"], include_chart=True)
        assert profile["shot_chart"]["basis"] == "projected", abbrev
        teams.append({"team": abbrev, **summarize(profile)})
        if abbrev in {"TOR", "GSW", "DEN"}:
            fixtures.append({"name": f"{abbrev} team", "profile": profile})
    model = chart_model()
    report = {"baseline": str(BASELINE), "sha256": digest, "players": len(rows), "teams": len(teams),
              "reference_players": len(model["profiles"]), "reference_season": model["season"],
              "mean_old_gray_density": {side: mean(row[side]["old_gray_density_fraction"] for row in rows) for side in ("offense", "defense")},
              "mean_half_pp_density": {side: mean(row[side]["within_half_pp_density_fraction"] for row in rows) for side in ("offense", "defense")},
              "all_gray_players": {side: [r["name"] for r in rows if r[side]["old_gray_cell_fraction"] == 1] for side in ("offense", "defense")},
              "player_rows": rows, "team_rows": teams, "model_limitations": model.get("limitations", [])}
    (OUT / "census.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "profiles.json").write_text(json.dumps(fixtures) + "\n")
    assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == digest
    print(json.dumps({key: value for key, value in report.items() if key not in {"player_rows", "team_rows", "all_gray_players"}}, indent=2))
    print("Selected players:", json.dumps([r for r in rows if normalize_name(r["name"]) in selected], indent=2))


if __name__ == "__main__":
    main()
