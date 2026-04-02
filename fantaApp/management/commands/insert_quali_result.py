from django.utils.dateparse import parse_duration

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fantaApp.models import Weekend, Qualifying, Driver, QualifyingResult
from fantaApp.services.jolpicaSource import get_qualifying_result
from fantaApp.services.fastf1Source import get_sprint_qualifying_result


def get_best_lap(*times):
    valid_times = [lap_time for lap_time in times if lap_time is not None]
    return min(valid_times) if valid_times else None


def resolve_fastf1_driver(*, season: int, data: dict) -> Driver:
    queryset = Driver.objects.filter(season=season)

    short_name = data.get("short_name")
    if short_name:
        driver = queryset.filter(short_name__iexact=short_name).first()
        if driver:
            return driver

    number = data.get("number")
    if number:
        driver = queryset.filter(number=number).first()
        if driver:
            return driver

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    if first_name and last_name:
        driver = queryset.filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name,
        ).first()
        if driver:
            return driver

    raise CommandError(
        "Impossibile fare match del pilota FastF1: "
        f"short_name={short_name}, number={number}, "
        f"first_name={first_name}, last_name={last_name}, "
        f"fastf1_driver_id={data.get('fastf1_driver_id')}, season={season}"
    )


class Command(BaseCommand):
    """
    Management command: `python manage.py insert_quali_result [--season <year>] [--round <number>] [--type <type>] [--dry-run]`
    """

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
        
    TYPES = [
        ('regular', 'Regular Race Qualifying'),
        ('sprint', 'Sprint Race Qualifying')
    ]
    
    @transaction.atomic
    def handle(self, *args, **options):
        season: int = options["season"]
        round: int = options["round"]
        q_type: str = options["type"]
        dry_run: bool = options["dry_run"]
        weekend = Weekend.objects.get(season=season, round_number=round)
        qualifying = Qualifying.objects.get(
            weekend=weekend,
            type = q_type
        )
        quali_objs :list[QualifyingResult] = []
        if q_type == 'regular':
            self.stdout.write(self.style.SUCCESS("=== Import regular qualigfying ==="))
            for data in get_qualifying_result(season, round):
                q1_time = parse_duration(data["q1_time"]) if data["q1_time"] else None
                q2_time = parse_duration(data["q2_time"]) if data["q2_time"] else None
                q3_time = parse_duration(data["q3_time"]) if data["q3_time"] else None
                # self.stdout.write(
                #     f"Looking up regular driver with api_id={data['driver_api_id']}"
                # )
                driver = Driver.objects.get(api_id=data["driver_api_id"])
                # self.stdout.write(
                #     f"Saving regular qualifying result for driver: "
                #     f"{driver.first_name} {driver.last_name} "
                #     f"(api_id={driver.api_id}, season={driver.season})"
                # )
                quali_objs.append(
                    QualifyingResult(
                        qualifying=qualifying,
                        driver=driver,
                        q1_time=q1_time,
                        q2_time=q2_time,
                        q3_time=q3_time,
                        best_lap=get_best_lap(q1_time, q2_time, q3_time),
                        position=data["position"]
                    )
                )
        else:
            self.stdout.write(self.style.SUCCESS("=== Import sprint qualigfying ==="))
            for data in get_sprint_qualifying_result(season, round):
                q1_time = parse_duration(data["q1_time"]) if data["q1_time"] else None
                q2_time = parse_duration(data["q2_time"]) if data["q2_time"] else None
                q3_time = parse_duration(data["q3_time"]) if data["q3_time"] else None
                driver = resolve_fastf1_driver(season=season, data=data)
                quali_objs.append(
                    QualifyingResult(
                        qualifying=qualifying,
                        driver=driver,
                        q1_time=q1_time,
                        q2_time=q2_time,
                        q3_time=q3_time,
                        best_lap=get_best_lap(q1_time, q2_time, q3_time),
                        position=data["position"],
                    )
                )
        

        # Inserimento veloce: una singola INSERT
        QualifyingResult.objects.bulk_create(quali_objs, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"• Races qualifying imported: {len(quali_objs)}"))

        # ------------------------------------------------------------------
        # Commit / Rollback
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry‑run active: volontary rollback"))
            raise transaction.TransactionManagementError("Dry‑run — transaction rollback")

        self.stdout.write(self.style.SUCCESS("=== Import succeded ==="))
    
