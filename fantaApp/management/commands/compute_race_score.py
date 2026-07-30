"""
Management command: `python manage.py compute_race_score --season <year> --round <number> --type <type>`

Calcola i punti dei giocatori per una singola gara tramite
la funzione `compute_player_score_per_race` del layer `services`.
"""

from django.core.management.base import BaseCommand
from fantaApp.models import Race, Weekend
from fantaApp.services.player_scoring import compute_player_score_per_race


class Command(BaseCommand):
    help = "compute all players score for a single race"

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
            help="sprint o regular",
        )

    def handle(self, *args, **options):
        season = options["season"]
        round_number = options["round"]
        race_type = options["type"]

        weekend = Weekend.objects.get(season=season, round_number=round_number)
        race = Race.objects.get(weekend=weekend, type=race_type)

        stats = compute_player_score_per_race(race=race)

        self.stdout.write(self.style.SUCCESS(f"Race: {stats['race']}"))
        self.stdout.write(self.style.SUCCESS(f"Giocatori aggiornati: {stats['players_updated']}"))

        if stats["errors"]:
            self.stdout.write(self.style.WARNING(f"Errori riscontrati: {len(stats['errors'])}"))
            for err in stats["errors"]:
                self.stderr.write(f"  • {err['player']} - {err['race']}: {err['error']}")