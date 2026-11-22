"""Rebuild the Stage 2 coach evidence from six cached NBA play-by-play archives.

See docs/agents/tasks/rotation-evidence.md for input URLs and reproduction.
DuckDB is used only to read the public archives, outside the game environment.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict, namedtuple
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from hashlib import file_digest
from itertools import groupby
import json
from pathlib import Path
import re
from statistics import mean, median, quantiles
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = "https://github.com/ramirobentes/nba_data/releases/download/pbp"
GUIDE = "https://cdn.nba.com/manage/2026/10/2026-27-NBA-Guide_v2.pdf"
BOXES = ROOT / "data/research/game_boxscores_2025_26.json"
SEASONS = (2024, 2025, 2026)
PHASES = ("regular", "playoffs")
ROLES = ("star", "starter", "sixth_man", "bench")
ALIAS = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA",
         "WSH": "WAS", "PHO": "PHX", "BRK": "BKN"}
PLAYER_ID = re.compile(r"^(\d+) ")
PERSONAL_FOUL = re.compile(r"\((\d) PF\)")
LINEUP_SPLIT = re.compile(r", (?=\d+ )")
EXPECTED = {2024: (1230, 82), 2025: (1230, 83), 2026: (1230, 85)}

Event = namedtuple(
    "Event", "period t kind subtype team offense home away desc player second third "
    "drawn lineup_home lineup_away ends start_poss shot_pts qualifiers",
)
Interval = namedtuple("Interval", "start end period home away margin")
Segment = namedtuple("Segment", "start end margin")


def period_end(period):
    return min(period, 4) * 720 + max(0, period - 4) * 300


def player_id(field):
    return int(field.split(" ", 1)[0]) if field and PLAYER_ID.match(field) else None


@lru_cache(maxsize=75000)
def lineup(field):
    return frozenset(player_id(person) for person in LINEUP_SPLIT.split(field or ""))


def summary(values):
    if not values:
        return {"n": 0}
    if len(values) == 1:
        quartiles = [values[0]] * 3
    else:
        quartiles = quantiles(values, n=4, method="inclusive")
    return dict(n=len(values), mean=round(mean(values), 4),
                **{k: round(v, 4) for k, v in zip(("p25", "median", "p75"), quartiles)})


class Evidence:
    def __init__(self):
        self.values = defaultdict(list)
        self.coaches = defaultdict(lambda: defaultdict(list))
        self.fits = defaultdict(list)
        self.examples = defaultdict(list)

    def add(self, game, metric, group, value):
        self.values[game.year, game.phase, metric, group].append(value)

    def team(self, game, team, metric, value):
        if game.phase == "regular":
            self.coaches[game.year, team][metric].append(value)

    def fit(self, game, metric, group, value):
        self.fits[metric].append((game.year, group, value))

    def describe(self):
        result = {str(year): {phase: {} for phase in PHASES} for year in SEASONS}
        for (year, phase, metric, group), values in sorted(self.values.items()):
            result[str(year)][phase].setdefault(metric, {})[group] = summary(values)
        for phase in PHASES:
            combined = defaultdict(list)
            for (year, row_phase, metric, group), values in self.values.items():
                if phase == row_phase:
                    combined[metric, group].extend(values)
            result.setdefault("pooled", {})[phase] = {}
            for (metric, group), values in sorted(combined.items()):
                result["pooled"][phase].setdefault(metric, {})[group] = summary(values)
        return result


@dataclass
class Game:
    year: int
    phase: str
    date: date
    id: str
    home: str
    away: str
    events: list[Event]
    intervals: list[Interval] | None = None

    @property
    def end(self):
        return period_end(self.events[-1].period)

    @property
    def teams(self):
        return self.home, self.away


def games(connection, archive):
    query = """
        SELECT season, season_type, game_date, game_id, team_home, team_away,
            period::int, secs_game, msg_type::int, act_type::int, team_abb,
            off_team_abb, hs::int, vs::int, description, player1_name,
            player2_name, player3_name, foul_drawn_person_id::int,
            lineup_home, lineup_away, possession::int, start_poss, shot_pts::int, qualifiers
        FROM read_parquet(?)
        ORDER BY game_date, game_id, number_event, event_num, "order"
    """
    cursor = connection.execute(query, [str(archive)])
    rows = iter(lambda: cursor.fetchmany(4096), [])
    stream = (row for batch in rows for row in batch)
    for header, group in groupby(stream, key=lambda row: row[:6]):
        yield Game(*header, [Event(*row[6:]) for row in group])


def reconstruct(game, audit):
    """Turn post-event lineup snapshots into preceding clock intervals."""
    first = game.events[0]
    last = game.events[-1]
    if first.kind != 12 or first.t != 0 or last.t != game.end or last.period < 4:
        audit["incomplete_game"] += 1
        return []
    intervals = []
    previous = first
    for event in game.events[1:]:
        if event.t < previous.t:
            audit["games_with_clock_reversal"] += 1
            return []
        if event.t > previous.t:
            home, away = lineup(previous.lineup_home), lineup(previous.lineup_away)
            if len(home) != 5 or len(away) != 5 or None in home | away or home & away:
                audit["games_with_invalid_floor"] += 1
                return []
            if event.t > period_end(previous.period):
                audit["missing_period_boundary"] += 1
                return []
            intervals.append(Interval(previous.t, event.t, previous.period,
                                      home, away, previous.home - previous.away))
        previous = event
    return intervals


def personal_fouls(game):
    """Use the feed's running personal count, excluding technicals."""
    for event in game.events:
        if event.kind != 6 or event.subtype in {11, 12, 13, 16, 17, 18, 25, 30, 32, 33}:
            continue
        pid = player_id(event.player)
        counts = PERSONAL_FOUL.findall(event.desc or "")
        if pid and counts:
            yield event, pid, int(counts[0])
        if event.subtype == 10 and len(counts) == 2:
            other = player_id(event.second)
            if other and pid != other:
                yield event, other, int(counts[1])


def points(game):
    """Scoring credit in event order, with official scorer corrections excluded."""
    for event in game.events:
        if event.kind in {1, 3} and event.shot_pts in {1, 2, 3} and event.team in game.teams:
            yield event, event.shot_pts


def spells_for_team(intervals, home):
    spells = defaultdict(list)
    quarter = defaultdict(Counter)
    players_by_state = defaultdict(set)
    for frame in intervals:
        players = frame.home if home else frame.away
        margin = frame.margin if home else -frame.margin
        duration = frame.end - frame.start
        for pid in players:
            past = spells[pid]
            if past and past[-1].end == frame.start:
                past[-1] = Segment(past[-1].start, frame.end, past[-1].margin)
            else:
                past.append(Segment(frame.start, frame.end, margin))
            quarter[pid][frame.period] += duration
        if frame.period == 4 and frame.end > 2580:
            state = "close_0_5" if abs(margin) <= 5 else "moderate_6_19" if abs(margin) < 20 else (
                "ahead_20_plus" if margin > 0 else "behind_20_plus")
            players_by_state[state].update(players)
    return spells, quarter, players_by_state


def normalize_name(name):
    name = unicodedata.normalize("NFKD", name.casefold())
    return "".join(ch for ch in name if ch.isascii() and ch.isalnum())


def box_reference():
    boxes = {}
    for game in json.loads(BOXES.read_text())["games"]:
        if len(game["teams"]) != 2 or game["status"] != "STATUS_FINAL":
            continue
        teams = {team["home_away"]: ALIAS.get(team["team_abbrev"], team["team_abbrev"])
                 for team in game["teams"]}
        boxes[game["date"], teams["home"], teams["away"]] = game
    return boxes


def audit_box(game, team_data, player_names, fouls, ref, audit):
    if game.year != 2026:
        return
    key = (game.date.isoformat(), *game.teams)
    box = ref.get(key)
    if box is None and game.phase == "playoffs":
        # Some playoff boxes are keyed by UTC date, one calendar day later.
        later = ref.get(((game.date + timedelta(days=1)).isoformat(), *game.teams))
        final = game.events[-1]
        if later and (later["home_score"], later["away_score"]) == (final.home, final.away):
            box = later
            audit["local_boxes_joined_using_utc_date"] += 1
    if box is None:
        audit["games_without_local_box"] += 1
        return
    audit["games_with_local_box"] += 1
    last = game.events[-1]
    audit["matching_final_scores"] += (last.home, last.away) == (box["home_score"], box["away_score"])
    if (last.home, last.away) != (box["home_score"], box["away_score"]):
        audit[f"score_disagreement_{game.id}"] += 1
    for starters, quarter, team in team_data:
        named = {normalize_name(player_names[pid]): pid for pid in quarter if pid in player_names}
        for player in box["players"]:
            if ALIAS.get(player["team_abbrev"], player["team_abbrev"]) != team or player["dnp"]:
                continue
            if player["minutes"] is None or player["minutes"] <= 0:
                continue
            audit["box_player_games_with_positive_minutes"] += 1
            pid = named.get(normalize_name(player["player_name"]))
            if pid is None:
                continue
            audit["matched_box_players"] += 1
            seconds = sum(quarter[pid].values())
            audit["box_minutes_within_60_seconds"] += abs(seconds - player["minutes"] * 60) <= 60.01
            audit["box_starter_agreement"] += (pid in starters) == player["starter"]
            audit["box_personal_foul_agreement"] += fouls[pid] == player["pf"]


@dataclass
class Prior:
    appearances: int = 0
    minutes: float = 0
    points: int = 0
    ft_attempts: int = 0
    ft_made: int = 0
    starts: int = 0

    def star(self):
        return (self.appearances >= 8 and self.minutes >= 30 * self.appearances
                and self.points >= 22 * self.appearances and self.starts * 2 >= self.appearances)


def roles_for_game(starters, players, prior):
    candidates = players.keys() - starters
    sixth = max((pid for pid in candidates if prior[pid].appearances >= 5),
                key=lambda pid: (prior[pid].minutes / prior[pid].appearances, -pid),
                default=None)
    return {pid: ("star" if prior[pid].star() else "starter") if pid in starters
            else "sixth_man" if pid == sixth else "bench" for pid in players}


def collect_player_rotations(evidence, game, team, role, spans, quarter, prior_game, prior):
    add = lambda metric, group, value: evidence.add(game, metric, group, value)
    for i, stint in enumerate(spans):
        duration = stint.end - stint.start
        add("stint_seconds", role, duration)
        if i:
            add("bench_rest_seconds", role, stint.start - spans[i - 1].end)
        # Exposure at elapsed stint time, restricted to Q1–Q3 play and outside quarter breaks.
        for cutoff in (240, 360, 480, 600):
            now = stint.start + cutoff
            quarter_end = period_end(int(now // 720 + 1))
            if duration >= cutoff and now < 2160 and quarter_end - now > 60:
                add("stint_exits_next_minute", f"{role}|at_{cutoff // 60}m", duration < cutoff + 60)

    if role not in {"star", "starter"}:
        return
    regulation_minutes = sum(quarter.get(q, 0) for q in range(1, 5)) / 60
    evidence.team(game, team, "starter_regulation_minutes", regulation_minutes)
    for q in range(1, 5):
        add("starter_seconds_by_quarter", f"{role}|Q{q}", quarter.get(q, 0))

    first = spans[0]
    sat = first.end < game.end
    add("opening_exit_in_Q1", role, sat and first.end < 720)
    if sat:
        add("opening_exit_elapsed_seconds", role, first.end)
        if first.end < 720:
            add("first_exit_Q1_clock_seconds", role, 720 - first.end)
        evidence.team(game, team, "first_sit_elapsed_seconds", first.end)
        if game.phase == "regular":
            evidence.fit(game, "opening_exit_elapsed_seconds", role, first.end)
        if len(spans) > 1:
            returned = spans[1].start
            add("first_return_elapsed_seconds", role, returned)
            add("first_rest_seconds", role, returned - first.end)
            if game.phase == "regular":
                evidence.fit(game, "first_rest_seconds", role, returned - first.end)
            if returned < 1440:
                period = int(returned // 720) + 1
                add("first_return_clock_seconds", f"{role}|Q{period}", period_end(period) - returned)
        add("first_exit_with_return", role, len(spans) > 1)

    if prior_game is not None:
        rest, previous_minutes = prior_game
        group = "second_night" if rest == 1 else "one_day_off" if rest == 2 else "two_or_more_days_off"
        workload = "prior_32plus" if previous_minutes >= 32 else "prior_under32"
        for metric, value in (("regulation_minutes", regulation_minutes), ("first_stint_seconds", first.end)):
            add(f"schedule_{metric}", f"{role}|{group}|{workload}", value)
        if prior.appearances >= 8:
            delta = regulation_minutes - prior.minutes / prior.appearances
            add("schedule_minutes_vs_own_prior_average", f"{role}|{group}|{workload}", delta)


def collect_team_rotations(evidence, game, team, starters, spans, quarter, players_by_state,
                           roles, top_eight):
    add = lambda metric, group, value: evidence.add(game, metric, group, value)
    eligible = [pid for pid in spans if sum(quarter[pid].values()) >= 300]
    # Exclude last-second special-purpose substitutions from the broad game depth count.
    used = [pid for pid in spans if sum(quarter[pid].values()) >= 60]
    add("depth_5_minute_players", "all", len(eligible))
    add("depth_1_minute_players", "all", len(used))
    evidence.team(game, team, "depth_5_minute_players", len(eligible))
    for state, players in players_by_state.items():
        add("depth_final_5m_by_margin", state, len(players))
    if game.phase == "playoffs" and len(top_eight) == 8:
        add("playoff_regular_top8_appearing", "all", len(top_eight & spans.keys()) / 8)
        add("playoff_regular_top8_playing_5m", "all", len(top_eight & set(eligible)) / 8)
        total = sum(sum(q.values()) for q in quarter.values())
        credited = sum(sum(quarter[pid].values()) for pid in top_eight)
        add("playoff_minutes_to_regular_top8", "all", credited / total)

    home = team == game.home
    close_seconds = Counter()
    start_five_seconds = 0
    for frame in game.intervals:
        if frame.period == 4 and frame.end > 2580 and abs(frame.margin) <= 5:
            duration = frame.end - max(frame.start, 2580)
            players = frame.home if home else frame.away
            close_seconds.update({pid: duration for pid in players})
            start_five_seconds += duration * (players == starters)
    if close_seconds:
        total = sum(close_seconds.values())
        starter_seconds = sum(close_seconds[pid] for pid in starters)
        add("close_Q4_player_seconds_from_starters", "all", starter_seconds / total)
        add("close_Q4_seconds_exact_starting_five", "all", start_five_seconds * 5 / total)
        final_close = next(frame for frame in reversed(game.intervals)
                           if frame.period == 4 and frame.end > 2580 and abs(frame.margin) <= 5)
        # Time-weighted most-used position slots and the last positive-time close lineup.
        closing = final_close.home if home else final_close.away
        add("close_Q4_last_lineup_starter_count", "all", len(closing & starters))
        for pid, duration in close_seconds.items():
            add("close_Q4_role_seconds_share", roles[pid], duration * 5 / total)
        for pid in starters:
            add("close_Q4_starter_seconds_share", roles[pid], close_seconds[pid] * 5 / total)
        evidence.team(game, team, "close_Q4_starter_share", starter_seconds / total)


def foul_situation(event, count):
    if count == 2 and event.period == 1:
        return "2_Q1"
    if count == 3 and event.period <= 2:
        return "3_first_half"
    if count in {4, 5}:
        return f"{count}_" + ("Q1_Q3" if event.period <= 3 else "Q4_OT")
    if count == 1 and event.period == 1:
        return "1_Q1_comparison"
    return None


def collect_foul_responses(evidence, game, team, spells, roles, foul_events):
    seen = set()
    for event, pid, count in foul_events:
        label = foul_situation(event, count)
        if pid not in spells or label is None or (pid, label) in seen:
            continue
        # Use the prior or current positive-clock stint, allowing an exit at this whistle.
        k = next((i for i, span in enumerate(spells[pid]) if span.start <= event.t <= span.end), None)
        if k is None or game.end - event.t <= 60:
            continue
        seen.add((pid, label))
        stint = spells[pid][k]
        role = roles[pid]
        group = f"{label}|{role}"
        near = stint.end - event.t <= 60 and stint.end < game.end
        on_whistle = stint.end == event.t
        add = lambda metric, key, value: evidence.add(game, metric, key, value)
        add("foul_exit_within_minute", group, near)
        add("foul_exit_same_clock", group, on_whistle)
        if label in {"1_Q1_comparison", "2_Q1"}:
            q1_clock = min(3, int((720 - event.t) // 180))
            add("q1_foul_clock_matched_exit_within_minute", f"{group}|clock_band_{q1_clock}", near)
        if label == "2_Q1" and role in {"star", "starter"}:
            evidence.team(game, team, "second_foul_Q1_exit_within_minute", near)
        if game.phase == "regular" and label != "1_Q1_comparison":
            evidence.fit(game, "foul_exit_within_minute", group, near)
        if not near:
            continue
        next_stint = spells[pid][k + 1] if k + 1 < len(spells[pid]) else None
        add("foul_bench_returned", group, next_stint is not None)
        if next_stint is not None:
            rest = next_stint.start - stint.end
            add("foul_bench_seconds_if_returned", group, rest)
            add("foul_return_elapsed_seconds_if_returned", group, next_stint.start)
            if game.phase == "regular" and label != "1_Q1_comparison":
                evidence.fit(game, "foul_bench_seconds_if_returned", group, rest)
            if label in {"2_Q1", "3_first_half"}:
                period = int(next_stint.start // 720) + 1 if next_stint.start < 2880 else 5
                add("early_foul_return_by_halftime", group, next_stint.start < 1440)
                if period <= 4:
                    add("early_foul_return_clock_seconds", f"{group}|Q{period}",
                        period_end(period) - next_stint.start)


def margin_bucket(margin):
    if abs(margin) <= 5:
        return "close_0_5"
    side = "ahead" if margin > 0 else "behind"
    size = "6_14" if abs(margin) < 15 else "15_19" if abs(margin) < 20 else (
        "20_24" if abs(margin) < 25 else "25_plus")
    return f"{side}_{size}"


def collect_blowouts(evidence, game, team, starters, spells, foul_events):
    last = {pid: spells[pid][-1].end for pid in starters if pid in spells}
    fouled_out = {pid for _, pid, count in foul_events if count >= 6}
    ejected = {player_id(event.player) for event in game.events if event.kind == 11}
    for pid in starters - fouled_out - ejected:
        if pid not in last or last[pid] < 2160 or last[pid] >= game.end:
            continue
        # Use score immediately before the first event at the substitution clock.
        clock = last[pid]
        prior = next(frame for frame in reversed(game.intervals) if frame.start < clock)
        margin = prior.margin if team == game.home else -prior.margin
        add = lambda name, label, value: evidence.add(game, name, label, value)
        if clock < 2880:
            add("Q4_permanent_starter_exit_clock_seconds", margin_bucket(margin), 2880 - clock)
    starts = [frame.start for frame in game.intervals]
    for time_left in (540, 360, 180, 60):
        now = 2880 - time_left
        frame = game.intervals[bisect_right(starts, now) - 1]
        players, margin = (frame.home, frame.margin) if team == game.home else (frame.away, -frame.margin)
        group = f"{time_left // 60}m|{margin_bucket(margin)}"
        evidence.add(game, "Q4_starters_on_floor_at_checkpoint", group, len(players & starters))
        for pid in players & starters:
            pulled = now < last[pid] <= now + 60 and last[pid] < game.end and pid not in fouled_out | ejected
            evidence.add(game, "Q4_permanent_exit_next_minute", group, pulled)
            if game.phase == "regular":
                evidence.fit(game, "Q4_permanent_exit_next_minute", group, pulled)


def opponent(game, team):
    return game.away if team == game.home else game.home


def team_margin(game, team, event):
    return event.home - event.away if team == game.home else event.away - event.home


def timeout_types(game):
    """Flag likely mandatory entries when an unfilled slot reaches its clock window."""
    types = {}
    for q, rows in groupby(enumerate(game.events), key=lambda row: row[1].period):
        prior = []
        for index, event in rows:
            if event.kind != 9 or event.team not in game.teams:
                continue
            left = period_end(q) - event.t
            first_due = not prior and event.team == game.home and 375 <= left <= 419
            second_due = len(prior) == 1 and event.team != prior[0] and 135 <= left <= 179
            types[index] = ("challenge" if event.subtype == 7 else "possible_mandatory"
                            if q <= 4 and (first_due or second_due) else "other_regular")
            prior.append(event.team)
    return types


def scoring_bursts(game):
    """Collapse scoring at the same clock by the same team, including free-throw trips."""
    bursts = []
    for index, event in enumerate(game.events):
        if event.kind not in {1, 3} or event.shot_pts not in {1, 2, 3} or event.team not in game.teams:
            continue
        if bursts:
            first, last, pts = bursts[-1]
            previous = game.events[last]
            if (event.period, event.t, event.team) == (previous.period, previous.t, previous.team):
                bursts[-1] = (first, index, pts + event.shot_pts)
                continue
        bursts.append((index, index, event.shot_pts))
    return bursts


def response_timeout(game, end_index, defending, types):
    scored = game.events[end_index]
    for j in range(end_index + 1, len(game.events)):
        current = game.events[j]
        if current.period != scored.period or current.t - scored.t > 10:
            break
        if j in types and current.team == defending and types[j] != "challenge":
            return types[j]
        if current.kind in {1, 2, 3, 5, 6, 10, 13}:
            break
    return None


def collect_timeouts(evidence, game):
    add = lambda metric, group, value: evidence.add(game, metric, group, value)
    timeouts = timeout_types(game)
    for team in game.teams:
        own = [(game.events[index], kind) for index, kind in timeouts.items()
               if game.events[index].team == team]
        add("timeouts_per_team_game", "all_logged", len(own))
        for kind in ("challenge", "possible_mandatory", "other_regular"):
            add("timeouts_per_team_game", kind, sum(group == kind for _, group in own))
        for period in range(1, game.events[-1].period + 1):
            label = f"Q{period}" if period <= 4 else "OT"
            add("timeouts_per_team_period", label, sum(event.period == period for event, _ in own))
            if period < 4:
                continue
            late = [(event, kind) for event, kind in own if event.period == period
                    and period_end(period) - event.t <= 120]
            add("timeouts_per_team_in_last_2m", label, len(late))
            for event, kind in late:
                margin = team_margin(game, team, event)
                state = "ahead" if margin > 0 else "behind" if margin < 0 else "tied"
                add("late_timeout_seconds_left", f"{label}|{state}", period_end(period) - event.t)

    previous = None
    run = 0
    bursts = scoring_bursts(game)
    for i, (_, end, pts) in enumerate(bursts):
        scored = game.events[end]
        defending = opponent(game, scored.team)
        if previous != (scored.period, scored.team):
            run = 0
        previous = scored.period, scored.team
        after = run + pts
        response = response_timeout(game, end, defending, timeouts)
        band = "0_5" if after < 6 else "6_7" if after < 8 else "8_9" if after < 10 else "10_plus"
        add("timeout_after_scoring_burst", band, response is not None)
        if game.phase == "regular":
            evidence.fit(game, "timeout_after_scoring_burst", band, response is not None)

        for threshold in (6, 8, 10):
            if not run < threshold <= after:
                continue
            label = str(threshold)
            add("timeout_at_run_first_crossing", label, response is not None)
            add("timeout_at_run_first_crossing_excluding_possible_mandatory", label,
                response == "other_regular")
            if threshold == 8:
                evidence.team(game, defending, "timeout_at_8_run_first_crossing", response is not None)
            if i + 1 < len(bursts):
                next_score = game.events[bursts[i + 1][1]]
                if next_score.period == scored.period:
                    add("next_score_stops_run", f"{label}|{response or 'no_timeout'}",
                        next_score.team == defending)
        run = after


Possession = namedtuple("Possession", "start end rows")


def period_possessions(game, rows):
    """Use the archive's possession endings, moving a missed-shot handoff to the rebound."""
    previous = rows[0]
    pending = []
    for event in rows:
        pending.append(event)
        if not event.ends or event.offense not in game.teams:
            continue
        start = previous
        if previous.kind in {2, 3} and previous.offense != event.offense:
            for row in pending:
                if row.kind == 4 and row.team == event.offense:
                    start = row
                    break
                if row.kind in {1, 2, 5, 6, 10}:
                    break
        yield Possession(start, event, pending)
        previous, pending = event, []


def late_seconds_bucket(left):
    return "0_10s" if left <= 10 else "10_24s" if left <= 24 else "24_60s"


def trailing_margin_bucket(margin):
    if margin >= -1:
        return "1"
    if margin >= -3:
        return "2_3"
    if margin >= -6:
        return "4_6"
    return "7_10" if margin >= -10 else "11_plus"


def take_foul(event, defense):
    return event.kind == 6 and event.subtype == 28 and event.team == defense


def collect_late_fouling(evidence, game, period, rows, possessions):
    add = lambda metric, group, value: evidence.add(game, metric, group, value)
    end = period_end(period)
    times = [event.t for event in rows]
    for event in rows:
        left = end - event.t
        if event.team not in game.teams or not take_foul(event, event.team) or not 0 < left <= 60:
            continue
        margin = team_margin(game, event.team, event)
        if margin < 0:
            add("trailing_take_foul_event_seconds_left", str(-margin), left)
        if margin == 3 and left <= 24:
            add("up_three_take_foul_event_seconds_left", "all", left)

    for start, finish, events in possessions:
        # Enter at gain of possession or at 60 seconds if the offense already had the ball.
        entry = max(start.t, end - 60)
        if finish.t <= end - 60 or entry >= end:
            continue
        defense = opponent(game, finish.offense)
        anchor = rows[bisect_right(times, entry) - 1] if entry > start.t else start
        margin = team_margin(game, defense, anchor)
        left = end - entry
        if margin >= 0 and (margin != 3 or left > 24):
            continue
        eligible = [event for event in events if event.t >= entry and event.kind == 6
                    and event.team == defense and event.subtype in {1, 28}
                    and event.offense == finish.offense and team_margin(game, defense, event) == margin]
        narrow = any(take_foul(event, defense) for event in eligible)
        broad = narrow or any(event.t - entry <= 5 for event in eligible)
        band = late_seconds_bucket(left)
        if margin < 0:
            group = f"down_{trailing_margin_bucket(margin)}|{band}"
            metric = "trailing_take_foul_per_opponent_possession"
        else:
            group = band
            metric = "up_three_take_foul_per_opponent_possession"
        add(metric, group, narrow)
        add(metric + "_including_early_personal", group, broad)
        if game.phase == "regular":
            evidence.fit(game, metric, group, narrow)


def collect_two_for_one(evidence, game, period, possessions):
    add = lambda metric, group, value: evidence.add(game, metric, group, value)
    end = period_end(period)
    for i, (start, finish, events) in enumerate(possessions):
        left = end - start.t
        if not 30 <= left <= 42 or i == 0 or possessions[i - 1].end.offense == finish.offense:
            continue
        first_shot = next((event for event in events if event.kind in {1, 2}
                           and event.team == finish.offense and event.t >= start.t), None)
        time_of_shot = end - first_shot.t if first_shot else 0
        early = time_of_shot >= 25
        close = period >= 4 and abs(team_margin(game, finish.offense, start)) <= 5
        clock = "30_34s" if left < 35 else "35_38s" if left < 39 else "39_42s"
        group = f"{'late_close' if close else 'other'}|{clock}"
        add("two_for_one_early_shot", group, early)
        add("two_for_one_early_shot_at_24s", group, time_of_shot >= 24)
        add("two_for_one_early_shot_at_27s", group, time_of_shot >= 27)
        if game.phase == "regular":
            evidence.fit(game, "two_for_one_early_shot", group, early)
        if not early:
            continue
        next_sides = [p.end.offense for p in possessions[i + 1:i + 3]]
        regained = (next_sides == [opponent(game, finish.offense), finish.offense]
                    and possessions[i + 2].start.t < end)
        add("two_for_one_second_possession_after_early_shot", group, regained)
        if regained:
            second = possessions[i + 2]
            shot = any(event.kind in {1, 2} and event.team == finish.offense for event in second.rows)
            add("two_for_one_second_shot_if_regained", group, shot)


def collect_hacking(evidence, game, period, rows, priors, player_names):
    targets = defaultdict(list)
    end = period_end(period)
    for i, event in enumerate(rows):
        if event.kind != 6 or event.subtype not in {6, 28} or end - event.t <= 120:
            continue
        if event.team not in game.teams or event.offense != opponent(game, event.team):
            continue
        drawn = event.drawn or player_id(event.third)
        if not drawn:
            continue
        # Require a free throw by the recipient at this whistle.
        for following in rows[i + 1:]:
            if following.t != event.t or following.kind == 6:
                break
            if following.kind == 3 and player_id(following.player) == drawn:
                targets[event.team, drawn].append(event.t)
                break
    found = []
    for (defense, pid), times in targets.items():
        prior = priors[pid]
        if prior.ft_attempts < 30 or prior.ft_made / prior.ft_attempts >= 0.65:
            continue
        paired = [(a, b) for a, b in zip(times, times[1:]) if b - a <= 180]
        if paired:
            first, second = paired[0]
            found.append((defense, pid))
            label = f"{game.year}_{game.phase}"
            evidence.examples[label].append({
                "game": game.id, "fouling_team": defense, "recipient": player_names.get(pid, str(pid)),
                "quarter": period, "first_seconds_left": round(end - first, 2),
                "second_seconds_left": round(end - second, 2),
                "prior_ft_attempts": prior.ft_attempts,
                "prior_ft_share": round(prior.ft_made / prior.ft_attempts, 4),
            })
    return found


def collect_end_game(evidence, game, priors, player_names):
    hacked = Counter()
    for period, period_rows in groupby(game.events, key=lambda event: event.period):
        rows = list(period_rows)
        possessions = list(period_possessions(game, rows))
        collect_two_for_one(evidence, game, period, possessions)
        if period >= 4:
            collect_late_fouling(evidence, game, period, rows, possessions)
        hacked.update(team for team, _ in collect_hacking(evidence, game, period, rows, priors, player_names))
    for team in game.teams:
        evidence.add(game, "hack_proxy_sequences_per_team_game", "all", hacked[team])
        evidence.add(game, "hack_proxy_team_game_with_sequence", "all", hacked[team] > 0)


def collect_games(connection, cache):
    evidence = Evidence()
    coverage = {}
    audit = Counter()
    player_names = {}
    ref = box_reference()
    for year in SEASONS:
        priors = defaultdict(Prior)
        team_totals = defaultdict(Counter)
        last_game = {}
        for phase in PHASES:
            file = cache / f"pbp_{phase}_{year}.parquet"
            top = {team: {pid for pid, _ in total.most_common(8)} for team, total in team_totals.items()}
            count = Counter()
            for game in games(connection, file):
                count["archive_games"] += 1
                count["archive_events"] += len(game.events)
                game.intervals = reconstruct(game, count)
                if not game.intervals:
                    count[f"excluded_{game.id}"] += 1
                    continue
                count["analyzed_games"] += 1
                collect_timeouts(evidence, game)
                for event in game.events:
                    for field in (event.player, event.second, event.third):
                        pid = player_id(field)
                        if pid:
                            player_names[pid] = field.split(" ", 1)[1]
                collect_end_game(evidence, game, priors, player_names)
                scoring = Counter()
                for event, pts in points(game):
                    pid = player_id(event.player)
                    if pid:
                        scoring[pid] += pts
                foul_events = list(personal_fouls(game))
                fouls = Counter({pid: number for _, pid, number in foul_events})
                teams_for_audit = []
                ft = Counter(player_id(event.player) for event in game.events
                             if event.kind == 3 and player_id(event.player))
                ft_made = Counter(player_id(event.player) for event, _ in points(game) if event.kind == 3)
                for team in game.teams:
                    home = team == game.home
                    starters = lineup(game.events[0].lineup_home if home else game.events[0].lineup_away)
                    spans, quarter, players_by_state = spells_for_team(game.intervals, home)
                    roles = roles_for_game(starters, spans, priors)
                    previous_date, previous_minutes = last_game.get(team, (None, {}))
                    for pid, intervals in spans.items():
                        previous = ((game.date - previous_date).days, previous_minutes[pid]
                                    ) if pid in previous_minutes and phase == "regular" else None
                        collect_player_rotations(evidence, game, team, roles[pid], intervals,
                                                 quarter[pid], previous, priors[pid])
                    collect_team_rotations(evidence, game, team, starters, spans, quarter,
                                           players_by_state, roles, top.get(team, set()))
                    collect_foul_responses(evidence, game, team, spans, roles, foul_events)
                    collect_blowouts(evidence, game, team, starters, spans, foul_events)
                    teams_for_audit.append((starters, quarter, team))
                    last_game[team] = (game.date, {pid: sum(quarter[pid].values()) / 60 for pid in starters})
                    if phase == "regular":
                        for pid in spans:
                            minutes = sum(quarter[pid].values()) / 60
                            total = priors[pid]
                            total.appearances += 1
                            total.minutes += minutes
                            total.points += scoring[pid]
                            total.starts += pid in starters
                            total.ft_attempts += ft[pid]
                            total.ft_made += ft_made[pid]
                            team_totals[team][pid] += minutes
                audit_box(game, teams_for_audit, player_names, fouls, ref, audit)
            expected = EXPECTED[year][PHASES.index(phase)]
            if count["archive_games"] != expected:
                raise ValueError(f"{year} {phase}: expected {expected} games, found {count['archive_games']}")
            with file.open("rb") as handle:
                coverage[f"{year}_{phase}"] = dict(
                    sorted(count.items()), url=f"{ARCHIVE}/{file.name}",
                    sha256=file_digest(handle, "sha256").hexdigest(),
                )
    return evidence, coverage, audit


def evaluate_fits(fit_rows):
    result = {}
    for metric, rows in sorted(fit_rows.items()):
        train = defaultdict(list)
        test = defaultdict(list)
        for year, group, value in rows:
            (test if year == 2026 else train)[group].append(value)
        pooled = [value for group in train.values() for value in group]
        is_boolean = isinstance(pooled[0], bool)
        baseline = mean(pooled) if is_boolean else median(pooled)
        predict = {}
        for group in sorted(set(train) | set(test)):
            values = train[group]
            if is_boolean:
                predict[group] = (sum(values) + 20 * baseline) / (len(values) + 20)
            else:
                predict[group] = median(values) if len(values) >= 20 else baseline
        errors = []
        base_errors = []
        for group, values in test.items():
            for value in values:
                if is_boolean:
                    errors.append((predict[group] - value) ** 2)
                    base_errors.append((baseline - value) ** 2)
                else:
                    errors.append(abs(predict[group] - value))
                    base_errors.append(abs(baseline - value))
        result[metric] = {
            "loss": "Brier" if is_boolean else "absolute_error",
            "training_n": len(pooled), "test_n": len(errors),
            "training_baseline": round(baseline, 4),
            "test_loss": round(mean(errors), 5), "baseline_test_loss": round(mean(base_errors), 5),
            "groups": {group: {"train_n": len(train[group]), "prediction": round(pred, 4),
                               "test": summary(test[group])} for group, pred in predict.items()},
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "output/rotation-evidence")
    parser.add_argument("--output", type=Path, default=ROOT / "data/research/rotation_evidence.json")
    args = parser.parse_args()

    import duckdb

    with duckdb.connect(config={"threads": 2}) as db:
        evidence, coverage, audit = collect_games(db, args.cache)
    result = {
        "schema_version": 1, "fit_seasons": [2024, 2025], "holdout_season": 2026,
        "coverage": coverage, "box_score_check": dict(sorted(audit.items())),
        "observations": evidence.describe(), "held_out_fits": evaluate_fits(evidence.fits),
        "hack_proxy_examples_by_season": dict(sorted(evidence.examples.items())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(args.output)
    print(json.dumps({"games": {key: row["analyzed_games"] for key, row in coverage.items()},
                      "box_score_check": result["box_score_check"]}, indent=2))


if __name__ == "__main__":
    main()
