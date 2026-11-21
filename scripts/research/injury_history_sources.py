"""Cached historical sources for the public injury-history builder."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
import time
from urllib.error import HTTPError, URLError

from opening_night_injuries import BASE, CACHE, PDF_CACHE, ROOT, SCOREBOARD, fetch, fetch_bytes


@dataclass(frozen=True)
class Season:
    year: int
    opener: str
    end: str
    cup_final: str
    play_in_days: tuple[str, ...]
    playoff_games: int

    @property
    def label(self) -> str:
        return f"{self.year - 1}-{self.year % 100:02}"

    @property
    def historical(self) -> bool:
        return self.year < 2026

    @property
    def cache(self) -> Path:
        return ROOT / "output/injury-history-2023-25" / self.label

    @property
    def espn_cache(self) -> Path:
        return self.cache / "espn" if self.historical else CACHE

    @property
    def pdf_cache(self) -> Path:
        return self.cache / "nba_pdf" if self.historical else PDF_CACHE

    @property
    def extra_days(self) -> tuple[str, ...]:
        if not self.historical:
            return self.play_in_days
        cup_day = {2024: "2023-12-09", 2025: "2024-12-17"}[self.year]
        return (cup_day, *self.play_in_days)


SEASONS = {
    s.label: s for s in (
        Season(2024, "2023-10-24", "2024-06-17", "401607495",
               ("2024-04-16", "2024-04-17", "2024-04-19"), 82),
        Season(2025, "2024-10-22", "2025-06-22", "401734908",
               ("2025-04-15", "2025-04-16", "2025-04-18"), 84),
        Season(2026, "2025-10-21", "2026-06-13", "401809839",
               ("2026-04-14", "2026-04-15", "2026-04-17"), 85),
    )
}

_espn_lock = Lock()
_espn_next_request = 0.0


def cached_request(loader, url, path, throttle=False):
    """Space requests on the ESPN host and retry transient failures only."""
    global _espn_next_request
    for attempt in range(3):
        if throttle and not path.exists() and not path.with_suffix(path.suffix + ".missing").exists():
            with _espn_lock:
                time.sleep(max(0, _espn_next_request - time.monotonic()))
                _espn_next_request = time.monotonic() + 0.35
        try:
            return loader(url, path)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            retry_after = error.headers.get("Retry-After", "")
            delay = int(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1)
        except (TimeoutError, URLError):
            if attempt == 2:
                raise
            delay = 2 ** (attempt + 1)
        if throttle:
            with _espn_lock:
                _espn_next_request = max(_espn_next_request, time.monotonic() + delay)
        time.sleep(delay)


def espn_events(season, get):
    """Enumerate regular and playoff schedules, with Cup and play-in scoreboards."""
    events = {}
    for team in range(1, 31):
        for stage, phase in ((2, "regular"), (3, "playoffs")):
            schedule = get(f"/teams/{team}/schedule?season={season.year}&seasontype={stage}",
                           f"ih_schedule_{team}_{stage}.json")
            for event in schedule["events"]:
                gid = str(event["id"])
                events[gid] = event, "cup_final" if gid == season.cup_final else phase
    for day in season.extra_days:
        scoreboard = get("/scoreboard?dates=" + day.replace("-", ""), f"ih_sb_{day}.json")
        for event in scoreboard["events"]:
            gid = str(event["id"])
            if gid == season.cup_final:
                events[gid] = event, "cup_final"
            elif event["season"]["type"] == 5 and day in season.play_in_days:
                events[gid] = event, "play_in"
    return events


def is_final(event):
    competition = event["competitions"][0]
    return (competition.get("status") or event["status"])["type"]["name"] == "STATUS_FINAL"


def capture_summaries(season, gids):
    def capture(gid):
        return cached_request(fetch_bytes, BASE + f"/summary?event={gid}",
                              season.espn_cache / f"sum_{gid}.json", throttle=True)

    # Several requests can be in flight, but the starts are paced across them.
    with ThreadPoolExecutor(max_workers=4) as workers:
        for gid, payload in zip(gids, workers.map(capture, gids)):
            if not payload:
                print(f"ESPN summary unavailable for {gid}", flush=True)
