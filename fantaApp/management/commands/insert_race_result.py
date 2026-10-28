from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fantaApp.models import Weekend, Race, RaceResult, RaceStartingGrid
from fantaApp.services import drivers
from fantaApp.services.sources.base import ResultsNotAvailable
from fantaApp.services.sources.openF1Source import RACE_SESSION, get_race_result


class Command(BaseCommand):
    help = "Import race result"

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
            choices=RACE_SESSION.keys(),
            help="sprint o regular",
        )

        parser.add_argument(
            "--dry-run",  # it's a boolean flag, if present it will roll back at the end
            action="store_true",
            help="Execute command without final commit",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        season: int = options["season"]
        round: int = options["round"]
        r_type: str = options["type"]
        dry_run: bool = options["dry_run"]
        weekend = Weekend.objects.get(season=season, round_number=round)
        race = Race.objects.get(weekend=weekend, type=r_type)

        session_name, start_field = RACE_SESSION[r_type]
        try:
            results = get_race_result(season, session_name, getattr(weekend, start_field))
        except ResultsNotAvailable as exc:
            raise CommandError(str(exc), returncode=3)

        # The official grid is imported after the qualifying (insert_starting_grid)
        grid = dict(
            RaceStartingGrid.objects.filter(race=race).values_list("driver_id", "position")
        )

        race_objs: list[RaceResult] = []
        for data in results:
            driver = drivers.get_driver_by_number(
                season=season, number=data["driver_number"]
            )
            race_objs.append(
                RaceResult(
                    race=race,
                    driver=driver,
                    position=data["position"],
                    status=data["status"],
                    starting_grid=grid.get(driver.id),
                    points=data["points"],
                    best_lap=data["best_lap"],
                    fast_lap=data["fast_lap"],
                )
            )

        RaceResult.objects.bulk_create(race_objs, ignore_conflicts=True)
        self.stdout.write(
            self.style.SUCCESS(f"• Races resuls imported: {len(race_objs)}")
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
