from django.utils import timezone
from ..models import Qualifying, Race


def event_start(event):
    """
    Ritorna l'orario ufficiale FIA di inizio dell'evento (Race o Qualifying),
    leggendo il campo giusto sul Weekend collegato in base al tipo di evento.
    """
    if isinstance(event, Qualifying):
        return getattr(
            event.weekend,
            "sprint_qualifying_start" if event.type == "sprint" else "qualifying_start",
            None,
        )
    else:  # Race
        return getattr(
            event.weekend,
            "sprint_start" if event.type == "sprint" else "race_start",
            None,
        )


def _event_has_started(event) -> bool:
    """
    Ritorna True se l'orario di inizio dell'evento è trascorso.

    • I DateTimeField sono salvati in UTC (USE_TZ=True).
    • Se per errore 'start' fosse naïve (senza tz), lo rendiamo aware in UTC
      così il confronto con `timezone.now()` (anch'esso UTC) è sempre coerente.
    """
    start = event_start(event)

    if not start:
        return False

    if timezone.is_naive(start):
        start = timezone.make_aware(start, timezone.utc)

    return timezone.now() >= start