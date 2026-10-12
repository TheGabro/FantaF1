from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from fantaApp.models import (
    ChampionshipPlayer,
    PlayerRaceChoice,
    PlayerRaceResult,
    Race,
    RaceResult,
)
from fantaApp.services import costs
from fantaApp.services import player_choices as pc
from fantaApp.services.player_scoring import compute_player_score_per_race

INITIAL_CREDIT = ChampionshipPlayer._meta.get_field("available_credit").default


class Command(BaseCommand):
    """
    Management command: `python manage.py recompute_race_costs --season <year> [--dry-run]`

    One-off fix: race choice costs were computed from the qualifying order
    instead of the official starting grid. Recompute every choice cost from
    RaceStartingGrid, then rebuild player credits and scores from scratch.
    """

    help = "Recompute race choice costs from the starting grid, then credits and scores"

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, required=True)
        parser.add_argument(
            "--dry-run",  # it's a boolean flag, if present it will roll back at the end
            action="store_true",
            help="Execute command without final commit",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        season: int = options["season"]
        dry_run: bool = options["dry_run"]
        players = list(ChampionshipPlayer.objects.filter(championship__year=season))

        self._check_credits_untouched(players)
        self._recompute_choice_costs(season)
        self._rebuild_credits(players)
        self._rebuild_scores(season, players)

        # ------------------------------------------------------------------
        # Commit / Rollback
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry‑run active: volontary rollback"))
            raise transaction.TransactionManagementError(
                "Dry‑run — transaction rollback"
            )

        self.stdout.write(self.style.SUCCESS("=== Recompute succeded ==="))

    def _applied_spent(self, player) -> int:
        return (
            PlayerRaceChoice.objects.filter(
                player=player, credit_applied=True
            ).aggregate(total=Sum("spent_amount"))["total"]
            or 0
        )

    def _check_credits_untouched(self, players):
        # Credits are rebuilt as INITIAL_CREDIT - applied costs: abort if any
        # player's credit was edited by hand, the rebuild would wipe it out
        edited = [
            f"{p.player_name} ({p.championship}): {p.available_credit} + "
            f"{self._applied_spent(p)} != {INITIAL_CREDIT}"
            for p in players
            if p.available_credit + self._applied_spent(p) != INITIAL_CREDIT
        ]
        if edited:
            raise CommandError(
                "Credits edited by hand, fix them before recomputing:\n"
                + "\n".join(edited)
            )

    def _recompute_choice_costs(self, season):
        self.stdout.write(self.style.SUCCESS("=== Choice costs ==="))
        choices_by_race_player = defaultdict(list)
        for choice in PlayerRaceChoice.objects.filter(
            race__weekend__season=season
        ).select_related("race__weekend", "player", "driver"):
            choices_by_race_player[(choice.race, choice.player)].append(choice)

        changed = 0
        for (race, player), choices in sorted(
            choices_by_race_player.items(),
            key=lambda item: (item[0][0].weekend.round_number, item[0][0].type),
        ):
            driver_ids = [choice.driver_id for choice in choices]
            options = costs.get_race_driver_options(
                race=race,
                player=player if race.type == "regular" else None,
                driver_ids=driver_ids,
            )
            options_by_driver_id = {option["driver"].id: option for option in options}

            if any(driver_id not in options_by_driver_id for driver_id in driver_ids):
                self.stdout.write(
                    self.style.WARNING(
                        f"• {race} - {player.player_name}: driver not on the grid, cost kept"
                    )
                )
                continue

            if race.type == "sprint":
                amount = pc.get_sprint_race_spent_amount(
                    player=player,
                    race=race,
                    driver_ids=driver_ids,
                    options_by_driver_id=options_by_driver_id,
                )
                new_amounts = {driver_id: amount for driver_id in driver_ids}
            else:
                pupillo_ids = [c.driver_id for c in choices if c.is_pupillo]
                new_amounts, _ = pc.get_regular_race_spent_amounts(
                    player=player,
                    race=race,
                    driver_ids=driver_ids,
                    pupillo_driver_id=pupillo_ids[0] if pupillo_ids else None,
                    options_by_driver_id=options_by_driver_id,
                )

            for choice in choices:
                new_amount = new_amounts[choice.driver_id]
                if new_amount != choice.spent_amount:
                    self.stdout.write(
                        f"• {race} - {player.player_name} - {choice.driver.short_name}: "
                        f"{choice.spent_amount} -> {new_amount}"
                    )
                    choice.spent_amount = new_amount
                    choice.save(update_fields=["spent_amount"])
                    changed += 1

        self.stdout.write(self.style.SUCCESS(f"• Choices updated: {changed}"))

    def _rebuild_credits(self, players):
        self.stdout.write(self.style.SUCCESS("=== Credits ==="))
        for player in players:
            new_credit = INITIAL_CREDIT - self._applied_spent(player)
            style = self.style.WARNING if new_credit < 0 else self.style.SUCCESS
            self.stdout.write(
                style(
                    f"• {player.player_name} ({player.championship}): "
                    f"{player.available_credit} -> {new_credit}"
                )
            )
            player.available_credit = new_credit
            player.save(update_fields=["available_credit"])

    def _rebuild_scores(self, season, players):
        self.stdout.write(self.style.SUCCESS("=== Scores ==="))
        old_scores = {player.id: player.total_score for player in players}
        deleted, _ = PlayerRaceResult.objects.filter(
            race__weekend__season=season
        ).delete()
        ChampionshipPlayer.objects.filter(id__in=old_scores).update(total_score=0)
        self.stdout.write(f"• PlayerRaceResult deleted: {deleted}")

        # Only races with official results can be scored
        scored_race_ids = RaceResult.objects.filter(
            race__weekend__season=season
        ).values("race_id")
        for race in Race.objects.filter(id__in=scored_race_ids):
            stats = compute_player_score_per_race(race=race)
            for err in stats["errors"]:
                self.stderr.write(f"  • {err['player']} - {err['race']}: {err['error']}")

        for player in ChampionshipPlayer.objects.filter(id__in=old_scores):
            self.stdout.write(
                f"• {player.player_name} ({player.championship}): "
                f"{old_scores[player.id]} -> {player.total_score}"
            )
