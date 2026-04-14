from django.core.exceptions import ValidationError
from ..models import (
    Weekend,
    Driver
)

SPRINT_RACE_COST_BY_GRID_POSITION = {
    1: 60,
    2: 50,
    3: 40,
    4: 30,
    5: 25,
    6: 20,
    7: 15,
    8: 0,
    9: 0,
    10: 0,
    11: 0,
    12: 0,
    13: 0,
    14: 0,
    15: 0,
    16: 0,
    17: 0,
    18: 0,
    19: 0,
    20: 0,
    21: 0,
    22: 0,
    
}
REGULAR_RACE_COST_BY_GRID_POSITION = {
    1: 140,
    2: 110,
    3: 90,
    4: 80,
    5: 70,
    6: 50,
    7: 40,
    8: 30,
    9: 20,
    10: 10,
    11: 0,
    12: 0,
    13: 0,
    14: 0,
    15: 0,
    16: 0,
    17: 0,
    18: 0,
    19: 0,
    20: 0,
    21: 0,
    22: 0,
}
COST_BY_STANDINGS_POSITION = {
    1: 30,
    2: 25,
    3: 20,
    4: 15,
    5: 10,
    6: 5
}
PUPILLO_DISCOUNT_STEP = 5
PUPILLO_MAX_DISCOUNT = 20


def get_cost_from_grid(mapping, grid_position: int) -> int:
    if not grid_position or grid_position < 1:
        raise ValidationError("Posizione di griglia non valida per calcolare il costo del pilota.")
    return mapping.get(grid_position, 0)

def get_cost_from_standings_position(*, driver, weekend) -> int:
    standing = (
        driver.standings
        .filter(
            weekend__season=weekend.season,
            weekend__round_number__lt=weekend.round_number,
        )
        .order_by("-weekend__round_number")
        .first()
    )
    if standing is None:
        return 0
    return COST_BY_STANDINGS_POSITION.get(standing.position, 0)

def get_regular_race_cost_breakdown(*, grid_position: int, driver: Driver, weekend: Weekend) -> dict:
    grid_cost = get_cost_from_grid(REGULAR_RACE_COST_BY_GRID_POSITION, grid_position)
    standings_cost = get_cost_from_standings_position(driver=driver, weekend=weekend)
    return {
        "grid_cost": grid_cost,
        "standings_cost": standings_cost,
        "total_cost": grid_cost + standings_cost,
    }


def get_regular_race_cost(*, grid_position: int, driver: Driver, weekend: Weekend) -> int:
    return get_regular_race_cost_breakdown(
        grid_position=grid_position,
        driver=driver,
        weekend=weekend,
    )["total_cost"]


def get_sprint_race_cost(grid_position: int) -> int:
    return get_cost_from_grid(SPRINT_RACE_COST_BY_GRID_POSITION, grid_position)