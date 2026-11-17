"""Read-only, request-local simulation telemetry; never part of a saved game."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from threading import Event
from typing import Callable, Any

_listener: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar("simulation_progress", default=None)
_stop_event: ContextVar[Event | None] = ContextVar("simulation_stop_event", default=None)


@contextmanager
def progress_listener(callback, *, stop_event: Event | None = None):
    token = _listener.set(callback)
    stop_token = _stop_event.set(stop_event)
    try:
        yield
    finally:
        _stop_event.reset(stop_token)
        _listener.reset(token)


def progress_listener_active() -> bool:
    return _listener.get() is not None


def simulation_stop_requested() -> bool:
    event = _stop_event.get()
    return bool(event and event.is_set())


def emit_progress(save, kind, *, game=None, series_id=None, rotation=None, team_signals=None, opponent=None, calendar=None):
    callback = _listener.get()
    if callback is None:
        return
    event = {"kind":kind, "date":save.get("state", {}).get("current_date"),
             "phase":save.get("state", {}).get("phase")}
    if game:
        event["game"] = {key:game.get(key) for key in ("game_id", "home_team_id", "away_team_id", "home_score", "away_score")}
    if rotation is not None:
        event["rotation"] = rotation
    if team_signals is not None:
        event["team_signals"] = team_signals
    if opponent is not None:
        event["opponent"] = opponent
    if calendar is not None:
        event["calendar"] = calendar
    if series_id:
        event["series_id"] = series_id
    if save.get("playoff_state"):
        event["playoffs"] = deepcopy(save["playoff_state"])
    try:
        callback(event)
    except Exception:
        # A lost browser or failed observer must not change simulation outcomes.
        pass
