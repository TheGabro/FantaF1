from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from fantaApp.models import EventProcessingStatus, Status
from fantaApp.services import event_processing as ep

STATUS_BY_NAME = {
    "processed": Status.PROCESSED,
    "waiting": Status.WAITING_FOR_RESULTS,
    "error": Status.ERROR,
}


class Command(BaseCommand):
    help = "Update status of an EventProcessingStatus instance (Used by Airflow DAG)"

    def add_arguments(self, parser):
        parser.add_argument("--status-id", type=int, required=True)
        parser.add_argument("--status", choices=STATUS_BY_NAME.keys(), required=True)
        parser.add_argument("--error", default="", help="Specifies the error message for the event if present")

    def handle(self, *args, **options):
        try:
            event_status = EventProcessingStatus.objects.get(id=options["status_id"])
        except EventProcessingStatus.DoesNotExist:
            raise CommandError(f"EventProcessingStatus with id {options['status_id']} does not exist.")
        final_status = ep.mark(event_status, status=STATUS_BY_NAME[options["status"]], now=timezone.now(), error=options["error"])
        self.stdout.write(f"{event_status.race or event_status.qualifying} → {final_status}")
