"""Evidence-only population of the approved 94 inputs (no simulation imports).

Wire contract: a normal player_model input section, containing normal PlayerInputs
records. Until the coordinator approves native status='prior', status='estimated'
plus reason='prior' means a usable prior, NOT direct evidence of this input. Use
estimation_status(), never status alone, when displaying evidence coverage.
Uncertainty.notes contains JSON plausibility intervals, not calibrated CIs.

Fixed anchors and shrinkage constants below are basketball judgments, not fits to
engine outcomes or to the 32 research players. Legacy traits only weakly condition
explicit priors; they never become measured raw skills. New sources plug in via InputEvidence, keyed by input
ID, with provenance, sample exposure, and source-correlation group. No I/O occurs
on import; no random numbers or wall-clock dates are used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import json
import math
from pathlib import Path
import re
import statistics
import unicodedata
from typing import Any, Mapping

from .player_model import INPUT_VERSION, PlayerInputs, validate_input_section
from .player_model_registry import REGISTRY_VERSION, definition_registry

METHOD_VERSION = 'e2_evidence_estimator_v3_conditioned_priors_observed_tendencies'
TECHNIQUE_SCALE = 'e2_technique_reference_v1_50_functional_75_strong_90_exceptional'
FT_SCALE = 'research_FT_conversion_percent_proxy_v1'
DEFINITIONS = {r['id']: r for r in definition_registry()['inputs']}
UNIVERSE_PATH = 'data/canonical/universe_2026_27_offseason.json'
SKILL_PATH = 'Player Stats/player_skill_input_2025_26.json'
STATS_PATH = 'Player Stats/player_stats.json'
CAREER_PATH = 'data/research/player_career_stats.json'
PACKET_PATH = 'docs/ratings-evidence-2026-10-29'
SHOT_ZONE_PATH = 'data/research/shot_chart_reference.json'
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

    def estimate_player_inputs(self, player: Any, traits: Any = None, *, prospect: bool = False) -> PlayerInputs:
        player = _plain(player)
        # Effective legacy summaries may condition priors, never become measurements.
        player_id = str(player['id'])
        pos = _position(player)
        records = _physical_inputs(player, prospect)
        records.update(_tendency_inputs(player, prospect))
        for iid in DEFINITIONS:
            if DEFINITIONS[iid]['kind'] == 'grade':
                p = _prior_grade(iid,player,prospect)
                if iid == 'S07':
                    p = {'guard':79,'wing':76,'big':70}[pos] - (3 if prospect else 0)
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
        self._apply_additional(records, self.additional.get(player_id, []))
        document = dict(version=INPUT_VERSION, registry_version=REGISTRY_VERSION,
                        player_id=player_id, inputs=records)
        return PlayerInputs(document)

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

    Current ranks, potential and legacy broad traits are NOT technique evidence.
    Generated players without observations receive explicit broad role priors.
    Real `public_stats.per_game` FT/3P attempts and percentages support weak,
    competition-uncertain current shooting estimates. `scouting` may provide a
    list of InputEvidence in approved definitions. Existing broad scouting reports
    can condition missing broad-trait priors, never replace supplied true traits
    or become independent technique observations. This function never wires draft.py.
    """
    p=_plain(prospect)
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
