"""Exact bounded selection using the existing package rank and duplicate identity."""
from bisect import bisect_left
import json


class PackageShortlist:
    def __init__(self, limit, include_terms, diagnostics=None):
        self.limit = max(4, int(limit))
        self.include_terms = include_terms
        self.entries = []
        self.by_identity = {}
        self.generated = 0
        self.diagnostics = diagnostics
        self.seen = set() if diagnostics is not None else None

    def __bool__(self):
        # Fallback depends on whether ANY candidate passed the value filter,
        # including terms candidates hidden by the plain-assets return mode.
        return bool(self.generated)

    def append(self, candidate):
        score, assets, terms = candidate
        self.generated += 1
        if self.diagnostics is not None:
            self.diagnostics['generated_packages'] += 1
            identity = (json.dumps(assets, sort_keys=True), json.dumps(terms, sort_keys=True))
            if identity not in self.seen:
                self.seen.add(identity)
                self.diagnostics['unique_packages'] += 1
        if terms and not self.include_terms:
            return
        if len(self.entries) == self.limit and score > self.entries[-1][0][0]:
            return
        if self.diagnostics is None:
            identity = (json.dumps(assets, sort_keys=True), json.dumps(terms, sort_keys=True))
        rank = (score, *identity)
        previous = self.by_identity.get(identity)
        if previous is not None:
            if rank >= previous[0]:
                return
            self.entries.remove(previous)
        elif len(self.entries) == self.limit:
            if rank >= self.entries[-1][0]:
                return
            worst = self.entries.pop()
            del self.by_identity[worst[0][1:]]
        entry = (rank, assets, terms)
        index = bisect_left([item[0] for item in self.entries], rank)
        self.entries.insert(index, entry)
        self.by_identity[identity] = entry
        if self.diagnostics is not None:
            self.diagnostics['peak_shortlist_entries'] = max(self.diagnostics['peak_shortlist_entries'],len(self.entries))

    def extend(self, candidates):
        for candidate in candidates:
            self.append(candidate)

    def ordered(self):
        return [(rank[0], assets, terms) for rank, assets, terms in self.entries]
