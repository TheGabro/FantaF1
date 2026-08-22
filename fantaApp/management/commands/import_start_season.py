"""
Management command: `python manage.py import_start_season [--season <year>] [--dry-run]`

Scarica piloti, circuiti e calendario per la stagione indicata tramite
le funzioni del layer `services` e li salva/aggiorna nel database Django.
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from fantaApp.models import Circuit, Driver, Weekend, Team, Race, Qualifying, EventProcessingStatus
from fantaApp.services import helper
from fantaApp.services.jolpicaSource import (
    get_circuits,
    get_drivers,
    get_weekends,
    get_teams,
)

# Le results F1 ufficiali arrivano con un certo ritardo dopo la bandiera a
# scacchi: un evento diventa "eligible" per l'elaborazione solo un po' dopo
# il suo orario di inizio ufficiale, non subito.
ELIGIBLE_AFTER_DELAY = timedelta(hours=2)


class Command(BaseCommand):
    help = "Import Season beginning"

    def _save_driver(self, *, season: int, data: dict, team: Team) -> Driver:
        short_name = data["short_name"] or data["drivers_api_id"][:3].upper()
        defaults = {
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "number": data["number"],
            "short_name": short_name,
            "season": season,
            "team": team,
        }

        driver = Driver.objects.filter(api_id=data["drivers_api_id"]).first()
        if driver:
            for field, value in defaults.items():
                setattr(driver, field, value)
            driver.save(update_fields=[*defaults.keys()])
            return driver

        fallback_driver = None
        if data["number"] is not None:
            fallback_driver = Driver.objects.filter(season=season, number=data["number"]).first()

        if fallback_driver is None:
            fallback_driver = Driver.objects.filter(
                season=season,
                first_name=data["first_name"],
                last_name=data["last_name"],
            ).first()

        if fallback_driver:
            old_api_id = fallback_driver.api_id
            for field, value in defaults.items():
                setattr(fallback_driver, field, value)
            fallback_driver.api_id = data["drivers_api_id"]
            fallback_driver.save(update_fields=["api_id", *defaults.keys()])
            self.stdout.write(
                self.style.WARNING(
                    f"Updated existing driver match for {fallback_driver.first_name} {fallback_driver.last_name}: "
                    f"api_id {old_api_id} -> {fallback_driver.api_id}"
                )
            )
            return fallback_driver

        return Driver.objects.get_or_create(api_id=data["drivers_api_id"], **defaults)

    def _init_processing_status(self, *, race=None, qualifying=None):
        event = race or qualifying
        start = helper.event_start(event)
        if not start:
            self.stdout.write(self.style.WARNING(f"Skipped processing status for {event}: no start time"))
            return

        if timezone.is_naive(start):
            start = timezone.make_aware(start, timezone.utc)

        EventProcessingStatus.objects.get_or_create(
            race=race,
            qualifying=qualifying,
            defaults={"eligible_after": start + ELIGIBLE_AFTER_DELAY},
        )

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            help="season to inizialize",
        )
        parser.add_argument(
            "--dry-run", #it's a boolean flag, if present it will roll back at the end
            action="store_true",
            help="Execute command without final commit",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        season: int = options["season"]
        dry_run: bool = options["dry_run"]

        self.stdout.write(self.style.MIGRATE_HEADING(f"=== Import season {season} ==="))

        # ------------------------------------------------------------------
        # 1) Circuits
        # ------------------------------------------------------------------
        circuits_cache: dict[str, Circuit] = {}
        for data in get_circuits(season):
            circuit, _ = Circuit.objects.get_or_create(
                api_id=data["circuit_api_id"],
                defaults={
                    "name": data["name"],
                    "country": data["country"],
                    "location": data["location"],
                },
            )
            circuits_cache[circuit.api_id] = circuit
        self.stdout.write(self.style.SUCCESS(f"• Circuits imported: {len(circuits_cache)}"))
        
        
        # ------------------------------------------------------------------
        # 2) Teams
        # ------------------------------------------------------------------
        
        teams_cache: dict[str, Team] = {}
        for data in get_teams(season):
            team, _ = Team.objects.get_or_create(
                api_id=data["constructor_api_id"],
                defaults={
                    "name": data['name'],
                    "nationality": data['nationality'],
                    "short_name": data['short_name']
                },
            )
            teams_cache[team.api_id] = team
        self.stdout.write(self.style.SUCCESS(f"• Teams imported: {len(teams_cache)}"))
    
            

        # ------------------------------------------------------------------
        # 3) Drivers
        # ------------------------------------------------------------------
        drivers_payload = get_drivers(season)
        for data in drivers_payload:
            self._save_driver(
                season=season,
                data=data,
                team=teams_cache[data["team"]],
            )
        self.stdout.write(self.style.SUCCESS(f"• Drivers imported: {len(drivers_payload)}"))
        

        # ------------------------------------------------------------------
        # 4) Weekends
        # ------------------------------------------------------------------
        weekends_payload = get_weekends(season)
        weekend_cache: dict[tuple[int, int], Weekend] = {}
        for data in weekends_payload:
            weekend, _ = Weekend.objects.get_or_create(
                season=season,
                round_number=data["round_number"],
                defaults={
                    "circuit": circuits_cache[data["circuit_api_id"]],
                    "event_name": data["event_name"],
                    "weekend_type": data['weekend_type'],
                    "fp1_start": datetime.strptime(data["fp1_start"], '%Y-%m-%d %H:%M:00Z'),
                    "fp2_start": datetime.strptime(data["fp2_start"], '%Y-%m-%d %H:%M:00Z') if 'fp2_start' in data else None,
                    "fp3_start": datetime.strptime(data["fp3_start"], '%Y-%m-%d %H:%M:00Z') if 'fp3_start' in data else None,
                    "sprint_qualifying_start": datetime.strptime(data["sprint_qualifying_start"], '%Y-%m-%d %H:%M:00Z') if 'sprint_qualifying_start' in data else None,
                    "sprint_start": datetime.strptime(data["sprint_start"], '%Y-%m-%d %H:%M:00Z') if 'sprint_start' in data else None,
                    "qualifying_start": datetime.strptime(data["qualifying_start"], '%Y-%m-%d %H:%M:00Z'),
                    "race_start": datetime.strptime(data["race_start"], '%Y-%m-%d %H:%M:00Z'),
                },
            )
            weekend_cache[(season, data["round_number"])] = weekend

        self.stdout.write(self.style.SUCCESS(f"• Races imported: {len(weekends_payload)}"))
        
        
        # ------------------------------------------------------------------
        # 4b) Races & Qualifying sessions
        # ------------------------------------------------------------------
        race_count = 0
        qualifying_count = 0

        for w in Weekend.objects.filter(season=season):

            # Il GP della domenica (type="regular") c'e' sempre; in piu', nei
            # weekend sprint, ci sono anche la sprint qualifying e la sprint race.
            event_types = ["regular"]
            if w.weekend_type == "sprint":
                event_types.append("sprint")

            for event_type in event_types:
                race, race_created = Race.objects.get_or_create(weekend=w, type=event_type)
                qualifying, qualifying_created = Qualifying.objects.get_or_create(weekend=w, type=event_type)

                # get_or_create qui sotto e' idempotente: se lo stato esiste
                # gia' non lo tocca, quindi va bene chiamarlo sempre e non solo
                # per le Race/Qualifying create in questo run (serve a
                # "recuperare" anche gli eventi creati da run precedenti).
                self._init_processing_status(race=race)
                self._init_processing_status(qualifying=qualifying)

                race_count += 1 if race_created else 0
                qualifying_count += 1 if qualifying_created else 0

        self.stdout.write(self.style.SUCCESS(f"• Race rows ready: {race_count} created"))
        self.stdout.write(self.style.SUCCESS(f"• Qualifying rows ready: {qualifying_count} created"))

        

        # ------------------------------------------------------------------
        # Commit / Rollback
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry‑run active: volontary rollback"))
            raise transaction.TransactionManagementError("Dry‑run — transaction rollback")

        self.stdout.write(self.style.SUCCESS("=== Import succeded ==="))