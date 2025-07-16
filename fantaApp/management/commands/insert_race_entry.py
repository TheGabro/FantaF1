from django.utils.dateparse import parse_duration

from django.core.management.base import BaseCommand
from django.db import transaction

from fantaApp.models import Weekend, Race, Driver, RaceEntry
from fantaApp.services.jolpicaSource import get_race_result


class Command(BaseCommand):
    help = "Import last race result"

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            help="year to call",
        )

        parser.add_argument(
            "--round",
            type=int,
            help="round to call",
        )

        parser.add_argument(
            "--type",
            type=str,
            help="round to call",
        )

        parser.add_argument(
            "--dry-run", #it's a boolean flag, if present it will roll back at the end
            action="store_true",
            help="Execute command without final commit",
        )
    
    @transaction.atomic
    def handle(self, *args, **options):
        year: int = options["year"]
        round: int = options["round"]
        type: str = options["type"]
        dry_run: bool = options["dry_run"]
        weekend = Weekend.objects.get(season=year, round_number=round)
        race, _ = Race.objects.get_or_create(
            weekend=weekend,
            defaults={"type": type}
        )
        quali_objs :list[RaceEntry] = []
        for data in get_race_result(year, round):
            fast_lap = parse_duration(data["fast_lap"]) if data["fast_lap"] else None
            quali_objs.append(
                RaceEntry(
                    race = race,
                    driver = Driver.objects.get(api_id=data["driver_api_id"]),
                    position = data["position"],
                    status = data["status"],
                    starting_grid = data["starting_grid"],
                    points = data["points"],
                    best_lap = data["best_lap"],
                    fast_lap = fast_lap,
                )
            )

        RaceEntry.objects.bulk_create(quali_objs, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"• Races resuls imported: {len(quali_objs)}"))

        # ------------------------------------------------------------------
        # Commit / Rollback
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry‑run active: volontary rollback"))
            raise transaction.TransactionManagementError("Dry‑run — transaction rollback")

        self.stdout.write(self.style.SUCCESS("=== Import succeded ==="))
    
