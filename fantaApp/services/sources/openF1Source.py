from datetime import datetime, timedelta, timezone

from .base import ResultsNotAvailable, rate_limited_get

BASE_URL = "https://api.openf1.org/v1/"

# OpenF1 session name and Weekend start field for each event type
QUALIFYING_SESSION = {
    "regular": ("Qualifying", "qualifying_start"),
    "sprint": ("Sprint Qualifying", "sprint_qualifying_start"),
}
RACE_SESSION = {
    "regular": ("Race", "race_start"),
    "sprint": ("Sprint", "sprint_start"),
}


def _get(endpoint: str, params: dict):
    response = rate_limited_get(f"{BASE_URL}{endpoint}", params=params, timeout=10)
    # During any live F1 session OpenF1 answers 401 to unauthenticated
    # clients, past sessions included: treat it as "retry later"
    if response.status_code == 401:
        raise ResultsNotAvailable(
            f"OpenF1 locked while a live session is in progress: {response.text}"
        )
    return response


def _session_key(season: int, session_name: str, session_start: datetime | None) -> int:
    if session_start is None:
        raise ResultsNotAvailable(
            f"{session_name} start date not set for season {season}"
        )

    sessions_r = _get("sessions", {"year": season, "session_name": session_name})
    sessions_r.raise_for_status()

    # OpenF1 returns ISO dates with offset, compare the day in UTC
    target_day = session_start.astimezone(timezone.utc).date()
    session_key = next(
        (
            s["session_key"]
            for s in sessions_r.json()
            if datetime.fromisoformat(s["date_start"]).astimezone(timezone.utc).date()
            == target_day
        ),
        None,
    )
    if session_key is None:
        raise ResultsNotAvailable(
            f"{session_name} session on {target_day} not found on OpenF1"
        )
    return session_key


def _fetch(endpoint: str, session_key: int) -> list[dict]:
    response = _get(endpoint, {"session_key": session_key})
    # OpenF1 answers 404 until the data is published
    if response.status_code == 404:
        data = []
    else:
        response.raise_for_status()
        data = response.json()
    if not data:
        raise ResultsNotAvailable(
            f"{endpoint} not yet available for session {session_key}"
        )
    return data


def _fill_positions(rows: list[dict]) -> list[dict]:
    """
    Unclassified drivers have no numeric position (None, "RT"): put them after
    the classified ones, in OpenF1 order (laps completed), as Jolpica does.
    """
    last = max((r["position"] for r in rows if isinstance(r["position"], int)), default=0)
    for r in rows:
        if not isinstance(r["position"], int):
            last += 1
            r["position"] = last
    return rows


def _seconds(value: float | None) -> timedelta | None:
    return timedelta(seconds=value) if value is not None else None


def _status(row: dict) -> str:
    """Map OpenF1 flags to RaceResult.STATUS_CHOICES."""
    if row["dsq"]:
        return "Disqualified"
    if row["dns"]:
        return "Did not start"
    if row["dnf"]:
        return "Retired"
    # Lapped drivers have "+1 LAP" instead of a gap in seconds
    if isinstance(row["gap_to_leader"], str):
        return "Lapped"
    return "Finished"


def get_starting_grid(
    season: int, session_name: str, session_start: datetime | None
) -> list[dict]:
    """
    Return the official starting grid (penalties included).
    OpenF1 ties it to the qualifying session: session_name is
    "Qualifying" for the Grand Prix or "Sprint Qualifying" for the sprint.
    """
    grid = _fetch("starting_grid", _session_key(season, session_name, session_start))
    return [
        {"driver_number": g["driver_number"], "position": g["position"]} for g in grid
    ]


def get_qualifying_result(
    season: int, session_name: str, session_start: datetime | None
) -> list[dict]:
    """session_name is "Qualifying" or "Sprint Qualifying"."""
    rows = _fill_positions(
        _fetch("session_result", _session_key(season, session_name, session_start))
    )
    results = []
    for r in rows:
        # duration holds the Q1, Q2, Q3 best laps in seconds
        q1, q2, q3 = r["duration"] or (None, None, None)
        results.append(
            {
                "driver_number": r["driver_number"],
                "position": r["position"],
                "q1_time": _seconds(q1),
                "q2_time": _seconds(q2),
                "q3_time": _seconds(q3),
            }
        )
    return results


def get_race_result(
    season: int, session_name: str, session_start: datetime | None
) -> list[dict]:
    """session_name is "Race" or "Sprint"."""
    session_key = _session_key(season, session_name, session_start)
    rows = _fill_positions(_fetch("session_result", session_key))

    fastest: dict[int, dict] = {}
    for lap in _fetch("laps", session_key):
        if lap["lap_duration"] is None:
            continue
        best = fastest.get(lap["driver_number"])
        if best is None or lap["lap_duration"] < best["lap_duration"]:
            fastest[lap["driver_number"]] = lap

    results = []
    for r in rows:
        lap = fastest.get(r["driver_number"])
        results.append(
            {
                "driver_number": r["driver_number"],
                "position": r["position"],
                "points": int(r.get("points") or 0),
                "status": _status(r),
                "best_lap": lap["lap_number"] if lap else None,
                "fast_lap": _seconds(lap["lap_duration"]) if lap else None,
            }
        )
    return results
