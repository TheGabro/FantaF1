"""Stato di una sessione per le pagine dei risultati (#103).

Dal via la pagina dei risultati mostra la propria scelta e uno stato: «in corso»
per una durata fissa dal via, poi «risultati non ancora pubblicati» finché i
risultati non sono importati, poi i risultati. Le durate servono solo a scegliere
il messaggio: sono di presentazione, non regole di gioco (decise il 9/11).
"""

from datetime import timedelta

from django.utils import timezone

from ..models import Qualifying
from ..services import helper

SESSION_DURATIONS = {
    ("race", "regular"): timedelta(hours=3),
    ("race", "sprint"): timedelta(hours=2),
    ("qualifying", "regular"): timedelta(hours=2),
    ("qualifying", "sprint"): timedelta(hours=2),
}

NOT_STARTED = "not_started"
RUNNING = "running"
WAITING_RESULTS = "waiting_results"
RESULTS = "results"


def session_state(event, *, has_results):
    """Uno fra NOT_STARTED, RUNNING, WAITING_RESULTS e RESULTS per una Race o
    una Qualifying. Con i risultati importati vale sempre RESULTS."""
    if has_results:
        return RESULTS
    if not helper._event_has_started(event):
        return NOT_STARTED
    kind = "qualifying" if isinstance(event, Qualifying) else "race"
    start = helper.event_start(event)
    if timezone.is_naive(start):
        start = timezone.make_aware(start, timezone.utc)
    if timezone.now() < start + SESSION_DURATIONS[(kind, event.type)]:
        return RUNNING
    return WAITING_RESULTS
