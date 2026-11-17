"""Prospect presentation using the same skill conversion as signed rookies."""
from datetime import date, timedelta
from hashlib import sha256
from random import Random

from .career_stats import season_summary


def prospect_rating_projection(canonical, prospect, report, coverage, save=None):
    from .draft import draft_traits_for_prospect, generated_class_for_context, primary_position_label, rookie_rotation_projection, rookie_trait_records
    from .save import player_display_attribute_summary, presentation_rating_value
    from .talent import modeled

    save = save or {}
    identity = prospect.get('id') or prospect.get('prospect_id')
    full = next((p for p in canonical.get('draft_prospects', []) if p.get('id') == identity), {})
    saved_class = (save.get('draft_state') or {}).get('draft') or {}
    pending = next((p for p in saved_class.get('draft_prospects', []) if p.get('id') == identity), {})
    pending = pending or next((p.get('prospect') or {} for p in save.get('pending_draft_selections', [])
                    if (p.get('prospect') or {}).get('id') == identity), {})
    generated = {}
    if not full and not pending and prospect.get('league') == 'generated':
        generated = generated_class_for_context(canonical, str(prospect['draft_year']))
        full = next((p for p in generated['draft_prospects'] if p['id'] == identity), {})
    # Board payloads omit model markers and public-stat priors; recover the
    # authoritative prospect before converting it, including legacy saves.
    full = {**full, **prospect, **pending}
    projected = dict(full)
    if coverage < 100:
        for field, estimate in (('current_ability', 'estimated_current'), ('potential', 'estimated_potential')):
            mid = (report.get(estimate) or {}).get('mid')
            if mid is not None:
                projected[field] = float(mid)
    true_traits = draft_traits_for_prospect(save, identity) or [
        row for row in [*canonical.get('draft_prospect_traits', []), *generated.get('draft_prospect_traits', [])]
        if row.get('prospect_id') == identity
    ]
    estimates = report.get('trait_estimates') or {}
    traits = true_traits
    if coverage < 100 and estimates:
        traits = [{'trait_key': key, 'value': value['mid']} for key, value in estimates.items()
                  if isinstance(value, dict) and value.get('mid') is not None]
    selected = next((row for row in save.get('incoming_rookies', []) if row.get('prospect_id') == identity), {})
    slot = int(selected.get('overall_pick') or full.get('rank') or 60)
    minutes, _ = rookie_rotation_projection(projected, slot, talent_model=modeled(projected))
    player = {'id': f'prospect-preview:{identity}', 'position': primary_position_label(full.get('position')),
              'minutes_projection': minutes, 'source_ids': projected.get('source_ids', [])}
    context = {'meta': canonical.get('meta', {}), 'players': [player],
               'traits': rookie_trait_records(player, projected, traits)}
    ratings = player_display_attribute_summary(context, player['id'])
    signed = next((row for row in canonical.get('players', []) if row.get('id') == selected.get('player_id')), None)
    if signed:
        ratings = player_display_attribute_summary(canonical, signed['id'])
    ability = float(projected.get('current_ability') or 0)
    potential = float(projected.get('potential') or ability)
    return {'now': ratings['overall'], 'ratings': ratings,
            'potential': presentation_rating_value(potential),
            'floor': presentation_rating_value(full.get('floor') if full.get('floor') is not None else max(20, ability - 8)),
            'ceiling': presentation_rating_value(full.get('ceiling') if full.get('ceiling') is not None else potential + 7)}


def college_production(prospect):
    identity = str(prospect.get('id') or prospect.get('name') or 'prospect')
    year = int(prospect.get('draft_year') or 2027)
    rng = Random(int.from_bytes(sha256(f'college-v1:{identity}:{year}'.encode()).digest()[:8], 'big'))
    big = str(prospect.get('position') or '') in {'C', 'PF'}
    guard = str(prospect.get('position') or '') in {'PG', 'SG'}
    games = rng.randint(25, 35)
    usage = rng.uniform(.65, 1.3)
    mpg = rng.uniform(22, 35)
    fga = rng.uniform(8, 15) * usage
    three_share = rng.uniform(.05, .35) if big else rng.uniform(.25, .58)
    fg2 = rng.uniform(.47, .64) if big else rng.uniform(.42, .57)
    fg3 = rng.uniform(.26, .43)
    ft = rng.uniform(.58, .89)
    opponents = ['Duke', 'Kentucky', 'Kansas', 'UConn', 'Gonzaga', 'Baylor', 'Houston', 'Arizona', 'UCLA', 'Michigan', 'Alabama', 'Auburn']
    logs = []
    for index in range(games):
        attempts = max(2, round(rng.gauss(fga, 3)))
        threes = min(attempts, max(0, round(rng.gauss(attempts * three_share, 1.5))))
        threes_made = sum(rng.random() < fg3 for _ in range(threes))
        twos_made = sum(rng.random() < fg2 for _ in range(attempts - threes))
        fta = max(0, round(rng.gauss(4 * usage, 2.5)))
        ftm = sum(rng.random() < ft for _ in range(fta))
        row = {
            'date': (date(year - 1, 11, 5) + timedelta(days=round(index * 120 / max(1, games - 1)))).isoformat(),
            'college_opponent': opponents[(index + rng.randrange(len(opponents))) % len(opponents)],
            'minutes': round(min(40, max(10, rng.gauss(mpg, 4))), 1),
            'points': twos_made * 2 + threes_made * 3 + ftm,
            'rebounds': max(0, round(rng.gauss(8 if big else 4, 2.5))),
            'assists': max(0, round(rng.gauss(4.5 if guard else 1.8, 1.8))),
            'steals': max(0, round(rng.gauss(1.3, 1))),
            'blocks': max(0, round(rng.gauss(1.8 if big else .3, .8))),
            'turnovers': max(0, round(rng.gauss(2.5 * usage, 1.3))),
            'fga': attempts, 'fgm': twos_made + threes_made,
            'fg3a': threes, 'fg3m': threes_made, 'fta': fta, 'ftm': ftm,
        }
        row['game_score'] = round(max(0, row['points'] + 1.2 * row['rebounds'] + 1.5 * row['assists'] + 3 * row['steals'] + 3 * row['blocks'] - 1.5 * row['turnovers']), 1)
        logs.append(row)
    fields = ['minutes', 'points', 'rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'fga', 'fgm', 'fg3a', 'fg3m', 'fta', 'ftm']
    totals = {'games': games, **{key: sum(row[key] for row in logs) for key in fields}}
    summary = season_summary(totals, f'{year-1}-{str(year)[-2:]}', games)
    summary['college_team'] = prospect.get('source_team') or 'College'
    return summary, logs
