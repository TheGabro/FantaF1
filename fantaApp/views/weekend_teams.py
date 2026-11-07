"""Scuderia dei piloti nel singolo weekend (#82).

Driver.team è la scuderia con cui il pilota è stato importato a inizio stagione.
Chi cambia sedile a stagione in corso (riserve, sostituzioni) ha la scuderia del
weekend in WeekendParticipant: è quella che danno colore ed etichetta del pilota
nelle pagine.
"""

from ..models import WeekendParticipant


def weekend_teams(**filters):
    """{(weekend_id, driver_id): Team} dei roster filtrati, in una query sola."""
    return {
        (p.weekend_id, p.driver_id): p.team
        for p in WeekendParticipant.objects.filter(**filters).select_related("team")
    }


def use_weekend_teams(weekend, drivers, *, teams=None):
    """Mette su ogni pilota la scuderia che ha in questo weekend.

    Si chiama solo prima del render: i piloti non vengono salvati, e le regole di
    gioco (per esempio il limite di scelte per scuderia) restano su Driver.team.
    Chi non è nel roster del weekend tiene Driver.team. `teams` evita una query
    per weekend nelle pagine che ne mostrano molti.
    """
    if teams is None:
        teams = weekend_teams(weekend=weekend)
    for driver in drivers:
        team = teams.get((weekend.id, driver.id))
        if team is not None:
            driver.team = team
