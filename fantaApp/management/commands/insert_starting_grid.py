from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fantaApp.models import Race, RaceStartingGrid, Weekend
from fantaApp.services import drivers
from fantaApp.services.sources.jolpicaSource import ResultsNotAvailable
from fantaApp.services.sources.openF1Source import get_starting_grid

# OpenF1 ties the grid to the qualifying session of the same race type
QUALIFYING_SESSION_BY_RACE_TYPE = {
    "regular": ("Qualifying", "qualifying_start"),
    "sprint": ("Sprint Qualifying", "sprint_qualifying_start"),
}


class Command(BaseCommand):
    """
    Management command: `python manage.py insert_starting_grid --season <year> --round <number> --type <regular|sprint> [--dry-run]`
    """

    help = "Import the official starting grid from OpenF1"

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, help="season to call")
        parser.add_argument("--round", type=int, help="round to call")
        parser.add_argument(
            "--type", type=str, choices=QUALIFYING_SESSION_BY_RACE_TYPE.keys()
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

        session_name, start_field = QUALIFYING_SESSION_BY_RACE_TYPE[r_type]
        try:
            grid = get_starting_grid(
                season, session_name, getattr(weekend, start_field)
            )
        except ResultsNotAvailable as exc:
            raise CommandError(str(exc), returncode=3)

        driver_ids = []
        for data in grid:
            driver = drivers.find_driver(season=season, number=data["driver_number"])
            if driver is None:
                raise CommandError(
                    f"Driver #{data['driver_number']} not found for season {season}"
                )
            # update_or_create so a new run refreshes the grid
            RaceStartingGrid.objects.update_or_create(
                race=race, driver=driver, defaults={"position": data["position"]}
            )
            driver_ids.append(driver.id)

        # Drop drivers no longer on the grid (e.g. withdrawn after a previous run)
        RaceStartingGrid.objects.filter(race=race).exclude(
            driver_id__in=driver_ids
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(f"• Starting grid imported: {len(driver_ids)} drivers")
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
