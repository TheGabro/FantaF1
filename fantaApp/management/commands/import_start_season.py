

"""
Management command: `python manage.py import_f1 <year> [--dry-run]`

Scarica piloti, circuiti e calendario per la stagione indicata tramite
le funzioni del layer `services` e li salva/aggiorna nel database Django.
"""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from fantaApp.models import Circuit, Driver, Race, Team
from fantaApp.services.jolpicaSource import (
    get_circuits,
    get_drivers,
    get_races,
    get_teams,
)


class Command(BaseCommand):
    help = "Import Season beginning"

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            help="year to inizialize",
        )
        parser.add_argument(
            "--dry-run", #it's a boolean flag, if present it will roll back at the end
            action="store_true",
            help="Execute command without final commit",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        year: int = options["year"]
        dry_run: bool = options["dry_run"]

        self.stdout.write(self.style.MIGRATE_HEADING(f"=== Import season {year} ==="))

        # ------------------------------------------------------------------
        # 1) Circuits
        # ------------------------------------------------------------------
        circuits_cache: dict[str, Circuit] = {}
        for data in get_circuits(year):
            circuit, _ = Circuit.objects.update_or_create(
                api_id=data["circuit_api_id"],
                defaults={
                    "name": data["name"],
                    "country": data["country"],
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
        for data in get_teams(year):
            team, _ = Team.objects.update_or_create(
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
        drivers_payload = get_drivers(year)
        for data in drivers_payload:
            Driver.objects.update_or_create(
                api_id=data["drivers_api_id"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name":  data["last_name"],
                    "number":     data["number"],
                    "short_name": data["short_name"],
                    "season": year,
                    "team": teams_cache[data["team"]],
                },
            )
        self.stdout.write(self.style.SUCCESS(f"• Drivers imported: {len(drivers_payload)}"))
        

        # ------------------------------------------------------------------
        # 4) Races
        # ------------------------------------------------------------------
        races_payload = get_races(year)
        race_objs: list[Race] = []
        for data in races_payload:
            race_objs.append(
                Race(
                    circuit=circuits_cache[data["circuit_api_id"]],
                    season=year,
                    round_number=data["round_number"],
                    event_name=data["event_name"],
                    race_type = data['race_type'],
                    fp1_start=datetime.strptime(data["fp1_start"], '%Y-%m-%d %H:%M:00Z'),
                    fp2_start = datetime.strptime(data["fp2_start"], '%Y-%m-%d %H:%M:00Z') if 'fp2_start' in data else None,
                    fp3_start = datetime.strptime(data["fp3_start"], '%Y-%m-%d %H:%M:00Z') if 'fp3_start' in data else None,
                    sprint_qualifying_start = datetime.strptime(data["sprint_qualifying_start"], '%Y-%m-%d %H:%M:00Z') if 'sprint_qualifying_start' in data else None,
                    sprint_start = datetime.strptime(data["sprint_start"], '%Y-%m-%d %H:%M:00Z') if 'sprint_start' in data else None,
                    qualifying_start=datetime.strptime(data["qualifying_start"], '%Y-%m-%d %H:%M:00Z'),
                    race_start=datetime.strptime(data["race_start"], '%Y-%m-%d %H:%M:00Z')
                )
            )

        # Inserimento veloce: una singola INSERT
        Race.objects.bulk_create(race_objs, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"• Races imported: {len(races_payload)}"))

        # ------------------------------------------------------------------
        # Commit / Rollback
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry‑run active: volontary rollback"))
            raise transaction.TransactionManagementError("Dry‑run — transaction rollback")

        self.stdout.write(self.style.SUCCESS("=== Import succeded ==="))