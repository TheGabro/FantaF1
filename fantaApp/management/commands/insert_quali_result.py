from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fantaApp.models import Weekend, Qualifying, QualifyingResult
from fantaApp.services import drivers
from fantaApp.services.sources.base import ResultsNotAvailable
from fantaApp.services.sources.openF1Source import (
    QUALIFYING_SESSION,
    get_qualifying_result,
)


def get_best_lap(*times):
    valid_times = [lap_time for lap_time in times if lap_time is not None]
    return min(valid_times) if valid_times else None


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

        parser.add_argument("--type", type=str, choices=QUALIFYING_SESSION.keys())

        parser.add_argument(
            "--dry-run",  # it's a boolean flag, if present it will roll back at the end
            action="store_true",
            help="Execute command without final commit",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        season: int = options["season"]
        round: int = options["round"]
        q_type: str = options["type"]
        dry_run: bool = options["dry_run"]
        weekend = Weekend.objects.get(season=season, round_number=round)
        qualifying = Qualifying.objects.get(weekend=weekend, type=q_type)

        session_name, start_field = QUALIFYING_SESSION[q_type]
        try:
            results = get_qualifying_result(
                season, session_name, getattr(weekend, start_field)
            )
        except ResultsNotAvailable as exc:
            raise CommandError(str(exc), returncode=3)

        quali_objs: list[QualifyingResult] = []
        for data in results:
            quali_objs.append(
                QualifyingResult(
                    qualifying=qualifying,
                    driver=drivers.get_driver_by_number(
                        season=season, number=data["driver_number"]
                    ),
                    q1_time=data["q1_time"],
                    q2_time=data["q2_time"],
                    q3_time=data["q3_time"],
                    best_lap=get_best_lap(
                        data["q1_time"], data["q2_time"], data["q3_time"]
                    ),
                    position=data["position"],
                )
            )

        # Inserimento veloce: una singola INSERT
        QualifyingResult.objects.bulk_create(quali_objs, ignore_conflicts=True)
        self.stdout.write(
            self.style.SUCCESS(f"• {q_type} qualifying imported: {len(quali_objs)}")
        )

        # ------------------------------------------------------------------
        # Commit / Rollback
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry‑run active: volontary rollback"))
            raise transaction.TransactionManagementError(
                "Dry‑run — transaction rollback"
            )

        self.stdout.write(self.style.SUCCESS("=== Import succeded ==="))
