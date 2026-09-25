"""Management command: `python manage.py set_seat --season <year> --from-round <n> [--dry-run]`

Interattivo: chiede pilota, team e l'eventuale pilota sostituito, poi aggiorna
i WeekendParticipant dal round indicato in poi.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fantaApp.models import Driver, Team, WeekendParticipant
from fantaApp.services import weekend_participants


class Command(BaseCommand):
    help = "Move a driver to a team's seat from a given round onward"

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, required=True, help="season")
        parser.add_argument(
            "--from-round",
            type=int,
            required=True,
            help="first round with the new seat",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Execute command without final commit",
        )

    def handle(self, *args, **options):
        season, from_round = options["season"], options["from_round"]

        driver = self._choose(
            list(
                Driver.objects.filter(season=season, number__isnull=False).order_by(
                    "last_name"
                )
            ),
            prompt="Which driver changes seat?",
            label=lambda d: f"{d.short_name} ({d.api_id})",
        )
        current_seat = (
            WeekendParticipant.objects.filter(
                weekend__season=season, weekend__round_number=from_round, driver=driver
            )
            .select_related("team")
            .first()
        )
        if current_seat:
            self.stdout.write(
                f"{driver.short_name} is in {current_seat.team.name} in R{from_round}"
            )
        while True:
            team = self._choose(
                list(Team.objects.filter(active=True)),
                prompt=f"Which team does {driver.short_name} drive for now?",
                label=lambda t: f"{t.name} ({t.api_id})",
            )
            if current_seat is None or current_seat.team_id != team.pk:
                break
            self.stdout.write(
                self.style.WARNING(
                    f"{driver.short_name} already drives for {team.name}: choose another team"
                )
            )
        seats = list(
            WeekendParticipant.objects.filter(
                weekend__season=season, weekend__round_number=from_round, team=team
            )
            .exclude(driver=driver)
            .select_related("driver")
        )
        replaced_seat = self._choose(
            seats,
            prompt=f"Who does {driver.short_name} replace? [enter = nobody]",
            label=lambda s: f"{s.driver.short_name} ({s.driver.api_id})",
            allow_none=True,
        )
        replaces = replaced_seat.driver if replaced_seat else None

        summary = f"{driver.short_name} -> {team.api_id} from R{from_round}"
        if replaces:
            summary += f", replaces {replaces.short_name}"
        if input(f"{summary}. Confirm? [y/N]: ").strip().lower() != "y":
            raise CommandError("Aborted")

        with transaction.atomic():
            try:
                changes = weekend_participants.set_seat(
                    season=season,
                    from_round=from_round,
                    driver=driver,
                    team=team,
                    replaces=replaces,
                )
            except ValueError as e:
                raise CommandError(str(e))

            for change in changes:
                self.stdout.write(f"• {change}")
            if not changes:
                self.stdout.write("No changes")

            if options["dry_run"]:
                raise transaction.TransactionManagementError(
                    "Dry-run — transaction rollback"
                )
        self.stdout.write(self.style.SUCCESS("• Seat updated"))

    def _choose(self, items, *, prompt, label, allow_none=False):
        """Stampa `items` numerati e ripete la domanda finche' la risposta non e' valida."""
        if not items and not allow_none:
            raise CommandError(f"Nothing to choose from: {prompt}")
        for i, item in enumerate(items, start=1):
            self.stdout.write(f"  {i}) {label(item)}")
        while True:
            answer = input(f"{prompt}: ").strip()
            if not answer and allow_none:
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(items):
                return items[int(answer) - 1]
            self.stdout.write(self.style.WARNING(f"Enter a number from 1 to {len(items)}"))
