"""Frozen pre-pass Stage B functions, loaded with original module dependencies."""

def player_attribute_summary(canonical: dict[str, Any], player_id: str) -> dict[str, float]:
    from .talent import enabled as talent_enabled, role_skill_value
    traits = trait_values_by_player(canonical).get(player_id, {})
    player = players_by_id_index(canonical).get(player_id, {})
    minutes = display_minutes_projection(player)

    def avg(keys: list[str], default: float = 50.0) -> float:
        values = [traits.get(key, default) for key in keys]
        return sum(values) / max(1, len(values))

    shooting = avg(["shooting_range", "shot_versatility", "release_speed"])
    creation = avg(["handle_pressure", "passing_reads", "rim_pressure", "shot_versatility"])
    defense = avg(["defensive_effort", "scheme_iq", "screen_navigation", "rim_deterrence"])
    athleticism = avg(["foot_speed_lateral_agility", "stamina_cardio", "rim_pressure"])
    iq = avg(["scheme_iq", "passing_reads", "portability", "playoff_translation"])
    rebounding = traits.get("offensive_rebounding", 50.0) * 0.66 + traits.get("rim_deterrence", 50.0) * 0.18 + traits.get("stamina_cardio", 50.0) * 0.16
    spacing = avg(["shooting_range", "release_speed", "shot_versatility"])
    steal = avg(["defensive_effort", "screen_navigation", "foot_speed_lateral_agility", "scheme_iq"])
    block = avg(["rim_deterrence", "foot_speed_lateral_agility", "defensive_effort"])
    overall = shooting * 0.22 + creation * 0.25 + defense * 0.22 + athleticism * 0.13 + iq * 0.12 + min(6.0, minutes / 7.0)
    if talent_enabled(canonical):
        role = role_skill_value((shooting, creation, defense, athleticism, iq, rebounding), player.get("position"))
        overall = .5 * overall + .5 * (role * .94 + min(6.0, minutes / 7.0))
    from .offense import enabled as offense_enabled, offensive_profile, FACETS
    offensive_attrs = {}
    if offense_enabled(canonical):
        profile = offensive_profile(canonical, player, traits)
        offensive_attrs = {key: round(profile[key], 1) for key in FACETS}
        offensive_attrs['offense'] = round(profile['offense_value'], 1)
    return {
        **offensive_attrs,
        "overall": round(clamp(overall, 1, 99), 1),
        "shooting": round(clamp(shooting, 1, 99), 1),
        "spacing": round(clamp(spacing, 1, 99), 1),
        "creation": round(clamp(creation, 1, 99), 1),
        "defense": round(clamp(defense, 1, 99), 1),
        "athleticism": round(clamp(athleticism, 1, 99), 1),
        "iq": round(clamp(iq, 1, 99), 1),
        "release": round(clamp(traits.get("release_speed", 50.0), 1, 99), 1),
        "range": round(clamp(traits.get("shooting_range", 50.0), 1, 99), 1),
        "versatility": round(clamp(traits.get("shot_versatility", 50.0), 1, 99), 1),
        "handle": round(clamp(traits.get("handle_pressure", 50.0), 1, 99), 1),
        "rim_pressure": round(clamp(traits.get("rim_pressure", 50.0), 1, 99), 1),
        "passing": round(clamp(traits.get("passing_reads", 50.0), 1, 99), 1),
        "stamina": round(clamp(traits.get("stamina_cardio", 50.0), 1, 99), 1),
        "rebounding": round(clamp(rebounding, 1, 99), 1),
        "def_effort": round(clamp(traits.get("defensive_effort", 50.0), 1, 99), 1),
        "screen_nav": round(clamp(traits.get("screen_navigation", 50.0), 1, 99), 1),
        "steal": round(clamp(steal, 1, 99), 1),
        "block": round(clamp(block, 1, 99), 1),
        "rim_deterrence": round(clamp(traits.get("rim_deterrence", 50.0), 1, 99), 1),
        "oreb": round(clamp(traits.get("offensive_rebounding", 50.0), 1, 99), 1),
        "lateral_agility": round(clamp(traits.get("foot_speed_lateral_agility", 50.0), 1, 99), 1),
        "scheme_iq": round(clamp(traits.get("scheme_iq", 50.0), 1, 99), 1),
        "portability": round(clamp(traits.get("portability", 50.0), 1, 99), 1),
        "playoff": round(clamp(traits.get("playoff_translation", 50.0), 1, 99), 1),
    }

