"""Explicit selection ranges shared by pick labels, validation and resolution."""

import re
from typing import Any


def protection_bounds(term: dict[str, Any]) -> tuple[int, int]:
    protected = term.get("protected_range") or {}
    try:
        raw_low = protected.get("from", 1)
        raw_high = protected.get("through", term.get("protected_top_n", 0))
        low, high = int(raw_low), int(raw_high)
        if any(isinstance(value, bool) or float(value) != int(value) for value in (raw_low, raw_high)):
            raise ValueError("Non-integer protection range")
        if term.get("protected_top_n") is not None and int(term["protected_top_n"]) != high:
            raise ValueError("Conflicting protection ranges")
        maximum = 30 if int(term.get("round") or term.get("primary_round") or 0) == 1 else 60
    except (TypeError, ValueError):
        raise ValueError("Pick protection requires an explicit numeric selection range.") from None
    if not 1 <= low <= high <= maximum:
        raise ValueError("Pick protection requires an explicit valid selection range; generic protection is not permitted.")
    return low, high


# NBA Board of Governors, 2026-05-28 (the "3-2-1" lottery). Announcement: "Teams will be unable to attach top-12
# through top-15 protections to newly traded draft picks." Official rules sheet: "Can't protect picks top-12 through
# top-15 in trades." Protections agreed before that stay as they are, so only new trade terms are checked.
BANNED_PROTECTION_ENDS = (12, 15)


def new_protection_issue(low: int, high: int, round_no: int) -> str:
    """Why this range can't be attached to a pick in a new trade ("" when it can).

    A range that stops at 12-15 is refused wherever it starts ("picks 2-14" would be a top-14 protection in all but
    name). Second-round picks are numbered 31-60, so the rule only reaches first-round picks.
    """
    first, last = BANNED_PROTECTION_ENDS
    if round_no != 2 and first <= high <= last:
        return (f"The league doesn't allow new protections that stop at picks {first} through {last}. "
                f"Protect through pick {first - 1} or earlier, or {last + 1} or later.")
    return ""


def ordinal(number: int) -> str:
    words = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth"]
    if number < 20:
        return words[number]
    tens = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty"}
    exact = {2: "twentieth", 3: "thirtieth", 4: "fortieth", 5: "fiftieth", 6: "sixtieth"}
    return exact[number // 10] if number % 10 == 0 else f"{tens[number // 10]}-{words[number % 10]}"


_TRAILING_NUMBER = re.compile(r"-(\d+)$").search


def ordered_pick_obligations(terms):
    """Restore imported allocation sequence, never alphabetical ID order.

    RealGM obligation IDs retain their source sequence as the final number.
    Older saves alphabetized those IDs, reversing dependent comparisons.
    Keep unrelated/custom obligations in place and preserve ownership/status.
    """
    output = list(terms)
    slots = []
    imported = []
    for index, term in enumerate(output):
        identifier = str(term.get("id") or "")
        if not identifier.startswith("pick_obligation_realgm-"):
            continue
        match = _TRAILING_NUMBER(identifier)
        if match:
            slots.append(index)
            imported.append((term.get("type") != "protected_pick", int(match.group(1)), index, term))
    imported.sort(key=lambda item: item[:3])
    for index, item in zip(slots, imported):
        output[index] = item[3]
    return output
