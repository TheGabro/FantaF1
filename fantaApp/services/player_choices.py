from django.core.exceptions import ValidationError
from django.db import transaction
from ..models import PlayerSprintQualifyingChoice


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