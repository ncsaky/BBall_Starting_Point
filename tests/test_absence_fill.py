"""The coach's fill-in when players are out, and the head coach's star workload (SMART-MINUTES)."""
from __future__ import annotations

from statistics import mean
import unittest

from nba_gm_data import absence_fill as af
from nba_gm_data import coach_cards, save as sv, staff

GAPS = {
    "PG": (0.0, -6.0, -26.0, None, None),
    "SG": (-7.0, 0.0, -9.0, -20.0, -33.0),
    "SF": (-13.0, -7.0, 0.0, -6.0, -10.0),
    "PF": (-20.0, -15.0, -9.0, 0.0, -5.0),
    "C": (None, None, -28.0, -16.0, 0.0),
}


def player(pid, pos, healthy, value=55.0, age=27.0, off="", defense=""):
    return af.FillPlayer(pid=pid, healthy=healthy, gaps=GAPS[pos], value=value, age=age, off_family=off,
                         def_family=defense)


def team(**overrides):
    """A plain healthy plan: five starters (PG..C), a bench of eight and two players outside the rotation."""
    rows = [
        player("pg1", "PG", 34, 66, off="handler", defense="guard"), player("sg1", "SG", 32, 62),
        player("sf1", "SF", 33, 64), player("pf1", "PF", 30, 60), player("c1", "C", 31, 63, off="big", defense="big"),
        player("g6", "SG", 24, 58), player("f7", "SF", 22, 56), player("c8", "C", 18, 55, off="big", defense="big"),
        player("pg9", "PG", 16, 54, off="handler", defense="guard"), player("pf10", "PF", 10, 52),
        player("sf11", "SF", 6, 50), player("pg12", "PG", 3, 48), player("c13", "C", 2, 47),
        player("x14", "SF", 0, 45), player("x15", "PF", 0, 44),
    ]
    for pid, healthy in overrides.items():
        for row in rows:
            if row.pid == pid:
                row.healthy = healthy
    return rows


def fill(out, rows=None, **kwargs):
    rows = rows or team()
    absent = [r for r in rows if r.pid in out]
    available = [r for r in rows if r.pid not in out]
    af.mark_starters(available, absent)
    vacated = sum(r.healthy for r in absent)
    adds = af.coach_fill(absent, available, vacated, **kwargs)
    return adds, {r.pid: r for r in available}, vacated


class CoachFillTests(unittest.TestCase):
    def test_nothing_missing_changes_nothing(self):
        rows = team()
        self.assertEqual(set(af.coach_fill([], rows, 0.0).values()), {0.0})

    def test_starting_center_out_bench_centers_take_the_spot(self):
        adds, players, vacated = fill({"c1"})
        self.assertAlmostEqual(sum(adds.values()), vacated, places=6)
        self.assertEqual(set(sorted(adds, key=adds.get)[-2:]), {"c8", "c13"})
        self.assertGreater(adds["c8"] + adds["c13"], vacated / 2)
        starters = [adds[p] for p in ("pg1", "sg1", "sf1", "pf1")]
        # Real 2025-26: other starters gained about 1.1-1.7 minutes each.
        self.assertTrue(all(0.3 < gain < 3.0 for gain in starters), starters)
        self.assertGreater(adds["c8"], 3 * mean(starters))
        # The backup center ends up playing the most of the bench centers (he already plays most).
        self.assertGreater(players["c8"].healthy + adds["c8"], players["c13"].healthy + adds["c13"])

    def test_point_guard_out_point_guards_take_the_spot(self):
        adds, _, _ = fill({"pg1"})
        self.assertEqual(set(sorted(adds, key=adds.get)[-2:]), {"pg9", "pg12"})
        self.assertGreater(adds["pg12"], adds["c13"])

    def test_thin_depth_leans_on_starters(self):
        solid, _, _ = fill({"c1"})
        no_centers = [r for r in team() if r.pid not in ("c8", "c13")]
        thin, _, _ = fill({"c1"}, no_centers)
        starters = ("pg1", "sg1", "sf1", "pf1")
        self.assertGreater(sum(thin[p] for p in starters), 1.3 * sum(solid[p] for p in starters))
        # With no center left the coach goes smaller: the power forwards take the most.
        self.assertGreater(thin["pf10"], solid["pf10"])
        self.assertEqual(set(sorted((p for p in thin if p not in starters), key=thin.get)[-2:]), {"pf10", "x15"})

    def test_better_backup_gets_more(self):
        rows = team(c13=0.0)
        rows.append(player("c16", "C", 0.0, 58, off="big", defense="big"))
        adds, _, _ = fill({"c1", "c8"}, rows)
        self.assertGreater(adds["c16"], adds["c13"])

    def test_deep_bench_call_ups_are_limited(self):
        rows = team() + [player(f"x{i}", "SF", 0.0, 44) for i in range(16, 20)]
        adds, players, _ = fill({"sf1", "f7"}, rows)
        called = [pid for pid, add in adds.items() if players[pid].healthy <= 0 and add > 0]
        self.assertLessEqual(len(called), af.DEEP_CALLUPS)

    def test_short_handed_team_stays_under_42(self):
        rows = team()
        out = {"pg1", "sg1", "sf1", "g6", "f7", "pf10", "sf11", "x14"}
        adds, players, vacated = fill(out, rows)
        self.assertAlmostEqual(sum(adds.values()), vacated, places=6)
        self.assertLessEqual(max(players[p].healthy + a for p, a in adds.items()), 42.0 + 1e-6)

    def test_two_starters_out_starters_gain_less_per_absence(self):
        sf, _, _ = fill({"sf1"})
        pg, _, _ = fill({"pg1"})
        two, _, _ = fill({"sf1", "pg1"})
        common = ("sg1", "pf1", "c1")
        # Real 2025-26: +1.5 each with one starter out, +2.25 (not +3) with two.
        self.assertLess(sum(two[p] for p in common), 0.9 * (sum(sf[p] for p in common) + sum(pg[p] for p in common)))
        self.assertGreater(sum(two[p] for p in common), sum(sf[p] for p in common))

    def test_star_workload_leans_on_starters(self):
        riding, _, _ = fill({"sf1"}, star_workload=2.5)
        limiting, _, _ = fill({"sf1"}, star_workload=-2.5)
        starters = ("pg1", "sg1", "pf1", "c1")
        self.assertGreater(sum(riding[p] for p in starters), sum(limiting[p] for p in starters))

    def test_rebuilding_team_plays_its_young_players(self):
        rows = team()
        for r in rows:
            r.age = 21.0 if r.pid in ("f7", "sf11") else 29.0
        rebuilding, _, _ = fill({"sf1"}, rows, phase="rebuilding")
        peak, _, _ = fill({"sf1"}, rows, phase="peak")
        self.assertGreater(rebuilding["f7"] + rebuilding["sf11"], peak["f7"] + peak["sf11"])

    def test_opponent_lean_moves_fill_minutes_only(self):
        class Fake(dict):
            pass

        big = {"id": "big", "_absence_fill": 6.0, "_fill_size": 0.9}
        small = {"id": "small", "_absence_fill": 6.0, "_fill_size": -0.8}
        starter = {"id": "starter"}
        pool = [{"player": big, "minutes": 16.0}, {"player": small, "minutes": 16.0}, {"player": starter, "minutes": 34.0}]
        original = af.opponent_lean
        try:
            af.opponent_lean = lambda canonical, opp: 1.0
            vs_big = af.opponent_adjusted_pool({}, pool, [Fake()])
            af.opponent_lean = lambda canonical, opp: -1.0
            vs_small = af.opponent_adjusted_pool({}, pool, [Fake()])
        finally:
            af.opponent_lean = original
        for adjusted in (vs_big, vs_small):
            self.assertAlmostEqual(sum(i["minutes"] for i in adjusted), sum(i["minutes"] for i in pool), places=9)
            self.assertEqual(adjusted[2]["minutes"], 34.0)
        self.assertGreater(vs_big[0]["minutes"], vs_big[1]["minutes"])
        self.assertLess(vs_small[0]["minutes"], vs_small[1]["minutes"])


class StarWorkloadTests(unittest.TestCase):
    def test_curve_keeps_total_and_moves_top_two(self):
        base = sv.star_workload_curve(0.0)
        riding = sv.star_workload_curve(2.5)
        limiting = sv.star_workload_curve(-2.5)
        self.assertAlmostEqual(sum(riding), sum(base), places=9)
        self.assertAlmostEqual(sum(limiting), sum(base), places=9)
        self.assertGreater(riding[0], base[0])
        self.assertGreater(riding[1], base[1])
        self.assertLess(limiting[0], base[0])
        self.assertLess(riding[5], base[5])

    def test_real_coaches_use_measured_values(self):
        kerr = {"slot": "head_coach", "name": "Steve Kerr", "id": "a"}
        nurse = {"slot": "head_coach", "name": "Nick Nurse", "id": "b"}
        self.assertLess(staff.coach_star_workload(kerr), -1.0)
        self.assertGreater(staff.coach_star_workload(nurse), 2.0)
        self.assertEqual(staff.coach_star_workload({"slot": "offensive_coordinator", "name": "Nick Nurse"}), 0.0)

    def test_generated_coach_draw_is_fixed_and_bounded(self):
        coach = {"slot": "head_coach", "name": "Nolan Pierce", "id": "gameplay_staff_x"}
        values = [staff.coach_star_workload({**coach, "id": f"g{i}"}) for i in range(300)]
        self.assertEqual(staff.coach_star_workload(coach), staff.coach_star_workload(dict(coach)))
        self.assertLessEqual(max(abs(v) for v in values), staff.STAR_WORKLOAD_LIMIT)
        self.assertGreater(mean(abs(v) for v in values), 0.8)

    def test_shown_value_is_the_engine_value(self):
        coach = {"slot": "head_coach", "name": "Steve Kerr", "id": "a", "skill_traits": {}, "personality_traits": {}}
        staff.ensure_star_workload(coach)
        minutes = staff.coach_star_workload(coach)
        self.assertAlmostEqual(minutes, staff.HEAD_COACH_STAR_WORKLOAD["steve kerr"], places=1)
        row = next(r for r in staff.staff_effect_rows(coach) if r["label"] == "Star workload")
        self.assertAlmostEqual(row["value"], staff.star_workload_score(minutes), places=1)
        self.assertIn("Limits his stars", row["description"])
        card = coach_cards.coach_card_details(coach, [coach])
        self.assertAlmostEqual(card["staff"]["personality_traits"]["star_workload"], staff.star_workload_score(minutes))
        self.assertIn("star_workload", card["descriptions"])
        # The staff grade ignores the trait.
        plain = {**coach, "personality_traits": {}}
        self.assertEqual(staff.staff_grade(plain), staff.staff_grade(coach))


class UserTargetsTests(unittest.TestCase):
    def test_user_targets_stay_and_missing_minutes_are_placed(self):
        roster = [{"id": f"p{i}", "name": f"P{i}", "position": pos, "height_inches": h}
                  for i, (pos, h) in enumerate([("PG", 75), ("SG", 77), ("SF", 79), ("PF", 81), ("C", 84),
                                                 ("PG", 74), ("SF", 79), ("C", 83), ("SG", 77), ("PF", 81)])]
        override = {"p0": 34, "p1": 32, "p2": 32, "p3": 30, "p4": 32, "p5": 20, "p6": 20, "p7": 16, "p8": 14, "p9": 0}
        health = {"p4": {"player_id": "p4", "availability_status": "out", "current_injury_id": "x", "days_left": 5}}
        canonical = {"players": roster, "teams": [{"id": "t"}], "traits": []}
        original = sv.player_attribute_summary
        try:
            sv.player_attribute_summary = lambda canonical, pid: {"overall": 55.0}
            result = sv.user_rotation_override_projection(roster, health, override, canonical=canonical, save={},
                                                          team_id="t")
        finally:
            sv.player_attribute_summary = original
        self.assertEqual(sum(result.values()), 240.0)
        self.assertEqual(result["p4"], 0.0)
        for pid, target in override.items():
            if pid != "p4":
                self.assertGreaterEqual(result[pid], target)
        self.assertEqual(result["p9"], 0.0)  # benched by the GM, and nine players with minutes remain
        self.assertEqual(max(("p7", "p3", "p0"), key=lambda pid: result[pid] - override[pid]), "p7")  # backup center


if __name__ == "__main__":
    unittest.main()
