"""
Management command:
`python manage.py rollback_event --season <year> --round <number> --type <regular|sprint> --event <race|qualifying> [--dry-run]`
`python manage.py rollback_event --all [--dry-run]`

Annulla l'elaborazione di uno o tutti gli eventi: cancella i dati importati/calcolati
e riporta l'EventProcessingStatus a "pending", cosi' che process_pending_qualifying/
process_pending_races lo riprenda al prossimo giro. Utile per correggere un evento finito in "error"
(o "processed" con dati sbagliati) senza dover intervenire a mano sul DB.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fantaApp.models import (
    EventProcessingStatus,
    PlayerRaceResult,
    QualifyingResult,
    Race,
    RaceResult,
    Qualifying,
    Status,
    Weekend,
)


class Command(BaseCommand):
    help = "Annulla l'elaborazione di uno o tutti gli eventi e li rimette in pending"

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int)
        parser.add_argument("--round", type=int)
        parser.add_argument("--type", type=str, choices=["regular", "sprint"])
        parser.add_argument("--event", type=str, choices=["race", "qualifying"])
        parser.add_argument(
            "--all",
            action="store_true",
            help="Rollback di tutti gli EventProcessingStatus esistenti, invece di uno solo",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Esegue senza commit finale (rollback volontario)",
        )

    def _rollback_one(self, event_status: EventProcessingStatus):
        if event_status.race:
            race = event_status.race
            deleted_results, _ = RaceResult.objects.filter(race=race).delete()
            deleted_scores, _ = PlayerRaceResult.objects.filter(race=race).delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f"• {race}: {deleted_results} RaceResult, {deleted_scores} PlayerRaceResult cancellati"
                )
            )
        else:
            qualifying = event_status.qualifying
            deleted_results, _ = QualifyingResult.objects.filter(
                qualifying=qualifying
            ).delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f"• {qualifying}: {deleted_results} QualifyingResult cancellati"
                )
            )

        event_status.status = Status.PENDING
        event_status.attempts = 0
        event_status.last_attempt_at = None
        event_status.last_error = ""
        event_status.save(
            update_fields=["status", "attempts", "last_attempt_at", "last_error"]
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rollback_all: bool = options["all"]
        dry_run: bool = options["dry_run"]

        if rollback_all:
            statuses = list(
                EventProcessingStatus.objects.select_related("race", "qualifying")
            )
        else:
            required = ("season", "round", "type", "event")
            missing = [name for name in required if options[name] is None]
            if missing:
                raise CommandError(
                    f"Senza --all servono tutti questi argomenti: {', '.join('--' + m for m in missing)}"
                )

            weekend = Weekend.objects.get(
                season=options["season"], round_number=options["round"]
            )
            if options["event"] == "race":
                race = Race.objects.get(weekend=weekend, type=options["type"])
                statuses = [EventProcessingStatus.objects.get(race=race)]
            else:
                qualifying = Qualifying.objects.get(
                    weekend=weekend, type=options["type"]
                )
                statuses = [EventProcessingStatus.objects.get(qualifying=qualifying)]

        for event_status in statuses:
            self._rollback_one(event_status)

        self.stdout.write(
            self.style.SUCCESS(f"• {len(statuses)} evento/i rimesso/i in 'pending'")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run attivo: rollback volontario"))
            raise transaction.TransactionManagementError(
                "Dry-run — transaction rollback"
            )

        self.stdout.write(self.style.SUCCESS("=== Rollback completato ==="))
