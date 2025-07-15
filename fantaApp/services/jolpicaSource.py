import requests
import time

# ── Simple module‑level rate‑limiter ────────────────────────────────────
_RATE_LIMIT_SEC = 0.35                # max ~3 requests per second
_last_call_ts = 0.0                   # perf_counter timestamp of last call

def rate_limited_get(url: str, **kwargs):
    """
    Wrapper attorno a requests.get che assicura di non superare
    ~3 req/sec (Jolpica ne permette 4).  Usa perf_counter per
    gestire anche chiamate molto ravvicinate.
    """
    global _last_call_ts
    now = time.perf_counter()
    elapsed = now - _last_call_ts
    if elapsed < _RATE_LIMIT_SEC:
        time.sleep(_RATE_LIMIT_SEC - elapsed)
    response = requests.get(url, **kwargs)
    _last_call_ts = time.perf_counter()
    return response

BASE_URL = 'https://api.jolpi.ca/ergast/f1/'


def get_drivers(season:int) -> list[dict]:
    drivers_url = f"{BASE_URL}{season}/drivers.json"
    driver_r = rate_limited_get(drivers_url, timeout=10)
    driver_r.raise_for_status()
    drivers : list[dict] = []
    for d in driver_r.json()["MRData"]["DriverTable"]["Drivers"]:
        diver_id = d["driverId"]
        constructor_url = f"{BASE_URL}/2025/drivers/{diver_id}/constructors"
        constructor_r = rate_limited_get(constructor_url, timeout = 10)
        constructor_r.raise_for_status()
        costructor = constructor_r.json()["MRData"]["ConstructorTable"]["Constructors"][0]
        drivers.append({
            "drivers_api_id": d["driverId"],
            "first_name": d["givenName"],
            "last_name":  d["familyName"],
            "number":     d["permanentNumber"],
            "short_name": d["code"],
            "team": costructor["constructorId"]
        })
    return drivers 

def get_teams(season:int) -> list[dict]:
    teams_url = f"{BASE_URL}{season}/constructors"
    teams_r = rate_limited_get(teams_url, timeout = 10)
    teams_r.raise_for_status()
    teams : list[dict] = []
    for c in teams_r.json()["MRData"]["ConstructorTable"]["Constructors"]:
        teams.append({
            "name": c['name'],
            "nationality":c['nationality'],
            "constructor_api_id": c['constructorId'],
            "short_name": c['name'][:3].upper()
            }
        )

    return teams

def get_circuits(season: int) -> list[dict]:
    circuits_url = f'{BASE_URL}{season}/circuits'
    circuits_r = rate_limited_get(circuits_url, timeout = 10)
    circuits_r.raise_for_status()
    circuits : list[dict] = []
    for c in circuits_r.json()["MRData"]["CircuitTable"]["Circuits"]:
        circuits.append({
            "name": c["circuitName"],
            "country": c["Location"]["country"],
            "location": c["Location"]["locality"],
            "circuit_api_id": c["circuitId"]
        })
        
    return circuits
        
def get_weekends(season:int) -> list[dict]:
    race_url = f'{BASE_URL}{season}/races'
    race_r = rate_limited_get(race_url, timeout=10)
    race_r.raise_for_status()
    races : list[dict] = []
    for r in race_r.json()['MRData']['RaceTable']['Races']:
        race = {
            "circuit_api_id": r["Circuit"]["circuitId"],
            "event_name": r["raceName"],
            "round_number": int(r["round"]),
            "fp1_start": f"{r['FirstPractice']['date']} {r['FirstPractice']['time']}",
            "qualifying_start": f"{r['Qualifying']['date']} {r['Qualifying']['time']}",
            "race_start": f"{r['date']} {r['time']}",
        }
        if 'Sprint' in r :
            race["race_type"] = "sprint"
            race["sprint_qualifying_start"] = f"{r['SprintQualifying']['date']} {r['SprintQualifying']['time']}"
            race["sprint_start"] = f"{r['Sprint']['date']} {r['Sprint']['time']}"
        else:
            race["race_type"] = "regular"
            race["fp2_start"] = f"{r['SecondPractice']['date']} {r['SecondPractice']['time']}"
            race["fp3_start"] = f"{r['ThirdPractice']['date']} {r['ThirdPractice']['time']}"
            
        races.append(race)
        
    return races

def get_qualifying_result(season : int, round :int) -> list[dict]:
    qualy_url = f"{BASE_URL}{season}/{round}/qualifying"
    qualy_r = rate_limited_get(qualy_url, timeout=10)
    qualy_r.raise_for_status()
    qualy_results : list[dict] = []
    for q in qualy_r.json()['MRData']['RaceTable']['Races'][0]['QualifyingResults']:
        driver_quali = {
            "driver_api_id": q["Driver"]["driverId"],
            "position": q["position"],
        }
        if 'Q1' in q:
            driver_quali["q1_time"] = q["Q1"]
        else:
            driver_quali["q1_time"] = None
        if 'Q2' in q:
            driver_quali["q2_time"] = q["Q2"]
        else:
            driver_quali["q2_time"] = None
        if 'Q3' in q:
            driver_quali["q3_time"] = q["Q3"]
        else:
            driver_quali["q3_time"] = None
        
        qualy_results.append(driver_quali)

    return qualy_results


def get_race_result(season: int, round: int) -> list[dict]:
    race_url = f"{BASE_URL}{season}/{round}/results"
    race_r = rate_limited_get(race_url, timeout=10)
    race_r.raise_for_status()
    race_results: list[dict] = []
    for r in race_r.json()['MRData']['RaceTable']['Races']['Results']:
        result = {
            "driver_api_id": r["Driver"]["driverId"],
            "position": int(r["position"]),
            "points": int(r["points"])
        }
        result["starting_grid"] = r["grid"] if "grid" in r else None
        result["status"] = r["status"] if "status" in r else None
        if 'FastestLap' in r:
            result["best_lap"] = r['FastestLap']['lap']
            result["fast_lap"] = r['FastestLap']['Time']['time']
        else:
            result["best_lap"] = None
            result["fast_lap"] = None

        race_results.append(result)

    return race_results
        

        
        
    

    