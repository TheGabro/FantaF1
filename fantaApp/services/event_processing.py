from django.db.models import QuerySet
from django.utils import timezone

from ..models import EventProcessingStatus, Status


def qualifying_ready(race) -> bool:
    return EventProcessingStatus.objects.filter(
        qualifying__weekend=race.weekend,
        qualifying__type=race.type,
        status=Status.PROCESSED,
    ).exists()


def mark(event_status, *, status, now, error="") -> str:
    """Registra l'esito di un tentativo sull'EventProcessingStatus."""
    # attempts is only a counter: the waiting budget is the Airflow sensor timeout
    event_status.status = status
    event_status.attempts += 1
    event_status.last_attempt_at = now
    event_status.last_error = error
    event_status.save(
        update_fields=["status", "attempts", "last_attempt_at", "last_error"]
    )

    return status


def eligible_events(now: timezone.datetime) -> QuerySet[EventProcessingStatus]:
    """return eligible EventProcessingStatus in chronological order."""

    eligible = (
        EventProcessingStatus.objects.select_related(
            "race__weekend", "qualifying__weekend"
        )
        .filter(
            status__in=[Status.PENDING, Status.WAITING_FOR_RESULTS],
            eligible_after__lte=now,
        )
        .order_by("eligible_after")
    )

    return eligible
