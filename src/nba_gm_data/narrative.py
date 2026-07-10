"""Generate optional local-LLM prose without delegating league truth.

Save-backed events remain authoritative. Model output is lazy, cached,
strictly parsed, semantically validated against a compact sim-only packet, and
replaced by deterministic fallback text whenever that contract fails.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any, Protocol

from .schema import CANONICAL_SEASON
from .utils import clamp, stable_id


NARRATIVE_PROMPT_VERSION = "narrative_v11"
SOCIAL_TEXT_MAX_CHARS = 760
TAX_LINE = 187_895_000
SECOND_APRON = 207_824_000
ANNUAL_CAP_GROWTH_RATE = 0.035
ALLOWED_PRESS_TONES = {"accountable", "optimistic", "deflect", "challenge"}
ALLOWED_PRESS_QUALITIES = {"good", "mixed", "bad"}

PERSONAS = [
    {
        "author": "Cap Sheet Carl",
        "handle": "@cap_sheet_carl",
        "persona": "cap obsessive",
        "style": "sharp salary-cap obsessive; uses cap-space and hard-cap room language, calls out bad years and fake bargains",
    },
    {
        "author": "Maya Chen",
        "handle": "@maya_hoops",
        "persona": "film analyst",
        "style": "film analyst with a real take; talks roles, coverages, spacing, matchup pressure, and who actually has to change",
    },
    {
        "author": "Jules Hart",
        "handle": "@jules_on_hoops",
        "persona": "beat reporter",
        "style": "dry beat reporter; skeptical of spin, notices locker-room politics and front-office stakes",
    },
    {
        "author": "Sideline Static",
        "handle": "@sideline_static",
        "persona": "fan chaos",
        "style": "funny fan account with agenda slang; can say cooked, nasty work, bit, hoops terrorism, or we are so back when it fits",
    },
    {
        "author": "The Skeptical Insider",
        "handle": "@skeptic_insider",
        "persona": "skeptical insider",
        "style": "skeptical transaction watcher; assumes every official explanation is spin, but do not mention leaks unless the context includes a rumor",
    },
    {
        "author": "Number Cruncher Nina",
        "handle": "@nina_numbers",
        "persona": "stats nerd",
        "style": "numbers-minded analyst with bite; names the stat or standings pressure that makes the move smart or dumb",
    },
    {
        "author": "Draft Sicko",
        "handle": "@draft_sicko",
        "persona": "draft sicko",
        "style": "prospect-and-pick obsessive; overreacts to pick math, upside bands, swaps, protections, and youth timelines",
    },
]

SOCIAL_STANCES = [
    {
        "label": "positive",
        "instruction": "lean positive if the facts allow it; explain why the move could work instead of defaulting to suspicion",
    },
    {
        "label": "balanced",
        "instruction": "name the upside and the risk in plain basketball terms",
    },
    {
        "label": "skeptical",
        "instruction": "be skeptical, but make the criticism specific to the supplied sim facts",
    },
    {
        "label": "excited",
        "instruction": "sound energized by the move or moment without inventing facts",
    },
    {
        "label": "wait_and_see",
        "instruction": "reserve judgment, but say exactly what on-court or roster question matters next",
    },
]


class NarrativeProvider(Protocol):
    name: str

    def generate_json(self, prompt: str, settings: dict[str, Any]) -> dict[str, Any]:
        ...


class NarrativeProviderError(RuntimeError):
    pass


class OllamaNarrativeProvider:
    name = "ollama"

    def generate_json(self, prompt: str, settings: dict[str, Any]) -> dict[str, Any]:
        base_url = str(settings.get("ollama_base_url") or "http://localhost:11434").rstrip("/")
        model = str(settings.get("ollama_model") or "llama3.1")
        timeout = float(settings.get("timeout_seconds") or 2.0)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": float(settings.get("temperature") or 0.8),
                "num_predict": int(settings.get("max_tokens") or 650),
            },
        }
        request = urllib.request.Request(
            f"{base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                body = ""
            message = f"HTTP {exc.code}"
            if body:
                try:
                    parsed = json.loads(body)
                    if isinstance(parsed, dict) and parsed.get("error"):
                        message = str(parsed["error"])
                    else:
                        message = body[:200]
                except json.JSONDecodeError:
                    message = body[:200]
            raise NarrativeProviderError(message) from exc
        except (OSError, urllib.error.URLError) as exc:
            raise NarrativeProviderError(str(exc)) from exc
        try:
            envelope = json.loads(raw)
            content = envelope.get("response") if isinstance(envelope, dict) else None
            if not content and isinstance(envelope, dict):
                content = envelope.get("thinking")
            if not isinstance(content, str):
                raise ValueError("missing response")
            return json.loads(content)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise NarrativeProviderError("Ollama returned malformed JSON") from exc


class FallbackNarrativeProvider:
    name = "fallback"

    def generate_json(self, prompt: str, settings: dict[str, Any]) -> dict[str, Any]:
        raise NarrativeProviderError("Fallback provider does not call a model.")


def default_narrative_settings() -> dict[str, Any]:
    return {
        "enabled": True,
        "provider": "ollama",
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "llama3.1",
        "timeout_seconds": 45.0,
        "max_posts_per_view": 12,
        "max_tokens": 900,
        "temperature": 0.95,
    }


def normalize_narrative_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = default_narrative_settings()
    if isinstance(settings, dict):
        normalized.update({key: value for key, value in settings.items() if value is not None})
    normalized["enabled"] = bool(normalized.get("enabled"))
    normalized["provider"] = str(normalized.get("provider") or "ollama").lower()
    if normalized["provider"] not in {"ollama", "fallback"}:
        normalized["provider"] = "ollama"
    normalized["timeout_seconds"] = float(clamp(float(normalized.get("timeout_seconds") or 45.0), 0.25, 120.0))
    normalized["max_posts_per_view"] = int(clamp(int(normalized.get("max_posts_per_view") or 12), 1, 48))
    normalized["max_tokens"] = int(clamp(int(normalized.get("max_tokens") or 650), 128, 4096))
    normalized["temperature"] = float(clamp(float(normalized.get("temperature") or 0.8), 0.0, 1.5))
    return normalized


def ensure_narrative_state(save: dict[str, Any]) -> None:
    save["narrative_settings"] = normalize_narrative_settings(save.get("narrative_settings"))
    cache = save.setdefault("narrative_cache", {})
    if cache.get("version") and cache.get("version") != NARRATIVE_PROMPT_VERSION:
        reset_narrative_cache(save)
        return
    cache.setdefault("version", NARRATIVE_PROMPT_VERSION)
    cache.setdefault("social", {})
    cache.setdefault("press", {})


def narrative_enabled(save: dict[str, Any]) -> bool:
    ensure_narrative_state(save)
    return bool(save.get("narrative_settings", {}).get("enabled"))


def provider_from_settings(settings: dict[str, Any]) -> NarrativeProvider:
    if str(settings.get("provider") or "").lower() == "fallback":
        return FallbackNarrativeProvider()
    return OllamaNarrativeProvider()


def narrative_status(save: dict[str, Any], provider: NarrativeProvider | None = None) -> dict[str, Any]:
    ensure_narrative_state(save)
    settings = save["narrative_settings"]
    output = {
        "enabled": settings.get("enabled"),
        "provider": settings.get("provider"),
        "ollama_base_url": settings.get("ollama_base_url"),
        "ollama_model": settings.get("ollama_model"),
        "timeout_seconds": settings.get("timeout_seconds"),
        "max_posts_per_view": settings.get("max_posts_per_view"),
        "cache_counts": {
            "social": len(save.get("narrative_cache", {}).get("social", {})),
            "press": len(save.get("narrative_cache", {}).get("press", {})),
        },
    }
    if provider is not None:
        available_models = ollama_available_models(settings) if settings.get("provider") == "ollama" else []
        if available_models:
            output["available_models"] = available_models
        try:
            provider.generate_json(
                'Return exactly JSON: {"ok": true, "message": "ready"}',
                {**settings, "timeout_seconds": min(float(settings.get("timeout_seconds") or 2.0), 3.0), "max_tokens": 64},
            )
            output["connection"] = "ok"
        except NarrativeProviderError as exc:
            message = str(exc)
            if "not found" in message.lower() and available_models:
                message = (
                    f"{message}. Available local models: {', '.join(available_models)}. "
                    f"Set the Ollama model to one of those, or run: ollama pull {settings.get('ollama_model') or 'llama3.1'}"
                )
            output["connection"] = f"unavailable: {message}"
    return output


def ollama_available_models(settings: dict[str, Any]) -> list[str]:
    base_url = str(settings.get("ollama_base_url") or "http://localhost:11434").rstrip("/")
    timeout = float(settings.get("timeout_seconds") or 2.0)
    request = urllib.request.Request(f"{base_url}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=min(timeout, 3.0)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
        return []
    models = payload.get("models") if isinstance(payload, dict) else []
    if not isinstance(models, list):
        return []
    names = [str(item.get("name") or item.get("model") or "").strip() for item in models if isinstance(item, dict)]
    return sorted(name for name in names if name)


def reset_narrative_cache(save: dict[str, Any]) -> None:
    save["narrative_cache"] = {"version": NARRATIVE_PROMPT_VERSION, "social": {}, "press": {}}


def team_maps(canonical: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    teams_by_id = {team.get("id"): team for team in canonical.get("teams", []) if team.get("id")}
    abbrev_by_id = {team_id: team.get("abbrev", team_id) for team_id, team in teams_by_id.items()}
    return teams_by_id, abbrev_by_id


def player_maps(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {player.get("id"): player for player in canonical.get("players", []) if player.get("id")}


def compact_record(record: dict[str, Any] | None) -> dict[str, Any]:
    record = record or {}
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    games = max(1, wins + losses)
    return {
        "wins": wins,
        "losses": losses,
        "win_pct": round(wins / games, 3),
        "points_for": round(float(record.get("points_for") or 0.0), 1),
        "points_against": round(float(record.get("points_against") or 0.0), 1),
    }


def deterministic_social_stance(source_id: str | None) -> dict[str, str]:
    digest = hashlib.sha256(str(source_id or "social").encode("utf-8")).hexdigest()
    return SOCIAL_STANCES[int(digest[:8], 16) % len(SOCIAL_STANCES)]


def compact_player_minutes(player: dict[str, Any]) -> float:
    for key in ("minutes_projection", "projected_mpg", "mpg", "minutes"):
        value = player.get(key)
        try:
            minutes = float(value)
        except (TypeError, ValueError):
            continue
        if minutes > 0:
            return round(minutes / 82.0 if minutes > 48 else minutes, 1)
    stats = player.get("stats") if isinstance(player.get("stats"), dict) else {}
    try:
        games = float(stats.get("games") or stats.get("gp") or 0)
        minutes = float(stats.get("minutes") or stats.get("min") or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(minutes / games, 1) if games > 0 and minutes > 0 else 0.0


def compact_team_context(
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_id: str,
    abbrev_by_id: dict[str, str],
) -> dict[str, Any]:
    unavailable = set(save.get("free_agent_player_ids") or []) | set(save.get("retired_player_ids") or [])
    roster = [
        player for player in canonical.get("players", [])
        if player.get("team_id") == team_id and player.get("id") not in unavailable
    ]
    roster.sort(
        key=lambda player: (
            -compact_player_minutes(player),
            -float(player.get("overall") or player.get("overall_rating") or player.get("rating") or 0.0),
            str(player.get("name") or ""),
        )
    )
    core_players = []
    for player in roster[:7]:
        minutes = compact_player_minutes(player)
        if minutes < 10 and len(core_players) >= 3:
            continue
        core_players.append(
            {
                "id": player.get("id"),
                "name": player.get("name"),
                "position": player.get("position"),
                "minutes": minutes,
            }
        )
    return {
        "team_id": team_id,
        "team": abbrev_by_id.get(team_id),
        "record": compact_record(save.get("team_records", {}).get(team_id)),
        "last_10": team_last_n_record(save, team_id, 10),
        "core_players": core_players[:6],
    }


def team_last_n_record(save: dict[str, Any], team_id: str, count: int) -> str:
    logs = [
        log for log in save.get("team_game_logs", [])
        if log.get("team_id") == team_id and log.get("result") in {"W", "L"}
    ][-count:]
    if not logs:
        return "0-0"
    wins = sum(1 for log in logs if log.get("result") == "W")
    return f"{wins}-{len(logs) - wins}"


def compact_per_game_line(save: dict[str, Any], player_id: str | None) -> dict[str, Any]:
    if not player_id:
        return {"games": 0, "ppg": 0.0, "rpg": 0.0, "apg": 0.0}
    stats = save.get("player_season_stats", {}).get(player_id) or {}
    games = int(stats.get("games") or 0)
    divisor = max(1, games)
    return {
        "games": games,
        "ppg": round(float(stats.get("points") or 0.0) / divisor, 1) if stats else 0.0,
        "rpg": round(float(stats.get("rebounds") or 0.0) / divisor, 1) if stats else 0.0,
        "apg": round(float(stats.get("assists") or 0.0) / divisor, 1) if stats else 0.0,
        "mpg": round(float(stats.get("minutes") or 0.0) / divisor, 1) if stats else 0.0,
    }


def trait_index(canonical: dict[str, Any]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for trait in canonical.get("traits", []) or []:
        player_id = trait.get("player_id")
        key = trait.get("trait_key")
        if not player_id or not key:
            continue
        try:
            value = float(trait.get("value") or 50.0)
        except (TypeError, ValueError):
            value = 50.0
        output.setdefault(player_id, {})[str(key)] = value
    return output


def compact_player_ratings(player: dict[str, Any], traits: dict[str, float]) -> dict[str, float]:
    def avg(keys: list[str], default: float = 50.0) -> float:
        values = [float(traits.get(key, default)) for key in keys]
        return round(sum(values) / max(1, len(values)), 1)

    shooting = avg(["release_speed", "shooting_range", "shot_versatility"])
    creation = avg(["handle_pressure", "passing_reads", "rim_pressure", "shot_versatility"])
    defense = avg(["defensive_effort", "scheme_iq", "rim_deterrence", "screen_navigation"])
    athleticism = avg(["foot_speed_lateral_agility", "stamina_cardio", "rim_pressure"])
    iq = avg(["scheme_iq", "passing_reads", "portability", "playoff_translation"])
    rebounding = round(
        float(traits.get("offensive_rebounding", 50.0)) * 0.66
        + float(traits.get("rim_deterrence", 50.0)) * 0.18
        + float(traits.get("stamina_cardio", 50.0)) * 0.16,
        1,
    )
    overall = round(
        shooting * 0.22
        + creation * 0.25
        + defense * 0.22
        + athleticism * 0.13
        + iq * 0.12
        + min(6.0, compact_player_minutes(player) / 7.0),
        1,
    )
    return {
        "overall": round(clamp(overall, 1, 99), 1),
        "offense": round(clamp(shooting * 0.42 + creation * 0.44 + iq * 0.14, 1, 99), 1),
        "spacing": shooting,
        "shooting": shooting,
        "creation": creation,
        "playmaking": avg(["handle_pressure", "passing_reads"]),
        "defense": defense,
        "rebounding": round(clamp(rebounding, 1, 99), 1),
        "age": round(float(player.get("age") or player.get("display_age") or 0.0), 1),
    }


def expanded_rating_profile(player: dict[str, Any], traits: dict[str, float]) -> dict[str, float]:
    ratings = compact_player_ratings(player, traits)
    profile = dict(ratings)
    profile.update(
        {
            "rim_pressure": round(float(traits.get("rim_pressure", 50.0)), 1),
            "passing": round(float(traits.get("passing_reads", 50.0)), 1),
            "handle": round(float(traits.get("handle_pressure", 50.0)), 1),
            "rim_protection": round(float(traits.get("rim_deterrence", 50.0)), 1),
            "screen_navigation": round(float(traits.get("screen_navigation", 50.0)), 1),
            "defensive_effort": round(float(traits.get("defensive_effort", 50.0)), 1),
            "shooting_range": round(float(traits.get("shooting_range", 50.0)), 1),
            "shot_versatility": round(float(traits.get("shot_versatility", 50.0)), 1),
        }
    )
    return profile


def rating_snippet(profile: dict[str, float]) -> str:
    return (
        "[Ratings: "
        f"OVR {float(profile.get('overall') or 0):.0f}, "
        f"OFF {float(profile.get('offense') or 0):.0f}, "
        f"DEF {float(profile.get('defense') or 0):.0f}, "
        f"SPC {float(profile.get('spacing') or 0):.0f}, "
        f"CRE {float(profile.get('creation') or 0):.0f}, "
        f"PLY {float(profile.get('playmaking') or 0):.0f}, "
        f"REB {float(profile.get('rebounding') or 0):.0f}, "
        f"RIM {float(profile.get('rim_pressure') or 0):.0f}]"
    )


def standout_rating_context(profile: dict[str, float], position: str | None = None) -> dict[str, Any]:
    labels = {
        "spacing": "spacing",
        "creation": "creation",
        "playmaking": "playmaking",
        "defense": "defense",
        "rebounding": "rebounding",
        "rim_pressure": "rim pressure",
        "rim_protection": "rim protection",
        "screen_navigation": "screen nav",
        "defensive_effort": "defensive effort",
        "shooting_range": "range",
    }
    rows = []
    for key, label in labels.items():
        value = float(profile.get(key) or 50.0)
        if value >= 68.0 or value <= 44.0:
            rows.append((abs(value - 50.0), label, value, key))
    rows.sort(key=lambda item: (-item[0], item[1]))
    top = rows[:4]
    if not top:
        top = sorted(
            [(abs(float(profile.get(key) or 50.0) - 50.0), label, float(profile.get(key) or 50.0), key) for key, label in labels.items()],
            key=lambda item: (-item[0], item[1]),
        )[:3]
    return {
        "position": position,
        "standouts": [{"key": key, "label": label, "value": round(value, 1)} for _, label, value, key in top],
        "evidence": "[Standouts: " + ", ".join(f"{label} {value:.0f}" for _, label, value, _ in top) + "]" if top else "",
    }


def health_profile_index(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        profile.get("player_id"): profile
        for profile in canonical.get("player_health_profiles", []) or []
        if profile.get("player_id")
    }


def health_state_index(canonical: dict[str, Any], save: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source = save.get("health_states") or canonical.get("player_health_states", []) or []
    return {state.get("player_id"): state for state in source if state.get("player_id")}


def compact_health_risk(profile: dict[str, Any] | None, state: dict[str, Any] | None) -> float | None:
    if not profile and not state:
        return None
    profile = profile or {}
    state = state or {}
    durability = float(profile.get("durability") or 62.0)
    risk = max(0.0, 65.0 - durability) * 0.3
    if profile.get("injury_prone"):
        risk += 4.0
    risk += min(4.0, len(profile.get("major_prior_injuries") or []) * 1.4)
    risk += min(1.5, len(profile.get("body_area_risk_tags") or []) * 0.25)
    if state.get("availability_status") != "active":
        risk += 1.25
    risk += float(state.get("rust") or 0.0) * 0.035
    return round(clamp(risk, 0.0, 34.0), 1)


def player_health_context(
    save: dict[str, Any],
    player_id: str | None,
    team_id: str | None,
    profile: dict[str, Any] | None,
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    risk = compact_health_risk(profile, state)
    line = compact_per_game_line(save, player_id)
    if risk is None and not line.get("games"):
        return {}
    team_record = save.get("team_records", {}).get(team_id or "") or {}
    team_games = int(team_record.get("wins") or 0) + int(team_record.get("losses") or 0)
    player_games = int(line.get("games") or 0)
    missed_games = max(0, team_games - player_games) if team_games > 0 else 0
    evidence_parts: list[str] = []
    if player_games > 0 and team_games > 0:
        evidence_parts.append(f"{player_games}/{team_games} GP this season")
    elif player_games > 0:
        evidence_parts.append(f"{player_games} GP this season")
    if missed_games >= 8:
        evidence_parts.append(f"{missed_games} missed games")
    if risk is not None:
        evidence_parts.append(f"injury risk {risk:.1f}")
    if state and state.get("availability_status") and state.get("availability_status") != "active":
        evidence_parts.append(str(state.get("availability_status")))
    return {
        "games": player_games,
        "team_games": team_games,
        "missed_games": missed_games,
        "injury_risk": risk,
        "availability_status": (state or {}).get("availability_status", "active") if state else None,
        "evidence": f"[{', '.join(evidence_parts)}]" if evidence_parts else "",
    }


def team_playmaking_rating(
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_id: str,
    traits_by_player: dict[str, dict[str, float]],
) -> float:
    unavailable = set(save.get("free_agent_player_ids") or []) | set(save.get("retired_player_ids") or [])
    values: list[tuple[float, float]] = []
    for player in canonical.get("players", []) or []:
        if player.get("team_id") != team_id or player.get("id") in unavailable:
            continue
        minutes = compact_player_minutes(player)
        if minutes < 4:
            continue
        rating = compact_player_ratings(player, traits_by_player.get(player.get("id"), {})).get("playmaking", 50.0)
        values.append((float(rating), max(1.0, minutes)))
    if not values:
        return 50.0
    total = sum(weight for _, weight in values)
    return round(sum(value * weight for value, weight in values) / max(1.0, total), 1)


def team_playmaking_rankings(
    canonical: dict[str, Any],
    save: dict[str, Any],
    traits_by_player: dict[str, dict[str, float]],
) -> dict[str, dict[str, Any]]:
    rows = [
        (team.get("id"), team.get("abbrev"), team_playmaking_rating(canonical, save, team.get("id"), traits_by_player))
        for team in canonical.get("teams", []) or []
        if team.get("id")
    ]
    rows.sort(key=lambda row: (-float(row[2]), str(row[1] or "")))
    return {
        str(team_id): {"team": abbrev, "rank": index + 1, "rating": rating}
        for index, (team_id, abbrev, rating) in enumerate(rows)
    }


def conference_leader_context(
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_id: str | None,
    abbrev_by_id: dict[str, str],
) -> dict[str, Any]:
    teams_by_id, _ = team_maps(canonical)
    conference = (teams_by_id.get(team_id or "") or {}).get("conference")
    if not conference:
        return {}
    records = []
    for record in (save.get("team_records") or {}).values():
        record_team_id = record.get("team_id")
        team = teams_by_id.get(record_team_id or "")
        if not team or team.get("conference") != conference:
            continue
        wins = int(record.get("wins") or 0)
        losses = int(record.get("losses") or 0)
        if wins + losses <= 0:
            continue
        records.append(
            {
                "team_id": record_team_id,
                "team": record.get("team_abbrev") or abbrev_by_id.get(record_team_id),
                "wins": wins,
                "losses": losses,
                "win_pct": wins / max(1, wins + losses),
            }
        )
    records.sort(key=lambda row: (-float(row["win_pct"]), -int(row["wins"]), str(row["team"] or "")))
    leaders = [
        {"team": row["team"], "record": f"{row['wins']}-{row['losses']}", "seed": index + 1}
        for index, row in enumerate(records[:3])
    ]
    if not leaders:
        return {}
    return {
        "conference": conference,
        "leaders": leaders,
        "evidence": f"[{conference} top: " + ", ".join(f"{row['team']} {row['record']} #{row['seed']}" for row in leaders[:2]) + "]",
    }


def season_start_year(season: str | None) -> int:
    match = re.match(r"^(\d{4})", str(season or CANONICAL_SEASON))
    return int(match.group(1)) if match else 2025


def next_season_label(season: str | None, offset: int = 1) -> str:
    start = season_start_year(season) + offset
    return f"{start}-{str(start + 1)[-2:]}"


def cap_lines_for_narrative(season: str | None) -> dict[str, float]:
    elapsed = max(0, season_start_year(season) - season_start_year(CANONICAL_SEASON))
    factor = (1.0 + ANNUAL_CAP_GROWTH_RATE) ** elapsed
    return {
        "tax_line": round(TAX_LINE * factor / 100_000) * 100_000,
        "hard_cap": round(SECOND_APRON * factor / 100_000) * 100_000,
    }


def contract_salary_for_narrative(contract: dict[str, Any], season: str) -> float | None:
    for row in contract.get("seasons") or []:
        if isinstance(row, dict) and str(row.get("season")) == str(season):
            try:
                return float(row.get("salary") or 0.0)
            except (TypeError, ValueError):
                return None
    return None


def team_cap_snapshot(canonical: dict[str, Any], team_id: str | None, season: str) -> dict[str, Any]:
    if not team_id:
        return {}
    player_ids = {player.get("id") for player in canonical.get("players", []) or [] if player.get("team_id") == team_id}
    payroll = 0.0
    unresolved = 0
    for contract in canonical.get("contracts", []) or []:
        if contract.get("player_id") not in player_ids:
            continue
        salary = contract_salary_for_narrative(contract, season)
        if salary is None:
            unresolved += 1
        else:
            payroll += salary
    lines = cap_lines_for_narrative(season)
    tax_space = float(lines["tax_line"]) - payroll
    hard_space = float(lines["hard_cap"]) - payroll
    return {
        "season": season,
        "payroll_millions": round(payroll / 1_000_000, 1),
        "cap_space_millions": round(tax_space / 1_000_000, 1),
        "hard_cap_space_millions": round(hard_space / 1_000_000, 1),
        "unresolved_contracts": unresolved,
    }


def cap_context_for_extension(canonical: dict[str, Any], save: dict[str, Any], team_id: str | None) -> dict[str, Any]:
    current_season = str((save.get("meta") or {}).get("season") or CANONICAL_SEASON)
    seasons = [next_season_label(current_season, 1), next_season_label(current_season, 2)]
    rows = [team_cap_snapshot(canonical, team_id, season) for season in seasons]
    rows = [row for row in rows if row]
    if not rows:
        return {}
    snippet = "[Cap: " + "; ".join(
        f"{row['season']} payroll ${row['payroll_millions']:.1f}M, cap room ${row['cap_space_millions']:+.1f}M, hard-cap room ${row['hard_cap_space_millions']:+.1f}M"
        for row in rows
    ) + "]"
    return {"rows": rows, "posture": cap_posture_for_rows(rows), "evidence": snippet}


def cap_posture_for_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "unknown"
    row_states = []
    for row in rows:
        cap_room = float(row.get("cap_space_millions") or 0.0)
        hard_room = float(row.get("hard_cap_space_millions") or 0.0)
        if cap_room >= 18.0 and hard_room >= 30.0:
            row_states.append("healthy")
        elif cap_room <= 0.0 or hard_room <= 12.0:
            row_states.append("tight")
        else:
            row_states.append("mixed")
    if all(state == "healthy" for state in row_states):
        return "healthy_space"
    if any(state == "tight" for state in row_states) and any(state == "healthy" for state in row_states):
        return "mixed"
    if any(state == "tight" for state in row_states):
        return "tight"
    return "mixed"


def player_contract_salary_millions(player: dict[str, Any], season: str | None) -> float:
    contract = player.get("contract") or player.get("canonical_contract") or {}
    seasons = contract.get("seasons") if isinstance(contract, dict) else []
    if isinstance(seasons, list):
        for row in seasons:
            if isinstance(row, dict) and (not season or str(row.get("season")) == str(season)):
                try:
                    return round(float(row.get("salary") or 0.0) / 1_000_000, 1)
                except (TypeError, ValueError):
                    return 0.0
    for key in ("salary", "annual_salary", "aav", "aav_millions"):
        value = contract.get(key) if isinstance(contract, dict) else None
        try:
            salary = float(value)
        except (TypeError, ValueError):
            continue
        if salary > 1_000:
            salary /= 1_000_000
        return round(salary, 1)
    return 0.0


def asset_display_label(asset: dict[str, Any], players_by_id: dict[str, dict[str, Any]]) -> str:
    label = asset.get("label") or asset.get("name") or asset.get("headline_label") or asset.get("pick_label") or asset.get("swap_label")
    if label:
        return str(label)
    if asset.get("kind") == "player":
        player = players_by_id.get(asset.get("id") or asset.get("player_id"))
        return str(player.get("name") or asset.get("id") or "player")
    return str(asset.get("id") or asset.get("value") or asset.get("kind") or "asset")


def social_subject_asset_label(asset: dict[str, Any]) -> str:
    label = str(asset.get("label") or "asset").strip()
    if asset.get("kind") == "pick":
        base = label.split(";")[0].strip()
        if asset.get("protected") and "protected" not in base.lower():
            base = f"{base} (protected)"
        return base
    return label


def compact_asset_context(
    asset: dict[str, Any],
    canonical: dict[str, Any],
    save: dict[str, Any],
    players_by_id: dict[str, dict[str, Any]],
    traits_by_player: dict[str, dict[str, float]],
    active_season: str | None,
) -> dict[str, Any]:
    kind = str(asset.get("kind") or "")
    label = asset_display_label(asset, players_by_id)
    if kind == "player":
        player_id = asset.get("id") or asset.get("player_id")
        player = players_by_id.get(player_id, {})
        line = compact_per_game_line(save, player_id)
        return {
            "kind": "player",
            "id": player_id,
            "label": label,
            "name": player.get("name") or label,
            "position": player.get("position"),
            "minutes": compact_player_minutes(player),
            "season_line": line,
            "ratings": compact_player_ratings(player, traits_by_player.get(player_id, {})),
            "salary_millions": player_contract_salary_millions(player, active_season),
        }
    if kind == "pick":
        label_low = label.lower()
        protections = asset.get("protections") or asset.get("protection") or asset.get("protection_summary") or asset.get("_protection_label")
        is_protected = bool(protections) or "protected" in label_low
        round_value = int(asset.get("round") or 0)
        return {
            "kind": "pick",
            "id": asset.get("id") or asset.get("pick_id"),
            "label": label,
            "round": round_value,
            "season": asset.get("season"),
            "is_first_round": round_value == 1 or " r1 " in f" {label_low} ",
            "is_second_round": round_value == 2 or " r2 " in f" {label_low} ",
            "protected": is_protected,
            "protection_text": str(protections or "").strip()[:120],
        }
    if kind == "pick_swap":
        return {"kind": "pick_swap", "id": asset.get("id"), "label": label}
    return {"kind": kind or "asset", "label": label}


def weighted_asset_rating(assets: list[dict[str, Any]], key: str) -> float:
    values = []
    for asset in assets:
        if asset.get("kind") != "player":
            continue
        ratings = asset.get("ratings") or {}
        minutes = max(1.0, float(asset.get("minutes") or 0.0))
        values.append((float(ratings.get(key) or 50.0), minutes))
    if not values:
        return 0.0
    total_weight = sum(weight for _, weight in values)
    return round(sum(value * weight for value, weight in values) / max(1.0, total_weight), 1)


def team_aliases_for_context(team: dict[str, Any], abbrev: str | None) -> list[str]:
    aliases: list[str] = []
    if abbrev:
        aliases.append(str(abbrev))
    name = str(team.get("name") or "").strip()
    if name:
        aliases.append(name)
        parts = name.split()
        if len(parts) > 1:
            aliases.append(parts[-1])
            aliases.append(" ".join(parts[:-1]))
    return list(dict.fromkeys(alias for alias in aliases if alias))


def trade_side_analysis(
    team_id: str | None,
    receives: list[dict[str, Any]],
    sends: list[dict[str, Any]],
    abbrev_by_id: dict[str, str],
    teams_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    salary_in = sum(float(asset.get("salary_millions") or 0.0) for asset in receives if asset.get("kind") == "player")
    salary_out = sum(float(asset.get("salary_millions") or 0.0) for asset in sends if asset.get("kind") == "player")
    team_abbrev = abbrev_by_id.get(team_id or "", team_id)
    return {
        "team": team_abbrev,
        "team_aliases": team_aliases_for_context((teams_by_id or {}).get(team_id or "") or {}, team_abbrev),
        "receives": [asset.get("label") for asset in receives],
        "sends": [asset.get("label") for asset in sends],
        "incoming_players": [asset for asset in receives if asset.get("kind") == "player"],
        "outgoing_players": [asset for asset in sends if asset.get("kind") == "player"],
        "incoming_picks": [asset for asset in receives if asset.get("kind") == "pick"],
        "outgoing_picks": [asset for asset in sends if asset.get("kind") == "pick"],
        "deltas": {
            "salary_millions": round(salary_in - salary_out, 1),
            "spacing": round(weighted_asset_rating(receives, "spacing") - weighted_asset_rating(sends, "spacing"), 1),
            "creation": round(weighted_asset_rating(receives, "creation") - weighted_asset_rating(sends, "creation"), 1),
            "defense": round(weighted_asset_rating(receives, "defense") - weighted_asset_rating(sends, "defense"), 1),
            "overall": round(weighted_asset_rating(receives, "overall") - weighted_asset_rating(sends, "overall"), 1),
        },
    }


def trade_social_analysis(
    canonical: dict[str, Any],
    save: dict[str, Any],
    details: dict[str, Any],
    abbrev_by_id: dict[str, str],
    players_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    from_team_id = details.get("from_team_id")
    to_team_id = details.get("to_team_id")
    teams_by_id, _ = team_maps(canonical)
    active_season = (canonical.get("meta") or {}).get("active_season") or (save.get("meta") or {}).get("season")
    traits_by_player = trait_index(canonical)
    from_assets = [
        compact_asset_context(asset, canonical, save, players_by_id, traits_by_player, active_season)
        for asset in details.get("from_assets", []) or []
    ]
    to_assets = [
        compact_asset_context(asset, canonical, save, players_by_id, traits_by_player, active_season)
        for asset in details.get("to_assets", []) or []
    ]
    all_assets = [*from_assets, *to_assets]
    picks = [asset for asset in all_assets if asset.get("kind") == "pick"]
    protected_picks = [asset for asset in picks if asset.get("protected")]
    r1_count = sum(1 for asset in picks if asset.get("is_first_round"))
    r2_count = sum(1 for asset in picks if asset.get("is_second_round"))
    from_subject = ", ".join(social_subject_asset_label(asset) for asset in from_assets) or "future considerations"
    to_subject = ", ".join(social_subject_asset_label(asset) for asset in to_assets) or "future considerations"
    display_label = f"Trade: {abbrev_by_id.get(from_team_id, from_team_id)} sends {from_subject}; {abbrev_by_id.get(to_team_id, to_team_id)} sends {to_subject}."
    hooks = []
    if picks:
        if r1_count:
            hooks.append(f"{r1_count} first-round pick(s) involved")
        if r2_count and not r1_count:
            hooks.append(f"{r2_count} second-round pick(s) involved; do not treat one R2 as major capital")
        if protected_picks:
            hooks.append("protected pick language is present; only describe protection using the supplied labels")
    else:
        hooks.append("no picks involved; do not mention pick math")
    sides = [
        trade_side_analysis(to_team_id, from_assets, to_assets, abbrev_by_id, teams_by_id),
        trade_side_analysis(from_team_id, to_assets, from_assets, abbrev_by_id, teams_by_id),
    ]
    direction_facts = [
        f"{side.get('team')} receives {', '.join(str(asset.get('label') or asset.get('name')) for asset in side.get('incoming_players', [])[:3]) or 'no players'}; "
        f"sends {', '.join(str(asset.get('label') or asset.get('name')) for asset in side.get('outgoing_players', [])[:3]) or 'no players'}"
        for side in sides
    ]
    if direction_facts:
        hooks.append("Trade sides are exact: " + " | ".join(direction_facts))
    for side in sides:
        deltas = side.get("deltas") or {}
        if any(abs(float(deltas.get(key) or 0.0)) >= 4.0 for key in ["spacing", "creation", "defense", "overall"]):
            hooks.append(
                f"{side.get('team')} rating deltas from player assets: "
                f"OVR {float(deltas.get('overall') or 0.0):+0.1f}, spacing {float(deltas.get('spacing') or 0.0):+0.1f}, "
                f"creation {float(deltas.get('creation') or 0.0):+0.1f}, defense {float(deltas.get('defense') or 0.0):+0.1f}"
            )
        if abs(float(deltas.get("salary_millions") or 0.0)) >= 1.0:
            hooks.append(f"{side.get('team')} salary delta: {float(deltas.get('salary_millions') or 0.0):+0.1f}M this season")
    return {
        "kind": "trade",
        "display_label": display_label,
        "teams": {
            "from": abbrev_by_id.get(from_team_id or "", from_team_id),
            "to": abbrev_by_id.get(to_team_id or "", to_team_id),
        },
        "sides": sides,
        "asset_mix": {
            "players": sum(1 for asset in all_assets if asset.get("kind") == "player"),
            "picks": len(picks),
            "first_round_picks": r1_count,
            "second_round_picks": r2_count,
            "protected_picks": len(protected_picks),
            "has_picks": bool(picks),
            "has_protected_picks": bool(protected_picks),
        },
        "commentary_hooks": hooks[:6],
    }


def stat_line_social_analysis(
    save: dict[str, Any],
    details: dict[str, Any],
    players_by_id: dict[str, dict[str, Any]],
    abbrev_by_id: dict[str, str],
) -> dict[str, Any]:
    player_id = details.get("player_id")
    player = players_by_id.get(player_id, {})
    line = compact_per_game_line(save, player_id)
    team_id = player.get("team_id") or next(iter(details.get("team_ids") or []), None)
    return {
        "kind": "major_stat_line",
        "player": player.get("name") or player_id,
        "team": player.get("team_abbrev") or abbrev_by_id.get(team_id or ""),
        "stat": details.get("stat"),
        "value": details.get("value"),
        "season_line": line,
        "display_label": f"{player.get('name') or 'Player'} recorded {int(float(details.get('value') or 0))} {details.get('stat') or 'stats'} for {player.get('team_abbrev') or abbrev_by_id.get(team_id or '')}.",
        "commentary_hooks": [
            "React to the actual stat line and season context.",
            "Do not mention coaches, rotation changes, or teammates unless supplied in team_context.",
        ],
    }


def extension_position_bucket(position: str | None) -> str:
    pos = str(position or "").upper()
    if pos in {"PG", "SG", "G"}:
        return "backcourt"
    if pos in {"SF", "F", "PF"}:
        return "wing/frontcourt"
    if pos == "C":
        return "frontcourt"
    return "roster"


def extension_board_context(
    save: dict[str, Any],
    details: dict[str, Any],
    player_id: str | None,
    team_id: str | None,
    team_abbrev: str | None,
    players_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not team_id or not team_abbrev:
        return {}
    date_value = str(details.get("date") or "")
    events = []
    for event in save.get("league_events", []) or []:
        if event.get("kind") != "extension":
            continue
        if team_id not in set(event.get("team_ids") or []):
            continue
        if date_value and str(event.get("date") or "") != date_value:
            continue
        events.append(event)
    signed: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for event in events:
        event_details = event.get("details") or {}
        event_player_id = event_details.get("player_id") or next(iter(event.get("player_ids") or []), None)
        player = players_by_id.get(event_player_id or "")
        if not player:
            continue
        headline = str(event.get("headline") or "")
        row = {
            "player_id": event_player_id,
            "name": player.get("name"),
            "position": player.get("position"),
            "bucket": extension_position_bucket(player.get("position")),
        }
        if "unresolved" in headline.lower() or "stall" in headline.lower() or event_details.get("is_trade_demand") or event_details.get("team_passed_on_extension"):
            unresolved.append(row)
        elif "extends" in headline.lower() or event_details.get("contract"):
            signed.append(row)
    if player_id and not any(row.get("player_id") == player_id for row in signed):
        player = players_by_id.get(player_id)
        if player:
            signed.append(
                {
                    "player_id": player_id,
                    "name": player.get("name"),
                    "position": player.get("position"),
                    "bucket": extension_position_bucket(player.get("position")),
                }
            )
    unresolved = [row for row in unresolved if row.get("player_id") != player_id]
    if not unresolved:
        return {}
    signed_names = [str(row.get("name") or "player") for row in signed[:3]]
    unresolved_names = [str(row.get("name") or "player") for row in unresolved[:3]]
    buckets = sorted({str(row.get("bucket") or "roster") for row in unresolved if row.get("bucket")})
    money_text = f"{buckets[0]} money still undecided" if len(buckets) == 1 else "multiple extension priorities still undecided"
    snippet = (
        f"[{team_abbrev} extension board: "
        f"{', '.join(signed_names) or 'signed player'} signed; "
        f"{', '.join(unresolved_names)} unresolved; {money_text}]"
    )
    return {
        "signed": signed,
        "unresolved": unresolved,
        "position_buckets": buckets,
        "evidence": snippet,
    }


def extension_social_analysis(
    canonical: dict[str, Any],
    save: dict[str, Any],
    details: dict[str, Any],
    abbrev_by_id: dict[str, str],
    players_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    player_id = details.get("player_id") or next(iter(details.get("player_ids") or []), None)
    team_id = details.get("team_id") or next(iter(details.get("team_ids") or []), None)
    player = players_by_id.get(player_id or "", {})
    if not team_id and player:
        team_id = player.get("team_id")
    team_abbrev = abbrev_by_id.get(team_id or "", team_id)
    contract = details.get("contract") or details
    terms = contract_terms_summary(contract)
    traits_by_player = trait_index(canonical)
    ratings = expanded_rating_profile(player, traits_by_player.get(player_id or "", {})) if player else {}
    standout_context = standout_rating_context(ratings, player.get("position")) if ratings else {}
    health_context = player_health_context(
        save,
        player_id,
        team_id,
        health_profile_index(canonical).get(player_id or ""),
        health_state_index(canonical, save).get(player_id or ""),
    )
    playmaking_rank = team_playmaking_rankings(canonical, save, traits_by_player).get(team_id or "", {})
    cap_context = cap_context_for_extension(canonical, save, team_id)
    conference_context = conference_leader_context(canonical, save, team_id, abbrev_by_id)
    extension_board = extension_board_context(save, details, player_id, team_id, team_abbrev, players_by_id)
    player_playmaking = float(ratings.get("playmaking") or 0.0)
    evidence: list[str] = []
    optional_context: list[str] = []
    aav_millions = 0.0
    years = 0
    if terms:
        try:
            aav = contract.get("annual_salary") or contract.get("salary") or contract.get("aav") or contract.get("aav_millions")
            aav_millions = float(aav)
            if aav_millions > 1_000:
                aav_millions /= 1_000_000
        except (AttributeError, TypeError, ValueError):
            aav_millions = 0.0
        try:
            years = int(contract.get("years") or contract.get("original_contract_years") or contract.get("term_years") or 0)
        except (AttributeError, TypeError, ValueError):
            years = 0
        total = aav_millions * years if aav_millions and years else 0.0
        total_text = f", total ${total:.1f}M" if total else ""
        evidence.append(f"[Contract: {terms} AAV{total_text}]")
    if ratings:
        evidence.append(rating_snippet(ratings))
    if standout_context.get("evidence"):
        evidence.append(str(standout_context["evidence"]))
    if health_context.get("evidence") and (int(health_context.get("missed_games") or 0) >= 8 or float(health_context.get("injury_risk") or 0.0) >= 5.0 or health_context.get("availability_status") != "active"):
        evidence.append(str(health_context["evidence"]))
    if cap_context.get("evidence"):
        evidence.append(str(cap_context["evidence"]))
    if playmaking_rank:
        optional_context.append(
            f"[{team_abbrev} team playmaking rank #{int(playmaking_rank.get('rank') or 0)} league-wide; "
            f"{player.get('name') or 'player'} player PLY {player_playmaking:.0f}]"
        )
    if conference_context.get("evidence"):
        optional_context.append(str(conference_context["evidence"]))
    if extension_board.get("evidence"):
        optional_context.append(str(extension_board["evidence"]))
    display = details.get("headline") or f"{team_abbrev or 'Team'} extends {player.get('name') or 'Player'}"
    if terms and " x " not in str(display):
        display = str(display).rstrip(".") + f" to {terms}."
    hooks = [
        "The displayed money is annual average salary (AAV), not total contract value. Never divide it by years.",
        "If discussing player quality, cite the broad Ratings or Standouts snippet. Do not default to playmaking unless playmaking is the actual angle.",
        "If discussing cap pressure, use the supplied cap room and hard-cap room snippet. Never mention aprons.",
        "Only mention conference leaders if you are explicitly discussing the standings race, and only use the supplied same-conference context.",
        "Only mention extension-board context if discussing team-building priorities or unresolved teammate negotiations.",
        "If using team playmaking rank, make clear the rank belongs to the team. The player only has a player PLY rating, not a league rank.",
        "If discussing health, cite only supplied sim injury-risk or missed-games evidence. Do not mention normal early-season GP.",
    ]
    age = float(ratings.get("age") or player.get("age") or 0.0)
    end_age = age + max(0, years)
    if age >= 32:
        hooks.append("Older extension: do not call this player a future-core or PG-of-the-future piece.")
    if player.get("position") not in {"PG", "SG", "G"}:
        hooks.append("Player is not a guard; do not frame the extension as solving the backcourt.")
    return {
        "kind": "extension",
        "display_label": display,
        "team": team_abbrev,
        "player": {
            "id": player_id,
            "name": player.get("name"),
            "position": player.get("position"),
            "age": age,
            "contract_end_age": round(end_age, 1) if end_age else None,
            "minutes": compact_player_minutes(player) if player else 0.0,
            "ratings": ratings,
            "rating_standouts": standout_context.get("standouts") or [],
            "health": health_context,
        },
        "contract": {
            "terms": terms,
            "aav_millions": round(aav_millions, 1) if aav_millions else 0.0,
            "years": years,
            "display_amount_is": "AAV",
        },
        "team_metrics": {
            "record": compact_record(save.get("team_records", {}).get(team_id or "")),
            "playmaking_rank": playmaking_rank,
            "cap_context": cap_context,
            "conference_context": conference_context,
            "extension_board": extension_board,
        },
        "evidence_snippets": evidence[:6],
        "optional_context_snippets": optional_context[:4],
        "commentary_hooks": hooks,
    }


def social_analysis_packet(
    canonical: dict[str, Any],
    save: dict[str, Any],
    item: dict[str, Any],
    related_details: dict[str, Any],
    abbrev_by_id: dict[str, str],
    players_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    kind = str(item.get("kind") or "")
    event_kind = str(related_details.get("kind") or "")
    if kind == "trade" and related_details:
        return trade_social_analysis(canonical, save, related_details, abbrev_by_id, players_by_id)
    if kind == "player_high" and related_details:
        return stat_line_social_analysis(save, related_details, players_by_id, abbrev_by_id)
    if kind == "extension" and related_details:
        return extension_social_analysis(canonical, save, related_details, abbrev_by_id, players_by_id)
    return {}


def social_context_packet(canonical: dict[str, Any], save: dict[str, Any], item: dict[str, Any], team_id: str | None = None) -> dict[str, Any]:
    teams_by_id, abbrev_by_id = team_maps(canonical)
    players_by_id = player_maps(canonical)
    involved_team_ids = sorted({team for team in item.get("team_ids", []) if team})
    text = str(item.get("subject") or item.get("text") or "")
    for team in canonical.get("teams", []):
        abbrev = str(team.get("abbrev") or "")
        if abbrev and re.search(rf"\b{re.escape(abbrev)}\b", text):
            involved_team_ids.append(team.get("id"))
    related_event = related_league_event_for_social(save, item)
    for event_team_id in (related_event or {}).get("team_ids") or []:
        if event_team_id:
            involved_team_ids.append(event_team_id)
    involved_team_ids = sorted({team for team in involved_team_ids if team})
    involved_players = []
    involved_player_ids = [player_id for player_id in item.get("player_ids", []) or [] if player_id]
    for event_player_id in (related_event or {}).get("player_ids") or []:
        if event_player_id:
            involved_player_ids.append(event_player_id)
    for player_id in sorted(dict.fromkeys(involved_player_ids)):
        player = players_by_id.get(player_id)
        if player:
            involved_players.append({"id": player_id, "name": player.get("name"), "team": abbrev_by_id.get(player.get("team_id"))})
    standings = sorted(
        [
            {
                "team_id": record.get("team_id"),
                "team": record.get("team_abbrev") or abbrev_by_id.get(record.get("team_id")),
                **compact_record(record),
            }
            for record in save.get("team_records", {}).values()
        ],
        key=lambda row: (-float(row.get("win_pct") or 0.0), str(row.get("team") or "")),
    )[:10]
    related_details = dict((related_event or {}).get("details") or {})
    if related_event:
        related_details.setdefault("kind", related_event.get("kind"))
        related_details.setdefault("headline", related_event.get("headline"))
        related_details.setdefault("date", related_event.get("date"))
        related_details.setdefault("team_ids", related_event.get("team_ids") or [])
        related_details.setdefault("player_ids", related_event.get("player_ids") or [])
    analysis = social_analysis_packet(canonical, save, item, related_details, abbrev_by_id, players_by_id)
    stance = deterministic_social_stance(item.get("id") or item.get("subject") or item.get("text"))
    display_subject = analysis.get("display_label") or social_display_subject(item, related_details)
    return {
        "prompt_version": NARRATIVE_PROMPT_VERSION,
        "mode": "social",
        "date": item.get("date") or save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "source": {
            "id": item.get("id"),
            "kind": item.get("kind"),
            "subject": item.get("subject") or item.get("text"),
            "factual_text": item.get("text"),
            "display_subject": display_subject,
            "details": compact_event_details(related_details),
        },
        "involved_teams": [
            {"id": tid, "abbrev": abbrev_by_id.get(tid), "record": compact_record(save.get("team_records", {}).get(tid))}
            for tid in involved_team_ids
            if tid in teams_by_id
        ],
        "involved_players": involved_players,
        "team_context": [
            compact_team_context(canonical, save, tid, abbrev_by_id)
            for tid in involved_team_ids
            if tid in teams_by_id
        ],
        "analysis": analysis,
        "standings_top": standings,
        "stance": stance,
        "rules": [
            "Use only facts provided in this packet.",
            "Write about source.display_subject, not a different recent event.",
            "Do not mention real-world history, real-life personalities, or current NBA knowledge unless present here.",
            "You may discuss involved teams using team_context and standings_top, but every named player must be in source.display_subject, involved_players, or team_context.core_players.",
            "Do not invent injuries, trades, stats, teams, staff, or player traits.",
        ],
    }


def related_league_event_for_social(save: dict[str, Any], item: dict[str, Any]) -> dict[str, Any] | None:
    item_date = str(item.get("date") or "")
    item_kind = str(item.get("kind") or "")
    subject = str(item.get("subject") or item.get("text") or "")
    candidate_kinds = {item_kind}
    if item_kind == "player_high":
        candidate_kinds.add("major_stat_line")
    candidates = [
        event for event in save.get("league_events", [])
        if str(event.get("date") or "") == item_date
        and str(event.get("kind") or "") in candidate_kinds
    ]
    if len(candidates) == 1:
        return candidates[0]
    for event in candidates:
        headline = str(event.get("headline") or "")
        if headline and (headline in subject or subject in headline):
            return event
    return None


def social_display_subject(item: dict[str, Any], details: dict[str, Any]) -> str:
    subject = str(item.get("subject") or item.get("text") or "League chatter").strip()
    if str(item.get("kind") or "") == "extension":
        terms = contract_terms_summary(details.get("contract") or details)
        if terms and " x " not in subject:
            return subject.rstrip(".") + f" to {terms}."
    return subject


def compact_event_details(details: dict[str, Any]) -> dict[str, Any]:
    if not details:
        return {}
    allowed = {
        "aav_millions",
        "annual_salary",
        "years",
        "projected_aav_millions",
        "minutes_projection",
        "reason",
        "is_trade_demand",
        "staff_grade",
        "candidate_grade",
        "fired_staff_grade",
        "slot",
        "action",
        "stat",
        "value",
    }
    output = {key: value for key, value in details.items() if key in allowed and value not in (None, "", [], {})}
    if details.get("contract"):
        output["contract_terms"] = contract_terms_summary(details.get("contract") or {})
    return output


def contract_terms_summary(contract: dict[str, Any]) -> str:
    if not isinstance(contract, dict):
        return ""
    annual = contract.get("annual_salary") or contract.get("salary") or contract.get("aav") or contract.get("aav_millions")
    years = contract.get("years") or contract.get("original_contract_years") or contract.get("term_years")
    seasons = contract.get("seasons") or []
    if years is None and isinstance(seasons, list) and seasons:
        years = len(seasons)
    if annual is None and isinstance(seasons, list) and seasons:
        salaries = [float(row.get("salary") or 0.0) for row in seasons if isinstance(row, dict)]
        if salaries:
            annual = sum(salaries) / len(salaries)
    try:
        annual_m = float(annual)
        if annual_m > 1_000:
            annual_m /= 1_000_000
    except (TypeError, ValueError):
        annual_m = 0.0
    try:
        years_i = int(years)
    except (TypeError, ValueError):
        years_i = 0
    if annual_m <= 0 or years_i <= 0:
        return ""
    money = f"${annual_m:.0f}M" if abs(annual_m - round(annual_m)) < 0.05 else f"${annual_m:.1f}M"
    return f"{money} x {years_i}"


def press_context_packet(
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_id: str,
    event: dict[str, Any] | None,
    base_prompt: dict[str, Any],
) -> dict[str, Any]:
    teams_by_id, abbrev_by_id = team_maps(canonical)
    players_by_id = player_maps(canonical)
    team = teams_by_id.get(team_id, {})
    recent_logs = [
        log for log in save.get("team_game_logs", [])
        if log.get("team_id") == team_id
    ][-5:]
    rotation_player_ids = []
    for player in canonical.get("players", []):
        if player.get("team_id") == team_id and float(player.get("minutes_projection") or 0.0) >= 18:
            rotation_player_ids.append(player.get("id"))
    rotation = [
        {
            "id": pid,
            "name": players_by_id.get(pid, {}).get("name"),
            "position": players_by_id.get(pid, {}).get("position"),
        }
        for pid in rotation_player_ids[:8]
        if pid in players_by_id
    ]
    event_headlines = list((event or {}).get("headlines") or [])
    if not event_headlines and (event or {}).get("headline"):
        event_headlines = [str((event or {}).get("headline"))]
    standings = sorted(
        [
            {
                "team_id": record.get("team_id"),
                "team": record.get("team_abbrev") or abbrev_by_id.get(record.get("team_id")),
                **compact_record(record),
            }
            for record in save.get("team_records", {}).values()
        ],
        key=lambda row: (-float(row.get("win_pct") or 0.0), str(row.get("team") or "")),
    )[:10]
    return {
        "prompt_version": NARRATIVE_PROMPT_VERSION,
        "mode": "press",
        "date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "team": {
            "id": team_id,
            "abbrev": team.get("abbrev") or abbrev_by_id.get(team_id),
            "name": team.get("name"),
            "record": compact_record(save.get("team_records", {}).get(team_id)),
            "morale": save.get("team_morale", {}).get(team_id),
            "fan_confidence": save.get("fan_confidence", {}).get(team_id),
            "owner_confidence": save.get("owner_confidence", {}).get(team_id),
        },
        "event": deepcopy(event or {}),
        "event_headlines": event_headlines[:10],
        "aggregated_event_count": len(event_headlines),
        "topic": base_prompt.get("topic"),
        "base_reporters": base_prompt.get("reporters", []),
        "team_context": [compact_team_context(canonical, save, team_id, abbrev_by_id)],
        "standings_top": standings,
        "rotation_core": rotation,
        "recent_team_games": recent_logs,
        "recent_news": [
            {"date": item.get("date"), "kind": item.get("kind"), "headline": item.get("headline")}
            for item in save.get("news_items", [])[-8:]
        ],
        "rules": [
            "Use only facts provided in this packet.",
            "Do not mention real-world history, real-life personalities, or current NBA knowledge unless present here.",
            "Write answer choices that are challenging but solvable from the context.",
            "Never label the correct answer in visible text.",
        ],
    }


def stable_context_hash(context: dict[str, Any]) -> str:
    payload = json.dumps(context, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def deterministic_persona(source_id: str | None) -> dict[str, str]:
    digest = hashlib.sha256(str(source_id or "narrative").encode("utf-8")).hexdigest()
    return PERSONAS[int(digest[:2], 16) % len(PERSONAS)]


def cache_key(mode: str, source_id: str | None, context_hash: str, persona: str | None = None) -> str:
    return stable_id("narrative", NARRATIVE_PROMPT_VERSION, mode, source_id or "source", context_hash, persona or "")


def narrative_provider_cache_key(settings: dict[str, Any], provider: NarrativeProvider | None = None) -> str:
    provider_name = str(getattr(provider, "name", "") or settings.get("provider") or "ollama").lower()
    if provider_name == "ollama":
        return "|".join(
            [
                "ollama",
                str(settings.get("ollama_base_url") or "http://localhost:11434").rstrip("/"),
                str(settings.get("ollama_model") or "llama3.1"),
                f"tokens={int(settings.get('max_tokens') or 650)}",
                f"temp={float(settings.get('temperature') or 0.8):.3f}",
            ]
        )
    return provider_name


def cached_social_entry_for_source(cache: dict[str, Any], item: dict[str, Any], persona: dict[str, str], provider_key: str) -> dict[str, Any] | None:
    source_id = item.get("id")
    if not source_id:
        return None
    for entry in cache.values():
        if not isinstance(entry, dict):
            continue
        if entry.get("source_item_id") != source_id:
            continue
        if entry.get("prompt_version") != NARRATIVE_PROMPT_VERSION:
            continue
        if entry.get("handle") != persona.get("handle"):
            continue
        if entry.get("provider_key") != provider_key:
            continue
        return entry
    return None


def build_social_prompt(context: dict[str, Any], persona: dict[str, str]) -> str:
    stance = context.get("stance") or {}
    analysis = context.get("analysis") or {}
    asset_mix = analysis.get("asset_mix") or {}
    evidence = analysis.get("evidence_snippets") or []
    optional_context = analysis.get("optional_context_snippets") or []
    return (
        "You are writing one in-universe NBA GM sandbox social media post.\n"
        "Return only JSON with keys: text, author, handle, persona.\n"
        f"Use this fixed account exactly: {persona['author']} {persona['handle']} ({persona['persona']}).\n"
        f"Style: {persona['style']}.\n"
        f"Required opinion stance: {stance.get('label', 'balanced')} - {stance.get('instruction', 'name one upside and one risk')}.\n"
        "The post must be about source.display_subject. Treat that as the event label the user will see before the post.\n"
        "Do not repeat source.display_subject or restate the transaction as your first sentence; the UI prints that label separately.\n"
        "Take a clear opinion and give a concrete basketball/cap/draft reason using analysis.commentary_hooks when available.\n"
        "You may discuss the current roster/standings context only when it is present in team_context or standings_top.\n"
        "The user likes concise bracketed proof. When analysis.evidence_snippets is non-empty, include at least one exact snippet from that list.\n"
        "If you discuss ratings, health, injury risk, missed games, cap room, hard-cap room, position, age timeline, or contract value, copy the relevant exact bracketed snippet.\n"
        "optional_context_snippets are optional. Use them only if your sentence explicitly discusses that exact topic; never paste a conference/top-seed or extension-board snippet onto an unrelated cap or player-rating take.\n"
        "For contract extensions, source.display_subject shows AAV x years. The dollar figure is annual average salary, not total value. Never divide it by years.\n"
        "This game models cap space and hard-cap room, not NBA aprons. Never use apron, second apron, apron pain, or apron tax language.\n"
        "Do not add player/staff names that are not explicitly in source.display_subject, involved_players, or team_context.core_players.\n"
        "Do not add team names that are not explicitly in source.display_subject, involved_teams, team_context, or standings_top.\n"
        f"Pick facts: has_picks={bool(asset_mix.get('has_picks'))}, protected_picks={int(asset_mix.get('protected_picks') or 0)}, first_round_picks={int(asset_mix.get('first_round_picks') or 0)}, second_round_picks={int(asset_mix.get('second_round_picks') or 0)}.\n"
        "If has_picks is false, do not mention picks, pick math, draft capital, swaps, or protections.\n"
        "If protected_picks is 0, do not call any pick protected.\n"
        "If only one second-round pick is involved, treat it as minor value unless analysis says otherwise.\n"
        "For trades, use analysis.sides as the authority: incoming_players are what that team receives, outgoing_players are what it sends.\n"
        "Never say a team acquired, received, traded for, or overpaid for a player it actually sent away.\n"
        "Never say a team sent, moved, shipped out, or gave up a player it actually received.\n"
        "If mentioning player salary or contract money in a trade, use only salary_millions from analysis.sides or exact salary-delta hooks.\n"
        "For trades, say what each team is plausibly trying to accomplish: fit, salary, timeline, rotation, value, or picks.\n"
        "Vary length naturally: sometimes one punchy sentence under 90 characters, sometimes 2-4 short sentences when the evidence needs room.\n"
        "Use slang only when it fits the persona. Mix positive, skeptical, funny, excited, and analytical reads across posts.\n"
        "Avoid bland phrases like 'roster construction implications', 'watching closely', 'time will tell', or 'interesting move'.\n"
        f"Exact evidence snippets available: {json.dumps(evidence, ensure_ascii=False)}.\n"
        f"Optional context snippets: {json.dumps(optional_context, ensure_ascii=False)}.\n"
        f"Hard rules: use only supplied sim facts; do not invent outside NBA knowledge; keep under {SOCIAL_TEXT_MAX_CHARS} characters; no hashtags.\n"
        f"Context JSON:\n{json.dumps(context, sort_keys=True, ensure_ascii=False)}"
    )


def build_press_prompt(context: dict[str, Any]) -> str:
    return (
        "You are designing one in-universe press conference mini-game for an NBA GM sandbox.\n"
        "Return only JSON with keys: reporter and answers.\n"
        "reporter must have name, beat, question.\n"
        "answers must contain exactly four objects with line, tone, quality, rationale.\n"
        "tone must be one of accountable, optimistic, deflect, challenge.\n"
        "quality must be one of good, mixed, bad. Include at least two good/mixed and at least one bad.\n"
        "Visible lines must not say they are good, bad, safe, correct, wrong, or optimal.\n"
        "Tie the question to event_headlines, team_context, recent_team_games, and standings_top. Avoid generic wording.\n"
        "If the event aggregates multiple moves, ask about the pattern or strategy across the moves, not just one headline.\n"
        "For a trade, ask what roster problem the move solves. For a head-coach hire/fire, ask what changes on the floor or in accountability.\n"
        "Vary answer length: one terse quote, two medium quotes, one longer quote. Make the answers plausibly tempting, not obvious.\n"
        "Hard rules: use only supplied sim facts; do not invent outside NBA knowledge; keep each answer under 260 characters.\n"
        f"Context JSON:\n{json.dumps(context, sort_keys=True, ensure_ascii=False)}"
    )


def fallback_social_payload(item: dict[str, Any], persona: dict[str, str]) -> dict[str, Any]:
    details = ((item.get("narrative") or {}).get("source_details") or {})
    stance = ((item.get("narrative") or {}).get("stance") or {})
    analysis = ((item.get("narrative") or {}).get("analysis") or {})
    stance_label = str(stance.get("label") or "balanced")
    kind = str(item.get("kind") or "social")
    if kind == "trade":
        hooks = analysis.get("commentary_hooks") or []
        hook = str(hooks[0]) if hooks else ""
        if analysis.get("asset_mix", {}).get("has_picks") is False:
            base = "This is about role fit, money, and whether the rotation actually gets cleaner."
        elif analysis.get("asset_mix", {}).get("second_round_picks") == 1 and not analysis.get("asset_mix", {}).get("first_round_picks"):
            base = "One second-rounder is seasoning, not the whole meal. The player fit has to be the real story."
        elif hook:
            base = hook
        else:
            base = "There is upside here, but the rotation answer has to be more than vibes."
        if stance_label in {"positive", "excited"}:
            text = f"I see the idea. {base}"
        elif stance_label == "skeptical":
            text = f"I need the basketball reason to show up fast. {base}"
        else:
            text = base
    elif kind in {"extension", "contract", "free_agent_signing", "free_agency_signing"}:
        snippets = analysis.get("evidence_snippets") or []
        rating_snippet = next((snippet for snippet in snippets if "OVR" in str(snippet)), "")
        health_snippet = next((snippet for snippet in snippets if "injury risk" in str(snippet).lower() or "GP" in str(snippet)), "")
        contract_snippet = next((snippet for snippet in snippets if "Contract:" in str(snippet)), "")
        proof = rating_snippet or health_snippet or contract_snippet
        proof_suffix = f" {proof}" if proof else ""
        if stance_label in {"positive", "excited"}:
            text = f"Good teams keep the right guys before the market gets weird.{proof_suffix}"
        elif stance_label == "skeptical":
            text = f"Fine if the role is real. Ugly if this is just paying for comfort.{proof_suffix}"
        else:
            text = f"Fair swing if the role holds; expensive if the fit slips.{proof_suffix}"
    elif kind in {"staff_hire", "staff_fire"}:
        if stance_label in {"positive", "excited"}:
            text = "Fresh voice, fresh accountability. Sometimes that matters more than the quote sheet."
        elif stance_label == "skeptical":
            text = "Job security meter just learned a new language."
        else:
            text = "The staff room changed; now the results have to justify the noise."
    elif kind == "injury":
        text = "Depth is not a slogan anymore; it is the whole assignment."
    elif kind == "player_high":
        stat = (analysis.get("stat") or "box-score").replace("_", " ")
        line = analysis.get("season_line") or {}
        if int(line.get("games") or 0) > 0:
            text = (
                f"That {stat} spike hits harder with the season line at "
                f"{float(line.get('ppg') or 0.0):.1f}/{float(line.get('rpg') or 0.0):.1f}/{float(line.get('apg') or 0.0):.1f}."
            )
        else:
            text = f"That {stat} spike is loud enough on its own. The box score did the talking."
    else:
        text = "The agenda merchants have enough material to be annoying and maybe right."
    return {
        "text": text[:SOCIAL_TEXT_MAX_CHARS].rstrip(),
        "author": persona["author"],
        "handle": persona["handle"],
        "persona": persona["persona"],
        "source": "fallback",
    }


def fallback_press_payload(context: dict[str, Any]) -> dict[str, Any]:
    team = (context.get("team") or {}).get("abbrev") or "the team"
    topic = str(context.get("topic") or "the current situation")
    event = context.get("event") or {}
    headline = event.get("headline") or topic
    team_record = (context.get("team") or {}).get("record") or {}
    record_text = f"{int(team_record.get('wins') or 0)}-{int(team_record.get('losses') or 0)}"
    if int(context.get("aggregated_event_count") or 0) > 1:
        headline = f"{team} made {context.get('aggregated_event_count')} related moves"
        question = f"{headline}. At {record_text}, what is the through-line connecting these decisions?"
    elif "Trade completed" in str(headline) or "trades" in str(headline).lower():
        question = f"{headline}. What roster problem was this trade supposed to solve for {team}?"
    elif "Head Coach" in str(headline) or "head coach" in str(headline).lower():
        question = f"{headline}. What should change first for {team}: role clarity, standards, or late-game decisions?"
    elif "extends" in str(headline).lower():
        question = f"{headline}. How are you balancing loyalty, price, and future flexibility at {record_text}?"
    else:
        question = f"{headline}. What is the basketball reason this matters for {team} right now?"
    return {
        "reporter": {
            "name": "Dana Price",
            "beat": "front-office accountability",
            "question": question,
        },
        "answers": [
            {
                "tone": "accountable",
                "quality": "good",
                "line": f"We made this because the current version of {team} needed a clearer basketball answer, not just a cleaner headline.",
                "rationale": "Takes responsibility and links the move to roster needs.",
            },
            {
                "tone": "optimistic",
                "quality": "mixed",
                "line": "I like the upside, but nobody gets credit for winning the transaction scroll. It has to show up in roles and results.",
                "rationale": "Reasonable optimism, though a little broad.",
            },
            {
                "tone": "challenge",
                "quality": "mixed",
                "line": f"The standard is not optional at {record_text}. If this move does not sharpen our habits, then we missed the point.",
                "rationale": "Sets a standard but risks adding pressure.",
            },
            {
                "tone": "deflect",
                "quality": "bad",
                "line": "We are not going to litigate details publicly. The outside reaction does not change what we do in the building.",
                "rationale": "Too evasive for a moment that needs context.",
            },
        ],
        "source": "fallback",
    }


def validate_no_unsupported_team_abbrevs(text: str, context: dict[str, Any], all_abbrevs: set[str]) -> bool:
    allowed = {str(team.get("abbrev")) for team in context.get("involved_teams", []) if team.get("abbrev")}
    if context.get("team", {}).get("abbrev"):
        allowed.add(str(context["team"]["abbrev"]))
    for team in context.get("team_context", []) or []:
        if team.get("team"):
            allowed.add(str(team.get("team")))
    for row in context.get("standings_top", []):
        if row.get("team"):
            allowed.add(str(row.get("team")))
    allowed.update({"NBA", "GM", "PPG", "RPG", "APG"})
    tokens = set(re.findall(r"\b[A-Z]{2,4}\b", text or ""))
    return not any(token in all_abbrevs and token not in allowed for token in tokens)


def alias_appears(alias: str, text: str) -> bool:
    if not alias or not text:
        return False
    flags = 0 if alias.isupper() and len(alias) <= 3 else re.IGNORECASE
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, flags=flags) is not None


def canonical_person_aliases(canonical: dict[str, Any]) -> set[str]:
    names: list[str] = []
    for player in canonical.get("players", []):
        if player.get("name"):
            names.append(str(player["name"]))
    for staff in (canonical.get("staff_profiles") or []) + (canonical.get("gameplay_staff_slots") or []):
        if staff.get("name"):
            names.append(str(staff["name"]))
    token_counts: dict[str, int] = {}
    token_source: dict[str, str] = {}
    for name in names:
        tokens = [token for token in re.findall(r"[A-Za-z][A-Za-z'.-]*", name) if token.lower() not in {"jr", "sr", "ii", "iii", "iv"}]
        for token in tokens:
            token_counts[token.lower()] = token_counts.get(token.lower(), 0) + 1
            token_source[token.lower()] = token
    aliases: set[str] = set()
    for name in names:
        clean = " ".join(str(name).split())
        if len(clean) >= 4:
            aliases.add(clean)
        tokens = [token for token in re.findall(r"[A-Za-z][A-Za-z'.-]*", clean) if token.lower() not in {"jr", "sr", "ii", "iii", "iv"}]
        for token in tokens:
            key = token.lower()
            if token_counts.get(key) == 1 and (len(token) >= 4 or token.isupper()):
                aliases.add(token_source.get(key, token))
    return aliases


def social_allowed_person_text(context: dict[str, Any]) -> str:
    source = context.get("source") or {}
    pieces = [
        source.get("subject"),
        source.get("factual_text"),
        source.get("display_subject"),
    ]
    pieces.extend(player.get("name") for player in context.get("involved_players", []) if player.get("name"))
    for team in context.get("team_context", []) or []:
        for player in team.get("core_players", []) or []:
            pieces.append(player.get("name"))
    analysis = context.get("analysis") or {}
    for side in analysis.get("sides", []) or []:
        for asset in [*(side.get("incoming_players") or []), *(side.get("outgoing_players") or [])]:
            pieces.append(asset.get("name") or asset.get("label"))
    if isinstance(analysis.get("player"), dict):
        pieces.append((analysis.get("player") or {}).get("name"))
    elif analysis.get("player"):
        pieces.append(analysis.get("player"))
    extension_board = ((analysis.get("team_metrics") or {}).get("extension_board") or {})
    for row in [*(extension_board.get("signed") or []), *(extension_board.get("unresolved") or [])]:
        pieces.append(row.get("name"))
    return " ".join(str(piece) for piece in pieces if piece)


def press_allowed_person_text(context: dict[str, Any]) -> str:
    event = context.get("event") or {}
    pieces = [
        context.get("topic"),
        event.get("headline"),
        " ".join(str(headline) for headline in context.get("event_headlines", []) if headline),
    ]
    pieces.extend(player.get("name") for player in context.get("rotation_core", []) if player.get("name"))
    return " ".join(str(piece) for piece in pieces if piece)


def validate_no_unsupported_person_names(text: str, context: dict[str, Any], canonical: dict[str, Any]) -> bool:
    aliases = canonical_person_aliases(canonical)
    if not aliases:
        return True
    allowed_text = social_allowed_person_text(context) if context.get("mode") == "social" else press_allowed_person_text(context)
    for alias in aliases:
        if alias_appears(alias, text) and not alias_appears(alias, allowed_text):
            return False
    return True


def has_banned_narrative_claim(text: str) -> bool:
    low = str(text or "").lower()
    banned = [
        "real life",
        "irl",
        "in reality",
        "last year's actual",
        "according to espn",
        "nba.com reports",
        "react to the actual game",
        "do not mention",
        "use only supplied",
        "context json",
        "hard rules:",
        "roster construction implications",
        "watching closely",
        "time will tell",
        "interesting move",
        "tom thibodeau",
        "thibodeau",
    ]
    return any(token in low for token in banned)


def clean_generated_social_text(text: str) -> str:
    cleaned = " ".join(str(text or "").split())
    cleaned = re.sub(r"\[\d+\]", "", cleaned).strip()
    cleaned = re.sub(r"\bages?\s+(\d+(?:\.\d+)?),\s*\[age\s+\1(?:\.0)?\]", r"age \1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bage\s+(\d+)\.0\b", r"age \1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:second\s+apron|first\s+apron|tax\s+apron|apron\s+pain|apron)\b", "hard-cap pressure", cleaned, flags=re.IGNORECASE)
    if cleaned.startswith("["):
        close = cleaned.find("]")
        content = cleaned[1:close] if close > 0 else ""
        known_snippet = re.match(r"^(?:Contract|Ratings|Standouts|Cap|East top|West top|[A-Z]{2,3} PLY)", content)
        remainder = cleaned[close + 1:].lstrip() if close > 0 else ""
        if close > 0 and not known_snippet and (close > 72 or close >= len(cleaned) - 1 or remainder.startswith("[")):
            cleaned = f"{content}{cleaned[close + 1:]}".strip()
    return cleaned


def text_has_exact_snippet(text: str, snippets: list[Any]) -> bool:
    return any(str(snippet) and str(snippet) in str(text or "") for snippet in snippets)


def text_without_known_snippets(text: str, analysis: dict[str, Any]) -> str:
    stripped = str(text or "")
    for snippet in [*(analysis.get("evidence_snippets") or []), *(analysis.get("optional_context_snippets") or [])]:
        if snippet:
            stripped = stripped.replace(str(snippet), "")
    return stripped


def uses_optional_context_irrelevantly(text: str, analysis: dict[str, Any]) -> bool:
    optional = [str(snippet) for snippet in analysis.get("optional_context_snippets") or [] if str(snippet)]
    if not optional:
        return False
    body = text_without_known_snippets(text, analysis).lower()
    for snippet in optional:
        if snippet not in text:
            continue
        snippet_low = snippet.lower()
        if " top:" in snippet_low:
            if not any(token in body for token in ["standings", "seed", "conference", "east", "west", "race", "contend", "playoff", "chase", "top of"]):
                return True
            if re.search(r"\b(?:east|west)\s+top\s+teams?['’]?\s+(?:rotation|spacing|fit|depth)", body):
                return True
        if "extension board:" in snippet_low and not any(
            token in body
            for token in ["extension", "talk", "priority", "priorities", "team-building", "money", "roster", "backcourt", "frontcourt", "wing", "guard"]
        ):
            return True
    return False


def unsupported_cap_pressure_claim(text: str, analysis: dict[str, Any]) -> bool:
    cap_context = ((analysis.get("team_metrics") or {}).get("cap_context") or {})
    rows = cap_context.get("rows") or []
    posture = str(cap_context.get("posture") or cap_posture_for_rows(rows)).lower()
    if posture != "healthy_space":
        return False
    low = str(text or "").lower()
    pressure_patterns = [
        "cap trouble",
        "tough cap spot",
        "cap crunch",
        "cap squeeze",
        "cap pressure",
        "hard-cap pressure",
        "hard cap pressure",
        "flexibility is already taking a hit",
        "future flexibility is already taking a hit",
        "mortgaged",
    ]
    if not any(pattern in low for pattern in pressure_patterns):
        return False
    room_language = ["still has room", "room to maneuver", "room to work", "space to work", "healthy space", "tons of space"]
    return not any(pattern in low for pattern in room_language)


def misstates_team_rank_as_player_rank(text: str, analysis: dict[str, Any]) -> bool:
    if analysis.get("kind") != "extension":
        return False
    player = analysis.get("player") or {}
    player_name = str(player.get("name") or "").strip()
    team_metrics = analysis.get("team_metrics") or {}
    team_rank = (team_metrics.get("playmaking_rank") or {}).get("rank")
    if not player_name or not team_rank:
        return False
    low = str(text or "").lower()
    try:
        rank_i = int(team_rank)
    except (TypeError, ValueError):
        return False
    rank_patterns = [rf"#\s*{rank_i}", ordinal_text(rank_i)]
    name_tokens = [token for token in re.findall(r"[A-Za-z][A-Za-z'.-]*", player_name) if token.lower() not in {"jr", "sr", "ii", "iii", "iv"}]
    aliases = [player_name]
    if name_tokens:
        aliases.append(name_tokens[-1])
    for alias in aliases:
        alias_pattern = re.escape(alias.lower())
        for rank_pattern in rank_patterns:
            if re.search(rf"{alias_pattern}[^.\n]{{0,80}}(?:ply|playmaking|playmaker)[^.\n]{{0,40}}(?:rank|ranked)?\s*{rank_pattern}", low):
                return True
            if re.search(rf"{alias_pattern}[^.\n]{{0,80}}(?:rank|ranked)\s*{rank_pattern}[^.\n]{{0,40}}(?:ply|playmaking|playmaker)", low):
                return True
    if re.search(rf"\b(?:he|she|they|you|player)\b[^.\n]{{0,60}}(?:ply|playmaking|playmaker)[^.\n]{{0,40}}(?:rank|ranked)?\s*(?:#\s*{rank_i}|{ordinal_text(rank_i)})", low):
        return True
    return False


def ordinal_text(value: int) -> str:
    suffix = "th"
    if value % 100 not in {11, 12, 13}:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def social_asset_aliases(asset: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    for key in ["name", "label"]:
        value = str(asset.get(key) or "").strip()
        if value:
            aliases.append(value)
    name = str(asset.get("name") or "").strip()
    tokens = [token for token in re.findall(r"[A-Za-z][A-Za-z'.-]*", name) if token.lower() not in {"jr", "sr", "ii", "iii", "iv"}]
    if len(tokens) >= 2 and len(tokens[-1]) >= 4:
        aliases.append(tokens[-1])
    return list(dict.fromkeys(alias for alias in aliases if len(alias) >= 3))


def near_team_asset_claim(text: str, team_alias: str, asset_alias: str, verbs: list[str]) -> bool:
    if not team_alias or not asset_alias:
        return False
    verb_pattern = "|".join(verbs)
    team = re.escape(team_alias)
    asset = re.escape(asset_alias)
    return re.search(
        rf"(?<![A-Za-z0-9]){team}(?![A-Za-z0-9])[^.\n]{{0,120}}\b(?:{verb_pattern})\b[^.\n]{{0,90}}(?<![A-Za-z0-9]){asset}(?![A-Za-z0-9])",
        text,
        flags=re.IGNORECASE,
    ) is not None


def wrong_trade_direction_claim(text: str, analysis: dict[str, Any]) -> bool:
    if analysis.get("kind") != "trade":
        return False
    receive_verbs = [
        "gets?",
        "receives?",
        "adds?",
        "lands?",
        "acquires?",
        "trades?\\s+for",
        "traded\\s+for",
        "overpays?\\s+for",
        "overpaid\\s+for",
        "paid\\s+for",
        "brings?\\s+in",
    ]
    send_verbs = [
        "sends?",
        "sent",
        "ships?",
        "shipped",
        "moves?",
        "moved",
        "trades?\\s+away",
        "traded\\s+away",
        "gives?\\s+up",
        "gave\\s+up",
        "giving\\s+up",
    ]
    for side in analysis.get("sides") or []:
        team_aliases = [str(alias) for alias in side.get("team_aliases") or [side.get("team")] if str(alias)]
        incoming_aliases = [alias for asset in side.get("incoming_players") or [] for alias in social_asset_aliases(asset)]
        outgoing_aliases = [alias for asset in side.get("outgoing_players") or [] for alias in social_asset_aliases(asset)]
        for team_alias in team_aliases:
            for alias in incoming_aliases:
                if near_team_asset_claim(text, team_alias, alias, send_verbs):
                    return True
            for alias in outgoing_aliases:
                if near_team_asset_claim(text, team_alias, alias, receive_verbs):
                    return True
    return False


def unsupported_trade_salary_claim(text: str, analysis: dict[str, Any]) -> bool:
    if analysis.get("kind") != "trade" or "$" not in str(text or ""):
        return False
    low = str(text or "").lower()
    if not any(token in low for token in ["salary", "contract", "cap", "money", "payroll", "dollar", "$"]):
        return False
    allowed_amounts: list[float] = []
    for side in analysis.get("sides") or []:
        deltas = side.get("deltas") or {}
        try:
            delta = abs(float(deltas.get("salary_millions") or 0.0))
            if delta >= 0.1:
                allowed_amounts.append(delta)
        except (TypeError, ValueError):
            pass
        for asset in [*(side.get("incoming_players") or []), *(side.get("outgoing_players") or [])]:
            try:
                amount = float(asset.get("salary_millions") or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
            if amount > 0:
                allowed_amounts.append(amount)
    if not allowed_amounts:
        return True
    for match in re.finditer(r"\$([0-9]+(?:\.[0-9]+)?)\s*(m|million|mil)?", str(text or ""), flags=re.IGNORECASE):
        try:
            mentioned = float(match.group(1))
        except (TypeError, ValueError):
            continue
        unit = str(match.group(2) or "").lower()
        if not unit and mentioned > 1_000:
            mentioned /= 1_000_000
        if not any(abs(mentioned - allowed) <= 0.75 for allowed in allowed_amounts):
            return True
    return False


def violates_extension_context_claims(text: str, context: dict[str, Any], canonical: dict[str, Any]) -> bool:
    low = str(text or "").lower()
    analysis = context.get("analysis") or {}
    if analysis.get("kind") != "extension":
        return False
    snippets = analysis.get("evidence_snippets") or []
    if snippets and not text_has_exact_snippet(text, snippets):
        return True
    if uses_optional_context_irrelevantly(text, analysis):
        return True
    if unsupported_cap_pressure_claim(text, analysis):
        return True
    if misstates_team_rank_as_player_rank(text, analysis):
        return True
    player = analysis.get("player") or {}
    contract = analysis.get("contract") or {}
    health = player.get("health") or {}
    team_metrics = analysis.get("team_metrics") or {}
    extension_board = team_metrics.get("extension_board") or {}
    position = str(player.get("position") or "").upper()
    age = float(player.get("age") or 0.0)
    aav = float(contract.get("aav_millions") or 0.0)
    for match in re.finditer(r"\$([0-9]+(?:\.[0-9]+)?)\s*m\s*(?:aav|annually|per year)", low, flags=re.IGNORECASE):
        try:
            mentioned = float(match.group(1))
        except (TypeError, ValueError):
            continue
        if aav > 0 and abs(mentioned - aav) > 0.75:
            return True
    for pattern in [
        r"annual\s+avg(?:erage)?\s+of\s+\$([0-9]+(?:\.[0-9]+)?)\s*m",
        r"annual\s+average\s+of\s+\$([0-9]+(?:\.[0-9]+)?)\s*m",
    ]:
        match = re.search(pattern, low, flags=re.IGNORECASE)
        if match:
            mentioned = float(match.group(1))
            if aav > 0 and abs(mentioned - aav) > 0.75:
                return True
    if aav > 0 and re.search(r"roughly\s+\$([0-9]+(?:\.[0-9]+)?)\s*m\s+aav", low, flags=re.IGNORECASE):
        mentioned = float(re.search(r"roughly\s+\$([0-9]+(?:\.[0-9]+)?)\s*m\s+aav", low, flags=re.IGNORECASE).group(1))
        if abs(mentioned - aav) > 0.75:
            return True
    health_terms = ["injury", "injured", "health", "healthy", "durability", "availability", "full season", "stay on the floor", "stay healthy"]
    if any(term in low for term in health_terms):
        health_snippets = [
            snippet for snippet in snippets
            if "injury risk" in str(snippet).lower() or " gp" in f" {str(snippet).lower()}" or "/82 gp" in str(snippet).lower() or "availability" in str(snippet).lower()
        ]
        if not health.get("evidence") or not text_has_exact_snippet(text, health_snippets):
            return True
    missed_games = int(health.get("missed_games") or 0)
    misleading_low_missed_phrases = [
        "only played",
        "just played",
        "barely played",
        "hasn't played a full season",
        "has not played a full season",
        "hasn't even played a full season",
        "has not even played a full season",
        "can't stay on the floor",
        "cannot stay on the floor",
    ]
    if missed_games < 8 and any(phrase in low for phrase in misleading_low_missed_phrases):
        return True
    if missed_games < 8 and re.search(r"\b(?:only|just|barely)\s+\d+\s+(?:gp|games?)\b", low):
        return True
    if missed_games < 8 and any(phrase in low for phrase in ["missed a lot", "missed time", "has missed games", "missed games"]) and "hasn't missed" not in low and "has not missed" not in low:
        return True
    board_buckets = {str(bucket) for bucket in extension_board.get("position_buckets") or []}
    backcourt_supported_by_board = "backcourt" in board_buckets and "extension board:" in low
    if position not in {"PG", "SG", "G"} and any(term in low for term in ["backcourt", "guard of", "pg of", "sg of"]) and not backcourt_supported_by_board:
        return True
    if position in {"PG", "SG", "G"} and "frontcourt" in low:
        return True
    if age >= 32 and any(term in low for term in ["of the future", "future core", "future pg", "future guard", "long-term cornerstone"]):
        return True
    team_record = team_metrics.get("record") or {}
    win_pct = float(team_record.get("win_pct") or 0.0)
    games = int(team_record.get("wins") or 0) + int(team_record.get("losses") or 0)
    if games >= 6 and win_pct < 0.45 and any(term in low for term in ["playoff push", "playoff chase", "contender", "contention"]):
        return True
    team_conferences = {
        str(team.get("abbrev")): str(team.get("conference") or "")
        for team in canonical.get("teams", []) or []
        if team.get("abbrev")
    }
    tokens = set(re.findall(r"\b[A-Z]{2,4}\b", text or ""))
    if "east" in low and any(team_conferences.get(token) == "West" for token in tokens):
        return True
    if "west" in low and any(team_conferences.get(token) == "East" for token in tokens):
        return True
    return False


def violates_social_context_claims(text: str, context: dict[str, Any], canonical: dict[str, Any]) -> bool:
    low = str(text or "").lower()
    analysis = context.get("analysis") or {}
    asset_mix = analysis.get("asset_mix") or {}
    if violates_extension_context_claims(text, context, canonical):
        return True
    if analysis.get("kind") == "trade":
        if wrong_trade_direction_claim(text, analysis):
            return True
        if unsupported_trade_salary_claim(text, analysis):
            return True
        has_picks = bool(asset_mix.get("has_picks"))
        if not has_picks and any(token in low for token in ["pick math", "draft capital", "protected", "protection", "swap", "r1", "r2", "second-round pick", "first-round pick"]):
            return True
        if int(asset_mix.get("protected_picks") or 0) <= 0 and any(token in low for token in ["protected", "protection"]):
            return True
        if int(asset_mix.get("first_round_picks") or 0) <= 0 and any(token in low for token in ["first-round", "1st round", " r1 "]):
            return True
    return False


def repeats_social_subject(text: str, context: dict[str, Any]) -> bool:
    subject = str((context.get("source") or {}).get("display_subject") or "").strip().rstrip(".")
    cleaned = str(text or "").strip()
    if not subject or len(subject) < 12:
        return False
    return cleaned.lower().startswith(subject.lower())


def strip_social_subject_prefix(text: str, context: dict[str, Any]) -> str:
    subject = str((context.get("source") or {}).get("display_subject") or "").strip()
    if not subject:
        return text
    stripped_subject = subject.rstrip(".")
    cleaned = str(text or "").strip()
    if cleaned.lower().startswith(subject.lower()):
        return cleaned[len(subject):].lstrip(" .:-")
    if stripped_subject and cleaned.lower().startswith(stripped_subject.lower()):
        return cleaned[len(stripped_subject):].lstrip(" .:-")
    return cleaned


def preferred_extension_evidence_snippet(text: str, analysis: dict[str, Any]) -> str:
    low = str(text or "").lower()
    snippets = [str(snippet) for snippet in analysis.get("evidence_snippets") or [] if str(snippet)]
    if not snippets:
        return ""
    def first_matching(*tokens: str) -> str:
        return next((snippet for snippet in snippets if any(token in snippet.lower() for token in tokens)), "")

    if any(term in low for term in ["injury", "health", "healthy", "durability", "availability", "full season", "missed", "floor"]):
        return first_matching("injury risk", " gp", "missed games", "availability") or snippets[0]
    if any(term in low for term in ["east", "west", "conference", "seed", "standings"]):
        optional = [str(snippet) for snippet in analysis.get("optional_context_snippets") or [] if str(snippet)]
        return next((snippet for snippet in optional if " top:" in snippet.lower()), "") or snippets[0]
    if any(term in low for term in ["playmaking", "ply", "backcourt", "guard", "creation", "table-set"]):
        return first_matching("ratings:", "standouts:") or snippets[0]
    if any(term in low for term in ["cap", "hard-cap", "salary", "money", "deal", "price", "value", "contract", "aav", "$"]):
        if any(term in low for term in ["cap", "hard-cap", "salary", "pressure", "flexibility", "room"]):
            return first_matching("cap:") or first_matching("contract:") or snippets[0]
        return first_matching("contract:") or snippets[0]
    if any(term in low for term in ["rating", "offense", "defense", "both ends", "stud", "talent", "role", "fit"]):
        return first_matching("standouts:", "ratings:") or snippets[0]
    return first_matching("standouts:", "ratings:") or snippets[0]


def append_required_social_evidence(text: str, context: dict[str, Any]) -> str:
    analysis = context.get("analysis") or {}
    if analysis.get("kind") != "extension":
        return text
    snippets = analysis.get("evidence_snippets") or []
    if not snippets or text_has_exact_snippet(text, snippets):
        return text
    snippet = preferred_extension_evidence_snippet(text, analysis)
    if not snippet:
        return text
    candidate = f"{text.rstrip()} {snippet}".strip()
    if len(candidate) <= SOCIAL_TEXT_MAX_CHARS:
        return candidate
    room = max(24, SOCIAL_TEXT_MAX_CHARS - len(snippet) - 1)
    shortened = text[:room].rstrip(" .,;:")
    return f"{shortened} {snippet}".strip()


def validate_social_payload(payload: dict[str, Any], context: dict[str, Any], canonical: dict[str, Any], persona: dict[str, str]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    text = " ".join(strip_social_subject_prefix(clean_generated_social_text(str(payload.get("text") or "")), context).split())
    text = append_required_social_evidence(text, context)
    if len(text) < 12 or len(text) > SOCIAL_TEXT_MAX_CHARS or has_banned_narrative_claim(text) or violates_social_context_claims(text, context, canonical) or repeats_social_subject(text, context):
        return None
    all_abbrevs = {str(team.get("abbrev")) for team in canonical.get("teams", []) if team.get("abbrev")}
    if not validate_no_unsupported_team_abbrevs(text, context, all_abbrevs):
        return None
    if not validate_no_unsupported_person_names(text, context, canonical):
        return None
    return {
        "text": text,
        "author": persona["author"],
        "handle": persona["handle"],
        "persona": persona["persona"],
        "source": str(payload.get("source") or "ollama"),
    }


def visible_answer_label(line: str) -> bool:
    low = line.lower()
    return not any(word in low for word in ["correct answer", "wrong answer", "best answer", "bad answer", "optimal answer"])


def validate_press_payload(payload: dict[str, Any], context: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    reporter = payload.get("reporter")
    answers = payload.get("answers")
    if not isinstance(reporter, dict) or not isinstance(answers, list) or len(answers) != 4:
        return None
    question = " ".join(str(reporter.get("question") or "").split())
    if len(question) < 20 or len(question) > 260 or has_banned_narrative_claim(question):
        return None
    topic = str(context.get("topic") or "").lower()
    headline = str((context.get("event") or {}).get("headline") or "").lower()
    question_low = question.lower()
    if topic and not any(token in question_low for token in topic.split()[:3]) and headline:
        headline_tokens = [token for token in re.findall(r"[a-z0-9]+", headline) if len(token) >= 4]
        if headline_tokens and not any(token in question_low for token in headline_tokens[:6]):
            return None
    cleaned_answers: list[dict[str, Any]] = []
    quality_counts = {"good": 0, "mixed": 0, "bad": 0}
    seen_lines: set[str] = set()
    for answer in answers:
        if not isinstance(answer, dict):
            return None
        line = " ".join(str(answer.get("line") or "").split())
        tone = str(answer.get("tone") or "").strip().lower()
        quality = str(answer.get("quality") or "").strip().lower()
        rationale = " ".join(str(answer.get("rationale") or "").split())
        if (
            len(line) < 20
            or len(line) > 280
            or line in seen_lines
            or tone not in ALLOWED_PRESS_TONES
            or quality not in ALLOWED_PRESS_QUALITIES
            or has_banned_narrative_claim(line)
            or not visible_answer_label(line)
        ):
            return None
        seen_lines.add(line)
        quality_counts[quality] += 1
        cleaned_answers.append({"line": line, "tone": tone, "quality": quality, "rationale": rationale[:220]})
    if quality_counts["bad"] < 1 or quality_counts["good"] + quality_counts["mixed"] < 2:
        return None
    all_abbrevs = {str(team.get("abbrev")) for team in canonical.get("teams", []) if team.get("abbrev")}
    combined = " ".join([question, *[answer["line"] for answer in cleaned_answers]])
    if not validate_no_unsupported_team_abbrevs(combined, context, all_abbrevs):
        return None
    if not validate_no_unsupported_person_names(combined, context, canonical):
        return None
    return {
        "reporter": {
            "name": " ".join(str(reporter.get("name") or "Dana Price").split())[:60],
            "beat": " ".join(str(reporter.get("beat") or "league accountability").split())[:80],
            "question": question,
        },
        "answers": cleaned_answers,
        "source": str(payload.get("source") or "ollama"),
    }


def social_cache_entry(
    canonical: dict[str, Any],
    save: dict[str, Any],
    item: dict[str, Any],
    team_id: str | None = None,
    provider: NarrativeProvider | None = None,
) -> dict[str, Any]:
    ensure_narrative_state(save)
    persona = deterministic_persona(item.get("id") or item.get("subject"))
    context = social_context_packet(canonical, save, item, team_id=team_id)
    context_hash = stable_context_hash(context)
    settings = save["narrative_settings"]
    active_provider = provider or provider_from_settings(settings)
    provider_key = narrative_provider_cache_key(settings, active_provider)
    key = cache_key("social", item.get("id"), context_hash, f"{persona['handle']}:{provider_key}")
    cache = save.setdefault("narrative_cache", {}).setdefault("social", {})
    existing_entry = cached_social_entry_for_source(cache, item, persona, provider_key)
    if existing_entry is not None:
        return existing_entry
    if key in cache:
        return cache[key]
    payload = None
    source = "fallback"
    if settings.get("enabled"):
        try:
            payload = active_provider.generate_json(build_social_prompt(context, persona), settings)
            source = getattr(active_provider, "name", "ollama")
        except NarrativeProviderError:
            payload = None
    if payload is None:
        payload = fallback_social_payload(
            {
                **item,
                "narrative": {
                    "source_details": context.get("source", {}).get("details") or {},
                    "stance": context.get("stance") or {},
                    "analysis": context.get("analysis") or {},
                },
            },
            persona,
        )
        source = "fallback"
    validated = validate_social_payload({**payload, "source": source}, context, canonical, persona)
    if validated is None:
        validated = fallback_social_payload(
            {
                **item,
                "narrative": {
                    "source_details": context.get("source", {}).get("details") or {},
                    "stance": context.get("stance") or {},
                    "analysis": context.get("analysis") or {},
                },
            },
            persona,
        )
    entry = {
        **validated,
        "id": key,
        "source_item_id": item.get("id"),
        "display_subject": context.get("source", {}).get("display_subject") or item.get("subject"),
        "analysis": context.get("analysis") or {},
        "context_hash": context_hash,
        "prompt_version": NARRATIVE_PROMPT_VERSION,
        "provider_key": provider_key,
    }
    cache[key] = entry
    return entry


def hydrate_social_items(
    canonical: dict[str, Any],
    save: dict[str, Any],
    items: list[dict[str, Any]],
    team_id: str | None = None,
    provider: NarrativeProvider | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Lazily enrich a bounded visible slice and report cache mutation."""
    ensure_narrative_state(save)
    before = json.dumps(save.get("narrative_cache", {}).get("social", {}), sort_keys=True)
    if not save.get("narrative_settings", {}).get("enabled"):
        return items, False
    max_items = int(save["narrative_settings"].get("max_posts_per_view") or 8)
    hydrated: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if index < max_items and item.get("kind") != "social_digest_marker":
            entry = social_cache_entry(canonical, save, item, team_id=team_id, provider=provider)
            hydrated.append({**item, **{key: entry[key] for key in ["text", "author", "handle", "persona"]}, "narrative": entry})
        else:
            hydrated.append(item)
    after = json.dumps(save.get("narrative_cache", {}).get("social", {}), sort_keys=True)
    return hydrated, before != after


def press_cache_entry(
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_id: str,
    event: dict[str, Any] | None,
    base_prompt: dict[str, Any],
    provider: NarrativeProvider | None = None,
) -> dict[str, Any]:
    ensure_narrative_state(save)
    context = press_context_packet(canonical, save, team_id, event, base_prompt)
    context_hash = stable_context_hash(context)
    source_id = (event or {}).get("id") or base_prompt.get("topic") or team_id
    settings = save["narrative_settings"]
    active_provider = provider or provider_from_settings(settings)
    provider_key = narrative_provider_cache_key(settings, active_provider)
    key = cache_key("press", str(source_id), context_hash, provider_key)
    cache = save.setdefault("narrative_cache", {}).setdefault("press", {})
    if key in cache:
        return cache[key]
    payload = None
    source = "fallback"
    if settings.get("enabled"):
        try:
            payload = active_provider.generate_json(build_press_prompt(context), settings)
            source = getattr(active_provider, "name", "ollama")
        except NarrativeProviderError:
            payload = None
    if payload is None:
        payload = fallback_press_payload(context)
        source = "fallback"
    validated = validate_press_payload({**payload, "source": source}, context, canonical)
    if validated is None:
        validated = fallback_press_payload(context)
    entry = {
        **validated,
        "id": key,
        "source_event_id": source_id,
        "context_hash": context_hash,
        "prompt_version": NARRATIVE_PROMPT_VERSION,
        "provider_key": provider_key,
    }
    cache[key] = entry
    return entry
