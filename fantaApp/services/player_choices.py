from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from ..models import (
    PlayerQualifyingChoice,
    PlayerQualifyingMultiChoice,
    PlayerRaceChoice,
    PlayerSprintQualifyingChoice,
    QualifyingResult,
)


SPRINT_RACE_COST_BY_GRID_POSITION_FACTOR = 1


def get_sprint_race_driver_cost(grid_position: int) -> int:
    if not grid_position or grid_position < 1:
        raise ValidationError("Posizione di griglia non valida per calcolare il costo del pilota.")

    return max(1, 21 - grid_position) * SPRINT_RACE_COST_BY_GRID_POSITION_FACTOR


def get_sprint_race_driver_options(*, race):
    options = []
    for result in (
        QualifyingResult.objects
        .filter(
            qualifying__weekend=race.weekend,
            qualifying__type="sprint",
        )
        .select_related("driver", "driver__team")
        .order_by("position")
    ):
        if not result.position:
            continue

        options.append({
            "driver": result.driver,
            "grid_position": result.position,
            "cost": get_sprint_race_driver_cost(result.position),
        })

    return options


def get_player_reserved_credit(*, player, exclude_race=None) -> int:
    queryset = PlayerRaceChoice.objects.filter(
        player=player,
        race__type="sprint",
        credit_applied=False,
    )

    if exclude_race is not None:
        queryset = queryset.exclude(race=exclude_race)

    reserved_credit = queryset.aggregate(total=Sum("spent_amount"))["total"]
    return reserved_credit or 0


def get_player_spendable_credit(*, player, exclude_race=None) -> int:
    return max(player.available_credit - get_player_reserved_credit(player=player, exclude_race=exclude_race), 0)


@transaction.atomic
def choose_sprint_race_drivers(*, player, race, drivers):
    if race.type != "sprint":
        raise ValidationError("La scelta crediti e griglia e' disponibile solo per la Sprint Race.")

    selected_drivers = list(drivers)
    if len(selected_drivers) != 2:
        raise ValidationError("Devi selezionare esattamente 2 piloti per la Sprint Race.")

    driver_ids = [driver.id for driver in selected_drivers]
    if len(driver_ids) != len(set(driver_ids)):
        raise ValidationError("Non puoi selezionare lo stesso pilota piu' di una volta.")

    options_by_driver_id = {
        option["driver"].id: option
        for option in get_sprint_race_driver_options(race=race)
    }

    missing_driver_ids = [driver_id for driver_id in driver_ids if driver_id not in options_by_driver_id]
    if missing_driver_ids:
        raise ValidationError("La griglia sprint non e' disponibile per uno o piu' piloti selezionati.")

    total_spent_amount = sum(options_by_driver_id[driver_id]["cost"] for driver_id in driver_ids)
    spendable_credit = get_player_spendable_credit(player=player, exclude_race=race)
    if total_spent_amount > spendable_credit:
        raise ValidationError(
            f"Crediti insufficienti: te ne servono {total_spent_amount}, ma ne hai disponibili {spendable_credit}."
        )

    PlayerRaceChoice.objects.filter(player=player, race=race).exclude(driver_id__in=driver_ids).delete()

    for driver in selected_drivers:
        PlayerRaceChoice.objects.update_or_create(
            player=player,
            race=race,
            driver=driver,
            defaults={
                "spent_amount": options_by_driver_id[driver.id]["cost"],
                "credit_applied": False,
                "is_pupillo": False,
            },
        )

    return total_spent_amount


@transaction.atomic
def choose_sprint_quali_driver(*, player, qualifying, driver, slot):

    if slot not in {"sq1", "sq2", "sq3"}:
        raise ValidationError("Slot not valid")

    if PlayerSprintQualifyingChoice.objects.filter(
            player=player,
            qualifying=qualifying,
            driver=driver).exclude(selection_slot=slot).exists():
        raise ValidationError("Driver is already taken in another slot")

    PlayerSprintQualifyingChoice.objects.update_or_create(
        player=player,
        qualifying=qualifying,
        selection_slot=slot,
        defaults={"driver": driver},
    )


@transaction.atomic
def choose_regular_quali_driver(*, player, qualifying, driver): 
    
    already_used = (
        PlayerQualifyingChoice.objects
        .filter(
            player=player,                                # già limita al campionato del player
            driver=driver,
            qualifying__type="regular",
            qualifying__weekend__season=qualifying.weekend.season,
        )
        .exclude(qualifying=qualifying)                  # permette eventuale modifica della stessa gara
        .exists()
    )

    if already_used:
        raise ValidationError("Driver already used in this season's Regular Qualifying")

    # Crea la nuova scelta
    PlayerQualifyingChoice.objects.update_or_create(
        player=player,
        qualifying=qualifying,
        defaults={"driver": driver},
    )

@transaction.atomic
def choose_regular_quali_multi_driver(*, player, qualifying, driver, slot):

    if slot not in {"sq1_pass", "sq2_pass", "q3_top3"}:
        raise ValidationError("Slot not valid")

    if PlayerQualifyingMultiChoice.objects.filter(
            player=player,
            qualifying=qualifying,
            driver=driver).exclude(selection_slot=slot).exists():
        raise ValidationError("Driver is already in taken in another slot")

    PlayerQualifyingMultiChoice.objects.update_or_create(
        player=player,
        qualifying=qualifying,
        selection_slot=slot,
        defaults={"driver": driver},
    )