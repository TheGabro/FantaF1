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

from django.core.management import CommandError, call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from fantaApp.models import EventProcessingStatus, Qualifying, Status
from fantaApp.services.sources.jolpicaSource import ResultsNotAvailable
from fantaApp.services.event_processing import qualifying_ready, mark, eligible_events

MAX_WAITING_ATTEMPTS = 10


class Command(BaseCommand):
    help = "Event processing: process pending events in chronological order"

    def _process_race(self, race):
        season, round_number = race.weekend.season, race.weekend.round_number
        call_command(
            "consolidate_player_credits",
            season=season,
            round=round_number,
            type=race.type,
        )
        call_command(
            "insert_race_result", season=season, round=round_number, type=race.type
        )
        if race.type == "regular":
            call_command(
                "insert_round_driver_standings", season=season, round=round_number
            )
        call_command(
            "compute_race_score", season=season, round=round_number, type=race.type
        )

    def _process_qualifying(self, qualifying):
        call_command(
            "insert_quali_result",
            season=qualifying.weekend.season,
            round=qualifying.weekend.round_number,
            type=qualifying.type,
        )

    def handle(self, *args, **options):
        now = timezone.now()

        eligible = eligible_events(now)

        processed = waiting = errored = skipped = 0

        for event_status in eligible:
            event = event_status.race or event_status.qualifying

            # La guardia sta fuori dal try: non puo' sollevare ResultsNotAvailable,
            # e se la query fallisse non avrebbe senso marcare la gara in errore.
            if event_status.race and not qualifying_ready(event_status.race):
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"… {event}: qualifying non ancora processed, skipping"
                    )
                )
                break

            try:
                if event_status.race:
                    self._process_race(event_status.race)
                else:
                    self._process_qualifying(event_status.qualifying)
            except CommandError as exc:
                if exc.returncode != 3:
                    raise
                final_status = mark(
                    event_status, status=Status.WAITING_FOR_RESULTS, now=now
                )
            except Exception as exc:
                mark(event_status, status=Status.ERROR, now=now, error=str(exc))
                errored += 1
                self.stdout.write(self.style.ERROR(f"✗ {event}: {exc}"))
            else:
                mark(event_status, status=Status.PROCESSED, now=now)
                processed += 1
                self.stdout.write(self.style.SUCCESS(f"✓ {event}: processed"))

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"=== Completed: {processed} processed, {waiting} waiting for results, "
                f"{skipped} blocked by a qualifying, {errored} in error ==="
            )
        )
