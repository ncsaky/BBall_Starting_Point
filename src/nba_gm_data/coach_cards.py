"""Coach-card comparisons and explanations of existing staff mechanics."""
from math import isfinite

TRAIT_HELP = {
    'rotation_management': 'Impacts rotation trust, adherence to requested minutes, and hands-on control. Higher ratings increase all three.',
    'locker_room': 'Impacts player buy-in and player development. Higher ratings improve both team ratings.',
    'scheme_balance': 'Impacts offensive structure, defensive structure, and playoff preparation. Higher ratings improve all three.',
    'shot_quality': 'Impacts offensive structure and playoff preparation. Higher ratings improve both.',
    'spacing_design': 'Impacts offensive structure. Higher ratings improve the team’s offensive structure rating.',
    'player_usage': 'Impacts matchup adjustments and experimentation. Higher ratings increase both team ratings.',
    'coverage_design': 'Impacts defensive structure. Higher ratings improve the team’s defensive structure rating.',
    'matchup_adjustment': 'Impacts matchup adjustments and playoff preparation. Higher ratings improve both.',
    'discipline': 'Impacts defensive structure. Higher ratings improve the team’s defensive structure rating.',
    'skill_development': 'Impacts player development. Higher ratings improve the team’s development rating.',
    'prospect_patience': 'Impacts player development. Higher ratings improve the team’s development rating.',
    'feedback_clarity': 'Impacts player buy-in. Higher ratings improve the team’s player buy-in rating.',
    'talent_eval': 'Impacts scouting coverage growth. Accounts for 58% of the scouting staff score; higher ratings increase coverage.',
    'risk_modeling': 'Impacts scouting coverage growth and team experimentation. Accounts for 27% of the scouting staff score; higher ratings increase both effects.',
    'international_coverage': 'Impacts scouting coverage growth. Accounts for 15% of the scouting staff score; higher ratings increase coverage.',
    'injury_prevention': 'Impacts injury probability. Higher ratings lower injury risk, subject to the health model’s limits.',
    'conditioning': 'Impacts fatigue accumulation. Higher ratings reduce fatigue gained from playing.',
    'recovery_planning': 'Impacts injury recovery time. Higher ratings reduce recovery time, subject to the health model’s limits.',
    'adaptability': 'Impacts staff grade. Higher ratings increase the grade used by staff-management decisions.',
    'communication': 'Impacts staff grade. Higher ratings increase the grade used by staff-management decisions.',
    'ambition': 'No direct team-rating modifier in this role.',
    'grade': 'Impacts staff evaluation and AI hiring or replacement decisions. Underlying traits determine specific team effects.',
    'morale': 'Tracks staff satisfaction. No direct team-rating modifier.',
    'job_security': 'Impacts AI replacement pressure. Higher security reduces replacement pressure; lower security increases it.',
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


def coach_card_details(staff, league_staff):
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
    return {'staff': {**staff, 'grade': round(grade, 2) if grade is not None else None},
            'averages': averages, 'peer_count': len(peers), 'descriptions': descriptions}
