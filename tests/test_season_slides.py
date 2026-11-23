"""Season slideshows: award rules (65-game rule, Sixth Man, Most Improved, All-NBA, Finals MVP), trade and
coaching-change ranking, per-stint continuity (traded players, new saves) and opens-once behaviour."""
from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.save import (
    AWARD_MIN_GAMES,
    award_finals_mvp,
    award_qualifying_games,
    count_award_game,
    create_league_save,
    finals_game_score,
    generate_league_awards,
    team_top_minutes_ids,
    update_playoff_player_stats,
)
from nba_gm_data.season_slides import (
    available_slideshows,
    coaching_changes,
    continuity_rows,
    roster_note,
    last_season_context,
    mark_seen,
    outlook_due,
    pending_slideshow,
    rank_trades,
    real_season_summary,
    stored_recap,
    team_postseason_results,
    team_stint_minutes,
    trade_receipts,
)

ROOT = Path(__file__).resolve().parents[1]


def season_line(games=72, minutes=2400.0, points=1500, rebounds=400, assists=300, steals=70, blocks=40,
                g20=None, g15=0, bench=None, top=None, team_id="team_gsw"):
    row = {"games": games, "minutes": minutes, "points": points, "rebounds": rebounds, "assists": assists,
           "steals": steals, "blocks": blocks, "turnovers": 100, "team_id": team_id}
    row["games_20_min"] = games if g20 is None else g20
    row["games_15_min"] = g15
    row["games_top_minutes"] = games if top is None else top
    row["games_bench"] = 0 if bench is None else bench
    return row


class AwardRuleTests(unittest.TestCase):
    def test_qualifying_games_follow_the_65_game_rule(self):
        self.assertEqual(award_qualifying_games({"games_20_min": 63, "games_15_min": 5}), 65)  # two 15-20 games count
        self.assertEqual(award_qualifying_games({"games_20_min": 62, "games_15_min": 1}), 63)
        self.assertEqual(award_qualifying_games({"games": 70}), 70)  # totals recorded before the counters existed
        self.assertEqual(AWARD_MIN_GAMES, 65)

    def test_bench_games_are_games_outside_the_top_five_in_minutes(self):
        lines = [{"player_id": f"p{i}", "team_id": "A", "minutes": 40 - i, "points": 10} for i in range(8)]
        lines += [{"player_id": "q0", "team_id": "B", "minutes": 30, "points": 5}, {"player_id": "dnp", "team_id": "B", "minutes": 0}]
        top = team_top_minutes_ids(lines)
        self.assertEqual(top, {"p0", "p1", "p2", "p3", "p4", "q0"})
        totals: dict = {}
        count_award_game(totals, {"player_id": "p6", "minutes": 17}, top)
        count_award_game(totals, {"player_id": "p6", "minutes": 22}, top)
        self.assertEqual((totals["games_20_min"], totals["games_15_min"], totals["games_bench"]), (1, 1, 2))
        self.assertNotIn("games_top_minutes", totals)

    def test_finals_game_score_and_finals_only_totals(self):
        self.assertAlmostEqual(finals_game_score({"points": 30, "fgm": 11, "fga": 20, "fta": 6, "ftm": 6, "rebounds": 10,
                                                  "assists": 5, "steals": 1, "blocks": 1, "turnovers": 3}), 30 + 4.4 - 14 + 4 + 1 + 3.5 + 0.7 - 3)
        save = {"playoff_state": {"round": "conference_finals"}}
        line = {"player_id": "p1", "team_id": "A", "points": 20, "minutes": 35}
        update_playoff_player_stats(save, {"game_id": "playoff_game_x-conference-finals-g1", "player_lines": [line]}, "2027-05-20")
        self.assertNotIn("nba_finals", save["playoff_player_stats"]["p1"])  # a conference final is not the Finals
        save["playoff_state"]["round"] = "finals"
        update_playoff_player_stats(save, {"game_id": "playoff_game_x-finals-finals-g1", "player_lines": [line]}, "2027-06-05")
        self.assertEqual(save["playoff_player_stats"]["p1"]["nba_finals"]["games"], 1)
        self.assertEqual(save["playoff_player_stats"]["p1"]["games"], 2)

    def test_finals_mvp_is_the_champions_best_finals_game_score(self):
        def totals(pid, team, finals_points, playoff_points):
            return {"player_id": pid, "player_name": pid, "team_id": team, "team_abbrev": team, "games": 20, "points": playoff_points,
                    "nba_finals": {"games": 6, "points": finals_points, "fgm": finals_points / 2.2, "fga": finals_points / 1.1}}
        save = {"meta": {"season": "2026-27"}, "state": {"current_date": "2027-06-14"},
                "playoff_state": {"champion_team_id": "A"},
                "playoff_player_stats": {"star": totals("star", "A", 120, 600),   # best over the whole playoffs
                                         "hero": totals("hero", "A", 170, 450),   # best in the Finals
                                         "loser": totals("loser", "B", 250, 700)}}
        award = award_finals_mvp(save)
        self.assertEqual(award["player_id"], "hero")
        self.assertEqual(award["finals_line"]["gp"], 6)
        self.assertEqual(save["finals_mvp"]["source"], "nba_finals_game_score")


class LeagueAwardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = load_app_canonical(ROOT)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = create_league_save(ROOT, cls.canonical, "GSW", Path(cls.tmp.name) / "awards.json", seed=31)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def player(self, name):
        return next(p for p in self.canonical["players"] if p["normalized_name"] == name)

    def awards_for(self, stats, *, history=None, season="2026-27"):
        save = deepcopy(self.base)
        save["player_season_stats"] = stats
        save["league_awards"] = []
        if history is not None:
            save["season_history"] = history
        return {row["award"] + (f":{row['player_id']}" if row["award"].startswith("ALL_NBA") else ""): row
                for row in generate_league_awards(self.canonical, save, season, seed=7)}

    def test_sixty_five_game_rule_sixth_man_and_all_nba(self):
        jokic, sga, brunson = self.player("nikola jokic"), self.player("shai gilgeous alexander"), self.player("jalen brunson")
        reid = self.player("naz reid")
        stats = {
            jokic["id"]: season_line(games=70, points=2100, rebounds=850, assists=700, team_id=jokic["team_id"]),
            # Huge numbers, but only 60 games of 20+ minutes: not eligible for MVP, DPOY, Sixth Man, MIP or All-NBA.
            sga["id"]: season_line(games=64, g20=60, g15=4, points=2300, team_id=sga["team_id"]),
            brunson["id"]: season_line(games=75, points=1900, team_id=brunson["team_id"]),
            # Off the bench in most games (outside his team's top five in minutes): the Sixth Man pool.
            reid["id"]: season_line(games=78, g20=70, g15=3, minutes=2100, points=1100, top=20, bench=58, team_id=reid["team_id"]),
        }
        awards = self.awards_for(stats)
        self.assertEqual(awards["MVP"]["player_id"], jokic["id"])
        self.assertNotIn(sga["id"], {row["player_id"] for row in awards.values()})
        self.assertEqual(awards["SMOY"]["player_id"], reid["id"])
        self.assertEqual(awards["SMOY"]["bench_games"], 58)
        all_nba = [row for key, row in awards.items() if key.startswith("ALL_NBA")]
        self.assertEqual(len(all_nba), 3)  # only three eligible players this time; positionless, in MVP-score order
        self.assertEqual({row["award"] for row in all_nba}, {"ALL_NBA_1"})
        self.assertEqual(min(all_nba, key=lambda row: row["vote_rank"])["player_id"], jokic["id"])
        self.assertTrue(all(row.get("criteria") for row in awards.values()))

    def test_rookie_of_the_year_is_exempt_from_the_65_game_rule(self):
        rookie = self.player("cooper flagg")
        stats = {rookie["id"]: season_line(games=50, g20=48, minutes=1600, points=1000, team_id=rookie["team_id"])}
        save = deepcopy(self.base)
        save["player_season_stats"] = stats
        save["incoming_rookies"] = [{"player_id": rookie["id"], "draft_year": 2025}]
        rows = {row["award"]: row for row in generate_league_awards(self.canonical, save, "2025-26", seed=3)}
        self.assertEqual(rows.get("ROTY", {}).get("player_id"), rookie["id"])
        self.assertNotIn("MVP", rows)

    def test_most_improved_compares_with_last_season(self):
        risen, steady = self.player("naz reid"), self.player("jalen brunson")
        previous = {risen["id"]: season_line(games=70, points=700, rebounds=300, assists=100),
                    steady["id"]: season_line(games=75, points=1900)}
        history = [{"season": "2026-27", "player_season_stats": previous}]
        stats = {risen["id"]: season_line(games=78, points=1500, rebounds=500, assists=200, team_id=risen["team_id"]),
                 steady["id"]: season_line(games=75, points=1950, team_id=steady["team_id"])}
        awards = self.awards_for(stats, history=history, season="2027-28")
        self.assertEqual(awards["MIP"]["player_id"], risen["id"])
        self.assertGreater(awards["MIP"]["production"], awards["MIP"]["previous_production"])

    def test_awards_are_generated_once_per_season(self):
        star = self.player("nikola jokic")
        save = deepcopy(self.base)
        save["player_season_stats"] = {star["id"]: season_line(team_id=star["team_id"])}
        save["league_awards"] = []
        first = generate_league_awards(self.canonical, save, "2026-27", seed=1)
        count = len(save["league_awards"])
        second = generate_league_awards(self.canonical, save, "2026-27", seed=99)
        self.assertEqual(len(save["league_awards"]), count)
        self.assertEqual(sorted(r["id"] for r in first), sorted(r["id"] for r in second))


class RankingTests(unittest.TestCase):
    def log(self, tid, involved, nets, teams=("team_a", "team_b")):
        return {"id": tid, "transaction_type": "trade", "teams": list(teams), "date": "2027-01-10",
                "assets": {"from_assets": [{"kind": "player", "id": f"{tid}-p1", "label": "P1"}],
                           "to_assets": [{"kind": "pick", "id": f"{tid}-k", "label": "Pick"}]},
                "evaluations": [{"perspective_team_id": team, "incoming_value": inc, "net_value": net}
                                for team, inc, net in zip(teams, involved, nets)]}

    def test_trades_rank_by_value_involved_or_value_swing_whichever_is_higher(self):
        logs = [
            self.log("big", (60, 58), (2, 1)),        # most value changed hands
            self.log("lopsided", (20, 25), (30, 18)),  # biggest swing
            self.log("middle", (40, 35), (8, 6)),      # second on both lists
            self.log("small", (5, 4), (1, 1)),
        ]
        ranked = rank_trades(logs)
        self.assertEqual([row["log"]["id"] for row in ranked], ["big", "lopsided", "middle"])
        self.assertEqual(ranked[0]["ranked_by"], "value exchanged")
        self.assertEqual(ranked[1]["ranked_by"], "value swing")

    def test_trade_receipts_two_and_multi_team(self):
        log = self.log("t", (1, 1), (1, 1))
        received = trade_receipts(log)
        self.assertEqual([a["id"] for a in received["team_b"]], ["t-p1"])
        self.assertEqual([a["id"] for a in received["team_a"]], ["t-k"])
        multi = {"teams": ["a", "b", "c"], "assets": {"format": "multi_team_v1", "transfers": [
            {"from_team_id": "a", "to_team_id": "b", "assets": [{"id": "x"}]}, {"from_team_id": "b", "to_team_id": "c", "assets": [{"id": "y"}]}]}}
        self.assertEqual({k: [a["id"] for a in v] for k, v in trade_receipts(multi).items()}, {"a": [], "b": ["x"], "c": ["y"]})

    def test_coaching_changes_pair_fire_and_hire_and_rank_by_importance(self):
        def event(kind, team, slot, date, importance, grade, name):
            return {"id": f"{kind}-{team}-{slot}", "kind": kind, "date": date, "team_ids": [team], "importance": importance,
                    "details": {"slot": slot, "staff_grade": grade, "staff_name": name}}
        events = [
            event("staff_fire", "t1", "head_coach", "2026-12-01", 0.76, 60, "Old"),
            event("staff_hire", "t1", "head_coach", "2026-12-01", 0.38, 81, "New"),
            event("staff_hire", "t2", "defensive_coordinator", "2026-11-01", 0.40, 70, "Coord"),
            event("staff_fire", "t3", "head_coach", "2027-01-05", 0.70, 55, "Gone"),
            event("staff_hire", "t4", "scouting_lead", "2026-11-01", 0.99, 90, "Scout"),  # not a coaching job
            event("staff_fire", "t5", "head_coach", "2026-06-01", 0.99, 50, "Last season"),  # before this season
        ]
        changes = coaching_changes(events, "2026-07-01")
        self.assertEqual([(c["team_id"], (c["fire"] or {}).get("details", {}).get("staff_name"), (c["hire"] or {}).get("details", {}).get("staff_name"))
                          for c in changes], [("t1", "Old", "New"), ("t3", "Gone", None), ("t2", None, "Coord")])
        self.assertAlmostEqual(changes[0]["importance"], 1.14)


class ContinuityTests(unittest.TestCase):
    def active(self):
        return {"teams": [{"id": "A", "abbrev": "AAA", "name": "A Team"}, {"id": "B", "abbrev": "BBB", "name": "B Team"}],
                "players": [{"id": "keep", "name": "Keeper", "team_id": "A"}, {"id": "hurt", "name": "Hurt", "team_id": "A"},
                            {"id": "moved", "name": "Mover", "team_id": "B"}, {"id": "rookie", "name": "Rookie", "team_id": "B"},
                            {"id": "gone", "name": "Gone", "team_id": None}]}

    def test_stints_count_each_team_for_a_traded_player(self):
        logs = [{"player_id": "moved", "team_id": "A", "minutes": 30, "date": "2026-11-01", "points": 10},
                {"player_id": "moved", "team_id": "A", "minutes": 30, "date": "2026-11-03"},
                {"player_id": "moved", "team_id": "B", "minutes": 25, "date": "2027-02-10"},
                {"player_id": "keep", "team_id": "A", "minutes": 0, "date": "2026-11-01"}]
        stints = team_stint_minutes(logs)
        self.assertEqual(stints[("moved", "A")]["minutes"], 60)
        self.assertEqual(stints[("moved", "B")]["minutes"], 25)
        self.assertNotIn(("keep", "A"), stints)

        last = {"stints": [{"player_id": "keep", "team_id": "A", "name": "Keeper", "minutes": 2000},
                           {"player_id": "hurt", "team_id": "A", "name": "Hurt", "minutes": 1000},
                           {"player_id": "moved", "team_id": "A", "name": "Mover", "minutes": 1000},
                           {"player_id": "moved", "team_id": "B", "name": "Mover", "minutes": 800},
                           {"player_id": "gone", "team_id": "B", "name": "Gone", "minutes": 1200}]}
        rows = {row["team"]["id"]: row for row in continuity_rows(self.active(), last, {"hurt": {"games": 40}})}
        a, b = rows["A"], rows["B"]
        self.assertEqual((a["kept_pct"], a["injured_pct"], a["gone_pct"], a["continuity_pct"]), (50.0, 25.0, 25.0, 75.0))
        self.assertEqual(a["arrivals"], [])
        # The traded player counts as kept for B by his B minutes only; the rookie is a new arrival with no minutes.
        self.assertEqual((b["kept_pct"], b["gone_pct"]), (40.0, 60.0))
        self.assertEqual([(r["name"], r["rookie"]) for r in b["arrivals"]], [("Rookie", True)])
        self.assertEqual([row["team"]["id"] for row in continuity_rows(self.active(), last, {"hurt": {"games": 40}})], ["A", "B"])

    def test_new_save_uses_real_2025_26_minutes(self):
        real = real_season_summary()
        self.assertEqual(real.get("season"), "2025-26")
        self.assertEqual(len(real["teams"]), 30)
        self.assertTrue(all(rec["wins"] + rec["losses"] == 82 for rec in real["teams"].values()))
        okc = [row for row in real["stints"] if row["team"] == "OKC"]
        self.assertGreater(sum(row["minutes"] for row in okc), 19680 - 1)  # 82 games x 240 minutes, plus overtime
        active = {"teams": [{"id": "team_okc", "abbrev": "OKC", "name": "Thunder"}],
                  "players": [{"id": "sga", "name": "Shai Gilgeous-Alexander", "normalized_name": "shai gilgeous alexander", "team_id": "team_okc"}]}
        last = last_season_context(active, {"season_history": []}, None, "2026-27")
        self.assertEqual(last["source"], "real")
        self.assertIn("real 2025-26", last["note"])
        sga = [row for row in last["stints"] if row["player_id"] == "sga"]
        self.assertEqual(len(sga), 1)
        self.assertGreater(sga[0]["minutes"], 1500)
        rows = continuity_rows(active, last, {})
        self.assertGreater(rows[0]["kept_pct"], 0)
        self.assertGreater(rows[0]["gone_pct"], 0)  # unmatched (retired, departed) players count as gone


class RosterNoteTests(unittest.TestCase):
    """The power-ranking note names the biggest change by player value, not by minutes (playtest 2026-11-21)."""

    VALUES = {"kawhi": 74.0, "ingram": 61.5, "mamu": 61.0, "grimes": 57.7, "kessler": 66.3, "lebron": 73.2,
              "hali": 72.5, "oubre": 57.0, "rook": 59.0, "bench": 50.0,
              "rotation_rook": 56.8, "raw_rook": 54.0}
    DRAFTED = {"kawhi": 2011, "ingram": 2016, "grimes": 2021, "kessler": 2022, "lebron": 2003, "hali": 2020,
               "oubre": 2015, "rook": 2026, "rotation_rook": 2026, "raw_rook": 2026}

    def note(self, gone=(), arrivals=(), injured=(), continuity=60.0):
        row = {"gone": [{"id": pid, "name": pid.title(), "minutes": 2000} for pid in gone],
               "arrivals": [{"id": pid, "name": pid.title(), "minutes_last_season": mins, "rookie": not mins} for pid, mins in arrivals],
               "injured": [{"id": pid, "name": pid.title(), "minutes": 1500} for pid in injured], "continuity_pct": continuity}
        return roster_note(row, self.VALUES.get, self.DRAFTED.get, 2026)

    def test_star_arrival_leads_over_more_minutes_lost(self):
        self.assertEqual(self.note(gone=["ingram", "mamu"], arrivals=[("kawhi", 2087)]), "Added Kawhi; lost Ingram and Mamu")

    def test_big_add_named_even_with_few_minutes_last_season(self):
        note = self.note(gone=["lebron"], arrivals=[("grimes", 2212), ("kessler", 155)])
        self.assertEqual(note, "Lost Lebron; added Kessler")

    def test_player_back_from_a_missed_season(self):
        self.assertEqual(self.note(arrivals=[("oubre", 1575), ("hali", 0)]), "Hali back after missing last season")

    def test_rookies_and_quiet_summers(self):
        self.assertEqual(self.note(arrivals=[("rook", 0)]), "Drafted Rook")
        self.assertEqual(self.note(arrivals=[("bench", 900)], continuity=90.0), "Running it back")
        self.assertEqual(self.note(injured=["kawhi"]), "Kawhi out injured")

    def test_rotation_ready_rookie_always_named(self):
        # A rookie who would already be a rotation player gets named beside bigger moves; a raw one does not.
        self.assertEqual(self.note(gone=["ingram", "mamu"], arrivals=[("kawhi", 2087), ("rotation_rook", 0)]),
                         "Added Kawhi; lost Ingram and Mamu; drafted Rotation_Rook")
        self.assertEqual(self.note(arrivals=[("rotation_rook", 0)]), "Drafted Rotation_Rook")
        self.assertEqual(self.note(arrivals=[("raw_rook", 0), ("bench", 900)], continuity=90.0), "Running it back")


class OpensOnceTests(unittest.TestCase):
    def save(self, **state):
        return {"meta": {"season": "2026-27", "gameplay_start_date": "2026-10-20"}, "state": state,
                "playoff_state": {}, "season_history": [], "schedule_state": {"simulated_game_ids": []}}

    def test_recap_pending_until_seen(self):
        save = self.save(phase="playoffs", current_date="2027-06-14")
        save["playoff_state"] = {"status": "completed", "champion_team_id": "A"}
        self.assertIsNone(pending_slideshow(save))  # nothing to show until the recap is stored
        save["season_slideshows"] = {"recaps": {"2026-27": {"slides": [{"key": "champion"}]}}}
        self.assertEqual(pending_slideshow(save), {"kind": "recap", "season": "2026-27"})
        mark_seen(save, "recap", "2026-27")
        self.assertIsNone(pending_slideshow(save))
        self.assertEqual(available_slideshows(save)[0]["kind"], "recap")

    def test_recap_reopens_from_season_history_after_rollover(self):
        save = self.save(phase="preseason", current_date="2027-10-01")
        save["meta"]["season"] = "2027-28"
        save["season_history"] = [{"season": "2026-27", "recap": {"slides": [{"key": "champion"}]}, "player_season_stats": {"x": {}}}]
        self.assertTrue(stored_recap(save, "2026-27"))
        self.assertEqual(available_slideshows(save), [{"kind": "recap", "season": "2026-27", "label": "2026-27 Year-End Recap"}])
        self.assertEqual(pending_slideshow(save), {"kind": "outlook", "season": "2027-28"})

    def test_outlook_due_at_preseason_and_new_career_start_only(self):
        self.assertTrue(outlook_due(self.save(phase="preseason", current_date="2027-10-01")))
        fresh = self.save(phase="regular_season", current_date="2026-10-20")
        self.assertTrue(outlook_due(fresh))
        mark_seen(fresh, "outlook", "2026-27")
        self.assertIsNone(pending_slideshow(fresh))
        played = self.save(phase="regular_season", current_date="2026-10-20")
        played["schedule_state"]["simulated_game_ids"] = ["g1"]
        self.assertFalse(outlook_due(played))
        self.assertFalse(outlook_due(self.save(phase="regular_season", current_date="2026-12-01")))

    def test_postseason_results(self):
        state = {"play_in": {"East": {"teams": {"7": "P", "9": "Q"}}},
                 "series": [{"round": "first_round", "team_ids": ["A", "P"]}, {"round": "conference_semifinals", "team_ids": ["A", "C"]},
                            {"round": "finals", "team_ids": ["A", "Z"]}],
                 "champion_team_id": "A"}
        results = team_postseason_results(state)
        self.assertEqual(results, {"P": "first_round", "Q": "play_in", "A": "champion", "C": "conference_semifinals", "Z": "finals"})


if __name__ == "__main__":
    unittest.main()
