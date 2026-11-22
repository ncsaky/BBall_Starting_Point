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
                for event in game.events:
                    for field in (event.player, event.second, event.third):
                        pid = player_id(field)
                        if pid:
                            player_names[pid] = field.split(" ", 1)[1]
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
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(args.output)
    print(json.dumps({"games": {key: row["analyzed_games"] for key, row in coverage.items()},
                      "box_score_check": result["box_score_check"]}, indent=2))


if __name__ == "__main__":
    main()
