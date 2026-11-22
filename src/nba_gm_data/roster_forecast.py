"""Indexes and bounded exact calculations owned by one immutable forecast snapshot.

Only private hypothetical views share these tables. Players in each trial are
owned copies; no actual coaching rotation or settlement approval is memoized.
"""
from collections import Counter
from .utils import copy_plain


class ForecastMemo(dict):
    def __init__(self, limit, stats, name):
        super().__init__()
        self.limit, self.stats, self.name = limit, stats, name

    def get(self, key, default=None):
        self.stats[self.name + ('.hits' if key in self else '.misses')] += 1
        return super().get(key, default)

    def __setitem__(self, key, value):
        if key not in self and len(self) >= self.limit:
            self.clear()
            self.stats[self.name + '.resets'] += 1
        super().__setitem__(key, value)
        self.stats[self.name + '.peak'] = max(self.stats[self.name + '.peak'], len(self))


_NOT_INDEXED = object()


def first_player_row(canonical, rows, player_id):
    """The first row of ``rows`` for this player (or None), using the forecast snapshot's index when ``rows`` is
    one of its source lists. A snapshot's sources are never edited while it is in use."""
    forecast = canonical.get('_roster_forecast_snapshot') if hasattr(canonical, 'get') else None
    if forecast is not None:
        found = forecast.first_row(rows, player_id)
        if found is not _NOT_INDEXED:
            return found
    indexed = canonical.get('_first_row_index') if hasattr(canonical, 'get') else None
    if indexed is not None:
        entry = indexed.get(id(rows))
        if entry is not None and entry[0] is rows:
            return entry[1].get(player_id)
    return next((row for row in rows if row.get('player_id') == player_id), None)


def first_row_index(*lists):
    """For a private trial view's ``_first_row_index``: each list's first row per player (MONTH-SPEED-2). Only for
    lists nobody edits while the view is in use."""
    out = {}
    for rows in lists:
        first = {}
        for row in rows:
            first.setdefault(row.get('player_id'), row)
        out[id(rows)] = (rows, first)
    return out


class ForecastSnapshot:
    """Read-only source indexes; create anew whenever authoritative inputs change."""
    def __init__(self, canonical):
        self.stats = Counter()
        self.players_source = canonical.get('players', [])
        self.players = {}
        self.teams = {}
        for ordinal, player in enumerate(self.players_source):
            self.players[player['id']] = (ordinal, player)
            self.teams.setdefault(player.get('team_id'), []).append((ordinal, player))
        self.traits = {}
        self.trait_values = {}
        self.trait_rows = {}
        for ordinal, trait in enumerate(canonical.get('traits', [])):
            pid, key = trait.get('player_id'), trait.get('trait_key')
            self.traits.setdefault(pid, []).append((ordinal, trait))
            # Match the distinct legacy sim and attribute-index semantics.
            self.trait_rows.setdefault(trait['player_id'], {})[trait['trait_key']] = trait
            if pid and key:
                value = trait.get('value')
                self.trait_values.setdefault(pid, {})[key] = float(value if value is not None else 50.0)
        self.contracts = {c['player_id']: c for c in canonical.get('contracts', [])}
        self.contracts_source = canonical.get('contracts', [])
        self.health = {}
        saved = canonical.get('_trade_planning_save') or {'health_states': canonical.get('player_health_states') or []}
        self.health_source = saved.get('health_states', [])
        self._first_rows = {}
        for ordinal, health in enumerate(saved.get('health_states', [])):
            self.health.setdefault(health.get('player_id'), []).append((ordinal, health))
        self.features = ForecastMemo(8192, self.stats, 'features')
        self.attributes = ForecastMemo(4096, self.stats, 'attributes')
        self.season_windows = ForecastMemo(32, self.stats, 'season_windows')
        self.stats.update(players_indexed=len(self.players_source),
                          traits_indexed=len(canonical.get('traits', [])),
                          contracts_indexed=len(canonical.get('contracts', [])))

    def first_row(self, rows, player_id):
        """next((r for r in rows if r.get('player_id') == player_id), None) for this snapshot's own contract or
        health rows (by identity), from an index built once; _NOT_INDEXED for any other list."""
        if rows is self.contracts_source:
            name = 'contracts'
        elif rows is self.health_source:
            name = 'health'
        else:
            return _NOT_INDEXED
        index = self._first_rows.get(name)
        if index is None:
            index = {}
            for row in rows:
                index.setdefault(row.get('player_id'), row)
            self._first_rows[name] = index
        return index.get(player_id)

    def roster(self, team_id, outgoing_ids=(), incoming_ids=()):
        rows = {ordinal: player for ordinal, player in self.teams.get(team_id, ())}
        for pid in incoming_ids:
            row = self.players.get(pid)
            if row is not None:
                rows[row[0]] = row[1]
        # Keep the original league collection order, even for incoming players.
        return [dict(copy_plain(p), team_id=team_id, minutes_projection=24)
                for _, p in sorted(rows.items()) if p['id'] not in outgoing_ids and not p.get('_inactive_player')]

    def selected_rows(self, index, player_ids):
        return [row for _, row in sorted(item for pid in player_ids for item in index.get(pid, ()))]

    def view(self, canonical, players, *, traits=None):
        """Share only audited immutable calculations, never source player indexes."""
        from .talent import enabled as talent_enabled
        from .offense import enabled as offense_enabled
        view = {k: v for k, v in canonical.items() if not str(k).startswith('_')}
        view.update(players=players, _allow_internal_caches=True,
                    _roster_forecast_snapshot=self, _roster_forecast_attributes=self.attributes,
                    _players_by_id={p['id']: p for p in players},
                    _trait_values_by_player=self.trait_values)
        if traits is not None:
            view['traits'] = traits
        view['_sim_feature_cache'] = {
            'owner_id': id(view), 'players_source': players, 'traits_source': view.get('traits', []),
            'talent_model': talent_enabled(view), 'offense_model': offense_enabled(view),
            'traits_by_player': self.trait_rows, 'player_features': self.features}
        return view
