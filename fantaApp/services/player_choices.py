from django.core.exceptions import ValidationError
from django.db import transaction
from ..models import PlayerSprintQualifyingChoice


@transaction.atomic
def choose_sprint_quali_driver(*, player, qualifying, driver, slot):

    if slot not in {"sq1", "sq2", "sq3"}:
        raise ValidationError("Slot not valid")

    if PlayerSprintQualifyingChoice.objects.filter(
            player=player, qualifying=qualifying, selection_slot=slot).exists():
        raise ValidationError("Slot is altready fullfilled")

    if PlayerSprintQualifyingChoice.objects.filter(
            player=player, qualifying=qualifying, driver=driver).exists():
        raise ValidationError("Driver is already in taken in another slot")

    PlayerSprintQualifyingChoice.objects.create(
        player=player,
        qualifying=qualifying,
        driver=driver,
        selection_slot=slot,
        cost=None,
    )