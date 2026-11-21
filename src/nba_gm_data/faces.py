"""Faces for people shown in the game.

Real people (the real head coaches, real draft prospects) use their real public photo when one was found
(gui/assets/headshots/real/, listed with sources in its manifest.json; scripts/fetch_real_headshots.py).
Made-up people get a face from the generated library (gui/assets/headshots/generated/<LIBRARY>/,
scripts/build_face_library.mjs): every face there belongs to one gender, and a made-up staff member's name is
drawn from the same gender's name list (staff_names.py), so name and face always agree.

A face is a library id such as "staff-f/0042". Within a league, faces are handed out so that no two staff members
share one while unused faces remain (several hundred per gender), and no two prospects in a draft class share one.
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

# The generated face library in use. Swap by building another style with scripts/build_face_library.mjs
# (same group sizes) and changing this name; new saves then use it.
LIBRARY = "open-peeps"
ASSETS = Path(__file__).resolve().parent / "gui" / "assets" / "headshots"
URL_ROOT = "/assets/headshots"

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
def library_manifest(library: str = LIBRARY) -> dict[str, Any]:
    path = ASSETS / "generated" / library / "manifest.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"groups": {}}


@lru_cache(maxsize=1)
def real_manifest() -> dict[str, Any]:
    try:
        return json.loads((ASSETS / "real" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def face_url(face_id: str | None, library: str = LIBRARY) -> str | None:
    return f"{URL_ROOT}/generated/{library}/{face_id}.svg" if face_id else None


def face_gender(face_id: str | None, library: str = LIBRARY) -> str | None:
    group = str(face_id or "").split("/")[0]
    return (library_manifest(library).get("groups", {}).get(group) or {}).get("gender")


def senior_band(age: Any) -> bool | None:
    """Grey-haired faces for older staff, younger-looking faces for younger staff, either in between."""
    try:
        age = float(age)
    except (TypeError, ValueError):
        return None
    return True if age >= SENIOR_AGE else False if age <= YOUNG_AGE else None


def pick_face(group: str, key: str, used: set[str] | None = None, *, senior: bool | None = None,
              library: str = LIBRARY) -> str | None:
    """The face for one person: a stable start from his or her key, then the next unused face of the group
    (matching the age band first). Reuses a face only once every face of the group is taken."""
    info = library_manifest(library).get("groups", {}).get(group)
    if not info or not info.get("count"):
        return None
    count = int(info["count"])
    seniors = set(info.get("senior") or [])
    used = used or set()
    start = _stable_int(f"{group}:{key}") % count
    for match_band in (True, False):
        for step in range(count):
            index = (start + step) % count + 1
            face_id = f"{group}/{index:04d}"
            if face_id in used or (match_band and senior is not None and (index in seniors) != senior):
                continue
            return face_id
    return f"{group}/{start + 1:04d}"


# ------------------------------------------------------------------------------------------------ staff
def staff_group(gender: str) -> str:
    return "staff-f" if gender == "female" else "staff-m"


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
    of the staff member's gender (and age band)."""
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
    group = staff_group(staff["gender"])
    if not staff.get("face_id") or face_gender(staff["face_id"]) != staff["gender"]:
        key = str(staff.get("market_source_id") or staff.get("id") or staff.get("name"))
        staff["face_id"] = pick_face(group, key, used, senior=senior_band(staff.get("age")))
    staff["headshot_url"] = face_url(staff["face_id"])
    staff["headshot_source"] = "generated"


def save_staff_people(save: dict[str, Any]) -> list[dict[str, Any]]:
    return [*save.get("staff_slots", []), *save.get("former_staff", []), *(save.get("staff_market_pool") or [])]


def ensure_staff_faces(people: Iterable[dict[str, Any]], held: Iterable[dict[str, Any]] = ()) -> None:
    """Faces for everyone listed who has none, avoiding faces already held (by `held` or earlier people).
    A newly faced made-up person whose name is already taken in the league gets a fresh name of the same gender."""
    people = list(people)
    held = list(held)
    used_faces = {p["face_id"] for p in [*held, *people] if p.get("face_id")}
    used_names = {normalize_name(p.get("name")) for p in [*held, *people] if p.get("headshot_url")}
    for person in people:
        if person.get("headshot_url") and (person.get("face_id") or person.get("headshot_source") == "real_photo"):
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
    """Every staff member stored in the save (employed, former, market pool) has a gender and a face."""
    people = save_staff_people(save)
    for staff in save.get("staff_slots", []):
        if staff.get("status") == REAL_COACH_STATUS:
            staff["real_person"] = True
    ensure_staff_faces(people)


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
    return pick_face("prospect-m", key, used)


def prospect_headshot_url(prospect: dict[str, Any], used: set[str] | None = None, real_id: str | None = None) -> str | None:
    """A prospect's picture: his stored one, else his real photo (real prospects only), else a generated face."""
    if prospect.get("headshot_url"):
        return prospect["headshot_url"]
    photo = real_prospect_photo(real_id, prospect.get("name")) if prospect.get("league") != "generated" else None
    return photo or face_url(prospect_face_id(str(prospect.get("id") or prospect.get("name")), used))


def _face_id_of(url: str | None) -> str | None:
    marker = f"{URL_ROOT}/generated/"
    if not url or not url.startswith(marker):
        return None
    return url[len(marker):].split("/", 1)[1].rsplit(".", 1)[0]


def assign_class_faces(prospects: list[Any], real_ids: dict[str, str] | None = None) -> list[Any]:
    """Headshots for one draft class (DraftProspect records or dicts), in class order: real photos where found,
    otherwise generated faces with no repeats inside the class."""
    from dataclasses import is_dataclass, replace

    real_ids = real_ids or {}
    rows = [dict(prospect.__dict__) if is_dataclass(prospect) else prospect for prospect in prospects]
    used = {face for face in (_face_id_of(row.get("headshot_url")) for row in rows) if face}
    out = []
    for prospect, row in zip(prospects, rows):
        if row.get("headshot_url"):
            out.append(prospect)
            continue
        url = prospect_headshot_url(row, used, real_ids.get(row.get("id")))
        face_id = _face_id_of(url)
        if face_id:
            used.add(face_id)
        out.append(replace(prospect, headshot_url=url) if is_dataclass(prospect) else {**prospect, "headshot_url": url})
    return out
