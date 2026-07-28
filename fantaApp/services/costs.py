"""
Logica di calcolo costi per piloti e gare.
Le costanti/tabelle sono definite in rules.py.
"""
from django.core.exceptions import ValidationError
from django.db.models import Sum

from ..models import (
    Driver,
    PlayerRaceChoice,
    QualifyingResult,
    Weekend,
)
from . import rules


# ============================================================================
# Calcolo costi base dalla griglia e classifica
# ============================================================================

def get_cost_from_grid(mapping: dict, grid_position: int) -> int:
    """Restituisce il costo base dalla posizione in griglia."""
    if not grid_position or grid_position < 1:
        raise ValidationError("Posizione di griglia non valida per calcolare il costo del pilota.")
    return mapping.get(grid_position, 0)


def get_cost_from_standings_position(*, driver: Driver, weekend: Weekend) -> int:
    """Restituisce il costo aggiuntivo dalla posizione in classifica piloti."""
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
    return rules.COST_BY_STANDINGS_POSITION.get(standing.position, 0)


# ============================================================================
# Calcolo costi gara regular
# ============================================================================

def get_regular_race_cost_breakdown(*, grid_position: int, driver: Driver, weekend: Weekend) -> dict:
    """Restituisce il breakdown del costo per la gara regular."""
    grid_cost = get_cost_from_grid(rules.REGULAR_RACE_COST_BY_GRID_POSITION, grid_position)
    standings_cost = get_cost_from_standings_position(driver=driver, weekend=weekend)
    return {
        "grid_cost": grid_cost,
        "standings_cost": standings_cost,
        "total_cost": grid_cost + standings_cost,
    }


def get_regular_race_cost(*, grid_position: int, driver: Driver, weekend: Weekend) -> int:
    """Restituisce il costo totale per la gara regular."""
    return get_regular_race_cost_breakdown(
        grid_position=grid_position,
        driver=driver,
        weekend=weekend,
    )["total_cost"]


# Alias per retrocompatibilità
def get_regular_race_driver_cost_breakdown(grid_position: int, driver: Driver, weekend: Weekend) -> dict:
    """Alias per get_regular_race_cost_breakdown."""
    return get_regular_race_cost_breakdown(
        grid_position=grid_position,
        driver=driver,
        weekend=weekend,
    )


# ============================================================================
# Calcolo costi gara sprint
# ============================================================================

def get_sprint_race_cost(grid_position: int) -> int:
    """Restituisce il costo per la gara sprint dalla posizione in griglia."""
    return get_cost_from_grid(rules.SPRINT_RACE_COST_BY_GRID_POSITION, grid_position)


# Alias per retrocompatibilità
def get_sprint_race_driver_cost(grid_position: int) -> int:
    """Alias per get_sprint_race_cost."""
    return get_sprint_race_cost(grid_position)


# ============================================================================
# Sconto pupillo
# ============================================================================

def get_regular_race_pupillo_discount(*, player, race, driver) -> int:
    """
    Calcola lo sconto pupillo per un pilota.
    Lo sconto aumenta per ogni weekend consecutivo in cui il pilota è stato scelto come pupillo.
    """
    if race.type != "regular":
        return 0

    consecutive_weekends = 0
    current_round = race.weekend.round_number - 1

    while current_round >= 1 and consecutive_weekends < (rules.PUPILLO_MAX_DISCOUNT // rules.PUPILLO_DISCOUNT_STEP):
        previous_pupillo = PlayerRaceChoice.objects.filter(
            player=player,
            race__type="regular",
            race__weekend__season=race.weekend.season,
            race__weekend__round_number=current_round,
            is_pupillo=True,
        ).first()

        if not previous_pupillo or previous_pupillo.driver_id != driver.id:
            break

        consecutive_weekends += 1
        current_round -= 1

    return min(consecutive_weekends * rules.PUPILLO_DISCOUNT_STEP, rules.PUPILLO_MAX_DISCOUNT)


# ============================================================================
# Opzioni pilota per la scelta gara
# ============================================================================

def get_race_driver_options(*, race, player=None) -> list:
    """
    Restituisce la lista delle opzioni pilota disponibili per una gara.
    Include costi, sconti pupillo e altre info utili per la scelta.
    """
    options = []
    for result in (
        QualifyingResult.objects
        .filter(
            qualifying__weekend=race.weekend,
            qualifying__type=race.type,
        )
        .select_related("driver", "driver__team")
        .order_by("position")
    ):
        if not result.position:
            continue

        if race.type == "sprint":
            option = {
                "driver": result.driver,
                "grid_position": result.position,
                "cost": get_sprint_race_cost(result.position),
            }
        else:
            cost_breakdown = get_regular_race_cost_breakdown(
                grid_position=result.position,
                driver=result.driver,
                weekend=race.weekend,
            )
            option = {
                "driver": result.driver,
                "grid_position": result.position,
                "grid_cost": cost_breakdown["grid_cost"],
                "standings_cost": cost_breakdown["standings_cost"],
                "cost": cost_breakdown["total_cost"],
            }

        if race.type == "regular" and player is not None:
            pupillo_discount = get_regular_race_pupillo_discount(
                player=player,
                race=race,
                driver=result.driver,
            )
            option["pupillo_discount"] = pupillo_discount
            option["pupillo_cost"] = max(option["cost"] - pupillo_discount, 0)
            option["previous_pupillo_streak"] = (
                pupillo_discount // rules.PUPILLO_DISCOUNT_STEP
                if pupillo_discount
                else 0
            )

        options.append(option)

    return options


def get_sprint_race_driver_options(*, race) -> list:
    """Restituisce le opzioni pilota per la gara sprint."""
    return get_race_driver_options(race=race)


# ============================================================================
# Gestione crediti player
# ============================================================================

def get_player_reserved_credit(*, player, exclude_race=None) -> int:
    """
    Restituisce i crediti già prenotati dal player per gare non ancora concluse.
    """
    queryset = PlayerRaceChoice.objects.filter(
        player=player,
        credit_applied=False,
    )

    if exclude_race is not None:
        queryset = queryset.exclude(race=exclude_race)

    reserved_credit = queryset.aggregate(total=Sum("spent_amount"))["total"]
    return reserved_credit or 0


def get_player_spendable_credit(*, player, exclude_race=None) -> int:
    """
    Restituisce i crediti effettivamente spendibili dal player.
    """
    return max(
        player.available_credit - get_player_reserved_credit(player=player, exclude_race=exclude_race),
        0,
    )
