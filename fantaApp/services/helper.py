from django.utils import timezone
from ..models import Qualifying, Race

def _event_has_started(event) -> bool:
    """
    Ritorna True se l'orario di inizio dell'evento è trascorso.

    • I DateTimeField sono salvati in UTC (USE_TZ=True).
    • Se per errore 'start' fosse naïve (senza tz), lo rendiamo aware in UTC
      così il confronto con `timezone.now()` (anch'esso UTC) è sempre coerente.
    """
    from django.utils import timezone

    # ---- ricava l'orario di start -------------------------------------------------
    if isinstance(event, Qualifying):
        start = getattr(
            event.weekend,
            "sprint_qualifying_start" if event.type == "sprint" else "qualifying_start",
            None,
        )
    else:  # Race
        start = getattr(
            event.weekend,
            "sprint_start" if event.type == "sprint" else "race_start",
            None,
        )

    if not start:
        return False
    
    if timezone.is_naive(start):
        start = timezone.make_aware(start, timezone.utc)

    return timezone.now() >= start