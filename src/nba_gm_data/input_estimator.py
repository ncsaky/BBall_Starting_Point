"""Evidence-only population of the approved 94 inputs (no simulation imports).

Wire contract: a normal player_model input section, containing normal PlayerInputs
records. Until the coordinator approves native status='prior', status='estimated'
plus reason='prior' means a usable prior, NOT direct evidence of this input. Use
estimation_status(), never status alone, when displaying evidence coverage.
Fictional generator definitions use reason='generated' and source='draft_model';
they define a fictional player rather than claim observations of a real person.
Uncertainty.notes contains JSON plausibility intervals, not calibrated CIs.

Fixed anchors and shrinkage constants below are basketball judgments, not fits to
engine outcomes or to the 32 research players. Legacy traits only weakly condition
explicit priors; they never become measured raw skills. New sources plug in via InputEvidence, keyed by input
ID, with provenance, sample exposure, and source-correlation group. No I/O occurs
on import; no random numbers or wall-clock dates are used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import unicodedata
from typing import Any, Mapping

from .player_model import INPUT_VERSION, PlayerInputs, validate_input_section
from .player_model_registry import REGISTRY_VERSION, definition_registry

METHOD_VERSION = 'e2b_hierarchical_family_priors_v1'
TECHNIQUE_SCALE = 'e2_technique_reference_v1_50_functional_75_strong_90_exceptional'
FT_SCALE = 'research_FT_conversion_percent_proxy_v1'
DEFINITIONS = {r['id']: r for r in definition_registry()['inputs']}
UNIVERSE_PATH = 'data/canonical/universe_2026_27_offseason.json'
SKILL_PATH = 'Player Stats/player_skill_input_2025_26.json'
STATS_PATH = 'Player Stats/player_stats.json'
CAREER_PATH = 'data/research/player_career_stats.json'
PACKET_PATH = 'docs/ratings-evidence-2026-10-29'
SHOT_ZONE_PATH = 'data/research/shot_chart_reference.json'
# ROOKIE-FIT (2026-11-21): the 2026 class's final college season, its projected rookie-year impact
# (scripts/research/rookie_fit.py) and the fitted college -> 94-input mapping (data/canonical/real_prospects.json).
ROOKIE_TRANSLATION_PATH = 'data/research/rookie_translation_2026.json'
ROOKIE_MAPPING_PATH = 'data/canonical/real_prospects.json'
ROOKIE_METHOD = 'rookie_translation_v1'
# The projection is the expected rookie-year impact (already a shrunk forecast), and it is this player's only
# level evidence. It enters the family-talent step exactly like a veteran's impact metric, at the most
# precision one impact observation may carry there (2), so it is not shrunk twice.
ROOKIE_PROJECTION_PRECISION = 2.0
# Same weights as the real 2027-2029 college prospects (real_prospects.INPUT_WEIGHT_*): share of a fitted
# college estimate = min(.6, .2 + .5 x how well college predicts the input) x minutes / (minutes + 300).
ROOKIE_EVIDENCE_PRIOR_MINUTES = 300.0
LIMIT = ('Raw technique is incompletely separated from tools, teammates and deployment; '
         'shared evidence is correlated, not independent observations.')


def canonical_json(value: Any) -> str:
    """Stable wire bytes (including newline); no runtime metadata."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')) + '\n'


def estimation_status(record: dict) -> str:
    return 'prior' if record.get('reason') == 'prior' else record['status']


def uncertainty_details(record: dict) -> dict:
    return json.loads(record['uncertainty']['notes'])


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def _get(row: Mapping, *keys: str) -> float | None:
    for key in keys:
        value = _number(row.get(key))
        if value is not None:
            return value
    return None


def _normalize(name: str) -> str:
    # Match only unique exact normalized names; never fuzzy-match identities.
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', name)


def _index(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list] = {}
    for row in rows:
        key = _normalize(row.get('name') or row.get('player') or '')
        grouped.setdefault(key, []).append(row)
    return {key: values[0] for key, values in grouped.items() if key and len(values) == 1}


def _position(player: dict) -> str:
    pos = str(player.get('position') or '')
    if pos in ('C', 'PF/C', 'C/PF'):
        return 'big'
    if pos in ('PG', 'SG', 'PG/SG', 'SG/PG', 'G'):
        return 'guard'
    return 'wing'


def _role(player: dict) -> str:
    return ' '.join(str(player.get(k) or '') for k in
                    ('primary_off_role', 'secondary_off_role', 'archetype')).lower()


def _soft_grade(value: float, center: float, spread: float) -> float:
    # Smooth fixed rescaling, NEVER clipping or annual min/max normalization.
    return 50 + 50 * math.tanh((value - center) / spread)


def _probability(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def _logit(value: float) -> float:
    return math.log(value / (1 - value))


def _bounded_band(mean: float, radius: float, bound: float = 100) -> list[float]:
    # Interval boundaries may meet the scale endpoints; values are never clamped.
    return [round(max(0, mean - radius), 6), round(min(bound, mean + radius), 6)]


def _evidence(source: str, method: str, group: str, **kwargs: Any) -> dict:
    return dict(source=source, method=method, shared_evidence_id=group, **kwargs)


def _record(value: dict, evidence: list[dict], interval: list | None = None,
            *, prior: bool = False, confidence: str = 'low', basis: str = '',
            intervals: dict | None = None, limitations: str = LIMIT) -> dict:
    notes = dict(basis=basis, limitations=limitations)
    if interval is not None:
        notes['interval'] = interval
    if intervals is not None:
        notes['intervals'] = intervals
    return dict(status='estimated', reason='prior' if prior else 'estimated', value=value,
                evidence=evidence, uncertainty=dict(confidence=confidence,
                notes=json.dumps(notes, sort_keys=True, ensure_ascii=False, separators=(',', ':'))))


def _grade_record(mean: float, radius: float, evidence: list[dict], *, prior: bool = False,
                  basis: str = '', scale: str = TECHNIQUE_SCALE, confidence: str = 'low') -> dict:
    return _record(dict(grade=round(mean, 6), scale=scale), evidence,
                   _bounded_band(mean, radius), prior=prior, basis=basis, confidence=confidence)


@dataclass(frozen=True)
class InputEvidence:
    """Additional source for one player's one input, in that input's wire units.

    value must use the registry shape (grade/physical/probability/distribution).
    interval(s) describe uncertainty in the same units. n and prior_exposure must
    describe the SAME opportunity unit; weight=n/(n+prior_exposure)*reliability.
    For qualitative scouting use n=1, prior_exposure=1; no invented event counts.
    source_id identifies the retained source; group_id deduplicates correlated
    sources. Multiple entries in one group contribute only the strongest entry.
    InputEvidence cannot turn an opportunity-free usage count into a propensity.
    """
    input_id: str
    value: dict
    interval: tuple[float, float] | None
    source_id: str
    method: str
    group_id: str
    n: float = 1
    prior_exposure: float = 1
    reliability: float = 0.7
    exposure_unit: str = 'qualitative_assessment'
    intervals: dict | None = None


def _prior_grade(iid: str, player: dict, prospect: bool) -> float:
    pos, role = _position(player), _role(player)
    skill = int(iid[1:]) if iid.startswith('S') else 0
    mean = 50.0
    if skill in (1, 2, 3, 4, 5, 6, 9):
        mean = {1: 55, 2: 45, 3: 43, 4: 50, 5: 48, 6: 43, 9: 47}[skill]
        mean += {'guard': 3, 'wing': 0, 'big': -6}[pos]
        if any(token in role for token in ('shooter', 'shooting', 'stretch')):
            mean += 7
    elif skill in (10, 11, 12, 13, 15, 21, 22, 23, 27, 28, 29, 30, 31, 32, 36, 37):
        mean += {'guard': -3, 'wing': 0, 'big': 6}[pos]
    elif skill in (16, 17, 18, 19, 20):
        mean += {'guard': 7, 'wing': 0, 'big': -5}[pos]
        if any(token in role for token in ('creator', 'handler', 'playmaker')):
            mean += 5
    elif iid.startswith('F'):
        mean += {'guard': 6, 'wing': 0, 'big': -3}[pos]
        if any(token in role for token in ('creator', 'handler', 'playmaker', 'connector')):
            mean += 4
        if iid.endswith('execution'):
            mean -= 2
    if prospect:
        mean -= 6  # uncertain pre-NBA readiness, never rank or projected upside
    return mean


def _physical_inputs(player: dict, prospect: bool) -> dict:
    pos = _position(player)
    h = _get(player, 'height_inches')
    w = _get(player, 'weight_lbs')
    span = _get(player, 'wingspan_inches')
    h = h if h is not None and h > 0 else None
    w = w if w is not None and w > 0 else None
    span = span if span is not None and span > 0 else None
    height = (h or {'guard': 76, 'wing': 80, 'big': 83}[pos]) * 2.54
    wingspan = span * 2.54 if span else height + {'guard': 7, 'wing': 10, 'big': 13}[pos]
    mass = (w or {'guard': 195, 'wing': 220, 'big': 245}[pos]) * 0.45359237
    # Reach is an explicitly uncertain anthropometric inference, not a test.
    reach = height * 1.32 + (wingspan - height) * .35
    data = {
        'P01': ('standing_height', height, 'cm', 2 if h else 12, h is not None),
        'P02': ('arm_span', wingspan, 'cm', 3 if span else 15, span is not None),
        'P03': ('standing_reach', reach, 'cm', 15, False),
        'P04': ('body_mass', mass, 'kg', 5 if w else 20, w is not None),
        'P10': ('jump_height', {'guard': 72, 'wing': 69, 'big': 62}[pos], 'cm', 30, False),
    }
    records = {}
    for iid in [f'P{i:02d}' for i in range(1, 13)]:
        source = UNIVERSE_PATH if not prospect else 'prospect:reported_physicals'
        if iid in data:
            metric, value, unit, radius, measured = data[iid]
            radius *= 1.3 if prospect else 1
            interval = [round(max(.001, value-radius), 6), round(value+radius, 6)]
            protocol = 'listed report; measurement date/protocol unverified' if measured else 'uncertain positional/anthropometric prior; not a measurement'
            evidence = [_evidence(source if measured else METHOD_VERSION + ':physical_prior',
                                  protocol, 'reported_geometry' if measured else 'physical_prior',
                                  notes=('height/span conditioned reach estimate' if iid == 'P03' else protocol))]
            if iid == 'P03' and (h or span):
                evidence.append(_evidence(source, 'reported geometry conditions an unmeasured reach prior', 'reported_geometry'))
            records[iid] = _record(dict(measurements=[dict(metric=metric, value=round(value, 6),
                unit=unit, protocol=protocol, interval=interval)]), evidence, interval,
                prior=not measured, confidence='medium' if measured else 'low', basis=protocol)
        else:
            # Neutral base only. Related evidence may later condition a wide prior;
            # mass/workload/navigation never become physical trial measurements.
            records[iid] = _record(dict(measurements=[], display_grade=dict(grade=50.0, scale=TECHNIQUE_SCALE)),
                [_evidence(METHOD_VERSION + ':physical_prior', 'no independent physical test retained', 'physical_prior')],
                [10.0, 90.0] if not prospect else [0.0, 100.0], prior=True,
                basis='unmeasured physical capacity; neutral broad prior')
    return records


def _tendency_inputs(player: dict, prospect: bool) -> dict:
    """Conditional priors only: observed frequency is NOT intrinsic willingness.

    Neither touches nor play-type outcomes count the unavailable alternatives.
    Additional sources can supply real conditional opportunity counts through
    InputEvidence. This initial data set has none, so no fabricated denominator.
    """
    pos, role = _position(player), _role(player)
    guard, big = pos == 'guard', pos == 'big'
    shooter = any(x in role for x in ('shooter', 'stretch', 'shooting'))
    creator = any(x in role for x in ('creator', 'handler', 'playmaker'))
    distributions = {
        'T01': dict(shoot=.28, drive=.25 if guard else .13, post=.16 if big else .04,
                    reset=.15, **{'pass': .30 if creator else .25}),
        'T02': dict(rim=.38 if big else .27, short_paint=.19, midrange=.16,
                    three=.43 if shooter else .22 if big else .38),
        'T03': dict(catch=.50, pull_up=.32 if guard else .12, movement=.28 if shooter else .10),
        'T11': dict(screen=.40, roll=.35 if big else .18, pop=.32 if shooter else .12, slip=.13),
        'T13': dict(pursue=.48, box_out=.52),
        'T16': dict(jump=.25, conservative_contest=.45, stay_down=.30),
        'T17': dict(offense=.50, defense=.35, transition=.15),
    }
    conditions = {
        'T01': 'reference half-court touch with shoot, drive, pass, post and reset options available; fixed spacing and coach freedom',
        'T02': 'shot chosen with equal access to the four declared regions; fixed lineup, defense and coach deployment',
        'T03': 'shooting opportunity with catch, pull-up and movement routes equally available; fixed distances and coverage',
        'T11': 'screen involvement available with screen, roll, pop and slip continuations feasible; fixed coach assignment',
        'T13': 'defensive rebound opportunity with pursuit and box-out both feasible; fixed team collection assignments',
        'T16': 'contest opportunity with all three responses physically feasible; fixed foul cost and coverage',
        'T17': 'equal discretionary workload opportunities on offense, defense and transition; fixed coach obligations',
    }
    propensities = {'T04': .30, 'T05': .52 if guard else .42, 'T06': .60 if creator else .38,
        'T07': .35, 'T08': .62 if creator else .42, 'T09': .42 if big else .30,
        'T10': .58 if shooter else .38, 'T12': .56 if big else .25,
        'T14': .32, 'T15': .50, 'T18': .48 if creator or big else .35}
    records = {}
    for iid in [f'T{i:02d}' for i in range(1, 19)]:
        ev = [_evidence(METHOD_VERSION + ':conditional_role_prior',
            'position/role prior; no observed available-choice denominator', 'conditional_role_prior')]
        radius = .44 if prospect else .35
        if iid in distributions:
            probs = distributions[iid]
            total = sum(probs.values())
            probs = {k: v / total for k, v in probs.items()}
            value = dict(reference_conditions=conditions[iid], rows=[dict(condition='reference_opportunity', probabilities=probs)])
            if iid == 'T02':
                value['spatial_reference'] = 'rim <4ft; short_paint 4-14ft; midrange 14ft to arc; three beyond arc; coarse regions, no measured heatmap'
            records[iid] = _record(value, ev, prior=True, intervals={k: _bounded_band(v, radius, 1) for k,v in probs.items()},
                basis='conditional opportunity prior, not realized event frequency')
        else:
            p = propensities[iid]
            records[iid] = _record(dict(probability=p, reference_conditions=
                'one eligible '+DEFINITIONS[iid]['name'].lower()+' opportunity; feasible alternatives, fixed coach role, spacing, matchup and physical capacity'),
                ev, _bounded_band(p, radius, 1), prior=True,
                basis='conditional prior; opportunity sets and coach orders unobserved')
    return records


def _career_totals(profile: dict) -> tuple[dict, list[str]]:
    # Explicit ESPN ID join; source is career season totals, NEVER game-box cache.
    totals: dict[str, float] = {}
    used = []
    for season, weight in [('2025-26', 1.0), ('2024-25', .6), ('2023-24', .36)]:
        rows = [r for r in profile.get('seasons', []) if r.get('season') == season]
        if len(rows) != 1 or (_get(rows[0], 'minutes') or 0) <= 0:
            continue
        row = rows[0]
        # Nulls stay absent, not zero. Invalid shot identities reject that pair.
        valid_pairs = {}
        for makes, attempts in [('ftm','fta'), ('fg3m','fg3a'), ('fgm','fga')]:
            m,a = _get(row,makes),_get(row,attempts)
            if m is not None and a is not None and 0 <= m <= a:
                valid_pairs.update({makes:m, attempts:a})
        for key in ['minutes', 'assists', 'turnovers']:
            v = _get(row,key)
            if v is not None and v >= 0:
                valid_pairs[key] = v
        for key,v in valid_pairs.items():
            totals[key] = totals.get(key,0) + weight*v
        used.append(season)
    return totals, used


# These links condition *uncertain priors*, not independent technique/tool tests.
# The legacy values are correlated effective summaries. No one-to-one renaming.
_LEGACY_PRIOR_LINKS = {
    'S01': ('shooting_range',), 'S02': ('shot_versatility', 'shooting_range'),
    'S03': ('release_speed', 'shot_versatility'),
    'S04': ('shot_versatility',), 'S05': ('shot_versatility', 'handle_pressure'),
    'S06': ('shot_versatility', 'release_speed'), 'S07': ('shooting_range',),
    'S08': ('release_speed',), 'S09': ('shooting_range',),
    'S10': ('rim_pressure',), 'S11': ('shot_versatility', 'rim_pressure'),
    'S12': ('rim_pressure',), 'S13': ('rim_pressure', 'offensive_rebounding'),
    'S14': ('passing_reads', 'handle_pressure'), 'S15': ('rim_pressure',),
    'S16': ('handle_pressure',), 'S17': ('handle_pressure',),
    'S18': ('handle_pressure', 'shot_versatility'), 'S19': ('rim_pressure', 'handle_pressure'),
    'S20': ('passing_reads', 'scheme_iq'), 'S21': ('rim_pressure', 'offensive_rebounding'),
    'S22': ('shot_versatility', 'rim_pressure'), 'S23': ('rim_pressure', 'shot_versatility'),
    'S24': ('rim_pressure',), 'S25': ('scheme_iq', 'portability'),
    'S26': ('release_speed', 'portability'), 'S27': ('offensive_rebounding', 'scheme_iq'),
    'S28': ('scheme_iq', 'passing_reads'), 'S29': ('offensive_rebounding',),
    'S30': ('offensive_rebounding', 'scheme_iq'),
    'S31': ('offensive_rebounding', 'scheme_iq'), 'S32': ('offensive_rebounding',),
    'S33': ('foot_speed_lateral_agility', 'defensive_effort'),
    'S34': ('rim_deterrence', 'screen_navigation'), 'S35': ('screen_navigation',),
    'S36': ('rim_deterrence', 'scheme_iq'), 'S37': ('rim_deterrence',),
    'S38': ('scheme_iq', 'defensive_effort'), 'S39': ('scheme_iq', 'defensive_effort'),
    'S40': ('foot_speed_lateral_agility', 'defensive_effort'),
    'S41': ('scheme_iq', 'defensive_effort'), 'S42': ('defensive_effort',),
    'S43': ('scheme_iq', 'defensive_effort'), 'S44': ('defensive_effort', 'scheme_iq'),
    'S45': ('scheme_iq',), 'S46': ('scheme_iq', 'defensive_effort'),
    'P05': ('foot_speed_lateral_agility', 'rim_pressure'),
    'P06': ('foot_speed_lateral_agility',), 'P07': ('foot_speed_lateral_agility',),
    'P08': ('rim_pressure', 'rim_deterrence'), 'P09': ('handle_pressure',),
    'P10': ('rim_deterrence', 'offensive_rebounding'),
    'P11': ('stamina_cardio',), 'P12': ('stamina_cardio',),
    'T04': ('shot_versatility',), 'T05': ('foot_speed_lateral_agility',),
    'T06': ('handle_pressure',), 'T07': ('passing_reads',),
    'T08': ('rim_pressure', 'handle_pressure'), 'T09': ('rim_pressure', 'scheme_iq'),
    'T10': ('release_speed',), 'T12': ('offensive_rebounding',),
    'T14': ('defensive_effort',), 'T15': ('defensive_effort', 'scheme_iq'),
    'T18': ('rim_pressure',),
}

_STAT_PRIOR_LINKS = {
    'S01': ('three_volume', 'three_accuracy'), 'S02': ('handler', 'three_accuracy'),
    'S03': ('movement', 'three_accuracy'), 'S04': ('spot_up',), 'S05': ('handler',),
    'S06': ('movement',), 'S07': ('ft_accuracy',), 'S08': ('movement', 'three_volume'),
    'S09': ('three_volume', 'three_accuracy'), 'S10': ('close',), 'S11': ('handler', 'close'),
    'S12': ('roller', 'close'), 'S13': ('roller', 'cut'), 'S14': ('security',),
    'S15': ('foul_drawing', 'close'), 'S16': ('creation', 'handler'), 'S17': ('security',),
    'S18': ('creation', 'handler'), 'S19': ('handler', 'foul_drawing'),
    'S20': ('passing', 'creation'), 'S21': ('post',), 'S22': ('post',), 'S23': ('post', 'close'),
    'S24': ('foul_drawing',), 'S25': ('cut',), 'S26': ('movement',), 'S27': ('roller',),
    'S28': ('roller', 'passing'), 'S29': ('oreb',), 'S30': ('dreb',),
    'S31': ('oreb', 'dreb'), 'S32': ('oreb', 'dreb'),
    'S33': ('guard_assignment', 'disruption'), 'S34': ('big_assignment',),
    'S35': ('guard_assignment', 'disruption'), 'S36': ('big_assignment', 'blocks'),
    'S37': ('blocks',), 'S38': ('disruption',), 'S39': ('disruption',),
    'S40': ('guard_assignment',), 'S41': ('disruption', 'steals'), 'S42': ('steals',),
    'S43': ('disruption', 'steals'), 'S44': ('disruption',), 'S45': ('foul_control',),
    'S46': ('disruption',),
    'P05': ('transition',), 'P06': ('transition',), 'P07': ('guard_assignment',),
    'P08': ('post',), 'P09': ('security',), 'P10': ('blocks', 'oreb'),
    'P11': ('workload',), 'P12': ('workload',),
    'T04': ('usage', 'handler'), 'T05': ('transition',), 'T06': ('handler', 'usage'),
    'T07': ('passing',), 'T08': ('usage',), 'T09': ('cut',), 'T10': ('movement',),
    'T12': ('oreb',), 'T14': ('steals', 'disruption'), 'T15': ('big_assignment',),
    'T18': ('foul_drawing',),
}

# Each distribution outcome has its own related-evidence prior. Missing feasible
# alternatives still forbid interpreting observed shares as measured willingness.
_DISTRIBUTION_PRIOR_LINKS = {
    'T01': {'shoot': (('shooting_range',), ('usage',)),
            'drive': (('rim_pressure',), ('handler',)),
            'pass': (('passing_reads',), ('passing',)),
            'post': (('rim_pressure',), ('post',)), 'reset': (('scheme_iq',), ())},
    'T02': {'rim': (('rim_pressure',), ('close',)),
            'short_paint': (('shot_versatility',), ('post',)),
            'midrange': (('shot_versatility',), ('handler',)),
            'three': (('shooting_range',), ('three_volume',))},
    'T03': {'catch': (('release_speed',), ('spot_up',)),
            'pull_up': (('handle_pressure',), ('handler',)),
            'movement': (('release_speed',), ('movement',))},
    'T11': {'screen': (('offensive_rebounding',), ('roller',)),
            'roll': (('rim_pressure',), ('roller',)),
            'pop': (('shooting_range',), ('three_volume',)),
            'slip': (('scheme_iq',), ('cut',))},
    'T13': {'pursue': (('offensive_rebounding',), ('dreb',)),
            'box_out': (('scheme_iq',), ('big_assignment',))},
    'T16': {'jump': (('rim_deterrence',), ('blocks',)),
            'conservative_contest': (('scheme_iq',), ('foul_control',)),
            'stay_down': (('scheme_iq',), ('guard_assignment',))},
    'T17': {'offense': (('rim_pressure',), ('usage',)),
            'defense': (('defensive_effort',), ('disruption',)),
            'transition': (('stamina_cardio',), ('transition',))},
}


def _trait_values(traits: Any, player_id: str) -> dict[str, float]:
    if isinstance(traits, Mapping):
        return {k: n for k,v in sorted(traits.items())
                if (n := _number(v.get('value') if isinstance(v, Mapping) else v)) is not None}
    values = {}
    for raw in traits or []:
        row = _plain(raw)
        if row.get('player_id', player_id) == player_id and (n := _get(row, 'value')) is not None:
            key = row['trait_key']
            if key in values and values[key] != n:
                raise ValueError('Conflicting legacy prior values for '+player_id+':'+key)
            values[key] = n
    return values


def _trait_index(rows: list) -> dict[str, dict]:
    grouped: dict[str, list] = {}
    for raw in rows:
        row = _plain(raw)
        grouped.setdefault(row['player_id'], []).append(row)
    return {pid: _trait_values(values, pid) for pid,values in grouped.items()}


def _mean(values) -> float:
    values = list(values)
    return sum(values)/len(values) if values else 0.0


# Hierarchical assumptions, declared before running the engine diagnostics:
# a unit-normal family talent has a .8 log-odds skill scale (~20 grade points
# at 50), and related unobserved techniques have correlation .65 with it.
# These are provisional basketball judgments, NOT empirical fitted correlations.
# Positive AND negative evidence transfers; offense is only weak evidence for
# shooting/rebounding, and never conditions defense, tools or choice tendencies.
# Impact models share data: average them as ONE observation with precision at
# most 2, discounted by MP/(MP+750). IQ precision <= .5; workload/usage <=
# .15. Context from a snapshot shares one precision budget (the maximum, not
# the sum). Legacy remains the existing weak local residual, not another
# observation here. A unit prior precision prevents extrapolating small samples.
# Direct inputs share precision by evidence lineage, not skill count.
FAMILY_CORRELATION = .65
FAMILY_LOG_ODDS_SCALE = .8
FAMILY_TECHNIQUES = {
    'shooting': tuple(f'S{i:02d}' for i in (1, 2, 3, 4, 5, 6, 8, 9)),
    'finishing': tuple(f'S{i:02d}' for i in (10, 11, 12, 13, 14, 15, 24)),
    'creation': tuple(f'S{i:02d}' for i in range(16, 21)),
    'post': ('S21', 'S22', 'S23'),
    'routes_screening': ('S25', 'S26', 'S27', 'S28'),
    'rebounding': ('S29', 'S30', 'S31', 'S32'),
    'perimeter_defense': ('S33', 'S34', 'S35', 'S40'),
    'interior_defense': ('S36', 'S37', 'S45'),
    'defensive_recognition': ('S38', 'S39', 'S41', 'S42', 'S43', 'S44', 'S46'),
    'passing_recognition': tuple(f'F{i:02d}.recognition' for i in range(1, 10)),
    'passing_execution': tuple(f'F{i:02d}.execution' for i in range(1, 10)),
}
# channel, impact loading, IQ loading, workload/usage loading.
FAMILY_CONTEXT = {
    'shooting': ('offense', .25, 0, 0),
    'finishing': ('offense', 1, 0, 1),
    'creation': ('offense', 1, .5, 1),
    'post': ('offense', 1, 0, 1),
    'routes_screening': ('offense', .5, .5, 0),
    'rebounding': ('defense', .35, 0, 0),
    'perimeter_defense': ('defense', 1, 0, 0),
    'interior_defense': ('defense', 1, .5, 0),
    'defensive_recognition': ('defense', 1, 1, 0),
    'passing_recognition': ('offense', .5, 1, 0),
    'passing_execution': ('offense', .5, .5, 0),
}



# BBI mappings follow the acquisition manifest's distinct channels. These are
# deliberately weak proxy constraints, never measurements of isolated technique.
# No physical tests, effort, conditional tendencies, typed passing reads, box-out
# technique or pressure-specific handling can be identified from these summaries.
BBI_METRIC_INPUTS = {
    'C&S 3PT Shot Making': ('S01',),
    'C&S 3PT FG%': ('S01',),
    'Stable C&S 3PT_pct': ('S01',),
    '3PT Pull Up Shot Making': ('S02',),
    '3PT Pull Up FG%': ('S02',),
    'Stable Pull Up 3PT_pct': ('S02',),
    'Midrange Pull Up FG%': ('S05',),
    'Deep 3PT Shot Making': ('S09',),
    'Rim Shot Making': ('S10',),
    'Rim FG%': ('S10',),
    'Floater Shot Making': ('S11',),
    'Floater FG%': ('S11',),
    'Contact Finish Rate': ('S15',),
    'Rim Shot Creation': ('S19',),
    'Stable Post Up PPP': ('S23',),
    'Drive Foul Drawn Rate': ('S24',),
    'Post Up Draw Foul Rate': ('S24',),
    'Screening Talent': ('S27',),
    'Offensive Rebounding Crashing Skill': ('S29',),
    'Defensive Rebounding Crashing Skill': ('S30',),
    'Offensive Rebounding Conversion Skill': ('S32',),
    'Defensive Rebounding Conversion Skill': ('S32',),
    'Adjusted Offensive Rebounding Success Rate': ('S32',),
    'Adjusted Defensive Rebounding Success Rate': ('S32',),
    'Perimeter Isolation Defense': ('S33',),
    'Ball Screen Navigation': ('S35',),
    'Off-Ball Chaser Defense': ('S35',),
    'Rim dFG% vs Expected': ('S37',),
    'Stable Rim dFG% vs. Expected': ('S37',),
    'Help Effectiveness Rating': ('S38',),
    'Pickpocket Rating': ('S42',),
    'Passing Lane Defense': ('S43',),
}
# Sign applies to the *displayed percentile*, which can already be ordered by
# desirability. Do not guess direction from a raw metric name. A capture must
# explicitly confirm higher_is_better for that representation.
BBI_SAMPLE_PRIORS = {'shots': 200, 'contests': 200, 'screens': 300,
                     'drives': 300, 'rebound_chances': 300, 'possessions': 1000}


def load_rookie_college(root: str | Path, path: Path | None = None) -> dict[str, dict]:
    """The 2026 rookies' college evidence: {player_id: {evidence, projection, involvement, college}}.

    evidence: one InputEvidence per input the college -> 94-input mapping speaks to (shooting from college
    shooting and free throws, rebounding from rebound rates, defensive events from steal and block rates,
    passing from assist rate and assist-to-turnover, handling and creation from usage, self-created shots and
    turnovers), valued at NBA entry (years in league 0, his draft slot) and weighted like the real 2027-2029
    prospects. projection: expected rookie-year impact per 100 possessions (offense 'o', defense 'd') from the
    translation fit. involvement: [measured-scale target, weight] for T08 from college usage (applied after the
    measured-tendency mapping, see apply_rookie_involvement). Missing files mean no rookie has college evidence.
    """
    root = Path(root)
    path, mapping_path = path or root / ROOKIE_TRANSLATION_PATH, root / ROOKIE_MAPPING_PATH
    if not path.exists() or not mapping_path.exists():
        return {}
    from .real_prospects import INPUT_WEIGHT_BASE, INPUT_WEIGHT_MAX, INPUT_WEIGHT_PER_R, input_parts
    with path.open(encoding='utf-8') as stream:
        bundle = json.load(stream)
    with mapping_path.open(encoding='utf-8') as stream:
        mapping = json.load(stream).get('input_mapping') or {}
    fits = mapping.get('targets') or {}
    out = {}
    for pid, entry in sorted((bundle.get('class_2026') or {}).items()):
        profile = entry['profile']
        minutes = float(entry['effective_minutes'])
        pick = max(1.0, float(entry['pick']))
        parts = input_parts(profile, mapping, entry['college'].get('height_in'))
        college = entry['college']
        line = (f"{college['team']} {college['season']}: {college['games']} games, {college['minutes']:.0f} min, "
                f"BPM {college['bpm']}")
        evidence, involvement = [], None
        for iid, part in sorted(parts.items()):
            fit = fits[iid]
            value = fit['intercept'] + part + fit['years_coef'] * (0 - 3) + fit['log_pick_coef'] * (math.log(pick) - 3)
            reliability = min(INPUT_WEIGHT_MAX, INPUT_WEIGHT_BASE + INPUT_WEIGHT_PER_R * max(0.0, fit['r_college']))
            if iid == 'T08':
                involvement = [round(value, 6), round(reliability * minutes / (minutes + ROOKIE_EVIDENCE_PRIOR_MINUTES), 6)]
                continue
            grade = round(_soft_grade_bounds(value), 6)
            radius = 2 * float(fit['residual_sd'])
            evidence.append(InputEvidence(
                iid, dict(grade=grade, scale=FT_SCALE if iid == 'S07' else TECHNIQUE_SCALE),
                tuple(_bounded_band(grade, radius)), 'barttorvik:final_college_season',
                f"{ROOKIE_METHOD}: college {'/'.join(fit['features'])} translated to NBA entry by the fitted "
                f"college -> input mapping ({ROOKIE_MAPPING_PATH}, r={fit['r_college']}); {line}",
                'college:' + pid, n=minutes, prior_exposure=ROOKIE_EVIDENCE_PRIOR_MINUTES,
                reliability=reliability, exposure_unit='college_minutes'))
        out[pid] = dict(evidence=evidence, projection=dict(entry['projection']), involvement=involvement,
                        name=entry['name'], college=college)
    return out


def apply_rookie_involvement(section: dict, college: Mapping[str, dict]) -> int:
    """College usage as evidence for involvement (T08), on the measured scale after the tendency mapping, so
    the league-wide scale map (and every veteran) is untouched. Same weight rule as the other college inputs."""
    changed = 0
    for pid, entry in sorted(college.items()):
        doc = section['players'].get(pid)
        if doc is None or not entry.get('involvement'):
            continue
        target, weight = entry['involvement']
        record = doc['inputs']['T08']
        old = float(record['value']['probability'])
        new = round((1 - weight) * old + weight * min(.95, max(.05, target)), 8)
        record['value'] = dict(record['value'], probability=new)
        record['evidence'] = [*record['evidence'], _evidence(
            'barttorvik:final_college_season', f'{ROOKIE_METHOD}: college usage on the measured true-usage scale '
            f'(fitted mapping, {ROOKIE_MAPPING_PATH})', 'college:' + pid,
            exposure=dict(value=entry['college']['minutes'], unit='college_minutes'),
            notes=f'target={target}; weight={weight}; before={old}')]
        changed += 1
    return changed


def load_bbi_evidence(root: str | Path) -> dict[str, list[InputEvidence]]:
    """Load a local cache automatically, without network or absent-cache changes.

    Only completed pre-opening regular seasons, confirmed full-season population
    percentiles, season-total rows and observed (not demo/synthetic/forecast)
    batches enter. Raw values/letter grades remain in the cache without invented
    unit conversions. Newest available season wins per player/input; all related
    BBI metrics share one correlation group so duplicates cannot increase weight.
    """
    from .bbi_import import CACHE_PATH, SCHEMA_VERSION, iter_records, number
    path = Path(root) / CACHE_PATH
    if not path.exists():
        return {}
    cache = json.loads(path.read_text())
    if cache.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Unsupported BBI cache schema')
    candidates = {}
    for row in iter_records(cache, path.parent):
        metric = row['metric_name']
        pid = row.get('canonical_player_id')
        season = row.get('season')
        if (not pid or metric not in BBI_METRIC_INPUTS or
            row.get('dataset_kind') != 'observed' or
            row.get('season_type') != 'regular' or
            season not in ('2023-24', '2024-25', '2025-26') or
            row.get('row_scope') != 'season_total' or
            row.get('percentile_population') != 'season_all_players'):
            continue
        batch = cache['batches'][row['batch_id']]
        if batch.get('completeness') != 'complete':
            continue
        spec = batch['metadata'].get('metrics', {}).get(metric, {})
        direction = spec.get('percentile_higher_is_better')
        if not isinstance(direction, bool):
            continue
        percentile = number(row.get('percentile'))
        if percentile is None or row.get('percentile_scale') not in ('0_1', '0_100'):
            continue
        p = percentile / (100 if row['percentile_scale'] == '0_100' else 1)
        if not 0 <= p <= 1:
            raise ValueError('Invalid BBI percentile')
        if not direction:
            p = 1 - p
        # A transparent provisional calibration judgment, not provider raw skill:
        # smoothly map reference-population standing to a conservative proxy band.
        # Endpoints stay finite; no rating is clipped at 100.
        proxy = 50 + 25 * math.tanh(2 * (p - .5))
        n = number(row.get('sample_size')); unit = row.get('sample_unit')
        if n is not None and n <= 0:
            continue  # an explicit zero opportunity sample is not missing exposure
        if n is not None and n > 0 and unit in BBI_SAMPLE_PRIORS:
            prior, reliability = BBI_SAMPLE_PRIORS[unit], .35
        elif number(row.get('minutes')) is not None and row['minutes'] <= 0:
            continue
        elif number(row.get('minutes')) is not None and row['minutes'] > 0:
            n, prior, reliability, unit = row['minutes'], 1000, .20, 'minutes'
        else:
            n, prior, reliability, unit = 1, 4, .15, 'qualitative_assessment'
        age_weight = {'2025-26': 1, '2024-25': .7, '2023-24': .45}[season]
        reliability *= age_weight
        method = (f'BBI provider proxy ({metric}); not measured raw technique; '
                  f'50+25*tanh(2*(desirability_percentile-.5)); '
                  f'kind={row["evidence_kind"]}; season={season}; '
                  f'retrieved={row["retrieved_at_utc"]}; raw cell row={row["source_row"]}; '
                  f'sample reliability is a declared judgment; missing event counts are not fabricated')
        for iid in BBI_METRIC_INPUTS[metric]:
            obs = InputEvidence(iid, dict(grade=proxy, scale=TECHNIQUE_SCALE),
                (max(0, proxy-30), min(100, proxy+30)),
                f'{CACHE_PATH}#batch={row["batch_id"]}&row={row["source_row"]}&metric={metric}',
                method, f'bbi:provider_overlap:{pid}', n=n, prior_exposure=prior,
                reliability=reliability, exposure_unit=unit)
            # Season first; strongest exposure within it; stable tie break.
            rank = (season, reliability*n/(n+prior), row['retrieved_at_utc'], canonical_json(asdict(obs)))
            key = (pid, iid)
            if key not in candidates or rank > candidates[key][0]:
                candidates[key] = (rank, obs)
    result = {}
    for (pid, _), (_, obs) in sorted(candidates.items()):
        result.setdefault(pid, []).append(obs)
    return result


class InputEstimator:
    """Reusable local-source estimator. Construct once for a complete universe."""

    def __init__(self, skill_rows: list[dict] = (), career_players: Mapping = (),
                 stats_rows: list[dict] = (), expert_cells: Mapping = (),
                 additional_evidence: Mapping[str, list[InputEvidence]] = (),
                 legacy_traits: list = (), shot_zones: list = ()):
        self.skills = _index(list(skill_rows))
        self.stats = _index(list(stats_rows))
        self.careers = dict(career_players)
        self.experts = dict(expert_cells)
        self.additional = dict(additional_evidence)
        self.legacy = _trait_index(legacy_traits)
        self.shot_zones = _index(list(shot_zones))

    @classmethod
    def from_local(cls, root: str | Path, *, use_expert: bool = True) -> 'InputEstimator':
        root = Path(root)
        def read(path):
            with (root / path).open() as stream:
                return json.load(stream)
        bbi = load_bbi_evidence(root)
        return cls(read(SKILL_PATH)['players'], read(CAREER_PATH)['players'],
                   read(STATS_PATH)['rows'], load_reference_cells(root) if use_expert else {},
                   additional_evidence=bbi,
                   legacy_traits=read(UNIVERSE_PATH).get('traits', []),
                   shot_zones=read(SHOT_ZONE_PATH).get('profiles', []))

    def estimate_player_inputs(self, player: Any, traits: Any = None, *, prospect: bool = False,
                               college: Mapping | None = None) -> PlayerInputs:
        """college (rookies with a final college season, see load_rookie_college): its fitted skill estimates
        enter as evidence entries and its projected rookie-year impact sets the family talent level, in place
        of the flat pre-NBA readiness offset and the old draft-model traits."""
        player = _plain(player)
        if _fictional_player(player):
            return _generated_player_inputs(player, traits)
        # Effective legacy summaries may condition priors, never become measurements.
        player_id = str(player['id'])
        pos = _position(player)
        records = _physical_inputs(player, prospect)
        records.update(_tendency_inputs(player, prospect))
        # The flat readiness offset is a judgement for rookies WITHOUT evidence; with a college season the
        # translation fit measures readiness instead (ROOKIE-FIT).
        offset = prospect and college is None
        if college is not None:
            traits = {}   # old draft-model traits (slot-based) are replaced by the college evidence
        for iid in DEFINITIONS:
            if DEFINITIONS[iid]['kind'] == 'grade':
                p = _prior_grade(iid,player,offset)
                if iid == 'S07':
                    p = {'guard':79,'wing':76,'big':70}[pos] - (3 if offset else 0)
                records[iid] = _grade_record(p, 36 if prospect else 30,
                    [_evidence(METHOD_VERSION + ':position_role_prior',
                               'fixed position/role prior; no direct evidence for this technique', 'position_role_prior')],
                    prior=True, basis='broad technique prior; old traits and overall/rank excluded',
                    scale=FT_SCALE if iid == 'S07' else TECHNIQUE_SCALE)
        if not prospect:
            self._statistics(player, records)
        self._personalize_priors(player, records, traits if traits is not None else self.legacy.get(player_id, {}),
                                 use_nba_evidence=not prospect)
        if not prospect:
            self._observed_tendencies(player, records)
            self._expert_adjustments(player_id, records)
        observations = self.additional.get(player_id, [])
        # BBI's existing contract is dimension-specific weak proxy evidence.
        # Apply it after pooling: a screen-navigation proxy is not a measurement
        # of neighboring containment/contact skills. Other explicitly defined
        # technique observations can inform their declared related family.
        bbi = [o for o in observations if o.group_id.startswith('bbi:')]
        self._apply_additional(records, [o for o in observations if not o.group_id.startswith('bbi:')])
        if college is not None:
            self._apply_additional(records, [o for o in college['evidence'] if DEFINITIONS[o.input_id]['kind'] == 'grade'])
            self._hierarchical_priors(player, records, projection=college['projection'])
        elif not prospect:
            self._hierarchical_priors(player, records)
        self._apply_additional(records, bbi)
        document = dict(version=INPUT_VERSION, registry_version=REGISTRY_VERSION,
                        player_id=player_id, inputs=records)
        return PlayerInputs(document)

    def _family_context(self, player: dict, family: str) -> list[dict]:
        """One correlated provider observation, using the newest usable window.

        Fixed unit anchors: 2 offensive / 1.5 defensive points per 100, 20 IQ
        points, 12 minutes/game or usage percentage points. No totals, projected
        impact, percentiles or imputed IQ are added as independent observations.
        Missing MP means zero precision, not an invented sample size.
        """
        name = _normalize(player.get('name', ''))
        channel, impact_loading, iq_loading, work_loading = FAMILY_CONTEXT[family]
        aliases = (('CraftedOPM', 'COPM'), ('OLEBRON',)) if channel == 'offense' else (
                   ('CraftedDPM', 'CDPM'), ('DLEBRON',))
        for row, source in ((self.stats.get(name, {}), STATS_PATH),
                            (self.skills.get(name, {}), SKILL_PATH)):
            mp = _get(row, 'MP')
            if mp is None or mp <= 0:
                continue
            reliability = mp / (mp + 750)
            parts = []
            impact = {next(k for k in keys if _get(row, k) is not None): value
                      for keys in aliases if (value := _get(row, *keys)) is not None}
            if impact:
                signal = _mean(impact.values()) / (2 if channel == 'offense' else 1.5)
                parts.append((impact_loading * signal, 2 * reliability, impact))
            iq = _get(row, 'BBallIQ')
            if iq is not None and iq_loading:
                parts.append((iq_loading * (iq - 50) / 20, .5 * reliability, {'BBallIQ': iq}))
            work = {k: v for k, keys in [('MIN', ('MIN', 'MPG')), ('USGpct', ('USGpct', 'USG%'))]
                    if (v := _get(row, *keys)) is not None}
            if work and work_loading:
                signal = _mean((v - (24 if k == 'MIN' else 20)) / 12 for k, v in work.items())
                parts.append((work_loading * signal, .15 * reliability, work))
            if parts:
                # These summaries can share both games and model ingredients.
                # Average their votes and retain only the largest precision.
                return [dict(signal=sum(z * p for z, p, _ in parts) / sum(p for _, p, _ in parts),
                             precision=max(p for _, p, _ in parts), source=source,
                             group='provider_context', minutes=mp,
                             fields={k: v for _, _, fields in parts for k, v in fields.items()})]
        return []

    def _projection_context(self, player: dict, family: str, projection: Mapping) -> list[dict]:
        """A rookie's projected rookie-year impact (per 100 possessions, offense / defense) as the family
        context, on the same unit anchors as a veteran's impact metric (2 offensive / 1.5 defensive points)."""
        channel, impact_loading, _, _ = FAMILY_CONTEXT[family]
        value = float(projection['o' if channel == 'offense' else 'd'])
        return [dict(signal=impact_loading * value / (2 if channel == 'offense' else 1.5),
                     precision=ROOKIE_PROJECTION_PRECISION, source='college:' + str(player['id']),
                     group='rookie_projection', projection_source=ROOKIE_TRANSLATION_PATH,
                     fields={('projected_rookie_' + channel): value})]

    def _hierarchical_priors(self, player: dict, records: dict, projection: Mapping | None = None) -> None:
        """Partial pooling of missing technique, with no recursive prior learning.

        Snapshot direct records before updating any prior. Shared source/group
        lineage forms connected components: copied mode/passing estimates or
        overlapping expert+provider blends cannot multiply the same evidence.
        Their already-shrunk grades are conservative clues, never deconvolved
        into fictional raw observations. FT has a different scale and is excluded.
        The old local residual retains role/body/legacy distinctions; it supplies
        no likelihood precision and is not recycled through the family factor.
        """
        observed = {iid: r for iid, r in records.items() if estimation_status(r) != 'prior'}
        for family, ids in FAMILY_TECHNIQUES.items():
            samples = []
            for iid in ids:
                if iid not in observed:
                    continue
                record = observed[iid]
                sources = [e for e in record['evidence'] if not (
                    e['source'].startswith(METHOD_VERSION) or e['source'] == 'legacy_trait_prior'
                    or e.get('shared_evidence_id', '').startswith(('related_prior:', 'body_prior:', 'role_prior:')))]
                if not sources:
                    continue
                lineage = {key for e in sources for key in (e['source'], e.get('shared_evidence_id', e['source']))}
                exposure = []
                for e in sources:
                    n = _get(e.get('exposure', {}), 'value')
                    if n is not None and n > 0:
                        unit = e['exposure'].get('unit', '')
                        if 'qualitative' in unit or 'assessment' in unit:
                            exposure.append(.25)  # one assessment is not one shot
                        else:
                            k = 750 if 'minute' in unit else 250
                            exposure.append(n / (n + k))
                # A qualitative assessment is one weak vote, not N possessions.
                reliability = max(exposure, default=.25)
                low, high = uncertainty_details(record)['interval']
                grade = record['value']['grade']
                radius = max(grade - low, high - grade)
                precision = reliability / (1 + (radius / 20) ** 2)
                samples.append(dict(inputs=[iid], lineage=lineage, precision=precision,
                                    signal=(grade - _prior_grade(iid, player, False)) / 20))
            # Merge overlapping lineage, including transitive overlap. Sorting
            # and averaging make the update independent of source/input order.
            groups = []
            while samples:
                component = [samples.pop(0)]
                lineage = set(component[0]['lineage'])
                while True:
                    matches = [s for s in samples if lineage & s['lineage']]
                    if not matches:
                        break
                    for s in matches:
                        samples.remove(s)
                        component.append(s)
                        lineage.update(s['lineage'])
                groups.append(dict(signal=_mean(s['signal'] for s in component),
                                   precision=max(s['precision'] for s in component),
                                   inputs=sorted(i for s in component for i in s['inputs']),
                                   sources=sorted(lineage), group='direct_family'))
            context = (self._projection_context(player, family, projection) if projection is not None
                       else self._family_context(player, family))
            observations = []
            for summary in context:
                overlap = [g for g in groups if summary['source'] in g['sources']]
                if overlap and summary.get('group') == 'rookie_projection':
                    # The college skill evidence and the projection come from the same college season: one
                    # observation (average signal, the larger precision), never counted twice.
                    observations.append(dict(
                        signal=_mean([summary['signal'], *(g['signal'] for g in overlap)]),
                        precision=max([summary['precision'], *(g['precision'] for g in overlap)]),
                        inputs=sorted(i for g in overlap for i in g['inputs']),
                        sources=sorted(set().union(*(g['sources'] for g in overlap))),
                        group='rookie_college_and_projection', fields=summary['fields']))
                elif overlap:
                    # More specific family evidence supersedes broad impact
                    # from the SAME data source. Averaging them would let an
                    # ambiguous global model overwhelm its own skill evidence.
                    observations.extend(dict(g, superseded_context=summary) for g in overlap)
                else:
                    observations.append(summary)
                groups = [g for g in groups if g not in overlap]
            observations.extend(groups)
            if not observations:
                continue
            precision = sum(o['precision'] for o in observations)
            latent = sum(o['precision'] * o['signal'] for o in observations) / (1 + precision)
            delta = FAMILY_LOG_ODDS_SCALE * FAMILY_CORRELATION * latent
            metadata = dict(family=family, latent_mean=latent, latent_variance=1 / (1 + precision),
                            correlation=FAMILY_CORRELATION, log_odds_scale=FAMILY_LOG_ODDS_SCALE,
                            observations=observations)
            for iid in ids:
                old = records[iid]
                if estimation_status(old) != 'prior':
                    continue
                base = old['value']['grade']
                mean = 100 * _probability(_logit(base / 100) + delta)
                # Retain broad uncertainty and any disagreement with the old
                # prior even when the family talent is well supported. This is
                # a plausibility envelope, never a calibrated confidence band.
                band = uncertainty_details(old)['interval']
                radius = max(40, mean - band[0], band[1] - mean)
                evidence = [*old['evidence'], _evidence(
                    METHOD_VERSION + ':family_talent',
                    'hierarchical related-family inference; unobserved skill remains a prior',
                    'family_talent:' + str(player['id']) + ':' + family,
                    notes=json.dumps(metadata, sort_keys=True, separators=(',', ':')))]
                records[iid] = _grade_record(mean, radius, evidence, prior=True,
                    basis='position/role plus weak local context and partially pooled family talent; no direct observation')

    def _prior_features(self, player: dict) -> dict[str, tuple[float, dict]]:
        """Related evidence, not observations of isolated talents or willingness."""
        name = _normalize(player.get('name', ''))
        rows = [(self.stats.get(name, {}), STATS_PATH), (self.skills.get(name, {}), SKILL_PATH)]
        specs = {
            'three_volume': (('3PAp75',), 5, 5),
            'three_accuracy': (('FG3_PCT', '3P%'), .35, .15),
            'ft_accuracy': (('FT_PCT', 'FT%'), .77, .20),
            'close': (('LT_06_PCT',), .60, .22),
            'handler': (('prbh_pct', 'Prbh%'), .15, .20),
            'post': (('post_pct', 'Post%'), .06, .12),
            'roller': (('pnrr_pct', 'Pnrr%'), .08, .16),
            'cut': (('cut_pct', 'Cut%'), .10, .15),
            'movement': (('offscreen_pct', 'OffScreen%', 'handoff_pct', 'Handoff%'), .05, .12),
            'spot_up': (('spotup_pct', 'SpotUp%'), .25, .25),
            'transition': (('transition_pct', 'Transition%'), .15, .20),
            'creation': (('boxCreationEst',), 4, 6),
            'passing': (('passerRating',), 35, 40),
            'security': (('cTOVpct', 'cTOV%'), 10, -8),
            'foul_drawing': (('FTr',), 25, 25),
            'oreb': (('ORBpct', 'ORB%'), 5, 7),
            'dreb': (('DRBpct', 'DRB%'), 15, 12),
            'blocks': (('BLKpct', 'BLK%'), 2, 4),
            'steals': (('STLpct', 'STL%'), 1.5, 1.5),
            'disruption': (('DEFLECTIONS', 'DEFL'), 2, 2),
            'foul_control': (('rPF',), 0, -2),
            'usage': (('USGpct', 'USG%'), 20, 12),
            'workload': (('MIN', 'MPG', 'minutes'), 24, 14),
        }
        features = {}
        for key, (aliases, center, spread) in specs.items():
            for row, source in rows:
                value = _get(row, *aliases)
                if value is None:
                    continue
                original = value
                if key in ('close', 'ft_accuracy', 'three_accuracy') and value > 1:
                    value /= 100
                mp = _get(row, 'MP')
                reliability = mp/(mp+750) if mp is not None and mp > 0 else .2
                signal = math.tanh((value-center)/spread)*reliability
                features[key] = (signal, dict(source=source, field=key, value=original, minutes=mp))
                break
        # Defended position shares are deployment context, never defense success.
        for row, source in rows:
            shares = {k: _get(row,k) for k in ('dPGpct','dSGpct','dPFpct','dCpct')}
            if any(v is None for v in shares.values()):
                continue
            contrast = (shares['dPGpct']+shares['dSGpct']-shares['dPFpct']-shares['dCpct'])/100
            mp = _get(row, 'MP')
            reliability = mp/(mp+750) if mp is not None and mp > 0 else .2
            for key, direction in [('guard_assignment',1),('big_assignment',-1)]:
                features[key] = (math.tanh(direction*contrast)*reliability,
                    dict(source=source,field=key,value=shares,minutes=mp))
            break
        # Verified career workload fallback when a provider window is absent.
        if 'workload' not in features:
            profile = self.careers.get(str(player.get('espn_player_id') or ''), {})
            latest = [r for r in profile.get('seasons',[]) if r.get('season')=='2025-26']
            if len(latest)==1:
                mp,games = _get(latest[0],'minutes'),_get(latest[0],'games')
                if mp is not None and games is not None and mp>0 and games>0:
                    mpg = mp/games
                    features['workload'] = (math.tanh((mpg-24)/14)*mp/(mp+750),
                        dict(source=CAREER_PATH,field='workload',value=mpg,minutes=mp))
        return features

    def _personalize_priors(self, player: dict, records: dict, traits: Any, *, use_nba_evidence: bool = True) -> None:
        """Weak, sourced conditioning of priors; direct estimates are untouched.

        Full log-odds residual budgets: legacy .60, related stats .40, body/age
        .25, defensive role .20. Each signal is bounded with tanh and averaged,
        never added once per correlated metric. No RNG, name or adapter targets.
        Broad uncertainty is retained irrespective of sample size.
        """
        pid = str(player['id'])
        values = _trait_values(traits, pid)
        features = self._prior_features(player) if use_nba_evidence else {}
        pos = _position(player)
        h,w,span,age = (_get(player,k) for k in ('height_inches','weight_lbs','wingspan_inches','age'))
        frame = {'guard':76,'wing':80,'big':83}[pos]
        expected_mass = {'guard':195,'wing':220,'big':245}[pos]
        geometry = {}
        observed_geometry = {k:v for k,v in [('height_inches',h),('weight_lbs',w),('wingspan_inches',span),('age',age)] if v is not None and v>0}
        if h is not None and h>0:
            geometry['size'] = math.tanh((h-frame)/5)
        if span is not None and span>0 and h is not None and h>0:
            geometry['length'] = math.tanh((span-h-{'guard':3,'wing':4,'big':5}[pos])/5)
        if w is not None and w>0:
            geometry['strength'] = math.tanh((w-expected_mass-((h-frame)*4 if h else 0))/40)
            geometry['movement'] = -geometry['strength']*.5
        if age is not None and age>0:
            geometry['sustained'] = math.tanh((27-age)/18)
            geometry['movement'] = _mean([geometry.get('movement',0),math.tanh((27-age)/20)])
        physical_links = {
            'P05':'movement','P06':'movement','P07':'movement','P08':'strength',
            'P09':'movement','P10':'length','P11':'sustained','P12':'sustained',
            'S12':'size','S13':'length','S21':'strength','S27':'strength','S29':'length',
            'S30':'size','S31':'strength','S32':'length','S34':'strength','S36':'size','S37':'length',
        }
        # Different defensive tasks inform a role prior, never task success.
        role = str(player.get('primary_def_role') or '').lower()
        role_signals = {}
        if any(k in role for k in ('rim','anchor','interior','big')):
            role_signals.update({iid:.5 for iid in ('S36','S37','S30','T15')})
        if any(k in role for k in ('on-ball','chaser','stopper','mobile','perimeter')):
            role_signals.update({iid:.4 for iid in ('S33','S35','S40','P07')})
        if any(k in role for k in ('help','roamer')):
            role_signals.update({iid:.5 for iid in ('S38','S39','T15')})

        for iid, old in list(records.items()):
            if estimation_status(old) != 'prior' or iid in ('P01','P02','P03','P04'):
                continue
            evidence = list(old['evidence'])
            legacy_used, feature_used = set(),set()

            def residual(legacy_keys, stat_keys):
                legacy_keys = [k for k in legacy_keys if k in values]
                stat_keys = [k for k in stat_keys if k in features]
                legacy_used.update(legacy_keys)
                feature_used.update(stat_keys)
                return (.60*_mean(math.tanh((values[k]-50)/45) for k in legacy_keys)
                        + .40*_mean(features[k][0] for k in stat_keys))

            if DEFINITIONS[iid]['kind']=='distribution':
                rows=[]
                for row in old['value']['rows']:
                    weights={}
                    for outcome,p in row['probabilities'].items():
                        legacy_keys,stat_keys = _DISTRIBUTION_PRIOR_LINKS[iid][outcome]
                        weights[outcome] = p*math.exp(residual(legacy_keys,stat_keys))
                    total=sum(weights.values())
                    rows.append(dict(condition=row['condition'],probabilities={k:v/total for k,v in weights.items()}))
                value=dict(old['value'],rows=rows)
                intervals={k:_bounded_band(p,.40,1) for k,p in rows[0]['probabilities'].items()}
                interval=None
            else:
                legacy_keys = _LEGACY_PRIOR_LINKS.get(iid,('passing_reads',) if iid.startswith('F') else ())
                stat_keys = _STAT_PRIOR_LINKS.get(iid,('passing', 'creation') if iid.startswith('F') else ())
                delta=residual(legacy_keys,stat_keys)
                if iid=='P12':
                    delta *= .55  # sustained workload is a weaker clue to rest recovery
                geometry_key=physical_links.get(iid)
                if geometry_key in geometry:
                    delta += .25*geometry[geometry_key]
                delta += .20*role_signals.get(iid,0)
                if DEFINITIONS[iid]['kind']=='propensity':
                    mean=_probability(_logit(old['value']['probability'])+delta)
                    value=dict(old['value'],probability=round(mean,8))
                    interval=_bounded_band(mean,.40,1)
                elif iid=='P10':
                    # Native-unit prior, NOT a vertical jump inferred as a fact.
                    mean=old['value']['measurements'][0]['value']*math.exp(.12*delta)
                    previous=uncertainty_details(old)['interval']
                    radius=max(35,(previous[1]-previous[0])/2)
                    interval=[round(max(.001,mean-radius),6),round(mean+radius,6)]
                    measure=dict(old['value']['measurements'][0],value=round(mean,6),interval=interval,
                                 protocol='body/related evidence conditioned jump prior; no jump trial')
                    value=dict(measurements=[measure])
                else:
                    display=DEFINITIONS[iid]['kind']=='physical'
                    grade=old['value']['display_grade' if display else 'grade']
                    prior=grade['grade'] if display else grade
                    mean=100*_probability(_logit(prior/100)+delta)
                    value=(dict(measurements=[],display_grade=dict(grade=round(mean,6),scale=TECHNIQUE_SCALE)) if display
                           else dict(grade=round(mean,6),scale=old['value']['scale']))
                    interval=_bounded_band(mean,45 if display else 40)
                intervals=None
                if geometry_key in geometry:
                    evidence.append(_evidence(UNIVERSE_PATH,'body/age conditions an uncertain prior; not a capacity test',
                        'body_prior:'+pid,notes=json.dumps(observed_geometry,sort_keys=True,separators=(',',':'))))
                if iid in role_signals:
                    evidence.append(_evidence(UNIVERSE_PATH,'defensive deployment conditions a prior, not observed task success',
                        'role_prior:'+pid,notes=role))
            if legacy_used:
                evidence.append(_evidence('legacy_trait_prior','weak correlated effective traits; no isolated measurement',
                    'legacy_trait_prior:'+pid,notes=UNIVERSE_PATH+'#traits; '+json.dumps({k:values[k] for k in sorted(legacy_used)},sort_keys=True,separators=(',',':'))))
            by_source={}
            for key in sorted(feature_used):
                info=features[key][1]
                by_source.setdefault(info['source'],{})[key]=dict(value=info['value'],minutes=info['minutes'])
            for source,metadata in sorted(by_source.items()):
                evidence.append(_evidence(source,'related outcomes/workload/deployment condition a prior; alternatives and technique unobserved',
                    'related_prior:'+pid,notes=json.dumps(metadata,sort_keys=True,separators=(',',':'))))
            if len(evidence)==len(old['evidence']):
                continue
            records[iid]=_record(value,evidence,interval,intervals=intervals,prior=True,basis=
                'player-conditioned prior shrunk toward position/role; related evidence is not a measurement',
                limitations=LIMIT+' Legacy traits and observed workload/geometry are weak prior context only; causal decomposition and available opportunity sets remain unknown.')

    def _observed_tendencies(self, player: dict, records: dict) -> None:
        """Observed deployment-conditioned behavior, separate from pure willingness.

        Exact attempt ratios identify three-point choice among field-goal
        attempts. Play-type tags support weaker, explicitly partial proxies.
        No mixed-window passes/touches ratios, invented catch/pull-up counts,
        efficiency-as-frequency, or simulation-score targets are used.
        """
        name=_normalize(player.get('name',''))
        rows=[(self.stats.get(name,{}),STATS_PATH),(self.skills.get(name,{}),SKILL_PATH)]

        def field(*aliases):
            for row,source in rows:
                raw=_get(row,*aliases)
                if raw is not None:
                    return raw,source,row
            return None,None,{}

        def frequency(*aliases):
            raw,source,row=field(*aliases)
            # Play-type shares are fractions; explicit percent fields are scaled
            # only by callers. A missing provider field is NEVER a zero event.
            return (raw,source,row) if raw is not None and 0<=raw<=1 else (None,None,{})

        def provenance(source,method,mp,notes,group='observed_tendency'):
            kwargs=dict(notes=notes)
            if mp is not None and mp>0:
                kwargs['exposure']=dict(value=mp,unit='source_snapshot_minutes')
            return _evidence(source,method,group+':'+str(player['id']),**kwargs)

        def weight(row,ceiling):
            mp=_get(row,'MP')
            return ceiling*(mp/(mp+750) if mp is not None and mp>0 else .2)

        def distribution(iid,target,w,evidence,basis,conditions,radius=.30):
            old=records[iid]
            prior=old['value']['rows'][0]['probabilities']
            total=sum(target.values())
            if total<=0 or set(target)!=set(prior):
                return
            target={k:v/total for k,v in target.items()}
            probs={k:(1-w)*prior[k]+w*target[k] for k in prior}
            value=dict(old['value'],reference_conditions=conditions,
                       rows=[dict(condition='reference_opportunity',probabilities=probs)])
            records[iid]=_record(value,[*old['evidence'],*evidence],
                intervals={k:_bounded_band(p,radius,1) for k,p in probs.items()},basis=basis,
                limitations=LIMIT+' Observed deployment is conditioned on, not mistaken for coach-independent willingness.')

        def propensity(iid,target,w,evidence,basis,conditions,radius=.35):
            old=records[iid]
            p=(1-w)*old['value']['probability']+w*target
            records[iid]=_record(dict(probability=round(p,8),reference_conditions=conditions),
                [*old['evidence'],*evidence],_bounded_band(p,radius,1),basis=basis,
                limitations=LIMIT+' Frequency is conditional on retained deployment; ability and unobserved opportunities remain confounded.')

        # T02: current regular-season 3PA/FGA first. Historical reference bins
        # supply only the conditional two-point-location shape, not a second
        # overlapping shooting sample. Broken historical game boxes never enter.
        profile=self.careers.get(str(player.get('espn_player_id') or ''),{})
        three=None
        for season,discount in [('2025-26',1.0),('2024-25',.6),('2023-24',.36)]:
            season_rows=[r for r in profile.get('seasons',[]) if r.get('season')==season]
            if len(season_rows)!=1:
                continue
            row=season_rows[0]
            n,a=_get(row,'fga'),_get(row,'fg3a')
            if n is not None and a is not None and n>0 and 0<=a<=n:
                three=(a/n,n*discount,CAREER_PATH,
                       f'{season} regular season; 3PA={a}; FGA={n}; exposure discount={discount}; explicit ESPN ID')
                break
        if three is None:
            for row,source in rows:
                rate=_get(row,'threePAr','3PAr')
                if rate is not None:
                    rate/=100  # both named source fields are percentage points
                gp,fga,fg3a=_get(row,'GP'),_get(row,'FGA'),_get(row,'FG3A','3PA')
                if fga is not None and fga<=0:
                    continue  # known empty/invalid denominator is not missing exposure
                if rate is None and fga is not None and fg3a is not None and fga>0 and 0<=fg3a<=fga:
                    rate=fg3a/fga
                if rate is None:
                    fgap75,threep75=_get(row,'FGAp75'),_get(row,'3PAp75')
                    if fgap75 is not None and threep75 is not None and fgap75>0:
                        rate=threep75/fgap75
                if rate is None or not 0<=rate<=1:
                    continue
                # Count only source-matched GP×FGA; otherwise minute exposure is
                # explicitly approximate, with a conservative mixed-window discount.
                mp=_get(row,'MP') or 0
                n=(gp*fga*.5 if gp is not None and fga is not None and gp>0 and fga>0 else mp*.20)
                if n>0:
                    three=(rate,n,source,f'provider 3PA/FGA share={rate}; effective attempts={n}; per-game GP×FGA halved, or .20×MP proxy; mixed window')
                    break
        old=records['T02']
        prior=old['value']['rows'][0]['probabilities']
        nonthree={k:prior[k]/(1-prior['three']) for k in ('rim','short_paint','midrange')}
        zone=self.shot_zones.get(name,{})
        zone_counts=dict.fromkeys(nonthree,0.0)
        bins=zone.get('bins') or []
        valid_zone=bool(bins)
        zone_total=zone_three=0.0
        for b in bins:
            if not isinstance(b,list) or len(b)<4:
                valid_zone=False;break
            x,y,z,n=(_number(v) for v in b[:4])
            if None in (x,y,z,n) or n<0 or z not in range(1,16):
                valid_zone=False;break
            zone_total+=n
            if z>=10:
                zone_three+=n
                continue
            distance=math.hypot(x,y)
            key='rim' if distance<4 else 'short_paint' if distance<14 else 'midrange'
            zone_counts[key]+=n
        declared=_get(zone,'attempts')
        valid_zone=valid_zone and declared is not None and abs(declared-zone_total)<1e-6
        zone_n=sum(zone_counts.values()) if valid_zone else 0
        if three is None and valid_zone and zone_total>0:
            three=(zone_three/zone_total,.6*zone_total,SHOT_ZONE_PATH,
                   f'2024-25 retained chart; 3PA={zone_three}; FGA={zone_total}; recency discount=.6; bin totals reconciled to declared attempts')
        evidence=[]
        if zone_n>0:
            effective=.6*zone_n
            nonthree={k:(.6*zone_counts[k]+100*nonthree[k])/(effective+100) for k in nonthree}
            evidence.append(_evidence(SHOT_ZONE_PATH,'2024-25 conditional two-point locations from retained aggregate bin centers',
                'shot_zone_reference:'+str(player['id']),exposure=dict(value=effective,unit='recency_discounted_two_point_attempts'),
                notes='2-ft bin centers; rim<4ft, short paint 4-14ft, midrange 14ft to arc; bin boundaries and season change uncertain; prior exposure=100'))
        if three is not None:
            rate,n,source,notes=three
            p3=(rate*n+100*prior['three'])/(n+100)
            evidence.append(_evidence(source,'three-point choice shrunk by 100 prior field-goal attempts',
                'shot_location_attempts:'+str(player['id']),exposure=dict(value=round(n,6),unit='effective_field_goal_attempts'),notes=notes))
        else:
            p3=prior['three']
        if evidence:
            probs={k:(1-p3)*v for k,v in nonthree.items()}
            probs['three']=p3
            value=dict(old['value'],reference_conditions=
                'one field-goal attempt under retained season deployment, shot access and defense; observed region-choice distribution, not equal-access intrinsic willingness',
                rows=[dict(condition='reference_opportunity',probabilities=probs)])
            intervals={k:_bounded_band(p,.18 if zone_n>0 else .32,1) for k,p in probs.items()}
            if three is not None:
                # Sampling plus a fixed deployment/form allowance, not nominal CI.
                radius=.05+2*math.sqrt(p3*(1-p3)/(three[1]+101))
                intervals['three']=_bounded_band(p3,radius,1)
            records['T02']=_record(value,[*old['evidence'],*evidence],intervals=intervals,
                basis='observed attempt-location mix; unobserved two-point regions retain player-conditioned priors',
                limitations='Three-point share uses attempts, never accuracy. Two-point locations use dated aggregate bins where available; other two-point shares remain priors. No game-box FGA, LT_06 efficiency or ambiguous FREQ field is used as shot volume.')

        # Direct frequency-tag proxies, conditional on observed finished plays.
        for iid,aliases,label in [
            ('T05',('transition_pct','Transition%'),'transition-tagged finished scoring play'),
            ('T09',('cut_pct','Cut%'),'cut-tagged finished scoring play'),
            ('T10',('offscreen_pct','OffScreen%','handoff_pct','Handoff%'),'off-screen or handoff-tagged finished scoring play')]:
            raw,source,row=frequency(*aliases)
            if raw is None:
                continue
            propensity(iid,raw,weight(row,.65),[provenance(source,'observed play-type frequency; opportunity-conditioned proxy',
                _get(row,'MP'),f'{aliases}: share={raw}; actual tag denominator is provider finished plays, not available route windows')],
                'observed play-type frequency shrunk toward player prior; available route windows not counted',
                'one provider-finished scoring play under retained coach deployment and defense; '+label)

        usage,source,row=field('USGpct','USG%')
        if usage is not None and 0<=usage<=100:
            propensity('T08',usage/100,weight(row,.65),[provenance(source,'observed possession-use rate as an involvement proxy',
                _get(row,'MP'),f'USG%={usage}; assignment and turnovers included, not intrinsic selfishness')],
                'possession-use frequency under observed deployment; coach workload is not innate willingness',
                'one team possession during player minutes under retained role and teammates; player consumes shot/FT/turnover possession')

        orb,source,row=field('ORBpct','ORB%')
        if orb is not None and 0<=orb<=100:
            # Recovery of a rebound requires both pursuit and winning the ball.
            # A role-specific success prior keeps crash probability separate from
            # ORB% itself; the decomposition remains a very uncertain proxy.
            success={'guard':.10,'wing':.14,'big':.22}[_position(player)]
            target=1-math.exp(-(orb/100)/success)
            propensity('T12',target,weight(row,.40),[provenance(source,'offensive rebound opportunity rate constrains a weak crash proxy',
                _get(row,'MP'),f'ORB%={orb}; assumed recovery scale={success}; target=1-exp(-ORB_fraction/scale); pursuit/tools/team instruction not isolated')],
                'rebound-rate-constrained crash proxy with explicit uncertain recovery conversion',
                'one offensive rebound opportunity under retained team crash assignment and body/tools; pursuit is latent, recovery rate observed',radius=.40)

        ftr,source,row=field('FTr')
        if ftr is not None and ftr>=0:
            propensity('T18',1-math.exp(-ftr/100),weight(row,.35),[provenance(source,'FT-attempt/FG-attempt rate weakly constrains contact preference',
                _get(row,'MP'),f'FTr={ftr}; fouls, craft, defender and attempt mix confounded; not counted contact-seeking attempts')],
                'contact-seeking proxy from foul exposure; technique and referee response not isolated',
                'one scoring attempt under retained deployment and whistle environment; contact opportunity unobserved',radius=.40)

        # Partial action and mode partitions. Missing outcomes retain prior mass;
        # never use mismatched touches/passes as a manufactured touch denominator.
        groups={
            'T01': {'shoot':(('spotup_pct','SpotUp%'),('offscreen_pct','OffScreen%'),('handoff_pct','Handoff%')),
                    'drive':(('prbh_pct','Prbh%'),('iso_pct','Iso%')),
                    'post':(('post_pct','Post%'),)},
            'T03': {'catch':(('spotup_pct','SpotUp%'),),
                    'pull_up':(('prbh_pct','Prbh%'),('iso_pct','Iso%')),
                    'movement':(('offscreen_pct','OffScreen%'),('handoff_pct','Handoff%'))},
        }
        for iid,options in groups.items():
            base=records[iid]['value']['rows'][0]['probabilities']
            target=dict(base);observed={};used_rows=[];ev=[]
            for outcome,alias_groups in options.items():
                found=[]
                for aliases in alias_groups:
                    raw,source,row=frequency(*aliases)
                    if raw is not None:
                        found.append(raw);used_rows.append(row)
                        ev.append(provenance(source,'play-type label is an imperfect action/mode proxy',_get(row,'MP'),f'{outcome}: {aliases}={raw}; mode/action outcomes not independently tagged'))
                if found:
                    observed[outcome]=sum(found)
            if not observed or not used_rows:
                continue
            if iid=='T01':
                # Preserve pass/reset exactly; only redistribute scoring choices.
                mass=sum(base[k] for k in options)
                scores={k:observed.get(k,base[k]) for k in options}
                total=sum(scores.values())
                if total<=0:
                    continue
                for k in scores:
                    target[k]=mass*scores[k]/total
            else:
                target.update(observed)
            w=min(weight(row,.35 if iid=='T01' else .45) for row in used_rows)
            distribution(iid,target,w,ev,
                'partial play-type action/mode proxy; unobserved pass/reset and overlapping shot modes remain uncertain',
                'one reference offensive opportunity with retained deployment and play availability; play-type action/mode proxy, pass/reset and exact catch/pull-up opportunities unobserved',radius=.35)

        roll,source,row=frequency('pnrr_pct','Pnrr%')
        if roll is not None:
            base=records['T11']['value']['rows'][0]['probabilities']
            involvement=math.tanh((roll-.08)/.16)
            p3=records['T02']['value']['rows'][0]['probabilities']['three']
            target=dict(base)
            target['screen']*=math.exp(.3*involvement)
            target['roll']*=math.exp(involvement*(1-p3))
            target['pop']*=math.exp(involvement*p3)
            distribution('T11',target,weight(row,.45),[provenance(source,
                'roll-man-tag frequency constrains involvement; roll/pop/slip response remains inferred',_get(row,'MP'),
                f'Pnrr share={roll}; shooting-location share conditions roll/pop prior; no continuation-opportunity counts')],
                'roll participation observed; screen/roll/pop/slip mix remains a broad shooting/role-conditioned proxy',
                'one screen involvement under retained deployment; roll-man tags observed, feasible roll/pop/slip alternatives not counted',radius=.40)

    def _statistics(self, player: dict, records: dict) -> None:
        name = _normalize(player.get('name', ''))
        # Prefer later Crafted snapshot; preserve per-field source identity.
        older, newer = self.skills.get(name, {}), self.stats.get(name, {})
        aliases = {'FT%':'FT_PCT','3P%':'FG3_PCT','LT_06_PCT':'LT_06_PCT',
                   'OffScreenPPP':'offscreen_ppp','HandoffPPP':'handoff_ppp',
                   'PrbhPPP':'prbh_ppp','IsoPPP':'iso_ppp','PostPPP':'post_ppp',
                   'Prbh%':'prbh_pct','Post%':'post_pct','Pnrr%':'pnrr_pct','Transition%':'transition_pct'}
        def field(key):
            keys = (aliases.get(key,key),key)
            for row, source in [(newer, STATS_PATH), (older, SKILL_PATH)]:
                v = _get(row,*keys)
                if v is not None:
                    return v, source, row
            return None,None,{}
        profile = self.careers.get(str(player.get('espn_player_id') or ''),{})
        totals,seasons = _career_totals(profile)
        pos,role = _position(player),_role(player)
        minutes = totals.get('minutes',0)

        def sampled(iid, rate, n, prior_rate, center, spread, source, group, basis,
                    *, k=180, radius=20, direct=False, detail=''):
            if rate is None or n <= 0:
                return
            posterior = (n*rate + k*prior_rate)/(n+k)
            mean = 100*posterior if direct else _soft_grade(posterior,center,spread)
            ev = _evidence(source, 'sample-weighted shrinkage toward fixed position/role prior', group,
                exposure=dict(value=round(n,6),unit='attempts' if direct or iid.startswith('S0') else 'effective_opportunities'),
                notes=f'{basis}; rate={rate:.8g}; prior={prior_rate:.8g}; prior_exposure={k}; '+detail)
            uncertainty = radius + 14*math.sqrt(k/(n+k))
            records[iid] = _grade_record(mean,uncertainty,[*records[iid]['evidence'],ev],
                basis=basis, scale=FT_SCALE if direct else TECHNIQUE_SCALE,
                confidence='medium' if direct and n>=150 else 'low')

        for iid,makes,attempts,rate_key,prior_rate,center,spread in [
            ('S07','ftm','fta','FT%', {'guard':.79,'wing':.76,'big':.70}[pos],.65,.25),
            ('S01','fg3m','fg3a','3P%', {'guard':.355,'wing':.35,'big':.32}[pos]+(.01 if 'shoot' in role else 0),.34,.11)]:
            n=totals.get(attempts,0)
            source=CAREER_PATH
            detail='recency-weighted seasons '+','.join(seasons)+'; explicit ESPN ID; no game-box shooting fields'
            if n>0:
                rate=totals[makes]/n
            else:
                rate,source,row=field(rate_key)
                if rate is None:
                    continue
                # Only known source per-game attempts × GP, explicitly approximate.
                denom = _get(row,'FTA' if iid=='S07' else 'FG3A','3PA')
                gp = _get(row,'GP')
                n=(denom or 0)*(gp or 0)*.5  # mixed window → half effective exposure
                detail='provider percentage; approximate attempts=per-game attempts×GP, halved for mixed windows'
            if rate is None or not 0<=rate<=1:
                continue
            sampled(iid,rate,n,prior_rate,center,spread,source,'career_shooting' if source==CAREER_PATH else 'provider_shooting',
                    'FT conversion' if iid=='S07' else 'shared reference-three inference; catch/pull-up split unobserved',
                    direct=iid=='S07',radius=5 if iid=='S07' else 19,k=100 if iid=='S07' else 250,detail=detail)
            if iid=='S01' and estimation_status(records[iid])=='estimated':
                # Same shared observation, NOT independent evidence or same execution.
                for split,penalty in [('S02',9),('S03',12)]:
                    base=records[iid]
                    # Smooth translation near endpoints preserves strict 0..100.
                    mean=100*_probability(_logit(base['value']['grade']/100)-penalty/20)
                    records[split]=_grade_record(mean,30,[*base['evidence']],basis=
                        'shared three-point baseline with live-dribble/movement difficulty prior; no measured mode split')

        # Close-shot outcomes mix dunks, size, defense and selection; a weak,
        # broad close-touch estimate only, never separate dunk/air-catch grades.
        close,source,row=field('LT_06_PCT')
        if close is not None:
            close=close/100 if close>1 else close
            mp=_get(row,'MP') or 0
            if 0<=close<=1:
                sampled('S10',close,mp*.035,.59,.57,.25,source,'provider_close',
                        'close-touch hypothesis from mixed close finishes; tools/shot selection unresolved',k=180,radius=28,
                        detail='effective close opportunities = .035×provider minutes; heuristic, not tagged layup attempts')
        # Context-specific PPP is retained as a weak scoring constraint, not a
        # success probability or an independent dribble/physical measurement.
        for iid,key,share in [('S05','PrbhPPP','Prbh%'),('S18','IsoPPP','iso_pct'),('S22','PostPPP','Post%')]:
            value,source,row=field(key)
            freq,_,_=field(share)
            mp=_get(row,'MP') or 0
            if value is None or freq is None or freq<=0 or mp<=0:
                continue
            n=mp*.4*freq
            mean=records[iid]['value']['grade']
            target=_soft_grade(value,.92 if iid!='S22' else .96,.45)
            weight=.35*n/(n+150)
            records[iid]=_grade_record((1-weight)*mean+weight*target,32,
                [*records[iid]['evidence'],_evidence(source,'weak play-type PPP constraint; technique decomposition uncertain',
                 'provider_playtype',exposure=dict(value=round(n,6),unit='approximate_finished_playtype_possessions'),
                 notes=f'{key}={value}; {share}={freq}; .4×MP×share proxy; no tagged pure-technique sample')],
                basis='play-type scoring constrains a broad technique hypothesis, with most mass retained on prior')

        # Recognition uses assist-creation context; execution uses the provider
        # passer model. AST/TOV is NEVER treated as pass success. Context eligibility
        # distinguishes supported families; unsupported routes remain broad priors.
        passer,psource,prow=field('passerRating')
        ast75,asource,arow=field('ASTp75')
        recognition_exposure=(_get(arow,'MP') or 0)*.5
        if ast75 is None and minutes>0 and 'assists' in totals:
            ast75=75*totals['assists']/(minutes*2.05)
            asource=CAREER_PATH
            recognition_exposure=minutes
        contexts={'F01':True,'F02':False,'F03':False,'F04':False,'F05':False,
                  'F06':False,'F07':False,'F08':False,'F09':False}
        for fam,key in [('F03','Prbh%'),('F05','Pnrr%'),('F06','Prbh%'),('F08','Post%'),('F09','Transition%')]:
            v,_,_=field(key)
            contexts[fam]=v is not None and v>.02
        for family,eligible in contexts.items():
            if not eligible:
                continue
            for part in ('recognition','execution'):
                iid=family+'.'+part
                if part=='recognition':
                    raw,source=ast75,asource
                    target=_soft_grade(raw,3.5,5) if raw is not None else None
                    exposure=recognition_exposure
                    explanation='assist creation per75 as a weak window-recognition constraint, not available-read success'
                else:
                    raw,source=passer,psource
                    target=_soft_grade(raw,35,40) if raw is not None else None
                    exposure=(_get(prow,'MP') or 0)*.5
                    explanation='provider passer model as a weak delivery constraint; read/physical/context effects unresolved'
                if target is None or exposure<=0:
                    continue
                base=records[iid]['value']['grade']
                weight=.55*exposure/(exposure+750)
                records[iid]=_grade_record((1-weight)*base+weight*target,32,
                    [*records[iid]['evidence'],_evidence(source,explanation,
                    'shared_passing_recognition' if part=='recognition' else 'shared_passing_execution',
                    exposure=dict(value=round(exposure,6),unit='recency_weighted_minutes' if source==CAREER_PATH else 'effective_provider_minutes'),
                    notes=f'raw={raw:.8g}; shared family constraint, not an independently measured {family} skill')],basis=explanation)

    def _expert_adjustments(self, player_id: str, records: dict) -> None:
        for (pid,iid), entry in sorted(self.experts.items()):
            if pid != player_id or DEFINITIONS[iid]['kind']!='grade' or iid=='S07':
                continue
            ref=entry['record']
            if 'grade' not in ref.get('value',{}):
                continue
            base=records[iid]
            raw=ref['value']['grade']
            mean=base['value']['grade']
            adjusted=.65*mean+.35*raw
            # Disagreement widens the band; expert opinion doesn't erase stats.
            radius=max((uncertainty_details(base)['interval'][1]-uncertainty_details(base)['interval'][0])/2,
                       abs(raw-mean)*.7,25)
            evidence=[*base['evidence'],_evidence(entry['packet'],
                '35% expert judgment adjustment; reference range magnitude provisional; shared with validation reference',
                'expert_'+player_id,notes='input='+iid+'; reference='+str(raw)+'; '+ref['uncertainty']['notes'])]
            evidence.extend(ref['evidence'])
            records[iid]=_grade_record(adjusted,radius,evidence,basis=
                'statistics/prior plus sourced expert residual; disagreement retained in uncertainty')

    def _apply_additional(self, records: dict, observations: list[InputEvidence]) -> None:
        groups={}
        for obs in observations:
            if obs.input_id not in DEFINITIONS:
                raise ValueError('Unapproved input: '+obs.input_id)
            if (not all(math.isfinite(x) for x in (obs.n,obs.prior_exposure,obs.reliability))
                or obs.n<=0 or obs.prior_exposure<=0 or not 0<obs.reliability<=1):
                raise ValueError('Evidence requires positive exposure/prior and reliability in (0,1]')
            if not obs.source_id or not obs.method or not obs.group_id or not obs.exposure_unit:
                raise ValueError('Evidence needs source, method, group and exposure unit')
            weight=obs.reliability*obs.n/(obs.n+obs.prior_exposure)
            key=(obs.input_id,obs.group_id)
            # Deterministic strongest source per correlation group, never double count.
            rank=(weight,canonical_json(asdict(obs)))
            if key not in groups or rank>groups[key][0]:
                groups[key]=(rank,obs)
        for key,(_,obs) in sorted(groups.items()):
            iid=obs.input_id
            old=records[iid]
            if DEFINITIONS[iid]['kind']=='grade' and obs.value.get('scale')!=old['value']['scale']:
                raise ValueError('Additional evidence must declare the same grade scale')
            band=obs.interval
            details=uncertainty_details(old)
            if DEFINITIONS[iid]['kind']=='distribution':
                if not obs.intervals:
                    raise ValueError('Distribution evidence requires outcome intervals')
                if set(obs.intervals) != set(obs.value['rows'][0]['probabilities']):
                    raise ValueError('Distribution intervals must cover every outcome')
                for outcome, bounds in obs.intervals.items():
                    if (len(bounds)!=2 or not all(math.isfinite(v) for v in bounds)
                        or not 0<=bounds[0]<=obs.value['rows'][0]['probabilities'][outcome]<=bounds[1]<=1):
                        raise ValueError('Invalid outcome uncertainty interval')
                details=dict(intervals=obs.intervals)
            elif band is None or len(band)!=2 or not all(math.isfinite(v) for v in band):
                raise ValueError('Evidence requires finite native-unit interval')
            candidate=_record(obs.value,[_evidence(obs.source_id,obs.method,obs.group_id)],
                list(band) if band else None, intervals=obs.intervals)
            # Validate source shape before arithmetic or mutation.
            PlayerInputs(dict(version=INPUT_VERSION,registry_version=REGISTRY_VERSION,
                              player_id='evidence_shape_check',inputs={iid:candidate}))
            scalar=scalar_value(candidate)
            if band and (scalar is None or not band[0]<=scalar<=band[1]):
                raise ValueError('Evidence value must lie inside its uncertainty interval')
            weight=obs.reliability*obs.n/(obs.n+obs.prior_exposure)
            blended=_blend_value(old['value'],obs.value,weight)
            ev=[*old['evidence'],_evidence(obs.source_id,obs.method,obs.group_id,
                exposure=dict(value=obs.n,unit=obs.exposure_unit),
                notes=f'prior exposure={obs.prior_exposure}; reliability={obs.reliability}; weight={weight:.8g}')]
            intervals=details.get('intervals')
            if intervals:
                previous=uncertainty_details(old).get('intervals',{})
                intervals={k:[min(previous.get(k,v)[0],v[0]),max(previous.get(k,v)[1],v[1])]
                           for k,v in intervals.items()}
            oldband=uncertainty_details(old).get('interval')
            if DEFINITIONS[iid]['kind']=='physical' and not old['value'].get('measurements') and obs.value.get('measurements'):
                oldband=None  # display-grade uncertainty cannot be combined with native units
            combined=[min(oldband[0],band[0]),max(oldband[1],band[1])] if band and oldband else band
            records[iid]=_record(blended,ev,list(combined) if combined else None,intervals=intervals,
                basis='new source shrunk against existing estimate; uncertainty envelope retains disagreement')

    def estimate_universe(self, universe: dict) -> dict:
        section=dict(version=INPUT_VERSION,registry_version=REGISTRY_VERSION,players={})
        legacy = _trait_index(universe.get('traits', []))
        for player in sorted(universe['players'],key=lambda p:p['id']):
            if player['id'] in section['players']:
                raise ValueError('Duplicate canonical player ID')
            section['players'][player['id']]=self.estimate_player_inputs(
                player, legacy.get(player['id'], self.legacy.get(player['id'], {}))).to_dict()
        validate_input_section(section)
        return section


def _plain(value: Any) -> dict:
    return asdict(value) if is_dataclass(value) else dict(value)


GENERATED_METHOD = 'generated_real_input_neighbors_v1'
GENERATED_INPUTS_PATH = 'data/canonical/player_inputs_2026_27.json'


def _fictional_player(player: dict) -> bool:
    """Use explicit generator identities, never a low evidence count or rank.

    rookie_player_record also labels the *real* 2026 class generated_rookie.
    That class must retain the evidence path, including after signing.
    Real college prospects in the 2027-2029 classes deliberately take the generated
    path (same slot-anchored scale as their generated classmates); their college
    profile then informs the inputs it speaks to (college_profile.inputs).
    """
    if player.get('league') == 'generated':
        return True
    kind = str(player.get('source_kind') or '')
    if kind == 'generated_rookie' and str(player.get('draft_year')) == '2026':
        return False
    return kind.startswith('generated_') or str(player.get('id', '')).startswith('generated_player_')


def _generated_detail(player: dict, key: str) -> float:
    """Stable [-1, 1] detail; independent of traversal, Python hash and engine RNG."""
    seed = [GENERATED_METHOD, str(player['id']), player.get('seed'), key]
    digest = hashlib.sha256(canonical_json(seed).encode()).digest()
    return 2 * int.from_bytes(digest[:8], 'big') / (2**64 - 1) - 1


@lru_cache(maxsize=1)
def _generated_reference(root: str) -> dict[str, tuple]:
    """Small numeric calibration table, loaded lazily from existing real inputs.

    No draft, adapter, display-rating or simulation outcomes are fitted here.
    current_ability is the canonical real-player ability coordinate; the linked
    legacy summaries only select the shape *within* that ability/position.
    """
    root = Path(root)
    universe = json.loads((root / UNIVERSE_PATH).read_text())
    path = root / GENERATED_INPUTS_PATH
    if path.exists():
        with path.open() as stream:
            documents = json.load(stream)['players']
    else:
        with gzip.open(str(path) + '.gz', 'rt') as stream:
            documents = json.load(stream)['players']
    traits = _trait_index(universe['traits'])
    reference = {iid: [] for iid in DEFINITIONS}
    for player in sorted(universe['players'], key=lambda p: p['id']):
        pid = player['id']
        ability = _get(player, 'current_ability')
        if _fictional_player(player) or pid not in documents or ability is None or not traits.get(pid):
            continue
        inputs = documents[pid]['inputs']
        for iid, record in inputs.items():
            scalar = scalar_value(record)
            if scalar is None:
                continue
            links = _LEGACY_PRIOR_LINKS.get(iid, ('passing_reads', 'scheme_iq'))
            shape = _mean(traits[pid].get(k, ability+7) for k in links)
            reference[iid].append((pid, ability, _position(player), shape, scalar))
    if not reference['S01']:
        raise ValueError('Generated players require real-player input calibration records')
    return {iid: tuple(rows) for iid, rows in reference.items()}


def _generated_player_inputs(player: dict, traits: Any) -> PlayerInputs:
    # Save stats, team changes and coach minutes are not generator definitions.
    # ratings_model's outer cache includes those fields; keep this bounded cache
    # on just the actual definition so routine save rebuilds do not refit skills.
    rows = traits
    pid = str(player['id'])
    if traits is not None and not isinstance(traits, Mapping):
        rows = [_plain(t) for t in traits]
        rows = [t for t in rows if t.get('prospect_id', pid) == pid]
    values = _trait_values(rows, pid)
    keys = ('id', 'seed', 'source_kind', 'source_ids', 'position', 'archetype',
            'primary_off_role', 'secondary_off_role', 'current_ability', 'potential',
            'height_inches', 'weight_lbs', 'wingspan_inches', 'college_profile')
    definition = {k: player[k] for k in keys if k in player}
    return _generated_definition_inputs(canonical_json(definition), canonical_json(values))


@lru_cache(maxsize=256)
def _generated_definition_inputs(player_json: str, traits_json: str) -> PlayerInputs:
    """Generator definitions are truth for fictional people, not weak evidence.

    For each scalar skill, interpolate the 24 nearest real input records in
    current ability (8-point bandwidth), linked trait shape (10 points), and
    position family (squared-distance penalty 2). Weights are exp(-distance/2).
    Unspecified detail is 12% of local SD times stable per-input variation.
    Body dimensions stay in native units; tendencies describe generated choices,
    separately from ability. Potential remains part of the generator definition;
    there is no extra potential bonus in this mapping. Constants specify
    smoothing, not display OVR targets.
    """
    from .resource_paths import game_resource_root

    player = json.loads(player_json)
    values = json.loads(traits_json)
    pid = str(player['id'])
    archetype = str(player.get('archetype') or player.get('primary_off_role') or '')
    ability = _get(player, 'current_ability')
    if ability is None:
        # Replacement generator omits ability; the supplied legacy definition
        # uses the same mean-minus-seven coordinate as real canonical players.
        ability = _mean(values.values()) - 7 if values else 40.0
    potential = _get(player, 'potential')
    potential = ability if potential is None else potential
    if 'shooting_range' not in values:
        from .draft import infer_trait_values, nba_trait_values_from_prospect

        broad = infer_trait_values(str(player.get('position') or ''), archetype, {},
                                   _get(player, 'height_inches'))
        broad = {k: values.get(k, v + 4 * _generated_detail(player, k)) for k, v in broad.items()}
        values = nba_trait_values_from_prospect(broad, ability, potential,
                    str(player.get('position') or ''), archetype,
                    talent_model='src_talent_balance_v2' in player.get('source_ids', []))
    reference = _generated_reference(str(game_resource_root()))
    # Real college prospects (draft classes 2027-2029): fitted college -> NBA estimates for the inputs college
    # production speaks to, {input_id: [entry value, weight]} (see real_prospects.input_targets).
    college = ((player.get('college_profile') or {}).get('inputs')) or {}
    physicals = _physical_inputs(player, False)
    tendencies = _tendency_inputs(player, False)
    position = _position(player)
    records = {}
    definition = dict(player_id=pid, current_ability=ability, potential=potential,
                      archetype=archetype, traits=values, height_inches=player.get('height_inches'),
                      weight_lbs=player.get('weight_lbs'), source_kind=player.get('source_kind'),
                      source_ids=player.get('source_ids', []))
    for iid, spec in DEFINITIONS.items():
        selected = []
        if spec['kind'] == 'grade' or iid in ('P05', 'P06', 'P07', 'P08', 'P09', 'P10', 'P11', 'P12'):
            links = _LEGACY_PRIOR_LINKS.get(iid, ('passing_reads', 'scheme_iq'))
            target = _mean(values.get(k, ability + 7) for k in links)
            candidates = []
            for rid, ca, pos, shape, scalar in reference[iid]:
                distance = ((ca - ability) / 8)**2 + ((shape - target) / 10)**2 + 2 * (pos != position)
                candidates.append((distance, rid, scalar))
            nearest = sorted(candidates)[:24]
            # Subtract minimum for stable weights even for out-of-support talent.
            weighted = [(math.exp(-(d - nearest[0][0]) / 2), rid, v) for d, rid, v in nearest]
            total = sum(w for w, _, _ in weighted)
            center = sum(w * v for w, _, v in weighted) / total
            sd = math.sqrt(sum(w * (v - center)**2 for w, _, v in weighted) / total)
            detail = .12 * sd * _generated_detail(player, iid)
            # Smooth grade rescaling keeps generated detail inside the scale;
            # there is no clipping or mass at the upper endpoint.
            scalar = (100 * _probability(_logit(center / 100) + detail / 25)
                      if iid != 'P10' and 0 < center < 100 else center + detail)
            if iid in college:
                target, weight = college[iid]
                scalar = _soft_grade_bounds((1 - weight) * scalar + weight * float(target))
            selected = [dict(player_id=rid, weight=round(w / total, 8)) for w, rid, _ in weighted]
            if spec['kind'] == 'grade':
                record = _grade_record(scalar, max(8, sd), [], scale=FT_SCALE if iid == 'S07' else TECHNIQUE_SCALE)
            else:
                record = physicals[iid]
                if iid == 'P10':
                    m = record['value']['measurements'][0]
                    m.update(value=round(scalar, 6), interval=[round(max(.001, scalar-20), 6), round(scalar+20, 6)],
                             protocol='fictional generator; real-input calibrated jump definition')
                    record['uncertainty']['notes'] = canonical_json(dict(interval=m['interval'])).strip()
                else:
                    record['value']['display_grade']['grade'] = round(scalar, 6)
                    record['uncertainty']['notes'] = canonical_json(dict(interval=_bounded_band(scalar, 15))).strip()
        elif iid.startswith('P'):
            record = physicals[iid]
        else:
            record = tendencies[iid]
            # These are fictional choices, so no observed opportunity count is
            # required. Link *relative* profile, not overall talent, to choices.
            links = _LEGACY_PRIOR_LINKS.get(iid)
            if iid == 'T08':
                # Involvement tracks ability in the real league (better players finish and create more
                # possessions): start from the same real neighbors as the skills, then let the profile tilt it.
                record['value']['probability'] = _generated_involvement(
                    reference['T08'], ability, _mean(values.get(k, ability+7) for k in links), position)
            if links:
                residual = (_mean(values.get(k, ability+7) for k in links) - _mean(values.values())) / 20
                old = record['value']['probability']
                probability = _probability(_logit(old) + .5 * residual + .10 * _generated_detail(player, iid))
                if iid in college:
                    target, weight = college[iid]
                    probability = (1 - weight) * probability + weight * _estimator_involvement(float(target))
                record['value']['probability'] = round(probability, 8)
                record['uncertainty']['notes'] = canonical_json(dict(interval=_bounded_band(probability, .25, 1))).strip()
            else:
                probs = record['value']['rows'][0]['probabilities']
                for outcome, (keys, _) in _DISTRIBUTION_PRIOR_LINKS[iid].items():
                    residual = (_mean(values.get(k, ability+7) for k in keys) - _mean(values.values())) / 20
                    probs[outcome] *= math.exp(.5 * residual + .10 * _generated_detail(player, iid+outcome))
                total = sum(probs.values())
                record['value']['rows'][0]['probabilities'] = {k: v/total for k, v in probs.items()}
                record['uncertainty']['notes'] = canonical_json(dict(intervals={k: _bounded_band(v/total, .25, 1) for k,v in probs.items()})).strip()
        notes = uncertainty_details(record)
        notes.update(basis='fictional generator definition; not an observation of a real person',
                     limitations='real-input interpolation and unspecified detail are modeling assumptions',
                     potential_use='generator conversion and future ceiling; no extra mapping bonus')
        record.update(reason='generated', evidence=[_evidence('draft_model', GENERATED_METHOD, 'generated:'+pid,
            notes=canonical_json(dict(definition=definition, reference=GENERATED_INPUTS_PATH,
                                      neighbors=selected)).strip())])
        record['uncertainty'].update(confidence='medium', notes=canonical_json(notes).strip())
        records[iid] = record
    return PlayerInputs(dict(version=INPUT_VERSION, registry_version=REGISTRY_VERSION,
                             player_id=pid, inputs=records))


@lru_cache(maxsize=4)
def _involvement_scale(root: str) -> dict | None:
    from .bbi_evidence import load_scale_map
    return (load_scale_map(Path(root)) or {}).get('T08')


def _generated_involvement(reference: tuple, ability: float, shape: float, position: str) -> float:
    """Involvement (T08) for a fictional player from the 24 nearest real players (same distance as the skills).

    Real inputs hold measured true usage; generated players are later placed on that measured scale by rank
    (bbi_evidence.map_tendency_inputs), so the neighbor value is returned on the estimator's scale."""
    candidates = sorted((((ca - ability) / 8)**2 + ((s - shape) / 10)**2 + 2 * (pos != position), v)
                        for _, ca, pos, s, v in reference)[:24]
    weights = [(math.exp(-(d - candidates[0][0]) / 2), v) for d, v in candidates]
    measured = sum(w * v for w, v in weights) / sum(w for w, _ in weights)
    from .bbi_evidence import map_to_measured
    from .resource_paths import game_resource_root
    scale = _involvement_scale(str(game_resource_root()))
    if not scale:
        return round(measured, 8)
    inverse = {'source': scale['target'], 'target': scale['source']}
    return round(map_to_measured(inverse, measured), 8)


def _soft_grade_bounds(value: float, margin: float = 5.0) -> float:
    """Keep a blended grade inside (0, 100) smoothly: unchanged between 5 and 95, eased (never clipped) beyond."""
    if value > 100 - margin:
        return 100 - margin + margin * math.tanh((value - (100 - margin)) / margin)
    if value < margin:
        return margin - margin * math.tanh((margin - value) / margin)
    return value


def _estimator_involvement(measured: float) -> float:
    """A measured-scale involvement (real players' inputs) placed on the estimator's scale, like the neighbours'."""
    from .bbi_evidence import map_to_measured
    from .resource_paths import game_resource_root
    scale = _involvement_scale(str(game_resource_root()))
    if not scale:
        return measured
    return map_to_measured({'source': scale['target'], 'target': scale['source']}, measured)


def _blend_value(old: dict, new: dict, weight: float) -> dict:
    if 'grade' in old:
        return dict(grade=round((1-weight)*old['grade']+weight*new['grade'],6),scale=old['scale'])
    if 'probability' in old:
        if old['reference_conditions']!=new['reference_conditions']:
            raise ValueError('Cannot combine different reference opportunities')
        return dict(probability=round((1-weight)*old['probability']+weight*new['probability'],8),
                    reference_conditions=old['reference_conditions'])
    if 'rows' in old:
        if (old['reference_conditions']!=new['reference_conditions'] or
            old.get('spatial_reference')!=new.get('spatial_reference') or
            [r['condition'] for r in old['rows']]!=[r['condition'] for r in new['rows']]):
            raise ValueError('Cannot combine different conditional distribution opportunities')
        result=json.loads(json.dumps(old))
        for result_row,old_row,new_row in zip(result['rows'],old['rows'],new['rows']):
            a,b=old_row['probabilities'],new_row['probabilities']
            if set(a)!=set(b):
                raise ValueError('Incompatible distribution outcomes')
            result_row['probabilities']={k:(1-weight)*a[k]+weight*b[k] for k in a}
        return result
    # Physical evidence is already in native units. Match metric/unit exactly;
    # protocol may change when replacing an inference with an actual test.
    result=json.loads(json.dumps(old))
    if new.get('measurements'):
        old_measures={(m['metric'],m['unit']):m for m in old['measurements']}
        for measure in new['measurements']:
            prior=old_measures.get((measure['metric'],measure['unit']))
            if prior is None:
                if not old['measurements']:
                    # First native-unit observation has no commensurate prior.
                    old_measures[(measure['metric'],measure['unit'])]=json.loads(json.dumps(measure))
                    result.pop('display_grade',None)
                    continue
                raise ValueError('Physical evidence must match the declared metric and unit')
            mean=(1-weight)*prior['value']+weight*measure['value']
            interval=[min(prior.get('interval',[prior['value']]*2)[0],measure.get('interval',[measure['value']]*2)[0]),
                      max(prior.get('interval',[prior['value']]*2)[1],measure.get('interval',[measure['value']]*2)[1])]
            prior.update(value=round(mean,6),interval=interval,protocol='source evidence shrunk against physical prior')
        result['measurements']=list(old_measures.values())
    if 'display_grade' in new:
        if old.get('display_grade',{}).get('scale')!=new['display_grade']['scale']:
            raise ValueError('Physical display grade requires the same declared scale')
        result['display_grade']=_blend_value(old['display_grade'],new['display_grade'],weight)
    return result


def _prospect_trait_priors(records: dict, prospect: dict, traits: Any, scouting: Any = None) -> None:
    """Broad draft traits condition uncertain priors, never renamed measurements."""
    if isinstance(traits, Mapping):
        values={k: _number(v) for k,v in traits.items()}
    else:
        rows=[_plain(r) for r in (traits or [])]
        values={r['trait_key']:_number(r['value']) for r in rows
                if r.get('prospect_id',prospect['id'])==prospect['id']}
    reported=set()
    if isinstance(scouting,Mapping) or is_dataclass(scouting):
        report=_plain(scouting)
        for key,band in (report.get('trait_estimates') or {}).items():
            if values.get(key) is None and isinstance(band,Mapping):
                mid=_number(band.get('mid'))
                if mid is not None:
                    values[key]=mid
                    reported.add(key)
    mapping={
        'shooting':['S01','S02','S03','S04','S05','S06'],
        'shot_creation':['S16','S18','S19'],
        'passing':[k for k in records if k.startswith('F')],
        'rebounding':['S29','S30','S31','S32'],
        'rim_protection':['S36','S37'],
        'defense':['S33','S35','S38','S39','S40'],
        'feel':['S20','S28','S44'],
    }
    for broad,ids in mapping.items():
        raw=values.get(broad)
        if raw is None:
            continue
        for iid in ids:
            old=records[iid]
            # Very weak prior conditioning in log-odds space, no hard bounds.
            mean=100*_probability(_logit(old['value']['grade']/100)+.15*(raw-50)/20)
            records[iid]=_grade_record(mean,40,[*old['evidence'],_evidence(
                'prospect:broad_scouting_prior' if broad in reported else 'prospect:broad_trait_prior',
                'broad generated/scouted trait conditions a prior, not isolated technique',
                'prospect_broad_traits',notes=f'{broad}={raw}; legacy dimensions not relabeled; uncertainty remains wide')],
                prior=True,basis='broad draft profile conditions a technique prior; no independent technique observation')


def estimate_prospect_inputs(prospect: Any, traits: Any = None, scouting: Any = None) -> PlayerInputs:
    """Generated dataclass/dict or real prospect → full validated PlayerInputs.

    Fictional definitions use the generated path, including their broad traits.
    For real prospects, ranks, potential and broad traits are NOT technique evidence.
    Real `public_stats.per_game` FT/3P attempts and percentages support weak,
    competition-uncertain current shooting estimates. `scouting` may provide a
    list of InputEvidence in approved definitions. Existing broad scouting reports
    can condition missing broad-trait priors, never replace supplied true traits
    or become independent technique observations. This function never wires draft.py.
    """
    p=_plain(prospect)
    if _fictional_player(p):
        return _generated_player_inputs(p, traits)
    extra=list(scouting) if isinstance(scouting,(list,tuple)) and all(isinstance(r,InputEvidence) for r in scouting) else []
    model=InputEstimator()
    result=model.estimate_player_inputs(p,traits,prospect=True).to_dict()
    _prospect_trait_priors(result['inputs'], p, traits, scouting)
    stats=p.get('public_stats') or {}
    # Public real-prospect schema inspected in the retained draft cache.
    pergame=stats.get('per_game') or stats.get('averages') or {}
    games=_get(stats,'games','gp') or _get(pergame,'games','gp') or 0
    for iid,pct_key,attempt_key in [('S07','ft_pct','fta'),('S01','fg3_pct','fg3a')]:
        rate=_get(pergame,pct_key)
        attempts=_get(pergame,attempt_key)
        if rate is None or attempts is None or games<=0 or attempts<=0:
            continue
        rate=rate/100 if rate>1 else rate
        if not 0<=rate<=1:
            continue
        old=result['inputs'][iid]
        n=games*attempts*.25
        pos=_position(p)
        prior=({'guard':.79,'wing':.76,'big':.70}[pos] if iid=='S07' else .34)
        posterior=(n*rate+150*prior)/(n+150)
        target=100*posterior if iid=='S07' else _soft_grade(posterior,.34,.11)
        result['inputs'][iid]=_grade_record(target,32,[*old['evidence'],_evidence(
            'prospect:public_stats','competition-uncertain shooting; quarter effective attempt exposure',
            'prospect_shooting',exposure=dict(value=n,unit='effective_attempts'),
            notes='percentages from public per-game stats; not NBA-equivalent competition')],
            basis='pre-NBA shooting evidence; broad competition and role uncertainty',
            scale=FT_SCALE if iid=='S07' else TECHNIQUE_SCALE)
    ast36=_get(stats.get('per_36') or {},'ast')
    if ast36 is not None and ast36>=0:
        iid='F01.recognition'
        old=result['inputs'][iid]
        target=_soft_grade(ast36,2.5,5)
        result['inputs'][iid]=_grade_record(.8*old['value']['grade']+.2*target,38,
            [*old['evidence'],_evidence('prospect:public_stats','weak per36 assist-creation constraint, not read success',
             'prospect_creation',notes=f'ast_per36={ast36}; no retained attempt count; competition/teammates confounded')],
            basis='reported pre-NBA assist creation weakly constrains connector recognition; delivery remains separate')
    # Explicit dimension evidence follows priors and public data.
    model._apply_additional(result['inputs'],extra)
    return PlayerInputs(result)


def load_reference_cells(root: str | Path) -> dict:
    """Newest estimated SOURCE cell; never scenarios/operational completions.

    Sort by date in filename then filename for same-day ties. Research packet
    revision dates, not mtime, drive precedence. Unknown cells do not erase older
    estimates. Proposed source section is intentional in the Nov15 packet;
    operational section has synthetic completions and is explicitly excluded.
    """
    cells={}
    paths=sorted((Path(root)/PACKET_PATH).glob('*INPUTS_*.json'),
                 key=lambda p:(re.search(r'\d{4}_\d{2}_\d{2}',p.name).group(),p.name))
    for path in paths:
        data=json.loads(path.read_text())
        section=data.get('proposed_source_input_section',data.get('player_input_section',{}))
        for pid,doc in sorted(section.get('players',{}).items()):
            for iid,record in sorted(doc['inputs'].items()):
                if record['status']=='estimated' and iid in DEFINITIONS:
                    cells[(pid,iid)]=dict(record=record,packet=str(path.relative_to(root)))
    return cells


def scalar_value(record: dict) -> float | None:
    value=record['value']
    if 'grade' in value:
        return value['grade']
    if value.get('measurements'):
        return value['measurements'][0]['value']
    if 'display_grade' in value:
        return value['display_grade']['grade']
    if 'probability' in value:
        return value['probability']
    return None


def validation_comparison(section: dict, references: Mapping, baseline: dict | None = None) -> dict:
    """Report raw native-unit differences; unlike units never pooled together."""
    by_input={iid:[] for iid in DEFINITIONS}
    differences=[]
    for (pid,iid),entry in sorted(references.items()):
        if pid not in section['players']:
            continue
        actual=section['players'][pid]['inputs'][iid]
        hand=scalar_value(entry['record'])
        estimate=scalar_value(actual)
        if hand is None or estimate is None:
            continue
        # Geometry comparisons use first native-unit measurement, not display grades.
        av,rv=actual['value'],entry['record']['value']
        if bool(av.get('measurements'))!=bool(rv.get('measurements')):
            continue
        if ('display_grade' in av and 'display_grade' in rv
            and av['display_grade']['scale']!=rv['display_grade']['scale']):
            continue  # no calibrated mapping between physical descriptor scales
        if av.get('measurements') and av['measurements'][0]['unit']!=rv['measurements'][0]['unit']:
            continue
        interval=uncertainty_details(actual)['interval']
        error=abs(estimate-hand)
        base_error=None
        base_inside=None
        if baseline:
            baseline_record=baseline['players'][pid]['inputs'][iid]
            base_error=abs(scalar_value(baseline_record)-hand)
            base_band=uncertainty_details(baseline_record)['interval']
            base_inside=base_band[0]<=hand<=base_band[1]
        row=dict(player_id=pid,input_id=iid,estimate=estimate,reference=hand,
                 absolute_difference=error,inside=interval[0]<=hand<=interval[1],
                 baseline_absolute_difference=base_error,baseline_inside=base_inside,packet=entry['packet'],
                 explanation=uncertainty_details(actual)['basis'])
        by_input[iid].append(row)
        if DEFINITIONS[iid]['kind']=='grade':
            differences.append(row)
    table=[]
    for iid,rows in by_input.items():
        table.append(dict(input_id=iid,name=DEFINITIONS[iid]['name'],count=len(rows),
            mean_absolute_difference=sum(r['absolute_difference'] for r in rows)/len(rows) if rows else None,
            inside_fraction=sum(r['inside'] for r in rows)/len(rows) if rows else None,
            baseline_mean_absolute_difference=sum(r['baseline_absolute_difference'] for r in rows)/len(rows) if rows and baseline else None,
            baseline_inside_fraction=sum(r['baseline_inside'] for r in rows)/len(rows) if rows and baseline else None))
    return dict(reference_players=len({pid for pid,_ in references}),reference_cells=len(references),
                comparable_cells=sum(len(r) for r in by_input.values()),
                excluded_cells=len(references)-sum(len(r) for r in by_input.values()),table=table,
                biggest_disagreements=sorted(differences,key=lambda r:(-r['absolute_difference'],r['player_id'],r['input_id']))[:10])


def coverage_counts(section: dict) -> dict:
    counts={iid:dict(estimated=0,prior=0) for iid in DEFINITIONS}
    for player in section['players'].values():
        for iid,record in player['inputs'].items():
            counts[iid][estimation_status(record)]+=1
    return counts


def source_join_audit(universe: dict, estimator: InputEstimator, minimum_minutes: float = 1000) -> dict:
    """Audit retained snapshots separately, never join their denominators.

    Eligibility is at least minimum_minutes in ANY retained 2025-26 snapshot or
    the unique 2025-26 career row. This catches a missing source rather than
    making that missing source the only way to enter the audit cohort.
    """
    rows=[]
    for p in sorted(universe['players'],key=lambda r:r['id']):
        key=_normalize(p.get('name',''))
        sources={}
        for index,source in [(estimator.skills,SKILL_PATH),(estimator.stats,STATS_PATH)]:
            mp=_get(index.get(key,{}),'MP')
            if mp is not None and mp>=0:
                sources[source]=mp
        career=estimator.careers.get(str(p.get('espn_player_id') or ''),{})
        latest=[r for r in career.get('seasons',[]) if r.get('season')=='2025-26']
        if len(latest)==1:
            mp=_get(latest[0],'minutes')
            if mp is not None and mp>=0:
                sources[CAREER_PATH]=mp
        minutes=max(sources.values(),default=0)
        rows.append(dict(player_id=p['id'],name=p['name'],minutes=minutes,minute_sources=sources,
                         rotation=minutes>=minimum_minutes,skill_joined=key in estimator.skills,
                         stats_joined=key in estimator.stats,
                         career_joined=str(p.get('espn_player_id') or '') in estimator.careers))
    return dict(minimum_minutes=minimum_minutes,players=rows,
        rotation_players=sum(r['rotation'] for r in rows),
        unmatched_skills=[r for r in rows if r['rotation'] and not r['skill_joined']],
        unmatched_stats=[r for r in rows if r['rotation'] and not r['stats_joined']])


def rotation_input_spread(section: dict, audit: dict) -> list[dict]:
    """Population SD in native units; distribution outcomes are all shown.

    Report flags are descriptive, NEVER used to tune estimates. Near zero means
    SD <1 grade point, <.5 cm/kg, or <.01 probability. No fake jitter is added.
    """
    players=[section['players'][r['player_id']] for r in audit['players']
             if r['rotation'] and r['player_id'] in section['players']]
    result=[]
    for iid,definition in DEFINITIONS.items():
        columns={}
        threshold=.01 if definition['kind'] in ('distribution','propensity') else 1.0
        for p in players:
            record=p['inputs'][iid]
            value=record['value']
            if definition['kind']=='distribution':
                for row in value['rows']:
                    for outcome,probability in row['probabilities'].items():
                        columns.setdefault(row['condition']+'/'+outcome,[]).append(probability)
            else:
                scalar=scalar_value(record)
                if scalar is not None:
                    unit=(value['measurements'][0]['unit'] if value.get('measurements') else
                          'probability' if definition['kind']=='propensity' else 'grade')
                    columns.setdefault(unit,[]).append(scalar)
                    if unit in ('cm','kg'):
                        threshold=.5
        deviations={k:statistics.pstdev(v) for k,v in sorted(columns.items())}
        flagged=[k for k,v in deviations.items() if v<threshold]
        result.append(dict(input_id=iid,name=definition['name'],count=len(players),
                           standard_deviations=deviations,near_zero=flagged,threshold=threshold))
    return result
