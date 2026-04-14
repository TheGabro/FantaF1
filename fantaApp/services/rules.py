from django.core.exceptions import ValidationError

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
PUPILLO_DISCOUNT_STEP = 5
PUPILLO_MAX_DISCOUNT = 20


def get_cost_from_grid(mapping, grid_position: int) -> int:
    if not grid_position or grid_position < 1:
        raise ValidationError("Posizione di griglia non valida per calcolare il costo del pilota.")
    return mapping.get(grid_position, 0)

def get_regular_race_cost(grid_position: int) -> int:
    return get_cost_from_grid(REGULAR_RACE_COST_BY_GRID_POSITION, grid_position)

def get_sprint_race_cost(grid_position: int) -> int:
    return get_cost_from_grid(SPRINT_RACE_COST_BY_GRID_POSITION, grid_position)