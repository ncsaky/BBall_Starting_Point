#!/usr/bin/env python3
"""Fit the per-body-part injury model (v2) to Basketball Index Injury Tracker evidence.

Evidence: data/research/bbi/tools/injury_*.json (extracted by scripts/bbi_extract_tools.py from the signed-in tool page).
For each body part, a Poisson model of injuries per game played, fitted on real player-seasons 2015-16..2025-26:

    injuries(part) ~ games_played * exp(season_intercept + b . features)

features (standardized): age, age^2, height, weight, possessions per game (workload), rim pressure, offensive rebounding,
conditioning (stamina), center, guard, recent same-part injuries (time-decayed) and recent other-part injuries.
Season intercepts are unpenalized so reporting coverage across seasons cannot drive the shared slopes. Gameplay uses
one intercept per part, anchored to the complete public records of 2023-24 through 2025-26 (new in-season injuries and
illnesses that cost a regular-season game; new_in_season) with the engine's history weight (injury_model.HISTORY_WEIGHT,
recorded as rate_fit.history_weight; rebuild whenever it changes) and the history a new career starts with.
The same-part term is the compounding effect; age/body/style terms decide which
injuries a player tends to get. Recovery times are not modeled parametrically: the engine samples a real absence for
the drawn part (diagnosis, days, games), weighted toward recent seasons.

    PYTHONPATH=src .venv/bin/python scripts/build_injury_model.py [--write] [--model-only]
Writes data/canonical/injury_model_v2.json and (unless --model-only) the git-ignored per-player evidence
data/canonical/injury_player_evidence_v4.json: real players' injury and illness history (the tracker since 2021-22
plus the public 2023-24 to 2025-26 stretches it lacks, see classify_public_stretches), forecasts and recovery speed.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

B = ROOT / "data/research/bbi/tools"
OUT = ROOT / "data/canonical/injury_model_v2.json"
# git-ignored: per-player Basketball Index evidence plus the public stretches the tracker lacks in 2023-24 through
# 2025-26 (v4, INJURY-ANCHOR 2026-11-21; v3 had 2025-26 only).
EVIDENCE_OUT = ROOT / "data/canonical/injury_player_evidence_v4.json"
# Complete public missed-game records (NBA injury reports + box scores; scripts/research/injury_history_2025_26.py
# --season). The tracker misses about a fifth of the injuries that cost games in 2023-25 and two-thirds in 2025-26, so
# real players' startup history is completed from these files, and the gameplay base rates are anchored to them.
PUBLIC_HISTORIES = {season: ROOT / f"data/research/injury_history_{season.replace('-', '_')}.json"
                    for season in ("2023-24", "2024-25", "2025-26")}
PUBLIC_HISTORY = PUBLIC_HISTORIES["2025-26"]
# An opening-night stretch continues an injury already in the tracker when a same-part entry within this many days
# before it either started after the previous regular season ended or never logged a return (health.py uses the same
# 400-day window for the real 2026-27 opening-night list).
CARRY_IN_DAYS = 400
# A stretch on a new team that starts this soon after the same part's stretch on the old team is one injury split by a
# trade, not a new one.
TRADE_SPLIT_DAYS = 10
FIRST_SEASON = "2015-16"
# Gameplay base rates are anchored to the complete public records (INJURY-ANCHOR, 2026-11-21): every injury or illness
# that cost a regular-season game, from official injury reports and box scores. The tracker seasons the rates used to be
# anchored to (2021-22 to 2024-25) are kept for comparisons in the research scripts.
RATE_ANCHOR_SEASONS = tuple(PUBLIC_HISTORIES)
TRACKER_ANCHOR_SEASONS = ("2021-22", "2022-23", "2023-24", "2024-25")
# The anchor splits each player-season into this many stretches so the history grows through the season as in the engine.
ANCHOR_SEGMENTS = 8
# Recovery times come from absences recorded since 2015, the same seasons the injury-rate models are fitted on
# (INJURIES-2, 2026-11-20). Older records describe a different reporting world: before 2005-06 the injured list had a
# five-game minimum and half the records have no logged return (median return 28 days in 2000-05, 10 in 2006-14, 5 in
# 2015-20, 4 in 2021-26). Even at a 6-year half-life they made the pool's tail half again too long against the
# tracker's own 2021-25 absences (90th percentile 45 days against 28).
RECOVERY_FIRST_YEAR = 2015
RIDGE = 3.0
HISTORY_DECAY_YEARS = 1.5
PARTS = ["ankle", "knee", "back", "hamstring", "hip", "foot", "calf", "shoulder", "groin", "quadriceps", "toe", "head",
         "wrist", "hand", "achilles", "thumb"]
# Basketball Index's rarer parts folded into the nearest of its 16 risk parts.
MERGE = {"heel": "foot", "finger": "hand", "elbow": "shoulder", "forearm": "wrist", "arm": "shoulder", "leg": "calf",
         "shin": "calf", "neck": "back", "abdomen": "back", "ribs": "back", "chest": "back", "tailbone": "back",
         "eye": "head", "dental": "head"}
FEATURES = ["age", "age2", "height", "weight", "poss_pg", "rim_pressure", "offensive_rebounding", "stamina",
            "center", "guard", "prior_same", "prior_other"]


def rows(name):
    d = json.loads((B / name).read_text())
    return d["rows"] if isinstance(d, dict) and "rows" in d else d


def season_start(season: str) -> date:
    return date(int(season[:4]), 10, 20)


def part_of(h) -> str | None:
    if h.get("cat") == "illness":
        return "illness"
    if h.get("cat") != "injury" or not h.get("part"):
        return None
    p = MERGE.get(h["part"], h["part"])
    return p if p in PARTS else None


def classify_public_stretches(tracker_rows, team_names, path=PUBLIC_HISTORY):
    """Sort every public 2025-26 missed-game stretch into what the injury history should do with it.

    Returns (stretches, status) where status[i] is one of:
      "added"          a new injury the tracker lacks: goes into the player's history;
      "tracker"        the tracker already logged it (Codex's match: player, team, category, site, side, date);
      "trade_split"    the same injury continuing on a new team after a trade;
      "carried_in"     on the team's opening night, continuing an injury already in the tracker;
      "management"     every missed game listed only as "injury management" (planned games off for a known condition:
                       61% on the second night of a back-to-back, 93% after a same-part injury in the past year; the
                       tracker logged them about 0.6x as often as other one-game injuries; STAR-INJURIES report);
      "illness"        an illness the tracker lacks: goes into the player's history too (INJURY-ANCHOR: the slopes are fit
                       with illness in the history, and counting it predicts the next illness and injury better);
      "no_part"        no body part the model knows;
      "not_medical"    coach's decision, G League, rest, personal, suspension, not with team, trade pending,
                       reconditioning without a named injury, or no reason given.
    An opening-night stretch with no tracker trace (a preseason or summer injury, or one from before the NBA) is
    "added", dated at the first game missed.
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "scripts/research"))
    from injury_history_2025_26 import match_tracker   # Codex's tracker match, so both reports count the same way
    doc = json.loads(Path(path).read_text())
    season = doc["season"]
    stretches = doc["stretches"]
    previous_season_end = date(int(season[:4]), 4, 15)
    candidates = defaultdict(list)
    for index, s in enumerate(stretches):
        if s["reason_category"] in ("injury", "illness"):
            candidates[s["player_id"]].append((index, s | {"team_name": team_names.get(s["team"], s["team"])}))
    matched = set()
    tracked = defaultdict(list)
    for entry in tracker_rows:
        if entry.get("cat") == "injury" and entry.get("start") and entry.get("player_id"):
            tracked[entry["player_id"]].append(entry)
        if entry.get("season") == season and entry.get("cat") in ("injury", "illness") and entry.get("start"):
            index = match_tracker(entry, candidates.get(entry.get("player_id"), []))
            if index is not None:
                matched.add(index)

    def sides_agree(a, b):
        return not (a in ("left", "right") and b in ("left", "right") and a != b)

    def carried_in(s):
        first = date.fromisoformat(s["first_game_missed"])
        for entry in tracked[s["player_id"]]:
            start = date.fromisoformat(entry["start"][:10])
            if (part_of(entry) == s["body_part"] and sides_agree((entry.get("side") or "").lower(), s.get("side") or "")
                    and 0 <= (first - start).days <= CARRY_IN_DAYS
                    and (start > previous_season_end or entry.get("censored") or not entry.get("end"))):
                return True
        return False

    status = {}
    last_by_player = {}
    for index, s in sorted(enumerate(stretches), key=lambda item: (item[1]["player_id"], item[1]["first_game_missed"])):
        category, part = s["reason_category"], MERGE.get(s.get("body_part") or "", s.get("body_part"))
        if category not in ("injury", "illness"):
            status[index] = "not_medical"
            continue
        previous = last_by_player.get(s["player_id"])
        last_by_player[s["player_id"]] = s
        if index in matched:
            status[index] = "tracker"
        elif category == "illness":
            status[index] = "illness"
        elif part not in PARTS:
            status[index] = "no_part"
        elif trade_split(previous, s):
            status[index] = "trade_split"
        elif s.get("injury_management_only"):
            status[index] = "management"
        elif s.get("at_team_season_start") and carried_in(s):
            status[index] = "carried_in"
        else:
            status[index] = "added"
    return stretches, status


def trade_split(previous, s) -> bool:
    """True when stretch s continues the player's previous medical stretch on another team (one injury split by a
    trade), not a new injury."""
    if not previous or previous["team"] == s["team"] or previous.get("body_part") != s.get("body_part"):
        return False
    a, b = previous.get("side") or "", s.get("side") or ""
    if a in ("left", "right") and b in ("left", "right") and a != b:
        return False
    gap = (date.fromisoformat(s["first_game_missed"]) - date.fromisoformat(previous["last_game_missed"])).days
    return 0 <= gap <= TRADE_SPLIT_DAYS


def team_schedules(stretches) -> dict[str, list[str]]:
    """Each team's game dates (all phases), from the games its players missed. Every team game has someone out (G League
    assignments, coach's decisions), so this is the full schedule: 82 regular-season dates for every team but one
    team-season with 81 in the three files."""
    days = defaultdict(set)
    for s in stretches:
        for source in s.get("sources") or []:
            days[s["team"]].add(source["date"])
    return {team: sorted(d) for team, d in days.items()}


def _medical_chains(stretches):
    """Each player's medical stretches in order, with whether each directly continues the previous one (same team, no
    game played between: a change of body part or side, or injury then illness, inside one absence)."""
    schedule = team_schedules(stretches)
    position = {team: {d: i for i, d in enumerate(days)} for team, days in schedule.items()}
    ordered = sorted(((i, s) for i, s in enumerate(stretches) if s["reason_category"] in ("injury", "illness")),
                     key=lambda item: (item[1]["player_id"], item[1]["first_game_missed"]))
    out, previous = [], {}
    for index, s in ordered:
        p = previous.get(s["player_id"])
        previous[s["player_id"]] = s
        continues = False
        if p is not None and p["team"] == s["team"]:
            a = position[s["team"]].get(p["last_game_missed"])
            b = position[s["team"]].get(s["first_game_missed"])
            continues = a is not None and b is not None and b == a + 1
        out.append((index, s, p, continues))
    return out, schedule


def new_in_season(stretches) -> dict[int, str | None]:
    """The complete record's new in-season injuries and illnesses, which the gameplay base rates are anchored to: one
    per absence the engine could draw (it draws injuries only in games played).

    Kept: injury and illness stretches that cost a regular-season game. Set aside, as in Codex's reports
    (docs/agents/tasks/injury-history-2023-25.md, "setting aside both"): stretches listed only as injury management
    (planned games off for a known condition, which the rest model covers) and stretches already underway at the team's
    first game (offseason, preseason and carried-over injuries, which the season-start injuries cover). Also set aside:
    the second half of an injury split by a trade, and a stretch that directly continues another medical stretch with no
    game played between (about 5%: the report changed the body part or side, or an injured player fell ill), since each
    is one absence, not two.
    Returns {index: part}, part being a model body part, "illness", or None for an injury with no known body part."""
    out: dict[int, str | None] = {}
    for index, s, previous, continues in _medical_chains(stretches)[0]:
        if (continues or trade_split(previous, s) or int(s.get("regular_season_games_missed") or 0) < 1
                or s.get("at_team_season_start") or s.get("injury_management_only")):
            continue
        category = s["reason_category"]
        part = "illness" if category == "illness" else MERGE.get(s.get("body_part") or "", s.get("body_part"))
        out[index] = part if part in PARTS or part == "illness" else None
    return out


def absence_lengths(stretches, new) -> dict[int, tuple[int, int, bool]]:
    """For each new in-season stretch: (games missed in all phases, regular-season games missed, censored), counting the
    stretches that directly continue it as the same absence. Censored: still out at the team's last game of the season
    (playoffs included), so the absence lasted at least that long."""
    chains, schedule = _medical_chains(stretches)
    following = {}
    for k, (index, s, _, continues) in enumerate(chains):
        if k + 1 < len(chains) and chains[k + 1][3] and chains[k + 1][1]["player_id"] == s["player_id"]:
            following[index] = chains[k + 1][0]
    out = {}
    for index in new:
        games = regular = 0
        current = index
        while True:
            s = stretches[current]
            games += int(s["games_missed"])
            regular += int(s["regular_season_games_missed"])
            if current not in following:
                break
            current = following[current]
        out[index] = (games, regular, stretches[current]["last_game_missed"] == schedule[s["team"]][-1])
    return out


LENGTH_BANDS = ((1, "1"), (5, "2-5"), (10, "6-10"), (20, "11-20"), (10**9, "21+"))   # games missed
# Body-part groups for the recovery-length correction (the same groups as the length reports, scripts/research/
# injury_lengths.py); each has 90+ absences in the three complete seasons.
RECOVERY_GROUPS = {"ankle": "ankle/foot/toe", "foot": "ankle/foot/toe", "toe": "ankle/foot/toe", "knee": "knee",
                   "quadriceps": "thigh", "hamstring": "thigh", "calf": "calf/achilles", "achilles": "calf/achilles",
                   "hip": "hip/groin", "groin": "hip/groin", "back": "back", "shoulder": "arm/hand", "wrist": "arm/hand",
                   "hand": "arm/hand", "thumb": "arm/hand", "head": "head", "illness": "illness"}


def band_index(games: int) -> int:
    return next(k for k, (limit, _) in enumerate(LENGTH_BANDS) if games <= limit)


def km_band_shares(lengths) -> list[float]:
    """Share of absences in each length band, from (games missed, censored) pairs: Kaplan-Meier, so an absence still
    running at the team's last game counts as lasting at least that long instead of as a short one."""
    events = Counter(g for g, censored in lengths if not censored)
    survival, s = {}, 1.0
    for t in sorted(events):
        at_risk = sum(1 for g, _ in lengths if g >= t)
        s *= 1.0 - events[t] / at_risk
        survival[t] = s

    def beyond(x):   # P(games > x)
        value = 1.0
        for t in sorted(survival):
            if t > x:
                break
            value = survival[t]
        return value
    shares, previous = [], 1.0
    for limit, _ in LENGTH_BANDS[:-1]:
        shares.append(previous - beyond(limit))
        previous = beyond(limit)
    return [*shares, previous]


def correct_recovery_lengths(recovery, lengths_by_part, part_counts):
    """Re-weight each part's recovery pool so the lengths of absences that cost a game match the complete public records
    (INJURY-ANCHOR). The pools are the tracker's recorded absences, and the tracker misses short absences far more often
    than long ones (one game: 48% of the complete records' absences, 40% of the tracker's), so drawn absences ran long.
    For each body-part group, every pool entry in a length band is weighted by (complete share of the band) / (pool share
    of the band), the pool shares mixing the group's parts in proportion to their complete counts. Within a band the
    tracker's real durations and diagnoses stay as they are, and parts keep their differences inside a group (an Achilles
    absence stays longer than a calf one). Weights are rescaled so each part's share of draws that cost a game is kept.
    Returns {group: (complete shares, pool shares before)} for the report."""
    groups = defaultdict(list)
    for part, lengths in lengths_by_part.items():
        if part in RECOVERY_GROUPS:
            groups[RECOVERY_GROUPS[part]].extend(lengths)
    report = {}
    for group, lengths in groups.items():
        parts = [p for p in recovery if RECOVERY_GROUPS.get(p) == group]
        total = sum(part_counts.get(p, 0) for p in parts)
        if not parts or not total:
            continue
        target = km_band_shares(lengths)
        mixed = [0.0] * len(LENGTH_BANDS)
        for p in parts:
            weights = [0.0] * len(LENGTH_BANDS)
            for e in recovery[p]:
                if e["days"] // 2 >= 1:
                    weights[band_index(e["days"] // 2)] += float(e.get("w") or 1.0)
            for k, w in enumerate(weights):
                mixed[k] += part_counts.get(p, 0) / total * w / (sum(weights) or 1.0)
        factor = [t / m if m > 0 else 1.0 for t, m in zip(target, mixed)]
        for p in parts:
            costing = [e for e in recovery[p] if e["days"] // 2 >= 1]
            before = sum(float(e.get("w") or 1.0) for e in costing)
            for e in costing:
                e["w"] = float(e.get("w") or 1.0) * factor[band_index(e["days"] // 2)]
            after = sum(e["w"] for e in costing) or 1.0
            for e in costing:
                e["w"] = round(e["w"] * before / after, 6)
        report[group] = ([round(t, 4) for t in target], [round(m, 4) for m in mixed])
    return report


def game_share(quantiles) -> float:
    """Share of the engine's draws for a part that cost at least one game: it draws days = max(1, round(quantile)) and
    misses days // 2 games (injury_model.sample_recovery, health.injury_return_date)."""
    from nba_gm_data.injury_model import _days_at
    n = 4000
    return sum(1 for k in range(n) if max(1, int(round(_days_at(quantiles, (k + 0.5) / n)))) >= 2) / n


def public_history_entries(stretches, status):
    """History rows [start, part, days, label] for the added injuries and illnesses. Days use the tracker's unit, two
    per missed game (INJURIES-2); the engine reads only the date and part."""
    out = defaultdict(list)
    for index, s in enumerate(stretches):
        if status.get(index) not in ("added", "illness"):
            continue
        part = "illness" if status[index] == "illness" else MERGE.get(s["body_part"], s["body_part"])
        diagnosis = next((d for d in s.get("diagnoses") or [] if d), "")
        label = f"{part} {diagnosis.lower()}".strip() if diagnosis else f"{part} injury"
        out[s["player_id"]].append([s["first_game_missed"], part, 2 * int(s["games_missed"]), label])
    return out


def poisson_ridge(X, y, exposure, intercepts, lam=RIDGE, iters=60):
    """Newton/IRLS for Poisson counts with an exposure offset and unpenalized intercepts."""
    n = len(X[0])
    b = [*intercepts, *([0.0] * (n - len(intercepts)))]
    for _ in range(iters):
        g = [0.0] * n
        H = [[0.0] * n for _ in range(n)]
        for x, yi, e in zip(X, y, exposure):
            eta = sum(bi * xi for bi, xi in zip(b, x))
            mu = e * math.exp(max(-30.0, min(30.0, eta)))
            r = yi - mu
            for i in range(n):
                g[i] += r * x[i]
                for j in range(i, n):
                    H[i][j] += mu * x[i] * x[j]
        for i in range(len(intercepts), n):
            g[i] -= lam * b[i]
            H[i][i] += lam
        for i in range(n):
            for j in range(i):
                H[i][j] = H[j][i]
        # Solve H d = g (Gaussian elimination).
        A = [row[:] + [gi] for row, gi in zip(H, g)]
        for i in range(n):
            piv = max(range(i, n), key=lambda r: abs(A[r][i]))
            A[i], A[piv] = A[piv], A[i]
            for r in range(i + 1, n):
                f = A[r][i] / A[i][i]
                for c in range(i, n + 1):
                    A[r][c] -= f * A[i][c]
        d = [0.0] * n
        for i in reversed(range(n)):
            d[i] = (A[i][n] - sum(A[i][k] * d[k] for k in range(i + 1, n))) / A[i][i]
        b = [bi + di for bi, di in zip(b, d)]
        if max(abs(di) for di in d) < 1e-7:
            break
    return b


def fit_season_rates(features, counts, exposure, seasons):
    """Return season intercepts and common slopes. Zero-event seasons have zero fitted rate."""
    season_totals = Counter()
    season_exposure = Counter()
    for season, count, games in zip(seasons, counts, exposure):
        season_totals[season] += count
        season_exposure[season] += games
    fitted = sorted(season for season, count in season_totals.items() if count)
    # Within a season that reports no events, the intercept tends to negative infinity.
    # That season contributes no information about the slopes.
    design, response, games = [], [], []
    for season, x, count, gp in zip(seasons, features, counts, exposure):
        if season_totals[season]:
            design.append([float(season == key) for key in fitted] + x)
            response.append(count)
            games.append(gp)
    initial = [math.log(season_totals[key] / season_exposure[key]) for key in fitted]
    b = poisson_ridge(design, response, games, initial)
    intercepts = dict(zip(fitted, b[:len(fitted)]))
    return {key: intercepts.get(key) for key in sorted(season_totals)}, b[len(fitted):]


def summarize_recovery(recovery):
    """Weighted duration quantiles (41 points) and diagnosis shares by duration band for each part's recovery pool."""
    summary = {}
    for part, pool in recovery.items():
        ordered = sorted(pool, key=lambda r: r["days"])
        total = sum(float(r.get("w") or 1.0) for r in ordered)
        quantiles, cumulative, idx = [], 0.0, 0
        for k in range(41):
            target = total * k / 40.0
            while idx < len(ordered) - 1 and cumulative + float(ordered[idx].get("w") or 1.0) < target:
                cumulative += float(ordered[idx].get("w") or 1.0)
                idx += 1
            quantiles.append(int(ordered[idx]["days"]))
        bands = []
        for limit in (3, 7, 14, 30, 60, 120, 100000):
            shares = Counter()
            for r in ordered:
                if (bands[-1][0] if bands else 0) < r["days"] <= limit:
                    shares[r["label"]] += float(r.get("w") or 1.0)
            top = shares.most_common(12)
            band_total = sum(v for _, v in top) or 1.0
            bands.append([limit, {label: round(v / band_total, 4) for label, v in top}])
        summary[part] = {"quantiles": quantiles, "labels_by_days": bands}
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--model-only", action="store_true", help="leave the local player evidence file alone")
    args = ap.parse_args()
    from nba_gm_data.injury_model import HISTORY_WEIGHT
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.save import trait_values_by_player
    canonical = load_app_canonical(ROOT)
    players = {p["id"]: p for p in canonical["players"]}
    traits = trait_values_by_player(canonical)

    history = rows("injury_player_history.json")
    seasons = rows("injury_player_seasons.json")
    by_player = defaultdict(list)
    for h in history:
        part = part_of(h)
        if part and h.get("player_id") and h.get("start"):
            by_player[h["player_id"]].append((date.fromisoformat(h["start"][:10]), part, h))

    data = []   # (pid, season, gp, features_raw dict, Counter of part injuries)
    for r in seasons:
        pid = r.get("player_id")
        if not pid or pid not in players or r["season"] < FIRST_SEASON or (r.get("gp") or 0) < 10:
            continue
        p, t = players[pid], traits.get(pid, {})
        birth = p.get("birthdate") or p.get("birth_date")
        if not birth:
            continue
        start = season_start(r["season"])
        age = (start - date.fromisoformat(str(birth)[:10])).days / 365.25
        in_season = Counter(part for d, part, _ in by_player[pid]
                            if r["season"] == _["season"])
        prior = defaultdict(float)
        for d, part, _ in by_player[pid]:
            if d < start:
                prior[part] += math.exp(-((start - d).days / 365.25) / HISTORY_DECAY_YEARS)
        pos = str(p.get("position") or "")
        data.append((pid, r["season"], r["gp"], {
            "age": age, "height": float(p.get("height_inches") or 78), "weight": float(p.get("weight_lbs") or 215),
            "poss_pg": (r.get("poss") or 0) / max(1, r["gp"]),
            "rim_pressure": float(t.get("rim_pressure", 50)), "offensive_rebounding": float(t.get("offensive_rebounding", 50)),
            "stamina": float(t.get("stamina_cardio", 50)), "center": 1.0 if "C" in pos else 0.0,
            "guard": 1.0 if pos.startswith(("PG", "SG", "G")) else 0.0,
        }, in_season, prior))

    raw_cols = ["age", "height", "weight", "poss_pg", "rim_pressure", "offensive_rebounding", "stamina"]
    mu = {c: statistics.fmean(d[3][c] for d in data) for c in raw_cols}
    sd = {c: statistics.pstdev(d[3][c] for d in data) or 1.0 for c in raw_cols}

    def featurize(f, prior_same, prior_other):
        z = {c: (f[c] - mu[c]) / sd[c] for c in raw_cols}
        return [z["age"], z["age"] ** 2, z["height"], z["weight"], z["poss_pg"], z["rim_pressure"],
                z["offensive_rebounding"], z["stamina"], f["center"], f["guard"], prior_same, prior_other]

    model = {"version": "injury_model_v2_2026_11_21", "source": "Basketball Index Injury Tracker (data/research/bbi/tools)",
             "first_season": FIRST_SEASON, "player_seasons": len(data), "games": sum(d[2] for d in data),
             "features": FEATURES, "standardization": {"mean": mu, "sd": sd}, "history_decay_years": HISTORY_DECAY_YEARS,
             "parts": {}, "merge": MERGE,
             "rate_fit": {"season_fixed_effects": True, "anchor_seasons": RATE_ANCHOR_SEASONS,
                          "history_weight": HISTORY_WEIGHT}}
    # The complete public records: which stretches are new injuries the tracker lacks (startup history), and which are
    # new in-season injuries and illnesses (the base-rate anchor).
    team_names = {t["abbrev"]: t["name"] for t in canonical["teams"]}
    public = {}
    for season, path in PUBLIC_HISTORIES.items():
        if path.exists():
            stretches, status = classify_public_stretches(history, team_names, path)
            public[season] = (stretches, status, new_in_season(stretches))
    # Injury and illness history as the engine reads it (injury_model.player_history): the tracker plus the public
    # stretches it lacks. The anchor uses the same history a new career starts with.
    engine_history = defaultdict(list)
    for pid, items in by_player.items():
        engine_history[pid].extend((d, part) for d, part, _ in items)
    for stretches, status, _ in public.values():
        for pid, entries in public_history_entries(stretches, status).items():
            engine_history[pid].extend((date.fromisoformat(e[0]), e[1]) for e in entries)

    fit_seasons = [row[1] for row in data]
    exposure = [row[2] for row in data]
    fits = {}
    for part in [*PARTS, "illness"]:
        features, counts = [], []
        for _, season, gp, raw, in_season, prior in data:
            same = prior.get(part, 0.0)
            other = sum(v for k, v in prior.items() if k != part)
            features.append(featurize(raw, same, other))
            counts.append(in_season.get(part, 0))
        season_intercepts, slopes = fit_season_rates(features, counts, exposure, fit_seasons)
        fits[part] = (season_intercepts, slopes, sum(counts))
        print(f"{part:11s} n={sum(counts):5d}  " +
              " ".join(f"{k}={v:+.2f}" for k, v in zip(FEATURES, slopes) if abs(v) >= 0.08))

    # Recovery pools: real absences per part (diagnosis, days, games, surgery), most recent seasons first.
    pools = defaultdict(list)
    for h in history:
        part = part_of(h)
        if part and h["season"] >= FIRST_SEASON and h.get("days"):
            pools[part].append({"label": h.get("label"), "days": int(h["days"]), "games": int(h.get("games") or 0),
                                "surgery": int(h.get("surgery") or 0), "season": h["season"],
                                "censored": int(h.get("censored") or 0)})
    # Injuries: Basketball Index's recorded absences (all players, since RECOVERY_FIRST_YEAR), grouped by body part,
    # labeled with the specific diagnosis where one exists, weighted with its 6-year half-life. An absence without a
    # logged return lasted at least its recorded days: it takes the median of longer returned cases for that part.
    observations = {o["observation_id"]: o for o in rows("injury_observations.json")}
    time_out = rows("injury_time_out.json")
    diagnosis = {}
    for t in time_out:
        if t["level"] == "specific":
            for oid in t["observation_ids"]:
                diagnosis.setdefault(oid, t["bucket"])
    bbi_pools = defaultdict(list)
    for t in time_out:
        if t["level"] != "body_part":
            continue
        part = MERGE.get(t["bucket"], t["bucket"])
        if part not in PARTS:
            continue
        for oid in t["observation_ids"]:
            o = observations.get(oid)
            if o and o.get("days") and int(o.get("start_year") or 0) >= RECOVERY_FIRST_YEAR:
                bbi_pools[part].append(o | {"label": diagnosis.get(oid) or f"{part} injury"})
    recovery = {}
    for part, obs in bbi_pools.items():
        returned = sorted(o["days"] for o in obs if o["return_logged"])
        entries = []
        for o in obs:
            days = int(o["days"])
            if not o["return_logged"]:
                longer = [d for d in returned if d >= days]
                days = int(statistics.median(longer)) if longer else days
            entries.append({"days": days, "label": o["label"], "w": round(0.5 ** (float(o["recency_years"]) / 6.0), 5),
                            "censored": int(not o["return_logged"])})
        recovery[part] = entries
    recovery["illness"] = [{"days": r["days"], "label": r["label"] or "illness", "w": 1.0, "censored": r["censored"]}
                           for r in pools.get("illness", [])]
    for part in PARTS:
        days = sorted(e["days"] for e in recovery.get(part, []))
        if days:
            q = statistics.quantiles(days, n=10)
            print(f"  recovery {part:11s} n={len(days):5d} median={q[4]:5.1f} p90={q[8]:6.1f}")
    # Base rates (INJURY-ANCHOR, 2026-11-21). For each part, one gameplay intercept so the player-seasons of the anchor
    # seasons, with the injury history a new career starts with (the tracker plus the public stretches it lacks, at the
    # engine's history weight), reproduce the complete public count of new in-season injuries that cost a
    # regular-season game. Injuries with no known body part are spread over the parts in proportion. Exposure is the
    # tracker's games played for the game's real players (10+ games), the same player-seasons the slopes are fit on.
    anchor_rows = [row for row in data if row[1] in public]
    anchor_keys = {(row[0], row[1]) for row in anchor_rows}
    target, unknown, new_by_season = Counter(), 0, Counter()
    lengths_by_part = defaultdict(list)
    for season, (stretches, _, new) in public.items():
        lengths = absence_lengths(stretches, new)
        for index, part in new.items():
            if part is not None:
                lengths_by_part[part].append((lengths[index][0], lengths[index][2]))
            if (stretches[index]["player_id"], season) not in anchor_keys:
                continue
            new_by_season[season] += 1
            if part is None:
                unknown += 1
            else:
                target[part] += 1
    known = sum(n for part, n in target.items() if part != "illness")
    unknown_factor = (known + unknown) / known if known else 1.0
    anchor_games = sum(row[2] for row in anchor_rows)

    # Recovery lengths: the tracker's pools, re-weighted to the complete records' mix of absence lengths (all players'
    # new in-season absences in the three seasons; correct_recovery_lengths).
    length_fix = correct_recovery_lengths(recovery, lengths_by_part, target)
    for group, (complete, pool) in sorted(length_fix.items()):
        print(f"  lengths {group:15s} complete 1/2-5/6-10/11-20/21+ " + "/".join(f"{100 * v:.0f}" for v in complete)
              + "  tracker pool " + "/".join(f"{100 * v:.0f}" for v in pool))
    # Committed model = derived numbers only (user decision 2026-11-18: raw Basketball Index data stays off GitHub).
    # Recovery pools become weighted duration quantiles plus diagnosis shares by duration band.
    summary = summarize_recovery(recovery)
    # The engine also draws injuries that cost no game (a one-day absence: 4-14% of draws by part, 19% of illnesses, from
    # the tracker's recovery times), so the expected count is taken over the share of draws that cost a game.
    shares = {part: game_share(summary[part]["quantiles"]) for part in fits if part in summary}

    # The engine adds each injury to the player's history the day it happens, so later games that season carry it.
    # The expected count does the same with the real season: each player-season is split into ANCHOR_SEGMENTS equal
    # stretches of the regular season (games spread evenly), each with the history as of its midpoint, real injuries
    # earlier that season included. Without this the engine counts the season's repeat injuries twice: once in the base
    # rate, once through the history.
    anchor_priors = []
    for pid, season, gp, raw, _, _ in anchor_rows:
        start = season_start(season)
        length = (date(start.year + 1, 4, 14) - start).days
        segments = []
        for k in range(ANCHOR_SEGMENTS):
            on = start + timedelta(days=round(length * (k + 0.5) / ANCHOR_SEGMENTS))
            prior = defaultdict(float)
            for d, part in engine_history.get(pid, []):
                if d < on:
                    prior[part] += math.exp(-((on - d).days / 365.25) / HISTORY_DECAY_YEARS)
            segments.append(prior)
        anchor_priors.append(segments)
    print(f"anchor: {len(anchor_rows)} player-seasons, {anchor_games} games, new in-season injuries and illnesses "
          f"{dict(sorted(new_by_season.items()))}; no body part {unknown} (x{unknown_factor:.3f} on the injury parts)")
    for part, (season_intercepts, slopes, n) in fits.items():
        expected_cost = 0.0
        for (pid, season, gp, raw, _, _), segments in zip(anchor_rows, anchor_priors):
            for prior in segments:
                same = prior.get(part, 0.0)
                other = sum(v for k, v in prior.items() if k != part)
                x = featurize(raw, HISTORY_WEIGHT * same, HISTORY_WEIGHT * other)
                expected_cost += gp / len(segments) * math.exp(sum(b * value for b, value in zip(slopes, x)))
        expected_cost *= shares.get(part, 1.0)
        count = target[part] * (unknown_factor if part != "illness" else 1.0)
        model["parts"][part] = {
            "intercept": math.log(count / expected_cost),
            "coef": dict(zip(FEATURES, slopes)),
            "season_intercepts": season_intercepts,
            "injuries": n,
            "per_1000_games": round(1000 * n / sum(exposure), 3),
            "anchor_per_1000_games": round(1000 * count / anchor_games, 3),
            "game_share": round(shares.get(part, 1.0), 4),
        }
        print(f"  anchor {part:11s} new {count:7.1f} ({1000 * count / anchor_games:5.2f} per 1,000 games), "
              f"share costing a game {shares.get(part, 1.0):.3f}, intercept {math.log(count / expected_cost):+.3f}")
    model["rate_fit"].update({
        "anchor": "complete public records: new in-season injuries and illnesses costing a regular-season game "
                  "(not injury management only, not underway at the team's opener, not a trade split, not a direct "
                  "continuation of another absence); history updated within the season as the engine does",
        "anchor_player_seasons": len(anchor_rows), "anchor_games": anchor_games,
        "anchor_new_injuries": dict(sorted(new_by_season.items())), "anchor_no_body_part": unknown,
        "anchor_segments": ANCHOR_SEGMENTS, "illness_in_history": True,
        "recovery_length_bands": {group: {"complete": complete, "tracker_pool": pool}
                                  for group, (complete, pool) in sorted(length_fix.items())},
    })
    model["recurrence_reference"] = {r["bucket"]: r["risk_ratio"] for r in rows("injury_recurrence.json")
                                     if r.get("level") == "body_part" and r.get("risk_ratio")}
    long_term = [r for r in rows("injury_long_term.json") if (r.get("d_rapm_1y_shrunk_ci") or [0, 0])[1] < 0]
    model["lasting_effects"] = [{k: r.get(k) for k in ("level", "bucket", "region", "n_treated", "d_rapm_1y_shrunk",
                                                       "d_rapm_1y_shrunk_ci", "d_rapm_2y", "d_poss_1y_pct")}
                                for r in long_term]
    model["return_ramp"] = rows("injury_short_term.json")
    # Real players' recent injuries and illnesses (start date, part, days) so a new save starts with their actual history:
    # the same-part and other-part history terms decay over ~1.5 years, so five seasons cover everything that still matters.
    recent = defaultdict(list)
    for h in history:
        part = part_of(h)
        if part and h.get("player_id") and h.get("start") and h["season"] >= "2021-22":
            recent[h["player_id"]].append([h["start"][:10], part, int(h.get("days") or 0), h.get("label")])
    # The tracker misses injuries that cost games (about a fifth in 2023-25, two-thirds in 2025-26), so the public
    # stretches fill in the ones it lacks (STAR-INJURIES for 2025-26; INJURY-ANCHOR for 2023-24 and 2024-25). The slope
    # fit above stays on the tracker alone (each season has its own intercept there).
    public_counts = {}
    for season, (stretches, status, _) in public.items():
        counts = Counter(status.values())
        for pid, entries in public_history_entries(stretches, status).items():
            if pid in players:
                recent[pid].extend(entries)
            else:
                counts["added_but_not_in_player_pool"] += len(entries)
        public_counts[season] = {"source": str(PUBLIC_HISTORIES[season].relative_to(ROOT)),
                                 "stretches": dict(sorted(counts.items()))}
        print(f"public {season} stretches:", dict(sorted(counts.items())))
    model["player_history"] = {pid: sorted(v) for pid, v in sorted(recent.items())}
    # Basketball Index's 2026-27 per-player injury forecast (games missed to injury per 82): the market's view of real
    # players' current proneness, blended into the AI's injury-risk score while it is fresh.
    model["player_forecast_2026_27"] = {r["player_id"]: r["missed_to_injury"] for r in rows("injury_player_projections.json")
                                        if r.get("player_id") and r.get("missed_to_injury") is not None}
    # Real players' recovery speed vs the league for the same injury (Basketball Index, shrunk percent; negative = quicker).
    model["player_recovery_pct"] = {r["player_id"]: r["recovery"]["pct"] for r in rows("injury_players.json")
                                    if r.get("player_id") and (r.get("recovery") or {}).get("pct") is not None
                                    and (r["recovery"].get("trusted") or 0)}
    print("lasting effects (CI below zero):", [(r["level"], r["bucket"], r["d_rapm_1y_shrunk"]) for r in model["lasting_effects"]])
    # Per-player evidence (history, forecasts, recovery speed) goes to a separate git-ignored file the engine merges.
    model["recovery_summary"] = summary
    evidence = {key: model.pop(key) for key in ("player_history", "player_forecast_2026_27", "player_recovery_pct")}
    evidence["version"] = model["version"]
    evidence["public_history"] = public_counts
    if args.write:
        OUT.write_text(json.dumps(model, separators=(",", ":")) + "\n")
        print("wrote", OUT, f"{OUT.stat().st_size/1e6:.2f} MB")
        if not args.model_only:
            EVIDENCE_OUT.write_text(json.dumps(evidence, separators=(",", ":")) + "\n")
            print("wrote local-only", EVIDENCE_OUT.name, f"{EVIDENCE_OUT.stat().st_size/1e6:.2f} MB")


if __name__ == "__main__":
    main()
