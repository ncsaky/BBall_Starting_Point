"""Offline defensive-job suitability experiment. Never imported by game runtime.

Scores are transparent trait-proxy estimates, not learned impact coefficients,
percentiles, assignment frequencies, points prevented or production DEF.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from collections.abc import Mapping, Sequence

from nba_gm_data.defense import rim_response

VERSION = 'offline_defensive_jobs_2026_11_11_v2'
JOBS = ('poa', 'chaser', 'wing_stopper', 'helper', 'mobile_big', 'anchor_big')
KEYS = MappingProxyType({
    'lateral': 'foot_speed_lateral_agility', 'effort': 'defensive_effort',
    'navigation': 'screen_navigation', 'scheme': 'scheme_iq',
    'rim': 'rim_deterrence', 'stamina': 'stamina_cardio',
})
# Interpretability hypotheses, not estimates of causal possession value.
RECIPES = MappingProxyType({
    'poa': (('lateral', .45), ('effort', .25), ('navigation', .20), ('scheme', .10)),
    'chaser': (('navigation', .50), ('lateral', .30), ('effort', .20)),
    'wing_stopper': (('lateral', .35), ('scheme', .35), ('effort', .20), ('navigation', .10)),
    'helper': (('scheme', .45), ('rim', .25), ('effort', .20), ('lateral', .10)),
    'mobile_big': (('lateral', .40), ('rim', .25), ('scheme', .25), ('effort', .10)),
    'anchor_big': (('rim', .60), ('scheme', .30), ('effort', .10)),
})
CRITICAL = MappingProxyType({
    'poa': ('lateral',), 'chaser': ('navigation', 'lateral'),
    'wing_stopper': ('lateral', 'scheme'), 'helper': ('scheme',),
    'mobile_big': ('lateral', 'rim'), 'anchor_big': ('rim', 'scheme'),
})
LIMITATIONS = MappingProxyType({
    'poa': 'No independent containment, hand discipline or screen matchup measurement.',
    'chaser': 'No independent off-ball tracking measurement; broad cardio is not intrinsic chaser skill.',
    'wing_stopper': 'No independent contact strength, denial or isolation matchup measurement.',
    'helper': 'Scheme/rim proxies do not measure help timing or recovery range independently.',
    'mobile_big': 'No independent switch containment or recovery-range measurement.',
    'anchor_big': 'Effective rim already embeds size; no independent range/avoidance measurement.',
})
MISSING_PRIOR = 35.0  # visible weak/unknown estimate, never excellent-by-default


@dataclass(frozen=True)
class Trait:
    value: float
    confidence: float = 0.0  # source confidence, not calibrated role probability
    provenance: str = 'unspecified'


@dataclass(frozen=True)
class Player:
    id: str
    name: str
    traits: tuple[tuple[str, Trait], ...]
    height: float | None = None
    observed_jobs: tuple[str, ...] = ()  # evidence only, never enters score
    observation_note: str = 'No reviewed deployment evidence attached.'


def _bounded(value: float, lo=0.0, hi=100.0) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Non-finite model input')
    return max(lo, min(hi, value))


def estimate(player: Player, *, bottleneck_allowance: float = 20.0,
             uniform_weight_blend: float = 0.0) -> dict:
    """One immutable input -> fresh result. No caches, RNG, mutation or label bonus."""
    allowance = _bounded(bottleneck_allowance)
    if not math.isfinite(uniform_weight_blend) or not 0 <= uniform_weight_blend <= 1:
        raise ValueError('Weight sensitivity blend must be 0–1')
    traits = dict(player.traits)
    if len(traits) != len(player.traits):
        raise ValueError('Duplicate trait key')
    channels = {}
    for channel, key in KEYS.items():
        trait = traits.get(key)
        value = _bounded(trait.value) if trait else MISSING_PRIOR
        if channel == 'rim' and trait:
            value = 0.0 if value == 0 else rim_response(value)
        channels[channel] = (value, trait)
    roles = {}
    for job in JOBS:
        base_recipe = RECIPES[job]
        recipe = tuple((k, w*(1-uniform_weight_blend) + uniform_weight_blend/len(base_recipe))
                       for k, w in base_recipe)
        blend = sum(channels[k][0] * weight for k, weight in recipe)
        weakest = min(CRITICAL[job], key=lambda k: channels[k][0])
        cap = channels[weakest][0] + allowance
        score = min(blend, cap)
        known = sum(w for k, w in recipe if channels[k][1] is not None)
        confidence = sum(w * _bounded(channels[k][1].confidence, 0, 1)
                         for k, w in recipe if channels[k][1] is not None)
        missing = [KEYS[k] for k, _ in recipe if channels[k][1] is None]
        roles[job] = {
            'score': round(score, 2), 'uncapped_blend': round(blend, 2),
            'input_coverage': round(known, 4), 'source_confidence': round(confidence, 4),
            'role_confidence': 'provisional trait proxies; not a validated role probability',
            'direct_job_measurement_coverage': 0.0, 'missing_inputs': missing,
            'reasons': [f'{k}: {channels[k][0]:.2f} × {w:.2f}' for k, w in recipe],
            'bottleneck': {'channel': weakest, 'cap': round(cap, 2), 'binding': cap < blend},
            'limitations': [LIMITATIONS[job],
                'Correlated source proxies are not independent observations.',
                *(['Missing traits use disclosed prior 35.'] if missing else [])],
        }
    ordered = sorted(JOBS, key=lambda job: -roles[job]['score'])
    return {
        'player_id': player.id, 'name': player.name, 'roles': roles,
        'suggested_primary': ordered[0], 'suggested_secondary': ordered[1],
        'suggestion_basis': 'Highest proxy estimates; not observed deployment or universal DEF.',
        'observed_jobs': list(player.observed_jobs), 'observation_note': player.observation_note,
        'sheltered': {'score': None, 'meaning': 'Reduced responsibility, not defensive quality.'},
        'production_def': None,  # attached separately by the runner, never substituted
    }


@dataclass(frozen=True)
class Context:
    name: str
    # Relative mutually exclusive responsibility buckets; normalized to five units.
    demand: tuple[tuple[str, float], ...]
    target_wing_height: float | None = None
    availability: tuple[tuple[str, float], ...] = ()


def _demands(context: Context) -> dict[str, float]:
    raw = dict(context.demand)
    if len(raw) != len(context.demand) or set(raw) != set(JOBS):
        raise ValueError('Every active job must have one demand')
    if any(not math.isfinite(v) or v < 0 for v in raw.values()) or sum(raw.values()) <= 0:
        raise ValueError('Invalid demand')
    total = sum(raw.values())
    return {job: raw[job] / total * 5.0 for job in JOBS}


def deployment_scores(players: Sequence[Player], context: Context) -> dict[str, dict[str, float]]:
    """Context does not alter stored base scores; physical fit is a separate risk."""
    health = dict(context.availability)
    if len(health) != len(context.availability) or set(health) - {p.id for p in players}:
        raise ValueError('Invalid availability IDs')
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in health.values()):
        raise ValueError('Availability must be an explicit 0–1 scenario factor')
    if context.target_wing_height is not None and not math.isfinite(context.target_wing_height):
        raise ValueError('Invalid matchup height')
    result = {}
    for p in players:
        if p.height is not None and not math.isfinite(p.height):
            raise ValueError('Invalid player height')
        roles = estimate(p)['roles']
        result[p.id] = {}
        for job in JOBS:
            fit = 1.0
            if job == 'wing_stopper' and context.target_wing_height is not None and p.height is not None:
                # A disclosed soft contact-mismatch hypothesis, not a size bonus.
                # No rim role gets a second size adjustment; no position bans.
                fit = max(.70, 1 - .02 * max(0, context.target_wing_height - p.height - 4))
            result[p.id][job] = roles[job]['score'] * fit * health.get(p.id, 1.0)
    return result


def summarize(players: Sequence[Player], context: Context,
              shares: Mapping[str, Mapping[str, float]]) -> dict:
    """Fixed total budget prevents shelter/duplicate-role credit from inflating fit.

    Shares describe fractions of each player's responsibility, NOT observed
    possession tracking. Coverage index caps credit at opponent job demand.
    Both means/indices are reference bookkeeping, not points-prevented metrics.
    """
    ids = [p.id for p in players]
    if len(players) != 5 or len(set(ids)) != 5 or set(shares) != set(ids):
        raise ValueError('Exactly five unique players and share rows required')
    demand = _demands(context)
    scores = deployment_scores(players, context)
    supplied = {job: 0.0 for job in JOBS}
    quality = {job: 0.0 for job in JOBS}
    rows = []
    for p in players:
        row = shares[p.id]
        if set(row) - {*JOBS, 'sheltered'}:
            raise ValueError('Unknown assignment')
        if any(not math.isfinite(v) or v < 0 for v in row.values()):
            raise ValueError('Invalid share')
        if not math.isclose(sum(row.values()), 1.0, abs_tol=1e-9):
            raise ValueError('Player responsibility shares must sum to one')
        reference = 0.0
        for job in JOBS:
            value = float(row.get(job, 0))
            supplied[job] += value
            quality[job] += value * scores[p.id][job]
            reference += value * scores[p.id][job]
        rows.append({'player_id': p.id, 'name': p.name, 'shares': dict(row),
                     'usage_mean_reference': round(reference, 4)})
    by_job = {}
    covered_score = 0.0
    for job in JOBS:
        covered = min(supplied[job], demand[job])
        average = quality[job] / supplied[job] if supplied[job] else 0.0
        covered_score += covered * average
        by_job[job] = {'demand': demand[job], 'supplied': supplied[job],
                       'covered': covered, 'gap': max(0, demand[job] - supplied[job]),
                       'excess_no_credit': max(0, supplied[job] - demand[job]),
                       'mean_assigned_quality': round(average, 4)}
    return {
        'context': context.name, 'players': rows, 'jobs': by_job,
        'usage_mean_reference': round(sum(r['usage_mean_reference'] for r in rows) / 5, 4),
        'coverage_adjusted_index': round(covered_score / 5, 4),
        'covered_responsibility_share': round(sum(v['covered'] for v in by_job.values()) / 5, 6),
        'sheltered_share': round(sum(r.get('sheltered', 0) for r in shares.values()) / 5, 6),
        'units': 'Experimental grade bookkeeping; not production DEF or predicted points.',
        'physical_fit_limits': {
            'missing_height_ids': [p.id for p in players if p.height is None],
            'meaning': 'Only an optional soft wing contact-mismatch scenario; unknown size is not verified fit. Effective rim gets no second size factor.',
        },
    }


def assign(players: Sequence[Player], context: Context) -> dict[str, dict[str, float]]:
    """Exact min-cost flow of 500 one-percent units; fixed order resolves ties.

    All six jobs remain available to every body/position. Fractions are hybrid
    responsibility over time, not a claim one player performs two jobs at once.
    Objective uses .0001-grade resolution; no stochastic or coach behavior.
    """
    if len(players) != 5 or len({p.id for p in players}) != 5:
        raise ValueError('Exactly five unique players required')
    demands = _demands(context)
    raw = {job: demands[job] * 100 for job in JOBS}
    capacities = {job: math.floor(raw[job]) for job in JOBS}
    order = sorted(JOBS, key=lambda job: -(raw[job] - capacities[job]))
    for job in order[:500 - sum(capacities.values())]:
        capacities[job] += 1
    scores = deployment_scores(players, context)
    # Mutable graph is strictly call-local. Edge [to, reverse-index, cap, cost].
    graph = [[] for _ in range(13)]
    source, sink = 0, 12
    def edge(a, b, cap, cost):
        forward = [b, len(graph[b]), cap, cost]
        reverse = [a, len(graph[a]), 0, -cost]
        graph[a].append(forward); graph[b].append(reverse)
        return forward
    tracked = {}
    for i, p in enumerate(players, 1):
        edge(source, i, 100, 0)
        for j, job in enumerate(JOBS, 6):
            tracked[p.id, job] = edge(i, j, 100, -round(scores[p.id][job] * 10000))
    for j, job in enumerate(JOBS, 6):
        edge(j, sink, capacities[job], 0)
    sent = 0
    while sent < 500:
        distance = [float('inf')] * 13; distance[source] = 0
        previous = [None] * 13
        for _ in range(12):
            changed = False
            for a, edges in enumerate(graph):
                for index, e in enumerate(edges):
                    if e[2] and distance[a] + e[3] < distance[e[0]]:
                        distance[e[0]] = distance[a] + e[3]
                        previous[e[0]] = (a, index); changed = True
            if not changed: break
        if previous[sink] is None:
            raise AssertionError('Complete role graph must cover all demands')
        amount = 500 - sent; node = sink
        while node != source:
            a, index = previous[node]; amount = min(amount, graph[a][index][2]); node = a
        node = sink
        while node != source:
            a, index = previous[node]; e = graph[a][index]
            e[2] -= amount; graph[node][e[1]][2] += amount; node = a
        sent += amount
    return {p.id: {job: (100 - tracked[p.id, job][2]) / 100 for job in JOBS}
            for p in players}
