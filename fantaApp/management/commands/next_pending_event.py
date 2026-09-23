import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from fantaApp.services import event_processing as ep


class Command(BaseCommand):
    help = "Prints the next pending event of the specified type (qualifying or race) in JSON format."

    def add_arguments(self, parser):
        parser.add_argument("--event", choices=["qualifying", "race"], required=True)

    def handle(self, *args, **options):
        now = timezone.now()
        next_event = (
            ep.eligible_events(now)
            .filter(**{f"{options['event']}__isnull": False})
            .first()
        )
        if not next_event:
            raise CommandError("No eligible events found", returncode=99)

        if options["event"] == "race" and not ep.qualifying_ready(next_event.race):
            raise CommandError(
                f"Race {next_event.race} is not eligible because qualifying is not ready",
                returncode=99,
            )

        event = next_event.race or next_event.qualifying
        self.stdout.write(
            json.dumps(
                {
                    "season": event.weekend.season,
                    "round": event.weekend.round_number,
                    "type": event.type,
                    "status_id": next_event.id,
                }
            )
        )
