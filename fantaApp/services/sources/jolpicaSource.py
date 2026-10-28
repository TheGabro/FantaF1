from .base import rate_limited_get

BASE_URL = "https://api.jolpi.ca/ergast/f1/"


def get_drivers(season: int) -> list[dict]:
    drivers_url = f"{BASE_URL}{season}/drivers.json?limit=100"
    driver_r = rate_limited_get(drivers_url, timeout=10)
    driver_r.raise_for_status()
    drivers: list[dict] = []
    for d in driver_r.json()["MRData"]["DriverTable"]["Drivers"]:
        diver_id = d["driverId"]
        constructor_url = f"{BASE_URL}{season}/drivers/{diver_id}/constructors"
        constructor_r = rate_limited_get(constructor_url, timeout=10)
        constructor_r.raise_for_status()
        costructor = constructor_r.json()["MRData"]["ConstructorTable"]["Constructors"][
            0
        ]
        short_name = d["code"] if "code" in d and d["code"] else diver_id[:3].upper()
        permanent_number = d.get("permanentNumber")
        drivers.append(
            {
                "drivers_api_id": d["driverId"],
                "first_name": d["givenName"],
                "last_name": d["familyName"],
                "number": int(permanent_number) if permanent_number else None,
                "short_name": short_name,
                "team": costructor["constructorId"],
            }
        )
    return drivers


def get_teams(season: int) -> list[dict]:
    teams_url = f"{BASE_URL}{season}/constructors"
    teams_r = rate_limited_get(teams_url, timeout=10)
    teams_r.raise_for_status()
    teams: list[dict] = []
    for c in teams_r.json()["MRData"]["ConstructorTable"]["Constructors"]:
        teams.append(
            {
                "name": c["name"],
                "nationality": c["nationality"],
                "constructor_api_id": c["constructorId"],
                "short_name": c["name"][:3].upper(),
            }
        )

    return teams


def get_circuits(season: int) -> list[dict]:
    circuits_url = f"{BASE_URL}{season}/circuits"
    circuits_r = rate_limited_get(circuits_url, timeout=10)
    circuits_r.raise_for_status()
    circuits: list[dict] = []
    for c in circuits_r.json()["MRData"]["CircuitTable"]["Circuits"]:
        circuits.append(
            {
                "name": c["circuitName"],
                "country": c["Location"]["country"],
                "location": c["Location"]["locality"],
                "circuit_api_id": c["circuitId"],
            }
        )

    return circuits


def get_weekends(season: int) -> list[dict]:
    race_url = f"{BASE_URL}{season}/races"
    race_r = rate_limited_get(race_url, timeout=10)
    race_r.raise_for_status()
    races: list[dict] = []
    for r in race_r.json()["MRData"]["RaceTable"]["Races"]:
        race = {
            "circuit_api_id": r["Circuit"]["circuitId"],
            "event_name": r["raceName"],
            "round_number": int(r["round"]),
            "fp1_start": f"{r['FirstPractice']['date']} {r['FirstPractice']['time']}",
            "qualifying_start": f"{r['Qualifying']['date']} {r['Qualifying']['time']}",
            "race_start": f"{r['date']} {r['time']}",
        }
        if "Sprint" in r:
            race["weekend_type"] = "sprint"
            race["sprint_qualifying_start"] = (
                f"{r['SprintQualifying']['date']} {r['SprintQualifying']['time']}"
            )
            race["sprint_start"] = f"{r['Sprint']['date']} {r['Sprint']['time']}"
        else:
            race["weekend_type"] = "regular"
            race["fp2_start"] = (
                f"{r['SecondPractice']['date']} {r['SecondPractice']['time']}"
            )
            race["fp3_start"] = (
                f"{r['ThirdPractice']['date']} {r['ThirdPractice']['time']}"
            )

        races.append(race)

    return races


def get_driver_standings(season: int, round: int) -> list[dict]:
    standings_url = f"{BASE_URL}{season}/{round}/driverStandings"
    standings_r = rate_limited_get(standings_url, timeout=10)
    standings_r.raise_for_status()
    standings: list[dict] = []
    last_position = 0
    for s in standings_r.json()["MRData"]["StandingsTable"]["StandingsLists"][0][
        "DriverStandings"
    ]:
        standing = {
            "driver_api_id": s["Driver"]["driverId"],
            "position": int(s["position"]) if "position" in s else last_position + 1,
            "points": int(s["points"]) if "points" in s else 0,
            "wins": int(s["wins"]) if "wins" in s else 0,
        }
        standings.append(standing)
        last_position += 1

    return standings
