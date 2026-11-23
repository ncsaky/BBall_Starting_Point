"""Drafted players (2026+) take the roles of the veterans whose ratings are shaped most like theirs."""
import unittest

from nba_gm_data.role_estimate import ROLE_SOURCE, assign_estimated_roles


def vet(pid, off, deff, height, **traits):
    return {"id": pid, "draft_year": 2015, "height_inches": height, "primary_off_role": off, "primary_def_role": deff}, traits


class RoleEstimateTests(unittest.TestCase):
    def league(self):
        players, traits = [], {}
        for i in range(10):
            p, t = vet(f"g{i}", "Primary Ball Handler", "On-Ball Guard", 75 + i % 2, shooting=70 + i, passing=80 + i, rebounding=40, rim=30)
            players.append(p); traits[p["id"]] = t
            p, t = vet(f"b{i}", "Rollman", "Rim Protector", 84 + i % 2, shooting=40, passing=45, rebounding=80 + i, rim=82 + i)
            players.append(p); traits[p["id"]] = t
        return players, traits

    def test_raw_big_rookie_matches_bigs_by_shape_not_level(self):
        players, traits = self.league()
        rookie = {"id": "r1", "draft_year": 2026, "height_inches": 85, "primary_off_role": "Connector", "primary_def_role": "Rookie"}
        players.append(rookie)
        traits["r1"] = {"shooting": 35, "passing": 38, "rebounding": 58, "rim": 60}  # low level, big's shape
        self.assertEqual(assign_estimated_roles({"players": players}, traits), 1)
        self.assertEqual((rookie["primary_off_role"], rookie["primary_def_role"]), ("Rollman", "Rim Protector"))
        self.assertEqual(rookie["role_source"], ROLE_SOURCE)

    def test_veterans_untouched_and_deterministic(self):
        players, traits = self.league()
        rookie = {"id": "r2", "draft_year": 2027, "height_inches": 75, "primary_off_role": "connector_guard", "primary_def_role": "Rookie"}
        players.append(rookie)
        traits["r2"] = {"shooting": 55, "passing": 62, "rebounding": 30, "rim": 25}
        before = [dict(p) for p in players if p["id"] != "r2"]
        assign_estimated_roles({"players": players}, traits)
        first = (rookie["primary_off_role"], rookie["primary_def_role"])
        assign_estimated_roles({"players": players}, traits)
        self.assertEqual(first, (rookie["primary_off_role"], rookie["primary_def_role"]))
        self.assertEqual(first, ("Primary Ball Handler", "On-Ball Guard"))
        self.assertEqual(before, [p for p in players if p["id"] != "r2"])


if __name__ == "__main__":
    unittest.main()
