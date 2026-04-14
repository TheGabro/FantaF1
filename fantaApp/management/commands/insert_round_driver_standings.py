from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fantaApp.models import Weekend, Driver, DriverStanding
from fantaApp.services.jolpicaSource import get_driver_standings

class Command(BaseCommand):
    help = "Import driver standings"

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            help="season to call",
        )

        parser.add_argument(
            "--round",
            type=int,
            help="round to call",
        )

        parser.add_argument(
            "--dry-run", #it's a boolean flag, if present it will roll back at the end
            action="store_true",
            help="Execute command without final commit",
        )
    
    @transaction.atomic
    def handle(self, *args, **options):
        season: int = options["season"]
        round: int = options["round"]
        dry_run: bool = options["dry_run"]
        weekend = Weekend.objects.get(season=season, round_number=round)
        drivers_by_api_id = {
            driver.api_id: driver
            for driver in Driver.objects.filter(season=season)
        }

        imported_count = 0
        created_count = 0
        updated_count = 0

        for data in get_driver_standings(season, round):
            driver_api_id = data["driver_api_id"]
            driver = drivers_by_api_id.get(driver_api_id)
            if driver is None:
                raise CommandError(
                    f"Driver non trovato per api_id={driver_api_id} nella season={season}"
                )

            _, created = DriverStanding.objects.update_or_create(
                weekend=weekend,
                driver=driver,
                defaults={
                    "position": data["position"],
                    "points": data["points"],
                    "wins": data["wins"],
                    "podiums": data.get("podiums", 0),
                },
            )
            imported_count += 1
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"• Driver standings processed: {imported_count} (created: {created_count}, updated: {updated_count})"
            )
        )

        # ------------------------------------------------------------------
        # Commit / Rollback
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry‑run active: volontary rollback"))
            raise transaction.TransactionManagementError("Dry‑run — transaction rollback")

        self.stdout.write(self.style.SUCCESS("=== Import succeded ==="))
    
