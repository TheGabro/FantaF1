import requests

BASE_URL = 'https://api.jolpi.ca/ergast/f1/'


def get_drivers(season:int) -> list[dict]:
    drivers_url = f"{BASE_URL}/{season}/drivers.json"
    driver_r = requests.get(drivers_url, timeout=10)
    driver_r.raise_for_status()
    drivers = []
    for d in driver_r.json()["MRData"]["DriverTable"]["Drivers"]:
        driver_id = d["driverId"]
        constructor_url = f"{BASE_URL}/{season}/drivers/{driver_id}/constructors"
        constructor_r = requests.get(constructor_url, timeout = 10)
        constructor_r.raise_for_status()
        constructor = driver_r.json()["MRData"]["ConstructorTable"]["Constructors"][0]
    
        drivers.append({
            "api_id": d["driverId"],
            "first_name": d["givenName"],
            "last_name":  d["familyName"],
            "number":     d["permanentNumber"],
            "short_name": d["code"],
            "season": season,
            "team": constructor[["constructorId"]]
        })
    return drivers 

def get_teams(season:int) -> list[dict]:
    teams_url = f"{BASE_URL}/{season}/constructors"
    teams_r = requests.get(teams_url, timeout = 10)
    teams_r.raise_for_status()
    teams = []
    for c in teams_r.json()["MRData"]["ConstructorTable"]["Constructors"]:
        teams.append({
            "name": c['name'],
            "nationality":c['nationality'],
            "api_id": c['constructorId'],
            "short_name": c['name'][:3].upper()
            }
        )

    return teams

def get_circuits(season: int) -> list[dict]:
    circuits_url = f'{BASE_URL}/{season}/circuits'
    circuits_r = requests.get(circuits_url, timeout = 10)
    circuits_r.raise_for_status()
    circuits = []
    for c in circuits_r.json()["MRData"]["CircuitTable"]["Circuits"]:
        circuits.append({
            "name": c["circuitName"],
            "country": c["Location"]["country"],
            "location": c["Location"]["locality"],
            "api_id": c["circuitId"]
        })

    