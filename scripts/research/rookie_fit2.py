#!/usr/bin/env python3
"""ROOKIE-FIT-2: a rookie's day-one ABILITY (impact per 100 possessions if he plays), not his playing time.

The first attempt (rookie_fit.py) fitted rookie impact pulled toward a bench level by minutes played, so a rookie who
sat behind veterans counted as a bad player and the whole class bunched near the floor. Here:

  * Target: first-season Basketball Index LEBRON (offense, defense, total) and Basketball Reference box plus-minus,
    as measured, for rookies who played (300+ minutes). No pull toward a floor.
  * Noise: each player's season weighs by how much it says (minutes / (minutes + 500)); a short season is noisier,
    not worse.
  * Who gets minutes: the players who play are not a random draw (teams see practice; a second-rounder who plays is
    a good one). A selection model (chance of playing 300+ minutes from the same evidence) gives each player the
    expected size of that bias (the inverse Mills ratio; Heckman's two-step correction), which enters the impact fit as
    a separate term. The ability estimate leaves it out: what the player would show if he played regardless.
  * Evidence: final college season (Barttorvik), age and age x production, draft slot, and (2015-2025, first round)
    a public big-board rank, the scouts' view. Ridge regression, strength chosen by leaving one draft out.
  * Checks: fit 2009-2019, score 2020-2025; leave one draft out; the 2025 class from a fit on 2009-2024.

    PYTHONPATH=src .venv/bin/python scripts/research/rookie_fit2.py [--backtest-2025] [--no-write]

Writes data/research/rookie_translation_2026.json (method rookie_translation_v2; same shape the builder reads, so the
college skill-shape mapping and every later step are unchanged) with each rookie's ability projection and its parts.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
sys.path.insert(0, str(ROOT / "src"))

import real_prospects as rp  # noqa: E402
import rookie_fit as rf  # noqa: E402

OUT = ROOT / "data/research/rookie_translation_2026.json"
SCOUTING = ROOT / "data/research/rookie_scouting_2026.json"
EARLY = ROOT / "data/research/rookie_real_lines.json"
BOARDS_HIST = ROOT / "data/research/draft_boards/real_board_vs_pick_2015_2025.csv"
PLAYED_MIN = 300.0          # a season long enough for a rookie impact measure to mean something
K_RELIABILITY = 500.0       # weight of a season in the fit: minutes / (minutes + 500)
TRAIN_LAST = 2019
FIELDS = ("o", "d", "lebron", "bpm")
COLLEGE = (*rf.FEATURES, "age_x_obpm", "age_x_dbpm")
MODELS = {"slot": ("log_pick",), "college": COLLEGE, "college_slot": (*COLLEGE, "log_pick")}

SQRT2 = math.sqrt(2.0)


def phi(z):
    return math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)


def Phi(z):
    return 0.5 * (1 + math.erf(z / SQRT2))


def mills(index_logit: float) -> float:
    """Inverse Mills ratio from a logistic index (probit scale ~ logit / 1.7)."""
    z = max(-6.0, min(8.0, index_logit / 1.7))
    return phi(z) / max(1e-9, Phi(z))


def played(e, field) -> bool:
    return e["minutes"] >= PLAYED_MIN and e[field] is not None


# ------------------------------------------------------------------------------------------------ board ranks


def load_board_history() -> dict[tuple[int, str], int]:
    out = {}
    with BOARDS_HIST.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            out[(int(row["year"]), rf.key(row["player"]))] = int(row["board_rank"])
    return out


def attach_boards(examples, boards):
    """First-round players of 2015-2025: the public board rank (unranked on a top-30 board -> 40)."""
    for e in examples:
        e["board"] = None
        if 2015 <= e["draft"] <= 2025:
            e["board"] = boards.get((e["draft"], rf.key(e["name"])), 40)


def derived(e) -> dict:
    d = rf.with_derived(e)
    if e.get("board") is not None:
        d["log_board"] = math.log(e["board"])
    d["mills"] = e.get("_mills", 0.0)
    return d


def design(examples, cols):
    return [[derived(e)[c] for c in cols] for e in examples]


def fit_linear(examples, ys, cols, ridge, weights=None):
    raw = design(examples, cols)
    means, sds = rp.standardizer(raw)
    z = [[(v - m) / s for v, m, s in zip(r, means, sds)] for r in raw]
    return {"cols": list(cols), "means": means, "sds": sds, "beta": rp.linear_fit(z, ys, ridge=ridge, w=weights)}


def predict(model, e, with_mills=False) -> float:
    x = derived(e)
    if not with_mills:
        x["mills"] = 0.0
    return model["beta"][0] + sum(b * (x[c] - m) / s for b, c, m, s in
                                  zip(model["beta"][1:], model["cols"], model["means"], model["sds"]))


def fit_selection(examples, field, cols, ridge=3.0):
    raw = design(examples, cols)
    means, sds = rp.standardizer(raw)
    z = [[(v - m) / s for v, m, s in zip(r, means, sds)] for r in raw]
    beta = rp.logistic_fit(z, [int(played(e, field)) for e in examples], [1.0] * len(examples), ridge=ridge)
    return {"cols": list(cols), "means": means, "sds": sds, "beta": beta}


def selection_index(model, e) -> float:
    x = derived(e)
    return model["beta"][0] + sum(b * (x[c] - m) / s for b, c, m, s in
                                  zip(model["beta"][1:], model["cols"], model["means"], model["sds"]))


def heckman(train, field, cols, ridge, correct=True):
    """Two-step: selection model on every drafted player, then the weighted impact fit on those who played with the
    inverse Mills ratio as an extra term. Returns (selection model, impact model)."""
    sel = fit_selection(train, field, cols)
    for e in train:
        e["_mills"] = mills(selection_index(sel, e))
    rows = [e for e in train if played(e, field)]
    ys = [e[field] for e in rows]
    w = [e["minutes"] / (e["minutes"] + K_RELIABILITY) for e in rows]
    out_cols = (*cols, "mills") if correct else cols
    return sel, fit_linear(rows, ys, out_cols, ridge, w)


def project(sel, model, e, with_mills=False):
    e["_mills"] = mills(selection_index(sel, e))
    return predict(model, e, with_mills)


def wcorr(xs, ys, ws):
    mx = sum(x * w for x, w in zip(xs, ws)) / sum(ws)
    my = sum(y * w for y, w in zip(ys, ws)) / sum(ws)
    cov = sum(w * (x - mx) * (y - my) for x, y, w in zip(xs, ys, ws))
    vx = sum(w * (x - mx) ** 2 for x, w in zip(xs, ws))
    vy = sum(w * (y - my) ** 2 for y, w in zip(ys, ws))
    return cov / math.sqrt(vx * vy)


def score(pairs):
    """pairs: (prediction, actual, minutes). Correlation weighted by reliability, plain correlation, Spearman."""
    p, a, m = zip(*pairs)
    w = [x / (x + K_RELIABILITY) for x in m]
    return {"n": len(pairs), "r_weighted": round(wcorr(p, a, w), 3), "r": round(statistics.correlation(p, a), 3),
            "spearman": round(rp.spearman(list(p), list(a)), 3),
            "rmse": round(math.sqrt(statistics.fmean((x - y) ** 2 for x, y in zip(p, a))), 3)}


def loyo_pred(examples, field, cols, ridge, correct=True):
    pred = {}
    for year in sorted({e["draft"] for e in examples}):
        train = [e for e in examples if e["draft"] != year]
        sel, model = heckman(train, field, cols, ridge, correct)
        for e in examples:
            if e["draft"] == year:
                pred[id(e)] = (project(sel, model, e, False), project(sel, model, e, True))
    return pred


def choose_ridge(examples, field, cols, correct=True):
    best = None
    for ridge in (3, 10, 30, 100, 300):
        pred = loyo_pred(examples, field, cols, ridge, correct)
        rows = [e for e in examples if played(e, field)]
        w = [e["minutes"] / (e["minutes"] + K_RELIABILITY) for e in rows]
        err = sum(wi * (pred[id(e)][1] - e[field]) ** 2 for e, wi in zip(rows, w)) / sum(w)
        if best is None or err < best[1] - 1e-9:
            best = (ridge, err)
    return best[0]


def evaluate(examples, field, label_cols, correct=True):
    out = {}
    for name, cols in label_cols.items():
        pool = [e for e in examples if all(c != "log_board" or e.get("board") is not None for c in cols)]
        ridge = choose_ridge(pool, field, cols, correct)
        train = [e for e in pool if e["draft"] <= TRAIN_LAST]
        test = [e for e in pool if e["draft"] > TRAIN_LAST and played(e, field)]
        res = {"ridge": ridge, "players": len(pool)}
        if train and test and len({e["draft"] for e in train}) > 2:
            sel, model = heckman(train, field, cols, ridge, correct)
            res["held_out"] = score([(project(sel, model, e, True), e[field], e["minutes"]) for e in test])
            res["held_out_1000"] = score([(project(sel, model, e, True), e[field], e["minutes"])
                                          for e in test if e["minutes"] >= 1000])
        lo = loyo_pred(pool, field, cols, ridge, correct)
        res["leave_one_draft_out"] = score([(lo[id(e)][1], e[field], e["minutes"]) for e in pool if played(e, field)])
        out[name] = res
    return out


def coefs(model):
    return {c: round(b, 4) for c, b in zip(model["cols"], model["beta"][1:])}


# ------------------------------------------------------------------------------------------------ main


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest-2025", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--fit-only", action="store_true", help="print the fit and checks, no class projection")
    parser.add_argument("--quick", action="store_true", help="skip the held-out checks (ridge 30, as they chose)")
    args = parser.parse_args()
    if args.backtest_2025:
        rf.TARGET_DRAFT, rf.FIT_DRAFTS = 2025, range(2009, 2025)
        OUT = ROOT / "output/rookie-fit-2/rookie_translation_2025_backtest.json"
        OUT.parent.mkdir(parents=True, exist_ok=True)
    examples, unmatched, by_player, ctx = rf.assemble()
    attach_boards(examples, load_board_history())
    print(f"drafted college players {rf.FIT_DRAFTS.start}-{rf.FIT_DRAFTS.stop - 1}: {len(examples)}; "
          f"played {PLAYED_MIN:.0f}+ minutes: {sum(played(e, 'lebron') for e in examples)}")
    report = {"drafts": [rf.FIT_DRAFTS.start, rf.FIT_DRAFTS.stop - 1], "players": len(examples),
              "played_min": PLAYED_MIN, "k_reliability": K_RELIABILITY, "outcomes": {}}
    finals, sels = {}, {}
    for field in FIELDS:
        if args.quick:      # the checks chose ridge 30 for every outcome (2026-11-22); skip them while iterating
            res, res_uncorrected, res_board = {"college_slot": {"ridge": 30, "leave_one_draft_out": {}}}, {}, {}
        else:
            res = evaluate(examples, field, MODELS)
            res_uncorrected = evaluate(examples, field, {"college_slot": MODELS["college_slot"]}, correct=False)
            board_cols = {"college_slot_2015": MODELS["college_slot"],
                          "college_slot_board_2015": (*MODELS["college_slot"], "log_board")}
            first_round = [e for e in examples if e.get("board") is not None and e["pick"] <= 30]
            res_board = evaluate(first_round, field, board_cols)
        ridge = res["college_slot"]["ridge"]
        sel, model = heckman(examples, field, MODELS["college_slot"], ridge)
        _, model_raw = heckman(examples, field, MODELS["college_slot"], ridge, correct=False)
        finals[field], sels[field] = model, sel
        report["outcomes"][field] = {"models": res, "uncorrected": res_uncorrected, "first_round_board": res_board,
                                     "coefficients": coefs(model), "coefficients_uncorrected": coefs(model_raw),
                                     "selection_coefficients": coefs(sel)}
        print(f"\n{field}: ridge {ridge}")
        for name, r in {**res, **{"uncorrected " + k: v for k, v in res_uncorrected.items()},
                        **{"1st round " + k: v for k, v in res_board.items()}}.items():
            print(f"  {name:36s} held-out {r.get('held_out')}\n  {'':36s} 1000+ {r.get('held_out_1000')}\n"
                  f"  {'':36s} LOYO {r['leave_one_draft_out']}")
        print("  coefficients:", coefs(model))
        print("  selection:", coefs(sel))
    # How much the correction moves people, by pick band (ability vs what the played sample would suggest).
    bands = []
    for lo, hi in rf.PICK_BANDS:
        rows = [e for e in examples if lo <= e["pick"] <= hi]
        a = [project(sels["lebron"], finals["lebron"], e) for e in rows]
        c = [project(sels["lebron"], finals["lebron"], e, True) for e in rows]
        real = [e["lebron"] for e in rows if played(e, "lebron")]
        bands.append({"picks": f"{lo}-{hi}", "n": len(rows), "share_played": round(len(real) / len(rows), 3),
                      "ability_mean": round(statistics.fmean(a), 2), "if_played_mean": round(statistics.fmean(c), 2),
                      "real_mean_if_played": round(statistics.fmean(real), 2) if real else None,
                      "ability_sd": round(statistics.pstdev(a), 2)})
    report["pick_bands"] = bands
    print("\nby pick band (total impact):")
    for b in bands:
        print("  ", b)
    if args.fit_only:
        return
    target, missing = rf.target_class(by_player, ctx)
    scouting = None if args.backtest_2025 else load_scouting()
    early = None if args.backtest_2025 else load_early()
    if early:
        report["early_games"] = {k: v for k, v in early.items() if k != "rookies"}
    class_out = {pid: class_entry(e, sels, finals, scouting, early)
                 for pid, e in sorted(target.items(), key=lambda kv: kv[1]["pick"])}
    report["class_without_college_line"] = missing
    bundle = {
        "version": 2, "method": "rookie_translation_v2",
        "sources": {
            "college": "Barttorvik player tables (barttorvik.com getadvstats CSV), final college season; team results",
            "nba_impact": "Basketball Index LEBRON by season (fanspo.com/bbi-role-explorer/lebron), cached at "
                          + str(rf.LEBRON_CSV.relative_to(ROOT)),
            "nba_minutes_bpm_draft": "Basketball Reference advanced tables and draft pages (development_evidence.json, "
                                     + str(EARLY.relative_to(ROOT)) + ")",
            "scouting": str(SCOUTING.relative_to(ROOT)),
            "early_games": str(EARLY.relative_to(ROOT)) + " (season_2027)",
        },
        "outcome": ("first NBA season impact per 100 possessions as measured, rookies with 300+ minutes, weighted by "
                    "minutes / (minutes + 500); selection into playing corrected (two-step, inverse Mills ratio) and "
                    "left out of the projection: ability if he plays, not playing time"),
        "blend": {"scout_rank": "geometric mean of draft slot and consensus board rank (history: a board rank carries "
                                "the same information as the slot; neither adds to the other)",
                  "readiness_nudge": READINESS_NUDGE, "early_games_k_minutes": K_EARLY},
        "models": {f: {"selection": {k: (v if k == "cols" else [round(x, 6) for x in v]) for k, v in sels[f].items()},
                       "impact": {k: (v if k == "cols" else [round(x, 6) for x in v]) for k, v in finals[f].items()}}
                   for f in FIELDS},
        "report": report,
        "class_2026": class_out,
    }
    if not args.no_write:
        OUT.write_text(json.dumps(bundle, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {OUT.relative_to(ROOT)}")
    print(f"\n{rf.TARGET_DRAFT} class ({len(class_out)} with a college line; without: {missing})")
    for pid, c in sorted(class_out.items(), key=lambda kv: -kv[1]["projection"]["lebron"]):
        parts = c["projection_parts"]
        fit, rd, g = parts["college_fit"], parts["readiness"], parts["early_games"]
        print(f"  {c['name'][:22]:22s} pick {c['pick']:>2} scout {parts['scout_rank']:5.1f} age {c['age']:4.1f}  "
              f"fit {fit['o'] + fit['d']:+.2f}  ready {rd['o'] + rd['d']:+.2f} ({rd['tier'][:5]})  "
              f"games {g['o'] + g['d']:+.2f} ({g['minutes']:.0f} min)  -> {c['projection']['lebron']:+.2f} "
              f"(O {c['projection']['o']:+.2f} D {c['projection']['d']:+.2f})")


# ------------------------------------------------------------------------------------------------ 2026 evidence

# Readiness write-ups (data/research/rookie_scouting_2026.json): a small nudge, in LEBRON points per 100 possessions.
# No history exists to fit it, so it stays well inside the fit's own error (about 1.1 points): a fifth of a point in
# all, mostly offense (the readiness notes are mostly about polish with the ball).
READINESS_NUDGE = {"ready_now": {"o": 0.15, "d": 0.05}, "project": {"o": -0.15, "d": -0.05}}
K_EARLY = 1500.0            # this season's games: weight minutes / (minutes + 1500)
EARLY_MIN_MINUTES = 100.0   # below this a box plus-minus is mostly noise (one hot or cold night); not used
EARLY_BPM_CAP = 10.0        # offensive / defensive box plus-minus held inside +-10 before conversion
NAME_FIX = {"labaron philon": "labaron philon jr", "christian anderson": "christian anderson jr"}


def load_scouting():
    if not SCOUTING.exists():
        return None
    data = json.loads(SCOUTING.read_text(encoding="utf-8"))
    return {"consensus": {rf.key(n): v for n, v in data["consensus"].items()},
            "readiness": {rf.key(n): v for n, v in data["readiness"].items()}}


def load_early():
    """This season's rookie box plus-minus so far, and the lines that put a rookie's offensive / defensive box
    plus-minus on the LEBRON scale, fitted on rookies 2015-16 to 2025-26 with 1000+ minutes."""
    if not EARLY.exists():
        return None
    data = json.loads(EARLY.read_text(encoding="utf-8"))
    lebron = {}
    with rf.LEBRON_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            lebron[(int(row["Season"]), rf.key(row["Player"]))] = (float(row["O-LEBRON"]), float(row["D-LEBRON"]))
    pairs = []
    for season, rows in data["classes"].items():
        for r in rows:
            got = lebron.get((int(season), rf.key(r["name"])))
            if got and r["mp"] >= 1000 and r.get("obpm") is not None:
                pairs.append((r["obpm"], r["dbpm"], *got))
    lines = {}
    for i, side in ((0, "o"), (1, "d")):
        xs, ys = [p[i] for p in pairs], [p[2 + i] for p in pairs]
        slope = statistics.covariance(xs, ys) / statistics.variance(xs)
        lines[side] = (round(statistics.fmean(ys) - slope * statistics.fmean(xs), 4), round(slope, 4),
                       round(statistics.correlation(xs, ys), 3))
    season = data["season_2027"]
    return {"as_of": season["as_of"], "conversion": lines, "conversion_players": len(pairs),
            "rookies": {rf.key(r["name"]): {**r, "team_context": season["teams"].get(r.get("team"))}
                        for r in season["rookies"]}}


def class_entry(e, sels, finals, scouting, early):
    k = rf.key(e["name"])
    cons = (scouting or {}).get("consensus", {}).get(k)
    scout_rank = math.exp((math.log(e["pick"]) + math.log(cons["geometric_mean_rank"])) / 2) if cons else e["pick"]
    fit = {f: round(project(sels[f], finals[f], dict(e, pick=scout_rank)), 3) for f in FIELDS}
    tier = ((scouting or {}).get("readiness", {}).get(k) or {}).get("tier", "unknown")
    nudge = READINESS_NUDGE.get(tier, {"o": 0.0, "d": 0.0})
    proj = {"o": fit["o"] + nudge["o"], "d": fit["d"] + nudge["d"]}
    games = {"o": 0.0, "d": 0.0, "minutes": 0.0, "weight": 0.0}
    row = (early["rookies"].get(k) or early["rookies"].get(NAME_FIX.get(k, ""))) if early else None
    if row and (row.get("mp") or 0) >= EARLY_MIN_MINUTES and row.get("obpm") is not None:
        w = row["mp"] / (row["mp"] + K_EARLY)
        conv = early["conversion"]
        seen = {s: conv[s][0] + conv[s][1] * max(-EARLY_BPM_CAP, min(EARLY_BPM_CAP, row["obpm" if s == "o" else "dbpm"]))
                for s in ("o", "d")}
        games = {"o": round(w * (seen["o"] - proj["o"]), 3), "d": round(w * (seen["d"] - proj["d"]), 3),
                 "minutes": row["mp"], "weight": round(w, 3), "games": row["g"], "team": row.get("team"),
                 "obpm": row["obpm"], "dbpm": row["dbpm"], "bpm": row.get("bpm"),
                 "seen_o": round(seen["o"], 3), "seen_d": round(seen["d"], 3),
                 "pts_per36": round(36 * row["pts"] / row["mp"], 1), "usg": row.get("usg_pct"),
                 "ts": row.get("ts_pct"), "team_net": (row.get("team_context") or {}).get("net_rtg")}
        proj = {s: proj[s] + games[s] for s in ("o", "d")}
    proj = {s: round(v, 3) for s, v in proj.items()}
    proj["lebron"] = round(proj["o"] + proj["d"], 3)
    proj["bpm"] = fit["bpm"]
    return {"name": e["name"], "pick": e["pick"], "age": round(e["x"]["age"], 2), "college": rf.college_card(e["line"]),
            "projection": proj,
            "projection_parts": {"scout_rank": round(scout_rank, 2), "consensus_rank": cons, "college_fit": fit,
                                 "readiness": {"tier": tier, **nudge}, "early_games": games},
            "profile": e["profile"], "effective_minutes": e["effective_minutes"]}


if __name__ == "__main__":
    main()
