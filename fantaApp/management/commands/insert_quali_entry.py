from django.utils.dateparse import parse_duration

from django.core.management.base import BaseCommand
from django.db import transaction

from fantaApp.models import Weekend, Qualifying, Driver, QualifyingEntry
from fantaApp.services.jolpicaSource import get_qualifying_result
from fantaApp.services.fastf1Source import get_sprint_qualifying_entry


class Command(BaseCommand):
    help = "Import last qualyfication result"

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
            "--type",
            type=str,
            help="type of the event"
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
        type: str = options["type"]
        dry_run: bool = options["dry_run"]
        weekend = Weekend.objects.get(season=season, round_number=round)
        qualifying, _ = Qualifying.objects.get_or_create(
            weekend=weekend,
            defaults={"type": type}
        )
        quali_objs :list[QualifyingEntry] = []
        if type == 'regular':
            self.stdout.write(self.style.SUCCESS("=== Import regular qualigfying ==="))
            for data in get_qualifying_result(season, round):
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
        else:
            self.stdout.write(self.style.SUCCESS("=== Import sprint qualigfying ==="))
            for data in get_sprint_qualifying_entry(season, round):
                q1_time = parse_duration(data["q1_time"]) if data["q1_time"] else None
                q2_time = parse_duration(data["q2_time"]) if data["q2_time"] else None
                q3_time = parse_duration(data["q3_time"]) if data["q3_time"] else None
                driver_number = 33 if data["number"] == 1 else data["number"]
                quali_objs.append(
                    QualifyingEntry(
                        qualifying = qualifying,
                        driver = Driver.objects.get(number=driver_number, season = season),
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
    
