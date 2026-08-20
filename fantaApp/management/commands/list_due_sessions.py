from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from fantaApp.models import Weekend


class Command(BaseCommand):
    help = "Elenca le sessioni F1 i cui risultati dovrebbero essere verificati"
    
    SESSION_SPECS = (
        ("Sprint qualifying", "sprint_qualifying_start"),
        ("Sprint race", "sprint_start"),
        ("Qualifying", "qualifying_start"),
        ("Race", "race_start"),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--grace-minutes",
            type=int,
            default=120,
            help="Minuti da attendere dopo l'inizio della sessione",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        grace_minutes = options["grace_minutes"]
        cutoff = now - timedelta(minutes=grace_minutes)

        self.stdout.write(f"UTC now: {now.isoformat()}")
        self.stdout.write(f"Sessioni iniziate entro: {cutoff.isoformat()}")

        due_count = 0
        
        candidates = []

        for session_label, start_field in self.SESSION_SPECS:
            filters = {
                f"{start_field}__isnull": False,
                f"{start_field}__lte": cutoff,
            }

            weekends = Weekend.objects.filter(**filters).order_by(
                "season",
                "round_number",
            )

            for weekend in weekends:
                started_at = getattr(weekend, start_field)
                
                candidates.append(
                    (
                        weekend.season,
                        weekend.round_number,
                        started_at,
                        session_label,
                        weekend.event_name,
                    )
                )
        
        for season, round_number, started_at, session_label, event_name in sorted(
            candidates,
            key=lambda item: (item[0], item[1], item[2]),
        ):
            self.stdout.write(
                f"- {season} round {round_number}: "
                f"{event_name} | {session_label} | "
                f"start: {started_at.isoformat()}"
            )

        self.stdout.write(f"Totale sessioni candidate: {len(candidates)}")