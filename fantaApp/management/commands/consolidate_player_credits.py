"""
Management command: `python manage.py consolidate_player_credits --season <year> --round <number> --type <type>`

Consolida (addebita definitivamente) i crediti prenotati per le scelte di una
singola gara, per tutti i giocatori, tramite la funzione `consolidate_race_credits`
del layer `services`.
"""

from django.core.management.base import BaseCommand
from fantaApp.models import Race, Weekend
from fantaApp.services.credit_consolidation import consolidate_race_credits

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

        updated_count = consolidate_race_credits(race=race)

        self.stdout.write(self.style.SUCCESS(f"Race: {race}"))
        self.stdout.write(self.style.SUCCESS(f"Giocatori aggiornati: {updated_count}"))