"""
Management command: `python manage.py process_pending_races`

Elabora gli EventProcessingStatus di tipo Race "eligible" (pending o
waiting_for_results con eligible_after nel passato): importa i risultati gara
e calcola i punteggi, aggiornando lo stato di avanzamento.

Una race viene saltata (senza consumare un tentativo) finche' la Qualifying
corrispondente non e' "processed": il calcolo del punteggio dipende dal bonus
qualifica, quindi va invocato DOPO process_pending_qualifying.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from fantaApp.models import EventProcessingStatus, Qualifying, Status
from fantaApp.services.jolpicaSource import ResultsNotAvailable

MAX_WAITING_ATTEMPTS = 10


class Command(BaseCommand):
    help = "Processa gli EventProcessingStatus di gara eligible: importa i risultati e calcola i punteggi"

    def _process_race(self, race):
        call_command("insert_race_result", season=race.weekend.season, round=race.weekend.round_number, type=race.type)
        call_command("compute_race_score", season=race.weekend.season, round=race.weekend.round_number, type=race.type)

    def _qualifying_ready(self, race) -> bool:
        qualifying = Qualifying.objects.filter(weekend=race.weekend, type=race.type).select_related("processing_status").first()
        return bool(qualifying) and qualifying.processing_status.status == Status.PROCESSED

    def handle(self, *args, **options):
        now = timezone.now()
        eligible = (
            EventProcessingStatus.objects.select_related("race__weekend")
            .filter(
                race__isnull=False,
                status__in=[Status.PENDING, Status.WAITING_FOR_RESULTS],
                eligible_after__lte=now,
            )
            .order_by("eligible_after")
        )

        processed = waiting = errored = skipped = 0

        for event_status in eligible:
            race = event_status.race

            if not self._qualifying_ready(race):
                skipped += 1
                self.stdout.write(self.style.WARNING(f"… {race}: in attesa della qualifica corrispondente"))
                continue

            try:
                self._process_race(race)
            except ResultsNotAvailable:
                event_status.attempts += 1
                event_status.last_attempt_at = now
                if event_status.attempts >= MAX_WAITING_ATTEMPTS:
                    event_status.status = Status.ERROR
                    event_status.last_error = "Risultati non disponibili dopo il numero massimo di tentativi"
                    errored += 1
                    self.stdout.write(
                        self.style.ERROR(f"✗ {race}: nessun risultato dopo {event_status.attempts} tentativi")
                    )
                else:
                    event_status.status = Status.WAITING_FOR_RESULTS
                    waiting += 1
                    self.stdout.write(self.style.WARNING(f"… {race}: risultati non ancora disponibili"))
                event_status.save(update_fields=["status", "attempts", "last_attempt_at", "last_error"])
            except Exception as exc:
                event_status.status = Status.ERROR
                event_status.attempts += 1
                event_status.last_attempt_at = now
                event_status.last_error = str(exc)
                event_status.save(update_fields=["status", "attempts", "last_attempt_at", "last_error"])
                errored += 1
                self.stdout.write(self.style.ERROR(f"✗ {race}: {exc}"))
            else:
                event_status.status = Status.PROCESSED
                event_status.attempts += 1
                event_status.last_attempt_at = now
                event_status.save(update_fields=["status", "attempts", "last_attempt_at"])
                processed += 1
                self.stdout.write(self.style.SUCCESS(f"✓ {race}: elaborata"))

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"=== Completato: {processed} processate, {waiting} in attesa, {skipped} in attesa di qualifica, {errored} in errore ==="
            )
        )
