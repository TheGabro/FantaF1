"""
Costanti e tabelle di gioco per FantaF1.
Questo file contiene SOLO le costanti - la logica di calcolo è in bonuses.py e costs.py.
"""
from decimal import Decimal


# ============================================================================
# Costi per posizione in griglia - Sprint Race
# ============================================================================

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


# ============================================================================
# Costi per posizione in griglia - Regular Race (Grand Prix)
# ============================================================================

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


# ============================================================================
# Costi aggiuntivi per posizione in classifica piloti
# ============================================================================

COST_BY_STANDINGS_POSITION = {
    1: 30,
    2: 25,
    3: 20,
    4: 15,
    5: 10,
    6: 5,
}


# ============================================================================
# Sconto pupillo
# ============================================================================

PUPILLO_DISCOUNT_STEP = 5
PUPILLO_MAX_DISCOUNT = 20


# ============================================================================
# Bonus multichoice (weekend sprint - qualifica regular)
# Si applica alla gara regular del weekend sprint
# ============================================================================

QUALIFYING_MULTICHOICE_BONUS_RULES = {
    "none": {
        "credit_discount": 0,
        "points_multiplier": Decimal("1"),
    },
    "q1_pass": {
        "credit_discount": 10,
        "points_multiplier": Decimal("1"),
    },
    "q2_pass": {
        "credit_discount": 20,
        "points_multiplier": Decimal("1.2"),
    },
    "q3_top3": {
        "credit_discount": 50,
        "points_multiplier": Decimal("2"),
    },
}

VALID_MULTI_CHOICE_SLOTS = ("q1_pass", "q2_pass", "q3_top3")
MULTI_CHOICE_SLOT_SIZES = {
    "q1_pass": 6,
    "q2_pass": 5,
    "q3_top3": 3,
}


# ============================================================================
# Bonus qualifica regular (weekend non-sprint)
# Si applica alla gara regular del weekend non-sprint
# credit_change: positivo = malus (costo aumenta), negativo = sconto (costo diminuisce)
# qualifying_points: punti guadagnati dalla scelta qualifica
# points_multiplier: moltiplicatore punti gara
# ============================================================================

REGULAR_QUALIFYING_BONUS_BY_POSITION = {
    22: {"credit_change": 30, "qualifying_points": 0, "points_multiplier": Decimal("1")},
    21: {"credit_change": 20, "qualifying_points": 0, "points_multiplier": Decimal("1")},
    20: {"credit_change": 20, "qualifying_points": 0, "points_multiplier": Decimal("1")},
    19: {"credit_change": 10, "qualifying_points": 0, "points_multiplier": Decimal("1")},
    18: {"credit_change": 10, "qualifying_points": 0, "points_multiplier": Decimal("1")},
    17: {"credit_change": 10, "qualifying_points": 0, "points_multiplier": Decimal("1")},
    16: {"credit_change": 0, "qualifying_points": 10, "points_multiplier": Decimal("1")},
    15: {"credit_change": 0, "qualifying_points": 20, "points_multiplier": Decimal("1")},
    14: {"credit_change": -5, "qualifying_points": 30, "points_multiplier": Decimal("1")},
    13: {"credit_change": -5, "qualifying_points": 40, "points_multiplier": Decimal("1")},
    12: {"credit_change": -10, "qualifying_points": 60, "points_multiplier": Decimal("1")},
    11: {"credit_change": -10, "qualifying_points": 80, "points_multiplier": Decimal("1")},
    10: {"credit_change": -15, "qualifying_points": 100, "points_multiplier": Decimal("1")},
    9: {"credit_change": -15, "qualifying_points": 200, "points_multiplier": Decimal("1")},
    8: {"credit_change": -20, "qualifying_points": 300, "points_multiplier": Decimal("1")},
    7: {"credit_change": -20, "qualifying_points": 400, "points_multiplier": Decimal("1.1")},
    6: {"credit_change": -25, "qualifying_points": 500, "points_multiplier": Decimal("1.2")},
    5: {"credit_change": -20, "qualifying_points": 600, "points_multiplier": Decimal("1.3")},
    4: {"credit_change": -15, "qualifying_points": 700, "points_multiplier": Decimal("1.4")},
    3: {"credit_change": -10, "qualifying_points": 800, "points_multiplier": Decimal("1.5")},
    2: {"credit_change": -5, "qualifying_points": 900, "points_multiplier": Decimal("1.7")},
    1: {"credit_change": 0, "qualifying_points": 1000, "points_multiplier": Decimal("2")},
}