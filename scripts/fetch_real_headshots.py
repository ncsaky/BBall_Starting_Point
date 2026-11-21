#!/usr/bin/env python3
"""Download real public headshots for the game's real head coaches and real draft prospects, once.

Sources (fetched politely: one request at a time, a delay between requests, every response cached on disk):
- Head coaches: the lead photo of the coach's English Wikipedia article (Wikimedia Commons, freely licensed;
  the licence and author are recorded per photo).
- College prospects: the player's headshot on his ESPN men's college basketball team roster
  (a.espncdn.com/i/headshots/, allowed by ESPN's robots.txt). ESPN photos are not cleared for redistribution;
  the manifest marks them reference_only_not_cleared, like the NBA player headshots the game already shows.
- High-school and international prospects: no consistent public source; they fall back to the generated
  face library (faces.py), recorded in the manifest as a deliberate fallback.

Images are resized to 260 px wide and stored as AVIF (coach photos as JPEG) under
src/nba_gm_data/gui/assets/headshots/real/ with manifest.json (person, source URL, date).

Usage:
  python3 scripts/fetch_real_headshots.py [--coaches] [--prospects] [--delay 0.8]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "nba_gm_data" / "gui" / "assets" / "headshots" / "real"
CACHE = ROOT / "output" / "headshots" / "cache"
UNIVERSE = ROOT / "data" / "canonical" / "universe_2026_27_offseason.json"
PROSPECTS = ROOT / "data" / "canonical" / "real_prospects.json"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
WIKI_UA = "NBA-GM-Sandbox-headshots/1.0 (private non-commercial game; low request rate)"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
TODAY = date.today().isoformat()
DELAY = 0.8
_last_request = 0.0


def fetch(url: str, *, ua: str = BROWSER_UA, binary: bool = False) -> bytes | None:
    """GET with an on-disk cache and a polite delay between live requests."""
    global _last_request
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if key.exists():
        data = key.read_bytes()
        return data or None
    for attempt in range(3):
        wait = DELAY - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        request = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            key.write_bytes(data)
            return data or None
        except urllib.error.HTTPError as error:
            if error.code in (429, 500, 502, 503, 504):
                # Back off (the server's Retry-After when given) and try again; never cache a throttled miss.
                pause = float(error.headers.get("Retry-After") or 0) or 10.0 * (attempt + 1)
                print(f"  {error.code} {url}: waiting {pause:.0f}s", file=sys.stderr)
                time.sleep(min(pause, 60.0))
                continue
            print(f"  miss {url}: {error}", file=sys.stderr)
            key.write_bytes(b"")  # a real miss (404 etc.): remember it so reruns stay polite
            return None
        except Exception as error:  # noqa: BLE001 - network hiccup: not cached
            print(f"  miss {url}: {error}", file=sys.stderr)
            return None
    return None


def fetch_json(url: str, **kwargs) -> dict | None:
    data = fetch(url, **kwargs)
    if not data:
        return None
    try:
        return json.loads(data)
    except ValueError:
        return None


def norm(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[.'’`]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", text)


def slug(text: str) -> str:
    return norm(text).replace(" ", "-")


CROPPER = ROOT / "output" / "headshots" / "tooling" / "bin" / "crop_headshot"


def crop_face(source: Path, target: Path, width: int = 260) -> list[int] | None:
    """Head-and-shoulders crop around the largest face (scripts/crop_headshot.swift, compiled into CROPPER)."""
    if not CROPPER.exists():
        subprocess.run(["swiftc", "-O", str(ROOT / "scripts" / "crop_headshot.swift"), "-o", str(CROPPER)], check=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(CROPPER), str(source), str(target), str(width)], capture_output=True, text=True)
    try:
        info = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None
    return info.get("crop") if info.get("faces") and target.exists() else None


def convert(source: Path, target: Path, fmt: str, width: int = 260, quality: int = 60) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["sips", "-s", "format", fmt, "-s", "formatOptions", str(quality), "--resampleWidth", str(width),
         str(source), "--out", str(target)],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and target.exists() and target.stat().st_size > 0


def stage(data: bytes, suffix: str) -> Path:
    path = CACHE / "staged" / (hashlib.sha1(data).hexdigest() + suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# ----------------------------------------------------------------------------------------------- coaches
WIKI_TITLES = {
    # Articles whose plain name is ambiguous on Wikipedia.
    "Mike Brown": "Mike Brown (basketball, born 1970)",
    "Charles Lee": "Charles Lee (basketball)",
    "Will Hardy": "Will Hardy (basketball)",
    "Doug Christie": "Doug Christie (basketball)",
    "Mitch Johnson": "Mitch Johnson (basketball)",
    "Sean Sweeney": "Sean Sweeney (basketball)",
    "Jordi Fernandez": "Jordi Fernández (basketball)",
    "Darko Rajakovic": "Darko Rajaković",
    "J.B. Bickerstaff": "J. B. Bickerstaff",
    "Brian Keefe": "Brian Keefe (basketball)",
    "David Adelman": "David Adelman",
    "Taylor Jenkins": "Taylor Jenkins (basketball)",
    "Chris Finch": "Chris Finch (basketball)",
    "Nick Nurse": "Nick Nurse",
    "Jordan Ott": "Jordan Ott",
    "Micah Nori": "Micah Nori",
}


def commons_licence(file_title: str) -> dict:
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=extmetadata|url"
           "&titles=" + urllib.parse.quote(file_title))
    data = fetch_json(url, ua=WIKI_UA) or {}
    for page in (data.get("query", {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
        return {
            "licence": (meta.get("LicenseShortName") or {}).get("value"),
            "licence_url": (meta.get("LicenseUrl") or {}).get("value"),
            "author": artist or None,
            "file_page": info.get("descriptionurl"),
        }
    return {}


def is_basketball(summary: dict | None) -> bool:
    text = (str((summary or {}).get("description") or "") + " " + str((summary or {}).get("extract") or "")).lower()
    return bool(summary) and "basketball" in text


def coach_summary(name: str) -> dict | None:
    """The coach's Wikipedia summary: a known title first, else the top basketball search hit for his name."""
    title = WIKI_TITLES.get(name, name)
    summary = fetch_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_")), ua=WIKI_UA)
    if is_basketball(summary):
        return summary
    search = fetch_json("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=5&srsearch="
                        + urllib.parse.quote(f"{name} basketball coach"), ua=WIKI_UA) or {}
    wanted = norm(name).split()
    for hit in search.get("query", {}).get("search", []):
        hit_title = hit.get("title", "")
        if norm(hit_title.split("(")[0]).split()[-1:] != wanted[-1:]:
            continue
        summary = fetch_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(hit_title.replace(" ", "_")), ua=WIKI_UA)
        if is_basketball(summary):
            return summary
    return None


def fetch_coaches(manifest: dict) -> None:
    universe = json.loads(UNIVERSE.read_text())
    heads = sorted((s for s in universe["staff_profiles"] if s.get("role") == "head_coach" and s.get("name")),
                   key=lambda s: s["team_id"])
    out = manifest.setdefault("coaches", {})
    for staff in heads:
        name = staff["name"]
        entry = {"name": name, "team_id": staff["team_id"], "gender": "male", "fetched": TODAY}
        summary = coach_summary(name)
        thumb = (summary or {}).get("thumbnail") or {}
        if not summary or not thumb:
            entry.update(status="fallback_generated", reason="no basketball Wikipedia article with a lead photo")
            out[norm(name)] = entry
            print(f"coach {name}: fallback")
            continue
        original = (summary.get("originalimage") or {}).get("source", "").split("?")[0]
        file_title = "File:" + urllib.parse.unquote(original.rsplit("/", 1)[-1]) if original else ""
        licence = commons_licence(file_title) if "/commons/" in original else {}
        if not licence.get("licence"):
            # Only freely licensed Commons photos: a file kept on English Wikipedia alone may be non-free.
            entry.update(status="fallback_generated", reason="lead photo is not a freely licensed Commons file",
                         source_page=(summary.get("content_urls") or {}).get("desktop", {}).get("page"))
            out[norm(name)] = entry
            print(f"coach {name}: fallback (licence)")
            continue
        # A 960 px rendition (a standard Wikimedia thumbnail width), cropped around his face, saved 260 px wide.
        image_url = re.sub(r"/\d+px-", "/960px-", thumb["source"]).split("?")[0]
        data = fetch(image_url, ua=WIKI_UA, binary=True) or fetch(original, ua=WIKI_UA, binary=True)
        target = OUT / "coaches" / f"{slug(name)}.jpg"
        cropped = crop_face(stage(data, ".jpg"), target) if data else None
        if not cropped and original:
            # Small faces in wide shots: try the full-size original.
            full = fetch(original, ua=WIKI_UA, binary=True)
            cropped = crop_face(stage(full, ".jpg"), target) if full else None
            image_url = original if cropped else image_url
        if not cropped:
            entry.update(status="fallback_generated", reason="photo download failed or no face found in it")
        else:
            entry.update(
                status="real_photo",
                file=f"/assets/headshots/real/coaches/{target.name}",
                source="wikipedia_lead_image",
                source_page=(summary.get("content_urls") or {}).get("desktop", {}).get("page"),
                source_url=image_url,
                rights="free_licence_wikimedia_commons",
                crop=cropped,
                **licence,
            )
        out[norm(name)] = entry
        print(f"coach {name}: {entry['status']}")


# ----------------------------------------------------------------------------------------------- prospects
TEAM_ALIASES = {
    "connecticut": "uconn", "miami fl": "miami", "miami oh": "miami oh", "mississippi": "ole miss",
    "nc state": "nc state", "n c state": "nc state", "louisiana lafayette": "louisiana",
    "ut martin": "ut martin", "cal st bakersfield": "cal state bakersfield", "saint marys": "saint marys",
    "st johns": "st johns", "fiu": "florida international", "umass": "massachusetts", "uconn": "uconn",
    "southern miss": "southern miss", "texas a m": "texas a m", "texas am": "texas a m", "mcneese st": "mcneese",
    "sam houston st": "sam houston", "app state": "app state", "appalachian st": "app state",
    "illinois chicago": "uic", "loyola chicago": "loyola chicago", "unc wilmington": "unc wilmington",
    "nebraska omaha": "omaha", "detroit": "detroit mercy", "grambling st": "grambling",
    "liu brooklyn": "long island university", "seattle": "seattle u", "southeastern louisiana": "se louisiana",
    "tennessee martin": "ut martin", "texas a m corpus chris": "texas a m corpus christi",
    "louisiana monroe": "ul monroe", "arkansas pine bluff": "arkansas pine bluff",
    "cal baptist": "california baptist", "queens": "queens university",
}


def espn_team_index() -> dict[str, dict]:
    data = fetch_json(f"{ESPN}/teams?limit=500") or {}
    teams = [t["team"] for t in data["sports"][0]["leagues"][0]["teams"]]
    index: dict[str, dict] = {}
    for team in teams:
        for label in (team.get("location"), team.get("shortDisplayName"), team.get("nickname"), team.get("abbreviation")):
            key = norm(label)
            if key and key not in index:
                index[key] = team
    return index


def team_key(name: str) -> str:
    key = norm(name)
    key = TEAM_ALIASES.get(key, key)
    key = re.sub(r"\bst$", "state", key)
    return TEAM_ALIASES.get(key, key)


def match_athlete(name: str, athletes: list[dict]) -> dict | None:
    wanted = norm(name)
    exact = [a for a in athletes if norm(a.get("fullName") or a.get("displayName")) == wanted]
    if len(exact) == 1:
        return exact[0]
    parts = wanted.split()
    if len(parts) >= 2:
        last = parts[-1]
        same_last = [a for a in athletes if norm(a.get("lastName")) == last or norm(a.get("displayName")).split()[-1:] == [last]]
        initial = [a for a in same_last if norm(a.get("firstName") or a.get("displayName"))[:1] == parts[0][:1]]
        if len(initial) == 1:
            return initial[0]
    return None


def fetch_prospects(manifest: dict, limit: int | None = None) -> None:
    prospects = json.loads(PROSPECTS.read_text())["prospects"]
    out = manifest.setdefault("prospects", {})
    index = espn_team_index()
    rosters: dict[str, list[dict]] = {}
    unmatched_teams: set[str] = set()
    done = 0
    for entry in prospects:
        pid = entry["id"]
        record = {"name": entry["name"], "kind": entry["kind"], "gender": "male", "fetched": TODAY}
        team_name = entry.get("college_team") or (entry.get("scouting") or {}).get("team")
        if not str(entry.get("kind", "")).startswith("college") or not team_name:
            record.update(status="fallback_generated",
                          reason=f"no consistent public headshot source for {entry['kind'].replace('_', ' ')} prospects")
            out[pid] = record
            continue
        team = index.get(team_key(team_name))
        if not team:
            unmatched_teams.add(team_name)
            record.update(status="fallback_generated", reason=f"college team {team_name!r} not found on ESPN")
            out[pid] = record
            continue
        if team["id"] not in rosters:
            data = fetch_json(f"{ESPN}/teams/{team['id']}/roster") or {}
            rosters[team["id"]] = list(data.get("athletes") or [])
        athlete = match_athlete(entry["name"], rosters[team["id"]])
        href = ((athlete or {}).get("headshot") or {}).get("href")
        if not href:
            record.update(status="fallback_generated",
                          reason="not on his ESPN team roster" if not athlete else "ESPN has no headshot for him",
                          espn_team=team.get("displayName"))
            out[pid] = record
            continue
        target = OUT / "prospects" / f"{slug(pid)}.avif"
        data = fetch(href, binary=True)
        if not data or not convert(stage(data, ".png"), target, "avif", 260, 60):
            record.update(status="fallback_generated", reason="photo download or conversion failed")
        else:
            record.update(
                status="real_photo",
                file=f"/assets/headshots/real/prospects/{target.name}",
                source="espn_college_roster",
                source_page=f"https://www.espn.com/mens-college-basketball/player/_/id/{athlete['id']}",
                source_url=href,
                espn_id=athlete["id"],
                espn_team=team.get("displayName"),
                rights="reference_only_not_cleared",
            )
        out[pid] = record
        done += 1
        if limit and done >= limit:
            break
    if unmatched_teams:
        print("unmatched college teams:", sorted(unmatched_teams), file=sys.stderr)


def main() -> None:
    global DELAY
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--coaches", action="store_true")
    parser.add_argument("--prospects", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=DELAY)
    args = parser.parse_args()
    DELAY = args.delay
    path = OUT / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {}
    manifest["notes"] = (
        "Real headshots stored once for the game (260 px). Coach photos: Wikimedia Commons, licence per photo. "
        "Prospect photos: ESPN college rosters, reference only (rights not cleared), like the NBA player headshots "
        "the game already links. status fallback_generated = no usable real photo; the game shows a generated face."
    )
    if args.coaches:
        fetch_coaches(manifest)
    if args.prospects:
        fetch_prospects(manifest, args.limit)
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    for group in ("coaches", "prospects"):
        rows = manifest.get(group) or {}
        real = sum(1 for r in rows.values() if r.get("status") == "real_photo")
        print(f"{group}: {real} real photos of {len(rows)}")


if __name__ == "__main__":
    main()
