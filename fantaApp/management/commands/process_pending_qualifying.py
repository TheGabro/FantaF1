"""
Management command: `python manage.py process_pending_qualifying`

Elabora gli EventProcessingStatus di tipo Qualifying "eligible" (pending o
waiting_for_results con eligible_after nel passato): importa i risultati di
qualifica e aggiorna lo stato di avanzamento.

Pensato per essere invocato periodicamente da uno scheduler esterno (Airflow),
PRIMA di process_pending_races: il calcolo del punteggio gara dipende dai
risultati di qualifica (bonus qualifica).
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from fantaApp.models import EventProcessingStatus, Status
from fantaApp.services.jolpicaSource import ResultsNotAvailable

MAX_WAITING_ATTEMPTS = 10


class Command(BaseCommand):
    help = "Processa gli EventProcessingStatus di qualifica eligible: importa i risultati"

    def _process_qualifying(self, qualifying):
        call_command(
            "insert_quali_result",
            season=qualifying.weekend.season,
            round=qualifying.weekend.round_number,
            type=qualifying.type,
        )

    def handle(self, *args, **options):
        now = timezone.now()
        eligible = (
            EventProcessingStatus.objects.select_related("qualifying__weekend")
            .filter(
                qualifying__isnull=False,
                status__in=[Status.PENDING, Status.WAITING_FOR_RESULTS],
                eligible_after__lte=now,
            )
            .order_by("eligible_after")
        )

        processed = waiting = errored = 0

        for event_status in eligible:
            qualifying = event_status.qualifying
            try:
                self._process_qualifying(qualifying)
            except ResultsNotAvailable:
                event_status.attempts += 1
                event_status.last_attempt_at = now
                if event_status.attempts >= MAX_WAITING_ATTEMPTS:
                    event_status.status = Status.ERROR
                    event_status.last_error = "Risultati non disponibili dopo il numero massimo di tentativi"
                    errored += 1
                    self.stdout.write(
                        self.style.ERROR(f"✗ {qualifying}: nessun risultato dopo {event_status.attempts} tentativi")
                    )
                else:
                    event_status.status = Status.WAITING_FOR_RESULTS
                    waiting += 1
                    self.stdout.write(self.style.WARNING(f"… {qualifying}: risultati non ancora disponibili"))
                event_status.save(update_fields=["status", "attempts", "last_attempt_at", "last_error"])
            except Exception as exc:
                event_status.status = Status.ERROR
                event_status.attempts += 1
                event_status.last_attempt_at = now
                event_status.last_error = str(exc)
                event_status.save(update_fields=["status", "attempts", "last_attempt_at", "last_error"])
                errored += 1
                self.stdout.write(self.style.ERROR(f"✗ {qualifying}: {exc}"))
            else:
                event_status.status = Status.PROCESSED
                event_status.attempts += 1
                event_status.last_attempt_at = now
                event_status.save(update_fields=["status", "attempts", "last_attempt_at"])
                processed += 1
                self.stdout.write(self.style.SUCCESS(f"✓ {qualifying}: elaborata"))

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"=== Completato: {processed} processate, {waiting} in attesa, {errored} in errore ==="
            )
        )
