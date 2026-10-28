import json

from django.core.management.base import BaseCommand, CommandError

from fantaApp.models import EventProcessingStatus, Status


def _to_dict(event_status: EventProcessingStatus) -> dict:
    event = event_status.race or event_status.qualifying
    return {
        "season": event.weekend.season,
        "round": event.weekend.round_number,
        "type": event.type,
        "status_id": event_status.id,
        "status": event_status.status,
        "eligible_after": event_status.eligible_after.isoformat(),
    }


class Command(BaseCommand):
    help = (
        "Prints in JSON format the next qualifying + race pair (same weekend and type) "
        "with at least one event not yet processed. Used by the Airflow DAG as calendar."
    )

    def handle(self, *args, **options):
        # ERROR included: a failed event blocks the following ones, keeping races in order
        first = (
            EventProcessingStatus.objects.select_related(
                "race__weekend", "qualifying__weekend"
            )
            .exclude(status=Status.PROCESSED)
            .order_by("eligible_after")
            .first()
        )
        if not first:
            raise CommandError("No events left to process", returncode=99)

        event = first.race or first.qualifying
        qualifying = EventProcessingStatus.objects.select_related(
            "qualifying__weekend"
        ).get(qualifying__weekend=event.weekend, qualifying__type=event.type)
        race = EventProcessingStatus.objects.select_related("race__weekend").get(
            race__weekend=event.weekend, race__type=event.type
        )

        self.stdout.write(
            json.dumps({"qualifying": _to_dict(qualifying), "race": _to_dict(race)})
        )
