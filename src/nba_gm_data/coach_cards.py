"""Coach-card comparisons and explanations of existing staff mechanics."""
from math import isfinite

# Every line describes an effect the engine applies (coaching overhaul 2026-11-18; project rule: what the user sees
# must match what the engine uses).
TRAIT_HELP = {
    'rotation_management': 'Game-plan minutes: how well the coach shifts minutes toward the right players for each opponent, and how carefully players returning from injury are eased back in.',
    'locker_room': 'Player relations (with communication): a small boost to the team at both ends, and the head coach\'s share of player development.',
    'scheme_balance': 'Game management (with adaptability): a small in-game edge at both ends, and a larger edge in the playoffs.',
    'shot_quality': 'The offensive scheme\'s shot quality: the main offensive coaching effect for every roster.',
    'spacing_design': 'Spacing design: an offensive boost that grows with the number of good shooters on the floor.',
    'player_usage': 'Creator usage: an offensive boost that grows when the team has a true primary creator.',
    'coverage_design': 'Coverage design: the main defensive coaching effect for every roster, and how well the defense controls pace.',
    'matchup_adjustment': 'Matchup scheming: hiding weak defenders and targeting the opponent\'s, game-plan minutes, and part of the playoff edge.',
    'discipline': 'Discipline: fewer defensive breakdowns and about 4% fewer fouls per step above average.',
    'skill_development': 'Player growth rate, with extra focus on shooting, handling and finishing skills.',
    'prospect_patience': 'Growth for young players getting opportunity.',
    'feedback_clarity': 'Player growth rate, with extra focus on reads, decision-making and team defense.',
    'talent_eval': 'Draft scouting accuracy (58% of the scouting score): less noise on prospect grades.',
    'risk_modeling': 'Draft scouting accuracy (27% of the scouting score), and part of how much the staff experiments with pace.',
    'international_coverage': 'Draft scouting accuracy (15% of the scouting score), especially for international prospects.',
    'injury_prevention': 'Lower injury odds on every body part, within the health model\'s limits.',
    'conditioning': 'Less fatigue gained from playing (fatigue raises injury odds and lowers in-game performance).',
    'recovery_planning': 'Shorter injury absences, faster fatigue recovery and faster return from post-injury rust.',
    'adaptability': 'Head coach: part of game management and matchup adjustments. All staff: part of the staff grade.',
    'communication': 'Head coach: part of player relations. All staff: part of the staff grade.',
    'ambition': 'Head coach: how hands-on the coach is with minutes and pace. No effect in other roles.',
    'star_workload': 'Head coach: how many minutes he plans for his two best players. 50 is an average coach; every 12 points is about one more minute a game for each (measured from real coaches, 2021-22 to 2025-26). A star-riding coach also leans a little more on his other starters when someone is out.',
    'grade': 'Overall staff evaluation used for hiring, firing and contract decisions. The specific traits drive the game effects.',
    'morale': 'Tracks staff satisfaction. No game effect yet.',
    'job_security': 'Pressure to replace this staff member: moves with results versus expectations.',
}


def displayed_staff_grade(staff):
    """Match the existing staff-list grade without changing simulation formulas."""
    for key in ('grade', 'rating', 'overall', 'staff_grade', 'reputation_grade_target'):
        if isinstance(staff.get(key), (int, float)) and isfinite(staff[key]):
            return float(staff[key])
    series = [float(value) for group in ('skill_traits', 'personality_traits')
              for value in (staff.get(group) or {}).values()
              if isinstance(value, (int, float)) and isfinite(value)]
    return sum(series) / len(series) if series else None


def with_star_workload(staff):
    """A head coach's star workload sits with his working-style traits (the value the minutes engine uses)."""
    if (staff.get('slot') or staff.get('role')) != 'head_coach':
        return staff
    from .staff import coach_star_workload, star_workload_score
    traits = dict(staff.get('personality_traits') or {})
    traits['star_workload'] = star_workload_score(coach_star_workload(staff))
    return {**staff, 'personality_traits': traits}


def coach_card_details(staff, league_staff):
    staff = with_star_workload(staff)
    league_staff = [with_star_workload(row) for row in league_staff]
    role = staff.get('slot') or staff.get('role')
    peers = [row for row in league_staff if (row.get('slot') or row.get('role')) == role
             and row.get('team_id') and row.get('market_status') not in {'fired', 'free_agent'}]
    def values(row):
        return {**(row.get('skill_traits') or {}), **(row.get('personality_traits') or {}),
                'grade': displayed_staff_grade(row), 'morale': row.get('morale'), 'job_security': row.get('job_security')}
    metrics = values(staff)
    peer_values = [values(row) for row in peers]
    averages = {}
    for key in metrics:
        series = [float(row[key]) for row in peer_values if isinstance(row.get(key), (int, float)) and isfinite(row[key])]
        averages[key] = round(sum(series) / len(series), 2) if series else None
    grade = displayed_staff_grade(staff)
    descriptions = dict(TRAIT_HELP)
    if role == 'head_coach':
        descriptions.update({
            'adaptability': 'Impacts matchup adjustments, experimentation, and staff grade. Higher ratings increase all three.',
            'communication': 'Impacts rotation trust, player buy-in, and staff grade. Higher ratings increase all three.',
            'ambition': 'Impacts hands-on control. Higher ratings increase the coach’s control; this is not a universal performance bonus.',
        })
        from .staff import coach_star_workload, star_workload_text
        descriptions['star_workload'] = f"{star_workload_text(coach_star_workload(staff))} {TRAIT_HELP['star_workload']}"
    return {'staff': {**staff, 'grade': round(grade, 2) if grade is not None else None},
            'averages': averages, 'peer_count': len(peers), 'descriptions': descriptions}
