"""Validated, sparse, dormant performance inputs; no engine adapter or defaults.

PlayerInputs owns an immutable serialized snapshot. Plain documents returned to
callers are private copies. The optional save section uses the same definitions
for imported players and future generated players. Absent entries mean unknown.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

from .player_model_registry import REGISTRY_VERSION, definition_registry

INPUT_VERSION = "player_performance_inputs_v1"
SAVE_SECTION = "player_performance_inputs"


def _object(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError(f"Expected object with fields {sorted(required)}; optional {sorted(optional)}")


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected a nonempty string")


def _number(value, low=None, high=None):
    if type(value) not in (int, float):
        raise ValueError("Expected a finite number (not a boolean)")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("Expected a finite number")
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f"Number outside [{low}, {high}]")


def _grade(value):
    _object(value, ("grade", "scale"))
    _number(value["grade"], 0, 100)
    _text(value["scale"])  # Declares the scale; no calibrated anchors are assumed.


def _evidence(rows):
    if not isinstance(rows, list):
        raise ValueError("Evidence must be a list")
    for row in rows:
        _object(row, ("source", "method"), ("as_of", "sample_size", "exposure", "shared_evidence_id", "notes"))
        for key in ("source", "method", "shared_evidence_id", "notes"):
            if key in row:
                _text(row[key])
        if "as_of" in row:
            _text(row["as_of"])
            if date.fromisoformat(row["as_of"]).isoformat() != row["as_of"]:
                raise ValueError("Evidence date must be YYYY-MM-DD")
        if "sample_size" in row and (type(row["sample_size"]) is not int or row["sample_size"] < 0):
            raise ValueError("Sample size must be a nonnegative integer")
        if "exposure" in row:
            _object(row["exposure"], ("value", "unit"))
            _number(row["exposure"]["value"], 0)
            _text(row["exposure"]["unit"])


def _value(definition, value):
    kind = definition["kind"]
    if kind == "grade":
        _grade(value)
    elif kind == "physical":
        _object(value, ("measurements",), ("display_grade",))
        measures = value["measurements"]
        if not isinstance(measures, list) or (not measures and "display_grade" not in value):
            raise ValueError("Physical estimate needs measurements or an explicitly separate grade")
        if definition["id"] in ("P01", "P02", "P03", "P04", "P10") and not measures:
            raise ValueError("Geometry and mass need measurements/estimates in physical units")
        seen = set()
        for measure in measures:
            _object(measure, ("metric", "value", "unit", "protocol"), ("interval",))
            for key in ("metric", "unit", "protocol"):
                _text(measure[key])
            if measure["unit"] not in definition["units"]:
                raise ValueError(f"Unsupported unit for {definition['id']}: {measure['unit']}")
            _number(measure["value"], 0)
            if definition["id"] in ("P01", "P02", "P03", "P04") and measure["value"] == 0:
                raise ValueError("Body dimensions and mass must be positive")
            marker = (measure["metric"], measure["protocol"])
            if marker in seen:
                raise ValueError("Duplicate physical observation metric/protocol")
            seen.add(marker)
            if "interval" in measure:
                interval = measure["interval"]
                if not isinstance(interval, list) or len(interval) != 2:
                    raise ValueError("Measurement interval needs two bounds in its measurement unit")
                for bound in interval:
                    _number(bound, 0)
                if not interval[0] <= measure["value"] <= interval[1]:
                    raise ValueError("Measurement must lie inside its interval")
        if "display_grade" in value:
            _grade(value["display_grade"])
    elif kind == "propensity":
        _object(value, ("probability", "reference_conditions"))
        _number(value["probability"], 0, 1)
        _text(value["reference_conditions"])
    else:
        _object(value, ("reference_conditions", "rows"), ("spatial_reference",))
        _text(value["reference_conditions"])
        if definition["id"] == "T02":
            _text(value.get("spatial_reference"))
        elif "spatial_reference" in value:
            raise ValueError("Spatial region reference belongs to T02")
        if not isinstance(value["rows"], list) or not value["rows"]:
            raise ValueError("Conditional distribution needs at least one row")
        seen = set()
        for row in value["rows"]:
            _object(row, ("condition", "probabilities"))
            _text(row["condition"])
            if row["condition"] in seen:
                raise ValueError("Duplicate distribution condition")
            seen.add(row["condition"])
            probs = row["probabilities"]
            if not isinstance(probs, dict) or not probs:
                raise ValueError("Expected outcome probabilities")
            if definition["outcomes"] and set(probs) != set(definition["outcomes"]):
                raise ValueError("Distribution outcomes must match its family")
            for outcome, probability in probs.items():
                _text(outcome)
                _number(probability, 0, 1)
            if not math.isclose(sum(probs.values()), 1.0, rel_tol=0, abs_tol=1e-9):
                raise ValueError("Distribution must sum to one; values are never silently normalized")


def _record(definition, record):
    _object(record, ("status", "value", "evidence", "uncertainty"), ("reason",))
    if record["status"] not in ("unknown", "estimated", "observed"):
        raise ValueError("Status must be unknown, estimated or observed")
    _evidence(record["evidence"])
    uncertainty = record["uncertainty"]
    _object(uncertainty, ("confidence", "notes"))
    if uncertainty["confidence"] not in ("unknown", "low", "medium", "high"):
        raise ValueError("Unknown confidence category")
    _text(uncertainty["notes"])
    if "reason" in record:
        _text(record["reason"])
    if record["status"] == "unknown":
        _text(record.get("reason"))
        if record["value"] is not None or uncertainty["confidence"] != "unknown":
            raise ValueError("Unknown is null with unknown confidence, never a numeric default")
    else:
        if not record["evidence"]:
            raise ValueError("A known input requires provenance")
        _value(definition, record["value"])


def _validate_player(document, definitions):
    _object(document, ("version", "registry_version", "player_id", "inputs"))
    if document["version"] != INPUT_VERSION or document["registry_version"] != REGISTRY_VERSION:
        raise ValueError("Unsupported player performance input/registry version")
    _text(document["player_id"])
    if not isinstance(document["inputs"], dict):
        raise ValueError("Inputs must be keyed by approved input ID")
    for key, record in document["inputs"].items():
        if key not in definitions:
            raise ValueError(f"Unknown or derived input ID: {key}")
        try:
            _record(definitions[key], record)
        except ValueError as exc:
            raise ValueError(f"{key}: {exc}") from exc


@dataclass(frozen=True, init=False)
class PlayerInputs:
    """Immutable validated input snapshot, serialized with fresh output ownership."""

    _json: str

    def __init__(self, document: dict[str, Any]):
        definitions = {row["id"]: row for row in definition_registry()["inputs"]}
        _validate_player(document, definitions)
        object.__setattr__(self, "_json", json.dumps(document, allow_nan=False, sort_keys=True, separators=(",", ":")))

    @property
    def player_id(self) -> str:
        return self.to_dict()["player_id"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._json)

    def input(self, input_id: str) -> dict | None:
        """A missing entry means unknown, and does not manufacture an estimate."""
        if input_id not in {row["id"] for row in definition_registry()["inputs"]}:
            raise ValueError(f"Unknown or derived input ID: {input_id}")
        return self.to_dict()["inputs"].get(input_id)


def validate_input_section(section: Any) -> None:
    _object(section, ("version", "registry_version", "players"))
    if section["version"] != INPUT_VERSION or section["registry_version"] != REGISTRY_VERSION:
        raise ValueError("Unsupported player performance input/registry version")
    if not isinstance(section["players"], dict):
        raise ValueError("Players must be keyed by stable player ID")
    definitions = {row["id"]: row for row in definition_registry()["inputs"]}
    for player_id, document in section["players"].items():
        _text(player_id)
        _validate_player(document, definitions)
        if player_id != document["player_id"]:
            raise ValueError("Player key and player_id differ")


def put_player_inputs(save: dict, inputs: PlayerInputs) -> None:
    """Attach a private validated copy; no population, engine conversion or growth."""
    section = save.get(SAVE_SECTION, {"version": INPUT_VERSION, "registry_version": REGISTRY_VERSION, "players": {}})
    # Validate before mutation, including existing unsupported/malformed data.
    validate_input_section(section)
    section = json.loads(json.dumps(section, allow_nan=False))
    document = inputs.to_dict()
    section["players"][document["player_id"]] = document
    save[SAVE_SECTION] = section


def get_player_inputs(save: dict, player_id: str) -> PlayerInputs | None:
    if SAVE_SECTION not in save:
        return None
    validate_input_section(save[SAVE_SECTION])
    document = save[SAVE_SECTION]["players"].get(player_id)
    return None if document is None else PlayerInputs(document)
