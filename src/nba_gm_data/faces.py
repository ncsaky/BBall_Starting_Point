"""Faces for people shown in the game.

Real people (the real head coaches, real draft prospects) use their own public photo when one was found
(gui/assets/headshots/real/, listed with sources in its manifest.json; scripts/fetch_real_headshots.py); real NBA
players keep their NBA headshots.
Made-up people (staff, draft prospects and the players they become) get, in order of preference:
  1. a generated face (gui/assets/headshots/generated/, scripts/build_generated_faces.py): an AI-generated portrait of
     a fictional person (no real person is depicted), made with OpenAI's image tool, with images at several ages;
  2. once every generated face of their gender and kind is in use, a stock photo (gui/assets/headshots/stock/,
     scripts/build_stock_faces.py): openly licensed photos of real, non-famous adults, each credited in
     stock/credits.json and in the game's Photo credits view.
Every face is tagged with one gender, and a made-up staff member's name is drawn from the same gender's name list
(staff_names.py), so name and face always agree.

A face is a library id such as "gen-staff-f/0004" (generated) or "staff-f/0042" (stock). Within a league, faces are
handed out so that no two staff members share one while unused faces remain, and no two prospects in a draft class
share one. Faces never draw from a game random stream: picks come from stable hashes of the person's key.

Faces age: a face may hold several images by age ("stages"), and every display shows the stage for the person's
current age (staff when their faces are ensured, players when the save's ages are applied: save.py
apply_effective_player_ages, prospects when shown).
"""

from __future__ import annotations

import hashlib
import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from . import staff_names
from .utils import normalize_name

# The face libraries (gui/assets/headshots/<library>/manifest.json), in order of preference for made-up people.
LIBRARY = "stock"  # openly licensed photos of real, non-famous adults (one stage each)
GENERATED = "generated"  # AI-generated fictional people, several stages by age ("gen-" group prefix)
LIBRARIES = (GENERATED, LIBRARY)
ASSETS = Path(__file__).resolve().parent / "gui" / "assets" / "headshots"
URL_ROOT = "/assets/headshots"
# Groups to draw from for each kind of made-up person, generated first.
STAFF_GROUPS = {"male": ("gen-staff-m", "staff-m"), "female": ("gen-staff-f", "staff-f")}
PROSPECT_GROUPS = ("gen-player-m", "prospect-m")

# Share of women among made-up staff, by role. NBA benches are still mostly men (women hold roughly one in
# twenty assistant-coach jobs), with more women in player development, scouting and analytics, and the most in
# medical and performance staff. Head coaches are almost all men; a woman can still be promoted or hired.
STAFF_WOMEN_SHARE = {
    "head_coach": 0.03,
    "offensive_coordinator": 0.07,
    "defensive_coordinator": 0.07,
    "development_lead": 0.14,
    "scouting_lead": 0.14,
    "performance_lead": 0.24,
}
SENIOR_AGE, YOUNG_AGE = 57, 47
REAL_COACH_STATUS = "real_head_coach_name_gameplay_profile"


def _stable_int(text: str) -> int:
    return int.from_bytes(hashlib.sha1(text.encode("utf-8")).digest()[:8], "big")


@lru_cache(maxsize=4)
def _read_manifest(library: str) -> dict[str, Any]:
    try:
        return json.loads((ASSETS / library / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"groups": {}}


@lru_cache(maxsize=4)
def library_manifest(library: str | None = None) -> dict[str, Any]:
    """One library's manifest, or (no library given) every library merged: groups and faces of all of them (their
    ids never collide: generated groups carry a "gen-" prefix)."""
    if library:
        return _read_manifest(library)
    merged: dict[str, Any] = {"ext": _read_manifest(LIBRARY).get("ext", "avif"), "groups": {}, "faces": {}}
    for name in reversed(LIBRARIES):
        manifest = _read_manifest(name)
        merged["groups"].update({group: {**info, "library": name} for group, info in (manifest.get("groups") or {}).items()})
        merged["faces"].update(manifest.get("faces") or {})
    return merged


@lru_cache(maxsize=16)
def group_faces(group: str) -> tuple[str, ...]:
    """The face ids of one group, in id order."""
    ids = sorted(face_id for face_id in (library_manifest().get("faces") or {}) if face_id.split("/")[0] == group)
    if not ids:  # a library without per-face entries: <group>/0001 .. <group>/<count>
        count = int((library_manifest().get("groups", {}).get(group) or {}).get("count") or 0)
        ids = [f"{group}/{index:04d}" for index in range(1, count + 1)]
    return tuple(ids)


def is_generated(face_id: str | None) -> bool:
    return str(face_id or "").startswith("gen-")


@lru_cache(maxsize=1)
def real_manifest() -> dict[str, Any]:
    try:
        return json.loads((ASSETS / "real" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# Career stages. A library face is one fictional person and may hold several images of that person at different
# ages (for example rookie, prime, veteran, late career), each with the youngest age it is shown from:
#   manifest["faces"]["staff-m/0042"] = {"gender": "male",
#                                         "stages": [{"min_age": 0, "file": "/assets/.../0042-a.avif"},
#                                                    {"min_age": 26, "file": "/assets/.../0042-b.avif"}]}
# The picture shown is the last stage whose min_age is at or below the person's current age. A single photo is a
# face with one stage (min_age 0). A face missing from manifest["faces"] is one stage at <library>/<id>.<ext>.
def face_entry(face_id: str | None, library: str | None = None) -> dict[str, Any] | None:
    return (library_manifest(library).get("faces") or {}).get(str(face_id or ""))


def face_stages(face_id: str | None, library: str | None = None) -> list[dict[str, Any]]:
    if not face_id:
        return []
    entry = face_entry(face_id, library) or {}
    stages = [stage for stage in entry.get("stages") or [] if stage.get("file")]
    if not stages:
        ext = library_manifest(library).get("ext", "avif")
        stages = [{"min_age": 0, "file": f"{URL_ROOT}/{library or LIBRARY}/{face_id}.{ext}"}]
    return sorted(stages, key=lambda stage: float(stage.get("min_age") or 0))


def stage_file(stages: list[dict[str, Any]], age: Any = None) -> str | None:
    """The image for a person of this age: the last stage whose min_age <= age (the first stage if age is unknown)."""
    if not stages:
        return None
    try:
        age = float(age)
    except (TypeError, ValueError):
        return stages[0]["file"]
    chosen = stages[0]
    for stage in stages:
        if float(stage.get("min_age") or 0) <= age:
            chosen = stage
    return chosen["file"]


def face_url(face_id: str | None, library: str | None = None, age: Any = None) -> str | None:
    return stage_file(face_stages(face_id, library), age)


@lru_cache(maxsize=4)
def _stage_files(library: str | None = None) -> dict[str, str]:
    return {stage["file"]: face_id for face_id, entry in (library_manifest(library).get("faces") or {}).items()
            for stage in entry.get("stages") or [] if stage.get("file")}


def face_id_from_url(url: str | None, library: str | None = None) -> str | None:
    """The library face a stored picture URL belongs to (any of its stages), or None for real photos."""
    text = str(url or "")
    if text in _stage_files(library):
        return _stage_files(library)[text]
    marker = f"{URL_ROOT}/{library or LIBRARY}/"
    return text[len(marker):].rsplit(".", 1)[0] if text.startswith(marker) else None


def stage_url(url: str | None, age: Any, library: str | None = None) -> str | None:
    """A stored picture URL moved to the stage that fits the person's current age (real photos and NBA headshots
    unchanged)."""
    if not str(url or "").startswith(URL_ROOT):
        return url
    face_id = face_id_from_url(url, library)
    return face_url(face_id, library, age) if face_id and valid_face(face_id, library) else url


def face_gender(face_id: str | None, library: str | None = None) -> str | None:
    entry = face_entry(face_id, library)
    if entry and entry.get("gender"):
        return entry["gender"]
    group = str(face_id or "").split("/")[0]
    return (library_manifest(library).get("groups", {}).get(group) or {}).get("gender")


def valid_face(face_id: str | None, library: str | None = None) -> bool:
    """A face id that exists in a current library (older saves may hold ids from a retired library)."""
    if face_entry(face_id, library):
        return True
    group, _, index = str(face_id or "").partition("/")
    info = library_manifest(library).get("groups", {}).get(group) or {}
    return index.isdigit() and 1 <= int(index) <= int(info.get("count") or 0)


def is_current_url(url: str | None, library: str | None = None) -> bool:
    """A picture URL that the current game ships: a real photo or an image of a current library's face. (The
    retired cartoon library of older saves also lived under generated/: only listed stage images count there.)"""
    text = str(url or "")
    if text.startswith(f"{URL_ROOT}/real/") or text in _stage_files(library):
        return True
    return LIBRARY in ((library,) if library else LIBRARIES) and text.startswith(f"{URL_ROOT}/{LIBRARY}/")


def senior_band(age: Any) -> bool | None:
    """Older-looking faces for older staff, younger-looking faces for younger staff, either in between."""
    try:
        age = float(age)
    except (TypeError, ValueError):
        return None
    return True if age >= SENIOR_AGE else False if age <= YOUNG_AGE else None


def _free_face(group: str, key: str, used: set[str], senior: bool | None) -> str | None:
    """The first unused face of a group from a stable start (matching the age band first), or None if all are used.
    Generated faces age with the person, so they have no age band."""
    ids = group_faces(group)
    if not ids:
        return None
    info = library_manifest().get("groups", {}).get(group) or {}
    seniors = set(info.get("senior") or [])
    start = _stable_int(f"{group}:{key}") % len(ids)
    bands = (True, False) if senior is not None and seniors else (False,)
    for match_band in bands:
        for step in range(len(ids)):
            face_id = ids[(start + step) % len(ids)]
            if face_id in used or (match_band and (int(face_id.split("/")[1]) in seniors) != senior):
                continue
            return face_id
    return None


def pick_face(group: str | Iterable[str], key: str, used: set[str] | None = None, *,
              senior: bool | None = None) -> str | None:
    """The face for one person from one group or from groups in order of preference (generated first, then stock):
    a stable start from his or her key, then the next unused face. Reuses a face only once every face of every
    group is taken (then the first group's stable choice)."""
    groups = (group,) if isinstance(group, str) else tuple(group)
    used = used or set()
    for name in groups:
        face_id = _free_face(name, key, used, None if is_generated(f"{name}/") else senior)
        if face_id:
            return face_id
    for name in groups:
        ids = group_faces(name)
        if ids:
            return ids[_stable_int(f"{name}:{key}") % len(ids)]
    return None


# ------------------------------------------------------------------------------------------------ staff
def staff_groups(gender: str) -> tuple[str, ...]:
    """The face groups for made-up staff of this gender, generated faces first."""
    return STAFF_GROUPS["female" if gender == "female" else "male"]


def face_source(face_id: str | None) -> str:
    return "generated_face" if is_generated(face_id) else "stock_photo"


@lru_cache(maxsize=1)
def reserved_real_names() -> frozenset[str]:
    """Real head coaches (now and recent): made-up staff never take one of these names."""
    from .staff import HEAD_COACH_REPUTATION_GRADES

    names = {normalize_name(name) for name in HEAD_COACH_REPUTATION_GRADES}
    names |= {normalize_name(entry.get("name")) for entry in (real_manifest().get("coaches") or {}).values()}
    return frozenset(names)


def draw_staff_identity(key: str, slot: str | None, avoid_names: set[str] | None = None) -> dict[str, str]:
    """Gender and a matching name for a made-up staff member (own random stream: other draws are unchanged)."""
    rng = random.Random(f"{key}:staff_identity_v1")
    gender = "female" if rng.random() < STAFF_WOMEN_SHARE.get(str(slot or ""), 0.1) else "male"
    avoid = (avoid_names or set()) | reserved_real_names()
    name = staff_names.draw_name(rng, gender)
    for _ in range(40):
        if normalize_name(name) not in avoid:
            break
        name = staff_names.draw_name(rng, gender)
    return {"gender": gender, "name": name}


def real_coach_entry(name: Any) -> dict[str, Any] | None:
    return (real_manifest().get("coaches") or {}).get(normalize_name(name))


def is_real_staff(staff: dict[str, Any]) -> bool:
    return bool(staff.get("real_person")) or staff.get("status") == REAL_COACH_STATUS


def apply_staff_face(staff: dict[str, Any], used: set[str] | None = None) -> None:
    """Give one staff member a gender and a face if missing: the real photo for a real coach, else a library face
    of the staff member's gender: a generated face while one is free, else a stock photo (matching the age band)."""
    if is_real_staff(staff):
        staff["real_person"] = True
        entry = real_coach_entry(staff.get("name")) or {}
        staff.setdefault("gender", entry.get("gender") or "male")
        if entry.get("status") == "real_photo" and entry.get("file"):
            staff["headshot_url"] = entry["file"]
            staff["headshot_source"] = "real_photo"
            staff.pop("face_id", None)
            return
    if not staff.get("gender"):
        staff["gender"] = staff_names.first_name_gender(staff.get("name")) or "male"
    if not valid_face(staff.get("face_id")) or face_gender(staff["face_id"]) != staff["gender"]:
        key = str(staff.get("market_source_id") or staff.get("id") or staff.get("name"))
        staff["face_id"] = pick_face(staff_groups(staff["gender"]), key, used, senior=senior_band(staff.get("age")))
    staff["headshot_url"] = face_url(staff["face_id"], age=staff.get("age"))
    staff["headshot_source"] = face_source(staff["face_id"])


def has_current_face(person: dict[str, Any]) -> bool:
    """Already shows a picture the game ships (older saves may point at a retired library: they get a new one)."""
    if not is_current_url(person.get("headshot_url")):
        return False
    return person.get("headshot_source") == "real_photo" or valid_face(person.get("face_id"))


def save_staff_people(save: dict[str, Any]) -> list[dict[str, Any]]:
    return [*save.get("staff_slots", []), *save.get("former_staff", []), *(save.get("staff_market_pool") or [])]


def ensure_staff_faces(people: Iterable[dict[str, Any]], held: Iterable[dict[str, Any]] = ()) -> None:
    """Faces for everyone listed who has none, avoiding faces already held (by `held` or earlier people).
    A newly faced made-up person whose name is already taken in the league gets a fresh name of the same gender."""
    people = list(people)
    held = list(held)
    used_faces = {p["face_id"] for p in [*held, *people] if has_current_face(p) and p.get("face_id")}
    used_names = {normalize_name(p.get("name")) for p in [*held, *people] if p.get("headshot_url")}
    for person in people:
        if has_current_face(person):
            if person.get("face_id"):
                # The career stage that fits the person's current age (staff age each season).
                person["headshot_url"] = face_url(person["face_id"], age=person.get("age"))
            continue
        if person.get("headshot_url") and not is_real_staff(person):
            # A face from a retired library (older save): a new photo, same person and name.
            person.pop("face_id", None)
            apply_staff_face(person, used_faces)
            used_faces.add(person["face_id"])
            continue
        if not is_real_staff(person) and normalize_name(person.get("name")) in used_names:
            # A new made-up person whose name is taken: a fresh name from the same gender's list.
            key = str(person.get("market_source_id") or person.get("id"))
            gender = person.get("gender") or staff_names.first_name_gender(person.get("name")) or "male"
            rng = random.Random(f"{key}:rename_v1")
            for _ in range(40):
                person["name"] = staff_names.draw_name(rng, gender)
                if normalize_name(person["name"]) not in used_names | reserved_real_names():
                    break
        apply_staff_face(person, used_faces)
        if person.get("face_id"):
            used_faces.add(person["face_id"])
        used_names.add(normalize_name(person.get("name")))


def ensure_save_staff_faces(save: dict[str, Any]) -> None:
    """Every staff member stored in the save (employed, former, market pool) has a gender and a face.
    Employed staff are faced first: the user's own staff, then the rest of the league in a stable shuffled order, so
    the generated faces (preferred while free) spread across teams instead of filling the first teams listed."""
    for staff in save.get("staff_slots", []):
        if staff.get("status") == REAL_COACH_STATUS:
            staff["real_person"] = True
    user_team = str((save.get("meta") or {}).get("user_team_id") or "")
    employed = sorted(save.get("staff_slots", []), key=lambda staff: (
        str(staff.get("team_id") or "") != user_team, _stable_int(f"face_order:{staff.get('id') or staff.get('name')}")))
    ensure_staff_faces([*employed, *save.get("former_staff", []), *(save.get("staff_market_pool") or [])])


# ------------------------------------------------------------------------------------------------ prospects
@lru_cache(maxsize=1)
def _real_prospect_photos() -> dict[str, dict[str, Any]]:
    rows = real_manifest().get("prospects") or {}
    by_key: dict[str, dict[str, Any]] = {}
    for real_id, entry in rows.items():
        by_key[real_id] = entry
        by_key.setdefault(f"name:{normalize_name(entry.get('name'))}", entry)
    return by_key


def real_prospect_photo(real_id: str | None = None, name: str | None = None) -> str | None:
    photos = _real_prospect_photos()
    entry = photos.get(str(real_id)) if real_id else None
    if entry is None and name:
        entry = photos.get(f"name:{normalize_name(name)}")
    return entry.get("file") if entry and entry.get("status") == "real_photo" else None


def prospect_face_id(key: str, used: set[str] | None = None) -> str | None:
    """A made-up prospect's face: a generated player face while one is free in his class, else a stock photo."""
    return pick_face(PROSPECT_GROUPS, key, used)


def prospect_headshot_url(prospect: dict[str, Any], used: set[str] | None = None, real_id: str | None = None) -> str | None:
    """A prospect's picture: his stored one (moved to the stage for his age), else his real photo (real prospects
    only), else a library face."""
    age = prospect.get("age")
    if is_current_url(prospect.get("headshot_url")):
        return stage_url(prospect["headshot_url"], age)
    photo = real_prospect_photo(real_id, prospect.get("name")) if prospect.get("league") != "generated" else None
    return photo or face_url(prospect_face_id(str(prospect.get("id") or prospect.get("name")), used), age=age)


def _face_id_of(url: str | None) -> str | None:
    return face_id_from_url(url)


def assign_class_faces(prospects: list[Any], real_ids: dict[str, str] | None = None) -> list[Any]:
    """Headshots for one draft class (DraftProspect records or dicts), in class order: real photos where found,
    otherwise generated faces, then stock photos, with no face repeated inside the class."""
    from dataclasses import is_dataclass, replace

    real_ids = real_ids or {}
    rows = [dict(prospect.__dict__) if is_dataclass(prospect) else prospect for prospect in prospects]
    used = {face for face in (_face_id_of(row.get("headshot_url")) for row in rows) if face}
    out = []
    for prospect, row in zip(prospects, rows):
        if is_current_url(row.get("headshot_url")):
            out.append(prospect)
            continue
        row = {**row, "headshot_url": None}
        url = prospect_headshot_url(row, used, real_ids.get(row.get("id")))
        face_id = _face_id_of(url)
        if face_id:
            used.add(face_id)
        out.append(replace(prospect, headshot_url=url) if is_dataclass(prospect) else {**prospect, "headshot_url": url})
    return out


# ------------------------------------------------------------------------------------------------ players
def stage_player_headshots(players: Iterable[dict[str, Any]]) -> None:
    """Made-up players drafted with a library face show the stage for their current age (rookie, prime, veteran,
    late career). Real NBA players and real prospects keep their own photos. Display only: no game value reads it."""
    for player in players:
        url = player.get("headshot_url")
        if url and str(url).startswith(URL_ROOT):
            player["headshot_url"] = stage_url(url, player.get("age"))
