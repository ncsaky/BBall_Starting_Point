"""Exactness checks for the deadline-speed changes (docs/agents/tasks/deadline-speed.md)."""
from __future__ import annotations

import json
import random
import unittest

from nba_gm_data import save as sv
from nba_gm_data import trade_roster as tr
from nba_gm_data import trade_wants as tw
from nba_gm_data import transactions as tx
from nba_gm_data.roster_forecast import ForecastSnapshot
from nba_gm_data.utils import clamp


def _reference_ai_role_targets(canonical, roster, priors):
    """The two-deep assignment as written before deadline-speed (dict states, slot scores computed in place)."""
    attrs = {p["id"]: sv.player_attribute_summary(canonical, p["id"]) for p in roster}
    quality = {p["id"]: attrs[p["id"]]["overall"] + min(32, max(0, float(priors.get(p["id"], 0)))) * .05 for p in roster}
    remaining = sorted(roster, key=lambda p: p["id"])
    groups = []
    for _ in range(2):
        states = {0: (0.0, ("",) * 5)}
        for player in remaining:
            pid = player["id"]
            scores = [sv.starting_slot_score(player, str(slot + 1), 0, attrs[pid]) + quality[pid] * .66 for slot in range(5)]
            for slot in range(5):
                if not any(token in sv.STARTING_FIVE_SLOT_FITS[str(slot + 1)] for token in sv.player_position_tokens(player)):
                    scores[slot] -= 1_000
            for mask, (score, assignment) in list(states.items()):
                for slot in range(5):
                    if mask & (1 << slot):
                        continue
                    new_mask = mask | (1 << slot)
                    total = score + scores[slot]
                    previous = states.get(new_mask)
                    if previous is None or total > previous[0]:
                        states[new_mask] = (total, assignment[:slot] + (pid,) + assignment[slot + 1:])
        full_mask = max(states, key=lambda mask: (mask.bit_count(), states[mask][0]))
        assignment = states[full_mask][1]
        groups.append(assignment)
        chosen = set(assignment) - {""}
        remaining = [p for p in remaining if p["id"] not in chosen]
    selected = [pid for group in groups for pid in group if pid]
    desired = {p["id"]: 0.0 for p in roster}
    for first, second in zip(*groups):
        if first and second:
            lead = clamp(24 + (quality[first] - quality[second]) * .6, 18, 36)
            desired[first], desired[second] = lead, 48 - lead
        elif first or second:
            desired[first or second] = 42
    targets = sv.bounded_minutes_allocation([
        {"player_id": pid, "desired": desired[pid], "minimum": 0, "maximum": 42 if pid in selected else 0}
        for pid in desired
    ], 240)
    return targets, selected


POSITIONS = ["PG", "SG", "SF", "PF", "C", "G", "F", "G-F", "F-C", "PG-SG", "SF-PF", "C-PF", None, ""]
TRAITS = ["shooting_range", "rim_pressure", "passing_reads", "handle_pressure", "defensive_effort", "rim_deterrence",
          "offensive_rebounding", "scheme_iq", "foot_speed_lateral_agility", "shot_versatility"]


def _random_league(rng, size, *, ties=False):
    players = []
    for i in range(size):
        players.append({"id": f"p{i:02d}", "team_id": "t1", "name": f"Player {i}",
                        "position": rng.choice(POSITIONS), "height_inches": rng.choice([72, 74, 76, 77, 78, 80, 82, 84, 86]),
                        "weight_lbs": 220, "age": 25, "minutes_projection": 24})
    value = (lambda: 55.0) if ties else (lambda: float(rng.randint(30, 90)))
    traits = [{"player_id": p["id"], "trait_key": key, "value": value()} for p in players for key in TRAITS]
    return {"meta": {"current_date": "2027-01-30"}, "teams": [{"id": "t1", "abbrev": "ONE"}],
            "players": players, "traits": traits, "contracts": []}


class RoleTargetDpTests(unittest.TestCase):
    def test_matches_reference_on_random_and_tied_rosters(self):
        rng = random.Random(20271119)
        for trial in range(60):
            league = _random_league(rng, rng.randint(3, 18), ties=trial % 5 == 0)
            league["_allow_internal_caches"] = True
            priors = {} if trial % 2 else {p["id"]: rng.uniform(0, 40) for p in league["players"]}
            roster = league["players"]
            self.assertEqual(sv.ai_role_targets(league, roster, priors), _reference_ai_role_targets(league, roster, priors),
                             f"trial {trial}")

    def test_slot_rows_follow_every_input(self):
        player = {"id": "x", "position": "SF", "height_inches": 80}
        attrs = {"overall": 60.0, "creation": 55.0, "passing": 50.0, "spacing": 70.0, "defense": 65.0,
                 "rebounding": 40.0, "rim_protection": 45.0}

        def fresh(p, a):
            tokens = sv.player_position_tokens(p)
            return (tuple(sv.starting_slot_score(p, str(s + 1), 0, a) for s in range(5)),
                    tuple(any(t in sv.STARTING_FIVE_SLOT_FITS[str(s + 1)] for t in tokens) for s in range(5)))

        self.assertEqual(sv._slot_score_row(player, attrs), fresh(player, attrs))
        variants = [({**player, "position": "C"}, attrs), ({**player, "height_inches": 85}, attrs),
                    ({"id": "x", "position": "SF", "height": 74}, attrs)]
        variants += [(player, {**attrs, field: 91.0}) for field in sv._SLOT_ROW_FIELDS]
        for p, a in variants:
            self.assertEqual(sv._slot_score_row(p, a), fresh(p, a))


def _search_league():
    players = [{"id": f"a{i}", "team_id": "t1" if i % 2 else "t2", "name": f"Same {i % 3}", "normalized_name": f"same {i % 3}",
                "position": "SF", "minutes_projection": 10 + i, "age": 24 + i} for i in range(10)]
    return {"meta": {"current_date": "2027-01-30"}, "teams": [{"id": "t1"}, {"id": "t2"}], "players": players}


class SearchIndexTests(unittest.TestCase):
    def test_team_rows_match_league_order_and_only_inside_a_search(self):
        league = _search_league()
        self.assertIsNone(tx._search_team_rows(league, "t1"))
        view = {**league, "_roster_forecast_snapshot": ForecastSnapshot(league)}
        self.assertEqual(tx._search_team_rows(view, "t1"), [p for p in league["players"] if p["team_id"] == "t1"])
        replaced = {**view, "players": list(league["players"])}  # a changed membership never uses the index
        self.assertIsNone(tx._search_team_rows(replaced, "t1"))

    def test_resolve_player_is_unchanged_by_the_index(self):
        league = _search_league()
        view = {**league, "_roster_forecast_snapshot": ForecastSnapshot(league)}
        for query in ("a3", "Same 1", "same 2", "Same", "a4"):
            for team in ("t1", "t2", None):
                try:
                    expected = tx.resolve_player(league, query, team_id=team)
                except ValueError as exc:
                    with self.assertRaises(ValueError) as ctx:
                        tx.resolve_player(view, query, team_id=team)
                    self.assertEqual(str(ctx.exception), str(exc))
                    continue
                self.assertIs(tx.resolve_player(view, query, team_id=team), expected)

    def test_market_value_memo_is_keyed_by_the_objects_passed(self):
        player = {"id": "m1", "name": "M", "age": 27, "minutes_projection": 30, "current_ability": 70, "potential": 74}
        valuation = {"player_value": 66.0, "on_court_value": 70.0, "playoff_value": 68.0}
        ctx = {"_trade_search_market_values": {}}
        expected = tx.market_trade_target_value(player, valuation)
        self.assertEqual(tx._search_market_value(ctx, player, valuation), expected)
        self.assertEqual(tx._search_market_value(ctx, player, valuation), expected)
        other = {**valuation, "player_value": 80.0, "on_court_value": 81.0}
        self.assertEqual(tx._search_market_value(ctx, player, other), tx.market_trade_target_value(player, other))
        moved = {**player, "minutes_projection": 6}
        self.assertEqual(tx._search_market_value(ctx, moved, other), tx.market_trade_target_value(moved, other))
        self.assertEqual(tx._search_market_value({}, player, valuation), expected)

    def test_search_context_carries_the_new_memos(self):
        league = _search_league()
        ctx = tx.trade_search_context(league)
        self.assertEqual(ctx["_trade_search_market_values"], {})
        self.assertEqual(list(ctx["_trade_search_exact_memo"]), ["base_sources"])
        self.assertIs(ctx["_trade_search_exact_memo"]["base_sources"][0], league["players"])
        self.assertIsNot(tx.trade_search_context(league)["_trade_search_exact_memo"], ctx["_trade_search_exact_memo"])

    def test_normalize_memo_matches_fresh_results_and_skips_other_lists(self):
        league = {**_search_league(), "draft_picks": [], "pick_obligations": []}
        ctx = tx.trade_search_context(league)
        team = {"id": "t1"}
        specs = [{"kind": "player", "value": "Same 1"}, {"kind": "player", "value": "a3"}]
        fresh = tx._normalize_assets(league, team, specs)
        first = tx.normalize_assets(ctx, team, specs)
        self.assertEqual(first, fresh)
        first[0]["label"] = "edited by a caller"
        self.assertEqual(tx.normalize_assets(ctx, team, specs), fresh)
        self.assertIn("normalized_assets", ctx["_trade_search_exact_memo"])
        preview = {**ctx, "players": [dict(p, name="Other") if p["id"] == "a1" else p for p in league["players"]]}
        self.assertEqual(tx.normalize_assets(preview, team, [{"kind": "player", "value": "a1"}]),
                         tx._normalize_assets(preview, team, [{"kind": "player", "value": "a1"}]))
        with self.assertRaises(ValueError):
            tx.normalize_assets(ctx, team, [{"kind": "player", "value": "nobody"}])


class SearchMemoTests(unittest.TestCase):
    def test_long_absences_match_a_fresh_scan_and_follow_the_rows(self):
        rows = [{"player_id": "a", "availability_status": "out", "return_date": "2027-03-01"},
                {"player_id": "b", "availability_status": "out", "return_date": "2027-02-05"},
                {"player_id": "c", "availability_status": "questionable", "return_date": "2027-04-01"},
                {"player_id": "d", "availability_status": "out", "return_date": None}]
        saved = {"state": {"current_date": "2027-01-30"}, "health_states": rows}
        ctx = {"_trade_search_exact_memo": {}}
        self.assertEqual(tr.long_absences(ctx, saved), [("a", 30)])
        self.assertEqual(tr.long_absences(ctx, saved), [("a", 30)])
        later = {"state": {"current_date": "2027-02-20"}, "health_states": rows}
        self.assertEqual(tr.long_absences(ctx, later), [])
        new_rows = rows + [{"player_id": "e", "availability_status": "out", "return_date": "2027-02-20"}]
        self.assertEqual(tr.long_absences(ctx, {**saved, "health_states": new_rows}), [("a", 30), ("e", 21)])
        self.assertEqual(tr.long_absences({}, saved), [("a", 30)])

    def test_wants_json_matches_json_dumps_per_list(self):
        entries = [{"kind": "picks", "id": "w1", "round": 1}, {"kind": "player", "id": "w2", "conditions": []}]
        other = [{"kind": "player", "id": "w9"}]
        ctx = {"_trade_search_exact_memo": {}}
        for value in (entries, other, entries):
            self.assertEqual(tw._entries_json(ctx, value), json.dumps(value, sort_keys=True))
        self.assertEqual(tw._entries_json({}, entries), json.dumps(entries, sort_keys=True))


class RotationStrengthReuseTests(unittest.TestCase):
    def test_roster_projection_strength_equals_a_fresh_feature_calculation(self):
        from nba_gm_data.sim import team_feature_vector
        rng = random.Random(7)
        league = _random_league(rng, 13)
        view = {**league, "_roster_forecast_snapshot": ForecastSnapshot(league)}
        rotation = tx.strategic_rotation_view(view, "t1")
        fresh = tx.contention_from_features(team_feature_vector(rotation, league["teams"][0], include_spatial=False).features)
        self.assertEqual(rotation["_strategic_contention"], fresh)
        self.assertEqual(tr.roster_projection(view, "t1")["strength"], round(fresh, 4))


    def test_rotation_strength_memo_follows_player_records_and_meta(self):
        from nba_gm_data.sim import team_feature_vector
        rng = random.Random(11)
        league = _random_league(rng, 12)
        forecast = ForecastSnapshot(league)
        team = league["teams"][0]

        def fresh(view):
            return tx.contention_from_features(team_feature_vector(view, team, include_spatial=False).features)

        players = [dict(p, minutes_projection=20) for p in league["players"][:10]]
        view = forecast.view(league, players)
        self.assertEqual(tx._rotation_strength(forecast, view, team), fresh(view))
        self.assertEqual(tx._rotation_strength(forecast, forecast.view(league, [dict(p) for p in players]), team), fresh(view))
        changed = [dict(p, minutes_projection=30 if i < 5 else 18) for i, p in enumerate(players)]
        changed_view = forecast.view(league, changed)
        self.assertEqual(tx._rotation_strength(forecast, changed_view, team), fresh(changed_view))
        new_meta = forecast.view({**league, "meta": dict(league["meta"])}, players)
        before = len(forecast._rotation_strengths)
        self.assertEqual(tx._rotation_strength(forecast, new_meta, team), fresh(new_meta))
        self.assertEqual(len(forecast._rotation_strengths), before)  # recomputed and replaced, not reused


class ValuationFeatureMemoTests(unittest.TestCase):
    def test_memo_matches_fresh_features_and_follows_inputs(self):
        from nba_gm_data.sim import player_feature_vector
        rng = random.Random(5)

        def fresh(league, player):
            league = {**league, "_allow_internal_caches": True}
            return player_feature_vector(league, player, include_spatial=False).features

        base = _random_league(rng, 4)
        base["_allow_internal_caches"] = True
        player = base["players"][0]
        self.assertEqual(tx._valuation_features(base, player, False), fresh(dict(base), player))
        variants = []
        moved = dict(base, players=[dict(player, minutes_projection=33)] + base["players"][1:])
        variants.append((moved, moved["players"][0]))
        traits = [dict(t, value=t["value"] + 7) if t["player_id"] == player["id"] else t for t in base["traits"]]
        variants.append((dict(base, traits=traits), player))
        variants.append((dict(base, meta={**base["meta"], "talent_model_version": 1}), player))
        for index, (league, who) in enumerate(variants):
            league = dict(league)
            self.assertEqual(tx._valuation_features(league, who, False), fresh(league, who))
            if index < 2:  # minutes and trait changes move the features
                self.assertNotEqual(tx._valuation_features(league, who, False), tx._valuation_features(base, player, False))


class FirstRowIndexTests(unittest.TestCase):
    def test_first_row_matches_a_scan_and_only_for_snapshot_lists(self):
        from nba_gm_data.roster_forecast import first_player_row
        contracts = [{"player_id": "a", "n": 1}, {"player_id": "b"}, {"player_id": "a", "n": 2}]
        health = [{"player_id": "b", "availability_status": "out"}]
        league = {"players": [], "contracts": contracts, "player_health_states": health}
        view = {**league, "_roster_forecast_snapshot": ForecastSnapshot(league)}
        self.assertIs(first_player_row(view, contracts, "a"), contracts[0])
        self.assertIsNone(first_player_row(view, contracts, "zz"))
        self.assertIs(first_player_row(view, health, "b"), health[0])
        other = list(contracts)
        other.insert(0, {"player_id": "a", "n": 0})
        self.assertIs(first_player_row(view, other, "a"), other[0])
        self.assertIs(first_player_row(league, contracts, "a"), contracts[0])
        self.assertEqual(sv.player_salary_table(view, "zz"), {})


if __name__ == "__main__":
    unittest.main()
