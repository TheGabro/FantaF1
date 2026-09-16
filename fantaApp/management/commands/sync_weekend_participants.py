from django.core.management.base import BaseCommand
from django.db import transaction

from fantaApp.services import weekend_participants


class Command(BaseCommand):
    help = "Sync weekend participants (roster piloti per round) for a season"

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, required=True, help="season to sync")
        parser.add_argument("--dry-run", action="store_true", help="Execute command without final commit")

    @transaction.atomic
    def handle(self, *args, **options):
        season = options["season"]
        created = weekend_participants.sync_weekend_participants(season=season)
        self.stdout.write(self.style.SUCCESS(f"• Weekend participants ready: {created} created"))

        if options["dry_run"]:
            raise transaction.TransactionManagementError("Dry-run — transaction rollback")
