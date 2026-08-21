"""
Funzioni per le scelte dei giocatori (choose_*).
La logica di calcolo bonus è in bonuses.py, la logica costi in costs.py.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    PlayerQualifyingChoice,
    PlayerQualifyingMultiChoice,
    PlayerRaceChoice,
    PlayerSprintQualifyingChoice,
)
from . import bonuses, costs


# ============================================================================
# Scelta piloti gara sprint
# ============================================================================

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
        for option in costs.get_sprint_race_driver_options(race=race)
    }

    missing_driver_ids = [driver_id for driver_id in driver_ids if driver_id not in options_by_driver_id]
    if missing_driver_ids:
        raise ValidationError("La griglia sprint non e' disponibile per uno o piu' piloti selezionati.")

    qualifying = race.weekend.qualifyings.filter(type="sprint").first()
    qualifying_bonus = bonuses.get_sprint_qualifying_bonus(player=player, qualifying=qualifying)

    base_cost = sum(options_by_driver_id[driver_id]["cost"] for driver_id in driver_ids)
    # Lo sconto non può portare il costo sotto zero: nessun guadagno di crediti.
    total_spent_amount = max(base_cost - qualifying_bonus["credit_discount"], 0)
    spendable_credit = costs.get_player_spendable_credit(player=player, exclude_race=race)
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
                "spent_amount": total_spent_amount,
                "credit_applied": False,
                "is_pupillo": False,
            },
        )

    return total_spent_amount


# ============================================================================
# Scelta piloti gara regular (Grand Prix)
# ============================================================================

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
        for option in costs.get_race_driver_options(race=race, player=player)
    }

    missing_driver_ids = [driver_id for driver_id in driver_ids if driver_id not in options_by_driver_id]
    if missing_driver_ids:
        raise ValidationError("La griglia del Grand Prix non e' disponibile per uno o piu' piloti selezionati.")

    pupillo_discount = options_by_driver_id[pupillo_driver.id].get("pupillo_discount", 0)
    selected_costs_by_driver_id = {}
    for driver in selected_drivers:
        option = options_by_driver_id[driver.id]
        if driver.id == pupillo_driver.id:
            selected_costs_by_driver_id[driver.id] = option.get("pupillo_cost", option["cost"])
        else:
            selected_costs_by_driver_id[driver.id] = option["cost"]

    qualifying_bonus = bonuses.get_race_bonus(player=player, race=race)
    adjusted_costs_by_driver_id = bonuses.apply_race_credit_change(
        costs_by_driver_id=selected_costs_by_driver_id,
        credit_change=qualifying_bonus["credit_change"],
    )
    total_spent_amount = sum(adjusted_costs_by_driver_id.values())

    spendable_credit = costs.get_player_spendable_credit(player=player, exclude_race=race)
    if total_spent_amount > spendable_credit:
        raise ValidationError(
            f"Crediti insufficienti: te ne servono {total_spent_amount}, ma ne hai disponibili {spendable_credit}."
        )

    PlayerRaceChoice.objects.filter(player=player, race=race).exclude(driver_id__in=driver_ids).delete()

    for driver in selected_drivers:
        option = options_by_driver_id[driver.id]
        is_pupillo = driver.id == pupillo_driver.id
        spent_amount = adjusted_costs_by_driver_id[driver.id]

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
        "qualifying_bonus_credit_change": qualifying_bonus["credit_change"],
        "qualifying_bonus_points_multiplier": qualifying_bonus["points_multiplier"],
        "qualifying_bonus_level": qualifying_bonus["level"],
        "qualifying_bonus_qualifying_points": qualifying_bonus["qualifying_points"],
    }


# ============================================================================
# Scelta pilota qualifica sprint
# ============================================================================

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


# ============================================================================
# Scelta pilota qualifica regular (weekend non-sprint)
# ============================================================================

@transaction.atomic
def choose_regular_quali_driver(*, player, qualifying, driver):
    already_used = (
        PlayerQualifyingChoice.objects
        .filter(
            player=player,
            driver=driver,
            qualifying__type="regular",
            qualifying__weekend__season=qualifying.weekend.season,
        )
        .exclude(qualifying=qualifying)
        .exists()
    )

    if already_used:
        raise ValidationError("Driver already used in this season's Regular Qualifying")

    PlayerQualifyingChoice.objects.update_or_create(
        player=player,
        qualifying=qualifying,
        defaults={"driver": driver},
    )


# ============================================================================
# Scelta multipla piloti qualifica regular (weekend sprint)
# ============================================================================

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