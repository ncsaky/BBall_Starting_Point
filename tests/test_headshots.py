"""Staff and prospect faces: gender-matched names and faces, no repeats in a league, real photos with sources."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

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
                self.assertEqual(person["headshot_url"], faces.face_url(person["face_id"], age=person.get("age")))
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
        # As in a new save, the 30 head coaches are the real coaches (real photos): the made-up staff and the market.
        save = {"staff_slots": [person for person in staff if person["slot"] != "head_coach"], "former_staff": []}
        staff = save["staff_slots"]
        market = [candidate for slot in STAFF_SLOTS for candidate in generated_staff_candidates(5, slot)]
        apply_market_faces(save, 5, market)
        # A face repeats only once every face of that gender (generated and stock) is in use: extra uses = people
        # beyond the faces available, women none.
        everyone = [*staff, *market]
        for gender in ("male", "female"):
            people = [person for person in everyone if person["gender"] == gender]
            available = sum(faces.library_manifest()["groups"][group]["count"] for group in faces.STAFF_GROUPS[gender])
            extra = len(people) - len({person["face_id"] for person in people})
            self.assertEqual(extra, max(0, len(people) - available), gender)
        # The same candidate keeps the same face whether the market is listed for one role or all of them.
        one_role = [candidate for candidate in generated_staff_candidates(5, "scouting_lead")]
        apply_market_faces(save, 5, one_role)
        by_id = {candidate["id"]: candidate["face_id"] for candidate in market}
        self.assertTrue(all(by_id[candidate["id"]] == candidate["face_id"] for candidate in one_role))

    def test_older_staff_get_older_looking_faces_when_available(self):
        # Generated faces age with the person (no age band); once they are all in use, older staff get stock photos
        # of older-looking people.
        generated = len(faces.group_faces("gen-staff-m"))
        staff = [{"id": f"s{index}", "slot": "scouting_lead", "gender": "male", "name": f"Mark Test{index}", "age": 64}
                 for index in range(generated + 20)]
        faces.ensure_staff_faces(staff)
        seniors = set(faces.library_manifest()["groups"]["staff-m"]["senior"])
        stock = [person for person in staff if not faces.is_generated(person["face_id"])]
        self.assertEqual(len(stock), 20)
        self.assertTrue(all(int(person["face_id"].split("/")[1]) in seniors for person in stock))
        # A 64-year-old with a generated face shows that person's late-career image.
        for person in staff[:generated]:
            self.assertEqual(person["headshot_url"], faces.face_stages(person["face_id"])[-1]["file"])

    def test_real_head_coach_keeps_his_name_and_gets_his_real_photo(self):
        coach = {"id": "x", "slot": "head_coach", "name": "Steve Kerr", "status": faces.REAL_COACH_STATUS}
        faces.apply_staff_face(coach)
        self.assertEqual(coach["name"], "Steve Kerr")
        self.assertEqual(coach["gender"], "male")
        self.assertEqual(coach["headshot_source"], "real_photo")
        self.assertTrue((GUI / coach["headshot_url"].lstrip("/")).exists())

    def test_every_real_head_coach_has_his_real_photo(self):
        for entry in faces.real_manifest()["coaches"].values():
            with self.subTest(name=entry["name"]):
                coach = {"id": entry["name"], "slot": "head_coach", "name": entry["name"], "status": faces.REAL_COACH_STATUS}
                faces.apply_staff_face(coach)
                self.assertEqual(coach["headshot_source"], "real_photo")
                self.assertIn("/headshots/real/coaches/", coach["headshot_url"])
                self.assertTrue((GUI / coach["headshot_url"].lstrip("/")).exists())

    def test_an_older_save_with_a_retired_cartoon_face_gets_a_photo(self):
        person = {"id": "old-1", "slot": "scouting_lead", "name": "Nicole Nelson", "gender": "female",
                  "face_id": "staff-f/0900", "headshot_url": "/assets/headshots/generated/open-peeps/staff-f/0900.svg"}
        faces.ensure_staff_faces([person])
        self.assertEqual(person["name"], "Nicole Nelson")
        self.assertTrue(faces.valid_face(person["face_id"]))
        self.assertEqual(faces.face_gender(person["face_id"]), "female")
        self.assertTrue((GUI / person["headshot_url"].lstrip("/")).exists())
        stale = {"id": "p1", "name": "Test Prospect", "headshot_url": "/assets/headshots/generated/open-peeps/prospect-m/0001.svg"}
        self.assertIn("/headshots/generated/player-m/", faces.prospect_headshot_url(stale))

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
        for row in photos:
            with self.subTest(name=row["name"]):
                self.assertIn(row["rights"], ("free_licence_wikimedia_commons", "reference_only_not_cleared"))
                if row["rights"] == "free_licence_wikimedia_commons":  # licence and author recorded for free photos
                    self.assertTrue(row.get("licence") and row.get("author"), row["name"])

    def test_every_real_prospect_gets_a_headshot_or_a_deliberate_fallback(self):
        rows = self.manifest["prospects"]
        for entry in self.prospects:
            with self.subTest(name=entry["name"]):
                row = rows.get(entry["id"])
                self.assertIsNotNone(row)
                self.assertIn(row["status"], ("real_photo", "fallback_stock"))
                if row["status"] == "fallback_stock":
                    self.assertTrue(row.get("reason"))
                url = faces.prospect_headshot_url({"id": entry["id"], "name": entry["name"], "league": "NCAA"},
                                                  real_id=entry["id"])
                self.assertTrue((GUI / url.lstrip("/")).exists(), url)
                self.assertEqual("/headshots/real/" in url, row["status"] == "real_photo")

    def test_every_coach_in_the_game_is_listed_with_a_real_photo(self):
        self.assertEqual(len(self.manifest["coaches"]), 30)
        self.assertTrue(all(row.get("gender") for row in self.manifest["coaches"].values()))
        self.assertTrue(all(row["status"] == "real_photo" for row in self.manifest["coaches"].values()))

    def test_most_real_prospects_have_their_own_photo(self):
        rows = self.manifest["prospects"].values()
        self.assertGreaterEqual(sum(row["status"] == "real_photo" for row in rows), 580)


class ProspectFaceTests(unittest.TestCase):
    def test_draft_classes_show_a_face_for_everyone_and_no_library_face_twice(self):
        generated = set(faces.group_faces("gen-player-m"))
        for year, real, seed in (("2027", True, 9), ("2027", True, 7), ("2031", False, 9)):
            with self.subTest(year=year, seed=seed):
                prospects = [to_plain(p) for p in generate_draft_class_records(year, seed=seed, real_prospects=real)["draft_prospects"]]
                urls = [p["headshot_url"] for p in prospects]
                self.assertTrue(all(urls))
                library = [faces.face_id_from_url(url) for url in urls if "/headshots/real/" not in url]
                self.assertTrue(all(library))
                self.assertEqual(len(library), len(set(library)))
                # Generated player faces first; stock photos only once every generated face is in the class.
                stock = [face_id for face_id in library if not faces.is_generated(face_id)]
                self.assertTrue(all(face_id.startswith(("gen-player-m/", "prospect-m/")) for face_id in library))
                if stock:
                    self.assertEqual(generated, set(library) - set(stock))
                else:
                    self.assertTrue(set(library) <= generated)
                self.assertTrue(all((GUI / url.lstrip("/")).exists() for url in urls))
                if real:
                    self.assertGreater(sum("/headshots/real/" in url for url in urls), 20)


STOCK = GUI / "assets" / "headshots" / "stock"
FREE_LICENCES = ("CC0", "Public domain", "Public Domain Mark", "CC BY ", "CC BY-SA ")


class StockLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = faces.library_manifest(faces.LIBRARY)
        cls.credits = json.loads((STOCK / "credits.json").read_text())["photos"]

    def test_every_face_in_the_game_is_a_photo_with_no_cartoon_assets_left(self):
        headshots = GUI / "assets" / "headshots"
        self.assertFalse((headshots / "generated" / "open-peeps").exists())
        files = [path for path in headshots.rglob("*") if path.is_file() and path.suffix != ".json"]
        self.assertTrue(files)
        self.assertEqual({path.suffix for path in files} - {".avif", ".jpg"}, set())
        self.assertFalse((ROOT / "scripts" / "build_face_library.mjs").exists())

    def test_library_manifest_matches_its_files_and_is_big_enough(self):
        self.assertEqual(faces.LIBRARY, "stock")
        groups = self.manifest["groups"]
        for group, info in groups.items():
            entries = {face_id: entry for face_id, entry in self.manifest["faces"].items() if face_id.startswith(f"{group}/")}
            self.assertEqual(len(entries), info["count"], group)
            for face_id, entry in entries.items():
                self.assertEqual(entry["gender"], info["gender"])
                self.assertTrue(entry["stages"] and entry["stages"][0]["min_age"] == 0, face_id)
                for stage in entry["stages"]:
                    self.assertTrue((GUI / stage["file"].lstrip("/")).exists(), stage["file"])
        self.assertEqual(groups["staff-m"]["gender"], "male")
        self.assertEqual(groups["staff-f"]["gender"], "female")
        self.assertGreaterEqual(groups["staff-m"]["count"] + groups["staff-f"]["count"], 300)  # Commons only (Openverse dropped: robots.txt)
        self.assertGreaterEqual(groups["staff-f"]["count"], 50)
        self.assertGreaterEqual(len(groups["staff-m"]["senior"]), 20)
        self.assertGreaterEqual(groups["prospect-m"]["count"], 60)  # a generated draft class has 60 prospects
        total = sum(path.stat().st_size for path in (GUI / "assets" / "headshots").rglob("*") if path.is_file())
        self.assertLess(total, 80_000_000)

    def test_a_face_shows_the_career_stage_that_fits_the_age(self):
        staged = {"library": "stock", "ext": "avif", "groups": {"staff-m": {"gender": "male", "count": 1}},
                  "faces": {"staff-m/0001": {"gender": "male", "stages": [
                      {"min_age": 36, "file": "/assets/headshots/stock/staff-m/0001-veteran.avif"},
                      {"min_age": 0, "file": "/assets/headshots/stock/staff-m/0001-rookie.avif"},
                      {"min_age": 26, "file": "/assets/headshots/stock/staff-m/0001-prime.avif"}]}}}
        with mock.patch.object(faces, "library_manifest", lambda library=faces.LIBRARY: staged), \
                mock.patch.object(faces, "_stage_files", lambda library=faces.LIBRARY: {
                    stage["file"]: "staff-m/0001" for stage in staged["faces"]["staff-m/0001"]["stages"]}):
            self.assertTrue(faces.face_url("staff-m/0001", age=21).endswith("rookie.avif"))
            self.assertTrue(faces.face_url("staff-m/0001", age=26).endswith("prime.avif"))
            self.assertTrue(faces.face_url("staff-m/0001", age=58).endswith("veteran.avif"))
            self.assertTrue(faces.face_url("staff-m/0001").endswith("rookie.avif"))  # unknown age: first stage
            # A stored picture moves to the stage for the person's current age; staff refresh as they age.
            self.assertTrue(faces.stage_url("/assets/headshots/stock/staff-m/0001-rookie.avif", 40).endswith("veteran.avif"))
            person = {"id": "s1", "name": "Mark Test", "gender": "male", "age": 30, "face_id": "staff-m/0001",
                      "headshot_url": "/assets/headshots/stock/staff-m/0001-rookie.avif", "headshot_source": "stock_photo"}
            faces.ensure_staff_faces([person])
            self.assertTrue(person["headshot_url"].endswith("prime.avif"))
        # A one-photo face is a single stage.
        face_id = next(iter(self.manifest["faces"]))
        self.assertEqual(faces.face_url(face_id, age=70), faces.face_url(face_id, age=20))

    def test_every_stock_photo_has_a_credit_with_an_allowed_licence(self):
        library = {f"{group}/{n:04d}" for group, info in self.manifest["groups"].items() for n in range(1, info["count"] + 1)}
        self.assertEqual({photo["face_id"] for photo in self.credits}, library)
        for photo in self.credits:
            with self.subTest(face=photo["face_id"]):
                self.assertTrue(photo["author"] and photo["source_url"] and photo["title"])
                self.assertTrue(photo["licence"].startswith(FREE_LICENCES), photo["licence"])
                if photo["licence"].startswith(("CC BY ", "CC BY-SA ")):
                    self.assertTrue(photo.get("licence_url"))
                self.assertTrue((GUI / photo["file"].lstrip("/")).exists())
                self.assertLess((GUI / photo["file"].lstrip("/")).stat().st_size, 30_000)


GENERATED = GUI / "assets" / "headshots" / "generated"


class GeneratedFaceTests(unittest.TestCase):
    """AI-generated faces of fictional people (scripts/build_generated_faces.py): used before stock photos, and every
    display shows the image for the person's current age."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = faces.library_manifest(faces.GENERATED)
        cls.source = json.loads((ROOT / "data" / "research" / "headshot_gen_library_manifest.json").read_text())

    def test_every_listed_fictional_person_is_in_the_game_with_all_stages(self):
        self.assertEqual({entry["source_id"] for entry in self.manifest["faces"].values()},
                         {person["id"] for person in self.source["people"]})  # re-run the build script per batch
        for group, info in self.manifest["groups"].items():
            self.assertEqual(len(faces.group_faces(group)), info["count"], group)
        self.assertEqual(self.manifest["groups"]["gen-staff-f"]["gender"], "female")
        for face_id, entry in self.manifest["faces"].items():
            with self.subTest(face=face_id):
                self.assertTrue(faces.is_generated(face_id))
                self.assertEqual(faces.face_gender(face_id), entry["gender"])
                self.assertEqual(len(entry["stages"]), 4 if face_id.startswith("gen-player-m/") else 3)
                ages = [stage["min_age"] for stage in entry["stages"]]
                self.assertEqual(ages[0], 0)
                self.assertEqual(ages, sorted(set(ages)))
                for stage in entry["stages"]:
                    path = GUI / stage["file"].lstrip("/")
                    self.assertTrue(path.exists(), stage["file"])
                    self.assertLess(path.stat().st_size, 15_000)

    def test_each_stage_shows_from_its_min_age(self):
        for face_id, entry in self.manifest["faces"].items():
            stages = entry["stages"]
            for previous, stage in zip([None, *stages], stages):
                with self.subTest(face=face_id, min_age=stage["min_age"]):
                    self.assertEqual(faces.face_url(face_id, age=stage["min_age"]), stage["file"])
                    self.assertEqual(faces.face_url(face_id, age=stage["min_age"] + 0.9), stage["file"])
                    if previous:
                        self.assertEqual(faces.face_url(face_id, age=stage["min_age"] - 0.1), previous["file"])
                        # A stored picture moves to the stage for the person's age, either way.
                        self.assertEqual(faces.stage_url(previous["file"], stage["min_age"]), stage["file"])
                        self.assertEqual(faces.stage_url(stage["file"], stage["min_age"] - 1), previous["file"])

    def test_made_up_staff_get_generated_faces_before_stock_photos(self):
        for gender, name in (("male", "Mark"), ("female", "Nicole")):
            generated = len(faces.group_faces(faces.STAFF_GROUPS[gender][0]))
            staff = [{"id": f"{gender}{index}", "slot": "scouting_lead", "gender": gender, "name": f"{name} Test{index}",
                      "age": 35 + index % 30} for index in range(generated + 10)]
            faces.ensure_staff_faces(staff)
            with self.subTest(gender=gender):
                face_ids = [person["face_id"] for person in staff]
                self.assertEqual(len(set(face_ids)), len(staff))
                self.assertEqual(sum(map(faces.is_generated, face_ids)), generated)
                self.assertTrue(all(not faces.is_generated(face_id) for face_id in face_ids[generated:]))
                for person in staff:
                    self.assertEqual(faces.face_gender(person["face_id"]), gender)
                    self.assertEqual(person["headshot_source"], faces.face_source(person["face_id"]))
                    self.assertEqual(person["headshot_url"], faces.face_url(person["face_id"], age=person["age"]))

    def test_a_new_league_spreads_generated_staff_faces_across_teams_with_the_users_team_first(self):
        staff = [person for person in league_staff() if person["slot"] != "head_coach"]
        save = {"meta": {"user_team_id": "team_29"}, "staff_slots": staff, "former_staff": []}
        faces.ensure_save_staff_faces(save)
        self.assertTrue(all(faces.is_generated(person["face_id"]) for person in staff if person["team_id"] == "team_29"))
        teams = {person["team_id"] for person in staff if faces.is_generated(person["face_id"])}
        self.assertGreater(len(teams), 15)

    def test_a_drafted_made_up_player_looks_older_as_seasons_pass(self):
        from nba_gm_data.draft import rookie_player_record
        from nba_gm_data.save import apply_effective_player_ages, canonical_with_save
        from nba_gm_data.schema import RookieContractProjection
        import inspect

        prospects = [to_plain(p) for p in generate_draft_class_records("2031", seed=9, real_prospects=False)["draft_prospects"]]
        prospect = next(p for p in prospects if faces.is_generated(faces.face_id_from_url(p["headshot_url"])))
        face_id = faces.face_id_from_url(prospect["headshot_url"])
        contract = RookieContractProjection("c1", "s1", prospect["id"], "team_00", "2031", "rookie_scale", "active", [], 0.0, 0.0, [], "")
        player = rookie_player_record({"draft_year": "2031", "overall_pick": 5, "name": prospect["name"]}, prospect,
                                      {"id": "team_00", "abbrev": "AAA"}, contract)
        nba_player = {"id": "real", "age": 25, "age_base_start_year": 2026,
                      "headshot_url": "https://a.espncdn.com/i/headshots/nba/players/full/1.png"}
        rookie_age = player["age"]
        shown = {}
        for season in range(2031, 2051):  # ages about 20 to 39
            canonical = {"players": [dict(player), dict(nba_player)]}
            save = {"meta": {"season": f"{season}-{str(season + 1)[-2:]}"}, "state": {"current_date": f"{season}-12-01"}}
            apply_effective_player_ages(canonical, save)
            faces.stage_player_headshots(canonical["players"])
            rookie, real = canonical["players"]
            self.assertEqual(rookie["age"], rookie_age + season - 2031)
            self.assertEqual(rookie["headshot_url"], faces.face_url(face_id, age=rookie["age"]))
            self.assertEqual(real["headshot_url"], nba_player["headshot_url"])  # real NBA players keep their photo
            shown[season] = rookie["headshot_url"]
        self.assertEqual(shown[2031], prospect["headshot_url"])  # the face he had as a prospect
        self.assertEqual(len(set(shown.values())), len(faces.face_stages(face_id)))  # every career stage appears
        self.assertEqual(shown[2050], faces.face_stages(face_id)[-1]["file"])
        # The save's active universe applies it right after the ages (what every player display reads).
        source = inspect.getsource(canonical_with_save)
        self.assertLess(source.index("apply_effective_player_ages(canonical, save)"), source.index("stage_player_headshots("))


if __name__ == "__main__":
    unittest.main()
