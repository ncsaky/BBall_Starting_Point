from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace(".", "").replace("-", " ")
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slugify(text: str | None) -> str:
    base = normalize_name(text).replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def stable_id(prefix: str, *parts: object) -> str:
    body = "-".join(slugify(str(part)) for part in parts if part is not None and str(part) != "")
    return f"{prefix}_{body}" if body else prefix


def maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def parse_inches(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return maybe_float(value)
    text = str(value).strip()
    if not text:
        return None
    feet_match = re.match(r"(?P<feet>\d+)'\s*(?P<inches>\d+(?:\.\d+)?)?", text)
    if feet_match:
        feet = float(feet_match.group("feet"))
        inches = float(feet_match.group("inches") or 0)
        return feet * 12 + inches
    return maybe_float(text)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def mean(values: Iterable[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def percentile_maps(rows: list[dict[str, Any]], fields: Iterable[str]) -> dict[str, dict[int, float]]:
    maps: dict[str, dict[int, float]] = {}
    for field in fields:
        values: list[tuple[int, float]] = []
        for idx, row in enumerate(rows):
            number = maybe_float(row.get(field))
            if number is not None:
                values.append((idx, number))
        values.sort(key=lambda item: item[1])
        if not values:
            maps[field] = {}
            continue
        denom = max(1, len(values) - 1)
        field_map: dict[int, float] = {}
        for rank, (idx, _) in enumerate(values):
            field_map[idx] = 100.0 * rank / denom
        maps[field] = field_map
    return maps


def percentile(percentiles: dict[str, dict[int, float]], field: str, idx: int, inverse: bool = False) -> float | None:
    value = percentiles.get(field, {}).get(idx)
    if value is None:
        return None
    return 100.0 - value if inverse else value


def present_count(row: dict[str, Any], fields: Iterable[str]) -> int:
    count = 0
    for field in fields:
        if maybe_float(row.get(field)) is not None:
            count += 1
    return count


def confidence_from_fields(row: dict[str, Any], fields: Iterable[str], base: float = 0.2, cap: float = 0.9) -> float:
    fields = list(fields)
    if not fields:
        return base
    coverage = present_count(row, fields) / len(fields)
    return round(min(cap, base + coverage * (cap - base)), 3)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [re.sub(r"\s+", " ", part).strip() for part in parts if part.strip()]
