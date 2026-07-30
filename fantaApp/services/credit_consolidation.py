from django.db import transaction

from ..models import ChampionshipPlayer, PlayerRaceChoice
from . import helper


def consolidate_race_credits_if_started(*, race) -> int:
    """
    Consolida (addebita definitivamente) i crediti prenotati per le scelte di UNA
    singola race, per TUTTI i giocatori, MA SOLO SE l'orario ufficiale FIA di
    inizio gara (race.weekend.race_start / sprint_start) e' gia' trascorso.

    E' un controllo ridondante lato server: la UI blocca gia' le modifiche alla
    scelta quando event_started e' True, ma questa funzione garantisce il
    consolidamento anche se qualcuno bypassasse la UI.

    Nota: usiamo l'orario ufficiale FIA di partenza, non l'orario di partenza
    effettivo/reale (che potrebbe slittare per bandiera rossa, pioggia, ecc.).
    Per la v1 va bene cosi'; in futuro si potra' raffinare.

    Returns:
        Numero di PlayerRaceChoice consolidate in questa chiamata.

    # TODO Airflow: schedulare un sensore/poll basato sullo stesso timestamp
    # (race.weekend.race_start / sprint_start) usato da helper._event_has_started,
    # cosi' da consolidare i crediti appena l'orario ufficiale e' trascorso.
    """
    if not helper._event_has_started(race):
        return 0

    pending_choices = list(
        PlayerRaceChoice.objects
        .select_for_update()
        .select_related("player", "race", "race__weekend")
        .filter(
            race=race,
            credit_applied=False,
        )
    )

    if not pending_choices:
        return 0

    totals_by_player_id = {}
    for choice in pending_choices:
        totals_by_player_id[choice.player_id] = totals_by_player_id.get(choice.player_id, 0) + choice.spent_amount

    players = {
        championship_player.id: championship_player
        for championship_player in ChampionshipPlayer.objects.select_for_update().filter(id__in=totals_by_player_id)
    }

    for player_id, total_spent in totals_by_player_id.items():
        championship_player = players[player_id]
        championship_player.available_credit -= total_spent
        championship_player.save(update_fields=["available_credit"])

    PlayerRaceChoice.objects.filter(id__in=[choice.id for choice in pending_choices]).update(credit_applied=True)
    return len(pending_choices)


@transaction.atomic
def consolidate_race_credits(*, race):
    return consolidate_race_credits_if_started(race=race)