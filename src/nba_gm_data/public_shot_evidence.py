"""Measured dunk evidence for the dunk-execution input (S12), from public Basketball-Reference shooting data.

Until 2026-11-19 every player's dunk execution was a position/body/role prior (no dunk data), so Luka Dončić and
Nikola Jokić sat in the top 1% and Stephen Curry near the middle. Basketball-Reference publishes, per player-season,
the share of field-goal attempts that were dunks and the share taken 0-3 feet from the rim
(data/research/bref_shooting_2024_2026.json, built by scripts/research/bref_shooting.py).

Method (declared; nothing fitted to simulation outcomes or to a ranking):
1. Dunk rate = dunk attempts / attempts within 3 feet, seasons 2025-26, 2024-25, 2023-24 weighted 1.0 / 0.6 / 0.35
   (the same recency weights as the Basketball Index overlay), with half an attempt of smoothing.
2. The model defines dunk execution as technique "when a dunk is physically available; reach and vertical decide
   availability" (player-object map, S12). So size is taken out first: each player is compared with the players
   closest to him in height, wingspan and body mass (the physical layer's own values; pool = players with at least
   MIN_POOL close attempts, kernel-weighted by size distance and sample, the player himself left out). His difference
   from those size peers in logit(dunk rate), in residual standard deviations, is his score: dunking more often than
   players his size scores high, less often scores low. A local comparison avoids extending a straight line past the
   tallest players. Jump capacity has no measurement in the model (it is a prior),
   so this score still carries some leaping ability; that is recorded as a limitation, and the physical input is left
   untouched (it needs its own evidence).
3. Score -> grade on the model's anchors with the overlay's curve (50 functional, ~75 at the 80th percentile, ~92 at
   the 97th): grade = 100 * logistic(1.31 * z). Smooth and never clipped.
4. Blended with the existing estimate by sample: share = close attempts / (close attempts + HALF_ATTEMPTS).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import fmean
from typing import Any, Mapping

DATA_FILE = "data/research/bref_shooting_2024_2026.json"
SEASON_WEIGHTS = {"2025-26": 1.0, "2024-25": 0.6, "2023-24": 0.35}
MIN_POOL = 60.0          # weighted close attempts to join the size regression
HALF_ATTEMPTS = 60.0     # weighted close attempts at which the measurement gets half the weight
GRADE_SLOPE = 1.31       # same curve as bbi_evidence._grade_from_z
VERSION = "bref_dunk_evidence_v1_2026_11_19"


def _normalize(name: str) -> str:
    from .input_estimator import _normalize as norm
    return norm(name)


def _measure(record: Mapping[str, Any] | None) -> float | None:
    try:
        return float(record["value"]["measurements"][0]["value"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def dunk_rates(data: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """normalized name -> {close, dunks, rate, seasons} (season-weighted attempts)."""
    out: dict[str, dict[str, float]] = {}
    for doc in data.get("players", {}).values():
        close = dunks = 0.0
        seasons = {}
        for season, weight in SEASON_WEIGHTS.items():
            row = (doc.get("seasons") or {}).get(season) or {}
            fga, near, dunk = row.get("fga"), row.get("pct_fga_00_03"), row.get("pct_fga_dunk")
            if not fga or near is None or dunk is None:
                continue
            close += weight * fga * near
            dunks += weight * fga * dunk
            seasons[season] = {"close_attempts": round(fga * near), "dunk_attempts": round(fga * dunk), "dunks_made": row.get("dunks")}
        if close > 0:
            key = _normalize(doc["name"])
            # Two players with one name: keep the larger sample (never merge them).
            if key not in out or out[key]["close"] < close:
                out[key] = {"close": close, "dunks": dunks, "rate": (dunks + 0.5) / (close + 1.0), "seasons": seasons}
    return out


class SizePeers:
    """Expected logit(dunk rate) for a body: sample-weighted mean of the pool players closest in height, wingspan and
    mass (Gaussian kernel on standardized size, bandwidth BANDWIDTH sd). A local comparison, so the tallest players are
    compared with other 7-footers instead of a straight line extended past the end of the data."""

    BANDWIDTH = 0.6

    def __init__(self, rows: list[tuple[list[float], float, float, str]]):
        self.rows = rows
        k = len(rows[0][0])
        total = sum(w for _, _, w, _ in rows)
        self.mean = [sum(w * x[i] for x, _, w, _ in rows) / total for i in range(k)]
        self.sd = [math.sqrt(sum(w * (x[i] - self.mean[i]) ** 2 for x, _, w, _ in rows) / total) or 1.0 for i in range(k)]
        resid = [(y - self.expected(x, pid), w) for x, y, w, pid in rows]
        self.residual_sd = math.sqrt(sum(w * r * r for r, w in resid) / sum(w for _, w in resid))

    def expected(self, body: list[float], exclude: str | None = None) -> float:
        num = den = 0.0
        for x, y, w, pid in self.rows:
            if pid == exclude:
                continue
            d2 = sum(((a - b) / s) ** 2 for a, b, s in zip(body, x, self.sd))
            k = w * math.exp(-0.5 * d2 / self.BANDWIDTH ** 2)
            num += k * y
            den += k
        return num / den


def apply_dunk_evidence(section: dict[str, Any], root: Path, universe: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(root) / DATA_FILE
    if not path.exists():
        return {"dunk_evidence": "skipped: no Basketball-Reference shooting file"}
    rates = dunk_rates(json.loads(path.read_text()))
    names = {p["id"]: _normalize(p["name"]) for p in universe.get("players", [])}
    body: dict[str, list[float]] = {}
    for pid, doc in section["players"].items():
        inputs = doc["inputs"]
        values = [_measure(inputs.get(i)) for i in ("P01", "P02", "P04")]
        if None not in values:
            body[pid] = values
    matched = {pid: rates[names[pid]] for pid in section["players"] if names.get(pid) in rates and pid in body}
    pool = [(body[pid], math.log(r["rate"] / (1 - r["rate"])), r["close"] / (r["close"] + MIN_POOL), pid)
            for pid, r in matched.items() if r["close"] >= MIN_POOL]
    if len(pool) < 50:
        return {"dunk_evidence": f"skipped: only {len(pool)} players in the size model"}
    peers = SizePeers(pool)
    sd = peers.residual_sd
    changed = 0
    for pid, r in matched.items():
        record = section["players"][pid]["inputs"].get("S12")
        if not record or "grade" not in (record.get("value") or {}):
            continue
        expected = peers.expected(body[pid], exclude=pid)
        z = (math.log(r["rate"] / (1 - r["rate"])) - expected) / sd
        grade = 100.0 / (1.0 + math.exp(-GRADE_SLOPE * z))
        share = r["close"] / (r["close"] + HALF_ATTEMPTS)
        old = float(record["value"]["grade"])
        new = round(share * grade + (1 - share) * old, 3)
        record["value"] = {**record["value"], "grade": new}
        expected_rate = 1.0 / (1.0 + math.exp(-expected))
        record["evidence"] = [*(record.get("evidence") or []), {
            "source": f"{DATA_FILE} (Basketball-Reference season shooting pages)",
            "method": (f"{VERSION}: dunk attempts per attempt within 3 ft {r['rate']:.3f} vs {expected_rate:.3f} expected "
                       f"for his height, wingspan and mass (score {z:+.2f} residual sd) -> grade {grade:.1f}, "
                       f"blended share {share:.2f} with prior/estimate {round(old, 3)}"),
            "exposure": {"unit": "weighted close attempts", "value": round(r["close"], 1)},
            "shared_evidence_id": f"bref_dunks:{pid}",
            "notes": "seasons: " + json.dumps(r["seasons"], sort_keys=True),
        }]
        if share >= 0.5:
            record["status"], record["reason"] = "estimated", "estimated"
            radius = 25.0 * (1 - share) + 10.0
            unc = dict(record.get("uncertainty") or {})
            try:
                notes = json.loads(unc.get("notes") or "{}")
            except ValueError:
                notes = {}
            notes.update({"basis": "measured dunk rate near the rim, net of body size (Basketball-Reference)",
                          "interval": [round(max(0.0, new - radius), 3), round(min(100.0, new + radius), 3)],
                          "limitations": ("Dunk rate also reflects jump capacity (unmeasured), role (lob finishing, "
                                          "transition) and willingness; size is controlled, nothing else.")})
            unc.update({"confidence": "medium" if share >= 0.75 else "low", "notes": json.dumps(notes, sort_keys=True)})
            record["uncertainty"] = unc
        changed += 1
    return {"dunk_evidence": {"players_measured": changed, "size_model_players": len(pool),
                              "residual_sd": round(sd, 3),
                              "mean_pool_rate": round(fmean(math.exp(y) / (1 + math.exp(y)) for _, y, _, _ in pool), 3),
                              "version": VERSION}}
