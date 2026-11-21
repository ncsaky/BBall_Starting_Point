"""Staff and prospect faces: gender-matched names and faces, no repeats in a league, real photos with sources."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from nba_gm_data import faces, staff_names
from nba_gm_data.draft import generate_draft_class_records
from nba_gm_data.schema import to_plain
from nba_gm_data.staff import STAFF_SLOTS, apply_market_faces, generated_staff_candidates, interim_staff

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "src" / "nba_gm_data" / "gui"
REAL = GUI / "assets" / "headshots" / "real"
TEAMS = [f"team_{index:02d}" for index in range(30)]


def league_staff(seed: int = 11) -> list[dict]:
    """A full league of made-up staff (30 teams x 6 roles), named the way a new save names them."""
    used: set[str] = set()
    staff = []
    for team in TEAMS:
        for slot in STAFF_SLOTS:
            identity = faces.draw_staff_identity(f"{seed}:{team}:{slot}", slot, used)
            used.add(identity["name"].lower())
            staff.append({"id": f"{team}:{slot}", "team_id": team, "slot": slot, "age": 30 + len(staff) % 35, **identity})
    return staff


class StaffIdentityTests(unittest.TestCase):
    def test_name_lists_never_share_a_first_name_and_leave_out_unisex_names(self):
        male, female = set(staff_names.ALL_FIRST_NAMES["male"]), set(staff_names.ALL_FIRST_NAMES["female"])
        self.assertFalse(male & female)
        for unisex in ("Jordan", "Taylor", "Jamie", "Quinn", "Kelly", "Morgan", "Alex", "Sam", "Drew", "Leslie", "Andrea"):
            self.assertNotIn(unisex, male)
        self.assertGreater(len(male), 250)
        self.assertGreater(len(female), 150)
        self.assertGreater(len(staff_names.ALL_LAST_NAMES), 300)

    def test_generated_staff_names_and_faces_always_share_a_gender(self):
        staff = league_staff()
        market = [candidate for slot in STAFF_SLOTS for candidate in generated_staff_candidates(5, slot)]
        interims = [interim_staff(team, "performance_lead", "2026-12-01", nonce) for nonce, team in enumerate(TEAMS)]
        everyone = [*staff, *market, *interims]
        faces.ensure_staff_faces(everyone)
        for person in everyone:
            with self.subTest(name=person["name"]):
                self.assertIn(person["gender"], ("male", "female"))
                self.assertEqual(staff_names.first_name_gender(person["name"]), person["gender"])
                self.assertEqual(faces.face_gender(person["face_id"]), person["gender"])
                self.assertTrue(person["headshot_url"].endswith(f"{person['face_id']}.svg"))
                self.assertTrue((GUI / person["headshot_url"].lstrip("/")).exists())

    def test_women_hold_a_realistic_minority_of_staff_jobs(self):
        staff = league_staff()
        women = [person for person in staff if person["gender"] == "female"]
        self.assertTrue(8 <= len(women) <= 45, len(women))
        heads = [person for person in staff if person["slot"] == "head_coach" and person["gender"] == "female"]
        self.assertLessEqual(len(heads), 3)

    def test_no_face_or_name_repeats_across_a_full_league_staff_and_its_market(self):
        staff = league_staff()
        faces.ensure_staff_faces(staff)
        self.assertEqual(len({person["face_id"] for person in staff}), len(staff))
        self.assertEqual(len({person["name"] for person in staff}), len(staff))
        save = {"staff_slots": staff, "former_staff": []}
        market = [candidate for slot in STAFF_SLOTS for candidate in generated_staff_candidates(5, slot)]
        apply_market_faces(save, 5, market)
        held = {person["face_id"] for person in staff}
        self.assertFalse(held & {candidate["face_id"] for candidate in market})
        self.assertEqual(len({candidate["face_id"] for candidate in market}), len(market))
        # The same candidate keeps the same face whether the market is listed for one role or all of them.
        one_role = [candidate for candidate in generated_staff_candidates(5, "scouting_lead")]
        apply_market_faces(save, 5, one_role)
        by_id = {candidate["id"]: candidate["face_id"] for candidate in market}
        self.assertTrue(all(by_id[candidate["id"]] == candidate["face_id"] for candidate in one_role))

    def test_older_staff_get_grey_haired_faces_when_available(self):
        staff = [{"id": f"s{index}", "slot": "scouting_lead", "gender": "male", "name": f"Mark Test{index}", "age": 64}
                 for index in range(20)]
        faces.ensure_staff_faces(staff)
        seniors = set(faces.library_manifest()["groups"]["staff-m"]["senior"])
        self.assertTrue(all(int(person["face_id"].split("/")[1]) in seniors for person in staff))

    def test_real_head_coach_keeps_his_name_and_gets_his_real_photo(self):
        coach = {"id": "x", "slot": "head_coach", "name": "Steve Kerr", "status": faces.REAL_COACH_STATUS}
        faces.apply_staff_face(coach)
        self.assertEqual(coach["name"], "Steve Kerr")
        self.assertEqual(coach["gender"], "male")
        self.assertEqual(coach["headshot_source"], "real_photo")
        self.assertTrue((GUI / coach["headshot_url"].lstrip("/")).exists())
        # A real coach without a freely licensed photo gets a generated face of his own gender.
        missing = next(entry for entry in faces.real_manifest()["coaches"].values() if entry["status"] != "real_photo")
        other = {"id": "y", "slot": "head_coach", "name": missing["name"], "status": faces.REAL_COACH_STATUS}
        faces.apply_staff_face(other)
        self.assertEqual(faces.face_gender(other["face_id"]), missing["gender"])

    def test_made_up_staff_never_take_a_real_head_coach_name(self):
        reserved = faces.reserved_real_names()
        staff = league_staff(seed=3)
        self.assertFalse({faces.normalize_name(person["name"]) for person in staff} & reserved)


class RealPhotoManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((REAL / "manifest.json").read_text())
        cls.prospects = json.loads((ROOT / "data" / "canonical" / "real_prospects.json").read_text())["prospects"]

    def test_every_real_photo_has_a_source_a_date_and_a_file(self):
        rows = [*self.manifest["coaches"].values(), *self.manifest["prospects"].values()]
        photos = [row for row in rows if row["status"] == "real_photo"]
        self.assertGreater(len(photos), 400)
        for row in photos:
            with self.subTest(name=row["name"]):
                for field in ("source", "source_url", "source_page", "fetched", "rights", "file"):
                    self.assertTrue(row.get(field), field)
                self.assertTrue((GUI / row["file"].lstrip("/")).exists())
                self.assertLess((GUI / row["file"].lstrip("/")).stat().st_size, 45_000)
        for row in self.manifest["coaches"].values():
            if row["status"] == "real_photo":
                self.assertTrue(row.get("licence"), row["name"])  # Commons licence recorded for every coach photo

    def test_every_real_prospect_gets_a_headshot_or_a_deliberate_fallback(self):
        rows = self.manifest["prospects"]
        for entry in self.prospects:
            with self.subTest(name=entry["name"]):
                row = rows.get(entry["id"])
                self.assertIsNotNone(row)
                self.assertIn(row["status"], ("real_photo", "fallback_generated"))
                if row["status"] == "fallback_generated":
                    self.assertTrue(row.get("reason"))
                url = faces.prospect_headshot_url({"id": entry["id"], "name": entry["name"], "league": "NCAA"},
                                                  real_id=entry["id"])
                self.assertTrue((GUI / url.lstrip("/")).exists(), url)
                self.assertEqual("/headshots/real/" in url, row["status"] == "real_photo")

    def test_every_coach_in_the_game_is_listed(self):
        self.assertEqual(len(self.manifest["coaches"]), 30)
        self.assertTrue(all(row.get("gender") for row in self.manifest["coaches"].values()))


class ProspectFaceTests(unittest.TestCase):
    def test_draft_classes_show_a_face_for_everyone_and_no_generated_face_twice(self):
        for year, real in (("2027", True), ("2031", False)):
            with self.subTest(year=year):
                prospects = [to_plain(p) for p in generate_draft_class_records(year, seed=9, real_prospects=real)["draft_prospects"]]
                urls = [p["headshot_url"] for p in prospects]
                self.assertTrue(all(urls))
                generated = [url for url in urls if "/generated/" in url]
                self.assertEqual(len(generated), len(set(generated)))
                self.assertTrue(all((GUI / url.lstrip("/")).exists() for url in urls))
                if real:
                    self.assertGreater(sum("/headshots/real/" in url for url in urls), 20)

    def test_generated_library_manifest_matches_its_files(self):
        manifest = faces.library_manifest()
        self.assertTrue(manifest["licence"]["name"])
        base = GUI / "assets" / "headshots" / "generated" / faces.LIBRARY
        for group, info in manifest["groups"].items():
            files = list((base / group).glob("*.svg"))
            self.assertEqual(len(files), info["count"], group)
        self.assertGreaterEqual(manifest["groups"]["staff-m"]["count"] + manifest["groups"]["staff-f"]["count"], 600)


if __name__ == "__main__":
    unittest.main()
