"""Starting-data repairs for demonstrated NBA rotation players, not career growth."""
from collections import defaultdict
from dataclasses import replace
from statistics import fmean
from typing import Any

from .imported_skill_calibration import number, recent_nba_sample
from .schema import Player, TraitValue
from .utils import clamp

SOURCE_ID = "src_rotation_profile_evidence_v8"
MARKER = "rotation_profile_evidence_v8"
RESTORABLE_KEYS = {'release_speed', 'shooting_range', 'shot_versatility', 'rim_pressure',
                   'handle_pressure', 'passing_reads', 'portability', 'playoff_translation'}


def demonstrated_rotation(player: Player, records: dict[str, Any], year: int) -> dict[str, Any] | None:
    rows = recent_nba_sample(player, records, year)
    if not rows or rows[0]['season'][:4] != str(year-1):
        return None
    latest = rows[0]
    mpg = float(latest['minutes'])/float(latest['games'])
    minutes = sum(float(r['minutes'])*(1 if int(r['season'][:4]) == year-1 else .5) for r in rows)
    if float(latest['games']) < 40 or mpg < 15 or minutes < 1000:
        return None
    return {'weighted_minutes': minutes, 'latest_games': latest['games'], 'latest_mpg': mpg,
            'sample_seasons': [r['season'] for r in rows],
            'source_urls': sorted({r['source_url'] for r in rows})}


def reconciled_prior(trait: TraitValue) -> dict[str, Any] | None:
    c = trait.components
    prior = c.get('league_trait_rating_calibration', {})
    previous, final = number(prior.get('previous_value')), number(prior.get('final_value'))
    preserved = number(c.get('2026_roster_refresh', {}).get('preserved_value'))
    if (previous is None or final is None or preserved is None or max(previous, final, preserved) > 100
            or abs(final-preserved) > .021):
        return None
    if (number(prior.get('csv_rank')) or 0) < 250:
        return None
    return prior


def calibrate_rotation_profiles(
    players: list[Player], traits: list[TraitValue], career_data: dict[str, Any], year: int,
) -> tuple[list[TraitValue], dict[str, Any]]:
    by_player: dict[str, list[TraitValue]] = defaultdict(list)
    for t in traits:
        by_player[t.player_id].append(t)
    replacements = {}
    report = {'policy': MARKER, 'players': [], 'examined_players': len(players),
              'notes': 'Reduce a contradictory ranking prior, not invent NBA skills or guarantee a roster role.'}
    for player in players:
        ts = by_player[player.id]
        if (player.draft_year or 0) >= year or any(
            k in t.components for t in ts for k in ('manual_calibration', 'imported_rookie_prior')
        ):
            continue
        evidence = demonstrated_rotation(player, career_data.get('players', {}), year)
        if not evidence:
            continue
        priors = [p for t in ts if (p := reconciled_prior(t)) is not None]
        depression = fmean(float(p['previous_value'])-float(p['final_value']) for p in priors) if priors else 0
        conflict = len(priors) >= 8 and depression >= 8
        changes = {}
        for trait in ts:
            c = trait.components
            if MARKER in c:
                continue
            target, reason, detail = trait.value, None, {}
            prior = reconciled_prior(trait)
            if conflict and prior and trait.trait_key in RESTORABLE_KEYS:
                pieces = c.get('components')
                if trait.trait_key == 'shot_versatility':
                    supported = (number(c.get('playtype_count')) or 0) >= 4
                else:
                    supported = (isinstance(pieces, list) and bool(pieces)
                                 and all(v is None or number(v) is not None for v in pieces)
                                 and sum(v is not None for v in pieces)*2 >= len(pieces))
                if supported:
                    # Retain 35% of the historical adjustment. Existing later
                    # corrections survive, and restoration cannot pass the old input.
                    delta = clamp((float(prior['previous_value'])-float(prior['final_value']))*.65, -20, 20)
                    endpoint = float(prior['previous_value'])
                    target = clamp(trait.value+delta, min(trait.value, endpoint), max(trait.value, endpoint))
                    reason = 'contradictory_tail_prior_weight'
                    detail = {'pre_prior_value': endpoint, 'historical_calibrated_value': prior['final_value'],
                              'remaining_adjustment_fraction': .35, 'profile_mean_depression': round(depression, 3)}
            if trait.trait_key == 'stamina_cardio' and trait.value < 40:
                # Conditioning is not games available. Use sustained workload,
                # not the percentile of last year's total minutes; health stays separate.
                age_penalty = clamp((float(player.age or 30)-30)*1.3, 0, 16)
                workload_prior = clamp(45+.7*evidence['latest_mpg']-age_penalty, 40, 73)
                target = trait.value+min(30, max(0, workload_prior-trait.value)*.65)
                reason = 'demonstrated_workload_not_availability_percentile'
                detail = {'workload_prior': workload_prior, 'age_penalty': age_penalty}
            target = round(clamp(target), 2)
            if abs(target-trait.value) < 1:
                continue
            info = {'previous': trait.value, 'corrected': target, 'delta': round(target-trait.value, 2),
                    'reason': reason, **evidence, **detail}
            replacements[(player.id, trait.trait_key)] = replace(
                trait, value=target, confidence=min(trait.confidence, .58),
                source_kind=f'{trait.source_kind}_rotation_profile_v8',
                source_ids=list(dict.fromkeys([*trait.source_ids, SOURCE_ID])),
                components={**c, MARKER: info},
                notes=f'{trait.notes} V8 demonstrated-role input correction; medicals and career rules unchanged.')
            changes[trait.trait_key] = info
        if changes:
            report['players'].append({'player_id': player.id, 'name': player.name, 'trait_changes': changes})
    report.update(adjusted_player_count=len(report['players']), adjusted_trait_count=len(replacements))
    return [replacements.get((t.player_id, t.trait_key), t) for t in traits], report
