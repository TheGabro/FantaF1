"""
Management command: `python manage.py process_pending_events`

Elabora gli EventProcessingStatus "eligible" (pending o waiting_for_results con
eligible_after nel passato) in ordine cronologico, un evento alla volta:
importa i risultati di qualifica e gara e calcola i punteggi, aggiornando lo
stato di avanzamento.

L'ordine di eligible_after e' anche l'ordine di dipendenza: la qualifica di un
weekend precede sempre la gara corrispondente. Come rete di sicurezza, una gara
la cui Qualifying non e' "processed" interrompe la passata: ci si arriva solo se
la qualifica e' finita in errore, e proseguire significherebbe calcolare
punteggi su dati incompleti.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from fantaApp.models import EventProcessingStatus, Qualifying, Status
from fantaApp.services.jolpicaSource import ResultsNotAvailable

MAX_WAITING_ATTEMPTS = 10


class Command(BaseCommand):
    help = "Processa gli EventProcessingStatus eligible in ordine cronologico"

    def _process_race(self, race):
        call_command(
            "insert_race_result",
            season=race.weekend.season,
            round=race.weekend.round_number,
            type=race.type,
        )
        call_command(
            "compute_race_score",
            season=race.weekend.season,
            round=race.weekend.round_number,
            type=race.type,
        )

    def _process_qualifying(self, qualifying):
        call_command(
            "insert_quali_result",
            season=qualifying.weekend.season,
            round=qualifying.weekend.round_number,
            type=qualifying.type,
        )

    def _qualifying_ready(self, race) -> bool:
        qualifying = (
            Qualifying.objects
            .filter(weekend=race.weekend, type=race.type)
            .select_related("processing_status")
            .first()
        )
        return bool(qualifying) and qualifying.processing_status.status == Status.PROCESSED

    def _mark(self, event_status, *, status, now, error=""):
        """Registra l'esito di un tentativo sull'EventProcessingStatus."""
        event_status.status = status
        event_status.attempts += 1
        event_status.last_attempt_at = now
        event_status.last_error = error
        event_status.save(
            update_fields=["status", "attempts", "last_attempt_at", "last_error"]
        )

    def handle(self, *args, **options):
        now = timezone.now()
        eligible = (
            EventProcessingStatus.objects
            .select_related("race__weekend", "qualifying__weekend")
            .filter(
                status__in=[Status.PENDING, Status.WAITING_FOR_RESULTS],
                eligible_after__lte=now,
            )
            .order_by("eligible_after")
        )

        processed = waiting = errored = skipped = 0

        for event_status in eligible:
            event = event_status.race or event_status.qualifying

            # La guardia sta fuori dal try: non puo' sollevare ResultsNotAvailable,
            # e se la query fallisse non avrebbe senso marcare la gara in errore.
            if event_status.race and not self._qualifying_ready(event_status.race):
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"… {event}: qualifica non elaborata, mi fermo qui")
                )
                break

            try:
                if event_status.race:
                    self._process_race(event_status.race)
                else:
                    self._process_qualifying(event_status.qualifying)
            except ResultsNotAvailable:
                # _mark incrementa attempts, quindi il confronto guarda avanti di uno.
                if event_status.attempts + 1 >= MAX_WAITING_ATTEMPTS:
                    self._mark(
                        event_status,
                        status=Status.ERROR,
                        now=now,
                        error="Risultati non disponibili dopo il numero massimo di tentativi",
                    )
                    errored += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ {event}: nessun risultato dopo {event_status.attempts} tentativi"
                        )
                    )
                else:
                    self._mark(event_status, status=Status.WAITING_FOR_RESULTS, now=now)
                    waiting += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"… {event}: risultati non disponibili, tentativo {event_status.attempts}"
                        )
                    )
            except Exception as exc:
                self._mark(event_status, status=Status.ERROR, now=now, error=str(exc))
                errored += 1
                self.stdout.write(self.style.ERROR(f"✗ {event}: {exc}"))
            else:
                self._mark(event_status, status=Status.PROCESSED, now=now)
                processed += 1
                self.stdout.write(self.style.SUCCESS(f"✓ {event}: elaborato"))

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"=== Completato: {processed} elaborati, {waiting} in attesa dei risultati, "
                f"{skipped} bloccati da una qualifica, {errored} in errore ==="
            )
        )
