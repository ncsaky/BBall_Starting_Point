#!/usr/bin/env python3
"""ROOKIE-FIT: how a final college season translates to rookie-year NBA play (drafts 2009-2025).

Evidence, no simulation:
  * College: Barttorvik player tables (data/research/barttorvik/raw/players_<season>.csv, local only), final college
    season of every drafted player; team strength from Barttorvik team results (adjusted efficiency, barthag).
  * NBA rookie year: Basketball Index LEBRON / O-LEBRON / D-LEBRON by season
    (data/research/bbi/captures/fanspo_tools/lebron/lebron_separate-seasons_raw_all-2010-2026.csv) and Basketball
    Reference minutes / BPM / draft picks (data/research/development_evidence.json, public_inputs).

Selection (who gets minutes): every drafted college player counts. His rookie impact is shrunk toward the level of
rookies who barely play, by minutes: y = (impact * minutes + R * K) / (minutes + K). A player who never plays is R.
R is measured (minutes-weighted impact of rookies with 50-500 minutes), K = 750 minutes (the estimator's usual
reliability anchor for a season's impact). Fits on players with real minutes only are reported for comparison.

Models (ridge, standardized features, ridge strength by leave-one-draft-out): draft slot alone; college alone;
college + slot. Checked on held-out drafts (fit 2009-2019, score 2020-2025) and leave-one-draft-out.

Writes data/research/rookie_translation_2026.json (fit, checks, the 2026 class's college lines and projections)
and prints the report tables.

    PYTHONPATH=src .venv/bin/python scripts/research/rookie_fit.py [--no-write]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
sys.path.insert(0, str(ROOT / "src"))

import real_prospects as rp  # noqa: E402  (college history, rates, shooting priors, team strength, ridge helpers)

LEBRON_CSV = ROOT / "data/research/bbi/captures/fanspo_tools/lebron/lebron_separate-seasons_raw_all-2010-2026.csv"
DEV_EVIDENCE = ROOT / "data/research/development_evidence.json"
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"
OUT = ROOT / "data/research/rookie_translation_2026.json"
FIT_DRAFTS = range(2009, 2026)        # rookie seasons 2009-10 .. 2025-26 (LEBRON starts 2009-10)
TRAIN_LAST = 2019                      # held-out check: fit 2009-2019, score 2020-2025
TARGET_DRAFT = 2026
K_MINUTES = 750.0
COLLEGE_MIN_MINUTES = 150.0            # final seasons shorter than this are not a usable college line

# Name differences between Barttorvik and the NBA sources (Barttorvik name -> NBA name), checked by hand.
ALIASES = {
    "nahshon hyland": "bones hyland", "herb jones": "herbert jones", "cameron thomas": "cam thomas",
    "carlton carrington": "bub carrington", "gregory jackson": "gg jackson", "jeenathan williams": "nate williams",
}

FEATURES = ("obpm", "dbpm", "usg", "ts", "orb_pct", "drb_pct", "ast_pct", "tov_pct", "stl_pct", "blk_pct", "ftr",
            "three_rate", "three_per40", "three_pct", "ft_pct", "height_c", "age", "team", "min_pct")
LABELS = {
    "obpm": "college offensive box plus-minus", "dbpm": "college defensive box plus-minus", "usg": "usage",
    "ts": "true shooting", "orb_pct": "offensive rebound rate", "drb_pct": "defensive rebound rate",
    "ast_pct": "assist rate", "tov_pct": "turnover rate", "stl_pct": "steal rate", "blk_pct": "block rate",
    "ftr": "free-throw rate", "three_rate": "share of shots from three", "three_per40": "threes tried per 40",
    "three_pct": "three-point % (career, shrunk)", "ft_pct": "free-throw % (career, shrunk)",
    "height_c": "height", "age": "age on draft day", "team": "team strength (barthag)", "min_pct": "minutes share",
    "log_pick": "draft slot (log)",
}


def key(name: str) -> str:
    k = rp.name_key(name)
    return ALIASES.get(k, k)


# ------------------------------------------------------------------------------------------------ NBA outcomes


def load_nba():
    dev = json.loads(DEV_EVIDENCE.read_text(encoding="utf-8"))["public_inputs"]
    bref = defaultdict(dict)        # name key -> season_end -> row
    for year, pid, name, age, minutes, bpm, vorp in dev["seasons"]:
        bref[key(name)][year] = {"bref_id": pid, "name": name, "age": age, "minutes": minutes, "bpm": bpm}
    draft = {(year, pick): (pid, name) for year, pick, pid, name in dev["draft"]}
    lebron = defaultdict(dict)
    with LEBRON_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            season = int(row["Season"])
            k = key(row["Player"])
            lebron[k][season] = {"lebron": float(row["LEBRON"]), "o": float(row["O-LEBRON"]),
                                 "d": float(row["D-LEBRON"]), "mpg": float(row["MPG"] or 0)}
    return bref, draft, lebron


# ------------------------------------------------------------------------------------------------ college lines


def college_line(seasons: dict, ctx) -> dict | None:
    last = max(seasons)
    row = seasons[last]
    minutes = rp.season_minutes(row)
    rates = rp.season_rates(row)
    shoot = rp.shooting(rp.career_totals(list(seasons.values())))
    born = rp.known_birth_date(row)
    team = rp.team_strength(ctx, last, row["team"])
    adj = ctx.get((last, row["team"]), {})
    return {"season": last, "name": row["name"], "team_name": row["team"], "conf": row.get("conf"),
            "class": str(row.get("class_year") or ""), "minutes": round(minutes, 1), "games": row.get("games"),
            "pick": row.get("nba_pick"), "born": born.isoformat() if born else None,
            "height_in": row.get("height_in"),
            "bpm": rp.num(row.get("bpm")), "obpm_raw": rp.num(row.get("obpm")), "dbpm_raw": rp.num(row.get("dbpm")),
            "rates": rates, "shoot": shoot, "team": team, "adjoe": adj.get("adjoe"), "adjde": adj.get("adjde"),
            "cls": rp.class_index(row), "pts_pg": row.get("pts_pg"), "reb_pg": row.get("reb_pg"),
            "ast_pg": row.get("ast_pg"), "stl_pg": row.get("stl_pg"), "blk_pg": row.get("blk_pg")}


def draft_age(line: dict, draft_year: int, nba_age: float | None = None) -> float:
    if line["born"]:
        return (dt.date(draft_year, *rp.DRAFT_DAY) - dt.date.fromisoformat(line["born"])).days / 365.25
    if nba_age is not None:
        return nba_age - 0.4     # Basketball Reference age is on 1 February of the rookie season
    return rp.TYPICAL_AGE_BY_CLASS[min(3, line["cls"])] + (draft_year - line["season"])


def feature_row(line: dict, age: float) -> dict[str, float]:
    r, s = line["rates"], line["shoot"]
    rel = min(1.0, line["minutes"] / 600)      # short seasons lean toward a typical draftee (as in the draft model)
    return {
        "obpm": line["obpm_raw"] * rel + 1.5 * (1 - rel), "dbpm": line["dbpm_raw"] * rel + 1.0 * (1 - rel),
        "usg": r["usg"], "ts": r["ts"], "orb_pct": min(20.0, r["orb_pct"]), "drb_pct": min(35.0, r["drb_pct"]),
        "ast_pct": min(45.0, r["ast_pct"]), "tov_pct": min(30.0, r["tov_pct"]), "stl_pct": min(6.0, r["stl_pct"]),
        "blk_pct": min(15.0, r["blk_pct"]), "ftr": min(80.0, r["ftr"]), "three_rate": r["three_rate"],
        "three_per40": r["three_per40"], "three_pct": s["three_pct"], "ft_pct": s["ft_pct"],
        "height_c": (line["height_in"] or 78) - 78, "age": max(18.5, min(26.0, age)), "team": line["team"],
        "min_pct": r["min_pct"],
    }


# ------------------------------------------------------------------------------------------------ assembly


def assemble():
    by_player = rp.load_history()
    ctx = rp.load_team_context()
    bref, draft, lebron = load_nba()
    examples, unmatched = [], []
    for seasons in by_player.values():
        last = max(seasons)
        row = seasons[last]
        pick = next((r["nba_pick"] for r in seasons.values() if r.get("nba_pick")), None)
        if not pick or last not in FIT_DRAFTS:
            continue
        line = college_line(seasons, ctx)
        if line["minutes"] < COLLEGE_MIN_MINUTES:
            continue
        k = key(row["name"])
        year = last
        if (year, pick) in draft:                       # 2009-2019: Basketball Reference draft table
            pid, name = draft[(year, pick)]
            if key(name) != k:
                # Barttorvik's pick is the right slot in a different year, or a name variant: trust the slot only
                # when the surname agrees.
                if k.split()[-1] != key(name).split()[-1]:
                    unmatched.append((year, pick, row["name"], name))
                    continue
            k = key(name)
        nba_rows = bref.get(k, {})
        first = year + 1
        rookie = nba_rows.get(first)
        if (rookie is None or rookie["minutes"] < 50) and (nba_rows.get(year + 2) or {}).get("minutes", 0) >= 500:
            # Missed (nearly) all of the first season, then played a real season: an injury or stash year, not a
            # verdict on readiness (Griffin, Embiid, Simmons, Holmgren). His first real season counts.
            first = year + 2
            rookie = nba_rows[first]
        if rookie is None and not nba_rows and year <= 2024:
            unmatched.append((year, pick, row["name"], "no NBA rows"))
        minutes = rookie["minutes"] if rookie else 0.0
        leb = lebron.get(k, {}).get(first)
        age = draft_age(line, year, rookie["age"] - (first - year - 1) if rookie else None)
        examples.append({"name": row["name"], "draft": year, "pick": pick, "line": line, "x": feature_row(line, age),
                         "minutes": minutes, "bpm": rookie["bpm"] if rookie else None, "first_season": first,
                         "lebron": leb["lebron"] if leb and minutes > 0 else None,
                         "o": leb["o"] if leb and minutes > 0 else None, "d": leb["d"] if leb and minutes > 0 else None,
                         "ever_nba": bool(nba_rows)})
    return examples, unmatched, by_player, ctx


def replacement(examples, field: str) -> float:
    rows = [(e[field], e["minutes"]) for e in examples if e[field] is not None and 50 <= e["minutes"] < 500]
    return sum(v * m for v, m in rows) / sum(m for _, m in rows)


def outcome(e, field: str, r_level: float) -> float:
    v = e[field] if e[field] is not None else r_level
    m = e["minutes"] if e[field] is not None else 0.0
    return (v * m + r_level * K_MINUTES) / (m + K_MINUTES)


# ------------------------------------------------------------------------------------------------ fitting


def design(examples, cols):
    rows = []
    for e in examples:
        rows.append([with_derived(e)[c] for c in cols])
    return rows


def fit(examples, ys, cols, ridge):
    raw = design(examples, cols)
    means, sds = rp.standardizer(raw)
    z = [[(v - m) / s for v, m, s in zip(r, means, sds)] for r in raw]
    beta = rp.linear_fit(z, ys, ridge=ridge)
    return {"cols": list(cols), "means": means, "sds": sds, "beta": beta}


def with_derived(example) -> dict:
    x = example["x"]
    return dict(x, log_pick=math.log(example["pick"]), age_x_obpm=(x["age"] - 21) * (x["obpm"] - 4),
                age_x_dbpm=(x["age"] - 21) * (x["dbpm"] - 3))


def predict(model, example) -> float:
    x = with_derived(example)
    return model["beta"][0] + sum(b * (x[c] - m) / s for b, c, m, s in
                                  zip(model["beta"][1:], model["cols"], model["means"], model["sds"]))


def scores(pred, actual):
    n = len(actual)
    rmse = math.sqrt(sum((p - a) ** 2 for p, a in zip(pred, actual)) / n)
    r = statistics.correlation(pred, actual) if n > 2 else float("nan")
    return {"n": n, "r": round(r, 3), "r2": round(r * r, 3), "rmse": round(rmse, 3),
            "spearman": round(rp.spearman(pred, actual), 3)}


def loyo(examples, ys, cols, ridge):
    pred = [0.0] * len(examples)
    for year in sorted({e["draft"] for e in examples}):
        train = [i for i, e in enumerate(examples) if e["draft"] != year]
        model = fit([examples[i] for i in train], [ys[i] for i in train], cols, ridge)
        for i, e in enumerate(examples):
            if e["draft"] == year:
                pred[i] = predict(model, e)
    return pred


def choose_ridge(examples, ys, cols):
    best = None
    for ridge in (1, 3, 10, 30, 100, 300):
        pred = loyo(examples, ys, cols, ridge)
        rmse = math.sqrt(statistics.fmean((p - y) ** 2 for p, y in zip(pred, ys)))
        if best is None or rmse < best[1] - 1e-9:
            best = (ridge, rmse)
    return best[0]


MODELS = {"slot": ("log_pick",), "college": FEATURES, "college_slot": (*FEATURES, "log_pick")}


def evaluate(examples, field, r_level):
    ys = [outcome(e, field, r_level) for e in examples]
    out = {}
    train = [i for i, e in enumerate(examples) if e["draft"] <= TRAIN_LAST]
    test = [i for i, e in enumerate(examples) if e["draft"] > TRAIN_LAST]
    played = [i for i in test if examples[i]["minutes"] >= 1000 and examples[i][field] is not None]
    for name, cols in MODELS.items():
        ridge = choose_ridge(examples, ys, cols)
        model = fit([examples[i] for i in train], [ys[i] for i in train], cols, ridge)
        pred = [predict(model, examples[i]) for i in test]
        lo = loyo(examples, ys, cols, ridge)
        out[name] = {
            "ridge": ridge,
            "held_out": scores(pred, [ys[i] for i in test]),
            "held_out_1000_min_raw": scores([predict(model, examples[i]) for i in played],
                                            [examples[i][field] for i in played]),
            "leave_one_draft_out": scores(lo, ys),
        }
    return ys, out


PICK_BANDS = ((1, 3), (4, 10), (11, 20), (21, 30), (31, 45), (46, 60))


def band_table(examples, field):
    out = []
    for lo, hi in PICK_BANDS:
        rows = [e for e in examples if lo <= e["pick"] <= hi]
        played = [e for e in rows if e["minutes"] >= 500 and e[field] is not None]
        out.append({"picks": f"{lo}-{hi}", "n": len(rows), "share_500_min": round(len(played) / len(rows), 3),
                    "mean_if_500_min": round(statistics.fmean(e[field] for e in played), 2) if played else None,
                    "median_minutes": statistics.median(e["minutes"] for e in rows)})
    return out


def coef_table(model):
    return {c: round(b, 4) for c, b in zip(model["cols"], model["beta"][1:])}


def college_bpm(e) -> float:
    return e["line"]["obpm_raw"] + e["line"]["dbpm_raw"]


GROUPS = {
    "older (22.5+), college BPM 9+": lambda e: e["x"]["age"] >= 22.5 and college_bpm(e) >= 9,
    "older (22.5+), college BPM under 9": lambda e: e["x"]["age"] >= 22.5 and college_bpm(e) < 9,
    "younger (under 21), college BPM 9+": lambda e: e["x"]["age"] < 21 and college_bpm(e) >= 9,
    "younger (under 21), college BPM under 9": lambda e: e["x"]["age"] < 21 and college_bpm(e) < 9,
    "first round, older 22.5+": lambda e: e["pick"] <= 30 and e["x"]["age"] >= 22.5,
    "first round, under 21": lambda e: e["pick"] <= 30 and e["x"]["age"] < 21,
}


def age_check(examples, ys, slot_pred, college_pred):
    """Mean residual by group: positive = played better than the model predicted (out of fold)."""
    out = {}
    for label, test in GROUPS.items():
        idx = [i for i, e in enumerate(examples) if test(e)]
        if not idx:
            continue
        out[label] = {"n": len(idx),
                      "mean_outcome": round(statistics.fmean(ys[i] for i in idx), 3),
                      "vs_slot_model": round(statistics.fmean(ys[i] - slot_pred[i] for i in idx), 3),
                      "vs_college_slot_model": round(statistics.fmean(ys[i] - college_pred[i] for i in idx), 3),
                      "median_pick": statistics.median(examples[i]["pick"] for i in idx),
                      "share_500_min": round(sum(examples[i]["minutes"] >= 500 for i in idx) / len(idx), 3)}
    return out


def residual_regression(examples, ys, slot_pred):
    """Slot-model residual on age, college BPM and their product (standardized): does age add day-one value?"""
    cols = ("age", "cbpm", "age_x_cbpm")
    raw = [[e["x"]["age"] - 21, college_bpm(e) - 7, (e["x"]["age"] - 21) * (college_bpm(e) - 7)] for e in examples]
    means, sds = rp.standardizer(raw)
    z = [[(v - m) / s for v, m, s in zip(r, means, sds)] for r in raw]
    beta = rp.linear_fit(z, [y - p for y, p in zip(ys, slot_pred)], ridge=1.0)
    return {c: round(b / s, 4) for c, b, s in zip(cols, beta[1:], sds)}   # per unit (year of age, BPM point)


def selected_only(examples, field, cols):
    """Ignoring selection: only rookies with 1000+ minutes, raw outcome. Shows what the shrinkage changes."""
    rows = [e for e in examples if e["minutes"] >= 1000 and e[field] is not None]
    return coef_table(fit(rows, [e[field] for e in rows], cols, 30)), len(rows)


def target_class(by_player, ctx):
    """The 2026 draftees with a usable college line, keyed by universe player id."""
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    rookies = {key(p["name"]): p for p in universe["players"]
               if str(p.get("draft_year")) == str(TARGET_DRAFT) and p.get("draft_status") == "drafted"}
    out = {}
    for seasons in by_player.values():
        last = max(seasons)
        row = seasons[last]
        if last != TARGET_DRAFT:
            continue
        player = rookies.get(key(row["name"]))
        if player is None:
            continue
        line = college_line(seasons, ctx)
        if line["minutes"] < COLLEGE_MIN_MINUTES:
            continue
        born = player.get("birthdate")
        if born and not line["born"]:
            line["born"] = born[:10]
        if player.get("height_inches"):
            line["height_in"] = player["height_inches"]
        pick = int(player.get("draft_position") or row.get("nba_pick") or 60)
        # Skill-evidence profile exactly as the college -> 94-input mapping was fitted (real_prospects
        # fit_input_mapping): final season plus half of the one before, by minutes; career shooting.
        rates, w0 = rp.season_rates(row), rp.season_minutes(row)
        prev = seasons.get(last - 1)
        w1 = 0.5 * rp.season_minutes(prev) if prev else 0.0
        if w1 > 0:
            prev_rates = rp.season_rates(prev)
            rates = {k: (rates[k] * w0 + prev_rates[k] * w1) / (w0 + w1) for k in rp.PROFILE_RATES}
        shoot = line["shoot"]
        profile = {**{k: round(rates[k], 5) for k in rp.PROFILE_RATES},
                   **{k: round(shoot[k], 5) for k in ("ft_pct", "three_pct", "rim_pct", "mid_pct")}}
        out[player["id"]] = {"name": player["name"], "draft": TARGET_DRAFT, "pick": pick, "line": line,
                             "x": feature_row(line, draft_age(line, TARGET_DRAFT)), "profile": profile,
                             "effective_minutes": round(w0 + w1, 1)}
    missing = sorted(p["name"] for k, p in rookies.items() if p["id"] not in out)
    return out, missing


def college_card(line: dict) -> dict:
    """The college line as stored in the translation bundle (read by input_estimator.load_rookie_college)."""
    return {"season": line["season"], "team": line["team_name"], "conf": line["conf"],
                "class": line["class"], "games": line["games"], "minutes": line["minutes"],
                "min_pct": r(line["rates"]["min_pct"], 1), "bpm": r(line["bpm"], 2),
                "obpm": r(line["obpm_raw"], 2), "dbpm": r(line["dbpm_raw"], 2),
                "usg": r(line["rates"]["usg"], 1), "ts": r(line["rates"]["ts"], 1),
                "orb_pct": r(line["rates"]["orb_pct"], 1), "drb_pct": r(line["rates"]["drb_pct"], 1),
                "ast_pct": r(line["rates"]["ast_pct"], 1), "tov_pct": r(line["rates"]["tov_pct"], 1),
                "stl_pct": r(line["rates"]["stl_pct"], 2), "blk_pct": r(line["rates"]["blk_pct"], 2),
                "ftr": r(line["rates"]["ftr"], 1), "three_rate": r(line["rates"]["three_rate"], 3),
                "three_per40": r(line["rates"]["three_per40"], 2),
                "three_pct": r(line["shoot"]["three_pct"], 3), "ft_pct": r(line["shoot"]["ft_pct"], 3),
                "fta": line["shoot"]["fta"], "three_a": line["shoot"]["three_a"],
                "rim_pct": r(line["shoot"]["rim_pct"], 3), "mid_pct": r(line["shoot"]["mid_pct"], 3),
                "rim_per40": r(line["rates"]["rim_per40"], 2), "dunk_per40": r(line["rates"]["dunk_per40"], 2),
                "unast_per40": r(line["rates"]["unast_per40"], 2),
                "unast_three": r(line["rates"]["unast_three"], 3), "ast_to": r(line["rates"]["ast_to"], 2),
                "team_strength": r(line["team"], 3), "height_in": line["height_in"],
                "pts_pg": line["pts_pg"], "reb_pg": line["reb_pg"], "ast_pg": line["ast_pg"]}


def r(value, digits=3):
    return None if value is None else round(value, digits)


def main() -> None:
    global K_MINUTES, TARGET_DRAFT, FIT_DRAFTS, OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--k", type=float, default=K_MINUTES, help="minutes of shrinkage toward replacement")
    parser.add_argument("--no-interactions", action="store_true",
                        help="drop the age x college production terms (sensitivity check)")
    parser.add_argument("--backtest-2025", action="store_true",
                        help="fit on drafts 2009-2024 only and project the 2025 class as of its draft (scratch file)")
    args = parser.parse_args()
    K_MINUTES = args.k
    if args.backtest_2025:
        TARGET_DRAFT, FIT_DRAFTS = 2025, range(2009, 2025)
        OUT = ROOT / "output/rookie-fit/rookie_translation_2025_backtest.json"
        OUT.parent.mkdir(parents=True, exist_ok=True)
    if not args.no_interactions:
        MODELS["college"] = (*FEATURES, "age_x_obpm", "age_x_dbpm")
        MODELS["college_slot"] = (*MODELS["college"], "log_pick")
    examples, unmatched, by_player, ctx = assemble()
    print(f"drafted college players {FIT_DRAFTS.start}-{FIT_DRAFTS.stop - 1}: {len(examples)}; "
          f"set aside (slot/name disagreement) {sum(1 for u in unmatched if u[3] != 'no NBA rows')}")
    if args.debug:
        for u in unmatched:
            print("  unmatched", u)
        for e in examples:
            if e["minutes"] == 0 and e["pick"] <= 30:
                print("  first-rounder without minutes", e["draft"], e["pick"], e["name"], "ever", e["ever_nba"])
    report = {"drafts": [FIT_DRAFTS.start, FIT_DRAFTS.stop - 1], "players": len(examples),
              "held_out": {"fit": [FIT_DRAFTS.start, TRAIN_LAST], "scored": [TRAIN_LAST + 1, FIT_DRAFTS.stop - 1]},
              "k_minutes": K_MINUTES, "outcomes": {}}
    finals = {}
    for field in ("lebron", "o", "d", "bpm"):
        r_level = replacement(examples, field)
        ys, out = evaluate(examples, field, r_level)
        slot_pred = loyo(examples, ys, MODELS["slot"], 1)
        cs_ridge = out["college_slot"]["ridge"]
        cs_pred = loyo(examples, ys, MODELS["college_slot"], cs_ridge)
        final = fit(examples, ys, MODELS["college_slot"], cs_ridge)
        finals[field] = final
        sel, sel_n = selected_only(examples, field, MODELS["college_slot"])
        report["outcomes"][field] = {
            "replacement_level": round(r_level, 3), "models": out, "pick_bands": band_table(examples, field),
            "age_groups": age_check(examples, ys, slot_pred, cs_pred),
            "slot_residual_per_unit": residual_regression(examples, ys, slot_pred),
            "coefficients_standardized": coef_table(final),
            "coefficients_ignoring_selection": {"n": sel_n, "coef": sel},
            "outcome_sd": round(statistics.pstdev(ys), 3),
        }
        if field == "lebron":
            report["examples_2025"] = sorted(
                [{"name": e["name"], "pick": e["pick"], "age": r(e["x"]["age"], 1), "minutes": e["minutes"],
                  "actual": r(e[field], 2), "shrunk": r(ys[i], 2), "slot_pred": r(slot_pred[i], 2),
                  "college_slot_pred": r(cs_pred[i], 2)}
                 for i, e in enumerate(examples) if e["draft"] == 2025], key=lambda d: d["pick"])
        print(f"\n{field}: replacement level {r_level:.2f}, outcome sd {statistics.pstdev(ys):.3f}")
        for name, res in out.items():
            print(f"  {name:13s} ridge {res['ridge']:>4}  held-out r {res['held_out']['r']:.3f} rmse "
                  f"{res['held_out']['rmse']:.3f}  (1000+ min raw r {res['held_out_1000_min_raw']['r']:.3f}, "
                  f"n {res['held_out_1000_min_raw']['n']})  LOYO r {res['leave_one_draft_out']['r']:.3f}")
        for b in report["outcomes"][field]["pick_bands"]:
            print("   ", b)
        for label, g in report["outcomes"][field]["age_groups"].items():
            print(f"    {label:42s} {g}")
        print("    slot residual per unit:", report["outcomes"][field]["slot_residual_per_unit"])
        print("    coefficients:", coef_table(final))
        print("    ignoring selection:", sel_n, sel)

    target, missing = target_class(by_player, ctx)
    projections = {}
    for pid, e in sorted(target.items(), key=lambda kv: kv[1]["pick"]):
        proj = {field: round(predict(finals[field], e), 3) for field in finals}
        line = e["line"]
        projections[pid] = {
            "name": e["name"], "pick": e["pick"], "age": round(e["x"]["age"], 2),
            "college": college_card(line),
            "projection": proj, "profile": e["profile"], "effective_minutes": e["effective_minutes"],
        }
    report["class_2026_without_college_line"] = missing
    print(f"\n{TARGET_DRAFT} class with a college line: {len(projections)}; without: {len(missing)} {missing}")
    for pid, p in sorted(projections.items(), key=lambda kv: -kv[1]["projection"]["lebron"]):
        c = p["college"]
        print(f"  {p['name'][:22]:22s} pick {p['pick']:>2} age {p['age']:4.1f}  college BPM {c['bpm']:5.1f} "
              f"(O {c['obpm']:4.1f} D {c['dbpm']:4.1f})  -> rookie LEBRON {p['projection']['lebron']:+.2f} "
              f"(O {p['projection']['o']:+.2f} D {p['projection']['d']:+.2f})  BPM {p['projection']['bpm']:+.2f}")
    bundle = {
        "version": 1,
        "method": "rookie_translation_v1",
        "sources": {
            "college": "Barttorvik player tables (barttorvik.com getadvstats CSV), final college season; team results",
            "nba_impact": "Basketball Index LEBRON by season (fanspo.com/bbi-role-explorer/lebron), cached at "
                          + str(LEBRON_CSV.relative_to(ROOT)),
            "nba_minutes_bpm_draft": "Basketball Reference advanced tables and draft pages (development_evidence.json)",
        },
        "outcome": "first NBA season impact per 100 possessions, shrunk toward the level of rookies who barely play "
                   "by minutes: (impact x minutes + replacement x 750) / (minutes + 750)",
        "age_production_interactions": not args.no_interactions,
        "models": {field: {"cols": m["cols"], "means": [round(v, 6) for v in m["means"]],
                           "sds": [round(v, 6) for v in m["sds"]], "beta": [round(v, 6) for v in m["beta"]]}
                   for field, m in finals.items()},
        "report": report,
        "class_2026": projections,
    }
    if not args.no_write:
        OUT.write_text(json.dumps(bundle, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
