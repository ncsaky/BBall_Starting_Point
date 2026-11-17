"""Versioned offensive roles and shot diets; estimates, not additional potential."""
import math
from typing import Any

from .utils import clamp, normalize_name

MODEL_VERSION = 1
SOURCE_ID = 'src_offensive_roles_v1'
VERSION = '2026-10-27-interior-offense-v9'
FACETS = ('post_creation', 'assisted_finishing', 'screening', 'offensive_rebounding')


def enabled(canonical: dict[str, Any]) -> bool:
    return canonical.get('meta', {}).get('offense_model_version') == MODEL_VERSION


def number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def build_priors(players, traits, careers, raw_players, year=2026):
    """Freeze identity-checked NBA evidence at ingestion; never read files in a game."""
    by_player = {}
    for t in traits:
        by_player.setdefault(t['player_id'], {})[t['trait_key']] = t['value']
    raw = {normalize_name(p['name']): p for p in raw_players}
    priors = {}
    for p in players:
        espn = str(p.get('espn_player_id') or '')
        record = careers.get('players', {}).get(espn, {})
        if not espn or str(record.get('espn_player_id')) != espn:
            continue
        rows = []
        for row in record.get('seasons', []):
            season = str(row.get('season', ''))
            if not season[:4].isdigit() or not year-2 <= int(season[:4]) < year:
                continue
            games, minutes = number(row.get('games')), number(row.get('minutes'))
            if (not games or not minutes or minutes > games*60
                    or f'/basketball/nba/athletes/{espn}/' not in str(row.get('source_url', ''))):
                continue
            rows.append((row, 1.0 if int(season[:4]) == year-1 else .5))
        if not rows:
            continue
        def sample(keys):
            usable = [(r, w) for r, w in rows if all(number(r.get(k)) is not None for k in keys)
                      and all(float(r[m]) <= float(r[a]) for m, a in
                              (('fgm', 'fga'), ('fg3m', 'fg3a'), ('ftm', 'fta')) if m in keys and a in keys)]
            minutes = sum(float(r['minutes'])*w for r, w in usable)
            return minutes, {k: sum(float(r[k])*w for r, w in usable) for k in keys}
        profile = {'anchors': by_player.get(p['id'], {}),
                   'source_urls': sorted({r['source_url'] for r, _ in rows}),
                   'seasons': sorted({r['season'] for r, _ in rows}), 'modeled': True}
        minutes, totals = sample(('fg3a', 'fg3m'))
        if minutes >= 200:
            # Volume and accuracy have different uncertainty. Zero attempts are
            # valid evidence of a nonshooting role, not 0% shooting talent.
            profile['three_per36'] = totals['fg3a']*36/minutes
            profile['volume_weight'] = min(.98, minutes/800)
            if totals['fg3a']:
                profile['three_pct'] = (totals['fg3m']+60*.35)/(totals['fg3a']+60)
        minutes, totals = sample(('fga', 'fgm', 'fg3a', 'fg3m'))
        attempts, makes = totals['fga']-totals['fg3a'], totals['fgm']-totals['fg3m']
        if minutes >= 200 and 0 <= makes <= attempts and attempts > 0:
            profile['two_pct'] = (makes+60*.54)/(attempts+60)
            profile['two_weight'] = min(.85, attempts/(attempts+80))
        minutes, totals = sample(('fta', 'ftm'))
        if minutes >= 200 and totals['fta'] > 0:
            profile['ft_pct'] = (totals['ftm']+30*.75)/(totals['fta']+30)
        r = raw.get(normalize_name(p['name']), {})
        # Play-type possession counts are absent. Limit these mixed-snapshot
        # estimates instead of treating a high PPP in a tiny sample as elite.
        latest = [r for r, _ in rows if str(r['season'])[:4] == str(year-1)]
        confidence = min(.35, sum(float(r['minutes']) for r in latest)/3000)
        profile['playtype_weight'] = confidence
        for source, key in (('Post%', 'post_share'), ('Pnrr%', 'roll_share'),
                            ('PostPPP', 'post_ppp'), ('PnrrPPP', 'roll_ppp')):
            value = number(r.get(source))
            if value is not None and value <= (1 if source.endswith('%') else 2.5):
                profile[key] = value
        priors[p['id']] = profile
    return priors


def offensive_profile(canonical, player, traits):
    """Current, evolving facets. Frozen evidence is adjusted by actual skill deltas."""
    get = lambda key: float(traits.get(key, 50))
    prior = canonical.get('meta', {}).get('offensive_profiles', {}).get(player['id'], {})
    anchors = prior.get('anchors', {})
    delta = lambda key: get(key)-float(anchors.get(key, get(key)))
    height = float(player.get('height_inches') or 78)
    weight = float(player.get('weight_lbs') or 215)
    size = clamp(40+(height-76)*4+(weight-210)*.12, 15, 95)
    position = str(player.get('position') or '').upper().split('/')[0]
    big = clamp((height-77)/6, 0, 1)*(1 if position in {'C', 'PF'} else .4)
    rim, versatility, passing = get('rim_pressure'), get('shot_versatility'), get('passing_reads')
    post = (.50*rim+.30*versatility+.20*get('handle_pressure'))*(.45+.55*big)
    finishing = .65*rim+.20*size+.15*get('foot_speed_lateral_agility')
    screening = .45*size+.35*get('scheme_iq')+.20*get('stamina_cardio')
    post_share = big*(.025+max(0, post-45)*.004)
    roll_share = big*(.10+max(0, finishing-45)*.004)
    w = float(prior.get('playtype_weight', 0))
    frequency_weight = min(.65, w*2)
    if 'post_share' in prior:
        post_share = (1-frequency_weight)*post_share+frequency_weight*prior['post_share']
    if 'roll_share' in prior:
        roll_share = (1-frequency_weight)*roll_share+frequency_weight*prior['roll_share']
    if 'post_ppp' in prior:
        target = clamp(50+(prior['post_ppp']-1)*85, 20, 90)
        target += .50*delta('rim_pressure')+.30*delta('shot_versatility')+.20*delta('handle_pressure')
        post = post*(1-w)+target*w
    if 'roll_ppp' in prior:
        target = clamp(50+(prior['roll_ppp']-1.05)*65, 20, 90)
        target += .65*delta('rim_pressure')+.15*delta('foot_speed_lateral_agility')
        finishing = finishing*(1-w)+target*w
    two_base = clamp(.43+rim*.0017+max(0, size-55)*.001, .40, .70)
    if 'two_pct' in prior:
        tw = prior['two_weight']
        observed = prior['two_pct']+delta('rim_pressure')*.0018+delta('shot_versatility')*.0005
        two_pct = two_base*(1-tw)+observed*tw
        finishing = finishing*(1-tw*.35)+clamp(50+(observed-.52)*160, 20, 90)*tw*.35
    else:
        two_pct = two_base
    fallback_threes = clamp(.55*(max(0, get('shooting_range')-28)/10)**1.7, 0, 12)
    three_per36 = fallback_threes
    if 'three_per36' in prior:
        observed = max(0, prior['three_per36']+delta('shooting_range')*.14+delta('release_speed')*.025)
        vw = prior['volume_weight']
        three_per36 = fallback_threes*(1-vw)+observed*vw
        if prior['three_per36'] <= .15 and abs(delta('shooting_range')) < 2 and abs(delta('release_speed')) < 2:
            three_per36 = min(three_per36, prior['three_per36']+.04)
    three_pct = prior.get('three_pct', .28+max(0, get('shooting_range')-35)*.002)
    three_pct += delta('shooting_range')*.0015+delta('release_speed')*.0005
    ft_pct = prior.get('ft_pct', .64+get('release_speed')*.0018)+delta('release_speed')*.001
    shooting = (get('shooting_range')+versatility+get('release_speed'))/3
    creation = (get('handle_pressure')+passing+rim+versatility)/4
    legacy = .35*shooting+.32*creation+.18*passing+.15*rim
    post_weight = .10+min(.2, post_share*.7)
    interior = post*post_weight+(1-post_weight)*(.45*finishing+.25*screening+.30*get('offensive_rebounding'))
    interior_weight = .32*big*clamp(1-three_per36/10, 0, 1)
    offense = legacy*(1-interior_weight)+interior*interior_weight
    return {k: round(v, 4) for k, v in {
        'offense_model_version': MODEL_VERSION, 'offense_value': clamp(offense, 1, 99),
        'post_creation': clamp(post, 1, 99), 'assisted_finishing': clamp(finishing, 1, 99),
        'screening': clamp(screening, 1, 99), 'offensive_rebounding': get('offensive_rebounding'),
        'post_share': clamp(post_share, 0, .50), 'roll_share': clamp(roll_share, 0, .55),
        'three_per36': clamp(three_per36, 0, 14), 'three_pct': clamp(three_pct, .20, .48),
        'two_pct': clamp(two_pct, .38, .75), 'ft_pct': clamp(ft_pct, .45, .95),
        'offensive_passing': passing,
    }.items()}


def support_passing(pool, features, player_id):
    other = [i for i in pool if i['player']['id'] != player_id and float(i.get('minutes') or 0) > 0]
    total = sum(float(i['minutes']) for i in other)
    return sum(float(i['minutes'])*features[i['player']['id']].get('offensive_passing', 50)
               for i in other)/total if total else 50


def extend_lineup_features(features, players, weights):
    active = [pid for pid in weights if players[pid].get('offense_model_version')]
    if not active:
        return
    total = sum(weights[pid] for pid in active) or 1
    features['offense_model_version'] = MODEL_VERSION
    for key in ('post_creation', 'assisted_finishing', 'screening'):
        features[key] = sum(players[pid][key]*weights[pid] for pid in active)/total
    features['post_threat'] = sum(max(0, players[pid]['post_creation']-45)*players[pid]['post_share']
                                   *weights[pid] for pid in active)/total


def finishing_multiplier(features, feeder=50):
    finish = features.get('assisted_finishing', 50)
    roll = features.get('roll_share', 0)
    post = features.get('post_creation', 50)
    post_share = features.get('post_share', 0)
    assisted = max(0, features.get('rim_pressure', 50)-60)*.006
    differentiation = clamp((finish-features.get('rim_pressure', 50))*.003, -.08, .12)
    feeding = clamp((feeder-55)*(finish-45)*.00018, -.05, .10)*min(1, roll*4)
    post_creation = max(0, post-50)*post_share*.009
    putbacks = max(0, features.get('offensive_rebounding', 50)-55)*max(0, finish-40)*.000035
    return clamp(1+assisted+differentiation+feeding+post_creation+putbacks, .85, 1.50)


def team_contribution(features):
    if not features.get('offense_model_version'):
        return 0.0
    # Rebounding already extends possessions in the existing model. Do not
    # award another generic rebounding bonus to team offensive efficiency.
    screen = (features.get('screening', 50)-50)*.025
    post = features.get('post_threat', 0)*.025
    return clamp(screen+post, -1.0, 2.0)


def valuation_adjustment(features):
    if not features.get('offense_model_version'):
        return 0.0
    # Existing impact already prices defense/rebounding. This is only a bounded
    # marginal recognition of offensive roles, not a replacement overall.
    return clamp((features.get('screening', 50)-50)*.025
                 +max(0, features.get('post_creation', 50)-50)*features.get('post_share', 0)*.12
                 +max(0, features.get('assisted_finishing', 50)-50)*features.get('roll_share', 0)*.08
                 +(features.get('offensive_rebounding', 50)-50)*.015, -1.5, 3.0)


def shooting_line(points, feat, minutes, rng):
    """Preserve assigned points; sample distinct 2PT/3PT/FT shot profiles."""
    rate = clamp(.13+max(0, feat.get('rim_pressure', 50)-55)*.0028
                 +max(0, feat.get('shot_creation', 50)-70)*.0015, .08, .34)
    # Unbiased stochastic rounding. The previous round(x + U(0, 1.8)) added ~0.9 free throws to every player
    # line regardless of profile (~34 FTA per 100 possessions vs the NBA's ~23). The old count is still used for
    # the number of RNG draws (it is never smaller), so the game's random stream, and therefore every score,
    # is unchanged; only the first `fta` draws count as attempts.
    u = rng.random()
    draws = max(0, round(points*rate+u*1.8))
    fta = min(draws, max(0, math.floor(points*rate+u)))
    makes = [rng.random() < feat['ft_pct'] for _ in range(draws)]
    ftm = min(points, sum(makes[:fta]))
    attempts = minutes*feat['three_per36']/36*rng.uniform(.85, 1.15)
    fg3a = int(attempts)+(rng.random() < attempts-int(attempts))
    sampled = sum(rng.random() < feat['three_pct'] for _ in range(fg3a))
    fg3m = min(sampled, (points-ftm)//3)
    if sampled > fg3m:
        fg3a = max(fg3m, fg3a-round((sampled-fg3m)/feat['three_pct']))
    remainder = points-ftm-3*fg3m
    if remainder % 2:
        # Two-point makes need an even remainder. This used to add a made free throw with no attempt, on about
        # half of all lines (league FT% ~90% vs the NBA's ~78%). Flip one free-throw outcome instead: with the
        # shooter's FT% chance a made attempt is added, otherwise a make becomes a miss, so FT% keeps its real
        # expectation. The choice reuses `u` (no extra RNG draw), leaving the random stream and scores unchanged.
        if (u * 1000.0) % 1.0 < feat['ft_pct'] or ftm == 0:
            ftm += 1
            fta += 1
        else:
            ftm -= 1
    fg2m = (points-ftm-3*fg3m)//2
    fg2a = max(fg2m, round(fg2m/feat['two_pct']+rng.gauss(0, .6)))
    return {'fgm': fg2m+fg3m, 'fga': fg2a+fg3a, 'fg3m': fg3m, 'fg3a': fg3a,
            'ftm': ftm, 'fta': max(fta, ftm)}
