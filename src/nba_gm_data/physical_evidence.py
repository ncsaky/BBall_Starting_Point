"""Measured evidence for functional strength (P08) and vertical / jump capacity (P10).

Until 2026-11-19 both inputs were position-and-body priors with no measurement behind them (jump height was 72 cm for
every guard-shaped body and 62 cm for every centre-shaped one; strength a grade with a spread of about 4 points). Two
kinds of real evidence now inform them, blended by how reliable each one is:

1. NBA Draft Combine tests (data/research/draft_combine_2000_2025.json, the NBA.com Strength & Agility tables):
   standing vertical leap (inches) for jump capacity and bench press reps at 185 lb for strength. They were measured
   at the combine, often years ago, so each result is moved to the player's current age along the game's own expected
   development curve for the matching physical rating (health.monthly_trait_delta, expected changes only): jump
   capacity follows the athletic curve (foot speed and agility), strength the general one (it holds up longer). The
   curve's rating points become inches or reps through the league spread of the rating and of the test.
2. In-game proxies, read against body size: how often a player dunks his close shots (Basketball-Reference), his
   blocks per 36 and offensive-rebound rate (2025-26), and Basketball Index's contact-finish rate, drive foul-drawn
   rate and putback scoring (recent seasons, local captures only). Each proxy model is a least-squares fit, on the
   players who also have a combine result, of the age-adjusted combine number on body size, position and the proxies;
   its out-of-fold error sets its weight.

Every player gets a size-and-position estimate (the same kind of fit with body measurements only; its error is the
widest, so it carries least weight). The final value is the precision-weighted mean of the estimates the player has:
combine result (error: the test's own noise plus a growing allowance per year since the combine), proxy model,
size model. Strength is stored as a grade (100 * logistic(1.31 z), the overlay curve, never clipped); jump capacity
as a standing-jump height in cm, as the record already was.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Mapping

COMBINE_FILE = "data/research/draft_combine_2000_2025.json"
VERSION = "physical_evidence_v1_2026_11_19"
SEASON_START = _dt.date(2026, 10, 21)
COMBINE_DAY = (5, 15)
GRADE_SLOPE = 1.31
# Combine test noise (share of the between-player standard deviation): test-retest correlations of jump and bench
# tests are around 0.9, so about a third of a standard deviation of error.
TEST_NOISE_SD = 0.33
# Age adjustment uncertainty added per year since the combine (in between-player standard deviations).
AGING_NOISE_PER_YEAR = 0.06
FOLDS = 10
# The game's development curve each test follows (health.monthly_trait_delta).
AGING_TRAIT = {"P10": "foot_speed_lateral_agility", "P08": "rim_deterrence"}
TEST = {"P10": "standing_vertical_in", "P08": "bench_reps_185"}
PROXIES = {
    "P10": ("dunk_logit", "blocks36_log", "orb_pct_log"),
    "P08": ("contact_finish", "drive_foul_drawn", "putback_pts", "orb_pct_log"),
}
BBI_METRICS = {"contact_finish": "Contact Finish Rate", "drive_foul_drawn": "Drive Foul Drawn Rate",
               "putback_pts": "Stable Putback Points Per 75"}


def _normalize(name: str) -> str:
    from .input_estimator import _normalize as norm
    return norm(name)


def _measure(record: Mapping[str, Any] | None) -> float | None:
    try:
        return float(record["value"]["measurements"][0]["value"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _current(record: Mapping[str, Any] | None) -> float:
    value = (record or {}).get("value") or {}
    if "display_grade" in value:
        return float(value["display_grade"]["grade"])
    return float(value["measurements"][0]["value"]) / 2.54 if value.get("measurements") else 0.0   # cm -> inches


def _age(birthdate: str | None, on: _dt.date) -> float | None:
    try:
        born = _dt.date.fromisoformat(str(birthdate)[:10])
    except ValueError:
        return None
    return (on - born).days / 365.25


# --- small linear algebra (standard library only) -------------------------------------------------------------
def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        if abs(m[col][col]) < 1e-12:
            m[col][col] = 1e-12
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def _ridge(x: list[list[float]], y: list[float], lam: float = 1.0) -> list[float]:
    k = len(x[0])
    xtx = [[sum(r[p] * r[q] for r in x) + (lam if p == q and p > 0 else 0.0) for q in range(k)] for p in range(k)]
    xty = [sum(r[p] * v for r, v in zip(x, y)) for p in range(k)]
    return _solve(xtx, xty)


class LinearModel:
    """Standardized ridge regression with out-of-fold error (for the reliability weight)."""

    def __init__(self, names: tuple[str, ...], rows: list[tuple[dict[str, float], float]]):
        self.names = names
        self.mean = {n: fmean(r[n] for r, _ in rows) for n in names}
        self.sd = {n: (pstdev([r[n] for r, _ in rows]) or 1.0) for n in names}
        x = [self._row(r) for r, _ in rows]
        y = [v for _, v in rows]
        self.beta = _ridge(x, y)
        oof = [0.0] * len(rows)
        for fold in range(FOLDS):
            train = [i for i in range(len(rows)) if i % FOLDS != fold]
            beta = _ridge([x[i] for i in train], [y[i] for i in train])
            for i in range(len(rows)):
                if i % FOLDS == fold:
                    oof[i] = sum(b * v for b, v in zip(beta, x[i]))
        self.n = len(rows)
        self.oof_rmse = math.sqrt(fmean((a - b) ** 2 for a, b in zip(oof, y)))
        my = fmean(y)
        self.oof_r = (sum((a - fmean(oof)) * (b - my) for a, b in zip(oof, y))
                      / math.sqrt(sum((a - fmean(oof)) ** 2 for a in oof) * sum((b - my) ** 2 for b in y)))

    def _row(self, values: Mapping[str, float]) -> list[float]:
        return [1.0] + [(values[n] - self.mean[n]) / self.sd[n] for n in self.names]

    def predict(self, values: Mapping[str, float]) -> float:
        return sum(b * v for b, v in zip(self.beta, self._row(values)))

    def describe(self) -> dict[str, Any]:
        return {"inputs": list(self.names), "n": self.n, "oof_r": round(self.oof_r, 3), "oof_rmse": round(self.oof_rmse, 3),
                "standardized_coefficients": {n: round(b, 3) for n, b in zip(("constant",) + self.names, self.beta)}}


# --- evidence tables -------------------------------------------------------------------------------------------
def combine_matches(universe: Mapping[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    """player id -> combine row (name match; the combine year must fit his draft year, or his age if undrafted)."""
    path = Path(root) / COMBINE_FILE
    if not path.exists():
        return {}
    rows: dict[str, list[dict[str, Any]]] = {}
    for row in json.loads(path.read_text())["players"]:
        rows.setdefault(_normalize(row["name"]), []).append(row)
    out = {}
    for player in universe.get("players", []):
        candidates = rows.get(_normalize(player["name"]), [])
        fits = []
        for row in candidates:
            combine_age = _age(player.get("birthdate"), _dt.date(row["year"], *COMBINE_DAY))
            draft = player.get("draft_year")
            if draft and not (draft - 2 <= row["year"] <= draft):
                continue
            if combine_age is not None and not 17.5 <= combine_age <= 26.5:
                continue
            fits.append(row)
        if len(fits) == 1 or (fits and len({r["year"] for r in fits}) == 1):
            out[player["id"]] = max(fits, key=lambda r: sum(v is not None for v in r.values()))
        elif fits:   # tested twice (returned to school): the later, closer-to-now result
            out[player["id"]] = max(fits, key=lambda r: r["year"])
    return out


_CURVE_CACHE: dict[tuple[str, int, int], float] = {}


def expected_rating_change(trait: str, age_from: float, age_to: float) -> float:
    """Sum of the development model's expected monthly changes (rating points) for an average rotation player."""
    key = (trait, round(age_from * 12), round(age_to * 12))
    if key in _CURVE_CACHE:
        return _CURVE_CACHE[key]
    from .health import monthly_trait_delta
    player = {"id": "reference", "rotation_priority": "core_rotation"}
    total, current = 0.0, 50.0
    months = max(0, round((age_to - age_from) * 12))
    for m in range(months):
        age = age_from + (m + 0.5) / 12.0
        delta = monthly_trait_delta(player, trait, current, age, 24.0, {}, 0.0, 1, "2026-01", expected=True)
        total += delta
        current += delta
    _CURVE_CACHE[key] = total
    return total


def trait_spread(universe: Mapping[str, Any], trait: str) -> float:
    values = [float(t["value"]) for t in universe.get("traits", []) if t.get("trait_key") == trait and t.get("value") is not None]
    return pstdev(values) if len(values) > 30 else 10.0


def proxy_values(universe: Mapping[str, Any], root: Path, section: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """player id -> proxy name -> value (only the proxies he has)."""
    out: dict[str, dict[str, float]] = {p["id"]: {} for p in universe.get("players", [])}
    names = {_normalize(p["name"]): p["id"] for p in universe.get("players", [])}
    # Dunks per close attempt (Basketball-Reference), as a logit; at least 40 weighted close attempts.
    from .public_shot_evidence import DATA_FILE as BREF, dunk_rates
    bref = Path(root) / BREF
    if bref.exists():
        for key, r in dunk_rates(json.loads(bref.read_text())).items():
            pid = names.get(key)
            if pid and r["close"] >= 40:
                out[pid]["dunk_logit"] = math.log(r["rate"] / (1 - r["rate"]))
    # Blocks per 36 and offensive-rebound rate, 2025-26 rotation players.
    targets = Path(root) / "data/calibration/nba_2025_26_targets.json"
    if targets.exists():
        for pid, t in json.loads(targets.read_text())["players"].items():
            if pid in out and float(t.get("minutes") or 0) >= 500:
                if t.get("blocks_per36") is not None:
                    out[pid]["blocks36_log"] = math.log(float(t["blocks_per36"]) + 0.1)
                if t.get("orb_pct") is not None:
                    out[pid]["orb_pct_log"] = math.log(float(t["orb_pct"]) + 0.5)
    # Basketball Index (local captures only), recent seasons weighted like the other overlays; 500+ minutes.
    try:
        from .bbi_evidence import SEASON_WEIGHTS, collect_values
        table = collect_values(Path(root), set(BBI_METRICS.values()))
    except (OSError, ValueError, KeyError, ImportError):
        table = {}
    for proxy, metric in BBI_METRICS.items():
        sums: dict[str, list[float]] = {}
        for season, weight in SEASON_WEIGHTS.items():
            for value, minutes, cid in table.get((season, metric), {}).values():
                if cid in out and minutes >= 200:
                    w = weight * min(1.0, minutes / 1500.0)
                    acc = sums.setdefault(cid, [0.0, 0.0, 0.0])
                    acc[0] += w * value
                    acc[1] += w
                    acc[2] += minutes
        for cid, (num, den, minutes) in sums.items():
            if den > 0 and minutes >= 500:
                out[cid][proxy] = num / den
    return out


def body_values(section: Mapping[str, Any], universe: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    out = {}
    positions = {p["id"]: str(p.get("position") or "") for p in universe.get("players", [])}
    for pid, doc in section["players"].items():
        inputs = doc["inputs"]
        h, w, m = (_measure(inputs.get(i)) for i in ("P01", "P02", "P04"))
        if None in (h, w, m):
            continue
        pos = positions.get(pid, "")
        out[pid] = {"height": h, "wingspan": w, "mass": m,
                    "guard": 1.0 if pos in ("PG", "SG", "G") else 0.0, "big": 1.0 if pos in ("C", "PF", "FC") else 0.0}
    return out


# Bench press and arm length (overnight ratings review, 2026-11-20). The combine bench is reps to failure at a fixed
# 185 lb. A longer arm moves the bar further on every rep (more work per rep, a longer lever at the bottom), so a
# long-armed player of the same strength does fewer reps: the test penalises reach, which basketball rewards.
# Among the 74 tested players in the league, at the same body mass, log reps fall with log wingspan at an elasticity
# of -7.4 (standard error 3.1); height adds nothing once wingspan is in (-0.3, se 3.6). Work per rep alone
# (bar travel proportional to arm length) gives -1, the smallest effect physics allows. The fitted elasticity is
# blended with that physics value by precision (ARM_PRIOR, ARM_PRIOR_SD: a deliberately wide prior), then each
# tested player's reps are moved to the tested players' average wingspan before the age adjustment. Body mass keeps
# its effect: more muscle is real strength.
ARM_PRIOR = -1.0
ARM_PRIOR_SD = 3.0


def _ols(x: list[list[float]], y: list[float]) -> tuple[list[float], list[float]]:
    k = len(x[0])
    xtx = [[sum(r[p] * r[q] for r in x) for q in range(k)] for p in range(k)]
    inverse = [_solve(xtx, [1.0 if i == j else 0.0 for i in range(k)]) for j in range(k)]   # columns of the inverse
    beta = _solve(xtx, [sum(r[p] * v for r, v in zip(x, y)) for p in range(k)])
    residual = [v - sum(b * c for b, c in zip(beta, r)) for r, v in zip(x, y)]
    s2 = sum(e * e for e in residual) / max(1, len(y) - k)
    return beta, [math.sqrt(s2 * inverse[p][p]) for p in range(k)]


def arm_length_adjusted_reps(raw: Mapping[str, float], body: Mapping[str, Mapping[str, float]]
                             ) -> tuple[dict[str, float], dict[str, Any]]:
    """Bench reps moved to the tested players' average wingspan (same body mass); see ARM_PRIOR."""
    tested = [pid for pid, reps in raw.items() if reps > 0 and pid in body]
    if len(tested) < 30:
        return dict(raw), {"skipped": f"{len(tested)} tested players"}
    x = [[1.0, math.log(body[p]["wingspan"]), math.log(body[p]["mass"])] for p in tested]
    beta, se = _ols(x, [math.log(raw[p]) for p in tested])
    fitted, fitted_se = beta[1], se[1]
    w_fit, w_prior = 1.0 / fitted_se ** 2, 1.0 / ARM_PRIOR_SD ** 2
    elasticity = (w_fit * fitted + w_prior * ARM_PRIOR) / (w_fit + w_prior)
    reference = math.exp(fmean(math.log(body[p]["wingspan"]) for p in tested))
    out = {pid: (reps * (reference / body[pid]["wingspan"]) ** elasticity if pid in body and reps > 0 else reps)
           for pid, reps in raw.items()}
    return out, {"n": len(tested), "fitted_elasticity": round(fitted, 3), "fitted_se": round(fitted_se, 3),
                 "physics_prior": ARM_PRIOR, "prior_sd": ARM_PRIOR_SD, "elasticity_used": round(elasticity, 3),
                 "reference_wingspan_cm": round(reference, 2), "mass_elasticity": round(beta[2], 3)}


def build_estimates(section: Mapping[str, Any], root: Path, universe: Mapping[str, Any]) -> dict[str, Any]:
    """Per input: the fitted models and each player's blended estimate (z in test units) with its sources."""
    players = {p["id"]: p for p in universe.get("players", [])}
    combine = combine_matches(universe, root)
    proxies = proxy_values(universe, root, section)
    body = body_values(section, universe)
    report: dict[str, Any] = {"combine_matched": len(combine)}
    estimates: dict[str, dict[str, dict[str, Any]]] = {}
    for iid in ("P10", "P08"):
        # The existing estimate (position/body prior plus related evidence) is itself a regressor, so the fitted
        # size model starts from it rather than replacing it.
        size_names = ("height", "wingspan", "mass", "guard", "big", "prior")
        for pid in body:
            body[pid]["prior"] = _current(section["players"][pid]["inputs"].get(iid))
        test, trait = TEST[iid], AGING_TRAIT[iid]
        raw = {pid: row[test] for pid, row in combine.items() if row.get(test) is not None and pid in body}
        if len(raw) < 60:
            report[iid] = f"skipped: {len(raw)} combine results"
            continue
        arm_report = None
        if iid == "P08":
            raw, arm_report = arm_length_adjusted_reps(raw, body)
        test_sd = pstdev(raw.values())
        rating_sd = trait_spread(universe, trait)
        adjusted, years = {}, {}
        for pid, value in raw.items():
            p = players[pid]
            row = combine[pid]
            then = _age(p.get("birthdate"), _dt.date(row["year"], *COMBINE_DAY)) or 21.0
            now = _age(p.get("birthdate"), SEASON_START) or float(p.get("age") or then)
            change = expected_rating_change(trait, then, now) / rating_sd * test_sd
            adjusted[pid] = value + change
            years[pid] = max(0.0, now - then)
        size_model = LinearModel(size_names, [({**body[pid]}, v) for pid, v in adjusted.items()])
        proxy_names = PROXIES[iid]
        full = [(pid, {**body[pid], **proxies[pid]}) for pid in adjusted if all(k in proxies[pid] for k in proxy_names)]
        proxy_model = LinearModel(size_names + proxy_names, [(vals, adjusted[pid]) for pid, vals in full]) if len(full) >= 60 else None
        # Proxy subsets for players missing part of the proxy set: the largest subset each player has.
        partial_models: dict[tuple[str, ...], LinearModel] = {}
        out: dict[str, dict[str, Any]] = {}
        for pid in section["players"]:
            if pid not in body:
                continue
            parts = []   # (value, error sd, label)
            size_pred = size_model.predict(body[pid])
            parts.append((size_pred, size_model.oof_rmse, "size and position"))
            have = tuple(k for k in proxy_names if k in proxies.get(pid, {}))
            model = None
            if have == proxy_names and proxy_model:
                model = proxy_model
            elif have:
                if have not in partial_models:
                    rows = [({**body[q], **proxies[q]}, adjusted[q]) for q in adjusted if all(k in proxies[q] for k in have)]
                    partial_models[have] = LinearModel(size_names + have, rows) if len(rows) >= 60 else None
                model = partial_models[have]
            if iid == "P08":
                # Strength: no in-game proxy or body measure predicts the combine bench among NBA players (bench vs body
                # mass r 0.08, vs every proxy |r| <= 0.17, 74 tested players), so untested players keep their
                # existing estimate unchanged and only tested players move.
                model = None
                parts = [(size_model.mean["prior"], 1e9, "unchanged")]
            if model is not None and model.oof_rmse < size_model.oof_rmse:
                # The proxy model already contains the size information: it replaces the size estimate.
                parts = [(model.predict({**body[pid], **proxies[pid]}), model.oof_rmse, "in-game proxies + size")]
            extra = {}
            if pid in adjusted:
                noise = test_sd * math.sqrt(TEST_NOISE_SD ** 2 + (AGING_NOISE_PER_YEAR * years[pid]) ** 2)
                tested = combine[pid][test]
                label = (f"combine {combine[pid]['year']} ({tested:g}"
                         + (f", arm-length-adjusted {raw[pid]:.1f}" if iid == "P08" else "")
                         + f", age-adjusted {adjusted[pid]:.1f})")
                parts.append((adjusted[pid], noise, label))
                extra = {"combine_z": (adjusted[pid] - fmean(adjusted.values())) / test_sd, "combine_error": noise,
                         "combine_label": label}
            weights = [1.0 / (sd * sd) for _, sd, _ in parts]
            value = sum(w * v for w, (v, _, _) in zip(weights, parts)) / sum(weights)
            error = math.sqrt(1.0 / sum(weights))
            out[pid] = {"value": value, "error": error, "test_sd": test_sd, **extra,
                        "sources": [{"label": label, "value": round(v, 2), "weight": round(w / sum(weights), 3)}
                                    for w, (v, _, label) in zip(weights, parts)]}
        mean = fmean(adjusted.values())
        for row in out.values():
            row["z"] = (row["value"] - mean) / test_sd
        estimates[iid] = out
        report[iid] = {"combine_results": len(raw), "test_mean": round(mean, 2), "test_sd": round(test_sd, 2),
                       "size_model": size_model.describe(),
                       "proxy_model": proxy_model.describe() if proxy_model else None}
        if arm_report:
            report[iid]["arm_length_adjustment"] = arm_report
    return {"report": report, "estimates": estimates}


def apply_physical_evidence(section: dict[str, Any], root: Path, universe: Mapping[str, Any]) -> dict[str, Any]:
    built = build_estimates(section, root, universe)
    estimates = built["estimates"]
    changed = {"P08": 0, "P10": 0}
    for iid, rows in estimates.items():
        for pid, row in rows.items():
            record = section["players"][pid]["inputs"].get(iid)
            if not record:
                continue
            value = dict(record.get("value") or {})
            measured = "combine_z" in row
            if iid == "P10":
                cm = row["value"] * 2.54
                radius = 1.96 * row["error"] * 2.54
                value["measurements"] = [{"interval": [round(cm - radius, 3), round(cm + radius, 3)], "metric": "jump_height",
                                          "protocol": ("NBA Draft Combine standing vertical, age-adjusted, blended with in-game proxies"
                                                       if measured else "size, position and in-game proxy estimate; no jump test"),
                                          "unit": "cm", "value": round(cm, 3)}]
                interval = value["measurements"][0]["interval"]
                new_display = round(cm, 3)
            else:
                if not measured:
                    continue
                # Combine bench (in z) and the existing grade (treated as one standard deviation of error: it does not
                # predict the bench) blended by precision, on the grade scale.
                prior = float((value.get("display_grade") or {}).get("grade") or 50.0)
                noise_z = row["combine_error"] / row["test_sd"]
                w = 1.0 / (noise_z * noise_z)
                tested = 100.0 / (1.0 + math.exp(-GRADE_SLOPE * row["combine_z"]))
                grade = (w * tested + prior) / (w + 1.0)
                row["error"] = row["test_sd"] * math.sqrt(1.0 / (w + 1.0))
                row["sources"] = [{"label": row["combine_label"], "value": round(tested, 2), "weight": round(w / (w + 1), 3)},
                                  {"label": "existing estimate", "value": round(prior, 2), "weight": round(1 / (w + 1), 3)}]
                lo = 100.0 / (1.0 + math.exp(-GRADE_SLOPE * (row["z"] - 1.96 * row["error"] / row["test_sd"])))
                hi = 100.0 / (1.0 + math.exp(-GRADE_SLOPE * (row["z"] + 1.96 * row["error"] / row["test_sd"])))
                value["display_grade"] = {**(value.get("display_grade") or {}), "grade": round(grade, 3)}
                interval = [round(lo, 3), round(hi, 3)]
                new_display = round(grade, 3)
            record["value"] = value
            record["evidence"] = [*(record.get("evidence") or []), {
                "source": f"{COMBINE_FILE} (NBA.com Draft Combine); Basketball-Reference dunks; 2025-26 box scores; "
                          "Basketball Index (local captures)",
                "method": f"{VERSION}: precision-weighted blend -> {new_display}",
                "notes": json.dumps(row["sources"], sort_keys=True),
                "shared_evidence_id": f"physical_evidence:{iid}:{pid}",
            }]
            confidence = "medium" if measured else "low"
            record["status"], record["reason"] = ("estimated", "estimated") if measured else (record.get("status"), record.get("reason"))
            unc = dict(record.get("uncertainty") or {})
            unc.update({"confidence": confidence, "notes": json.dumps({
                "basis": ("NBA Draft Combine test moved to his current age along the game's development curve, blended with "
                          "in-game proxies" if measured else "body size and position (and in-game proxies where available); "
                          "no combine test"),
                "interval": interval,
                "limitations": "Combine tests are years old for veterans; in-game proxies also reflect role and skill.",
            }, sort_keys=True)})
            record["uncertainty"] = unc
            changed[iid] += 1
    return {"physical_evidence": {"changed": changed, **built["report"], "version": VERSION}}


def main() -> int:   # diagnostics: PYTHONPATH=src python -m nba_gm_data.physical_evidence
    root = Path(__file__).resolve().parents[2]
    from .ratings_model import INPUTS_FILE
    section = json.loads((root / INPUTS_FILE).read_text())
    universe = json.loads((root / "data/canonical/universe_2026_27_offseason.json").read_text())
    built = build_estimates(section, root, universe)
    print(json.dumps(built["report"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
