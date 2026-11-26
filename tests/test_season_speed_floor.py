"""SEASON-SPEED-FLOOR (2026-11-25): the eight-player floor on rest shutdowns, the draftee-role cache, the injury-event
index and the settled waiver-wire pruning at rollover."""
import unittest
from copy import deepcopy

from nba_gm_data import health
from nba_gm_data import role_estimate
from nba_gm_data.save import prune_settled_waiver_entries

TEAMS = [{"id": "team_bos", "abbrev": "BOS", "conference": "East"}, {"id": "team_nyk", "abbrev": "NYK", "conference": "East"}]
GAME = {"externalGameId": "g1", "gameDate": "2027-04-10", "homeTeamId": "2", "awayTeamId": "18", "phase": "regular"}


def state(pid, **extra):
    return {"player_id": pid, "fatigue": 0.0, "availability_status": "active", "current_injury_id": None, "rust": 0.0,
            "games_missed": 0, **extra}


def shut(pid, fatigue=0.0, **extra):
    return state(pid, fatigue=fatigue, fatigue_date="2027-04-09",
                 rest_shutdown={"team_id": "team_bos", "since": "2027-04-01", "reason": "season over"}, **extra)


def hurt(pid):
    return state(pid, availability_status="out", current_injury_id=f"inj-{pid}", return_date="2027-05-30")


class EightPlayerFloorTests(unittest.TestCase):
    """BOS late in a lost season: three hurt, five shut down, four healthy. Minutes under the coach's rest threshold, so
    no new rest decisions are drawn tonight; only the floor acts."""

    def league(self, healthy=4, shut_down=5, injured=3):
        players, states = [], []
        for i in range(healthy):
            players.append({"id": f"ok{i}", "team_id": "team_bos", "age": 27.0, "minutes_projection": 20.0})
            states.append(state(f"ok{i}"))
        for i in range(shut_down):
            # one shut-down player still carries minutes (inside the health pass's list), the rest are at zero
            minutes = 30.0 if i == 0 else 0.0
            players.append({"id": f"sd{i}", "team_id": "team_bos", "age": 31.0, "minutes_projection": minutes,
                            "_trade_value_minutes_projection": 30.0 - i})
            states.append(shut(f"sd{i}", fatigue=float(i)))
        for i in range(injured):
            players.append({"id": f"in{i}", "team_id": "team_bos", "age": 29.0, "minutes_projection": 0.0})
            states.append(hurt(f"in{i}"))
        for i in range(10):
            players.append({"id": f"ny{i}", "team_id": "team_nyk", "age": 27.0, "minutes_projection": 20.0})
            states.append(state(f"ny{i}"))
        records = {"team_bos": {"wins": 20, "losses": 59}, "team_nyk": {"wins": 50, "losses": 29}}
        return {"teams": deepcopy(TEAMS), "players": players, "traits": [], "injury_events": [],
                "player_health_states": states, "save_team_records": records}

    def run_game(self, canonical):
        result = health.simulate_health(".", canonical, "2027-04-09", "2027-04-10", seed=3, schedule=[GAME],
                                        box_score_fatigue=True)
        return {s["player_id"]: s for s in result["final_states"]}, result["rest_decisions"]

    def available(self, canonical, states):
        canonical = {**canonical, "player_health_states": list(states.values())}
        pool = [{"player": p, "minutes": 1.0, "actual": None} for p in canonical["players"] if p["team_id"] == "team_bos"]
        return {item["player"]["id"] for item in health.sandbox_health_adjusted_pool(canonical, "2027-04-10", pool)}

    def test_recalls_the_healthiest_shut_down_players_up_to_eight(self):
        canonical = self.league()
        states, decisions = self.run_game(canonical)
        available = self.available(canonical, states)
        self.assertEqual(len(available), 8)
        # least fatigue first: sd0..sd3 come back, sd4 (most tired) stays shut down
        self.assertEqual(available, {"ok0", "ok1", "ok2", "ok3", "sd0", "sd1", "sd2", "sd3"})
        self.assertIn("rest_shutdown", states["sd4"])
        for pid in ("sd0", "sd1", "sd2", "sd3"):
            self.assertNotIn("rest_shutdown", states[pid])
        self.assertEqual(sorted(d["player_id"] for d in decisions if d["kind"] == "recalled"), ["sd0", "sd1", "sd2", "sd3"])
        # injured players stay out
        for pid in ("in0", "in1", "in2"):
            self.assertEqual(states[pid]["availability_status"], "out")

    def test_no_recall_when_eight_are_available(self):
        canonical = self.league(healthy=8)
        states, decisions = self.run_game(canonical)
        self.assertFalse([d for d in decisions if d["kind"] == "recalled"])
        for i in range(5):
            self.assertIn("rest_shutdown", states[f"sd{i}"])

    def test_short_roster_recalls_everyone_it_can(self):
        canonical = self.league(healthy=1, shut_down=3, injured=8)
        states, _decisions = self.run_game(canonical)
        self.assertEqual(self.available(canonical, states), {"ok0", "sd0", "sd1", "sd2"})

    def test_user_rest_is_left_alone(self):
        canonical = self.league()
        canonical["player_health_states"] = [
            {**s, "user_rest": {"team_id": "team_bos", "games_left": 2}} if s["player_id"] == "ok3" else s
            for s in canonical["player_health_states"]]
        states, _decisions = self.run_game(canonical)
        available = self.available(canonical, states)
        self.assertNotIn("ok3", available)
        self.assertEqual(len(available), 8)   # five shut-down players recalled instead
        self.assertEqual(states["ok3"]["user_rest"]["games_left"], 1)


class RoleCacheTests(unittest.TestCase):
    def league(self):
        players, traits = [], {}
        for i in range(10):
            players.append({"id": f"g{i}", "draft_year": 2015, "height_inches": 75 + i % 2,
                            "primary_off_role": "Primary Ball Handler", "primary_def_role": "On-Ball Guard"})
            traits[f"g{i}"] = {"shooting": 70 + i, "passing": 80 + i, "rebounding": 40, "rim": 30}
            players.append({"id": f"b{i}", "draft_year": 2015, "height_inches": 84 + i % 2,
                            "primary_off_role": "Rollman", "primary_def_role": "Rim Protector"})
            traits[f"b{i}"] = {"shooting": 40, "passing": 45, "rebounding": 80 + i, "rim": 82 + i}
        players.append({"id": "r", "draft_year": 2027, "height_inches": 80})
        traits["r"] = {"shooting": 50, "passing": 52, "rebounding": 55, "rim": 50}
        return players, traits

    def roles(self, players, traits, fresh=False):
        if fresh:
            role_estimate._clear_caches()
        players = deepcopy(players)
        role_estimate.assign_estimated_roles({"players": players}, traits)
        rookie = next(p for p in players if p["id"] == "r")
        return rookie["primary_off_role"], rookie["primary_def_role"]

    def test_cached_answer_matches_a_fresh_one_and_follows_every_input(self):
        players, traits = self.league()
        first = self.roles(players, traits, fresh=True)
        self.assertEqual(self.roles(players, traits), first)
        # the draftee's own ratings, a veteran's ratings, a veteran's role and a height each make a new key
        changes = [
            lambda p, t: t.__setitem__("r", {**t["r"], "rebounding": 90, "rim": 92}),
            lambda p, t: [t.__setitem__(f"g{i}", {**t[f"g{i}"], "rebounding": 85, "rim": 85}) for i in range(10)],
            lambda p, t: [v.__setitem__("primary_off_role", "Connector") for v in p if v["id"].startswith("b")],
            lambda p, t: next(v for v in p if v["id"] == "r").__setitem__("height_inches", 86),
        ]
        for change in changes:
            p, t = deepcopy(players), deepcopy(traits)
            change(p, t)
            cached = self.roles(p, t)
            self.assertEqual(cached, self.roles(p, t, fresh=True))


class InjuryIndexTests(unittest.TestCase):
    def test_follows_appends_and_new_lists(self):
        events = [{"id": "e1", "player_id": "a"}, {"id": "e2", "player_id": "b"}]
        canonical = {"injury_events": events}
        self.assertEqual([e["id"] for e in health.injury_events_by_player(canonical)["a"]], ["e1"])
        events.append({"id": "e3", "player_id": "a"})
        self.assertEqual([e["id"] for e in health.injury_events_by_player(canonical)["a"]], ["e1", "e3"])
        canonical["injury_events"] = [{"id": "e4", "player_id": "a"}]
        self.assertEqual([e["id"] for e in health.injury_events_by_player(canonical)["a"]], ["e4"])
        self.assertEqual(health.injury_events_by_player({"injury_events": []}), {})


class WaiverPruneTests(unittest.TestCase):
    def entry(self, wid, status, resolved, seasons):
        return {"id": wid, "status": status, "resolved_date": resolved, "clearance_date": resolved,
                "contract": {"seasons": [{"season": s} for s in seasons]}}

    def test_drops_only_settled_entries_with_finished_contracts(self):
        save = {"waiver_wire": [
            self.entry("old_done", "cleared", "2027-12-01", ["2027-28"]),            # dropped
            self.entry("old_claimed", "claimed", "2027-11-01", ["2027-28", "2028-29"]),  # dropped
            self.entry("old_running", "cleared", "2027-12-01", ["2027-28", "2029-30"]),  # contract still runs
            self.entry("last_season", "cleared", "2028-12-01", ["2028-29"]),          # the season just ended
            {"id": "pending", "status": "pending", "clearance_date": "2027-01-01"},
        ]}
        self.assertEqual(prune_settled_waiver_entries(save, 2029), 2)
        self.assertEqual([e["id"] for e in save["waiver_wire"]], ["old_running", "last_season", "pending"])


if __name__ == "__main__":
    unittest.main()
