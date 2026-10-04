from datetime import datetime, timezone

from .jolpicaSource import ResultsNotAvailable, rate_limited_get

BASE_URL = "https://api.openf1.org/v1/"


def _get(endpoint: str, params: dict):
    response = rate_limited_get(f"{BASE_URL}{endpoint}", params=params, timeout=10)
    # During any live F1 session OpenF1 answers 401 to unauthenticated
    # clients, past sessions included: treat it as "retry later"
    if response.status_code == 401:
        raise ResultsNotAvailable(
            f"OpenF1 locked while a live session is in progress: {response.text}"
        )
    return response


def get_starting_grid(
    season: int, session_name: str, session_start: datetime | None
) -> list[dict]:
    """
    Return the official starting grid (penalties included).
    OpenF1 ties it to the qualifying session: session_name is
    "Qualifying" for the Grand Prix or "Sprint Qualifying" for the sprint.
    """
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

    grid_r = _get("starting_grid", {"session_key": session_key})
    # OpenF1 answers 404 until the grid is published
    if grid_r.status_code == 404:
        grid = []
    else:
        grid_r.raise_for_status()
        grid = grid_r.json()
    if not grid:
        raise ResultsNotAvailable(
            f"Starting grid not yet available for session {session_key}"
        )

    return [
        {"driver_number": g["driver_number"], "position": g["position"]} for g in grid
    ]
