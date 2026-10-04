from datetime import datetime, timezone

from .jolpicaSource import ResultsNotAvailable, rate_limited_get

BASE_URL = "https://api.openf1.org/v1/"


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

    sessions_r = rate_limited_get(
        f"{BASE_URL}sessions",
        params={"year": season, "session_name": session_name},
        timeout=10,
    )
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

    grid_r = rate_limited_get(
        f"{BASE_URL}starting_grid",
        params={"session_key": session_key},
        timeout=10,
    )
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
