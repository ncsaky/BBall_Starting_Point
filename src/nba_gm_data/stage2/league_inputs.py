"""League input bridge: every player's 94 inputs compiled into the physics pieces' typed profiles (Stage 2).

The experimental physics pieces (offense_response, interior_defense) were built on hand-made player packets. This
module compiles the league's estimated inputs (data/canonical/player_inputs_2026_27.json, 691 players) into the same
typed profiles, through the shared reader (experimental_inputs.InterpretedInputs), so the pieces can be scored
against real data.

ONE rule for cells that are not player-specific evidence (documented, never a hand-supplied control):
- "estimated" cells (player-specific evidence) and "prior" cells (the estimator's position/role/body prior for that
  player) are both used at their stored central value; the stored uncertainty interval is kept next to the value
  (`intervals`), so later pieces can sample or widen it. The bridge never moves a value.
- "unknown" cells (none in today's league file; generated or future players may have them) get the league prior for
  the player's position group (guard / wing / big, input_estimator's grouping): the group median of that input, with
  the group's 10th-90th percentile range as its uncertainty, reason "prior", confidence "low", and provenance naming
  this rule.
- A physical quantity the kernels need in units the league file does not carry (P05 acceleration, m/s^2) is converted
  from the player's league rank on that grade onto the measured distribution of the same ability (2000-2025 combine
  three-quarter sprint times; a = 2d/t^2 from rest), under its own explicit protocol label. Its interval converts
  the grade's interval the same way.

The compiled numbers are cached (memory, plus output/stage2/ on disk keyed by the inputs file and this version), so a
full league compile is a one-off cost. Profiles rebuilt from the cache carry `inputs=None`: the kernels only read the
numbers; the PlayerInputs snapshot is available on demand through `interpreted_inputs()`.
"""
from __future__ import annotations

import bisect
import copy
import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import median
from typing import Any

from ..experimental_inputs import (LEAGUE_ACCELERATION, InputInterpretation, InterpretedInputs, LeagueInterpretedInputs,
                                   VERSION as INPUT_INTERPRETATION_VERSION)
from ..interior_defense import Coefficients, InteriorProfile, compile_profile
from ..offense_response import OffenseCoefficients, OffensiveProfile, compile_offense
from ..player_model import PlayerInputs

INPUTS_FILE = "data/canonical/player_inputs_2026_27.json"
UNIVERSE_FILE = "data/canonical/universe_2026_27_offseason.json"
COMBINE_FILE = "data/research/draft_combine_2000_2025.json"
CACHE_FILE = "output/stage2/league_profiles.json"
BRIDGE_VERSION = "stage2_league_bridge_v1_2026_11_21"
ROUNDING_TOLERANCE = 1e-5  # distributions stored to 6 decimals; larger gaps are real errors and still fail
SPRINT_DISTANCE_M = 22.86  # three-quarter court sprint, 75 ft
PRIOR_RULE = ("stage2 bridge group prior: median of the player's position group (guard/wing/big) for this input; "
              "uncertainty = the group's 10th-90th percentile range; not player evidence")
# Inputs each compiled piece reads (for the coverage report).
OFFENSE_READS = tuple(f"S{i:02d}" for i in range(1, 16)) + ("P03", "P08", "P09", "P10", "T01", "T02", "T03")
INTERIOR_READS = ("S36", "S37", "S45", "P02", "P03", "P05", "P08", "P09", "P10", "T16")

_MEMORY: dict[str, Any] = {}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _inputs_path(root: str | Path) -> Path:
    path = Path(root) / INPUTS_FILE
    if not path.exists():
        gz = path.with_suffix(path.suffix + ".gz")
        if gz.exists():
            import gzip
            path.write_bytes(gzip.decompress(gz.read_bytes()))
    return path


def load_league_documents(root: str | Path) -> dict[str, dict]:
    key = f"docs:{Path(root).resolve()}"
    if key not in _MEMORY:
        _MEMORY[key] = _load_json(_inputs_path(root))["players"]
    return _MEMORY[key]


def player_directory(root: str | Path) -> dict[str, dict]:
    """player id -> {name, position, group} from the canonical universe (for priors and reports)."""
    key = f"dir:{Path(root).resolve()}"
    if key not in _MEMORY:
        from ..input_estimator import _position
        path = Path(root) / UNIVERSE_FILE
        players = _load_json(path).get("players", []) if path.exists() else []
        _MEMORY[key] = {p["id"]: {"name": p.get("name"), "position": p.get("position"), "group": _position(p),
                                  "espn_player_id": str(p.get("espn_player_id") or "") or None}
                        for p in players if p.get("id")}
    return _MEMORY[key]


def _interval(record: dict) -> Any:
    try:
        notes = json.loads(record["uncertainty"]["notes"])
    except (KeyError, TypeError, ValueError):
        return None
    return notes.get("interval") or notes.get("intervals")


def _scalar(record: dict) -> float | None:
    value = record.get("value")
    if not isinstance(value, dict):
        return None
    if "grade" in value:
        return float(value["grade"])
    if "probability" in value:
        return float(value["probability"])
    if value.get("display_grade"):
        return float(value["display_grade"]["grade"])
    return None


# ---- the documented prior rule for unknown cells -------------------------------------------------------------
def group_priors(documents: dict[str, dict], directory: dict[str, dict]) -> dict[tuple[str, str], dict]:
    """(group, input id) -> a complete record built from that group's non-unknown values of the input."""
    values: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for pid, doc in documents.items():
        group = directory.get(pid, {}).get("group", "wing")
        for iid, record in doc["inputs"].items():
            if record.get("status") != "unknown":
                values[(group, iid)].append(record)
    priors = {}
    for (group, iid), records in values.items():
        priors[(group, iid)] = _prior_record(iid, records)
    return priors


def _quantile(ordered: list[float], q: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    x = q * (len(ordered) - 1)
    lo = int(math.floor(x))
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (x - lo)


def _prior_record(iid: str, records: list[dict]) -> dict:
    template = copy.deepcopy(records[0]["value"])
    interval: Any = None
    if "grade" in template:
        xs = sorted(float(r["value"]["grade"]) for r in records)
        template["grade"] = round(median(xs), 6)
        interval = [round(_quantile(xs, .1), 6), round(_quantile(xs, .9), 6)]
    elif "probability" in template:
        xs = sorted(float(r["value"]["probability"]) for r in records)
        template["probability"] = round(median(xs), 6)
        interval = [round(_quantile(xs, .1), 6), round(_quantile(xs, .9), 6)]
    elif "rows" in template:
        # Mean of the group's distributions (a mean of distributions is a distribution); per-outcome 10-90 range.
        outcomes = list(template["rows"][0]["probabilities"])
        cols = {o: sorted(float(r["value"]["rows"][0]["probabilities"][o]) for r in records) for o in outcomes}
        mean = {o: sum(cols[o]) / len(cols[o]) for o in outcomes}
        total = sum(mean.values())
        probs = {o: round(mean[o] / total, 9) for o in outcomes}
        probs[outcomes[-1]] = round(1 - sum(probs[o] for o in outcomes[:-1]), 9)
        template["rows"] = [{"condition": template["rows"][0]["condition"], "probabilities": probs}]
        interval = {o: [round(_quantile(cols[o], .1), 6), round(_quantile(cols[o], .9), 6)] for o in outcomes}
    else:  # physical
        if template.get("measurements"):
            m0 = template["measurements"][0]
            same = [r for r in records if r["value"].get("measurements")
                    and r["value"]["measurements"][0]["metric"] == m0["metric"]]
            xs = sorted(float(r["value"]["measurements"][0]["value"]) for r in same)
            lo, hi = _quantile(xs, .1), _quantile(xs, .9)
            template["measurements"] = [{"metric": m0["metric"], "unit": m0["unit"], "protocol": m0["protocol"],
                                         "value": round(median(xs), 6), "interval": [round(lo, 6), round(hi, 6)]}]
            interval = [round(lo, 6), round(hi, 6)]
        if template.get("display_grade"):
            xs = sorted(float(r["value"]["display_grade"]["grade"]) for r in records if r["value"].get("display_grade"))
            template["display_grade"]["grade"] = round(median(xs), 6)
            interval = interval or [round(_quantile(xs, .1), 6), round(_quantile(xs, .9), 6)]
    notes = {"basis": PRIOR_RULE, "interval" if not isinstance(interval, dict) else "intervals": interval,
             "limitations": "group prior only; no player-specific evidence"}
    return {"status": "estimated", "reason": "prior", "value": template,
            "evidence": [{"source": BRIDGE_VERSION, "method": PRIOR_RULE, "shared_evidence_id": f"stage2_group_prior:{iid}"}],
            "uncertainty": {"confidence": "low", "notes": json.dumps(notes, sort_keys=True)}}


# ---- unit conversion the kernels need (P05 acceleration) ------------------------------------------------------
def sprint_reference(root: str | Path) -> list[float]:
    key = f"sprint:{Path(root).resolve()}"
    if key not in _MEMORY:
        rows = _load_json(Path(root) / COMBINE_FILE)["players"]
        _MEMORY[key] = sorted(float(r["three_quarter_sprint_s"]) for r in rows if r.get("three_quarter_sprint_s"))
    return _MEMORY[key]


def _rank(ordered: list[float], x: float) -> float:
    """Mid-rank percentile of x within ordered values, in (0, 1)."""
    lo = bisect.bisect_left(ordered, x)
    hi = bisect.bisect_right(ordered, x)
    return (lo + hi) / 2 / len(ordered) if ordered else .5


def acceleration_from_grade(grade: float, league_grades: list[float], sprint_times: list[float]) -> float:
    """League rank of the acceleration grade -> the same rank's combine three-quarter sprint time -> 2d/t^2."""
    u = min(max(_rank(league_grades, grade), .5 / len(league_grades)), 1 - .5 / len(league_grades))
    seconds = _quantile(sprint_times, 1 - u)  # a higher grade is a faster (shorter) sprint
    return 2 * SPRINT_DISTANCE_M / seconds ** 2


def bridge_document(doc: dict, priors: dict[tuple[str, str], dict], group: str,
                    league_p05: list[float], sprint_times: list[float]) -> tuple[dict, dict]:
    """A bridged copy of one player's inputs document, and a note of what the bridge did. The source is untouched."""
    out = copy.deepcopy(doc)
    filled, rounding = [], []
    for iid, record in list(out["inputs"].items()):
        rows = (record.get("value") or {}).get("rows") if isinstance(record.get("value"), dict) else None
        if rows:
            for row in rows:
                probs = row["probabilities"]
                residual = 1.0 - sum(probs.values())
                if residual != 0 and abs(residual) <= ROUNDING_TOLERANCE:
                    # Storage rounding (6 decimals) left the mix off one by up to 1e-6, which the player model's
                    # validator rejects. The residual goes to the largest outcome; nothing else moves.
                    top = max(probs, key=probs.get)
                    probs[top] = probs[top] + residual
                    rounding.append(iid)
        if record.get("status") == "unknown":
            prior = priors.get((group, iid))
            if prior is None:
                raise ValueError(f"{doc['player_id']} {iid}: unknown and no group prior available")
            out["inputs"][iid] = copy.deepcopy(prior)
            filled.append(iid)
    p05 = out["inputs"].get("P05")
    if p05 and p05["value"].get("display_grade") and not any(m["metric"] == "acceleration" for m in p05["value"]["measurements"]):
        grade = float(p05["value"]["display_grade"]["grade"])
        value = acceleration_from_grade(grade, league_p05, sprint_times)
        interval = _interval(p05)
        bounds = sorted(acceleration_from_grade(float(b), league_p05, sprint_times) for b in interval) if interval else [value, value]
        bounds = [min(bounds[0], value), max(bounds[1], value)]
        p05["value"]["measurements"].append({"metric": "acceleration", "unit": "m/s2", "protocol": LEAGUE_ACCELERATION,
                                             "value": round(value, 6), "interval": [round(bounds[0], 6), round(bounds[1], 6)]})
        # The display grade stays: it is the stored input; the measurement is its declared unit conversion.
    return out, {"filled_unknown": filled, "rounding_repaired": rounding}


def interpreted_inputs(root: str | Path, player_id: str) -> InterpretedInputs:
    """The full validated input snapshot for one player, bridged (slow path; the compiled cache avoids it)."""
    return _interpreted_with_notes(root, player_id)[0]


def _interpreted_with_notes(root: str | Path, player_id: str) -> tuple[InterpretedInputs, dict]:
    documents = load_league_documents(root)
    directory = player_directory(root)
    priors = _league_priors(root)
    league_p05 = _league_p05(root)
    bridged, notes = bridge_document(documents[player_id], priors, directory.get(player_id, {}).get("group", "wing"),
                                     league_p05, sprint_reference(root))
    return LeagueInterpretedInputs(PlayerInputs(bridged), InputInterpretation()), notes


def _league_priors(root: str | Path) -> dict:
    key = f"priors:{Path(root).resolve()}"
    if key not in _MEMORY:
        _MEMORY[key] = group_priors(load_league_documents(root), player_directory(root))
    return _MEMORY[key]


def _league_p05(root: str | Path) -> list[float]:
    key = f"p05:{Path(root).resolve()}"
    if key not in _MEMORY:
        _MEMORY[key] = _league_p05_values(root)
    return _MEMORY[key]


def _league_p05_values(root: str | Path) -> list[float]:
    return sorted(float(doc["inputs"]["P05"]["value"]["display_grade"]["grade"])
                  for doc in load_league_documents(root).values()
                  if doc["inputs"].get("P05", {}).get("value") and doc["inputs"]["P05"]["value"].get("display_grade"))


# ---- compile -------------------------------------------------------------------------------------------------
def _offense_numbers(profile: OffensiveProfile) -> dict:
    return {"skills": list(profile.skills), "willingness": profile.willingness, "locations": list(profile.locations),
            "modes": list(profile.modes), "standing_reach_cm": profile.standing_reach_cm, "jump_cm": profile.jump_cm,
            "strength": profile.strength, "balance": profile.balance, "ft_probability": profile.ft_probability,
            "revision": profile.revision, "input_contract": profile.input_contract}


def _interior_numbers(profile: InteriorProfile) -> dict:
    keep = ("positioning", "technique", "legal", "standing_reach_cm", "acceleration_m_s2", "strength_capacity",
            "balance_capacity", "jump_cm", "jump_choice", "conservative_choice", "stay_down_choice", "revision",
            "input_contract", "wingspan_cm")
    return {k: getattr(profile, k) for k in keep}


def compile_player(root: str | Path, player_id: str) -> dict:
    """Compile one player through the shared reader into offense and interior numbers (no cache)."""
    inputs, bridge_notes = _interpreted_with_notes(root, player_id)
    doc = load_league_documents(root)[player_id]
    record = {"offense": None, "interior": None, "errors": {}, "bridge": bridge_notes}
    try:
        record["offense"] = _offense_numbers(compile_offense(inputs))
    except ValueError as exc:
        record["errors"]["offense"] = str(exc)
    try:
        record["interior"] = _interior_numbers(compile_profile(inputs))
    except ValueError as exc:
        record["errors"]["interior"] = str(exc)
    rows = doc["inputs"]
    t02 = rows.get("T02", {}).get("value") or {}
    record["shot_regions"] = dict(t02["rows"][0]["probabilities"]) if t02.get("rows") else None
    record["intervals"] = {iid: _interval(rows[iid]) for iid in OFFENSE_READS + INTERIOR_READS if iid in rows}
    record["reasons"] = {iid: (rows[iid].get("status"), rows[iid].get("reason")) for iid in rows}
    return record


def _stamp(root: str | Path) -> str:
    path = _inputs_path(root)
    st = path.stat()
    from ..interior_defense import FORMULA_VERSION
    from ..offense_response import VERSION as OFFENSE_VERSION
    return "|".join([BRIDGE_VERSION, INPUT_INTERPRETATION_VERSION, OFFENSE_VERSION, FORMULA_VERSION,
                     str(st.st_size), str(int(st.st_mtime))])


def compile_league(root: str | Path, *, refresh: bool = False, write_cache: bool = True) -> dict:
    """{player_id: compiled record} for the whole league; cached in memory and on disk."""
    root = Path(root)
    stamp = _stamp(root)
    key = f"league:{root.resolve()}"
    cached = _MEMORY.get(key)
    if cached and cached["stamp"] == stamp and not refresh:
        return cached
    cache_path = root / CACHE_FILE
    if not refresh and cache_path.exists():
        try:
            data = _load_json(cache_path)
            if data.get("stamp") == stamp:
                _MEMORY[key] = data
                return data
        except ValueError:
            pass
    started = time.perf_counter()
    documents = load_league_documents(root)
    players = {pid: compile_player(root, pid) for pid in sorted(documents)}
    data = {"stamp": stamp, "version": BRIDGE_VERSION, "compile_seconds": round(time.perf_counter() - started, 2),
            "players": players}
    if write_cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True))
    _MEMORY[key] = data
    return data


def offense_profile(record: dict, coefficients: OffenseCoefficients = OffenseCoefficients(), player_id: str = "") -> OffensiveProfile:
    """A kernel-ready OffensiveProfile rebuilt from compiled numbers (inputs=None; the kernels read numbers only)."""
    o = record["offense"]
    return OffensiveProfile(None, player_id, tuple(o["skills"]), o["willingness"], tuple(o["locations"]), tuple(o["modes"]),
                            o["standing_reach_cm"], o["jump_cm"], o["strength"], o["balance"], coefficients,
                            o["revision"], o["ft_probability"], o["input_contract"])


def interior_profile(record: dict, coefficients: Coefficients = Coefficients()) -> InteriorProfile:
    i = record["interior"]
    return InteriorProfile(None, i["positioning"], i["technique"], i["legal"], i["standing_reach_cm"], i["acceleration_m_s2"],
                           i["strength_capacity"], i["balance_capacity"], i["jump_cm"], i["jump_choice"],
                           i["conservative_choice"], i["stay_down_choice"], coefficients, i["revision"],
                           i["input_contract"], i["wingspan_cm"])


def league_offense_profiles(root: str | Path, coefficients: OffenseCoefficients = OffenseCoefficients()) -> dict[str, OffensiveProfile]:
    data = compile_league(root)
    return {pid: offense_profile(rec, coefficients, pid) for pid, rec in data["players"].items() if rec["offense"]}


# ---- coverage ------------------------------------------------------------------------------------------------
def coverage_report(root: str | Path) -> dict:
    data = compile_league(root)
    players = data["players"]
    per_input: dict[str, Counter] = defaultdict(Counter)
    for rec in players.values():
        for iid, (status, reason) in rec["reasons"].items():
            per_input[iid][reason if status != "unknown" else "unknown"] += 1
    families = defaultdict(Counter)
    for iid, counts in per_input.items():
        fam = "passing" if iid.startswith("F") else {"S": "skills", "P": "physical", "T": "tendencies"}[iid[0]]
        families[fam].update(counts)
    def share(iids):
        rows = {iid: dict(per_input[iid]) for iid in iids}
        return {iid: {"prior": c.get("prior", 0), "estimated": c.get("estimated", 0), "unknown_filled": c.get("unknown", 0),
                      "prior_share": round(c.get("prior", 0) / max(1, sum(c.values())), 3)} for iid, c in rows.items()}
    return {
        "players": len(players),
        "offense_compiled": sum(1 for r in players.values() if r["offense"]),
        "interior_compiled": sum(1 for r in players.values() if r["interior"]),
        "errors": {pid: r["errors"] for pid, r in players.items() if r["errors"]},
        "compile_seconds": data.get("compile_seconds"),
        "families": {fam: dict(c) for fam, c in families.items()},
        "offense_inputs": share(OFFENSE_READS),
        "interior_inputs": share(INTERIOR_READS),
        "most_prior_inputs": sorted(((iid, round(c.get("prior", 0) / max(1, sum(c.values())), 3)) for iid, c in per_input.items()),
                                    key=lambda kv: -kv[1])[:20],
    }
