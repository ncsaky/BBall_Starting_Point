"""A box-score impact estimate the game can compute from its own season totals, on the Box Plus/Minus scale.

The real development evidence (data/research/development_evidence.json) measures growth with Basketball Reference's
Box Plus/Minus (BPM). The game's season totals keep minutes, points, rebounds, assists, steals, blocks, turnovers and
shooting (no offensive/defensive rebound split, no fouls, no plus-minus), so the exact BPM formula cannot be rebuilt.
Instead this fits real BPM on the same fields the game keeps: ESPN season totals for today's players
(data/research/player_career_stats.json, 2015-16 to 2025-26) matched by name and season to the BPM panel.

The estimate then measures real and simulated seasons the same way: year-over-year change for players with 1,000+
minutes in both seasons, by age and by starting third among same-age qualifiers.

    PYTHONPATH=src .venv/bin/python scripts/research/dev_curve_box.py fit
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics as st
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "data" / "research" / "development_evidence.json"
CAREER = ROOT / "data" / "research" / "player_career_stats.json"
FIT_OUT = ROOT / "data" / "research" / "dev_curve_box_bpm.json"
QUALIFY = 1000.0
FIT_MINUTES = 500.0
FIRST_FIT_SEASON = 2016   # season-end year; earlier seasons hold too few of today's players


def norm_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z ]", "", text.replace("-", " "))
    words = [w for w in text.split() if w not in {"jr", "sr", "ii", "iii", "iv", "v"}]
    return " ".join(words)


FEATURES = ("mpg", "pts", "scoring_eff", "shots", "fg3a", "ast", "reb", "stl", "blk", "tov", "ast_x_reb")


def features(totals: Mapping[str, Any]) -> list[float] | None:
    """Per-36 rates (and minutes per game) from one season's totals."""
    minutes = float(totals.get("minutes") or 0.0)
    games = float(totals.get("games") or 0.0)
    if minutes <= 0 or games <= 0:
        return None
    per = 36.0 / minutes
    g = lambda key: float(totals.get(key) or 0.0) * per
    shots = g("fga") + 0.44 * g("fta")
    # Points above a fixed 57% true-shooting line on the player's own shot volume (BPM's efficiency term).
    scoring_eff = g("points") - 2.0 * 0.57 * shots
    ast, reb = g("assists"), g("rebounds")
    return [minutes / games, g("points"), scoring_eff, shots, g("fg3a"), ast, reb, g("steals"), g("blocks"),
            g("turnovers"), math.sqrt(max(ast, 0.0) * max(reb, 0.0))]


def real_panel() -> list[dict[str, Any]]:
    """ESPN season totals matched to the BPM panel (name + season end year; minutes within 5%)."""
    evidence = json.loads(EVIDENCE.read_text())
    cols = evidence["public_inputs"]["season_columns"]
    bpm: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for raw in evidence["public_inputs"]["seasons"]:
        row = dict(zip(cols, raw))
        bpm[(norm_name(row["name"]), int(row["year"]))].append(row)
    career = json.loads(CAREER.read_text())["players"]
    out = []
    for player in career.values():
        key_name = norm_name(player.get("name") or "")
        for season in player.get("seasons") or []:
            year = int(str(season["season"])[:4]) + 1
            candidates = [r for r in bpm.get((key_name, year), [])
                          if abs(float(r["minutes"]) - float(season.get("minutes") or 0)) <= 0.05 * max(1.0, float(r["minutes"])) + 30]
            if len(candidates) != 1:
                continue
            ref = candidates[0]
            out.append({"player": ref["player"], "name": ref["name"], "year": year, "age": int(ref["age"]),
                        "minutes": float(ref["minutes"]), "bpm": float(ref["bpm"]), "totals": season,
                        "draft_position": player.get("draft_position"), "draft_year": player.get("draft_year")})
    return out


def _solve(xtx: list[list[float]], xty: list[float]) -> list[float]:
    n = len(xty)
    a = [row[:] + [xty[i]] for i, row in enumerate(xtx)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(n):
            if r != col and a[col][col]:
                f = a[r][col] / a[col][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col])]
    return [a[i][n] / a[i][i] for i in range(n)]


def fit(rows: Iterable[Mapping[str, Any]], ridge: float = 1e-3) -> dict[str, Any]:
    """Minutes-weighted least squares of BPM on the box features (seasons with 500+ minutes)."""
    data = [(features(r["totals"]), r["bpm"], r["minutes"]) for r in rows
            if r["year"] >= FIRST_FIT_SEASON and r["minutes"] >= FIT_MINUTES]
    data = [(x, y, w) for x, y, w in data if x is not None]
    means = [sum(x[i] * w for x, _, w in data) / sum(w for *_, w in data) for i in range(len(FEATURES))]
    sds = [math.sqrt(sum(w * (x[i] - means[i]) ** 2 for x, _, w in data) / sum(w for *_, w in data)) or 1.0
           for i in range(len(FEATURES))]
    k = len(FEATURES) + 1
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for x, y, w in data:
        z = [1.0] + [(v - m) / s for v, m, s in zip(x, means, sds)]
        for i in range(k):
            xty[i] += w * z[i] * y
            for j in range(k):
                xtx[i][j] += w * z[i] * z[j]
    total = sum(w for *_, w in data)
    for i in range(1, k):
        xtx[i][i] += ridge * total
    beta = _solve(xtx, xty)
    model = {"features": list(FEATURES), "mean": means, "sd": sds, "intercept": beta[0], "weights": beta[1:]}
    preds = [estimate(model, None, x) for x, *_ in data]
    ys = [y for _, y, _ in data]
    ws = [w for *_, w in data]
    ybar = sum(y * w for y, w in zip(ys, ws)) / total
    ss_res = sum(w * (y - p) ** 2 for y, p, w in zip(ys, preds, ws))
    ss_tot = sum(w * (y - ybar) ** 2 for y, w in zip(ys, ws))
    model["fit"] = {"rows": len(data), "seasons": f"{FIRST_FIT_SEASON}-2026", "weighted_r2": round(1 - ss_res / ss_tot, 4),
                    "residual_sd": round(math.sqrt(ss_res / total), 3)}
    return model


def estimate(model: Mapping[str, Any], totals: Mapping[str, Any] | None, x: list[float] | None = None) -> float | None:
    x = features(totals) if x is None else x
    if x is None:
        return None
    return model["intercept"] + sum(w * (v - m) / s for w, v, m, s in zip(model["weights"], x, model["mean"], model["sd"]))


def load_model() -> dict[str, Any]:
    return json.loads(FIT_OUT.read_text())


# ---- shared measurement ---------------------------------------------------------------------------------------------
def thirds(values: Mapping[str, float]) -> dict[str, str]:
    """Bottom / middle / top third by value (ties broken by id, as the evidence breaks them by player id)."""
    order = sorted(values, key=lambda k: (values[k], k))
    n = len(order)
    out = {}
    for i, key in enumerate(order):
        out[key] = "bottom" if i < n / 3 else "middle" if i < 2 * n / 3 else "top"
    return out


def development_table(seasons: Mapping[int, Mapping[str, Mapping[str, Any]]], value_key: str = "bpm",
                      qualify: float = QUALIFY) -> dict[int, dict[str, list[float]]]:
    """Year-over-year change by starting age and starting third. seasons[year][player] = {age, minutes, value_key}."""
    table: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    years = sorted(seasons)
    for year in years:
        nxt = seasons.get(year + 1)
        if not nxt:
            continue
        qualified = {pid: r for pid, r in seasons[year].items() if r["minutes"] >= qualify and r.get(value_key) is not None}
        by_age: dict[int, dict[str, float]] = defaultdict(dict)
        for pid, r in qualified.items():
            by_age[int(r["age"])][pid] = r[value_key]
        for age, values in by_age.items():
            levels = thirds(values)
            for pid, level in levels.items():
                after = nxt.get(pid)
                if not after or after["minutes"] < qualify or after.get(value_key) is None:
                    continue
                delta = after[value_key] - values[pid]
                table[age]["all"].append(delta)
                table[age][level].append(delta)
    return table


def summarize_table(table: Mapping[int, Mapping[str, list[float]]], ages: Iterable[int] = range(19, 37)) -> dict[str, Any]:
    out = {}
    for age in ages:
        cell = table.get(age) or {}
        out[str(age)] = {k: {"n": len(v), "mean": round(st.mean(v), 2)} for k, v in cell.items() if v}
    return out


def prior_level_table(seasons: Mapping[int, Mapping[str, Mapping[str, Any]]], value_key: str = "bpm",
                      qualify: float = QUALIFY) -> dict[int, dict[str, list[float]]]:
    """Change from season t to t+1, with the starting third taken from season t-1.

    Thirds picked on the same season the change starts from pull the top down and the bottom up by measurement noise
    alone (a lucky season is followed by an ordinary one). Picking the third one season earlier removes most of that,
    so this table is the closer guide to how much underlying ability changes at each level. Players need the minutes
    cut in all three seasons; age is the age in season t."""
    table: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for year in sorted(seasons):
        prev, cur, nxt = seasons.get(year - 1), seasons[year], seasons.get(year + 1)
        if not prev or not nxt:
            continue
        by_age: dict[int, dict[str, float]] = defaultdict(dict)
        for pid, r in cur.items():
            p, n = prev.get(pid), nxt.get(pid)
            if (r["minutes"] >= qualify and p and n and p["minutes"] >= qualify and n["minutes"] >= qualify
                    and None not in (p.get(value_key), r.get(value_key), n.get(value_key))):
                by_age[int(r["age"])][pid] = p[value_key]
        for age, values in by_age.items():
            for pid, level in thirds(values).items():
                delta = nxt[pid][value_key] - cur[pid][value_key]
                table[age]["all"].append(delta)
                table[age][level].append(delta)
    return table


def evidence_seasons() -> dict[int, dict[str, dict[str, Any]]]:
    evidence = json.loads(EVIDENCE.read_text())
    cols = evidence["public_inputs"]["season_columns"]
    games = {int(k): int(v) for k, v in evidence["definitions"]["schedule_games_overrides"].items()}
    seasons: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for raw in evidence["public_inputs"]["seasons"]:
        row = dict(zip(cols, raw))
        if row["bpm"] is None or row["minutes"] is None:
            continue
        year = int(row["year"])
        # The minutes cut is prorated in shortened seasons; scaling minutes to 82 games applies the same cut.
        seasons[year][row["player"]] = {"age": int(row["age"]), "minutes": float(row["minutes"]) * 82 / games.get(year, 82),
                                        "bpm": float(row["bpm"]), "name": row["name"]}
    return seasons


def peak_age(table: Mapping[int, Mapping[str, list[float]]], start: int = 19, end: int = 36) -> int | None:
    """Running sum of mean changes from `start`, smoothed over three ages; the age where it is highest."""
    index, level = {start: 0.0}, 0.0
    for age in range(start, end):
        values = (table.get(age) or {}).get("all") or []
        level += st.mean(values) if values else 0.0
        index[age + 1] = level
    smooth = {a: st.mean([index[b] for b in (a - 1, a, a + 1) if b in index]) for a in index}
    return max(smooth, key=smooth.get) if smooth else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fit", "real", "prior"))
    args = parser.parse_args()
    if args.command == "prior":
        # 2004-05 to 2025-26 (the evidence's study window); level from the season before.
        seasons = {y: s for y, s in evidence_seasons().items() if y >= 2004}
        same, prior = development_table({y: s for y, s in seasons.items() if y >= 2005}, "bpm"), prior_level_table(seasons, "bpm")
        print("age | same-season thirds: bottom middle top | prior-season thirds: n bottom middle top all")
        for age in range(19, 37):
            a, b = same.get(age) or {}, prior.get(age) or {}
            m = lambda c, k: f"{st.mean(c[k]):+.2f}" if c.get(k) else "  -  "
            print(age, m(a, "bottom"), m(a, "middle"), m(a, "top"), "|", len(b.get("all", [])),
                  m(b, "bottom"), m(b, "middle"), m(b, "top"), m(b, "all"))
        return
    rows = real_panel()
    if args.command == "fit":
        model = fit(rows)
        FIT_OUT.write_text(json.dumps(model, indent=1) + "\n")
        print(json.dumps(model["fit"]), dict(zip(model["features"], [round(w, 3) for w in model["weights"]])))
        return
    model = load_model()
    seasons: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        seasons[r["year"]][r["player"]] = {"age": r["age"], "minutes": r["minutes"], "bpm": r["bpm"],
                                           "box": estimate(model, r["totals"])}
    for key in ("bpm", "box"):
        table = development_table({y: s for y, s in seasons.items() if y >= FIRST_FIT_SEASON}, key)
        print(key, "peak", peak_age(table))
        for age, cell in summarize_table(table, range(19, 35)).items():
            print(age, {k: (v["n"], v["mean"]) for k, v in cell.items()})


if __name__ == "__main__":
    main()
