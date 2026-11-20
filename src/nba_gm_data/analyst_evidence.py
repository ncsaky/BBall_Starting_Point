"""Analyst evidence for the 94-input player model (analyst-first task, 2026-11-19).

The user's evidence priority: when analysts and data-driven measures disagree about a skill, follow the analysts
("generally, we trust them more, because impact metrics can be skewed with small samples or really dependent on
their context"). This module turns attributed analyst claims (data/research/analyst_claims_2026.json: Nerd Sesh
episodes and linked film analysis, each with a title, publication date, locator and paraphrase)
into an explicit evidence source for the inputs they name. It never sets a number by hand: each claim states a level,
the level becomes a league-percentile target, and the target is blended with the existing value by declared weights.

Method (declared; nothing fitted to simulation outcomes or to a ranking):
1. Level -> one-sided league percentile band and target (LEVELS). The current value's percentile is its rank among
   every rostered player's value of that input (the same pool the claim contradiction check used).
2. Claim weight = support (both hosts 1.0, one host or analyst 0.6, disputed 0.35) x context (playoff-only 0.5: a claim about
   elite playoff defenses is only half about the season-long skill; one-game or opening-week samples 0.25) x
   specificity (a claim naming n inputs counts min(1, 2/n) for each) x 0.5 when the claim is generic ("bad defender"
   with no detail).
3. If the claims whose band already contains the current percentile carry at least half the analyst weight, nothing
   changes (the data agrees; a weak side remark cannot pull an elite value down). Otherwise the claims' weighted
   target score is blended with the current score: share = analyst weight / (analyst weight + data
   weight), data weight DATA_WEIGHT for an input backed by player-specific measurements, PRIOR_WEIGHT for a guess.
   One both-hosts claim against measured data leads (share 0.63); one host alone splits evenly (0.5); a disputed claim
   moves a third of the way. The blended score maps back through the league's own distribution of that input, so the
   input keeps its scale, nothing is clipped, and the claim cannot push a player past the league's existing range.
4. General playmaking claims ("good passer", "creator for others") name the connector read (F01.recognition); the
   hosts almost never distinguish read types, so such a claim informs the four general passing reads together
   (PASSING_READS: connector, pick-and-roll feed, drive-and-kick, skip) and counts as one input for specificity.
   Specific reads a claim names (short roll, post, lob, transition) are kept as named.
5. Layers stay separate: claims on technique inputs (S, F) and on unmeasured physical tools (P05-P12) are applied;
   claims on tendencies (T: what a player chooses to do) are recorded only, as are free-throw claims (S07 is a
   measured free-throw percentage), measured body size (P01-P04) and any physical stored as a measurement (jump
   height P10 is a centimetre prior, so "athletic" claims do not move it).
Every changed record gets one evidence entry per claim (source, episode, date, timestamp, paraphrase) plus the blend.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist
from typing import Any, Mapping

CLAIMS_FILE = "data/research/analyst_claims_2026.json"
VERSION = "analyst_evidence_v1_2026_11_19"
# level -> (band low, band high, target) in league percentiles. Bands are one-sided: a praise level is a floor and a
# criticism level a ceiling, because "solid rim protector" does not say "not elite" (Zubac, Gobert) and "below-average
# shooter" does not say "not terrible".
LEVELS = {
    "elite": (90.0, 100.0, 96.0),
    "strong": (72.0, 100.0, 85.0),
    "above_average": (52.0, 100.0, 66.0),
    "below_average": (0.0, 48.0, 33.0),
    "weak": (0.0, 28.0, 15.0),
    "very_weak": (0.0, 12.0, 5.0),
}
SUPPORT = {"both_hosts": 1.0, "one_host": 0.6, "single_analyst": 0.6, "disputed": 0.35}
CONTEXT = {"general": 1.0, "regular_season": 1.0, "playoffs": 0.5}
SMALL_SAMPLE = 0.25
GENERIC = 0.5
DATA_WEIGHT = 0.6
PRIOR_WEIGHT = 0.2
SKIP_INPUTS = {"S07", "P01", "P02", "P03", "P04"}
PASSING_READS = ("F01.recognition", "F03.recognition", "F06.recognition", "F07.recognition")
_ND = NormalDist()


def load_claims(root: Path) -> list[dict[str, Any]]:
    path = Path(root) / CLAIMS_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text())["claims"]


def claim_inputs(claim: Mapping[str, Any]) -> list[str]:
    """Inputs a claim informs: as named, with a general playmaking claim spread over the general passing reads."""
    named = list(claim.get("inputs", []))
    if "F01.recognition" not in named:
        return named
    return [i for i in named if i not in PASSING_READS] + list(PASSING_READS)


def _specificity_count(claim: Mapping[str, Any]) -> int:
    named = list(claim.get("inputs", []))
    reads = [i for i in named if i in PASSING_READS]
    return len(named) - len(reads) + (1 if reads else 0)


def claim_weight(claim: Mapping[str, Any]) -> float:
    """Evidence weight of one claim for each input it names."""
    notes = (claim.get("notes") or "").lower()
    weight = SUPPORT.get(claim.get("support"), 0.6) * CONTEXT.get(claim.get("context"), 1.0)
    if claim.get("episode", "").lower().startswith("opening week") or "one game" in notes or "small sample" in notes:
        weight *= SMALL_SAMPLE
    if "generic" in notes:
        weight *= GENERIC
    applicable = [i for i in claim.get("inputs", []) if applicable_input(i)]
    return weight * min(1.0, 2.0 / max(1, _specificity_count(claim))) if applicable else 0.0


def _claim_source(claim: Mapping[str, Any]) -> str:
    publication = f"{claim.get('source', 'analyst')}: {claim.get('episode')}"
    if claim.get("url"):
        return f"{publication} ({claim.get('published')}, {claim['url']}), {claim.get('locator')}"
    return f"{publication} (YouTube {claim.get('video_id')}, {claim.get('published')}), {claim.get('timestamp')}"


def applicable_input(iid: str) -> bool:
    return not iid.startswith("T") and iid not in SKIP_INPUTS


def _slot(record: Mapping[str, Any]) -> str | None:
    value = record.get("value") if isinstance(record, Mapping) else None
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("grade"), (int, float)):
        return "grade"
    display = value.get("display_grade")
    if isinstance(display, dict) and isinstance(display.get("grade"), (int, float)) and not value.get("measurements"):
        return "display_grade"
    return None


def _read(record: Mapping[str, Any], slot: str) -> float:
    value = record["value"]
    return float(value["display_grade"]["grade"] if slot == "display_grade" else value["grade"])


def _write(record: dict[str, Any], slot: str, new: float) -> None:
    if slot == "display_grade":
        record["value"] = {**record["value"], "display_grade": {**record["value"]["display_grade"], "grade": new}}
    else:
        record["value"] = {**record["value"], "grade": new}


def _percentile(pool: list[float], x: float) -> float:
    import bisect
    lo, hi = bisect.bisect_left(pool, x), bisect.bisect_right(pool, x)
    return 100.0 * ((lo + hi) / 2 + 0.5) / (len(pool) + 1)


def _quantile(pool: list[float], pct: float) -> float:
    n = len(pool)
    pos = min(max(pct / 100.0 * (n + 1) - 1.0, 0.0), n - 1.0)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    return pool[lo] + (pool[hi] - pool[lo]) * (pos - lo)


def _z(pct: float) -> float:
    return _ND.inv_cdf(min(max(pct, 0.05), 99.95) / 100.0)


def apply_analyst_evidence(section: dict[str, Any], root: Path, claims: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Blend attributed analyst claims into an input section in place. Returns a summary with every change."""
    claims = load_claims(root) if claims is None else claims
    players = section["players"]
    by_target: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    recorded = 0
    for claim in claims:
        pid = claim.get("player_id")
        if claim.get("not_applied") or pid not in players:
            recorded += 1
            continue
        for iid in claim_inputs(claim):
            if applicable_input(iid) and claim.get("level") in LEVELS:
                by_target[(pid, iid)].append(claim)
    pools: dict[str, list[float]] = {}
    for _, iid in by_target:
        if iid in pools:
            continue
        values = []
        for doc in players.values():
            record = doc["inputs"].get(iid)
            slot = _slot(record) if record else None
            if slot:
                values.append(_read(record, slot))
        pools[iid] = sorted(values)
    changes = []
    agreed = 0
    for (pid, iid), items in sorted(by_target.items()):
        record = players[pid]["inputs"].get(iid)
        slot = _slot(record) if record else None
        pool = pools.get(iid) or []
        if not slot or len(pool) < 30:
            continue
        old = _read(record, slot)
        pct = _percentile(pool, old)
        weights = [claim_weight(c) for c in items]
        total = sum(weights)
        if total <= 0:
            continue
        agreeing = sum(w for w, c in zip(weights, items) if LEVELS[c["level"]][0] <= pct <= LEVELS[c["level"]][1])
        if agreeing >= total - agreeing:
            agreed += 1
            continue
        target_z = sum(w * _z(LEVELS[c["level"]][2]) for w, c in zip(weights, items)) / total
        measured = record.get("reason") != "prior"   # same test as input_estimator.estimation_status
        data_weight = DATA_WEIGHT if measured else PRIOR_WEIGHT
        share = total / (total + data_weight)
        new_pct = 100.0 * _ND.cdf(share * target_z + (1 - share) * _z(pct))
        new = round(_quantile(pool, new_pct), 3)
        _write(record, slot, new)
        evidence = list(record.get("evidence") or [])
        for w, c in zip(weights, items):
            evidence.append({
                "source": _claim_source(c),
                "method": f"{VERSION}: claim level {c['level']} ({c.get('support')}, {c.get('context')}), weight {w:.2f}",
                "notes": c.get("claim", ""),
                "shared_evidence_id": f"analyst:{c.get('id')}",
            })
        evidence.append({
            "source": CLAIMS_FILE,
            "method": (f"{VERSION}: league percentile {pct:.0f} -> {new_pct:.0f}; analyst weight {total:.2f} vs "
                       f"{'measured' if measured else 'prior'} data weight {data_weight} (analyst share {share:.2f}); "
                       f"value {round(old, 3)} -> {new}"),
            "shared_evidence_id": f"analyst_blend:{pid}:{iid}",
        })
        record["evidence"] = evidence
        if share >= 0.5 and not measured:
            record["status"], record["reason"] = "estimated", "estimated"
        changes.append({"player_id": pid, "input": iid, "old": round(old, 3), "new": new, "pct_old": round(pct, 1),
                        "pct_new": round(new_pct, 1), "share": round(share, 3), "claims": [c.get("id") for c in items]})
    return {"analyst_evidence": {"version": VERSION, "claims": len(claims), "recorded_only": recorded,
                                 "player_inputs_claimed": len(by_target), "agreed": agreed, "changed": len(changes)},
            "analyst_changes": changes}
