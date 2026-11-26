"""NBA.com play-type evidence for the transition share of effort allocation (T17), RATINGS-FIVE-INPUTS 2026-11-25.

T17 (effort allocation: offense / defense / transition) had Basketball Index evidence for the defense share only;
its transition share was a fixed prior (.15 before renormalising) that matched real transition play at r .25.
NBA.com's 2025-26 play-type tables (Synergy, data/research/nba_synergy_playtypes_2025_26.json) give, for every player, how
many of the possessions he finished came in transition. That share of his offensive-end play is the evidence:

1. Measured share s = transition possessions / all his play-type possessions (n).
2. Players' sampling noise is shrunk by a prior strength K fitted from the data (true spread across players against
   binomial sampling noise): s_hat = (n * s + K * s_prior) / (n + K).
3. s_prior: the player's existing transition share of his offensive-end effort, placed on the measured scale by
   rank (players without NBA.com data, including generated rookies, get only this; the mapping is saved in
   bbi_evidence.SCALE_MAP_FILE as "T17:transition_share").
4. T17 keeps its defense share (Basketball Index defensive distance); the rest of the effort is split
   transition = (1 - defense) * s_hat, offense = (1 - defense) * (1 - s_hat).

Today's engine reads T17's defense share only (trait_adapter), which this step does not change.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Mapping

PLAYTYPE_FILE = "data/research/nba_synergy_playtypes_2025_26.json"
VERSION = "playtype_transition_v1_2026_11_25"
MIN_SCALE_POSS = 200.0   # players whose measured share defines the measured scale (about a rotation season)


def load_playtypes(root: Path) -> dict[str, Any] | None:
    path = Path(root) / PLAYTYPE_FILE
    return json.loads(path.read_text()) if path.exists() else None


def measured_transition(data: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """canonical_id -> {"share": transition share of his play-type possessions, "poss": all his play-type possessions}."""
    out = {}
    for cid, rec in data.get("players", {}).items():
        n = float(rec.get("total_poss") or 0.0)
        # Absent from the transition table = not measured, not zero: NBA.com lists 10+ possessions only, and a few
        # high-volume players are missing from it altogether (Russell Westbrook, 1,071 possessions in other play types).
        if n <= 0 or "Transition" not in rec.get("types", {}):
            continue
        trans = float(rec["types"]["Transition"][0])
        out[cid] = {"share": min(1.0, trans / n), "poss": n}
    return out


def prior_strength(measured: Mapping[str, Mapping[str, float]], min_poss: float = MIN_SCALE_POSS) -> float:
    """K (possessions) such that n / (n + K) is the reliability of a player's measured share:
    K = mean binomial variance / true variance across players, true = observed - mean sampling variance."""
    rows = [(m["share"], m["poss"]) for m in measured.values() if m["poss"] >= min_poss]
    if len(rows) < 20:
        return 200.0
    shares = [s for s, _ in rows]
    p = statistics.fmean(shares)
    sampling = statistics.fmean(s * (1 - s) / n for s, n in rows)
    true_var = max(1e-6, statistics.pvariance(shares) - sampling)
    return p * (1 - p) / true_var


def _offensive_share(mix: Mapping[str, float]) -> float | None:
    off = float(mix.get("offense", 0.0)) + float(mix.get("transition", 0.0))
    return float(mix["transition"]) / off if off > 0 else None


def apply_transition_evidence(section: dict[str, Any], root: Path) -> dict[str, Any]:
    from .bbi_evidence import SCALE_MAP_FILE, _mix, _quantile_points, map_to_measured
    from .input_estimator import _bounded_band
    data = load_playtypes(root)
    if not data:
        return {"t17_transition_measured": 0}
    measured = measured_transition(data)
    k = prior_strength(measured)
    players = section["players"]
    source = []
    for doc in players.values():
        mix = _mix(doc["inputs"].get("T17"))
        share = _offensive_share(mix) if mix else None
        if share is not None:
            source.append(share)
    target = [m["share"] for m in measured.values() if m["poss"] >= MIN_SCALE_POSS]
    table = {"source": _quantile_points(source), "target": _quantile_points(target)}
    counts = {"t17_transition_measured": 0, "t17_transition_mapped": 0, "prior_strength_poss": round(k, 1),
              "measured_scale_players": len(target)}
    for pid, doc in players.items():
        record = doc["inputs"].get("T17")
        mix = _mix(record) if record else None
        if not mix or not all(c in mix for c in ("offense", "defense", "transition")):
            continue
        prior = _offensive_share(mix)
        if prior is None:
            continue
        prior_mapped = map_to_measured(table, prior)
        ev = measured.get(pid)
        n = ev["poss"] if ev else 0.0
        share = (n * ev["share"] + k * prior_mapped) / (n + k) if ev else prior_mapped
        defense = float(mix["defense"])
        probs = {"offense": (1 - defense) * (1 - share), "defense": defense, "transition": (1 - defense) * share}
        record["value"] = {**record["value"], "rows": [dict(record["value"]["rows"][0],
                                                              probabilities={c: round(v, 6) for c, v in probs.items()})]}
        if ev:
            weight = n / (n + k)
            record["evidence"] = [*(record.get("evidence") or []), {
                "source": f"{PLAYTYPE_FILE} (NBA.com Synergy play types, 2025-26 regular season)",
                "method": (f"{VERSION}: transition share of his offensive-end effort = transition possessions / all "
                           f"play-type possessions ({ev['share']:.3f} of {n:.0f}), blended at share {weight:.2f} with "
                           f"his earlier transition share placed on the measured scale by rank ({prior_mapped:.3f}); "
                           f"defense share kept"),
                "shared_evidence_id": f"nba_playtypes:{pid}:T17",
                "notes": f"prior strength {k:.0f} possessions (true spread across players vs sampling noise)",
            }]
            try:
                notes = json.loads((record.get("uncertainty") or {}).get("notes") or "{}")
            except ValueError:
                notes = {}
            intervals = dict(notes.get("intervals") or {})
            sd = (1 - defense) * math.sqrt(max(share * (1 - share), 1e-6) / (n + k))
            for c in ("offense", "transition"):
                intervals[c] = _bounded_band(probs[c], 0.02 + 2 * sd, 1)
            notes["intervals"] = intervals
            if "uncertainty" in record:
                record["uncertainty"] = {**record["uncertainty"],
                                         "notes": json.dumps(notes, sort_keys=True, ensure_ascii=False, separators=(",", ":"))}
            if weight >= 0.5:
                record["status"], record["reason"] = "estimated", "estimated"
            counts["t17_transition_measured"] += 1
        else:
            counts["t17_transition_mapped"] += 1
    path = Path(root) / SCALE_MAP_FILE
    scale = json.loads(path.read_text()) if path.exists() else {}
    scale["T17:transition_share"] = table
    path.write_text(json.dumps(scale, indent=0) + "\n")
    return counts
