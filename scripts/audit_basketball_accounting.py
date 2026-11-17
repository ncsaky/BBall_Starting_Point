"""Audit seeded fixed-roster seasons on disposable saves, not career balance."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import tempfile

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.box_score import opportunity_errors
from nba_gm_data.save import canonical_with_save, create_league_save, load_save, schedule_for_save
from nba_gm_data.schema import to_plain
from nba_gm_data.sim import build_sim_indices, load_sim_context, sim_game_with_context


SHOT_FIELDS = ("fgm", "fga", "fg3m", "fg3a", "ftm", "fta")
BOX_FIELDS = ("points", *SHOT_FIELDS, "rebounds", "assists", "turnovers", "steals", "blocks")


def game_errors(result):
    errors = []
    for row in [*result["player_lines"], *result["team_lines"]]:
        label = row.get("player_id") or row["team_id"]
        if row["points"] != 2*row["fgm"]+row["fg3m"]+row["ftm"]:
            errors.append(("shooting_points", label))
        if not (0 <= row["fg3m"] <= row["fg3a"] <= row["fga"] and
                0 <= row["fgm"] <= row["fga"] and 0 <= row["ftm"] <= row["fta"] and
                0 <= row["fgm"]-row["fg3m"] <= row["fga"]-row["fg3a"]):
            errors.append(("shooting_attempts", label))
        if any(row[key] < 0 or int(row[key]) != row[key] for key in BOX_FIELDS):
            errors.append(("negative_or_fractional_count", label))
    for team in result["team_lines"]:
        players = [row for row in result["player_lines"] if row["team_id"] == team["team_id"]]
        for key in BOX_FIELDS:
            if team[key] != sum(row[key] for row in players):
                errors.append(("team_player_sum", f"{team['team_id']}:{key}"))
        overtime = int(team.get("overtime_periods") or 0)
        if abs(sum(row["minutes"] for row in players)-(240+25*overtime)) > .1:
            errors.append(("team_minutes", team["team_id"]))
        if any(not 0 <= row["minutes"] <= 48+5*overtime for row in players):
            errors.append(("player_minutes", team["team_id"]))
        score = result["home_score"] if team["team_id"] == result["home_team_id"] else result["away_score"]
        if score != team["points"]:
            errors.append(("score_team_sum", team["team_id"]))
    if result["home_score"] == result["away_score"]:
        errors.append(("tied_final", result["game_id"]))
    errors.extend(opportunity_errors(result['player_lines'], result['team_lines']))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 19, 31])
    parser.add_argument("--compare", type=Path, help="Prior report; require identical game scores for all seeds")
    parser.add_argument("--save", nargs="+", type=Path, help="Read archived career box scores instead of simulating new seasons")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output path; existing evidence is preserved")
    if args.save and args.compare:
        parser.error("--compare is only available for seeded simulations")
    root = Path(__file__).resolve().parents[1]
    if args.save:
        report = {"mode":"read-only saved career accounting, including history archives", "saves":[], "errors":Counter(), "examples":{}}
        for path in args.save:
            save = load_save(path, include_history=True)
            games = save.get("game_results", [])
            if not games:
                parser.error(f"No box scores in {path}")
            for result in games:
                for category, detail in game_errors(result):
                    report["errors"][category] += 1
                    report["examples"].setdefault(category,{"save":str(path),"game_id":result["game_id"],"detail":detail})
            report["saves"].append({"path":str(path), "games":len(games), "state":save["state"]})
        report["errors"] = dict(report["errors"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+"\n")
        print(json.dumps(report, indent=2))
        return 1 if report["errors"] else 0
    canonical = load_app_canonical(root)
    report = {"mode":"sandbox-sim, fixed initial roster across full regular-season schedules",
              "limits":"No in-season trades, development or evolving health in this distribution run. Career actions are audited separately.",
              "sim_source_sha256":hashlib.sha256((root/'src/nba_gm_data/sim.py').read_bytes()).hexdigest(),
              "save_source_sha256":hashlib.sha256((root/'src/nba_gm_data/save.py').read_bytes()).hexdigest(),
              "seasons":[], "errors":Counter(), "examples":{}}
    with tempfile.TemporaryDirectory(prefix="nba-accounting-") as tmp:
        for seed in args.seeds:
            save = create_league_save(root, canonical, "GSW", Path(tmp)/f"seed-{seed}.json", seed=seed)
            context = load_sim_context(root, canonical_with_save(canonical, save))
            context["schedule"] = schedule_for_save(root, save)
            appearances = Counter(str(team) for game in context["schedule"] if game.get("phase")=="regular"
                                  for team in [game["homeTeamId"],game["awayTeamId"]])
            context["indices"] = build_sim_indices(context)
            scores, totals, wins, overtime_games = [], Counter(), Counter(), 0
            per_game, margins, player_points = [], [], []
            for game in context["schedule"]:
                if game.get("phase") != "regular":
                    continue
                result = to_plain(sim_game_with_context(context, str(game["externalGameId"]), mode="sandbox-sim", seed=seed))
                scores.append([result["game_id"], result["home_score"], result["away_score"]])
                margins.append(abs(result["home_score"]-result["away_score"]))
                overtime_games += any(team.get("overtime_periods") for team in result["team_lines"])
                for category, detail in game_errors(result):
                    report["errors"][category] += 1
                    report["examples"].setdefault(category,{"seed":seed,"game_id":result["game_id"],"detail":detail})
                wins[result["home_team_id"] if result["home_score"]>result["away_score"] else result["away_team_id"]] += 1
                for team in result["team_lines"]:
                    per_game.append(team["points"])
                    totals.update({key:team[key] for key in BOX_FIELDS})
                player_points.extend(row["points"] for row in result["player_lines"])
            team_games = len(scores)*2
            report["seasons"].append({"seed":seed,"games":len(scores),"overtime_games":overtime_games,
                "scheduled_games_per_team":dict(appearances),
                "points_per_team_game":statistics.mean(per_game),"margin_mean":statistics.mean(margins),
                "player_single_game_points_max":max(player_points),"team_wins":dict(wins),
                "box_per_team_game":{key:value/team_games for key,value in totals.items()},
                "shooting_pct":{key:totals[made]/max(1,totals[attempts])*100 for key,made,attempts in
                    [("fg","fgm","fga"),("three","fg3m","fg3a"),("ft","ftm","fta")]},"scores":scores})
            print(f"Seed {seed}: {len(scores)} games, {overtime_games} OT, {statistics.mean(per_game):.2f} PPG",flush=True)
    if args.compare:
        before = json.loads(args.compare.read_text())
        prior = {row["seed"]:row["scores"] for row in before["seasons"]}
        assert all(row["scores"] == prior[row["seed"]] for row in report["seasons"]), "Game outcomes changed"
        report["scores_and_winners_exact_match"] = True
    report["errors"] = dict(report["errors"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"errors":report["errors"],"examples":report["examples"]},indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
