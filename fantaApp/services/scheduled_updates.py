from django.db import transaction

from ..models import ChampionshipPlayer, PlayerRaceChoice
from . import helper


def _apply_started_race_credits(*, race_type, player=None):
    pending_choices = list(
        PlayerRaceChoice.objects
        .select_for_update()
        .select_related("player", "race", "race__weekend")
        .filter(
            race__type=race_type,
            credit_applied=False,
        )
    )

    if player is not None:
        pending_choices = [choice for choice in pending_choices if choice.player_id == player.id]

    started_choices = [choice for choice in pending_choices if helper._event_has_started(choice.race)]
    if not started_choices:
        return 0

    totals_by_player_id = {}
    for choice in started_choices:
        totals_by_player_id[choice.player_id] = totals_by_player_id.get(choice.player_id, 0) + choice.spent_amount

    players = {
        championship_player.id: championship_player
        for championship_player in ChampionshipPlayer.objects.select_for_update().filter(id__in=totals_by_player_id)
    }

    for player_id, total_spent in totals_by_player_id.items():
        championship_player = players[player_id]
        championship_player.available_credit -= total_spent
        championship_player.save(update_fields=["available_credit"])

    PlayerRaceChoice.objects.filter(id__in=[choice.id for choice in started_choices]).update(credit_applied=True)
    return len(started_choices)


@transaction.atomic
# TODO Airflow: chiamare questa funzione da un job schedulato quando vorrai riattivare l'addebito automatico dei crediti Sprint Race.
def apply_started_sprint_race_credits(*, player=None):
    return _apply_started_race_credits(race_type="sprint", player=player)


@transaction.atomic
# TODO Airflow: chiamare questa funzione da un job schedulato quando vorrai riattivare l'addebito automatico dei crediti Grand Prix.
def apply_started_regular_race_credits(*, player=None):
    return _apply_started_race_credits(race_type="regular", player=player)