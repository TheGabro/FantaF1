"""Management command: `python manage.py import_drivers --season <year> [--dry-run]`"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fantaApp.services import drivers
from fantaApp.services.sources import jolpicaSource


class Command(BaseCommand):
    help = "Import drivers for a season"

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, required=True, help="season to import")
        parser.add_argument("--dry-run", action="store_true", help="Execute command without final commit")

    @transaction.atomic
    def handle(self, *args, **options):
        season = options["season"]
        payload = jolpicaSource.get_drivers(season)
        try:
            saved = drivers.save_drivers(season=season, payload=payload)
        except drivers.TeamNotFound as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS(f"• Drivers imported: {len(saved)}"))

        if options["dry_run"]:
            raise transaction.TransactionManagementError("Dry-run — transaction rollback")
