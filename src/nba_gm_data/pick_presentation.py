"""Pick entitlement expressions, labels and explicit draft-resolution references."""

from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
from operator import methodcaller
import pickle
from typing import Any

from .utils import stable_id
from .pick_rules import ordinal, protection_bounds, ordered_pick_obligations


def _indexed_view(canonical: dict[str, Any]) -> dict[str, Any]:
    """Share lookups only within this read-only presentation operation."""
    index = canonical.get("_pick_presentation_index")
    picks = canonical.get("draft_picks", [])
    terms = canonical.get("pick_obligations", [])
    teams = canonical.get("teams", [])
    if index and index["picks_source"] is picks and index["terms_source"] is terms and index["teams_source"] is teams:
        return canonical
    return {**canonical, "_pick_presentation_index": {
        "picks_source": picks, "terms_source": terms, "teams_source": teams,
        "picks": {pick["id"]: pick for pick in picks},
        "teams": {team.get("id"): team.get("abbrev") for team in teams},
        "active": [term for term in ordered_pick_obligations(terms)
                   if term.get("type") == "pick_swap" and term.get("status", "active") in {"active", "pending_resolution"}],
    }}


def _rebased_view(canonical: dict[str, Any], picks: list[dict[str, Any]]) -> dict[str, Any]:
    """The indexed view with a replacement pick list; terms and teams (and their ordering) are reused."""
    index = canonical["_pick_presentation_index"]
    return {**canonical, "draft_picks": picks, "_pick_presentation_index": {
        "picks_source": picks, "terms_source": index["terms_source"], "teams_source": index["teams_source"],
        "picks": {pick["id"]: pick for pick in picks}, "teams": index["teams"], "active": index["active"],
    }}


def _term_table(canonical: dict[str, Any]) -> dict[str, Any]:
    """Per-view facts about the active swap terms (subjects, prefixes, holders), computed once.

    Valid for the same read-only operation as the index itself: the view's picks and terms are not
    edited while it is in use.
    """
    index = canonical["_pick_presentation_index"]
    table = index.get("term_table")
    if table is None:
        active = index["active"]
        subjects = [_subjects(term) for term in active]
        prefixes = [_prefix_from(canonical, term, ids) for term, ids in zip(active, subjects)]
        holders = [_holder(term) for term in active]
        buckets: dict[tuple[Any, str], list[int]] = {}
        for position, key in enumerate(zip(holders, prefixes)):
            buckets.setdefault(key, []).append(position)
        positions: dict[int, int] = {}
        for position, term in enumerate(active):
            positions.setdefault(id(term), position)
        protected = [term for term in canonical.get("pick_obligations", []) if term.get("type") == "protected_pick"
                     and term.get("status", "active") in {"active", "pending_resolution"}]
        table = index["term_table"] = {
            "subjects": subjects, "subject_sets": [set(ids) for ids in subjects], "prefixes": prefixes,
            "holders": holders, "buckets": buckets, "positions": positions, "protected": protected,
        }
    return table


def _term_facts(canonical: dict[str, Any], term: dict[str, Any]) -> tuple[list[str], str, str | None]:
    """(subjects, prefix, holder) of a term, read from the view's table when the term is one of its rows."""
    table = _term_table(canonical)
    position = table["positions"].get(id(term))
    if position is not None and canonical["_pick_presentation_index"]["active"][position] is term:
        return table["subjects"][position], table["prefixes"][position], table["holders"][position]
    subjects = _subjects(term)
    return subjects, _prefix_from(canonical, term, subjects), _holder(term)


def _holder(term: dict[str, Any]) -> str | None:
    return term.get("current_rights_holder_team_id") or term.get("original_rights_holder_team_id") or term.get("receiver_team_id")


def _better(term: dict[str, Any]) -> bool:
    return str(term.get("benefit") or term.get("swap_benefit") or term.get("rights_benefit") or "better").lower() not in {"worse", "less", "less_favorable", "lower"}


def _subjects(term: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(pid for pid in [term.get("team_a_pick_id") or term.get("primary_pick_id"), term.get("team_b_pick_id") or term.get("counterparty_pick_id"), *(term.get("comparison_pool_pick_ids") or [])] if pid))


def _active(canonical: dict[str, Any]) -> list[dict[str, Any]]:
    if canonical.get("_pick_presentation_index"):
        return canonical["_pick_presentation_index"]["active"]
    return [term for term in ordered_pick_obligations(canonical.get("pick_obligations", [])) if term.get("type") == "pick_swap" and term.get("status", "active") in {"active", "pending_resolution"}]


def _protections(canonical: dict[str, Any], pick_ids: list[str]) -> list[dict[str, Any]]:
    if canonical.get("_pick_presentation_index"):
        return [term for term in _term_table(canonical)["protected"] if term.get("primary_pick_id") in pick_ids]
    return [term for term in canonical.get("pick_obligations", []) if term.get("type") == "protected_pick" and term.get("status", "active") in {"active", "pending_resolution"} and term.get("primary_pick_id") in pick_ids]


def _team(canonical: dict[str, Any], team_id: str | None) -> str:
    if canonical.get("_pick_presentation_index"):
        return canonical["_pick_presentation_index"]["teams"].get(team_id) or str(team_id or "TBD").removeprefix("team_").upper()
    return next((team.get("abbrev") for team in canonical.get("teams", []) if team.get("id") == team_id), None) or str(team_id or "TBD").removeprefix("team_").upper()


def _pick_map(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if canonical.get("_pick_presentation_index"):
        return canonical["_pick_presentation_index"]["picks"]
    return {pick["id"]: pick for pick in canonical.get("draft_picks", [])}


def _names(canonical: dict[str, Any], pick_ids: list[str]) -> str:
    picks = _pick_map(canonical)
    return "/".join(dict.fromkeys(_team(canonical, picks.get(pid, {}).get("original_team_id")) for pid in pick_ids))


def _prefix(canonical: dict[str, Any], term: dict[str, Any]) -> str:
    return _prefix_from(canonical, term, _subjects(term))


def _prefix_from(canonical: dict[str, Any], term: dict[str, Any], subjects: list[str]) -> str:
    pick = _pick_map(canonical).get(subjects[0] if subjects else "", {})
    return f"{term.get('season') or pick.get('season') or '----'} R{term.get('round') or pick.get('round') or '?'}"


def _remainder(canonical: dict[str, Any], holder: str | None, owners: list[str | None], favourable: str, opposite: str) -> str:
    owners = list(dict.fromkeys(owner for owner in owners if owner))
    others = [owner for owner in owners if owner != holder]
    if len(others) == 1:
        return f"{_team(canonical, others[0])} receives the {opposite} favourable of those two picks."
    # A transferred right can belong to neither subject's current owner.
    # The engine gives the remaining pick to the displaced owner, so name
    # both deterministic branches instead of choosing a fictitious recipient.
    return " ".join(f"If the {favourable} favourable pick is transferred from {_team(canonical, owner)}, {_team(canonical, owner)} receives the {opposite} favourable of those two picks." for owner in owners)


def swap_step_label(canonical: dict[str, Any], term: dict[str, Any]) -> str:
    picks = _pick_map(canonical)
    ids = _subjects(term)
    holder_id = _holder(term)
    holder = _team(canonical, holder_id)
    better = _better(term)
    favourable = "more" if better else "less"
    opposite = "less" if better else "more"
    pool = term.get("comparison_pool_pick_ids") or []
    if pool:
        comparing_id = term.get("comparison_holder_team_id")
        counterparty_id = term.get("comparison_counterparty_team_id")
        comparing = _team(canonical, comparing_id)
        counterparty = _team(canonical, counterparty_id)
        counts = Counter(picks.get(pid, {}).get("current_owner_team_id") for pid in pool)
        left = f"the {'least' if better else 'most'} favourable pick held by {comparing}" if counts[comparing_id] > 1 else f"the pick allocated to {comparing}"
        right = f"the {'most' if better else 'least'} favourable pick held by {counterparty}" if counts[counterparty_id] > 1 else f"the pick allocated to {counterparty}"
        remainder = _remainder(canonical, holder_id, [comparing_id, counterparty_id], favourable, opposite)
        body = f"{holder} receives the {favourable} favourable of {left} and {right} from {_names(canonical, pool)}; {remainder}"
        if _protections(canonical, pool):
            body = f"If {comparing} or {counterparty} holds no pick in this pool after protections resolve, this comparison is skipped and ownership stays unchanged. Otherwise, {body}"
    else:
        owners = [picks.get(pid, {}).get("current_owner_team_id") for pid in ids[:2]]
        remainder = _remainder(canonical, holder_id, owners or [term.get("counterparty_team_id")], favourable, opposite)
        body = f"{holder} receives the {favourable} favourable of {_names(canonical, ids[:2])}; {remainder}"
    protected = term.get("subject_protected_top_n") or {}
    ranges = [f"{_names(canonical, [pid])}: picks 1–{int(top)}" for pid, top in protected.items() if int(top or 0) > 0]
    if ranges:
        body = f"If a compared pick falls in its protected range ({'; '.join(ranges)}), both compared picks stay with their current owners. Otherwise, {body}"
    return f"{_prefix(canonical, term)}: {body}"


def _group(canonical: dict[str, Any], term: dict[str, Any]) -> list[dict[str, Any]]:
    if term.get("allocation_comparison"):
        return [term]
    if not canonical.get("_pick_presentation_index"):
        canonical = _indexed_view(canonical)
    active = _active(canonical)
    table = _term_table(canonical)
    subjects, prefix, holder = _term_facts(canonical, term)
    # Rows sharing this term's holder and season/round prefix, in active order.
    bucket = table["buckets"].get((holder, prefix), ())
    if term.get("nested_anchor_pick_id"):
        return [active[i] for i in bucket if active[i].get("nested_anchor_pick_id") == term["nested_anchor_pick_id"]]
    candidates = [i for i in bucket if not active[i].get("allocation_comparison")]
    subject_sets, subject_lists = table["subject_sets"], table["subjects"]
    ids = set(subjects)
    selected = {term.get("id")}
    while True:
        connected = [i for i in candidates if not ids.isdisjoint(subject_sets[i])]
        new_selected = {active[i].get("id") for i in connected} | selected
        if new_selected == selected:
            break
        selected = new_selected
        ids.update(pid for i in connected for pid in subject_lists[i])
    return [active[i] for i in candidates if active[i].get("id") in selected] or [term]


def _dependencies(canonical: dict[str, Any], group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not canonical.get("_pick_presentation_index"):
        canonical = _indexed_view(canonical)
    terms = _active(canonical)
    table = _term_table(canonical)
    group_ids = {row.get("id") for row in group}
    last = max((index for index, row in enumerate(terms) if row.get("id") in group_ids), default=-1)
    needed = set(pid for row in group for pid in _term_facts(canonical, row)[0])
    prefix = _term_facts(canonical, group[0])[1]
    prefixes, subject_sets, subject_lists = table["prefixes"], table["subject_sets"], table["subjects"]
    rows = []
    for position in range(last, -1, -1):
        if prefixes[position] == prefix and not needed.isdisjoint(subject_sets[position]):
            rows.append(terms[position])
            needed.update(subject_lists[position])
    return list(reversed(rows)) or group


def _fold_label(canonical: dict[str, Any], group: list[dict[str, Any]], dependencies: list[dict[str, Any]]) -> str | None:
    # Flatten only a proven one-slot chain of identical min/max comparisons.
    # Mixed allocations, earlier outside comparisons and protections retain
    # their ordered explanation instead of inventing a best-of-all promise.
    if len(group) < 2 or dependencies != group or any(row.get("subject_protected_top_n") for row in group) or len({_better(row) for row in group}) != 1:
        return None
    picks = _pick_map(canonical)
    holder = _holder(group[0])
    all_ids = list(dict.fromkeys(pid for row in group for pid in _subjects(row)))
    if _protections(canonical, all_ids):
        return None
    held = [pid for pid in all_ids if picks.get(pid, {}).get("current_owner_team_id") == holder]
    if len(held) != 1:
        return None
    seen = {held[0]}
    for index, row in enumerate(group):
        subjects = set(_subjects(row))
        if not seen.intersection(subjects) or len(subjects - seen) != 1:
            return None
        if row.get("comparison_pool_pick_ids"):
            new_id = next(iter(subjects - seen))
            if row.get("comparison_holder_team_id") != holder or picks.get(new_id, {}).get("current_owner_team_id") != row.get("comparison_counterparty_team_id"):
                return None
        elif index:
            # A later fixed-ID swap compares the original pick again, not
            # the entitlement selected by the preceding comparison.
            return None
        seen.update(subjects)
    outcome = "most" if _better(group[0]) else "least"
    return f"{_prefix(canonical, group[0])}: {_team(canonical, holder)} receives the {outcome} favourable of {_names(canonical, all_ids)}."


def _compute_nested_entitlements(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Project proven single-slot chains onto their existing pick ID.

    Leaves remain physical picks; every swap node selects exactly one output.
    No new pick or ownership record is created by this projection.
    """
    canonical = _indexed_view(canonical)
    picks = _pick_map(canonical)
    result = {}
    seen = set()
    for term in _active(canonical):
        group = _group(canonical, term)
        key = tuple(row.get("id") for row in group)
        if key in seen:
            continue
        seen.add(key)
        holder = _holder(group[0])
        ids = list(dict.fromkeys(pid for row in group for pid in _subjects(row)))
        explicit = group[0].get("nested_anchor_pick_id")
        if len(group) < 2 or any(pid not in picks for pid in ids):
            continue
        if any(row.get("subject_protected_top_n") for row in group) or _protections(canonical, ids):
            continue
        held = [pid for pid in ids if picks[pid].get("current_owner_team_id") == holder]
        # Existing output references remain authoritative if the buyer also
        # owns another leaf. Ownership counts must not dissolve the bundle.
        anchor = explicit or (held[0] if len(held) == 1 else None)
        if not anchor or anchor not in picks or picks[anchor].get("current_owner_team_id") != holder:
            continue
        if not explicit and _dependencies(canonical, group) != group:
            continue
        used_check = {anchor}
        previous_check = None
        valid = True
        for index, row in enumerate(group):
            new_ids = set(_subjects(row)) - used_check
            expected_input = {"obligation_id": previous_check} if previous_check else {"pick_id": anchor}
            if explicit:
                other = row.get("nested_other_pick_id")
                valid = row.get("nested_input") == expected_input and other in picks and other not in used_check
            else:
                valid = bool(used_check.intersection(_subjects(row))) and len(new_ids) == 1
                other = next(iter(new_ids), None)
                if index and not row.get("comparison_pool_pick_ids"):
                    valid = False
                if row.get("comparison_pool_pick_ids") and (row.get("comparison_holder_team_id") != holder or picks.get(other, {}).get("current_owner_team_id") != row.get("comparison_counterparty_team_id")):
                    valid = False
            if not valid:
                break
            used_check.add(other)
            previous_check = row["id"]
        if not valid:
            continue
        def leaf(pid):
            return {"type": "pick", "pick_id": pid, "team_abbrev": _team(canonical, picks[pid].get("original_team_id")),
                    "owner_abbrev": _team(canonical, picks[pid].get("current_owner_team_id"))}
        tree = leaf(anchor)
        used = {anchor}
        steps = []
        previous = None
        for row in group:
            other = row.get("nested_other_pick_id") if explicit else next(pid for pid in _subjects(row) if pid not in used)
            input_ref = {"obligation_id": previous} if previous else {"pick_id": anchor}
            steps.append({"obligation_id": row["id"], "input": input_ref, "other_pick_id": other})
            tree = {"type": "swap", "obligation_id": row["id"], "benefit": "better" if _better(row) else "worse",
                    "left": tree, "right": leaf(other), "recipient_abbrev": _team(canonical, holder)}
            used.add(other)
            previous = row["id"]
        def describe(node):
            if node["type"] == "pick":
                return node["team_abbrev"]
            return f"[the {'more' if node['benefit'] == 'better' else 'less'} favourable of {describe(node['left'])}/{describe(node['right'])}]"
        label = f"{_prefix(canonical, group[-1])}: {_team(canonical, holder)} receives {describe(tree)[1:-1]}."
        result[anchor] = {"anchor_pick_id": anchor, "root_obligation_id": previous, "obligation_ids": list(key),
                          "underlying_pick_ids": ids, "rights_holder_team_id": holder, "tree": tree, "steps": steps,
                          "label": label, "pick_count": 1}
    return result


def materialize_nested_inputs(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Persist explicit output references without moving anyone's picks."""
    entitlements = nested_entitlements(canonical)
    terms = {row.get("id"): row for row in canonical.get("pick_obligations", [])}
    for anchor, entitlement in entitlements.items():
        for step in entitlement["steps"]:
            row = terms[step["obligation_id"]]
            row["nested_anchor_pick_id"] = anchor
            row["nested_input"] = step["input"]
            row["nested_other_pick_id"] = step["other_pick_id"]
    # Preserve downstream claims on a counterparty's REMAINDER, even if a
    # buyer later owns several leaves in the pool. The claim follows the
    # output slot, not every physical pick that happens to share an owner.
    slots = {}
    bundled = {step["obligation_id"] for item in entitlements.values() for step in item["steps"]}
    for row in _active(canonical):
        if row.get("id") in bundled:
            slots[row["nested_anchor_pick_id"]] = {"obligation_id": row["id"]}
            slots[row["nested_other_pick_id"]] = {"obligation_id": row["id"], "outcome": "remainder"}
        elif row.get("comparison_pool_pick_ids") and not row.get("allocation_comparison"):
            left = row.get("team_a_pick_id") or row.get("primary_pick_id")
            right = row.get("team_b_pick_id") or row.get("counterparty_pick_id")
            pool = set(row["comparison_pool_pick_ids"])
            referenced = slots.get(left) or slots.get(right)
            picks = _pick_map(canonical)
            if referenced and {left, right}.issubset(pool):
                # Only a one-slot comparison can be converted this way.
                owners = [row.get("comparison_holder_team_id"), row.get("comparison_counterparty_team_id")]
                if all(sum(picks.get(pid, {}).get("original_team_id") == owner for pid in pool) == 1 for owner in owners):
                    row.setdefault("nested_input", slots.get(left, {"pick_id": left}))
                    row.setdefault("nested_other_input", slots.get(right, {"pick_id": right}))
                    row.setdefault("nested_other_pick_id", right)
    # Save the rank-to-asset mapping before any trade changes its owner.
    for entitlement in ranked_pool_entitlements(canonical).values():
        pool = set(entitlement["pool_pick_ids"])
        for row in _active(canonical):
            if row.get("allocation_comparison") and set(row.get("comparison_pool_pick_ids") or []) == pool:
                row["allocation_slot_pick_ids"] = entitlement["allocation_slot_pick_ids"]
    return entitlements


def _compute_swap_presentation(canonical: dict[str, Any], term: dict[str, Any]) -> dict[str, Any]:
    canonical = _indexed_view(canonical)
    group = _group(canonical, term)
    dependencies = _dependencies(canonical, group)
    ids = list(dict.fromkeys(pid for row in dependencies for pid in _subjects(row)))
    picks = _pick_map(canonical)
    team_ids = list(dict.fromkeys(picks.get(pid, {}).get("original_team_id") for pid in ids if picks.get(pid, {}).get("original_team_id")))
    asset_ids = list(dict.fromkeys(pid for row in _dependencies(canonical, [term]) for pid in _subjects(row)))
    asset_team_ids = list(dict.fromkeys(picks.get(pid, {}).get("original_team_id") for pid in asset_ids if picks.get(pid, {}).get("original_team_id")))
    front_id = _holder(term) if _better(term) else term.get("comparison_counterparty_team_id")
    if not front_id:
        front_id = next((picks.get(pid, {}).get("current_owner_team_id") for pid in _subjects(term)[:2] if picks.get(pid, {}).get("current_owner_team_id") != _holder(term)), None)
    front_team = _team(canonical, front_id) if front_id else None
    origins = [_team(canonical, tid) for tid in team_ids]
    # Main bubbles represent the original assets. A transferred entitlement
    # is identified by a badge, never by adding a third owner logo.
    if front_team not in origins:
        original_b = picks.get(term.get("team_b_pick_id") or term.get("counterparty_pick_id"), {}).get("original_team_id")
        front_team = _team(canonical, original_b) if original_b else origins[-1] if origins else None
    team_owners = {_team(canonical, picks[pid].get("original_team_id")): _team(canonical, picks[pid].get("current_owner_team_id")) for pid in ids if pid in picks}
    pair_owners = {}
    counterparty = term.get("comparison_counterparty_team_id") or term.get("counterparty_team_id")
    comparing_holder = term.get("comparison_holder_team_id")
    direct_owners = {picks.get(pid, {}).get("current_owner_team_id") for pid in _subjects(term)[:2]}
    if len(origins) == 2 and counterparty and (_holder(term) == comparing_holder or _holder(term) in direct_owners):
        better_recipient = _holder(term) if _better(term) else counterparty
        worse_recipient = counterparty if _better(term) else _holder(term)
        back_team = next(origin for origin in origins if origin != front_team)
        pair_owners = {front_team: _team(canonical, better_recipient), back_team: _team(canonical, worse_recipient)}
    nested = next((item for item in nested_entitlements(canonical).values() if term.get("id") in item["obligation_ids"]), None)
    label = nested["label"] if nested else _fold_label(canonical, group, dependencies)
    if label is None:
        label = swap_step_label(canonical, group[0]) if len(dependencies) == 1 else f"{_prefix(canonical, group[0])} connected allocation — apply in this order:\n" + "\n".join(f"{index}. {swap_step_label(canonical, row).split(': ', 1)[-1]}" for index, row in enumerate(dependencies, 1))
    protection_notes = []
    for protection in _protections(canonical, ids):
        primary = picks.get(protection.get("primary_pick_id"), {})
        original = _team(canonical, primary.get("original_team_id"))
        receiver = _team(canonical, primary.get("current_owner_team_id") if primary.get("current_owner_team_id") != protection.get("sender_team_id") else protection.get("receiver_team_id"))
        low, high = protection_bounds(protection)
        range_label = f"picks {low}–{high}"
        note = f"If {original} lands in {range_label}, {original} retains that pick; otherwise, {receiver} receives it."
        fallback = next((picks[pid] for pid in protection.get("fallback_pick_ids", []) if pid in picks), None)
        if fallback:
            note += f" In the protected branch, {receiver} instead receives {fallback.get('season')} R{fallback.get('round')} {_team(canonical, fallback.get('original_team_id'))}."
        protection_notes.append(note)
    if protection_notes:
        label = "First resolve protections: " + " ".join(protection_notes) + "\nThen " + label
    return {
        "label": label,
        "nested_entitlement": nested,
        "team_ids": team_ids,
        "team_abbrevs": [_team(canonical, tid) for tid in team_ids],
        "asset_team_abbrevs": [_team(canonical, tid) for tid in asset_team_ids],
        "front_team_abbrev": front_team,
        "team_owners": team_owners,
        "pair_icon_owners": pair_owners,
        "is_swap": True,
        "has_protection": bool(_protections(canonical, ids) or any(row.get("subject_protected_top_n") for row in dependencies)),
        "asset_has_protection": bool(_protections(canonical, asset_ids) or any(row.get("subject_protected_top_n") for row in _dependencies(canonical, [term]))),
        "group_id": stable_id("pick_display", *[row.get("id") for row in group]),
        "obligation_ids": [row.get("id") for row in group],
        "underlying_pick_ids": ids,
        "rights_holder_team_id": _holder(term),
    }


def _compute_ranked_pool_entitlements(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Assign one stable rank to each existing pick asset in a proven pool.

    The guarantee follows that asset when traded. Original allocation owners
    determine ranks; current owners only determine who can offer the asset.
    Protected/mixed/dependent pools are deliberately not treated as a sort.
    """
    canonical = _indexed_view(canonical)
    result = {}
    picks = _pick_map(canonical)
    seen = set()
    baseline = None
    for term in _active(canonical):
        pool = term.get("comparison_pool_pick_ids") or []
        key = tuple(sorted(pool))
        if not term.get("allocation_comparison") or not pool or key in seen:
            continue
        seen.add(key)
        if baseline is None:
            # Built once per call: the picks are not edited while this projection runs.
            baseline_picks = [{**pick, "current_owner_team_id": pick.get("_allocation_initial_owner_team_id") or pick.get("current_owner_team_id")} for pick in picks.values()]
            baseline = _rebased_view(canonical, baseline_picks)
            initial = {pick["id"]: pick for pick in baseline_picks}
        owner = term.get("comparison_holder_team_id")
        if not _ranked_allocation_label(baseline, term, owner):
            continue
        rows = [row for row in _active(canonical) if set(row.get("comparison_pool_pick_ids") or []) == set(pool)]
        remaining = {initial[pid].get("current_owner_team_id") for pid in pool}
        order = []
        edges = [(row.get("comparison_holder_team_id"), row.get("comparison_counterparty_team_id")) for row in rows]
        while remaining:
            roots = [tid for tid in remaining if not any(b == tid and a in remaining for a, b in edges)]
            if len(roots) != 1:
                break
            order.append(roots[0]); remaining.remove(roots[0])
        if remaining:
            continue
        slots = [pid for tid in order for pid in sorted(pool) if initial[pid].get("current_owner_team_id") == tid]
        for rank, pid in enumerate(slots, 1):
            result[pid] = {"pool_pick_ids": list(key), "rank": rank, "pool_size": len(pool), "allocation_slot_pick_ids": slots}
    return result


def _ranked_allocation_label(canonical: dict[str, Any], term: dict[str, Any], owner: str | None) -> str | None:
    pool = term.get("comparison_pool_pick_ids") or []
    if not term.get("allocation_comparison") or not pool:
        return None
    if _protections(canonical, pool):
        return None
    if canonical.get("_pick_presentation_index"):
        active, subject_sets = _active(canonical), _term_table(canonical)["subject_sets"]
        rows = [row for row, subjects in zip(active, subject_sets) if not subjects.isdisjoint(pool)]
    else:
        rows = [row for row in _active(canonical) if set(_subjects(row)).intersection(pool)]
    if any(not row.get("allocation_comparison") or row.get("subject_protected_top_n") or set(row.get("comparison_pool_pick_ids") or []) != set(pool) or not _better(row) for row in rows):
        return None
    picks = _pick_map(canonical)
    counts = Counter(picks.get(pid, {}).get("current_owner_team_id") for pid in pool)
    edges = list(dict.fromkeys((row.get("comparison_holder_team_id"), row.get("comparison_counterparty_team_id")) for row in rows))
    order = []
    remaining = set(counts) - {None}
    while remaining:
        roots = [tid for tid in remaining if not any(b == tid and a in remaining for a, b in edges)]
        if len(roots) != 1:
            return None
        order.append(roots[0])
        remaining.remove(roots[0])
    expected = [(order[i], order[i + 1]) for step in range(len(order) - 1) for i in range(len(order) - 1 - step)]
    if len(order) == 2:
        expected = [(order[0], order[1])] * min(counts.values())
    actual = [(row.get("comparison_holder_team_id"), row.get("comparison_counterparty_team_id")) for row in rows]
    if actual != expected or owner not in order:
        return None
    amount = counts[owner]
    first = sum(counts[tid] for tid in order[:order.index(owner)]) + 1
    last = first + amount - 1
    if first == 1:
        rank = ("the more favourable" if len(pool) == 2 else "the most favourable") if amount == 1 else f"the {amount} most favourable"
    elif last == len(pool):
        rank = ("the less favourable" if len(pool) == 2 else "the least favourable") if amount == 1 else f"the {amount} least favourable"
    else:
        # Use the nearer end; ties use least, so a three-pick middle slot is
        # "second least favourable", matching the approved language.
        from_least = first + last >= len(pool) + 1
        positions = list(range(len(pool) - last + 1, len(pool) - first + 2)) if from_least else list(range(first, last + 1))
        words = [ordinal(position) for position in positions]
        ranks = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
        rank = f"the {ranks} {'least' if from_least else 'most'} favourable"
    return f"{_prefix(canonical, term)}: {_team(canonical, owner)} receives {rank} of {_names(canonical, pool)}."


def _compute_pick_presentation(canonical: dict[str, Any], pick: dict[str, Any]) -> dict[str, Any] | None:
    canonical = _indexed_view(canonical)
    terms = [row for row in _active(canonical) if pick.get("id") in _subjects(row)]
    if not terms:
        return None
    owner = pick.get("current_owner_team_id")
    owned_rights = [row for row in terms if _holder(row) == owner and not row.get("allocation_comparison")]
    compared_owner = [row for row in terms if owner in {row.get("comparison_holder_team_id"), row.get("comparison_counterparty_team_id")}]
    term = owned_rights[0] if owned_rights else compared_owner[-1] if compared_owner else terms[0]
    result = swap_presentation(canonical, term)
    if result.get("nested_entitlement") and pick.get("id") != result["nested_entitlement"]["anchor_pick_id"]:
        result.pop("nested_entitlement", None)
    asset_rank = pick.get("_ranked_entitlement")
    if asset_rank:
        result["asset_rank"] = asset_rank["rank"]
        result["asset_pool_size"] = asset_rank["pool_size"]
    ranked = _ranked_allocation_label(canonical, term, owner)
    if ranked:
        result["label"] = ranked
        pool = term.get("comparison_pool_pick_ids") or []
        rows = [row for row in _active(canonical) if set(row.get("comparison_pool_pick_ids") or []) == set(pool)]
        holders = {row.get("comparison_holder_team_id") for row in rows}
        counterparties = {row.get("comparison_counterparty_team_id") for row in rows}
        first_recipient = holders - counterparties
        if len(first_recipient) == 1:
            front = _team(canonical, next(iter(first_recipient)))
            if front in result["team_abbrevs"]:
                result["front_team_abbrev"] = front
        if result.get("pair_icon_owners"):
            front = result["front_team_abbrev"]
            better_owner = result["pair_icon_owners"][front]
            worse_owner = next(owner for origin, owner in result["pair_icon_owners"].items() if origin != front)
            result["label"] = f"{_prefix(canonical, term)}: {better_owner} receives the more favourable of {_names(canonical, pool)}; {worse_owner} receives the less favourable of those two picks."
        # Arrange layers by outcome rank, not source-file participant order.
        # A two-pick recipient occupies the first two layers; the one-pick
        # remainder recipient goes behind both (HOU/PHX/DAL in 2029).
        owner_order = []
        remaining_owners = {_pick_map(canonical).get(pid, {}).get("current_owner_team_id") for pid in pool} - {None}
        edges = [(row.get("comparison_holder_team_id"), row.get("comparison_counterparty_team_id")) for row in rows]
        while remaining_owners:
            roots = [tid for tid in remaining_owners if not any(b == tid and a in remaining_owners for a, b in edges)]
            if len(roots) != 1:
                break
            owner_order.append(roots[0])
            remaining_owners.remove(roots[0])
        if not remaining_owners:
            owner_ranks = {_team(canonical, tid): index for index, tid in enumerate(owner_order)}
            result["team_abbrevs"] = sorted(result["team_abbrevs"], key=lambda origin: owner_ranks.get(result["team_owners"].get(origin), len(owner_order)))
        result["pool_group_id"] = stable_id("pick_pool_display", owner, *pool)
        result["pick_count"] = sum(1 for pid in pool if _pick_map(canonical).get(pid, {}).get("current_owner_team_id") == owner)
    elif len(_group(canonical, term)) == 1 and not term.get("comparison_pool_pick_ids") and owner != _holder(term):
        result["label"] = swap_step_label(canonical, term)
    return result


def draft_assets_display(canonical: dict[str, Any], assets: list[dict[str, Any]], team_id: str) -> list[dict[str, Any]]:
    """Deduplicate context glyphs; nested trade bundles already use one pick ID."""
    groups: dict[str, dict[str, Any]] = {}
    for asset in assets:
        presentation = asset.get("pick_presentation") or {}
        if asset.get("kind") == "pick_swap" and presentation.get("rights_holder_team_id") == team_id:
            groups.setdefault(presentation["group_id"], presentation)
    consumed: set[tuple[str, str]] = set()
    combined = []
    for asset in assets:
        nested = (asset.get("pick_presentation") or {}).get("nested_entitlement")
        if asset.get("kind") != "pick" or not nested or asset.get("id") != nested["anchor_pick_id"]:
            continue
        combined.append({**asset, "label": nested["label"], "condition_summary": nested["label"], "display_only": True})
        consumed.add(("pick", asset["id"]))
        consumed.update(("pick", row["id"]) for row in assets if row.get("is_additional") and row.get("id") in nested["underlying_pick_ids"])

    picks = _pick_map(canonical)
    for presentation in groups.values():
        # Only merge the owned physical pick if this group replaces one slot.
        owned_ids = [pid for pid in presentation["underlying_pick_ids"] if picks.get(pid, {}).get("current_owner_team_id") == team_id]
        anchor = next((asset for asset in assets if asset.get("kind") == "pick" and asset.get("id") in owned_ids), None) if len(owned_ids) == 1 else None
        members = [asset for asset in assets if asset.get("kind") == "pick_swap" and asset.get("id") in presentation["obligation_ids"]]
        if not members:
            continue
        base = anchor or members[0]
        combined.append({**base, "pick_presentation": presentation, "label": anchor["label"] if anchor else presentation["label"], "condition_summary": anchor.get("condition_summary") if anchor else presentation["label"], "display_only": True})
        consumed.update((asset["kind"], asset["id"]) for asset in members)
        consumed.update(("pick", asset["id"]) for asset in assets if asset.get("kind") == "pick" and asset.get("is_additional") and asset.get("id") in presentation["underlying_pick_ids"])
        if anchor:
            consumed.add(("pick", anchor["id"]))
    remaining = [asset for asset in assets if (asset.get("kind"), asset.get("id")) not in consumed]
    pools: dict[str, list[dict[str, Any]]] = {}
    for asset in remaining:
        presentation = asset.get("pick_presentation") or {}
        if asset.get("kind") == "pick" and not asset.get("is_additional") and presentation.get("pool_group_id") and presentation.get("pick_count", 1) > 1:
            pools.setdefault(presentation["pool_group_id"], []).append(asset)
    for members in pools.values():
        presentation = members[0]["pick_presentation"]
        if len(members) != presentation["pick_count"]:
            continue
        combined.append({**members[0], "label": presentation["label"], "condition_summary": presentation["label"], "display_only": True, "member_pick_ids": [member["id"] for member in members]})
        consumed.update(("pick", member["id"]) for member in members)
    visible = []
    shown_pairs = {asset["pick_presentation"]["group_id"] for asset in combined if (asset.get("pick_presentation") or {}).get("pair_icon_owners")}
    for asset in remaining:
        if (asset.get("kind"), asset.get("id")) in consumed:
            continue
        presentation = asset.get("pick_presentation") or {}
        if presentation.get("pair_icon_owners"):
            if presentation["group_id"] in shown_pairs:
                continue
            shown_pairs.add(presentation["group_id"])
            visible.append({**asset, "label": presentation["label"], "condition_summary": presentation["label"], "display_only": True})
        else:
            visible.append(asset)
    return [*visible, *combined]


# --- Reuse within one immutable trade search -------------------------------------------------------------
#
# A trade search asks for the same pick entitlements and labels thousands of times against an unchanged
# league (see transactions.trade_search_context). A search context carries a "_pick_presentation_memo"
# dict; results are kept per (picks, terms, teams) list triple and every caller gets a private copy.
# An entry is dropped whenever a list is replaced, changes length or has an item replaced, or any pick's
# owner, or any term's status, rights holder, nested anchor or field count changes. (Pick annotations such
# as "_obligations" are not read here; the one that is, "_ranked_entitlement", is part of the result key.) Contexts without the memo
# key (saves, dashboards, settlement) compute fresh results exactly as before.

_MEMO_LIMIT = 16
_TRUSTED: ContextVar[tuple[Any, ...] | None] = ContextVar("pick_presentation_trusted_entry", default=None)
_PICK_OWNER = methodcaller("get", "current_owner_team_id")
_TERM_STATUS = methodcaller("get", "status")
_TERM_HOLDER = methodcaller("get", "current_rights_holder_team_id")
_TERM_ANCHOR = methodcaller("get", "nested_anchor_pick_id")


def _memo_entry(canonical: dict[str, Any]) -> dict[str, Any] | None:
    memo = canonical.get("_pick_presentation_memo")
    if memo is None:
        return None
    picks = canonical.get("draft_picks", [])
    terms = canonical.get("pick_obligations", [])
    teams = canonical.get("teams", [])
    key = (id(picks), id(terms), id(teams))
    trusted = _TRUSTED.get()
    if trusted is not None and trusted[0] is memo and trusted[1] == key:
        # A nested call made while computing a result for this very entry: these functions only read
        # the league lists, so the guard taken a moment ago still holds.
        return trusted[2]
    guard = (
        list(map(id, picks)), list(map(_PICK_OWNER, picks)),
        list(map(id, terms)), list(map(len, terms)), list(map(_TERM_STATUS, terms)),
        list(map(_TERM_HOLDER, terms)), list(map(_TERM_ANCHOR, terms)), list(map(id, teams)),
    )
    entry = memo.pop(key, None)  # re-inserted below: least recently used entries are evicted first
    if (entry is None or entry["sources"][0] is not picks or entry["sources"][1] is not terms
            or entry["sources"][2] is not teams or entry["guard"] != guard):
        while len(memo) >= _MEMO_LIMIT:
            memo.pop(next(iter(memo)))
        # The entry keeps its source lists alive, so their ids cannot be reused while it exists.
        entry = {"key": key, "sources": (picks, terms, teams), "guard": guard, "results": {}}
    memo[key] = entry
    return entry


def _memoized(canonical: dict[str, Any], key: tuple[Any, ...], compute, *args: Any) -> Any:
    entry = _memo_entry(canonical)
    if entry is None:
        return compute(canonical, *args)
    results = entry["results"]
    stored = results.get(key)
    if stored is None:
        token = _TRUSTED.set((canonical["_pick_presentation_memo"], entry["key"], entry))
        try:
            value = compute(canonical, *args)
        finally:
            _TRUSTED.reset(token)
        # Plain JSON-like data built here; the bytes never leave this process.
        results[key] = (args, pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
        return value
    return pickle.loads(stored[1])


def nested_entitlements(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Project proven single-slot chains onto their existing pick ID (see _compute_nested_entitlements)."""
    return _memoized(canonical, ("nested",), _compute_nested_entitlements)


def ranked_pool_entitlements(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Stable ranks for assets in proven allocation pools (see _compute_ranked_pool_entitlements)."""
    return _memoized(canonical, ("ranked",), _compute_ranked_pool_entitlements)


def swap_presentation(canonical: dict[str, Any], term: dict[str, Any]) -> dict[str, Any]:
    # Keyed by the term object; the entry keeps it alive, so the id stays unique.
    return _memoized(canonical, ("swap", id(term)), _compute_swap_presentation, term)


def pick_presentation(canonical: dict[str, Any], pick: dict[str, Any]) -> dict[str, Any] | None:
    # The result reads only these fields of the supplied pick; everything else comes from the league lists.
    rank = pick.get("_ranked_entitlement")
    key = ("pick", pick.get("id"), pick.get("current_owner_team_id"),
           (rank["rank"], rank["pool_size"]) if rank else None)
    return _memoized(canonical, key, _compute_pick_presentation, pick)
