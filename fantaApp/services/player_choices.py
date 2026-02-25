from django.core.exceptions import ValidationError
from django.db import transaction
from ..models import PlayerQualifyingChoice, PlayerSprintQualifyingChoice


@transaction.atomic
def choose_sprint_quali_driver(*, player, qualifying, driver, slot):

    if slot not in {"sq1", "sq2", "sq3"}:
        raise ValidationError("Slot not valid")

    if PlayerSprintQualifyingChoice.objects.filter(
            player=player,
            qualifying=qualifying,
            driver=driver).exclude(selection_slot=slot).exists():
        raise ValidationError("Driver is already in taken in another slot")

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