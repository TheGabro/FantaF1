from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from . import rules

from ..models import (
    PlayerQualifyingChoice,
    PlayerQualifyingMultiChoice,
    PlayerRaceChoice,
    PlayerSprintQualifyingChoice,
    QualifyingResult,
)


from . import rules

def get_regular_race_driver_cost(grid_position: int) -> int:
    return rules.get_regular_race_cost(grid_position)

def get_sprint_race_driver_cost(grid_position: int) -> int:
    return rules.get_sprint_race_cost(grid_position)


def get_regular_race_pupillo_discount(*, player, race, driver) -> int:
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


def get_race_driver_options(*, race, player=None):
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
                "cost": get_sprint_race_driver_cost(result.position),
            }
        else:
            option = {
                "driver": result.driver,
                "grid_position": result.position,
                "cost": get_regular_race_driver_cost(result.position),
            }

        if race.type == "regular" and player is not None:
            pupillo_discount = get_regular_race_pupillo_discount(
                player=player,
                race=race,
                driver=result.driver,
            )
            option["pupillo_discount"] = pupillo_discount
            option["pupillo_cost"] = max(option["cost"] - pupillo_discount, 0)

        options.append(option)

    return options


def get_sprint_race_driver_options(*, race):
    return get_race_driver_options(race=race)


def get_player_reserved_credit(*, player, exclude_race=None) -> int:
    queryset = PlayerRaceChoice.objects.filter(
        player=player,
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
    if len(selected_drivers) != 1:
        raise ValidationError("Devi selezionare esattamente 1 pilota per la Sprint Race.")

    driver_ids = [driver.id for driver in selected_drivers]

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
def choose_regular_race_drivers(*, player, race, drivers, pupillo_driver):
    if race.type != "regular":
        raise ValidationError("La scelta del pupillo e' disponibile solo per il Grand Prix.")

    selected_drivers = list(drivers)
    if len(selected_drivers) != 2:
        raise ValidationError("Devi selezionare esattamente 2 piloti per il Grand Prix.")

    driver_ids = [driver.id for driver in selected_drivers]
    if len(driver_ids) != len(set(driver_ids)):
        raise ValidationError("Non puoi selezionare lo stesso pilota piu' di una volta.")

    if pupillo_driver.id not in driver_ids:
        raise ValidationError("Il pupillo deve essere uno dei 2 piloti selezionati.")

    options_by_driver_id = {
        option["driver"].id: option
        for option in get_race_driver_options(race=race, player=player)
    }

    missing_driver_ids = [driver_id for driver_id in driver_ids if driver_id not in options_by_driver_id]
    if missing_driver_ids:
        raise ValidationError("La griglia del Grand Prix non e' disponibile per uno o piu' piloti selezionati.")

    pupillo_discount = options_by_driver_id[pupillo_driver.id].get("pupillo_discount", 0)
    total_spent_amount = 0
    for driver in selected_drivers:
        option = options_by_driver_id[driver.id]
        if driver.id == pupillo_driver.id:
            total_spent_amount += option.get("pupillo_cost", option["cost"])
        else:
            total_spent_amount += option["cost"]

    spendable_credit = get_player_spendable_credit(player=player, exclude_race=race)
    if total_spent_amount > spendable_credit:
        raise ValidationError(
            f"Crediti insufficienti: te ne servono {total_spent_amount}, ma ne hai disponibili {spendable_credit}."
        )

    PlayerRaceChoice.objects.filter(player=player, race=race).exclude(driver_id__in=driver_ids).delete()

    for driver in selected_drivers:
        option = options_by_driver_id[driver.id]
        is_pupillo = driver.id == pupillo_driver.id
        spent_amount = option.get("pupillo_cost", option["cost"]) if is_pupillo else option["cost"]

        PlayerRaceChoice.objects.update_or_create(
            player=player,
            race=race,
            driver=driver,
            defaults={
                "spent_amount": spent_amount,
                "credit_applied": False,
                "is_pupillo": is_pupillo,
            },
        )

    return {
        "total_spent_amount": total_spent_amount,
        "pupillo_discount": pupillo_discount,
    }


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
def choose_regular_quali_multi_choices(*, player, qualifying, selections_by_slot):
    valid_slots = {"q1_pass", "q2_pass", "q3_top3"}

    invalid_slots = set(selections_by_slot.keys()) - valid_slots
    if invalid_slots:
        raise ValidationError("Invalid Slot")

    seen_driver_ids = set()
    rows_to_create = []

    for slot, drivers in selections_by_slot.items():
        for driver in drivers:
            if driver.id in seen_driver_ids:
                raise ValidationError("Driver already in another slot.")
            seen_driver_ids.add(driver.id)

            rows_to_create.append(
                PlayerQualifyingMultiChoice(
                    player=player,
                    qualifying=qualifying,
                    selection_slot=slot,
                    driver=driver,
                )
            )

    PlayerQualifyingMultiChoice.objects.filter(
        player=player,
        qualifying=qualifying,
    ).delete()

    PlayerQualifyingMultiChoice.objects.bulk_create(rows_to_create)