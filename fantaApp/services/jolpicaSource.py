import requests

BASE_URL = 'https://api.jolpi.ca/ergast/f1/'


def get_drivers(season:int):
    drivers_url = f"{BASE_URL}/{season}/drivers.json"
    driver_r = requests.get(drivers_url, timeout=10)
    driver_r.raise_for_status()
    drivers = []
    constructor = []
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
            "team": constructor[["constructorId"]]
        })

        constructor.append({
            "name": constructor['name'],
            "nationality":constructor['nationality'],
            "api_id": constructor['constructorId'],
            "short_name": constructor['name'][:3].upper()
            }
        )
    return drivers