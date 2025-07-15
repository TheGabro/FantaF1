from django.utils.dateparse import parse_duration

from django.core.management.base import BaseCommand
from django.db import transaction

from fantaApp.models import Weekend, Qualifying, Driver, QualifyingEntry
from fantaApp.services.jolpicaSource import get_qualifying_result


class Command(BaseCommand):
    help = "Import last qualyfication result"

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
            "--dry-run", #it's a boolean flag, if present it will roll back at the end
            action="store_true",
            help="Execute command without final commit",
        )
    
    @transaction.atomic
    def handle(self, *args, **options):
        year: int = options["year"]
        round: int = options["round"]
        dry_run: bool = options["dry_run"]
        weekend = Weekend.objects.get(season=year, round_number=round)
        qualifying, _ = Qualifying.objects.get_or_create(
            weekend=weekend,
            defaults={"type": "regular"}
        )
        quali_objs :list[QualifyingEntry] = []
        for data in get_qualifying_result(year, round):
            q1_time = parse_duration(data["q1_time"]) if data["q1_time"] else None
            q2_time = parse_duration(data["q2_time"]) if data["q2_time"] else None
            q3_time = parse_duration(data["q3_time"]) if data["q3_time"] else None
            quali_objs.append(
                QualifyingEntry(
                    qualifying = qualifying,
                    driver = Driver.objects.get(api_id=data["driver_api_id"]),
                    q1_time = q1_time,
                    q2_time = q2_time,
                    q3_time = q3_time,
                    best_lap = min(t for t in [q1_time, q2_time, q3_time] if t is not None),
                    position = data["position"]
                )
            )

        # Inserimento veloce: una singola INSERT
        QualifyingEntry.objects.bulk_create(quali_objs, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"• Races qualifying imported: {len(quali_objs)}"))

        # ------------------------------------------------------------------
        # Commit / Rollback
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry‑run active: volontary rollback"))
            raise transaction.TransactionManagementError("Dry‑run — transaction rollback")

        self.stdout.write(self.style.SUCCESS("=== Import succeded ==="))
    
