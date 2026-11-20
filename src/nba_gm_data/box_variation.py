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


def missed_attempts(rng, makes, probability, upper=.82):
    # Negative-binomial failures before a fixed number of makes. Unlike
    # makes/pct rounding, this permits genuinely inefficient individual nights.
    probability = min(upper, max(.25, probability))
    return sum(int(math.log(max(1e-12, rng.random())) / math.log(1 - probability)) for _ in range(makes))


MISS_FILL = 0.82  # team FG% game-to-game sd ~.059, the 2025-26 NBA's (xPoints game database, 2,460 team-games)
PLAYER_REBOUND_SHARE = 0.92  # fitted 2026-11-17: player rebounds per 36 bias +0.67 -> +0.13 (real-minutes replay)


# Shot difficulty and team context (2026-11-19, unused-ratings audit). The game's score fixes the team's points and
# possessions, so a team that scores more efficiently than its players' own shooting percentages implies loses
# two-point misses here (and a colder team gains them). That gap used to be shared in plain proportion to each player's
# misses, so a team's good offence made its tough-shot creators as much more efficient as its spot-up shooters and
# finishers: high-usage scorers ran ~4 points of two-point percentage above their own (Ingram, Brunson, Booker true
# shooting .63-.65 vs .57-.59 real). Real team offence mostly improves the shots teammates are set up for; a player
# who lives on difficult self-created shots keeps close to his own shot-making. Each player's share of the team's
# miss swing is therefore scaled by exp(-k * z), z = his shot difficulty tolerance (T04, built from Basketball
# Index shot quality and openness) in league standard deviations. k is fitted to real 2025-26 true shooting of the
# 150 heaviest-minute players (scripts/fit_shot_difficulty_share.py). Old-ratings saves have no T04: unchanged.
DIFFICULTY_FEATURE = 'shot_difficulty'
DIFFICULTY_REF, DIFFICULTY_SD = 0.269, 0.033   # league mean and spread of T04 (691 players)
SHOT_DIFFICULTY_SHARE = 0.5   # fitted: TS mean abs error .0258 -> .0246; top-15 tolerance players +.019 -> +.007


# Two-point misses that add up to the player's own percentage (2026-11-19, shooters). Misses were drawn per make (so
# they averaged makes x (1 - pct) / pct, already the player's own percentage) and, on a night with no two-point make,
# 1.3 more per 36 whoever the player was. The second part came on top of the first: a pure shooter, who has no
# two-point make on most nights, carried 2.5 two-point attempts per 36 at .25 (AJ Green; real 1.0 at .47) and the
# spot-up group lost .05 of two-point percentage here. Now, if his two-point attempts arrive at his own rate and each
# goes in at his own percentage (a Poisson process), a night with no make has misses ~ Poisson(rate x (1 - pct)), and
# the per-make draw is thinned by P(at least one make) = 1 - exp(-expected makes), so the misses over all nights still
# average rate x (1 - pct). His rate is what his expected points leave after his threes and free throws (correlation
# 0.94 with real 2025-26 two-point attempts per 36), with a small floor. Old-ratings players keep the old rule.
ZERO_MAKE_MISSES_LEGACY = 1.3
TWO_ATTEMPTS_FLOOR = 0.25
OWN_RATE_MISSES = True


def two_attempts_per36(feat):
    """The player's expected two-point attempts per 36 (new ratings), or None (old ratings)."""
    points = feat.get('points_per36')
    if points is None or feat.get('three_per36') is None or not feat.get('two_pct'):
        return None
    free = float(points) * float(feat.get('fta_per_point') or 0.0) * float(feat.get('ft_pct') or .75)
    left = float(points) - 3 * float(feat['three_per36']) * float(feat.get('three_pct') or .35) - free
    return max(TWO_ATTEMPTS_FLOOR, left / (2 * float(feat['two_pct'])))


def team_context_share(difficulty):
    if difficulty is None or not SHOT_DIFFICULTY_SHARE:
        return 1.0
    return math.exp(-SHOT_DIFFICULTY_SHARE * (float(difficulty) - DIFFICULTY_REF) / DIFFICULTY_SD)


def removed_by_weight(values, remove, weights, identities):
    """Remove `remove` units from integer counts in proportion to weights, never below zero (deterministic)."""
    values = list(values)
    remove = max(0, min(int(remove), sum(values)))
    out = [0.0] * len(values)
    left, open_ = float(remove), [i for i in range(len(values)) if values[i] > 0 and weights[i] > 0]
    while left > 1e-9 and open_:
        total = sum(weights[i] for i in open_)
        capped = [i for i in open_ if out[i] + left * weights[i] / total >= values[i]]
        if not capped:
            for i in open_:
                out[i] += left * weights[i] / total
            left = 0.0
            break
        for i in capped:
            left -= values[i] - out[i]
            out[i] = float(values[i])
            open_.remove(i)
    if left > 1e-9:   # every weighted count is exhausted: take the rest in plain proportion
        rest = [v - o for v, o in zip(values, out)]
        total = sum(rest)
        out = [o + left * r / total for o, r in zip(out, rest)]
    taken = [math.floor(q + 1e-9) for q in out]
    order = sorted(range(len(values)), key=lambda i: (-(out[i] - taken[i]), str(identities[i])))
    for i in order[:remove - sum(taken)]:
        taken[i] += 1
    return [v - t for v, t in zip(values, taken)]


def increased_counts(weights, extra, identities):
    """Largest-remainder split of `extra` new events in proportion to `weights` (deterministic)."""
    total = sum(weights)
    if extra <= 0 or total <= 0:
        return [0] * len(weights)
    quotas = [w * extra / total for w in weights]
    assigned = [math.floor(q) for q in quotas]
    order = sorted(range(len(weights)), key=lambda i: (-(quotas[i] - assigned[i]), str(identities[i])))
    for i in order[:extra - sum(assigned)]:
        assigned[i] += 1
    return assigned


def vary_box_score(canonical, groups, team_lines, feature_groups, seed):
    from .sim import player_feature_vector, redistribute_integer_stat, turnover_rate_per_minute
    from .box_score import reduced_counts
    rng = random.Random(seed)
    player_features = {}
    for index, lines in enumerate(groups):
        own, opp = feature_groups[index], feature_groups[1-index]
        shooting_day = rng.gauss(0, .025)
        pressure = (float(opp.get('defensive_events', 60)) - 60) / 40
        rim = (float(opp.get('defense_rim', opp.get('rim_deterrence', 60))) - 60) / 40
        passing = (float(own.get('passing', 60)) - 60) / 40
        # Shared game environment couples teammates without making all players
        # good or bad together. Individual draws still dominate rare outliers.
        disruption_day = rng.gauss(0, .13)
        difficulty = {}
        for line in lines:
            minutes = float(line.get('minutes') or 0)
            if minutes <= 0:
                continue
            player = next((p for p in canonical.get('players', []) if p['id'] == line['player_id']), None)
            feat = player_feature_vector(canonical, player).features if player else {}
            player_features[line['player_id']] = feat
            if feat.get(DIFFICULTY_FEATURE) is not None:
                difficulty[line['player_id']] = float(feat[DIFFICULTY_FEATURE])
            two_makes = int(line['fgm'] - line['fg3m'])
            base = float(feat.get('two_pct') or .51)
            paint_share = float(feat.get('roll_share', .15)) + float(feat.get('post_share', .15))
            probability = base + shooting_day + rng.gauss(0, .045) - rim * (.020 + paint_share * .025)
            rate = two_attempts_per36(feat) if OWN_RATE_MISSES else None
            if rate is None:
                two_misses = missed_attempts(rng, two_makes, probability)
                if two_makes == 0:
                    two_misses = poisson(rng, minutes / 36 * ZERO_MAKE_MISSES_LEGACY)
            else:
                probability = min(.82, max(.25, probability))
                attempts = minutes / 36 * rate
                if two_makes == 0:
                    two_misses = poisson(rng, attempts * (1 - probability))
                else:
                    # Thin the per-make misses by P(at least one make): (1 - p') / p' = s (1 - p) / p.
                    thin = 1 - math.exp(-attempts * probability)
                    two_misses = missed_attempts(rng, two_makes, probability / (probability + thin * (1 - probability)),
                                                 upper=.97)
            line['fga'] = int(line['fg3a']) + two_makes + two_misses
            # The player's own expected turnovers (box_rates fit). This used to be the larger of the engine's
            # rounded draw and a usage formula, which handed bench players extra turnovers and flattened ball
            # handlers to ~2 per 36 (2026-11-18).
            baseline = minutes * turnover_rate_per_minute(feat)
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
        # Missed twos move toward the game's actual possessions in BOTH directions. The old one-sided cap
        # (possessions + 8) only removed misses in high-scoring games and never added them in low-scoring ones,
        # which pushed league 2P% to ~59% vs players' own ~54% (2026-11-17).
        target_fga = max(mandatory, round((float(team['possessions']) - turnovers - .44 * free_throws - rate * makes) / (1 - rate)))
        misses = [p['fga'] - p['fg3a'] - (p['fgm'] - p['fg3m']) for p in lines]
        ids = [p['player_id'] for p in lines]
        # Fill MISS_FILL of the gap: the engine's whole game-to-game scoring luck would otherwise land on two-point
        # misses alone (team FG% spread ~.074 vs the NBA's .059).
        wanted = max(0, round(sum(misses) + MISS_FILL * (target_fga - mandatory - sum(misses))))
        # The opponent's rim protection still shows in the box after the fill: about +1.5 two-point misses against an elite
        # rim protector, about -1.2 against a weak one (within the possession budget's slack).
        wanted = max(0, wanted + round(rim * 2.0))
        context = [team_context_share(difficulty.get(p['player_id'])) for p in lines]
        if sum(misses) > wanted:
            if any(c != 1.0 for c in context):
                misses = removed_by_weight(misses, sum(misses) - wanted, [m * c for m, c in zip(misses, context)], ids)
            else:
                misses = reduced_counts(misses, wanted, ids)
        elif sum(misses) < wanted:
            # Spread the extra misses like the player's own two-point volume (makes plus generated misses).
            # A player with no two-point volume tonight keeps a small claim (.5) so a cold team still spreads its misses.
            weights = [(((p['fgm'] - p['fg3m']) + m) or (.5 if float(p.get('minutes') or 0) > 0 else 0)) * c
                       for p, m, c in zip(lines, misses, context)]
            misses = [m + extra for m, extra in zip(misses, increased_counts(weights, wanted - sum(misses), ids))]
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
        # Some missed shots end as team rebounds (out of bounds, end of period) credited to no player.
        player_share = PLAYER_REBOUND_SHARE
        rebounds = round(max(20, min(70, (own_miss * oreb_rate + opp_miss * (1 - opp_oreb_rate)) * player_share + rng.gauss(0, 3.5))))
        redistribute_integer_stat(lines, 'rebounds', rebounds, 1.)
        # Blocks already arrive as per-player Poisson draws (team sd ~2.2); the real 2025-26 team-game sd is 2.46, so
        # only the remaining sqrt(2.46^2 - 2.2^2) ~ 1.1 is added here (was 1.7 on a near-fixed team total).
        for key, sigma in (('steals', 2.0), ('blocks', 1.1)):
            target = max(0, round(float(team.get(key) or 0) + rng.gauss(0, sigma)))
            redistribute_integer_stat(lines, key, target, 1.)
        team['offensive_rebounds'] = min(rebounds, round(own_miss * oreb_rate * player_share))
        team['defensive_rebounds'] = max(0, rebounds - team['offensive_rebounds'])
    # Screen assists (new ratings): their own generator, after every other draw; see screens.py.
    from .screens import add_screen_assists
    add_screen_assists(groups, player_features, seed)
