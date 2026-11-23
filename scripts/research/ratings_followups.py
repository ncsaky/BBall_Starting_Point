#!/usr/bin/env python3
"""RATINGS-FOLLOWUPS (2026-11-22): evidence for the five follow-ups of RATINGS-AUDIT-GSW.

Research only; the builder (scripts/build_player_inputs.py) reads the JSON files this writes.

    PYTHONPATH=src .venv/bin/python scripts/research/ratings_followups.py thin      # thin-sample players' level
    PYTHONPATH=src .venv/bin/python scripts/research/ratings_followups.py injury    # return from a major injury
    PYTHONPATH=src .venv/bin/python scripts/research/ratings_followups.py value     # value formula misses
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/research"))
from ratings_audit_gsw import LEBRON_CSV, norm  # noqa: E402

SEASON_WEIGHTS = (1.0, 0.7, 0.45)   # the builder's weights for the last, second-last and third-last season
THIN_MAX = 1000.0                   # recent NBA minutes below this count as a thin sample
OUTCOME_MINUTES = 250.0             # a season counts as measured with this many minutes (as the audit)
THIN_OUT = ROOT / "data/research/thin_sample_level_2026_27.json"


def panel():
    data = json.loads((ROOT / "data/research/development_evidence.json").read_text())["public_inputs"]
    minutes, ages, first = {}, {}, {}
    for year, _, name, age, mp, _, _ in data["seasons"]:
        if mp is None:
            continue
        key = (norm(name), int(year))
        minutes[key] = minutes.get(key, 0.0) + float(mp)
        if age is not None:
            ages[key] = float(age)
        if float(mp) > 0:
            first[norm(name)] = min(first.get(norm(name), 9999), int(year))
    pick = {}
    for year, number, _, name in data["draft"]:
        if number is not None:
            pick[norm(name)] = int(number)
    return minutes, ages, first, pick


def years_in_league(name: str, s: int, minutes, ages, first) -> int:
    """Seasons since his first NBA minutes, counting only seasons whose age fits his (not a father of the same name)."""
    age_s = ages.get((name, s))
    if age_s is None:
        return s - first.get(name, s)
    own = [y for y in range(first.get(name, s), s + 1) if minutes.get((name, y), 0.0) > 0
           and (ages.get((name, y)) is None or abs(ages[(name, y)] - (age_s - (s - y))) <= 1.5)]
    return s - min(own, default=s)


def lebron_rows() -> dict[str, dict[int, tuple[float, float]]]:
    rows: dict[str, dict[int, tuple[float, float]]] = {}
    with LEBRON_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.setdefault(norm(row["Player"]), {})[int(row["Season"])] = (float(row["O-LEBRON"]), float(row["D-LEBRON"]))
    return rows


def experience_band(years: int) -> str:
    return "1-2" if years <= 2 else "3-4" if years <= 4 else "5+"


def thin_cases():
    """Every player-season s (2011-2026, 250+ minutes) whose three seasons before s hold 1-999 NBA minutes."""
    minutes, ages, first, pick = panel()
    leb = lebron_rows()
    cases = []
    for name, seasons in leb.items():
        for s, outcome in seasons.items():
            if s < 2011 or minutes.get((name, s), 0.0) < OUTCOME_MINUTES:
                continue
            window = [(k, minutes.get((name, s - k), 0.0)) for k in (1, 2, 3)]
            total = sum(m for _, m in window)
            if not 0 < total < THIN_MAX:
                continue
            parts = [(seasons[s - k], SEASON_WEIGHTS[k - 1] * m) for k, m in window if m > 0 and (s - k) in seasons]
            if not parts:
                continue
            weight = sum(w for _, w in parts)
            own = tuple(sum(v[i] * w for v, w in parts) / weight for i in (0, 1))
            years = years_in_league(name, s, minutes, ages, first)
            cases.append({"name": name, "season": s, "age": ages.get((name, s)), "years": years,
                          "first_round": (pick.get(name) or 99) <= 30, "minutes": total, "own": own, "outcome": outcome})
    return cases


def _group_key(case, scheme):
    if scheme == "minutes":
        return "all"
    if scheme == "experience":
        return experience_band(case["years"])
    if scheme == "experience_draft":
        return experience_band(case["years"]) + ("/first-round" if case["first_round"] else "/other")
    if scheme == "age":
        a = case["age"] or 26
        return "<=23" if a <= 23 else "24-27" if a <= 27 else "28+"
    raise ValueError(scheme)


def _fit(cases, scheme, k):
    """Group means of outcome and own number, then outcome = mean + m/(m+k) x (own - group own mean)."""
    groups = {}
    for c in cases:
        groups.setdefault(_group_key(c, scheme), []).append(c)
    out = {}
    for g, rows in groups.items():
        out[g] = {"n": len(rows),
                  "level": [statistics.fmean(r["outcome"][i] for r in rows) for i in (0, 1)],
                  "own_mean": [statistics.fmean(r["own"][i] for r in rows) for i in (0, 1)]}
    return out


def _predict(model, case, scheme, k):
    g = model[_group_key(case, scheme)]
    w = case["minutes"] / (case["minutes"] + k) if k is not None else 0.0
    return tuple(g["level"][i] + w * (case["own"][i] - g["own_mean"][i]) for i in (0, 1))


def cross_validate(cases, scheme, k):
    """Leave-one-season-out squared error (offense + defense) of the scheme's prediction."""
    err = n = 0.0
    for s in sorted({c["season"] for c in cases}):
        train = [c for c in cases if c["season"] != s]
        test = [c for c in cases if c["season"] == s]
        model = _fit(train, scheme, k)
        for c in test:
            if _group_key(c, scheme) not in model:
                continue
            p = _predict(model, c, scheme, k)
            err += sum((c["outcome"][i] - p[i]) ** 2 for i in (0, 1))
            n += 1
    return err / n


def played_next_season() -> dict:
    """Of players whose last three seasons hold 1-999 NBA minutes (window ending in a season they played), the share
    who play any / 250+ minutes the next season, and their measured level in the window (all of them), by experience."""
    minutes, ages, first, _ = panel()
    leb = lebron_rows()
    groups: dict[str, list] = {}
    for name, seasons in leb.items():
        for t in seasons:
            s = t + 1
            if not 2011 <= s <= 2026 or minutes.get((name, t), 0.0) <= 0:
                continue
            window = [(k, minutes.get((name, s - k), 0.0)) for k in (1, 2, 3)]
            if not 0 < sum(m for _, m in window) < THIN_MAX:
                continue
            parts = [(seasons[s - k], SEASON_WEIGHTS[k - 1] * m) for k, m in window if m > 0 and (s - k) in seasons]
            weight = sum(w for _, w in parts)
            own = sum((v[0] + v[1]) * w for v, w in parts) / weight
            groups.setdefault(experience_band(years_in_league(name, s, minutes, ages, first)), []).append((minutes.get((name, s), 0.0), own))
    return {g: {"windows": len(v), "played_any": round(sum(1 for m, _ in v if m > 0) / len(v), 3),
                "played_250": round(sum(1 for m, _ in v if m >= OUTCOME_MINUTES) / len(v), 3),
                "measured_level_all": round(statistics.fmean(o for _, o in v), 3)} for g, v in sorted(groups.items())}


def thin() -> dict:
    """Real level of thin-sample players (1-999 NBA minutes in the three seasons before), by years in the league.

    Cases: every player-season s (2011-2026) with 250+ minutes whose three seasons before s hold 1-999 NBA minutes
    (Basketball Reference). Own number = his Basketball Index LEBRON over those seasons, weighted by minutes and the
    builder's season weights (1 / 0.7 / 0.45). Forecast of his LEBRON in s = his group's level in s + m/(m+k) x (own
    number - his group's mean own number), m = his minutes. k and the grouping are chosen by leave-one-season-out
    cross-validation (squared error, offense + defense); groupings tested: one pooled group, years since his first NBA
    minutes (1-2, 3-4, 5+), age, years x draft round. Each group's age change is recorded so the builder can use the
    player's own age.
    Survivors only: players who did not reach 250 minutes in s are missing (see played_next_season), so the levels are
    an upper bound, as for the no-track-record level.
    """
    cases = thin_cases()
    ks = [100, 150, 200, 250, 300, 350, 400, 500, 700, 1000, 2000]
    results = {}
    own_only = sum(sum((c["outcome"][i] - c["own"][i]) ** 2 for i in (0, 1)) for c in cases) / len(cases)
    results["own number only (no pull)"] = round(own_only, 4)
    best_k = {}
    for scheme in ("minutes", "experience", "age", "experience_draft"):
        results[scheme + " groups, group level only"] = round(cross_validate(cases, scheme, None), 4)
        best = min(ks, key=lambda k: cross_validate(cases, scheme, k))
        results[scheme + f" groups, own number weighted m/(m+{best})"] = round(cross_validate(cases, scheme, best), 4)
        best_k[scheme] = best
    # The grouping with the smallest cross-validated error (ties go to the simplest, one pooled group). Years in the
    # league were tested because a veteran who rarely plays may be worse than a young player who rarely plays.
    errors = {sc: cross_validate(cases, sc, best_k[sc]) for sc in ("minutes", "experience", "age", "experience_draft")}
    scheme = min(errors, key=lambda sc: (round(errors[sc], 3), sc != "minutes"))
    k = best_k[scheme]
    by_experience = _fit(cases, "experience", best_k["experience"])
    model = _fit(cases, scheme, k)
    groups = {g: {"n": v["n"], "offense": round(v["level"][0], 3), "defense": round(v["level"][1], 3),
                  "own_mean_offense": round(v["own_mean"][0], 3), "own_mean_defense": round(v["own_mean"][1], 3)}
              for g, v in sorted(model.items())}
    # The age change already inside each group's level (the age curve's change from the measured seasons to the next
    # season, averaged over the group's cases), so a player far older or younger than his group's typical case is
    # moved by the difference (the builder adds his own age's change and takes this off).
    lag, _ = _curve()
    for g in groups:
        rows = [c for c in cases if _group_key(c, scheme) == g]
        for side in ("offense", "defense"):
            groups[g]["mean_case_lag_" + side] = round(statistics.fmean(lag(side, c["age"] or 26) for c in rows), 4)
        groups[g]["mean_age"] = round(statistics.fmean(c["age"] or 26 for c in rows), 2)
    return {"version": "thin_sample_level_v1_2026_11_22", "method": " ".join(thin.__doc__.split()),
            "sources": ["Basketball Index LEBRON by season 2010-2026 (fanspo tools capture, local)",
                        "Basketball Reference minutes, ages and draft (data/research/development_evidence.json)"],
            "thin_max_minutes": THIN_MAX, "cases": len(cases), "grouping": scheme,
            "experience_groups_tested": {g: {"n": v["n"], "offense": round(v["level"][0], 3),
                                             "defense": round(v["level"][1], 3)} for g, v in sorted(by_experience.items())},
            "minutes_k": k, "groups": groups, "cv_mean_squared_error": results,
            "played_next_season": played_next_season()}


# ---------------------------------------------------------------------------------------------------------------------
# Step 2: return from a major injury (Achilles tendon rupture, ACL tear).
#
# Cases: every NBA Achilles rupture or ACL tear 2010-2025 the repo's Basketball Index injury data names (Injury Tracker
# capture: data/research/bbi/tools/injury_player_history.json for today's players, injury_examples.json for its listed
# historical cases), plus widely reported cases of the same years (season of injury from public injury reports). Each is
# checked against Basketball Reference minutes (a long absence right after). Left out: injuries before 2010 (no LEBRON),
# players with no NBA level before the injury (rookies, under 250 minutes in the three seasons before), and Klay
# Thompson (ACL then Achilles back to back, no separate first season back).
# season = the season (end year) in which he got hurt, or the last season he played before an offseason injury.
INJURY_CASES = [
    # name, injury, season, source
    ("Mehmet Okur", "achilles", 2010, "bbi_examples"), ("Chauncey Billups", "achilles", 2012, "bbi_examples"),
    ("Kobe Bryant", "achilles", 2013, "bbi_examples"), ("Anderson Varejao", "achilles", 2015, "bbi_examples"),
    ("Brandon Jennings", "achilles", 2015, "bbi_examples"), ("Wesley Matthews", "achilles", 2015, "public"),
    ("Rudy Gay", "achilles", 2017, "public"), ("DeMarcus Cousins", "achilles", 2018, "bbi_examples"),
    ("Kevin Durant", "achilles", 2019, "bbi_history"), ("John Wall", "achilles", 2019, "public"),
    ("Rodney Hood", "achilles", 2020, "public"), ("Dwight Powell", "achilles", 2020, "bbi_history"),
    ("Brandon Clarke", "achilles", 2023, "bbi_history"), ("Dejounte Murray", "achilles", 2025, "bbi_history"),
    ("Isaiah Jackson", "achilles", 2025, "bbi_history"), ("Dru Smith", "achilles", 2025, "bbi_history"),
    ("James Wiseman", "achilles", 2025, "bbi_history"), ("Jayson Tatum", "achilles", 2025, "bbi_history"),
    ("Tyrese Haliburton", "achilles", 2025, "bbi_history"), ("Damian Lillard", "achilles", 2025, "bbi_history"),
    ("Donte DiVincenzo", "achilles", 2026, "bbi_history"),
    ("Danilo Gallinari", "acl", 2013, "public"), ("Danilo Gallinari", "acl", 2022, "public"),
    ("Ricky Rubio", "acl", 2012, "public"), ("Ricky Rubio", "acl", 2022, "public"),
    ("Derrick Rose", "acl", 2012, "public"), ("Rajon Rondo", "acl", 2013, "public"),
    ("Iman Shumpert", "acl", 2012, "public"), ("Lou Williams", "acl", 2013, "public"),
    ("Tony Wroten", "acl", 2015, "public"), ("Jabari Parker", "acl", 2015, "public"),
    ("Jabari Parker", "acl", 2017, "public"), ("Zach LaVine", "acl", 2017, "bbi_examples"),
    ("Brandon Knight", "acl", 2017, "public"), ("Kristaps Porzingis", "acl", 2018, "bbi_history"),
    ("Dejounte Murray", "acl", 2018, "bbi_history"), ("DeMarcus Cousins", "acl", 2019, "bbi_examples"),
    ("Jeremy Lamb", "acl", 2020, "bbi_examples"), ("Jonathan Isaac", "acl", 2020, "bbi_examples"),
    ("Spencer Dinwiddie", "acl", 2021, "bbi_examples"), ("Jamal Murray", "acl", 2021, "bbi_examples"),
    ("Thomas Bryant", "acl", 2021, "bbi_examples"), ("Markelle Fultz", "acl", 2021, "bbi_examples"),
    ("Kawhi Leonard", "acl", 2021, "public"), ("Dario Saric", "acl", 2021, "bbi_history"),
    ("Joe Ingles", "acl", 2022, "bbi_examples"), ("Saddiq Bey", "acl", 2024, "bbi_history"),
    ("Moritz Wagner", "acl", 2025, "bbi_examples"), ("Grant Williams", "acl", 2025, "bbi_examples"),
    ("Kyrie Irving", "acl", 2025, "bbi_history"), ("Fred VanVleet", "acl", 2025, "bbi_history"),
    ("Jimmy Butler", "acl", 2026, "bbi_history"),
]
# Today's players whose Achilles rupture or ACL tear came in 2023-24 or later (their first season back is not, or only
# partly, in the measured seasons). Sources: Basketball Index Injury Tracker capture (bbi_history, bbi_examples), the
# NBA's official 2025-26 injury reports (data/research/injury_history_2025_26.json, nba_reports). season as in
# INJURY_CASES.
CURRENT_INJURED = [
    {"player": "Damian Lillard", "injury": "achilles", "season": 2025, "sources": ["bbi_history", "nba_reports"]},
    {"player": "Tyrese Haliburton", "injury": "achilles", "season": 2025, "sources": ["bbi_history", "nba_reports"]},
    {"player": "Jayson Tatum", "injury": "achilles", "season": 2025, "sources": ["bbi_history", "nba_reports"]},
    {"player": "Dejounte Murray", "injury": "achilles", "season": 2025, "sources": ["bbi_history", "nba_reports"]},
    {"player": "Donte DiVincenzo", "injury": "achilles", "season": 2026, "sources": ["bbi_history", "nba_reports"]},
    {"player": "Isaiah Jackson", "injury": "achilles", "season": 2025, "sources": ["bbi_history"]},
    {"player": "Dru Smith", "injury": "achilles", "season": 2025, "sources": ["bbi_history"]},
    {"player": "James Wiseman", "injury": "achilles", "season": 2025, "sources": ["bbi_history"]},
    {"player": "Kyrie Irving", "injury": "acl", "season": 2025, "sources": ["bbi_history"]},
    {"player": "Fred VanVleet", "injury": "acl", "season": 2025, "sources": ["bbi_history", "nba_reports"]},
    {"player": "Jimmy Butler", "injury": "acl", "season": 2026, "sources": ["nba_reports"]},
    {"player": "De'Anthony Melton", "injury": "acl", "season": 2025, "sources": ["nba_reports"]},
    {"player": "Grant Williams", "injury": "acl", "season": 2025, "sources": ["bbi_history", "nba_reports"]},
    {"player": "Moritz Wagner", "injury": "acl", "season": 2025, "sources": ["bbi_examples", "nba_reports"]},
    {"player": "Saddiq Bey", "injury": "acl", "season": 2024, "sources": ["bbi_history"]},
    {"player": "Johnny Furphy", "injury": "acl", "season": 2026, "sources": ["nba_reports"]},
    {"player": "N'Faly Dante", "injury": "acl", "season": 2026, "sources": ["nba_reports"]},
    {"player": "Jamir Watkins", "injury": "acl", "season": 2026, "sources": ["bbi_history"]},
]
INJURY_OUT = ROOT / "data/research/major_injury_return_2026_27.json"
AGE_CURVE = ROOT / "data/research/age_projection_2026_27.json"
INJURY_AGE_SPLIT = 30          # age at injury: under 30 / 30 and over (the user's "in their 30s")


def _curve():
    c = json.loads(AGE_CURVE.read_text())
    lo, hi = min(int(a) for a in c["annual"]["offense"]), max(int(a) for a in c["annual"]["offense"])

    def at(table, side, age):
        return table[side][str(min(max(int(round(age)), lo), hi))]
    # lag(a): the measured three-season blend to the next season's average, at the age then (shift = lag - annual/2)
    lag = lambda side, age: at(c["shift"], side, age) + 0.5 * at(c["annual"], side, age)
    annual = lambda side, age: at(c["annual"], side, age)
    return lag, annual


def injury_cases() -> list[dict]:
    """Each case: level before (the builder's three-season blend through the injury season), the first season back
    (first later season with 250+ minutes, within three seasons), what his age alone predicts for that season (the age
    curve of the age step), and the difference (the injury's cost beyond age)."""
    minutes, ages, _, _ = panel()
    leb = lebron_rows()
    lag, annual = _curve()
    out = []
    for name, injury, s0, source in INJURY_CASES:
        key = norm(name)
        seasons = leb.get(key, {})
        age0 = ages.get((key, s0)) or next((ages[(key, s0 - k)] + k for k in (1, 2) if (key, s0 - k) in ages), None)
        parts = [(seasons[s0 - k], SEASON_WEIGHTS[k] * min(minutes.get((key, s0 - k), 0.0), 2500.0))
                 for k in range(3) if (s0 - k) in seasons and minutes.get((key, s0 - k), 0.0) >= OUTCOME_MINUTES]
        case = {"player": name, "injury": injury, "season": s0, "age": age0, "source": source}
        if not parts or age0 is None:
            case["status"] = "no measured level before"
            out.append(case)
            continue
        level = [sum(v[i] * w for v, w in parts) / sum(w for _, w in parts) for i in (0, 1)]
        back = next((s for s in range(s0 + 1, s0 + 4) if minutes.get((key, s), 0.0) >= OUTCOME_MINUTES and s in seasons),
                    None)
        case.update({"level_before": [round(x, 3) for x in level]})
        if back is None:
            case["status"] = "not back yet" if s0 + 1 >= 2026 else "no 250-minute season within three seasons"
            out.append(case)
            continue
        expected = []
        for i, side in enumerate(("offense", "defense")):
            e = level[i] + lag(side, age0 + 1)
            for s in range(s0 + 2, back + 1):
                e += annual(side, age0 + (s - s0))
            expected.append(e)
        actual = seasons[back]
        case.update({"status": "back", "season_back": back, "seasons_missed": back - s0 - 1,
                     "minutes_back": minutes.get((key, back)), "expected_back": [round(x, 3) for x in expected],
                     "actual_back": list(actual),
                     "cost": [round(actual[i] - expected[i], 3) for i in (0, 1)]})
        out.append(case)
    return out


def injury_return() -> dict:
    """Cost of an Achilles rupture or ACL tear in the first season back, beyond age, by injury and age at injury.

    Cost = real LEBRON in the first season back (250+ minutes) minus what his measured level before the injury and the
    age curve predict for that season (data/research/age_projection_2026_27.json: the same change the age step gives
    every veteran, missed seasons included). Groups: injury x age at injury (under 30 / 30+), means unweighted, with a
    standard error. Survivors only: players who never got back to 250 minutes are counted apart (return share), so the
    cost is if anything understated. Basketball Index's own matched estimate (injury_long_term.json, all ages, matched
    controls) is reported alongside as a check.
    """
    cases = injury_cases()
    groups = {}
    for injury in ("achilles", "acl"):
        for band, test in (("under 30", lambda a: a < INJURY_AGE_SPLIT), ("30+", lambda a: a >= INJURY_AGE_SPLIT)):
            sel = [c for c in cases if c["injury"] == injury and c.get("age") is not None and test(c["age"])
                   and c["status"] in ("back", "no 250-minute season within three seasons")]
            back = [c for c in sel if c["status"] == "back"]
            g = {"cases": len(sel), "back": len(back), "return_share": round(len(back) / len(sel), 3) if sel else None}
            for i, side in enumerate(("offense", "defense")):
                xs = [c["cost"][i] for c in back]
                if xs:
                    g["cost_" + side] = round(statistics.fmean(xs), 3)
                    g["se_" + side] = round(statistics.stdev(xs) / math.sqrt(len(xs)), 3) if len(xs) > 1 else None
            totals = [c["cost"][0] + c["cost"][1] for c in back]
            if totals:
                g["cost_total"] = round(statistics.fmean(totals), 3)
                g["se_total"] = round(statistics.stdev(totals) / math.sqrt(len(totals)), 3) if len(totals) > 1 else None
            groups[f"{injury} {band}"] = g
    # Partial pooling: each group's cost is pulled toward the pooled cost by how much the groups really differ
    # (between-group variance above what their standard errors explain; zero means the split is noise).
    applied = {}
    back_all = [c for c in cases if c["status"] == "back"]
    for i, side in enumerate(("offense", "defense")):
        pooled = statistics.fmean(c["cost"][i] for c in back_all)
        means = [(g["cost_" + side], g["se_" + side]) for g in groups.values() if g.get("se_" + side)]
        tau2 = max(0.0, statistics.pvariance([m for m, _ in means]) - statistics.fmean(se ** 2 for _, se in means))
        applied.setdefault("pooled", {})[side] = round(pooled, 3)
        applied.setdefault("between_group_variance", {})[side] = round(tau2, 4)
        for name, g in groups.items():
            se = g.get("se_" + side)
            w = tau2 / (tau2 + se ** 2) if se and tau2 > 0 else 0.0
            applied.setdefault(name, {})[side] = round(w * g["cost_" + side] + (1 - w) * pooled, 3)
    applied["cases_back"] = len(back_all)
    bbi = {}
    path = ROOT / "data/research/bbi/tools/injury_long_term.json"
    if path.exists():
        for r in json.loads(path.read_text()):
            if r["level"] == "specific" and r["bucket"] in ("Achilles tendon rupture", "ACL tear"):
                bbi[r["bucket"]] = {k: r.get(k) for k in ("n_treated", "returned_rate", "d_rapm_1y", "d_rapm_1y_shrunk",
                                                            "d_rapm_1y_shrunk_ci")}
    return {"version": "major_injury_return_v1_2026_11_22", "method": " ".join(injury_return.__doc__.split()),
            "sources": ["Basketball Index LEBRON by season 2010-2026 (fanspo tools capture, local)",
                        "Basketball Index Injury Tracker (data/research/bbi/tools: injury_player_history, "
                        "injury_examples, injury_long_term)",
                        "public injury reports for the season of injury (cases marked 'public')",
                        "Basketball Reference minutes and ages (data/research/development_evidence.json)"],
            "age_split": INJURY_AGE_SPLIT, "groups": groups, "applied_cost": applied,
            "basketball_index_matched_estimate": bbi, "current_players": CURRENT_INJURED, "cases": cases}


# ---------------------------------------------------------------------------------------------------------------------
# Step 3: why the game ranks high-usage scorers below analysts (value formula diagnostics).
SCORERS = ["Jalen Brunson", "Jaylen Brown", "Trae Young", "Paolo Banchero", "Alperen Sengun", "Julius Randle",
           "Keyonte George", "Michael Porter Jr.", "Shai Gilgeous-Alexander", "Luka Dončić", "Anthony Edwards",
           "Devin Booker", "Tyrese Maxey", "Donovan Mitchell", "De'Aaron Fox", "Zach LaVine", "DeMar DeRozan",
           "Cade Cunningham", "LaMelo Ball", "Jamal Murray"]
BIGS = ["Donovan Clingan", "Isaiah Hartenstein", "Jarrett Allen", "Walker Kessler", "Onyeka Okongwu", "Rudy Gobert",
        "Victor Wembanyama", "Chet Holmgren", "Evan Mobley"]


def value_rows(replay: bool = True):
    """Fit-sample rows as scripts/fit_impact_value.py builds them, with the current fit's prediction."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import fit_impact_value as fiv
    from nba_gm_data import bbi_evidence as be
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.impact_value import PREDICTORS, load_fit, predictor_row
    from nba_gm_data.offense import offensive_profile
    from nba_gm_data.ratings_model import effective_inputs, install_inputs_model
    from nba_gm_data.save import trait_values_by_player
    canonical = load_app_canonical(ROOT)
    install_inputs_model(canonical, ROOT, replay_last_season=replay)
    traits = trait_values_by_player(canonical)
    players = {p["id"]: p for p in canonical["players"]}
    table = be.collect_values(ROOT, set(fiv.TARGETS.values()))
    analyst = fiv.analyst_ranks(players.values())
    rows = []
    for pid, player in players.items():
        if pid not in traits or (player.get("draft_year") or 0) >= fiv.ROOKIE_DRAFT_YEAR:
            continue
        values, minutes = {}, 0.0
        for side, metric in fiv.TARGETS.items():
            cell = table.get((fiv.SEASON, metric), {}).get(pid)
            if cell:
                values[side] = cell[0]
                minutes = max(minutes, cell[1])
        if len(values) == 2 and minutes >= 200:
            profile = offensive_profile(canonical, player, traits[pid])
            rows.append((pid, player["name"], predictor_row(traits[pid], player, profile, effective_inputs(canonical, pid)),
                         values, minutes, float(player.get("age") or 27.0)))
    targets, _ = fiv.blended_targets(rows, analyst, fiv.ANALYST_WEIGHT)
    fit = load_fit(ROOT)
    out = []
    for r, t in zip(rows, targets):
        parts = {}
        for side in ("offense", "defense"):
            c = fit["coefficients"][side]
            parts[side] = {name: w * (v - m) / s for name, w, v, m, s in zip(PREDICTORS, c["weights"], r[2], c["mean"], c["sd"])}
        pred = {side: fit["coefficients"][side]["intercept"] + sum(parts[side].values()) for side in parts}
        out.append({"id": r[0], "name": r[1], "x": dict(zip(PREDICTORS, r[2])), "real": r[3], "minutes": r[4],
                    "target": {"offense": t[0], "defense": t[1]}, "note": t[2], "pred": pred, "parts": parts,
                    "analyst": analyst.get(r[0])})
    return out


def _wmean(pairs):
    sw = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / sw if sw else float("nan")


def value_diagnose(replay: bool = True) -> None:
    rows = value_rows(replay)
    w = lambda r: r["minutes"] / (r["minutes"] + 800.0)
    print(f"{len(rows)} fit players; misses are real/target minus the game's prediction (per 100 possessions)")
    for key in ("in_involvement", "in_creation", "in_shooting", "in_finishing"):
        xs = sorted(rows, key=lambda r: r["x"][key])
        print(f"\nBy {key} (fifths, low to high): offense miss vs LEBRON | vs target ; defense miss vs LEBRON | vs target")
        for q in range(5):
            sel = xs[q * len(xs) // 5:(q + 1) * len(xs) // 5]
            o_l = _wmean([(r["real"]["offense"] - r["pred"]["offense"], w(r)) for r in sel])
            o_t = _wmean([(r["target"]["offense"] - r["pred"]["offense"], w(r)) for r in sel])
            d_l = _wmean([(r["real"]["defense"] - r["pred"]["defense"], w(r)) for r in sel])
            d_t = _wmean([(r["target"]["defense"] - r["pred"]["defense"], w(r)) for r in sel])
            print(f"  {q + 1}: {key} {sel[0]['x'][key]:.3f}-{sel[-1]['x'][key]:.3f}  offense {o_l:+.2f} | {o_t:+.2f}"
                  f"   defense {d_l:+.2f} | {d_t:+.2f}")
    print("\nNamed players: real multi-year LEBRON (off/def), fit target, game prediction, analyst rank")
    by = {norm(r["name"]): r for r in rows}
    for name in SCORERS + BIGS:
        r = by.get(norm(name))
        if not r:
            continue
        print(f"  {name:24s} real {r['real']['offense']:+.2f}/{r['real']['defense']:+.2f}  target "
              f"{r['target']['offense']:+.2f}/{r['target']['defense']:+.2f}  game {r['pred']['offense']:+.2f}/"
              f"{r['pred']['defense']:+.2f}  analyst {r['analyst'] or '-'}  T08 {r['x']['in_involvement']:.3f}")
    for name in ("Jalen Brunson", "Jaylen Brown", "Trae Young", "Paolo Banchero", "Alperen Sengun", "Donovan Clingan"):
        r = by.get(norm(name))
        if not r:
            continue
        top = sorted(r["parts"]["offense"].items(), key=lambda kv: -abs(kv[1]))[:10]
        print(f"\n{name} offense parts: " + ", ".join(f"{k} {v:+.2f} (x={r['x'][k]:.2f})" for k, v in top))
        top = sorted(r["parts"]["defense"].items(), key=lambda kv: -abs(kv[1]))[:6]
        print(f"{name} defense parts: " + ", ".join(f"{k} {v:+.2f} (x={r['x'][k]:.2f})" for k, v in top))


# ---------------------------------------------------------------------------------------------------------------------
# Step 4: aging of physical tools.
PHYSICAL_METRICS = ("Avg Speed Offense", "Avg Speed Defense")
PHYSICAL_OUT = ROOT / "data/research/physical_aging_2026_27.json"


def _bbi_history(metrics) -> dict[tuple[str, int], dict[str, tuple[float, float]]]:
    """(name, season end year) -> {metric: (value, minutes)} from every Basketball Index Leaderboards Values capture."""
    from nba_gm_data.bbi_evidence import CACHE_DIR, _values_batches
    from nba_gm_data.bbi_import import iter_records
    folder = ROOT / CACHE_DIR
    index = json.loads((folder / "normalized.json").read_text())
    keep = _values_batches(index)
    out: dict[tuple[str, int], dict[str, tuple[float, float]]] = {}
    for row in iter_records(index, folder):
        if row.get("batch_id") not in keep or row.get("metric_name") not in metrics:
            continue
        value = row.get("raw_value")
        season = str(row.get("season") or "")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or len(season) < 7:
            continue
        year = int(season[:4]) + 1
        out.setdefault((norm(row.get("player_name_raw") or ""), year), {})[row["metric_name"]] = (
            float(value), float(row.get("minutes") or 0.0))
    return out


AGE_BANDS = ((20, 23), (24, 26), (27, 29), (30, 32), (33, 35), (36, 41))


def athletic_markers() -> dict:
    """Within-player change per season of athletic box-score markers, by age band (players with 1,000+ minutes in both
    seasons): blocks, steals and rebounds per minute (ESPN career stats of today's players, data/research/
    player_career_stats.json) and the share of shots within 3 feet that are dunks (Basketball Reference, 2023-24 to
    2025-26, 60+ close attempts). Per cent change per season for the rates; league standard deviations for the dunk
    share (log-odds). These also reflect role, so they bound athletic decline from above at ages where roles shrink."""
    _, ages, _, _ = panel()
    out = {}
    d = json.loads((ROOT / "data/research/player_career_stats.json").read_text())["players"]
    res: dict[str, dict[int, list[float]]] = {}
    for p in d.values():
        ss = {int(s["season"][:4]) + 1: s for s in p["seasons"] if s.get("minutes")}
        for y, s in ss.items():
            a, age = ss.get(y - 1), ages.get((norm(p["name"]), y))
            if not a or age is None or s["minutes"] < 1000 or a["minutes"] < 1000:
                continue
            for stat in ("blocks", "steals", "rebounds"):
                change = math.log(((s[stat] or 0) + 1) / s["minutes"]) - math.log(((a[stat] or 0) + 1) / a["minutes"])
                res.setdefault(stat, {}).setdefault(int(age), []).append(change)
    shooting = json.loads((ROOT / "data/research/bref_shooting_2024_2026.json").read_text())["players"]

    def dunk_logit(row):
        try:
            close = row["fga"] * row["pct_fga_00_03"]
            if row["minutes"] < 1000 or close < 60:
                return None
            return math.log((row["dunks"] + 0.5) / (close - row["dunks"] + 0.5))
        except (KeyError, TypeError):
            return None
    latest = [x for x in (dunk_logit(p["seasons"].get("2025-26", {})) for p in shooting.values()) if x is not None]
    sd = statistics.pstdev(latest)
    for p in shooting.values():
        for before, after, year in (("2023-24", "2024-25", 2025), ("2024-25", "2025-26", 2026)):
            x0, x1 = dunk_logit(p["seasons"].get(before, {})), dunk_logit(p["seasons"].get(after, {}))
            age = ages.get((norm(p["name"]), year))
            if x0 is not None and x1 is not None and age is not None:
                res.setdefault("dunk_share_sd", {}).setdefault(int(age), []).append((x1 - x0) / sd)
    for stat, by in res.items():
        bands = {}
        for lo, hi in AGE_BANDS:
            v = [x for a in range(lo, hi + 1) for x in by.get(a, [])]
            if len(v) > 1:
                scale = 1.0 if stat == "dunk_share_sd" else 100.0
                bands[f"{lo}-{hi}"] = {"n": len(v), "change": round(scale * statistics.fmean(v), 3),
                                       "se": round(scale * statistics.stdev(v) / math.sqrt(len(v)), 3)}
        out[stat if stat == "dunk_share_sd" else stat + "_per_minute_pct"] = bands
    return out


def physical_aging() -> dict:
    """Real change of Basketball Index's tracked movement speed by age (within the same player, season to season).

    Players with 1,000+ minutes in both seasons (2013-14 to 2025-26), change in Avg Speed Offense and Avg Speed Defense
    (miles per hour of tracked movement) divided by the league's between-player spread that season, so the change is in
    league standard deviations per year. Age = age in the later season (Basketball Reference). Smoothed across ages
    (Gaussian, 1.5 years). Average speed also reflects role, pace and effort (Basketball Index's own caveat), so this
    is an upper bound on pure athletic decline at ages where roles shrink. Survivors only.
    """
    hist = _bbi_history(set(PHYSICAL_METRICS))
    _, ages, _, _ = panel()
    spread = {}
    for metric in PHYSICAL_METRICS:
        by_year: dict[int, list[float]] = {}
        for (name, year), cells in hist.items():
            if metric in cells and cells[metric][1] >= 1000:
                by_year.setdefault(year, []).append(cells[metric][0])
        spread[metric] = {y: statistics.pstdev(v) for y, v in by_year.items() if len(v) > 30}
    changes: dict[int, list[float]] = {}
    for (name, year), cells in hist.items():
        prev = hist.get((name, year - 1))
        age = ages.get((name, year))
        if not prev or age is None:
            continue
        zs = []
        for metric in PHYSICAL_METRICS:
            a, b = prev.get(metric), cells.get(metric)
            if a and b and a[1] >= 1000 and b[1] >= 1000 and year in spread[metric] and year - 1 in spread[metric]:
                sd = 0.5 * (spread[metric][year] + spread[metric][year - 1])
                zs.append((b[0] - a[0]) / sd)
        if zs:
            changes.setdefault(int(age), []).append(statistics.fmean(zs))
    raw = {a: (statistics.fmean(v), float(len(v))) for a, v in changes.items() if len(v) >= 5}
    import math as _m
    smooth = {}
    for a in range(20, 41):
        num = den = 0.0
        for b, (mean, n) in raw.items():
            k = n * _m.exp(-0.5 * ((a - b) / 1.5) ** 2)
            num, den = num + k * mean, den + k
        smooth[a] = round(num / den, 4) if den else None
    # The league-wide drift (everyone's average speed moves with pace and tracking changes) is removed: changes are
    # centred so the minutes-weighted league average change is zero, as the age step is centred.
    centre = statistics.fmean(x for v in changes.values() for x in v)
    return {"version": "physical_aging_v1_2026_11_22", "method": " ".join(physical_aging.__doc__.split()),
            "sources": ["Basketball Index Leaderboards Values 2013-14 to 2025-26 (local capture): Avg Speed Offense, "
                        "Avg Speed Defense", "Basketball Reference ages (data/research/development_evidence.json)"],
            "league_drift_sd_per_year": round(centre, 4),
            "raw": {str(a): [round(m, 4), int(n)] for a, (m, n) in sorted(raw.items())},
            "annual_sd": {str(a): (round(v - centre, 4) if v is not None else None) for a, v in smooth.items()},
            "athletic_markers": athletic_markers(), "athletic_markers_method": " ".join(athletic_markers.__doc__.split())}


# ---------------------------------------------------------------------------------------------------------------------
# Snapshots and comparisons.
def snapshot_from(inputs_path: str, out_path: str) -> None:
    """The game's overall / offense / defense and value for every rostered player, from an inputs file (.json or
    .json.gz), as a new save would see them (opening day; scripts/research/rookie_fit_check.py snapshot)."""
    import gzip
    from nba_gm_data import ratings_model
    import rookie_fit_check as rfc
    opener = gzip.open if inputs_path.endswith(".gz") else open
    with opener(inputs_path, "rt", encoding="utf-8") as handle:
        section = json.load(handle)
    key, _ = ratings_model._load_inputs_keyed(ROOT)
    ratings_model._INPUT_CACHE[key] = {pid: doc["inputs"] for pid, doc in section["players"].items()}
    rows = rfc.snapshot()
    Path(out_path).write_text(json.dumps(rows, indent=0) + "\n")
    print(f"{len(rows)} players -> {out_path}")


def moved(before_path: str, after_path: str, names: list[str]) -> None:
    """How many players moved, the largest moves, and named players before / after."""
    before = {r["id"]: r for r in json.loads(Path(before_path).read_text())}
    after = {r["id"]: r for r in json.loads(Path(after_path).read_text())}
    diffs = sorted(((after[p]["ovr"] - before[p]["ovr"], p) for p in after if p in before), key=lambda t: t[0])
    print(f"overall moved 0.1+: {sum(1 for d, _ in diffs if abs(d) >= 0.1)}; 1.0+: {sum(1 for d, _ in diffs if abs(d) >= 1.0)}"
          f"; up 0.1+: {sum(1 for d, _ in diffs if d >= 0.1)}; down 0.1+: {sum(1 for d, _ in diffs if d <= -0.1)}")
    for d, p in diffs[:6] + diffs[-6:]:
        print(f"  {after[p]['name']:26s} {before[p]['ovr']:5.1f} -> {after[p]['ovr']:5.1f} ({d:+.1f})  rank {before[p]['rank']} -> "
              f"{after[p]['rank']}  value {before[p]['impact_off']:+.2f}/{before[p]['impact_def']:+.2f} -> "
              f"{after[p]['impact_off']:+.2f}/{after[p]['impact_def']:+.2f}")
    print("| Player | Age | Overall before -> after | League rank | Value off/def before -> after |")
    print("|---|---:|---|---|---|")
    keyed = {norm(r["name"]): r for r in after.values()}
    for name in names:
        r = keyed.get(norm(name))
        if not r:
            print(f"| {name} | not rostered |")
            continue
        b = before[r["id"]]
        print(f"| {r['name']} | {r['age']:.0f} | {b['ovr']} -> {r['ovr']} | {b['rank']} -> {r['rank']} | "
              f"{b['impact_off']:+.2f}/{b['impact_def']:+.2f} -> {r['impact_off']:+.2f}/{r['impact_def']:+.2f} |")


def _spearman(a, b):
    def ranks(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        for k, i in enumerate(order):
            r[i] = k
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return cov / math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))


def analyst_compare(*snapshots: str) -> None:
    """The game's order of the analyst-ranked veterans (ESPN NBA Rank 2026 and The Ringer Top 100, as the audit) against
    the analysts' order, and the named high-usage scorers and rim-protecting bigs, for each snapshot."""
    from ratings_audit_gsw import analyst_rank_map
    ranks = analyst_rank_map()
    lebron = {}
    with LEBRON_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["Season"] == "2026":
                lebron[norm(row["Player"])] = (float(row["O-LEBRON"]), float(row["D-LEBRON"]))
    tables = []
    for path in snapshots:
        snap = json.loads(Path(path).read_text())
        rows = []
        for r in snap:
            a = ranks.get(norm(r["name"]))
            if a and r["draft_year"] != "2026":
                rows.append({**r, "analyst": statistics.fmean([a.get("espn") or 110, a.get("ringer") or 110])})
        rows.sort(key=lambda r: r["analyst"])
        for i, r in enumerate(rows, 1):
            r["analyst_rank"] = i
        for i, r in enumerate(sorted(rows, key=lambda r: -r["impact"]), 1):
            r["game_rank"] = i
        rho = _spearman([r["analyst_rank"] for r in rows], [r["game_rank"] for r in rows])
        gap = statistics.fmean(abs(r["game_rank"] - r["analyst_rank"]) for r in rows)
        with_leb = [r for r in rows if norm(r["name"]) in lebron]
        rho_o = _spearman([lebron[norm(r["name"])][0] for r in with_leb], [r["impact_off"] for r in with_leb])
        rho_d = _spearman([lebron[norm(r["name"])][1] for r in with_leb], [r["impact_def"] for r in with_leb])
        print(f"{path}: {len(rows)} analyst-ranked players; rank correlation with analysts {rho:.3f}, average gap "
              f"{gap:.1f} places; game value vs last season's LEBRON (rank correlation, these players): offense "
              f"{rho_o:.3f}, defense {rho_d:.3f}")
        tables.append({norm(r["name"]): r for r in rows})
    print("\n| Player | Analysts | " + " | ".join(f"game rank ({Path(p).stem})" for p in snapshots)
          + " | value off/def (last) | LEBRON 2025-26 off/def |")
    print("|---|---:|" + "---:|" * len(snapshots) + "---|---|")
    for name in SCORERS + BIGS:
        key = norm(name)
        if key not in tables[-1]:
            continue
        r = tables[-1][key]
        leb = lebron.get(key)
        print(f"| {r['name']} | {r['analyst_rank']} | " + " | ".join(str(t[key]["game_rank"]) if key in t else "-" for t in tables)
              + f" | {r['impact_off']:+.2f}/{r['impact_def']:+.2f} | "
              + (f"{leb[0]:+.2f}/{leb[1]:+.2f}" if leb else "-") + " |")


def value_experiments() -> None:
    """Refit the value formula on the fit sample (2025-26-level ratings) under alternative specifications and report,
    for each: out-of-fold correlation with the blended target and with real multi-year LEBRON (offense, defense), the
    rank correlation of the predicted order with the analysts' order (ESPN / Ringer players in the sample), and the
    named scorers' and bigs' places in that order. Nothing is written."""
    import random
    sys.path.insert(0, str(ROOT / "scripts"))
    import fit_impact_value as fiv
    from nba_gm_data.impact_value import BODY_PREDICTORS, DEFENSE_ONLY, OFFENSE_ONLY, PREDICTORS
    from ratings_audit_gsw import analyst_rank_map
    rows = value_rows(True)
    amap = analyst_rank_map()
    for r in rows:
        a = amap.get(norm(r["name"]))
        r["audit_analyst"] = statistics.fmean([a.get("espn") or 110, a.get("ringer") or 110]) if a else None
    w = [r["minutes"] / (r["minutes"] + 800.0) for r in rows]
    X = [[r["x"][p] for p in PREDICTORS] for r in rows]
    cols = list(zip(*X))
    mu = [statistics.fmean(c) for c in cols]
    sd = [statistics.pstdev(c) or 1.0 for c in cols]
    Z = [[1.0, *[(v - m) / s for v, m, s in zip(x, mu, sd)]] for x in X]
    idx = list(range(len(rows)))
    random.Random(11).shuffle(idx)
    folds = [idx[i::5] for i in range(5)]
    FREE = {1 + PREDICTORS.index(n) for n in (*BODY_PREDICTORS, "in_involvement")}

    def targets_for(split):
        if split == "league":
            return [(r["target"]["offense"], r["target"]["defense"]) for r in rows]
        # "own": the analysts' gap goes to each side in proportion to the player's own real impact profile: the share
        # of his (offense - league offense) in his total distance from the league middle; otherwise the league split.
        out = []
        for r in rows:
            gap_o = r["target"]["offense"] - r["real"]["offense"]
            gap_d = r["target"]["defense"] - r["real"]["defense"]
            gap = gap_o + gap_d
            o_rel, d_rel = max(0.0, r["real"]["offense"] + 0.5), max(0.0, r["real"]["defense"] + 0.5)
            share = o_rel / (o_rel + d_rel) if o_rel + d_rel > 0 else 0.7
            out.append((r["real"]["offense"] + gap * share, r["real"]["defense"] + gap * (1 - share)))
        return out

    def run(label, split="league", lam=fiv.RIDGE, drop_def=(), drop_off=(), free_extra=()):
        tg = targets_for(split)
        preds = {}
        corr = {}
        for k, side in enumerate(("offense", "defense")):
            y = [t[k] for t in tg]
            drop = {1 + PREDICTORS.index(n) for n in (OFFENSE_ONLY if side == "defense" else DEFENSE_ONLY)}
            drop |= {1 + PREDICTORS.index(n) for n in (drop_def if side == "defense" else drop_off)}
            Zs = [[0.0 if j in drop else v for j, v in enumerate(z)] for z in Z]
            free = FREE | {1 + PREDICTORS.index(n) for n in free_extra}
            free = free - drop
            oof = [0.0] * len(rows)
            for f in folds:
                tr = [i for i in idx if i not in f]
                c = fiv.ridge_nonnegative([Zs[i] for i in tr], [y[i] for i in tr], [w[i] for i in tr], lam, free)
                for i in f:
                    oof[i] = sum(a * b for a, b in zip(Zs[i], c))
            corr[side] = (round(fiv.wcorr(y, oof, w), 3), round(fiv.wcorr([r["real"][side] for r in rows], oof, w), 3))
            preds[side] = oof
        total = [a + b for a, b in zip(preds["offense"], preds["defense"])]
        ranked = [i for i in range(len(rows)) if rows[i]["audit_analyst"] is not None]
        game_order = sorted(ranked, key=lambda i: -total[i])
        analyst_order = sorted(ranked, key=lambda i: rows[i]["audit_analyst"])
        g_rank = {i: n + 1 for n, i in enumerate(game_order)}
        a_rank = {i: n + 1 for n, i in enumerate(analyst_order)}
        rho = _spearman([a_rank[i] for i in ranked], [g_rank[i] for i in ranked])
        gap = statistics.fmean(abs(a_rank[i] - g_rank[i]) for i in ranked)
        names = {norm(rows[i]["name"]): i for i in ranked}
        show = ["Jalen Brunson", "Jaylen Brown", "Trae Young", "Paolo Banchero", "Alperen Sengun", "Donovan Clingan",
                "Isaiah Hartenstein", "Jarrett Allen", "Walker Kessler", "Rudy Gobert"]
        places = " ".join(f"{n.split()[-1]} {g_rank[names[norm(n)]]}/{a_rank[names[norm(n)]]}" for n in show if norm(n) in names)
        print(f"{label:52s} oof off {corr['offense']} def {corr['defense']} | analysts rho {rho:.3f} gap {gap:.1f} "
              f"({len(ranked)} players) | {places}")
        return preds

    print("Columns: out-of-fold correlation (with target, with real LEBRON); analysts' order; game/analyst places")
    run("current specification")
    run("no usage term on defense", drop_def=("in_involvement",))
    run("analyst gap split by own profile", split="own")
    run("both", split="own", drop_def=("in_involvement",))
    for lam in (0.5, 1.0, 4.0):
        run(f"ridge {lam}", lam=lam)
    run("no usage on defense, ridge 1.0", drop_def=("in_involvement",), lam=1.0)


# ---------------------------------------------------------------------------------------------------------------------
# Step 6 (coordinator, 2026-11-22): rookies' involvement on the veterans' usage scale.
ROOKIE_INVOLVEMENT_OUT = ROOT / "data/research/rookie_involvement_2026.json"
ROOKIE_USAGE_MIN_MINUTES = 300.0


def rookie_involvement() -> dict:
    """Rookies' involvement (T08) for the 2026 class on the veterans' usage scale.

    1. Veterans' line: involvement in the inputs file against Basketball Reference usage %, veterans with 1,000+
       minutes in 2025-26 (scripts/research/rookie_fit2.usage_line, the line the early-games evidence already uses).
    2. Rookie usage from college: real rookie-season usage % (Basketball Reference, classes 2015-16 to 2025-26, 300+
       minutes) against the final college season's usage % (Barttorvik) and log draft pick, weighted least squares by
       rookie minutes (the ROOKIE-FIT sample of drafted college players). Survivors only (rookies who played).
    3. Each 2026 rookie's involvement = the veterans' line at his forecast rookie usage, so a rookie expected to use
       18% of his team's plays gets what a veteran at 18% has. Draftees without a college line (international
       players) are forecast at the average drafted player's college usage and their own pick.
    4. This season's real usage so far joins the forecast by precision (see with_season), then the veterans' line.
    """
    import rookie_fit as rf
    import rookie_fit2 as rf2
    real = json.loads((ROOT / "data/research/rookie_real_lines.json").read_text())
    line = rf2.usage_line(real.get("usage_2025_26") or {})
    by_class = {(int(season), rf.key(r["name"])): r for season, rows in real["classes"].items() for r in rows}
    examples, _, _, _ = rf.assemble()
    rows = []
    for e in examples:
        r = by_class.get((e["first_season"], rf.key(e["name"])))
        if r and r.get("usg_pct") is not None and (r.get("mp") or 0) >= ROOKIE_USAGE_MIN_MINUTES:
            rows.append((e["x"]["usg"], math.log(e["pick"]), float(r["usg_pct"]), float(r["mp"]), e["name"]))
    # weighted least squares: usage = a + b * college usage + c * log pick
    X = [[1.0, u, lp] for u, lp, _, _, _ in rows]
    y = [t for _, _, t, _, _ in rows]
    w = [m for _, _, _, m, _ in rows]
    n = 3
    A = [[sum(wi * x[i] * x[j] for x, wi in zip(X, w)) for j in range(n)] for i in range(n)]
    b = [sum(wi * x[i] * t for x, t, wi in zip(X, y, w)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            f = A[j][i] / A[i][i]
            for k in range(i, n):
                A[j][k] -= f * A[i][k]
            b[j] -= f * b[i]
    coef = [0.0] * n
    for i in reversed(range(n)):
        coef[i] = (b[i] - sum(A[i][k] * coef[k] for k in range(i + 1, n))) / A[i][i]
    pred = [sum(c * v for c, v in zip(coef, x)) for x in X]
    resid = [t - p for t, p in zip(y, pred)]
    r2 = 1 - sum(wi * e * e for e, wi in zip(resid, w)) / sum(wi * (t - sum(wi2 * t2 for t2, wi2 in zip(y, w)) / sum(w)) ** 2
                                                          for t, wi in zip(y, w))
    bundle = json.loads((ROOT / "data/research/rookie_translation_2026.json").read_text())["class_2026"]
    players = {}
    for pid, entry in sorted(bundle.items()):
        usg = (entry.get("college") or {}).get("usg")
        pick = entry.get("pick")
        if usg is None or not pick:
            continue
        usage = coef[0] + coef[1] * float(usg) + coef[2] * math.log(max(1.0, float(pick)))
        players[pid] = {"name": entry["name"], "college_usage": usg, "pick": pick, "rookie_usage": round(usage, 2),
                        "involvement": round(min(0.95, max(0.05, line["intercept"] + line["slope"] * usage)), 4)}
    # This season's real usage so far (Basketball Reference) joins the forecast in usage terms, each by its precision:
    # the forecast's own error (residual spread of the fit above) and the counting noise of a usage share over his
    # minutes (team plays while he is on court: 102 possessions per 48 minutes, binomial share). Counting noise is the
    # least noise a share can have, so this weight is an upper bound; it replaces the earlier fixed 1,000-minute weight.
    plays_per_minute = 102.0 / 48.0
    forecast_var = statistics.pvariance(resid)
    early = {rf.key(r["name"]): r for r in (real.get("season_2027") or {}).get("rookies", [])}

    def with_season(row):
        r = early.get(rf.key(row["name"]))
        if not r or r.get("usg_pct") is None or not r.get("mp"):
            return row
        share = row["rookie_usage"] / 100.0      # the expected share sets the noise (a 0% in two minutes is noise)
        noise = share * (1 - share) / (plays_per_minute * float(r["mp"])) * 1e4
        w = forecast_var / (forecast_var + noise)
        usage = w * float(r["usg_pct"]) + (1 - w) * row["rookie_usage"]
        return {**row, "season_usage": r["usg_pct"], "season_minutes": r["mp"], "season_weight": round(w, 3),
                "usage": round(usage, 2),
                "involvement": round(min(0.95, max(0.05, line["intercept"] + line["slope"] * usage)), 4)}

    # 2026 draftees without a college line (international players): the average drafted player's college usage, his pick.
    mean_usage = sum(u * m for u, _, _, m, _ in rows) / sum(m for *_, m, _ in rows)
    universe = json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text())
    for p in universe["players"]:
        if p.get("draft_year") == 2026 and p.get("draft_status") == "drafted" and p["id"] not in players \
                and p.get("draft_position"):
            usage = coef[0] + coef[1] * mean_usage + coef[2] * math.log(max(1.0, float(p["draft_position"])))
            players[p["id"]] = {"name": p["name"], "college_usage": None, "pick": p["draft_position"],
                                "rookie_usage": round(usage, 2),
                                "involvement": round(min(0.95, max(0.05, line["intercept"] + line["slope"] * usage)), 4)}
    players = {pid: with_season(row) for pid, row in players.items()}
    return {"version": "rookie_involvement_v1_2026_11_22", "method": " ".join(rookie_involvement.__doc__.split()),
            "sources": ["Basketball Reference usage %: veterans 2025-26 and rookie classes 2015-16 to 2025-26 "
                        "(data/research/rookie_real_lines.json)", "Barttorvik final college seasons (local)",
                        "inputs file involvement (data/canonical/player_inputs_2026_27.json.gz)"],
            "veterans_line": line, "rookie_usage_fit": {"intercept": round(coef[0], 4), "college_usage": round(coef[1], 4),
                                                        "log_pick": round(coef[2], 4), "rookies": len(rows),
                                                        "weighted_r2": round(r2, 3),
                                                        "residual_sd": round(statistics.pstdev(resid), 2)},
            "season_evidence": {"plays_per_minute": round(plays_per_minute, 4), "forecast_variance": round(forecast_var, 3),
                                "as_of": (real.get("season_2027") or {}).get("as_of")},
            "players": players}


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "thin":
        out = thin()
        THIN_OUT.write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps(out, indent=1))
    elif cmd == "rookie-involvement":
        out = rookie_involvement()
        ROOKIE_INVOLVEMENT_OUT.write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps({k: out[k] for k in ("veterans_line", "rookie_usage_fit")}, indent=1))
        for pid, r in sorted(out["players"].items(), key=lambda kv: -kv[1]["involvement"]):
            print(f"  {r['name']:24s} pick {r['pick']:>2} college usage {r['college_usage'] or 0:5.1f} -> rookie {r['rookie_usage']:5.1f}"
                  f" -> involvement {r['involvement']:.3f}")
    elif cmd == "snapshot":
        snapshot_from(sys.argv[2], sys.argv[3])
    elif cmd == "analysts":
        analyst_compare(*sys.argv[2:])
    elif cmd == "moved":
        moved(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif cmd == "physical":
        out = physical_aging()
        PHYSICAL_OUT.write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps(out, indent=1))
    elif cmd == "value-experiments":
        value_experiments()
    elif cmd == "value":
        value_diagnose(replay="--opening-day" not in sys.argv)
    elif cmd == "injury":
        out = injury_return()
        INJURY_OUT.write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps({k: out[k] for k in ("groups", "applied_cost", "basketball_index_matched_estimate")}, indent=1))
        for c in out["cases"]:
            print(c["player"], c["injury"], c["season"], c.get("age"), c["status"], c.get("level_before"),
                  c.get("season_back"), c.get("expected_back"), c.get("actual_back"), c.get("cost"))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
