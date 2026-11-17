"""Matchup-conditioned box-score texture without changing scores or scoring RNG.

This is a conditional box-score model, not possession-by-possession simulation.
The scoring engine already resolves matchup strength; here those outcomes gain
plausible shooting misses, ball security and rebound opportunities.
"""
import math
import random


def poisson(rng, mean):
    threshold, product, count = math.exp(-max(0, mean)), 1., 0
    while product > threshold:
        product *= rng.random()
        count += 1
    return max(0, count - 1)


def missed_attempts(rng, makes, probability):
    # Negative-binomial failures before a fixed number of makes. Unlike
    # makes/pct rounding, this permits genuinely inefficient individual nights.
    probability = min(.82, max(.25, probability))
    return sum(int(math.log(max(1e-12, rng.random())) / math.log(1 - probability)) for _ in range(makes))


def vary_box_score(canonical, groups, team_lines, feature_groups, seed):
    from .sim import player_feature_vector, redistribute_integer_stat
    from .box_score import reduced_counts
    rng = random.Random(seed)
    for index, lines in enumerate(groups):
        own, opp = feature_groups[index], feature_groups[1-index]
        shooting_day = rng.gauss(0, .025)
        pressure = (float(opp.get('defensive_events', 60)) - 60) / 40
        rim = (float(opp.get('defense_rim', opp.get('rim_deterrence', 60))) - 60) / 40
        passing = (float(own.get('passing', 60)) - 60) / 40
        # Shared game environment couples teammates without making all players
        # good or bad together. Individual draws still dominate rare outliers.
        disruption_day = rng.gauss(0, .13)
        for line in lines:
            minutes = float(line.get('minutes') or 0)
            if minutes <= 0:
                continue
            player = next((p for p in canonical.get('players', []) if p['id'] == line['player_id']), None)
            feat = player_feature_vector(canonical, player).features if player else {}
            two_makes = int(line['fgm'] - line['fg3m'])
            base = float(feat.get('two_pct') or .51)
            paint_share = float(feat.get('roll_share', .15)) + float(feat.get('post_share', .15))
            probability = base + shooting_day + rng.gauss(0, .045) - rim * (.020 + paint_share * .025)
            two_misses = missed_attempts(rng, two_makes, probability)
            if two_makes == 0:
                two_misses = poisson(rng, minutes / 36 * 1.3)
            line['fga'] = int(line['fg3a']) + two_makes + two_misses
            usage = float(feat.get('usage') or 60)
            baseline = max(float(line.get('turnovers') or 0), minutes * (.015 + usage / 2200))
            turnover_mean = baseline * max(.5, 1 + pressure * .22 - passing * .12 + disruption_day)
            line['turnovers'] = poisson(rng, turnover_mean)
        team = team_lines[index]
        # Fixed scores do not permit unlimited cold-shooting misses on top of
        # turnovers. Bound the estimated possession budget (FT trips are not
        # available, so .44 is an approximation with dead-ball/rounding slack).
        rate = min(.38, max(.16, .24 + (own.get('offensive_rebounding', 50) - 50) * .0022))
        makes = sum(p['fgm'] for p in lines)
        mandatory = sum(p['fg3a'] + p['fgm'] - p['fg3m'] for p in lines)
        free_throws = sum(p['fta'] for p in lines)
        turnovers = sum(p['turnovers'] for p in lines)
        budget = float(team['possessions']) + 8
        max_turnovers = max(0, int(budget - mandatory + rate * (mandatory - makes) - .44 * free_throws))
        assigned = reduced_counts([p['turnovers'] for p in lines], max_turnovers, [p['player_id'] for p in lines])
        for line, count in zip(lines, assigned):
            line['turnovers'] = count
        turnovers = sum(assigned)
        allowed_fga = max(mandatory, int((budget - turnovers - .44 * free_throws - rate * makes) / (1 - rate)))
        misses = [p['fga'] - p['fg3a'] - (p['fgm'] - p['fg3m']) for p in lines]
        misses = reduced_counts(misses, max(0, allowed_fga - mandatory), [p['player_id'] for p in lines])
        for line, count in zip(lines, misses):
            line['fga'] = line['fg3a'] + line['fgm'] - line['fg3m'] + count
        for key in ('fga', 'fgm', 'turnovers'):
            team[key] = sum(int(p.get(key) or 0) for p in lines)
        assists = round(max(8, min(43, float(team.get('assists') or 26) - pressure * 1.7 - disruption_day * 5 + rng.gauss(0, 3.6))))
        redistribute_integer_stat(lines, 'assists', assists, 1.)
    # Rebounds depend on the missed shots that actually exist on both sides;
    # the final accounting pass enforces the hard opportunity limits.
    misses = [t['fga'] - t['fgm'] for t in team_lines]
    for index, lines in enumerate(groups):
        team, own, opp = team_lines[index], feature_groups[index], feature_groups[1-index]
        own_miss, opp_miss = misses[index], misses[1-index]
        oreb_rate = min(.38, max(.16, .24 + (own.get('offensive_rebounding', 50) - 50) * .0022))
        opp_oreb_rate = min(.38, max(.16, .24 + (opp.get('offensive_rebounding', 50) - 50) * .0022))
        rebounds = round(max(20, min(70, own_miss * oreb_rate + opp_miss * (1 - opp_oreb_rate) + rng.gauss(0, 3.5))))
        redistribute_integer_stat(lines, 'rebounds', rebounds, 1.)
        for key, sigma in (('steals', 2.0), ('blocks', 1.7)):
            target = max(0, round(float(team.get(key) or 0) + rng.gauss(0, sigma)))
            redistribute_integer_stat(lines, key, target, 1.)
        team['offensive_rebounds'] = min(rebounds, round(own_miss * oreb_rate))
        team['defensive_rebounds'] = max(0, rebounds - team['offensive_rebounds'])

