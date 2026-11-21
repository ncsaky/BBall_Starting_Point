#!/usr/bin/env python3
"""Build the game's stock face library: openly licensed photos of real people for made-up staff and prospects.

Every face shown in the game is a photo of a real human. Real people (head coaches, real prospects) use their own
photo (scripts/fetch_real_headshots.py). Made-up staff and made-up prospects get a photo from this library.

Sources (no account needed, polite: one request at a time with a delay, every response cached on disk):
- Openverse API (api.openverse.org), anonymous use within its published limits (20 requests a minute, 200 a day),
  licences CC0, public domain mark, CC BY and CC BY-SA only. The images themselves come from where Openverse found
  them (mostly Flickr's static image servers and Wikimedia Commons).
- Wikimedia Commons API: stock-photo imports (Unsplash, Pixabay, Pexels files released under CC0 or similar).

Steps (each one resumable; everything intermediate lives in output/headshots-v2/):
  search     run the query list against Openverse and Commons, store candidates (licence, author, tags)
  download   fetch each candidate photo once (about 1024 px)
  process    cut the person out, greyscale, ESPN-style head-and-shoulders framing (scripts/stock_headshot.swift);
             reject photos with no face, several faces, a turned or tilted head, low resolution or a bad frame
  sheet      numbered contact sheets of the accepted faces for the human review (gender, age band, rejects)
  publish    copy the reviewed faces into gui/assets/headshots/stock/ with manifest.json and credits.json

Usage:
  python3 scripts/build_stock_faces.py search|download|process|sheet|publish [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "output" / "headshots-v2"
CACHE = WORK / "cache"
PHOTOS = WORK / "photos"
CUTS = WORK / "cuts"
CANDIDATES = WORK / "candidates.json"  # merged; each search writes its own file (they can run side by side)
OV_CANDIDATES = WORK / "candidates-openverse.json"
WC_CANDIDATES = WORK / "candidates-commons.json"
PROCESSED = WORK / "processed.json"
REVIEW = ROOT / "data" / "overrides" / "stock_face_review.json"
OUT = ROOT / "src" / "nba_gm_data" / "gui" / "assets" / "headshots" / "stock"
TOOL = WORK / "bin" / "stock_headshot"
SHEET_TOOL = WORK / "bin" / "contact_sheet"
UA = "NBA-GM-Sandbox-headshots/2.0 (private non-commercial hobby game; low request rate)"
TODAY = date.today().isoformat()
_last: dict[str, float] = {}

LICENCES = {  # Openverse licence code -> (display name prefix, allowed)
    "cc0": "CC0", "pdm": "Public Domain Mark", "by": "CC BY", "by-sa": "CC BY-SA",
}
# Words in a title or tags that point to a public figure, a minor, a group or a non-photo: skipped outright.
SKIP_WORDS = re.compile(
    r"\b(senator|congress\w*|mayor|minister|president|governor|ambassador|politician|candidate|campaign|"
    r"parliament|official portrait|actor|actress|singer|rapper|musician|celebrity|band|concert|premiere|"
    r"red carpet|king|queen|prince|princess|pope|bishop|general|admiral|"
    r"child|children|kid|kids|boy|girl|baby|teen|teenager|toddler|school ?boy|school ?girl|student council|"
    r"group|team photo|couple|wedding|bride|family|crowd|friends|"
    r"painting|drawing|sketch|illustration|statue|sculpture|mannequin|doll|cosplay|costume|halloween|"
    r"nude|naked|lingerie|bikini|swimsuit|sexy|glamour|boudoir|fashion model|"
    r"selfie|mugshot|wanted|deceased|funeral|memorial|grave)\b",
    re.I,
)

# Openverse queries: (query, pages of 10). Openverse times out on pages of 20 at the moment, so pages of 10; about
# 170 requests in all, under the anonymous 200-a-day limit.
OPENVERSE_QUERIES = [
    ("professional headshot", 14), ("corporate headshot", 12), ("headshot", 14), ("businessman portrait", 10),
    ("man headshot", 10), ("older man portrait", 10), ("african american man portrait", 10),
    ("asian man portrait", 6), ("hispanic man portrait", 6), ("businesswoman portrait", 10), ("woman headshot", 12),
    ("black woman portrait", 6), ("basketball player portrait", 12), ("young man portrait", 12),
    ("young black man portrait", 10), ("athlete portrait", 8), ("college student portrait", 6),
]
# Wikimedia Commons: stock-photo imports (Unsplash and Pexels files, mostly CC0). (search, most results)
COMMONS_QUERIES = [
    ('incategory:"Images_from_Unsplash" portrait', 600), ('incategory:"Images_from_Unsplash" man', 1100),
    ('incategory:"Images_from_Unsplash" woman', 900), ('incategory:"Images_from_Unsplash" face', 400),
    ('incategory:"Images_from_Unsplash_(review_needed)" portrait', 400), ('incategory:"Files_from_Pexels"', 500),
    ("portrait man unsplash filetype:bitmap", 100), ("portrait woman unsplash filetype:bitmap", 100),
    ("portrait pixabay filetype:bitmap", 50), ("man pixabay filetype:bitmap", 50), ("woman pixabay filetype:bitmap", 50),
    # Professional headshots uploaded to Commons (mostly by the people themselves); only those no article uses.
    ("intitle:headshot filetype:bitmap", 3000), ("professional headshot filetype:bitmap", 1500),
    ('incategory:"Portrait_photographs_of_women" -painting', 1500),
]
NAMED_PEOPLE_QUERIES = {query for query, _ in COMMONS_QUERIES[-3:]}


# --------------------------------------------------------------------------------------------- fetching
def fetch(url: str, *, delay: float = 1.0, host_key: str | None = None, headers_out: dict | None = None) -> bytes | None:
    """GET with an on-disk cache and a polite delay per host. Throttled answers are retried, never cached."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if key.exists():
        return key.read_bytes() or None
    host = host_key or urllib.parse.urlparse(url).netloc
    for attempt in range(3):
        wait = delay - (time.monotonic() - _last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.monotonic()
        request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
                if headers_out is not None:
                    headers_out.update({k.lower(): v for k, v in response.headers.items()})
            key.write_bytes(data)
            return data or None
        except urllib.error.HTTPError as error:
            if headers_out is not None:
                headers_out.update({k.lower(): v for k, v in (error.headers or {}).items()})
            if error.code in (429, 500, 502, 503, 504):
                pause = float(error.headers.get("Retry-After") or 0) or 20.0 * (attempt + 1)
                print(f"  {error.code} {url}: waiting {pause:.0f}s", file=sys.stderr)
                if pause > 120:
                    return None
                time.sleep(pause)
                continue
            print(f"  miss {error.code} {url}", file=sys.stderr)
            key.write_bytes(b"")
            return None
        except Exception as error:  # noqa: BLE001 - network hiccup: not cached
            print(f"  miss {url}: {error}", file=sys.stderr)
            return None
    return None


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def skip_reason(title: str, tags: list[str]) -> str | None:
    text = " ".join([title, *tags])
    match = SKIP_WORDS.search(text)
    return f"word: {match.group(0).lower()}" if match else None


# --------------------------------------------------------------------------------------------- search
OPENVERSE_BUDGET = 185  # live requests in one run: under the anonymous 200 a day
_openverse_live = [0]
_lock = threading.Lock()


def search_openverse(candidates: dict) -> None:
    """Three queries at a time (Openverse answers slowly, about 15 s a page): about 10 requests a minute in all,
    under the anonymous 20 a minute; each worker waits out any Retry-After the server sends."""
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda item: search_openverse_query(candidates, *item[1], worker=item[0] % 3),
                      enumerate(OPENVERSE_QUERIES)))


def search_openverse_query(candidates: dict, query: str, pages: int, worker: int) -> None:
    base = "https://api.openverse.org/v1/images/"
    for page in range(1, pages + 1):
        params = {"q": query, "license": "cc0,pdm,by,by-sa", "page_size": 10, "page": page}
        url = base + "?" + urllib.parse.urlencode(params)
        cached = (CACHE / hashlib.sha1(url.encode()).hexdigest()).exists()
        with _lock:
            if not cached and _openverse_live[0] >= OPENVERSE_BUDGET:
                print("Openverse request budget for this run used: stopping", file=sys.stderr, flush=True)
                return
            _openverse_live[0] += 0 if cached else 1
        headers: dict = {}
        data = fetch(url, delay=3.5, host_key=f"openverse-{worker}", headers_out=headers)
        left = headers.get("x-ratelimit-available-anon_sustained")
        if left is not None and int(left) < 8:
            print("Openverse daily allowance nearly used: stopping", file=sys.stderr)
            return
        with _lock:
            try:
                body = json.loads(data) if data else {}
            except ValueError:
                body = {}
            results = body.get("results") or []
            for row in results:
                cid = f"ov:{row['id']}"
                if cid in candidates:
                    candidates[cid]["queries"] = sorted({*candidates[cid]["queries"], query})
                    continue
                tags = [t.get("name", "") for t in row.get("tags") or []]
                machine = {t["name"]: t.get("accuracy") for t in row.get("tags") or [] if t.get("accuracy")}
                candidates[cid] = {
                    "id": cid, "source": "openverse", "provider": row.get("provider"), "title": row.get("title") or "",
                    "image_url": row.get("url"), "landing_url": row.get("foreign_landing_url"),
                    "author": row.get("creator") or "Unknown", "author_url": row.get("creator_url"),
                    "licence_code": row.get("license"), "licence_version": row.get("license_version"),
                    "licence_url": row.get("license_url"), "tags": tags, "machine_tags": machine,
                    "queries": [query], "width": row.get("width"), "height": row.get("height"),
                    "skip": skip_reason(row.get("title") or "", tags),
                }
            print(f"openverse {query!r} p{page}: {len(results)} (allowance left {left}); {len(candidates)} candidates", flush=True)
            save_json(OV_CANDIDATES, candidates)
        if data and page >= int(body.get("page_count") or 0):
            break


COMMONS_OK = re.compile(r"^(cc0|public domain|pd|cc[- ]by(-sa)?[- ][0-9.]+|cc by(-sa)? [0-9.]+)", re.I)


def search_commons(candidates: dict) -> None:
    api = "https://commons.wikimedia.org/w/api.php"
    for query, most in COMMONS_QUERIES:
        offset = 0
        while offset < most:
            params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                      "gsrsearch": query, "gsrlimit": 50, "gsroffset": offset, "prop": "imageinfo",
                      "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1024}
            if query in NAMED_PEOPLE_QUERIES:
                # Headshots uploaded under a person's name: keep only photos that no Wikipedia article uses
                # (an article means a notable, possibly famous, person).
                params.update(prop="imageinfo|globalusage", gunamespace=0, gulimit="max")
            data = fetch(api + "?" + urllib.parse.urlencode(params), delay=2.5)
            body = json.loads(data) if data else {}
            pages = (body.get("query") or {}).get("pages") or {}
            for page in pages.values():
                info = (page.get("imageinfo") or [{}])[0]
                meta = info.get("extmetadata") or {}
                licence = (meta.get("LicenseShortName") or {}).get("value", "")
                cid = f"wc:{page.get('pageid')}"
                if cid in candidates or "jpeg" not in str(info.get("mime")):
                    continue
                author = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
                title = page.get("title", "").removeprefix("File:").rsplit(".", 1)[0]
                cats = re.sub(r"<[^>]+>", "", (meta.get("Categories") or {}).get("value", ""))
                candidates[cid] = {
                    "id": cid, "source": "commons", "provider": "wikimedia", "title": title,
                    "image_url": info.get("thumburl") or info.get("url"), "landing_url": info.get("descriptionurl"),
                    "author": author or "Unknown", "author_url": None, "licence_name": licence,
                    "licence_url": (meta.get("LicenseUrl") or {}).get("value"), "tags": cats.split("|"),
                    "machine_tags": {}, "queries": [query], "width": info.get("width"), "height": info.get("height"),
                    "skip": None if COMMONS_OK.match(licence) else f"licence: {licence}",
                }
                if not candidates[cid]["skip"]:
                    candidates[cid]["skip"] = skip_reason(title, [])
                if not candidates[cid]["skip"] and page.get("globalusage"):
                    candidates[cid]["skip"] = "used on a Wikipedia article (notable person)"
            print(f"commons {query!r} +{offset}: {len(pages)}; {len(candidates)} candidates", flush=True)
            save_json(WC_CANDIDATES, candidates)
            if "continue" not in body:
                break
            offset += 50


def licence_name(row: dict) -> str:
    if row.get("licence_name"):
        return row["licence_name"]
    code, version = row.get("licence_code"), row.get("licence_version")
    name = LICENCES.get(code, str(code).upper())
    return f"{name} {version}" if version and code not in ("cc0", "pdm") else ("CC0 1.0" if code == "cc0" else name)


# --------------------------------------------------------------------------------------------- download / process
def photo_path(row: dict) -> Path:
    return PHOTOS / (hashlib.sha1(row["id"].encode()).hexdigest()[:16] + ".jpg")


PERSON_WORDS = re.compile(
    r"\b(portrait|face|headshot|head shot|smil\w*|beard\w*|glasses|man|woman|men|women|guy|lady|gentleman|"
    r"businessman|businesswoman|person|people|eyes|looking|close-?up|model|male|female|athlete|hair\w*|young|"
    r"old|elderly|senior|student|professional|suit)\b", re.I)


def likely_person(row: dict) -> bool:
    """Stock-photo imports (Unsplash, Pexels, Pixabay) are mostly landscapes and objects: only titles that name a
    person are worth downloading. Openverse results and named headshot uploads are all of people."""
    if row.get("source") != "commons" or set(row.get("queries") or []) & NAMED_PEOPLE_QUERIES:
        return True
    return bool(PERSON_WORDS.search(row.get("title") or ""))


def download(candidates: dict, limit: int | None) -> None:
    todo = [row for row in candidates.values() if not row.get("skip") and row.get("image_url")
            and not photo_path(row).exists() and not row.get("download_failed") and likely_person(row)]
    # Wikimedia throttles full-size originals hard (upload.wikimedia.org); its standard thumbnails come first.
    todo.sort(key=lambda row: "upload.wikimedia.org" in str(row["image_url"]))
    todo = todo[:limit] if limit else todo
    print(f"{len(todo)} photos to download", flush=True)
    # One worker per image host, each one request at a time with a pause (hosts are independent).
    by_host: dict[str, list[dict]] = {}
    for row in todo:
        by_host.setdefault(urllib.parse.urlparse(row["image_url"]).netloc, []).append(row)
    done = [0]

    def run(rows: list[dict]) -> None:
        for row in rows:
            data = fetch(row["image_url"], delay=1.0)
            with _lock:
                done[0] += 1
                if not data or len(data) < 8000:
                    row["download_failed"] = True
                else:
                    photo_path(row).parent.mkdir(parents=True, exist_ok=True)
                    photo_path(row).write_bytes(data)
                if done[0] % 50 == 0:
                    print(f"  {done[0]}/{len(todo)}", flush=True)
                    save_json(CANDIDATES, candidates)

    with ThreadPoolExecutor(max_workers=max(1, len(by_host))) as pool:
        list(pool.map(run, by_host.values()))
    save_json(CANDIDATES, candidates)


def ensure_tools() -> None:
    for tool, source in ((TOOL, "stock_headshot.swift"), (SHEET_TOOL, "contact_sheet.swift")):
        if not tool.exists() or tool.stat().st_mtime < (ROOT / "scripts" / source).stat().st_mtime:
            tool.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["swiftc", "-O", str(ROOT / "scripts" / source), "-o", str(tool)], check=True)


def judge(m: dict) -> str | None:
    """Why a processed photo is unsuitable, or None when it can be a headshot."""
    if m.get("error"):
        return m["error"]
    if not m.get("faces"):
        return "no face"
    if m["second_face_ratio"] > 0.12:
        return "more than one face"
    if m["face_px"] < 110:
        return "face too small in the photo"
    if abs(m["yaw"]) > 25 or abs(m["roll"]) > 16:
        return "head turned or tilted"
    if m["quality"] < 0.35:
        return "poor face capture"
    if m["outside"] > 0.12:
        return "too tightly cropped for head and shoulders"
    if m["body_bottom"] < 0.35 or m["cover"] < 0.22:
        return "shoulders cut or cut-out failed"
    if m["cover"] > 0.80:
        return "cut-out failed (background kept)"
    return None


def process(candidates: dict) -> None:
    ensure_tools()
    processed = load_json(PROCESSED, {})
    todo = [row for row in candidates.values() if photo_path(row).exists() and row["id"] not in processed]
    CUTS.mkdir(parents=True, exist_ok=True)

    def run(row: dict):
        target = CUTS / (photo_path(row).stem + ".png")
        result = subprocess.run([str(TOOL), str(photo_path(row)), str(target), "520"], capture_output=True, text=True)
        try:
            m = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            m = {"error": "tool failed"}
        return row["id"], m

    with ThreadPoolExecutor(max_workers=6) as pool:
        for count, (cid, m) in enumerate(pool.map(run, todo), 1):
            m["reject"] = judge(m)
            processed[cid] = m
            if count % 100 == 0:
                print(f"  processed {count}/{len(todo)}")
                save_json(PROCESSED, processed)
    save_json(PROCESSED, processed)
    accepted = sum(1 for m in processed.values() if not m.get("reject"))
    print(f"processed {len(processed)}; accepted {accepted}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=["search", "search-openverse", "search-commons", "download", "process", "sheet",
                                         "review", "publish"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sheet", type=int, help="review: the sheet number")
    parser.add_argument("--codes", help="review: one code letter per face on the sheet")
    args = parser.parse_args()
    if args.step == "review":
        record_review(args.sheet, args.codes)
        return
    if args.step in ("search", "search-commons"):
        search_commons(load_json(WC_CANDIDATES, {}))
    if args.step in ("search", "search-openverse"):
        search_openverse(load_json(OV_CANDIDATES, {}))
    candidates = load_json(CANDIDATES, {})
    for part in (load_json(WC_CANDIDATES, {}), load_json(OV_CANDIDATES, {})):
        for cid, row in part.items():
            candidates.setdefault(cid, row)
    save_json(CANDIDATES, candidates)
    if args.step == "download":
        download(candidates, args.limit)
    if args.step == "process":
        process(candidates)
    if args.step == "sheet":
        make_sheets(candidates)
    if args.step == "publish":
        publish(candidates)


# --------------------------------------------------------------------------------------------- review and publish
# The human review (data/overrides/stock_face_review.json) gives every machine-accepted photo one code, read off
# numbered contact sheets: m = man (staff), o = older man (staff, 55 or older), f = woman (staff),
# g = older woman (staff, 55 or older), p = young man (generated prospects), x = reject (minor, famous or
# identifiable public figure, watermark, second person, bad cut-out, costume or glamour shot, unclear gender).
SHEETS = WORK / "sheets"
SHEET_SIZE = 48
CODES = {"m": ("staff-m", False), "o": ("staff-m", True), "f": ("staff-f", False), "g": ("staff-f", True),
         "p": ("prospect-m", False)}
GROUPS = {"staff-m": "male", "staff-f": "female", "prospect-m": "male"}
USE = {"staff-m": "Made-up staff (man)", "staff-f": "Made-up staff (woman)", "prospect-m": "Made-up prospect"}


def cut_path(cid: str) -> Path:
    return CUTS / (hashlib.sha1(cid.encode()).hexdigest()[:16] + ".png")


def accepted_ids() -> list[str]:
    processed = load_json(PROCESSED, {})
    return sorted(cid for cid, m in processed.items() if not m.get("reject") and cut_path(cid).exists())


def make_sheets(candidates: dict) -> None:
    """Numbered contact sheets (48 faces each) of machine-accepted photos not yet reviewed."""
    ensure_tools()
    review = load_json(REVIEW, {}).get("codes", {})
    # Grouped by photographer, so several photos of one person sit together on a sheet (one is kept).
    todo = sorted((cid for cid in accepted_ids() if cid not in review),
                  key=lambda cid: (str(candidates.get(cid, {}).get("author")).lower(), candidates.get(cid, {}).get("title", "")))
    SHEETS.mkdir(parents=True, exist_ok=True)
    index = load_json(SHEETS / "index.json", {})
    start = max([int(k) for k in index] + [0]) + 1
    for offset in range(0, len(todo), SHEET_SIZE):
        number = start + offset // SHEET_SIZE
        ids = todo[offset:offset + SHEET_SIZE]
        index[str(number)] = ids
        listing = SHEETS / f"sheet-{number:03d}.txt"
        listing.write_text("".join(f"{cut_path(cid)}\t{i + 1}\n" for i, cid in enumerate(ids)))
        subprocess.run([str(SHEET_TOOL), str(SHEETS / f"sheet-{number:03d}.jpg"), "8", "156", "114", str(listing)],
                       check=True, capture_output=True)
    save_json(SHEETS / "index.json", index)
    print(f"{len(todo)} faces on sheets {start}..{start + max(0, len(todo) - 1) // SHEET_SIZE}")


def record_review(sheet: int, codes: str) -> None:
    """Store the codes read off one sheet (one letter per face, in sheet order; spaces ignored)."""
    ids = load_json(SHEETS / "index.json", {})[str(sheet)]
    letters = [c for c in codes if not c.isspace()]
    if len(letters) != len(ids):
        raise SystemExit(f"sheet {sheet}: {len(ids)} faces but {len(letters)} codes")
    review = load_json(REVIEW, {"codes": {}})
    review["about"] = ("Human review of stock face photos (scripts/build_stock_faces.py). Codes: m man, o older man, "
                       "f woman, g older woman, p young man (prospects), x rejected.")
    for cid, letter in zip(ids, letters):
        if letter not in CODES and letter != "x":
            raise SystemExit(f"unknown code {letter!r}")
        review["codes"][cid] = letter
    save_json(REVIEW, review)


def publish(candidates: dict) -> None:
    """Copy the reviewed faces into the game (260 px AVIF with transparency), with manifest.json and credits.json."""
    review = load_json(REVIEW, {}).get("codes", {})
    chosen: dict[str, list[tuple[str, bool]]] = {group: [] for group in GROUPS}
    for cid in sorted(review, key=lambda c: hashlib.sha1(c.encode()).hexdigest()):
        if review[cid] in CODES and cut_path(cid).exists():
            group, senior = CODES[review[cid]]
            chosen[group].append((cid, senior))
    if OUT.exists():
        for old in OUT.rglob("*.avif"):
            old.unlink()
    manifest = {"library": "stock", "ext": "avif", "built_by": "scripts/build_stock_faces.py", "built": TODAY,
                "about": "Openly licensed photos of real, non-famous adults (CC0, public domain, CC BY, CC BY-SA), "
                         "cut out and greyscale, credited one by one in credits.json.", "groups": {}}
    photos = []
    for group, rows in chosen.items():
        (OUT / group).mkdir(parents=True, exist_ok=True)
        seniors = []
        for number, (cid, senior) in enumerate(rows, 1):
            face_id = f"{group}/{number:04d}"
            target = OUT / f"{face_id}.avif"
            subprocess.run(["sips", "-s", "format", "avif", "-s", "formatOptions", "55", "--resampleWidth", "260",
                            str(cut_path(cid)), "--out", str(target)], check=True, capture_output=True)
            if senior:
                seniors.append(number)
            row = candidates[cid]
            photos.append({
                "face_id": face_id, "file": f"/assets/headshots/stock/{face_id}.avif", "use": USE[group],
                "title": row.get("title") or "Untitled", "author": row.get("author") or "Unknown",
                "author_url": row.get("author_url"), "licence": licence_name(row), "licence_url": row.get("licence_url"),
                "source_url": row.get("landing_url"), "image_url": row.get("image_url"),
                "provider": row.get("provider"), "found_via": row.get("source"), "candidate": cid,
            })
        manifest["groups"][group] = {"gender": GROUPS[group], "count": len(rows), "senior": seniors}
    save_json(OUT / "manifest.json", manifest)
    save_json(OUT / "credits.json", {
        "about": "Every stock photo in the game's face library: title, author, licence and source. CC BY and CC BY-SA "
                 "photos are used under their licence terms (credited here and in the game's Photo credits view; "
                 "changes made: cut out from the background, cropped, resized, greyscale).",
        "photos": photos,
    })
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print({group: len(rows) for group, rows in chosen.items()}, f"{size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
