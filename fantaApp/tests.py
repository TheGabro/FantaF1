import json
from decimal import Decimal
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.base import Message
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.template.loader import render_to_string
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from . import urls as fanta_urls
from .views import dashboard, invites

# In test DEBUG è sempre False, quindi lo storage WhiteNoise pretende il manifest
# prodotto da collectstatic e qualsiasi template con {% static %} esplode. I test
# che renderizzano pagine usano lo storage semplice, senza hash nei nomi.
TEST_STORAGES = {
    **django_settings.STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

from .models import (
    Championship,
    ChampionshipManager,
    ChampionshipPlayer,
    Circuit,
    Driver,
    DriverStanding,
    EventProcessingStatus,
    League,
    PlayerQualifyingChoice,
    Qualifying,
    PlayerQualifyingMultiChoice,
    PlayerSprintQualifyingChoice,
    PlayerRaceResult,
    QualifyingResult,
    Race,
    RaceResult,
    RaceStartingGrid,
    Status,
    Team,
    Weekend,
    WeekendParticipant,
    PlayerRaceChoice,
)
from .services import event_processing as ep
from .services import player_choices as pc
from .services import bonuses
from .services import costs
from .services import credit_consolidation as su
from .services import player_scoring


class SprintRaceChoiceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="player1",
            email="player1@example.com",
            password="password123",
        )
        self.client.force_login(self.user)

        self.championship = Championship.objects.create(name="Sprint Cup", year=2026)
        self.league = League.objects.create(
            championship=self.championship, name="League 1"
        )
        ChampionshipManager.objects.create(
            user=self.user, championship=self.championship
        )
        self.player = ChampionshipPlayer.objects.create(
            user=self.user,
            championship=self.championship,
            league=self.league,
            player_name="Player One",
            available_credit=15,
        )

        self.circuit = Circuit.objects.create(
            name="Imola",
            country="Italy",
            location="Imola",
            api_id="circuit-imola",
        )
        self.weekend = Weekend.objects.create(
            circuit=self.circuit,
            event_name="Emilia Romagna GP",
            round_number=7,
            season=2026,
            weekend_type="sprint",
            sprint_qualifying_start=timezone.now() - timedelta(days=1),
            sprint_start=timezone.now() + timedelta(days=1),
            qualifying_start=timezone.now() + timedelta(days=2),
            race_start=timezone.now() + timedelta(days=3),
        )
        self.sprint_qualifying = Qualifying.objects.create(
            weekend=self.weekend, type="sprint"
        )
        self.sprint_race = Race.objects.create(weekend=self.weekend, type="sprint")

        self.team = Team.objects.create(
            name="Fast Team",
            short_name="FST",
            api_id="team-fast",
            nationality="Italian",
        )

        self.driver_1 = self._create_driver(api_id="drv-1", number=11, short_name="AAA")
        self.driver_2 = self._create_driver(api_id="drv-2", number=12, short_name="BBB")
        self.driver_3 = self._create_driver(api_id="drv-3", number=13, short_name="CCC")

        QualifyingResult.objects.create(
            qualifying=self.sprint_qualifying,
            driver=self.driver_1,
            position=1,
        )
        QualifyingResult.objects.create(
            qualifying=self.sprint_qualifying,
            driver=self.driver_2,
            position=2,
        )
        QualifyingResult.objects.create(
            qualifying=self.sprint_qualifying,
            driver=self.driver_3,
            position=20,
        )
        for driver, position in ((self.driver_1, 1), (self.driver_2, 2), (self.driver_3, 20)):
            RaceStartingGrid.objects.create(
                race=self.sprint_race, driver=driver, position=position
            )

    def _create_driver(self, *, api_id, number, short_name):
        return Driver.objects.create(
            first_name=f"Driver{number}",
            last_name="Test",
            number=number,
            short_name=short_name,
            team=self.team,
            season=2026,
            api_id=api_id,
        )

    def test_sprint_race_choice_blocks_when_credit_is_not_enough(self):
        url = reverse(
            "sprint_race_choice",
            args=[self.championship.id, self.weekend.id, self.sprint_race.id],
        )

        response = self.client.post(url, {"drivers": [self.driver_1.id]})

        self.assertRedirects(response, url)
        self.assertFalse(
            PlayerRaceChoice.objects.filter(
                player=self.player, race=self.sprint_race
            ).exists()
        )

    def test_sprint_race_choice_can_be_changed_before_event_start_without_scaling_credit(
        self,
    ):
        self.player.available_credit = 100
        self.player.save(update_fields=["available_credit"])

        pc.choose_sprint_race_drivers(
            player=self.player,
            race=self.sprint_race,
            drivers=[self.driver_3],
        )

        self.player.refresh_from_db()
        self.assertEqual(self.player.available_credit, 100)

        reserved_before_change = costs.get_player_reserved_credit(player=self.player)
        self.assertEqual(
            reserved_before_change,
            costs.get_sprint_race_driver_cost(20),
        )

        pc.choose_sprint_race_drivers(
            player=self.player,
            race=self.sprint_race,
            drivers=[self.driver_1],
        )

        selected_driver_ids = set(
            PlayerRaceChoice.objects.filter(
                player=self.player, race=self.sprint_race
            ).values_list("driver_id", flat=True)
        )
        self.assertSetEqual(selected_driver_ids, {self.driver_1.id})
        self.assertEqual(self.player.available_credit, 100)
        self.assertEqual(
            costs.get_player_reserved_credit(player=self.player),
            costs.get_sprint_race_driver_cost(1),
        )

    def test_started_sprint_race_applies_credit_only_once(self):
        self.player.available_credit = 40
        self.player.save(update_fields=["available_credit"])
        pc.choose_sprint_race_drivers(
            player=self.player,
            race=self.sprint_race,
            drivers=[self.driver_3],
        )

        self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
        self.weekend.save(update_fields=["sprint_start"])

        su.consolidate_race_credits(race=self.sprint_race)
        self.player.refresh_from_db()

        expected_credit = 40 - costs.get_sprint_race_driver_cost(20)
        self.assertEqual(self.player.available_credit, expected_credit)
        self.assertEqual(
            PlayerRaceChoice.objects.filter(
                player=self.player, race=self.sprint_race, credit_applied=True
            ).count(),
            1,
        )

        su.consolidate_race_credits(race=self.sprint_race)
        self.player.refresh_from_db()
        self.assertEqual(self.player.available_credit, expected_credit)


class GrandPrixChoiceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="player2",
            email="player2@example.com",
            password="password123",
        )
        self.client.force_login(self.user)

        self.championship = Championship.objects.create(
            name="Grand Prix Cup", year=2026
        )
        self.league = League.objects.create(
            championship=self.championship, name="League GP"
        )
        ChampionshipManager.objects.create(
            user=self.user, championship=self.championship
        )
        self.player = ChampionshipPlayer.objects.create(
            user=self.user,
            championship=self.championship,
            league=self.league,
            player_name="Player GP",
            available_credit=1300,
        )

        self.circuit = Circuit.objects.create(
            name="Monza",
            country="Italy",
            location="Monza",
            api_id="circuit-monza",
        )

        self.team = Team.objects.create(
            name="Grand Team",
            short_name="GRT",
            api_id="team-grand",
            nationality="Italian",
        )

        self.driver_1 = self._create_driver(
            api_id="gp-drv-1", number=21, short_name="DDD"
        )
        self.driver_2 = self._create_driver(
            api_id="gp-drv-2", number=22, short_name="EEE"
        )
        self.driver_3 = self._create_driver(
            api_id="gp-drv-3", number=23, short_name="FFF"
        )

        self.weekend_bundles = [
            self._create_regular_weekend_bundle(round_number)
            for round_number in range(1, 6)
        ]

    def _create_driver(self, *, api_id, number, short_name):
        return Driver.objects.create(
            first_name=f"Driver{number}",
            last_name="Test",
            number=number,
            short_name=short_name,
            team=self.team,
            season=2026,
            api_id=api_id,
        )

    def _create_regular_weekend_bundle(self, round_number):
        weekend = Weekend.objects.create(
            circuit=self.circuit,
            event_name=f"Weekend {round_number}",
            round_number=round_number,
            season=2026,
            weekend_type="regular",
            qualifying_start=timezone.now() - timedelta(days=2),
            race_start=timezone.now() + timedelta(days=round_number),
        )
        qualifying = Qualifying.objects.create(weekend=weekend, type="regular")
        race = Race.objects.create(weekend=weekend, type="regular")

        QualifyingResult.objects.create(
            qualifying=qualifying, driver=self.driver_1, position=1
        )
        QualifyingResult.objects.create(
            qualifying=qualifying, driver=self.driver_2, position=2
        )
        QualifyingResult.objects.create(
            qualifying=qualifying, driver=self.driver_3, position=10
        )
        for driver, position in ((self.driver_1, 1), (self.driver_2, 2), (self.driver_3, 10)):
            RaceStartingGrid.objects.create(race=race, driver=driver, position=position)

        return {"weekend": weekend, "qualifying": qualifying, "race": race}

    def test_race_driver_options_follow_starting_grid_not_qualifying(self):
        race = self.weekend_bundles[0]["race"]
        # Grid penalty: P10 in qualifying, P13 on the grid
        RaceStartingGrid.objects.filter(race=race, driver=self.driver_3).update(
            position=13
        )
        # Driver without a qualifying result still starts the race
        no_quali_driver = self._create_driver(
            api_id="drv-4", number=14, short_name="DDD"
        )
        RaceStartingGrid.objects.create(race=race, driver=no_quali_driver, position=20)

        options = {
            option["driver"].id: option
            for option in costs.get_race_driver_options(race=race)
        }

        self.assertEqual(options[self.driver_3.id]["grid_position"], 13)
        self.assertEqual(
            options[self.driver_3.id]["cost"],
            costs.get_regular_race_cost(
                grid_position=13, driver=self.driver_3, weekend=race.weekend
            ),
        )
        self.assertEqual(options[no_quali_driver.id]["grid_position"], 20)

    def _consolidated_choice_on_grid_penalty(self):
        """Pick drivers 1-2 at P1-P2, consolidate, then move driver 1 to P13."""
        race = self.weekend_bundles[0]["race"]
        pc.choose_regular_race_drivers(
            player=self.player,
            race=race,
            drivers=[self.driver_1, self.driver_2],
            pupillo_driver=self.driver_1,
        )
        spent = sum(
            PlayerRaceChoice.objects.filter(race=race).values_list(
                "spent_amount", flat=True
            )
        )
        PlayerRaceChoice.objects.filter(race=race).update(credit_applied=True)
        self.player.available_credit = 2000 - spent
        self.player.save(update_fields=["available_credit"])
        RaceStartingGrid.objects.filter(race=race, driver=self.driver_1).update(
            position=13
        )
        return race

    def test_recompute_race_costs_uses_grid_and_rebuilds_credit(self):
        race = self._consolidated_choice_on_grid_penalty()
        old_spent = PlayerRaceChoice.objects.get(
            race=race, driver=self.driver_1
        ).spent_amount

        call_command("recompute_race_costs", season=2026, stdout=StringIO())

        choice = PlayerRaceChoice.objects.get(race=race, driver=self.driver_1)
        self.assertLess(choice.spent_amount, old_spent)
        applied = sum(
            PlayerRaceChoice.objects.filter(player=self.player).values_list(
                "spent_amount", flat=True
            )
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.available_credit, 2000 - applied)

    def test_recompute_race_costs_aborts_on_hand_edited_credit(self):
        race = self._consolidated_choice_on_grid_penalty()
        self.player.available_credit += 50
        self.player.save(update_fields=["available_credit"])
        old_spent = PlayerRaceChoice.objects.get(
            race=race, driver=self.driver_1
        ).spent_amount

        with self.assertRaises(CommandError):
            call_command("recompute_race_costs", season=2026, stdout=StringIO())

        self.assertEqual(
            PlayerRaceChoice.objects.get(race=race, driver=self.driver_1).spent_amount,
            old_spent,
        )

    def test_regular_race_choice_requires_pupillo_among_selected_drivers(self):
        race = self.weekend_bundles[0]["race"]

        with self.assertRaisesMessage(
            ValidationError, "Il pupillo deve essere uno dei 2 piloti selezionati."
        ):
            pc.choose_regular_race_drivers(
                player=self.player,
                race=race,
                drivers=[self.driver_1, self.driver_2],
                pupillo_driver=self.driver_3,
            )

    def test_regular_race_pupillo_discount_grows_on_consecutive_weekends_and_caps(self):
        for bundle in self.weekend_bundles[:4]:
            pc.choose_regular_race_drivers(
                player=self.player,
                race=bundle["race"],
                drivers=[self.driver_1, self.driver_2],
                pupillo_driver=self.driver_1,
            )

        fifth_race = self.weekend_bundles[4]["race"]
        result = pc.choose_regular_race_drivers(
            player=self.player,
            race=fifth_race,
            drivers=[self.driver_1, self.driver_2],
            pupillo_driver=self.driver_1,
        )

        self.assertEqual(
            costs.get_regular_race_pupillo_discount(
                player=self.player, race=fifth_race, driver=self.driver_1
            ),
            20,
        )
        self.assertEqual(result["pupillo_discount"], 20)
        self.assertEqual(
            result["total_spent_amount"],
            costs.get_regular_race_driver_cost_breakdown(
                grid_position=1,
                driver=self.driver_1,
                weekend=fifth_race.weekend,
            )["total_cost"]
            - 20
            + costs.get_regular_race_driver_cost_breakdown(
                grid_position=2,
                driver=self.driver_2,
                weekend=fifth_race.weekend,
            )["total_cost"],
        )

        pupillo_choice = PlayerRaceChoice.objects.get(
            player=self.player, race=fifth_race, driver=self.driver_1
        )
        non_pupillo_choice = PlayerRaceChoice.objects.get(
            player=self.player, race=fifth_race, driver=self.driver_2
        )
        self.assertTrue(pupillo_choice.is_pupillo)
        self.assertEqual(
            pupillo_choice.spent_amount,
            costs.get_regular_race_driver_cost_breakdown(
                grid_position=1,
                driver=self.driver_1,
                weekend=fifth_race.weekend,
            )["total_cost"]
            - 20,
        )
        self.assertFalse(non_pupillo_choice.is_pupillo)
        self.assertEqual(
            non_pupillo_choice.spent_amount,
            costs.get_regular_race_driver_cost_breakdown(
                grid_position=2,
                driver=self.driver_2,
                weekend=fifth_race.weekend,
            )["total_cost"],
        )

    def test_started_regular_race_applies_credit_only_once(self):
        first_race = self.weekend_bundles[0]["race"]
        result = pc.choose_regular_race_drivers(
            player=self.player,
            race=first_race,
            drivers=[self.driver_1, self.driver_2],
            pupillo_driver=self.driver_1,
        )

        first_race.weekend.race_start = timezone.now() - timedelta(minutes=5)
        first_race.weekend.save(update_fields=["race_start"])

        su.consolidate_race_credits(race=first_race)
        self.player.refresh_from_db()

        expected_credit = 1300 - result["total_spent_amount"]
        self.assertEqual(self.player.available_credit, expected_credit)
        self.assertEqual(
            PlayerRaceChoice.objects.filter(
                player=self.player, race=first_race, credit_applied=True
            ).count(),
            2,
        )

        su.consolidate_race_credits(race=first_race)
        self.player.refresh_from_db()
        self.assertEqual(self.player.available_credit, expected_credit)


class SprintWeekendRegularQualifyingBonusTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="player-bonus",
            email="bonus@example.com",
            password="password123",
        )

        self.championship = Championship.objects.create(name="Bonus Cup", year=2026)
        self.league = League.objects.create(
            championship=self.championship, name="Bonus League"
        )
        ChampionshipManager.objects.create(
            user=self.user, championship=self.championship
        )
        self.player = ChampionshipPlayer.objects.create(
            user=self.user,
            championship=self.championship,
            league=self.league,
            player_name="Bonus Player",
            available_credit=500,
        )

        self.circuit = Circuit.objects.create(
            name="Spa",
            country="Belgium",
            location="Spa",
            api_id="circuit-spa",
        )
        self.team = Team.objects.create(
            name="Bonus Team",
            short_name="BON",
            api_id="team-bonus",
            nationality="Belgian",
        )

        self.drivers = [
            Driver.objects.create(
                first_name=f"Driver{index}",
                last_name="Bonus",
                number=30 + index,
                short_name=f"B{index:02d}"[-3:],
                team=self.team,
                season=2026,
                api_id=f"bonus-drv-{index}",
            )
            for index in range(1, 16)
        ]

        self.weekend = Weekend.objects.create(
            circuit=self.circuit,
            event_name="Sprint Weekend Bonus",
            round_number=4,
            season=2026,
            weekend_type="sprint",
            sprint_qualifying_start=timezone.now() - timedelta(days=3),
            qualifying_start=timezone.now() - timedelta(days=2),
            race_start=timezone.now() + timedelta(days=1),
        )
        self.qualifying = Qualifying.objects.create(
            weekend=self.weekend, type="regular"
        )
        self.race = Race.objects.create(weekend=self.weekend, type="regular")

        for index, driver in enumerate(self.drivers, start=1):
            QualifyingResult.objects.create(
                qualifying=self.qualifying,
                driver=driver,
                q1_time=timedelta(minutes=1, seconds=index),
                q2_time=timedelta(minutes=1, seconds=10 + index)
                if index <= 15
                else None,
                q3_time=timedelta(minutes=1, seconds=20 + index)
                if index <= 8
                else None,
                position=index,
            )
            RaceStartingGrid.objects.create(
                race=self.race, driver=driver, position=index
            )

        for driver in self.drivers[9:15]:
            PlayerQualifyingMultiChoice.objects.create(
                player=self.player,
                qualifying=self.qualifying,
                selection_slot="q1_pass",
                driver=driver,
            )

        for driver in self.drivers[3:8]:
            PlayerQualifyingMultiChoice.objects.create(
                player=self.player,
                qualifying=self.qualifying,
                selection_slot="q2_pass",
                driver=driver,
            )

    def test_multichoice_level_on_grid_uses_position_thresholds(self):
        grid = {
            driver_id: SimpleNamespace(driver_id=driver_id, position=position)
            for driver_id, position in enumerate(range(1, 23), start=1)
        }
        choices_by_slot = {
            "q1_pass": [11, 12, 13, 14, 15, 16],  # grid P11-P16: pass Q1
            "q2_pass": [4, 5, 6, 7, 8],  # grid P4-P8: pass Q2
            "q3_top3": [1, 2, 3],
        }
        self.assertEqual(
            bonuses.resolve_multichoice_level(
                choices_by_slot=choices_by_slot, results_by_driver_id=grid, on_grid=True
            ),
            "q3_top3",
        )

        # One Q1 pick starts P17 (e.g. grid penalty): no level reached
        choices_by_slot["q1_pass"][-1] = 17
        self.assertEqual(
            bonuses.resolve_multichoice_level(
                choices_by_slot=choices_by_slot, results_by_driver_id=grid, on_grid=True
            ),
            "none",
        )

    def test_regular_race_bonus_reaches_q2_tier_when_top3_is_not_matched(self):
        for driver in (self.drivers[0], self.drivers[1], self.drivers[8]):
            PlayerQualifyingMultiChoice.objects.create(
                player=self.player,
                qualifying=self.qualifying,
                selection_slot="q3_top3",
                driver=driver,
            )

        bonus = bonuses.get_race_bonus(player=self.player, race=self.race)

        self.assertEqual(bonus["level"], "q2_pass")
        self.assertEqual(bonus["credit_change"], -20)  # negativo = sconto
        self.assertEqual(bonus["points_multiplier"], Decimal("1.2"))

    def test_regular_race_bonus_discount_is_applied_to_total_spent_amount(self):
        for driver in self.drivers[:3]:
            PlayerQualifyingMultiChoice.objects.create(
                player=self.player,
                qualifying=self.qualifying,
                selection_slot="q3_top3",
                driver=driver,
            )

        result = pc.choose_regular_race_drivers(
            player=self.player,
            race=self.race,
            drivers=[self.drivers[0], self.drivers[1]],
            pupillo_driver=self.drivers[0],
        )

        self.assertEqual(result["qualifying_bonus_level"], "q3_top3")
        self.assertEqual(
            result["qualifying_bonus_credit_change"], -50
        )  # negativo = sconto
        self.assertEqual(result["qualifying_bonus_points_multiplier"], Decimal("2"))
        self.assertEqual(result["total_spent_amount"], 200)
        self.assertEqual(
            sum(
                PlayerRaceChoice.objects.filter(
                    player=self.player, race=self.race
                ).values_list("spent_amount", flat=True)
            ),
            200,
        )


class CreditConsolidationTests(TestCase):
    def setUp(self):
        self.circuit = Circuit.objects.create(
            name="Silverstone",
            country="UK",
            location="Silverstone",
            api_id="circuit-silverstone",
        )
        self.team = Team.objects.create(
            name="Consolidation Team",
            short_name="CNS",
            api_id="team-consolidation",
            nationality="British",
        )
        self.weekend = Weekend.objects.create(
            circuit=self.circuit,
            event_name="Consolidation GP",
            round_number=8,
            season=2026,
            weekend_type="sprint",
            sprint_qualifying_start=timezone.now() - timedelta(days=2),
            sprint_start=timezone.now() + timedelta(days=1),
            qualifying_start=timezone.now() + timedelta(days=2),
            race_start=timezone.now() + timedelta(days=3),
        )
        self.sprint_race = Race.objects.create(weekend=self.weekend, type="sprint")
        self.other_race = Race.objects.create(weekend=self.weekend, type="regular")

        self.driver = Driver.objects.create(
            first_name="Driver",
            last_name="Consolidation",
            number=44,
            short_name="CON",
            team=self.team,
            season=2026,
            api_id="drv-consolidation",
        )

        self.user_a = get_user_model().objects.create_user(
            username="consolidation-a",
            email="consolidation-a@example.com",
            password="password123",
        )
        self.championship_a = Championship.objects.create(
            name="Consolidation Cup A", year=2026
        )
        self.league_a = League.objects.create(
            championship=self.championship_a, name="League A"
        )
        ChampionshipManager.objects.create(
            user=self.user_a, championship=self.championship_a
        )
        self.player_a = ChampionshipPlayer.objects.create(
            user=self.user_a,
            championship=self.championship_a,
            league=self.league_a,
            player_name="Player A",
            available_credit=100,
        )

        self.user_b = get_user_model().objects.create_user(
            username="consolidation-b",
            email="consolidation-b@example.com",
            password="password123",
        )
        self.championship_b = Championship.objects.create(
            name="Consolidation Cup B", year=2026
        )
        self.league_b = League.objects.create(
            championship=self.championship_b, name="League B"
        )
        ChampionshipManager.objects.create(
            user=self.user_b, championship=self.championship_b
        )
        self.player_b = ChampionshipPlayer.objects.create(
            user=self.user_b,
            championship=self.championship_b,
            league=self.league_b,
            player_name="Player B",
            available_credit=100,
        )

    def _create_choice(self, *, player, race, spent_amount):
        return PlayerRaceChoice.objects.create(
            player=player,
            race=race,
            driver=self.driver,
            spent_amount=spent_amount,
        )

    def test_returns_zero_and_does_not_touch_credit_before_race_start(self):
        choice = self._create_choice(
            player=self.player_a, race=self.sprint_race, spent_amount=30
        )

        updated_count = su.consolidate_race_credits(race=self.sprint_race)

        self.assertEqual(updated_count, 0)
        self.player_a.refresh_from_db()
        self.assertEqual(self.player_a.available_credit, 100)
        choice.refresh_from_db()
        self.assertFalse(choice.credit_applied)

    def test_consolidates_credit_once_race_has_started(self):
        self._create_choice(
            player=self.player_a, race=self.sprint_race, spent_amount=30
        )
        self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
        self.weekend.save(update_fields=["sprint_start"])

        updated_count = su.consolidate_race_credits(race=self.sprint_race)

        self.assertEqual(updated_count, 1)
        self.player_a.refresh_from_db()
        self.assertEqual(self.player_a.available_credit, 70)
        self.assertTrue(
            PlayerRaceChoice.objects.get(
                player=self.player_a, race=self.sprint_race
            ).credit_applied
        )

    def test_consolidation_is_idempotent(self):
        self._create_choice(
            player=self.player_a, race=self.sprint_race, spent_amount=30
        )
        self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
        self.weekend.save(update_fields=["sprint_start"])

        first_run = su.consolidate_race_credits(race=self.sprint_race)
        second_run = su.consolidate_race_credits(race=self.sprint_race)

        self.assertEqual(first_run, 1)
        self.assertEqual(second_run, 0)
        self.player_a.refresh_from_db()
        self.assertEqual(self.player_a.available_credit, 70)

    def test_consolidates_multiple_players_across_different_championships(self):
        self._create_choice(
            player=self.player_a, race=self.sprint_race, spent_amount=30
        )
        self._create_choice(
            player=self.player_b, race=self.sprint_race, spent_amount=45
        )
        self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
        self.weekend.save(update_fields=["sprint_start"])

        updated_count = su.consolidate_race_credits(race=self.sprint_race)

        self.assertEqual(updated_count, 2)
        self.player_a.refresh_from_db()
        self.player_b.refresh_from_db()
        self.assertEqual(self.player_a.available_credit, 70)
        self.assertEqual(self.player_b.available_credit, 55)

    def test_consolidation_ignores_choices_from_other_races(self):
        self._create_choice(
            player=self.player_a, race=self.sprint_race, spent_amount=30
        )
        other_choice = self._create_choice(
            player=self.player_a, race=self.other_race, spent_amount=999
        )
        self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
        self.weekend.save(update_fields=["sprint_start"])
        # self.other_race e' di tipo "regular": usa weekend.race_start, ancora nel futuro

        updated_count = su.consolidate_race_credits(race=self.sprint_race)

        self.assertEqual(updated_count, 1)
        other_choice.refresh_from_db()
        self.assertFalse(other_choice.credit_applied)

    def test_consolidation_returns_zero_when_no_pending_choices_exist(self):
        self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
        self.weekend.save(update_fields=["sprint_start"])

        updated_count = su.consolidate_race_credits(race=self.sprint_race)

        self.assertEqual(updated_count, 0)


class PlayerScoringTests(TestCase):
    def setUp(self):
        self.circuit = Circuit.objects.create(
            name="Suzuka",
            country="Japan",
            location="Suzuka",
            api_id="circuit-suzuka",
        )
        self.team = Team.objects.create(
            name="Scoring Team",
            short_name="SCR",
            api_id="team-scoring",
            nationality="Japanese",
        )

        self.weekend = Weekend.objects.create(
            circuit=self.circuit,
            event_name="Scoring GP",
            round_number=9,
            season=2026,
            weekend_type="regular",
            qualifying_start=timezone.now() - timedelta(days=2),
            race_start=timezone.now() - timedelta(days=1),
        )
        self.qualifying = Qualifying.objects.create(
            weekend=self.weekend, type="regular"
        )
        self.race = Race.objects.create(weekend=self.weekend, type="regular")

        self.second_weekend = Weekend.objects.create(
            circuit=self.circuit,
            event_name="Scoring GP 2",
            round_number=10,
            season=2026,
            weekend_type="regular",
            qualifying_start=timezone.now() - timedelta(days=2),
            race_start=timezone.now() - timedelta(days=1),
        )
        self.second_qualifying = Qualifying.objects.create(
            weekend=self.second_weekend, type="regular"
        )
        self.second_race = Race.objects.create(
            weekend=self.second_weekend, type="regular"
        )

        self.driver_1 = self._create_driver(
            api_id="score-drv-1", number=51, short_name="SC1"
        )
        self.driver_2 = self._create_driver(
            api_id="score-drv-2", number=52, short_name="SC2"
        )

        self.user_a = get_user_model().objects.create_user(
            username="scoring-a",
            email="scoring-a@example.com",
            password="password123",
        )
        self.championship_a = Championship.objects.create(
            name="Scoring Cup A", year=2026
        )
        self.league_a = League.objects.create(
            championship=self.championship_a, name="League A"
        )
        ChampionshipManager.objects.create(
            user=self.user_a, championship=self.championship_a
        )
        self.player_a = ChampionshipPlayer.objects.create(
            user=self.user_a,
            championship=self.championship_a,
            league=self.league_a,
            player_name="Scoring Player A",
            available_credit=1000,
        )

        self.user_b = get_user_model().objects.create_user(
            username="scoring-b",
            email="scoring-b@example.com",
            password="password123",
        )
        self.championship_b = Championship.objects.create(
            name="Scoring Cup B", year=2026
        )
        self.league_b = League.objects.create(
            championship=self.championship_b, name="League B"
        )
        ChampionshipManager.objects.create(
            user=self.user_b, championship=self.championship_b
        )
        self.player_b = ChampionshipPlayer.objects.create(
            user=self.user_b,
            championship=self.championship_b,
            league=self.league_b,
            player_name="Scoring Player B",
            available_credit=1000,
        )

    def _create_driver(self, *, api_id, number, short_name):
        return Driver.objects.create(
            first_name=f"Driver{number}",
            last_name="Scoring",
            number=number,
            short_name=short_name,
            team=self.team,
            season=2026,
            api_id=api_id,
        )

    def _create_race_result(
        self, *, race, driver, position, points, starting_grid=None
    ):
        return RaceResult.objects.create(
            race=race,
            driver=driver,
            position=position,
            status="Finished",
            starting_grid=starting_grid if starting_grid is not None else position,
            points=points,
        )

    def test_compute_race_points_raises_when_player_has_no_choices(self):
        with self.assertRaises(ValueError):
            player_scoring.compute_race_points(player=self.player_a, race=self.race)

    def test_compute_race_points_sums_official_points_of_chosen_drivers(self):
        self._create_race_result(
            race=self.race, driver=self.driver_1, position=1, points=25
        )
        self._create_race_result(
            race=self.race, driver=self.driver_2, position=3, points=15
        )
        PlayerRaceChoice.objects.create(
            player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100
        )
        PlayerRaceChoice.objects.create(
            player=self.player_a, race=self.race, driver=self.driver_2, spent_amount=60
        )

        result = player_scoring.compute_race_points(
            player=self.player_a, race=self.race
        )

        self.assertEqual(result.fia_points, 40)
        self.assertEqual(result.credit_spent, 160)
        self.assertEqual(result.point_multiplier, 1.0)
        self.assertEqual(result.total_points, 40.0)

    def test_compute_race_points_ignores_driver_without_race_result(self):
        self._create_race_result(
            race=self.race, driver=self.driver_1, position=1, points=25
        )
        # driver_2 e' stato scelto ma non ha ancora un RaceResult importato (es. DNS non ancora inserito)
        PlayerRaceChoice.objects.create(
            player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100
        )
        PlayerRaceChoice.objects.create(
            player=self.player_a, race=self.race, driver=self.driver_2, spent_amount=60
        )

        result = player_scoring.compute_race_points(
            player=self.player_a, race=self.race
        )

        self.assertEqual(result.fia_points, 25)

    def test_compute_race_points_applies_qualifying_multiplier(self):
        self._create_race_result(
            race=self.race, driver=self.driver_1, position=1, points=25
        )
        PlayerRaceChoice.objects.create(
            player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100
        )
        QualifyingResult.objects.create(
            qualifying=self.qualifying, driver=self.driver_1, position=1
        )
        # Grid penalty: P1 in qualifying, P3 on the grid
        RaceStartingGrid.objects.create(race=self.race, driver=self.driver_1, position=3)
        PlayerQualifyingChoice.objects.create(
            player=self.player_a, qualifying=self.qualifying, driver=self.driver_1
        )

        result = player_scoring.compute_race_points(
            player=self.player_a, race=self.race
        )

        # The multiplier follows the grid: P3 -> x1.5 (rules.py), not P1 -> x2
        self.assertEqual(result.point_multiplier, 1.5)
        self.assertEqual(result.total_points, 37.5)

    def test_compute_race_points_upserts_existing_result(self):
        race_result = self._create_race_result(
            race=self.race, driver=self.driver_1, position=1, points=25
        )
        PlayerRaceChoice.objects.create(
            player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100
        )

        player_scoring.compute_race_points(player=self.player_a, race=self.race)
        self.assertEqual(
            PlayerRaceResult.objects.filter(
                player=self.player_a, race=self.race
            ).count(),
            1,
        )

        race_result.points = 18
        race_result.save(update_fields=["points"])
        player_scoring.compute_race_points(player=self.player_a, race=self.race)

        self.assertEqual(
            PlayerRaceResult.objects.filter(
                player=self.player_a, race=self.race
            ).count(),
            1,
        )
        updated_result = PlayerRaceResult.objects.get(
            player=self.player_a, race=self.race
        )
        self.assertEqual(updated_result.fia_points, 18)

    def test_compute_player_score_per_race_only_updates_players_with_choices(self):
        self._create_race_result(
            race=self.race, driver=self.driver_1, position=1, points=25
        )
        PlayerRaceChoice.objects.create(
            player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100
        )
        # player_b non ha fatto scelte per questa gara

        stats = player_scoring.compute_player_score_per_race(race=self.race)

        self.assertEqual(stats["players_updated"], 1)
        self.assertEqual(stats["errors"], [])
        self.player_a.refresh_from_db()
        self.player_b.refresh_from_db()
        self.assertEqual(self.player_a.total_score, 25)
        self.assertEqual(self.player_b.total_score, 0)
        self.assertFalse(
            PlayerRaceResult.objects.filter(
                player=self.player_b, race=self.race
            ).exists()
        )

    def test_compute_player_score_per_race_updates_players_across_different_championships(
        self,
    ):
        self._create_race_result(
            race=self.race, driver=self.driver_1, position=1, points=25
        )
        self._create_race_result(
            race=self.race, driver=self.driver_2, position=2, points=18
        )
        PlayerRaceChoice.objects.create(
            player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100
        )
        PlayerRaceChoice.objects.create(
            player=self.player_b, race=self.race, driver=self.driver_2, spent_amount=90
        )

        stats = player_scoring.compute_player_score_per_race(race=self.race)

        self.assertEqual(stats["players_updated"], 2)
        self.player_a.refresh_from_db()
        self.player_b.refresh_from_db()
        self.assertEqual(self.player_a.total_score, 25)
        self.assertEqual(self.player_b.total_score, 18)

    def test_compute_player_score_per_race_aggregates_total_score_across_multiple_races(
        self,
    ):
        self._create_race_result(
            race=self.race, driver=self.driver_1, position=1, points=25
        )
        self._create_race_result(
            race=self.second_race, driver=self.driver_1, position=2, points=18
        )
        PlayerRaceChoice.objects.create(
            player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100
        )
        PlayerRaceChoice.objects.create(
            player=self.player_a,
            race=self.second_race,
            driver=self.driver_1,
            spent_amount=100,
        )

        player_scoring.compute_player_score_per_race(race=self.race)
        player_scoring.compute_player_score_per_race(race=self.second_race)

        self.player_a.refresh_from_db()
        self.assertEqual(self.player_a.total_score, 43)
        self.assertEqual(
            PlayerRaceResult.objects.filter(player=self.player_a).count(), 2
        )


@override_settings(STORAGES=TEST_STORAGES)
class LoginNextRedirectTests(TestCase):
    """F0: il ritorno dal login, su cui poggia ogni link d'invito."""

    def setUp(self):
        self.client = Client()
        get_user_model().objects.create_user(
            username="next-user",
            email="next@example.com",
            password="password123",
        )

    def test_login_returns_to_requested_internal_page(self):
        target = reverse("user_dashboard")
        response = self.client.post(
            reverse("login"),
            {"identifier": "next-user", "password": "password123", "next": target},
        )

        self.assertRedirects(response, target)

    def test_login_ignores_external_next(self):
        response = self.client.post(
            reverse("login"),
            {
                "identifier": "next-user",
                "password": "password123",
                "next": "https://evil.example.com/",
            },
        )

        self.assertRedirects(response, reverse("user_dashboard"))

    def test_register_logs_in_and_returns_to_next(self):
        # #94: dopo l'iscrizione si entra subito e si torna a next (es. un invito).
        target = reverse("create_championship")
        response = self.client.post(
            reverse("register"),
            {
                "username": "brand-new",
                "email": "brand-new@example.com",
                "password": "Pista-Monza-1922",
                "password2": "Pista-Monza-1922",
                "next": target,
            },
        )

        self.assertRedirects(response, target)
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            get_user_model().objects.get(username="brand-new").pk,
        )


@override_settings(STORAGES=TEST_STORAGES)
class GameLandingTests(TestCase):
    """/game/ presenta il gioco a tutti; i pulsanti dipendono dal login (#90)."""

    def test_anonymous_visitor_sees_sign_up_and_login_cards(self):
        response = self.client.get(reverse("game"))

        self.assertContains(response, "Inizia a giocare")
        self.assertContains(response, "Bentornato in griglia")
        self.assertNotContains(response, "Bentornato, ")

    def test_logged_in_user_sees_link_to_championships_instead_of_cards(self):
        user = get_user_model().objects.create_user(
            username="pilota", email="pilota@example.com", password="password123"
        )
        self.client.force_login(user)

        response = self.client.get(reverse("game"))

        self.assertContains(response, "Bentornato, pilota")
        self.assertContains(response, f'href="{reverse("user_dashboard")}"')
        self.assertNotContains(response, "Inizia a giocare")
        self.assertNotContains(response, "Bentornato in griglia")


class RaceResultsLoginRequiredTests(TestCase):
    """#51: le pagine dei risultati gara chiedono il login come le altre del weekend."""

    def test_anonymous_users_are_sent_to_login(self):
        for url_name in ("sprint_race_results", "regular_race_results"):
            with self.subTest(url_name=url_name):
                # Il login scatta prima di ogni accesso al database: bastano id qualsiasi.
                url = reverse(url_name, args=[1, 1, 1])
                response = self.client.get(url)

                self.assertRedirects(
                    response,
                    f"{reverse('login')}?next={url}",
                    fetch_redirect_response=False,
                )


@override_settings(STORAGES=TEST_STORAGES)
class CreateChampionshipTests(TestCase):
    """F1: chi crea il campionato entra anche come giocatore."""

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="organizzatore",
            email="organizzatore@example.com",
            password="password123",
        )
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        payload = {
            "name": "Coppa Amici",
            "year": 2026,
            "leagues-TOTAL_FORMS": "2",
            "leagues-INITIAL_FORMS": "0",
            "leagues-MIN_NUM_FORMS": "0",
            "leagues-MAX_NUM_FORMS": "1000",
            "leagues-0-name": "Serie A",
            "leagues-1-name": "Serie B",
            "join_as_player": "on",
            "player_name": "Dave",
            "player_league_index": "1",
        }
        payload.update(overrides)
        return payload

    def test_form_page_offers_the_player_fields(self):
        response = self.client.get(reverse("create_championship"))

        self.assertContains(response, "Partecipo anch")
        self.assertContains(response, "id_player_league_index")
        self.assertContains(response, 'value="organizzatore"')

    def test_creator_becomes_player_in_the_chosen_league(self):
        self.client.post(reverse("create_championship"), self._payload())

        championship = Championship.objects.get(name="Coppa Amici")
        player = ChampionshipPlayer.objects.get(
            user=self.user, championship=championship
        )
        self.assertEqual(player.player_name, "Dave")
        self.assertEqual(player.league.name, "Serie B")
        self.assertEqual(player.available_credit, 2000)
        self.assertTrue(
            ChampionshipManager.objects.filter(
                user=self.user, championship=championship
            ).exists()
        )

    def test_player_name_defaults_to_username(self):
        self.client.post(reverse("create_championship"), self._payload(player_name=""))

        player = ChampionshipPlayer.objects.get(user=self.user)
        self.assertEqual(player.player_name, "organizzatore")

    def test_out_of_range_league_index_falls_back_to_the_first_league(self):
        self.client.post(
            reverse("create_championship"), self._payload(player_league_index="99")
        )

        player = ChampionshipPlayer.objects.get(user=self.user)
        self.assertEqual(player.league.name, "Serie A")

    def test_manager_can_stay_out_of_the_game(self):
        payload = self._payload()
        del payload["join_as_player"]
        self.client.post(reverse("create_championship"), payload)

        championship = Championship.objects.get(name="Coppa Amici")
        self.assertTrue(
            ChampionshipManager.objects.filter(
                user=self.user, championship=championship
            ).exists()
        )
        self.assertFalse(
            ChampionshipPlayer.objects.filter(
                user=self.user, championship=championship
            ).exists()
        )

    def test_failed_creation_leaves_nothing_behind(self):
        Championship.objects.create(name="Coppa Amici", year=2026)

        self.client.post(reverse("create_championship"), self._payload())

        self.assertEqual(Championship.objects.filter(name="Coppa Amici").count(), 1)
        self.assertFalse(ChampionshipPlayer.objects.filter(user=self.user).exists())

    # #157: il form si apre in un pop-up di I miei campionati.

    def test_dashboard_buttons_open_the_create_dialog(self):
        response = self.client.get(reverse("user_dashboard"))

        self.assertContains(response, 'id="create-championship-dialog"')
        self.assertContains(response, 'name="from_dialog"')
        # Senza JavaScript restano link alla pagina del form.
        self.assertContains(
            response,
            f'href="{reverse("create_championship")}" class="btn-primary mt-4"'
            " data-open-create-dialog",
        )
        self.assertFalse(response.context["open_create_dialog"])

    def test_dialog_creation_lands_on_the_new_championship(self):
        response = self.client.post(
            reverse("create_championship"), self._payload(from_dialog="1")
        )

        championship = Championship.objects.get(name="Coppa Amici")
        self.assertRedirects(
            response,
            reverse("championship_info", args=[championship.id]),
            fetch_redirect_response=False,
        )

    def test_dialog_errors_reopen_the_dialog_on_the_dashboard(self):
        Championship.objects.create(name="Coppa Amici", year=2026)

        response = self.client.post(
            reverse("create_championship"), self._payload(from_dialog="1")
        )

        self.assertTemplateUsed(response, "fantaApp/user_dashboard.html")
        self.assertTrue(response.context["open_create_dialog"])
        self.assertContains(
            response, 'aria-labelledby="create-championship-title" open>'
        )
        # Un solo messaggio, il nostro: niente doppione del vincolo del modello.
        self.assertEqual(
            response.context["create_form"].non_field_errors(),
            ["Questo nome per il campionato è già in uso quest'anno"],
        )

    def test_page_errors_stay_on_the_page(self):
        Championship.objects.create(name="Coppa Amici", year=2026)

        response = self.client.post(reverse("create_championship"), self._payload())

        self.assertTemplateUsed(response, "fantaApp/create_championship.html")
        self.assertNotContains(response, 'name="from_dialog"')

    def test_create_page_has_no_inline_script(self):
        """#67: il JavaScript del form sta in un file statico."""
        response = self.client.get(reverse("create_championship"))

        self.assertContains(response, "fantaApp/js/create-championship.js")
        self.assertNotContains(response, "addEventListener")


@override_settings(STORAGES=TEST_STORAGES)
class InviteAndJoinTests(TestCase):
    """F2, F3 e F4: iscrizione, link d'invito firmato, codice incollato a mano."""

    def setUp(self):
        self.client = Client()
        self.organizer = get_user_model().objects.create_user(
            username="capo",
            email="capo@example.com",
            password="password123",
        )
        self.guest = get_user_model().objects.create_user(
            username="ospite",
            email="ospite@example.com",
            password="password123",
        )

        self.championship = Championship.objects.create(
            name="Campionato Invitato", year=2026
        )
        self.league_a = League.objects.create(
            championship=self.championship, name="Serie A"
        )
        self.league_b = League.objects.create(
            championship=self.championship, name="Serie B"
        )
        ChampionshipManager.objects.create(
            user=self.organizer, championship=self.championship
        )

        self.other_championship = Championship.objects.create(
            name="Altro Campionato", year=2026
        )
        self.other_league = League.objects.create(
            championship=self.other_championship, name="Lega Estranea"
        )

        self.join_url = reverse("join_championship", args=[self.championship.id])

    # --- F2 ---------------------------------------------------------------

    def test_join_page_lists_only_the_leagues_of_this_championship(self):
        self.client.force_login(self.guest)

        response = self.client.get(self.join_url)

        self.assertContains(response, "Serie A")
        self.assertContains(response, "Serie B")
        self.assertNotContains(response, "Lega Estranea")

    def test_join_creates_the_player_in_the_selected_league(self):
        self.client.force_login(self.guest)

        response = self.client.post(
            self.join_url, {"player_name": "Ospite", "league": self.league_b.id}
        )

        self.assertRedirects(
            response, reverse("championship_dashboard", args=[self.championship.id])
        )
        player = ChampionshipPlayer.objects.get(
            user=self.guest, championship=self.championship
        )
        self.assertEqual(player.league, self.league_b)

    def test_join_rejects_a_league_of_another_championship(self):
        self.client.force_login(self.guest)

        response = self.client.post(
            self.join_url, {"player_name": "Ospite", "league": self.other_league.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ChampionshipPlayer.objects.filter(user=self.guest).exists())

    def test_join_rejects_a_player_name_already_taken(self):
        ChampionshipPlayer.objects.create(
            user=self.organizer,
            championship=self.championship,
            league=self.league_a,
            player_name="Ospite",
        )
        self.client.force_login(self.guest)

        response = self.client.post(
            self.join_url, {"player_name": "Ospite", "league": self.league_a.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ChampionshipPlayer.objects.filter(user=self.guest).exists())

    def test_joining_twice_is_welcomed_instead_of_crashing(self):
        ChampionshipPlayer.objects.create(
            user=self.guest,
            championship=self.championship,
            league=self.league_a,
            player_name="Ospite",
        )
        self.client.force_login(self.guest)

        response = self.client.get(self.join_url)

        self.assertRedirects(
            response, reverse("championship_dashboard", args=[self.championship.id])
        )
        self.assertEqual(ChampionshipPlayer.objects.filter(user=self.guest).count(), 1)

    def test_join_requires_login_and_comes_back_after_it(self):
        response = self.client.get(self.join_url)

        self.assertRedirects(response, f"{reverse('login')}?next={self.join_url}")

    # --- F3 ---------------------------------------------------------------

    def test_invite_link_leads_to_the_join_page(self):
        self.client.force_login(self.guest)
        token = invites.make_invite_token(self.championship)

        response = self.client.get(reverse("invite_accept", args=[token]))

        self.assertRedirects(response, self.join_url)

    def test_tampered_token_is_refused(self):
        self.client.force_login(self.guest)
        token = invites.make_invite_token(self.championship) + "x"

        response = self.client.get(reverse("invite_accept", args=[token]))

        self.assertRedirects(response, reverse("user_dashboard"))

    def test_expired_token_is_refused(self):
        self.client.force_login(self.guest)
        token = invites.make_invite_token(self.championship)

        with patch.object(invites, "INVITE_MAX_AGE", timedelta(seconds=-1)):
            response = self.client.get(reverse("invite_accept", args=[token]))

        self.assertRedirects(response, reverse("user_dashboard"))

    def test_invite_box_is_shown_only_to_managers(self):
        self.client.force_login(self.organizer)
        manager_response = self.client.get(
            reverse("championship_info", args=[self.championship.id])
        )
        self.assertContains(manager_response, "Invita i tuoi amici")

        self.client.force_login(self.guest)
        guest_response = self.client.get(
            reverse("championship_info", args=[self.championship.id])
        )
        self.assertNotContains(guest_response, "Invita i tuoi amici")

    # --- F4 ---------------------------------------------------------------

    def test_pasted_full_invite_url_is_accepted(self):
        self.client.force_login(self.guest)
        token = invites.make_invite_token(self.championship)
        pasted = f"https://fantaf1.example.com{reverse('invite_accept', args=[token])}"

        response = self.client.post(reverse("invite_redeem"), {"invite_code": pasted})

        self.assertRedirects(response, self.join_url)

    def test_pasted_bare_token_is_accepted(self):
        self.client.force_login(self.guest)
        token = invites.make_invite_token(self.championship)

        response = self.client.post(
            reverse("invite_redeem"), {"invite_code": f"  {token}  "}
        )

        self.assertRedirects(response, self.join_url)

    def test_empty_code_is_reported_without_crashing(self):
        self.client.force_login(self.guest)

        response = self.client.post(reverse("invite_redeem"), {"invite_code": "   "})

        self.assertRedirects(response, reverse("user_dashboard"))


@override_settings(STORAGES=TEST_STORAGES)
class ChampionshipManageTests(TestCase):
    """Manage tab (#70): players by league, reserved to managers, who can promote players."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.manager = User.objects.create_user(
            username="capo", email="capo@example.com", password="password123"
        )
        self.player_user = User.objects.create_user(
            username="pilota", email="pilota@example.com", password="password123"
        )

        self.championship = Championship.objects.create(name="Gestita", year=2026)
        self.league_a = League.objects.create(championship=self.championship, name="Serie A")
        self.league_b = League.objects.create(championship=self.championship, name="Serie B")
        ChampionshipManager.objects.create(user=self.manager, championship=self.championship)
        ChampionshipPlayer.objects.create(
            user=self.manager,
            championship=self.championship,
            league=self.league_a,
            player_name="Capo",
        )
        self.player = ChampionshipPlayer.objects.create(
            user=self.player_user,
            championship=self.championship,
            league=self.league_b,
            player_name="Pilota",
        )

        self.players_url = reverse("championship_manage_players", args=[self.championship.id])
        self.info_url = reverse("championship_info", args=[self.championship.id])

    def promote_url(self, player):
        return reverse(
            "championship_promote_manager", args=[self.championship.id, player.id]
        )

    def is_manager(self, user):
        return ChampionshipManager.objects.filter(
            user=user, championship=self.championship
        ).exists()

    def test_manager_sees_players_grouped_by_league(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.players_url)

        self.assertEqual(response.status_code, 200)
        leagues = {league.name: league.participants.all() for league in response.context["leagues"]}
        self.assertEqual([p.player_name for p in leagues["Serie A"]], ["Capo"])
        self.assertEqual([p.player_name for p in leagues["Serie B"]], ["Pilota"])
        self.assertContains(response, "Rendi manager")

    def test_players_page_query_count_does_not_grow_with_players(self):
        self.client.force_login(self.manager)
        self.client.get(self.players_url)  # warm up session and caches

        with CaptureQueriesContext(connection) as before:
            self.client.get(self.players_url)
        for i in range(5):
            user = get_user_model().objects.create_user(
                username=f"extra{i}", email=f"extra{i}@example.com", password="password123"
            )
            ChampionshipPlayer.objects.create(
                user=user,
                championship=self.championship,
                league=self.league_b,
                player_name=f"Extra {i}",
            )
        with CaptureQueriesContext(connection) as after:
            self.client.get(self.players_url)

        self.assertEqual(len(after.captured_queries), len(before.captured_queries))

    def test_non_manager_is_sent_back_to_the_championship(self):
        self.client.force_login(self.player_user)

        response = self.client.get(self.players_url)

        self.assertRedirects(
            response, reverse("championship_dashboard", args=[self.championship.id])
        )

    def test_manage_tab_is_shown_only_to_managers(self):
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(self.info_url), self.players_url)

        self.client.force_login(self.player_user)
        self.assertNotContains(self.client.get(self.info_url), self.players_url)

    def test_manager_promotes_a_player(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.promote_url(self.player))

        self.assertRedirects(response, self.players_url)
        self.assertTrue(self.is_manager(self.player_user))

    def test_promoting_twice_does_not_duplicate_the_manager(self):
        self.client.force_login(self.manager)

        self.client.post(self.promote_url(self.player))
        self.client.post(self.promote_url(self.player))

        self.assertEqual(
            ChampionshipManager.objects.filter(
                user=self.player_user, championship=self.championship
            ).count(),
            1,
        )

    def test_non_manager_cannot_promote(self):
        self.client.force_login(self.player_user)

        self.client.post(self.promote_url(self.player))

        self.assertFalse(self.is_manager(self.player_user))

    def test_player_of_another_championship_cannot_be_promoted(self):
        other = Championship.objects.create(name="Altro", year=2026)
        stranger = ChampionshipPlayer.objects.create(
            user=get_user_model().objects.create_user(
                username="estraneo", email="estraneo@example.com", password="password123"
            ),
            championship=other,
            league=League.objects.create(championship=other, name="Lega Estranea"),
            player_name="Estraneo",
        )
        self.client.force_login(self.manager)

        response = self.client.post(self.promote_url(stranger))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.is_manager(stranger.user))

    def test_promote_refuses_get(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.promote_url(self.player))

        self.assertEqual(response.status_code, 405)
        self.assertFalse(self.is_manager(self.player_user))

    def demote_url(self, player):
        return reverse(
            "championship_demote_manager", args=[self.championship.id, player.id]
        )

    def test_manager_demotes_another_manager(self):
        ChampionshipManager.objects.create(user=self.player_user, championship=self.championship)
        self.client.force_login(self.manager)

        response = self.client.post(self.demote_url(self.player))

        self.assertRedirects(response, self.players_url)
        self.assertFalse(self.is_manager(self.player_user))
        self.assertTrue(self.is_manager(self.manager))

    def test_manager_can_step_down_and_loses_the_page(self):
        ChampionshipManager.objects.create(user=self.player_user, championship=self.championship)
        me = ChampionshipPlayer.objects.get(user=self.manager, championship=self.championship)
        self.client.force_login(self.manager)

        response = self.client.post(self.demote_url(me))

        self.assertRedirects(
            response,
            reverse("championship_dashboard", args=[self.championship.id]),
            fetch_redirect_response=False,
        )
        self.assertFalse(self.is_manager(self.manager))

    def test_last_manager_cannot_step_down(self):
        me = ChampionshipPlayer.objects.get(user=self.manager, championship=self.championship)
        self.client.force_login(self.manager)

        self.client.post(self.demote_url(me))

        self.assertTrue(self.is_manager(self.manager))

    def test_remove_button_is_hidden_for_the_last_manager(self):
        self.client.force_login(self.manager)

        self.assertNotContains(self.client.get(self.players_url), "Togli ruolo")

    def test_non_manager_cannot_demote(self):
        ChampionshipManager.objects.create(user=self.player_user, championship=self.championship)
        stranger = get_user_model().objects.create_user(
            username="intruso", email="intruso@example.com", password="password123"
        )
        self.client.force_login(stranger)

        self.client.post(
            self.demote_url(
                ChampionshipPlayer.objects.get(user=self.manager, championship=self.championship)
            )
        )

        self.assertTrue(self.is_manager(self.manager))


@override_settings(STORAGES=TEST_STORAGES)
class RegularQualifyingPickerTests(TestCase):
    """La griglia della qualifica regular segue il roster del weekend e il
    limite di scelte per scuderia definiti dal backend."""

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="pole-hunter",
            email="pole@example.com",
            password="password123",
        )
        self.client.force_login(self.user)

        self.championship = Championship.objects.create(name="Pole Cup", year=2026)
        league = League.objects.create(championship=self.championship, name="Lega")
        self.player = ChampionshipPlayer.objects.create(
            user=self.user,
            championship=self.championship,
            league=league,
            player_name="Pole Hunter",
        )

        circuit = Circuit.objects.create(
            name="Imola", country="Italy", location="Imola", api_id="circuit-imola"
        )
        self.full_team = Team.objects.create(
            name="Scuderia Piena",
            short_name="SPI",
            api_id="team-full",
            nationality="IT",
        )
        other_team = Team.objects.create(
            name="Scuderia Libera",
            short_name="SLI",
            api_id="team-free",
            nationality="IT",
        )

        def driver(code, number, team):
            return Driver.objects.create(
                first_name=code,
                last_name=f"Pilota{code}",
                number=number,
                short_name=code,
                team=team,
                season=2026,
                api_id=f"drv-{code.lower()}",
            )

        used_1 = driver("US1", 1, self.full_team)
        used_2 = driver("US2", 2, self.full_team)
        self.third_seat = driver("TRD", 3, self.full_team)
        self.free_driver = driver("FRE", 4, other_team)
        self.not_racing = driver("RES", 5, other_team)

        # Due qualifiche già giocate con i due titolari della scuderia piena
        for round_number, used in ((1, used_1), (2, used_2)):
            past_weekend = Weekend.objects.create(
                circuit=circuit,
                event_name=f"GP {round_number}",
                round_number=round_number,
                season=2026,
                weekend_type="regular",
            )
            PlayerQualifyingChoice.objects.create(
                player=self.player,
                qualifying=Qualifying.objects.create(
                    weekend=past_weekend, type="regular"
                ),
                driver=used,
            )

        self.weekend = Weekend.objects.create(
            circuit=circuit,
            event_name="GP Imola",
            round_number=3,
            season=2026,
            weekend_type="regular",
            qualifying_start=timezone.now() + timedelta(days=1),
        )
        self.qualifying = Qualifying.objects.create(
            weekend=self.weekend, type="regular"
        )
        for racing in (self.third_seat, self.free_driver):
            WeekendParticipant.objects.create(
                weekend=self.weekend, driver=racing, team=racing.team
            )

        self.url = reverse(
            "race_qualifying_choice",
            args=[self.championship.id, self.weekend.id, self.qualifying.id],
        )

    def test_grid_shows_only_weekend_participants(self):
        response = self.client.get(self.url)

        drivers = response.context["drivers"]
        self.assertEqual(
            {d.id for d in drivers}, {self.third_seat.id, self.free_driver.id}
        )
        self.assertNotContains(response, "PilotaRES")

    def test_driver_of_a_team_at_the_limit_is_locked_with_the_reason(self):
        response = self.client.get(self.url)

        drivers = {d.id: d for d in response.context["drivers"]}
        self.assertEqual(
            drivers[self.third_seat.id].locked_reason, "scuderia già scelta 2 volte"
        )
        self.assertIsNone(drivers[self.free_driver.id].locked_reason)
        self.assertContains(response, "al massimo 2 volte")

    def test_post_refuses_a_driver_of_a_team_at_the_limit(self):
        self.client.post(self.url, {"driver": self.third_seat.id})

        self.assertFalse(
            PlayerQualifyingChoice.objects.filter(
                player=self.player, qualifying=self.qualifying
            ).exists()
        )

    def test_post_accepts_a_participant_of_a_free_team(self):
        self.client.post(self.url, {"driver": self.free_driver.id})

        choice = PlayerQualifyingChoice.objects.get(
            player=self.player, qualifying=self.qualifying
        )
        self.assertEqual(choice.driver, self.free_driver)


class WeekendPagesFixture:
    """Stagione minima per aprire ogni pagina: un weekend regular e uno sprint,
    con sessioni, roster, griglia e risultati, più un campionato con un giocatore."""

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="giocatore", email="giocatore@example.com", password="password123"
        )
        # Ha un account ma non gioca nel campionato (#58).
        self.outsider = get_user_model().objects.create_user(
            username="spettatore", email="spettatore@example.com", password="password123"
        )

        self.championship = Championship.objects.create(name="Smoke Cup", year=2026)
        self.league = League.objects.create(championship=self.championship, name="Lega")
        # Senza il giocatore: la pagina di iscrizione si apre invece di rimandare al campionato.
        self.open_championship = Championship.objects.create(
            name="Open Cup", year=2026, is_private=False
        )
        League.objects.create(championship=self.open_championship, name="Lega Aperta")
        ChampionshipManager.objects.create(
            user=self.user, championship=self.championship
        )
        ChampionshipPlayer.objects.create(
            user=self.user,
            championship=self.championship,
            league=self.league,
            player_name="Giocatore",
        )

        circuit = Circuit.objects.create(
            name="Monza", country="Italy", location="Monza", api_id="circuit-monza"
        )
        team = Team.objects.create(
            name="Scuderia Smoke",
            short_name="SMK",
            api_id="team-smoke",
            nationality="IT",
        )
        drivers = [
            Driver.objects.create(
                first_name=f"Pilota{n}",
                last_name=f"Smoke{n}",
                number=n,
                short_name=f"SM{n}",
                team=team,
                season=2026,
                api_id=f"drv-smoke-{n}",
            )
            for n in (1, 2)
        ]

        future = timezone.now() + timedelta(days=7)
        self.regular_weekend = Weekend.objects.create(
            circuit=circuit,
            event_name="GP Regular",
            round_number=1,
            season=2026,
            weekend_type="regular",
            qualifying_start=future,
            race_start=future + timedelta(days=1),
        )
        self.sprint_weekend = Weekend.objects.create(
            circuit=circuit,
            event_name="GP Sprint",
            round_number=2,
            season=2026,
            weekend_type="sprint",
            sprint_qualifying_start=future + timedelta(days=7),
            sprint_start=future + timedelta(days=8),
            qualifying_start=future + timedelta(days=8),
            race_start=future + timedelta(days=9),
        )
        self.regular_qualifying = Qualifying.objects.create(
            weekend=self.regular_weekend, type="regular"
        )
        self.regular_race = Race.objects.create(
            weekend=self.regular_weekend, type="regular"
        )
        self.sprint_qualifying = Qualifying.objects.create(
            weekend=self.sprint_weekend, type="sprint"
        )
        self.sprint_race = Race.objects.create(
            weekend=self.sprint_weekend, type="sprint"
        )
        self.sprint_weekend_qualifying = Qualifying.objects.create(
            weekend=self.sprint_weekend, type="regular"
        )
        Race.objects.create(weekend=self.sprint_weekend, type="regular")

        for weekend in (self.regular_weekend, self.sprint_weekend):
            for driver in drivers:
                WeekendParticipant.objects.create(
                    weekend=weekend, driver=driver, team=team
                )
        # Classifica della qualifica del sabato: la pagina dei risultati (#195)
        # si apre senza aspettare il via.
        for position, driver in enumerate(drivers, start=1):
            QualifyingResult.objects.create(
                qualifying=self.regular_qualifying,
                driver=driver,
                position=position,
                q1_position=position,
                q1_time=timedelta(minutes=1, seconds=20 + position, milliseconds=123),
            )
        for race in (self.regular_race, self.sprint_race):
            for position, driver in enumerate(drivers, start=1):
                RaceStartingGrid.objects.create(
                    race=race, driver=driver, position=position
                )
                RaceResult.objects.create(
                    race=race,
                    driver=driver,
                    position=position,
                    status="Finished",
                    starting_grid=position,
                )

    def pages(self):
        """Rotta -> args delle pagine che si aprono con una GET e rispondono 200."""
        c = self.championship.id
        rw, sw = self.regular_weekend.id, self.sprint_weekend.id
        return {
            "account": [],
            "account_profile": [],
            "account_security": [],
            "user_dashboard": [],
            "create_championship": [],
            "join_championship": [self.open_championship.id],
            "championship_dashboard": [c],
            "championship_next_weekend": [c],
            "championship_my_choices": [c],
            "championship_calendar": [c],
            "championship_league_standings": [c],
            "championship_general_standings": [c],
            "championship_qualifying_standings": [c],
            "championship_sprint_standings": [c],
            "championship_info": [c],
            "championship_manage_players": [c],
            "championship_leave": [c],
            "weekend_details": [c, rw],
            "sprint_race_qualifying_choice": [c, sw, self.sprint_qualifying.id],
            "race_qualifying_choice": [c, rw, self.regular_qualifying.id],
            "race_qualifying_multi_choice": [c, sw, self.sprint_weekend_qualifying.id],
            "sprint_race_choice": [c, sw, self.sprint_race.id],
            "regular_race_choice": [c, rw, self.regular_race.id],
            "sprint_race_results": [c, sw, self.sprint_race.id],
            "regular_race_results": [c, rw, self.regular_race.id],
            "race_qualifying_results": [c, rw, self.regular_qualifying.id],
        }


@override_settings(STORAGES=TEST_STORAGES)
class PageSmokeTests(WeekendPagesFixture, TestCase):
    """Rete di sicurezza per i refactoring (#53): ogni rotta si apre senza errori."""

    # Pagine aperte anche senza login.
    PUBLIC_PAGES = {
        "home",
        "game",
        "game_rules",
        "f1_drivers_standings",
        "login",
        "register",
    }
    # Azioni, non pagine: hanno i loro test (InviteAndJoinTests, LoginNextRedirectTests,
    # ChampionshipManageTests).
    ACTIONS = {
        "logout",
        "invite_redeem",
        "invite_accept",
        "championship_promote_manager",
        "championship_demote_manager",
    }
    # Indirizzi vecchi rimandati ai nuovi (#89): li prova LegacyUrlRedirectTests.
    LEGACY_REDIRECTS = {
        "legacy_user_dashboard",
        "legacy_championship_dashboard",
        "legacy_invite_accept",
    }
    # Pagine pubbliche con argomenti (#134): rotta -> args nel fixture.
    PUBLIC_PAGES_WITH_ARGS = {"f1_race_results": [2026, 1]}

    def test_every_route_is_covered(self):
        routes = {p.name for p in fanta_urls.urlpatterns}

        self.assertEqual(
            routes,
            set(self.pages())
            | self.PUBLIC_PAGES
            | self.ACTIONS
            | self.LEGACY_REDIRECTS
            | set(self.PUBLIC_PAGES_WITH_ARGS),
        )

    def test_public_pages_with_arguments_open_for_anonymous_users(self):
        for name, args in self.PUBLIC_PAGES_WITH_ARGS.items():
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 200)

    def test_public_pages_open_for_anonymous_users(self):
        for name in self.PUBLIC_PAGES:
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_every_page_opens_for_an_enrolled_player(self):
        self.client.force_login(self.user)

        for name, args in self.pages().items():
            with self.subTest(route=name):
                self.assertEqual(
                    self.client.get(reverse(name, args=args)).status_code, 200
                )

    def test_game_page_opens_for_a_logged_in_user(self):
        # A differenza di home, /game/ non rimanda alla dashboard chi è autenticato.
        self.client.force_login(self.user)

        self.assertEqual(self.client.get(reverse("game")).status_code, 200)

    def test_protected_pages_redirect_anonymous_users_to_login(self):
        for name, args in self.pages().items():
            url = reverse(name, args=args)
            with self.subTest(route=name):
                self.assertRedirects(
                    self.client.get(url),
                    f"{reverse('login')}?next={url}",
                    fetch_redirect_response=False,
                )


@override_settings(STORAGES=TEST_STORAGES)
class NotEnrolledWeekendPagesTests(WeekendPagesFixture, TestCase):
    """Chi non gioca il campionato (es. un manager che non partecipa) non deve
    prendere un 500 sulle pagine del weekend (#58)."""

    CHOICE_PAGES = (
        "sprint_race_qualifying_choice",
        "race_qualifying_choice",
        "race_qualifying_multi_choice",
        "sprint_race_choice",
        "regular_race_choice",
    )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.outsider)

    def test_choice_pages_redirect_to_the_weekend_with_a_message(self):
        pages = self.pages()
        for name in self.CHOICE_PAGES:
            championship_id, weekend_id, _ = pages[name]
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=pages[name]), follow=True)

                self.assertRedirects(
                    response,
                    reverse("weekend_details", args=[championship_id, weekend_id]),
                )
                self.assertContains(response, "Non sei iscritto")

    def test_choice_pages_refuse_a_post(self):
        url = reverse("regular_race_choice", args=self.pages()["regular_race_choice"])

        response = self.client.post(url, {})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerRaceChoice.objects.exists())

    def test_results_page_shows_the_classification_without_the_player_panel(self):
        for name in ("sprint_race_results", "regular_race_results"):
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=self.pages()[name]))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Smoke1")
                self.assertNotContains(response, "La tua gara")

    def test_weekend_detail_hides_the_choice_buttons(self):
        url = reverse("weekend_details", args=self.pages()["weekend_details"])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Scegli")
        self.assertNotContains(response, "Da scegliere")

    def test_weekend_detail_still_shows_the_choice_buttons_to_players(self):
        self.client.force_login(self.user)
        url = reverse("weekend_details", args=self.pages()["weekend_details"])

        self.assertContains(self.client.get(url), "Scegli")


@override_settings(STORAGES=TEST_STORAGES)
class ItalianDatesTests(WeekendPagesFixture, TestCase):
    """Le pagine mostrano date in italiano e in ora italiana, il DB resta in UTC (#91)."""

    def test_weekend_page_shows_italian_names_and_rome_time(self):
        # Luglio: ora legale, Roma è UTC+2.
        self.regular_weekend.qualifying_start = datetime(
            2026, 7, 4, 13, 0, tzinfo=dt_timezone.utc
        )
        self.regular_weekend.race_start = datetime(
            2026, 7, 5, 13, 0, tzinfo=dt_timezone.utc
        )
        self.regular_weekend.save()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "weekend_details", args=[self.championship.id, self.regular_weekend.id]
            )
        )

        self.assertContains(response, "5 luglio 2026")
        self.assertContains(response, "Sab 4 Lug · 15:00")
        self.assertContains(response, "Dom 5 Lug · 15:00")

    def test_next_weekend_countdown_is_in_italian(self):
        # La fixture fa partire il primo weekend fra 7 giorni.
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("championship_next_weekend", args=[self.championship.id])
        )

        # timeuntil separa numero e unità con uno spazio non divisibile.
        self.assertContains(response, "fra 6 giorni")

    def test_form_errors_are_in_italian(self):
        response = self.client.post(reverse("register"), {})

        self.assertContains(response, "Questo campo è obbligatorio.")


class EventProcessingServiceTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        circuit = Circuit.objects.create(
            name="Monza",
            country="Italy",
            location="Monza",
            api_id="circuit-monza",
        )
        self.weekend = Weekend.objects.create(
            circuit=circuit,
            event_name="Italian GP",
            round_number=14,
            season=2026,
            weekend_type="sprint",
        )
        self.sprint_qualifying = Qualifying.objects.create(
            weekend=self.weekend, type="sprint"
        )
        self.sprint_race = Race.objects.create(weekend=self.weekend, type="sprint")
        self.qualifying = Qualifying.objects.create(
            weekend=self.weekend, type="regular"
        )
        self.race = Race.objects.create(weekend=self.weekend, type="regular")

    def _status(self, *, event, status=Status.PENDING, hours_ago=1, attempts=0):
        field = "race" if isinstance(event, Race) else "qualifying"
        return EventProcessingStatus.objects.create(
            **{field: event},
            status=status,
            eligible_after=self.now - timedelta(hours=hours_ago),
            attempts=attempts,
        )

    def test_eligible_statuses_filters_by_status_and_date_in_chronological_order(self):
        self._status(event=self.sprint_race, status=Status.PROCESSED, hours_ago=4)
        race_status = self._status(
            event=self.race, status=Status.WAITING_FOR_RESULTS, hours_ago=2
        )
        qualifying_status = self._status(event=self.qualifying, hours_ago=3)
        self._status(event=self.sprint_qualifying, hours_ago=-1)

        self.assertEqual(
            list(ep.eligible_events(self.now)),
            [qualifying_status, race_status],
        )

    def test_qualifying_ready_requires_processed_qualifying_of_same_type(self):
        qualifying_status = self._status(event=self.qualifying)

        self.assertFalse(ep.qualifying_ready(self.race))

        qualifying_status.status = Status.PROCESSED
        qualifying_status.save(update_fields=["status"])
        self.assertTrue(ep.qualifying_ready(self.race))
        self.assertFalse(ep.qualifying_ready(self.sprint_race))

    def test_mark_waiting_never_turns_into_error(self):
        # An event resumed after an ERROR may already have many attempts
        event_status = self._status(event=self.race, status=Status.ERROR, attempts=32)

        result = ep.mark(event_status, status=Status.WAITING_FOR_RESULTS, now=self.now)
        event_status.refresh_from_db()
        self.assertEqual(result, Status.WAITING_FOR_RESULTS)
        self.assertEqual(event_status.status, Status.WAITING_FOR_RESULTS)
        self.assertEqual(event_status.attempts, 33)
        self.assertEqual(event_status.last_attempt_at, self.now)
        self.assertEqual(event_status.last_error, "")

    def test_mark_records_error_and_processed(self):
        event_status = self._status(event=self.qualifying, attempts=5)

        ep.mark(event_status, status=Status.ERROR, now=self.now, error="boom")
        event_status.refresh_from_db()
        self.assertEqual(event_status.status, Status.ERROR)
        self.assertEqual(event_status.last_error, "boom")
        self.assertEqual(event_status.attempts, 6)

        ep.mark(event_status, status=Status.PROCESSED, now=self.now)
        event_status.refresh_from_db()
        self.assertEqual(event_status.status, Status.PROCESSED)
        self.assertEqual(event_status.last_error, "")

    def _next_pair(self):
        out = StringIO()
        call_command("next_pair_events", stdout=out)
        return json.loads(out.getvalue().strip().splitlines()[-1])

    def test_next_pair_events_returns_oldest_unprocessed_pair(self):
        self._status(event=self.sprint_qualifying, status=Status.PROCESSED, hours_ago=30)
        self._status(event=self.sprint_race, status=Status.PROCESSED, hours_ago=20)
        quali = self._status(event=self.qualifying, status=Status.ERROR, hours_ago=10)
        # race still in the future: the planner must see it to wait for it
        race = self._status(event=self.race, hours_ago=-12)

        pair = self._next_pair()

        self.assertEqual(pair["qualifying"]["status_id"], quali.id)
        self.assertEqual(pair["qualifying"]["status"], Status.ERROR)
        self.assertEqual(pair["race"]["status_id"], race.id)
        self.assertEqual(pair["race"]["type"], "regular")

    def test_next_pair_events_exits_99_when_everything_is_processed(self):
        self._status(event=self.qualifying, status=Status.PROCESSED)
        self._status(event=self.race, status=Status.PROCESSED)

        with self.assertRaises(CommandError) as ctx:
            call_command("next_pair_events", stdout=StringIO())
        self.assertEqual(ctx.exception.returncode, 99)


class InsertSprintQualifyingResultTests(TestCase):
    COMMAND = "fantaApp.management.commands.insert_quali_result"

    def setUp(self):
        circuit = Circuit.objects.create(
            name="Marina Bay", country="Singapore", location="Singapore", api_id="marina_bay"
        )
        weekend = Weekend.objects.create(
            circuit=circuit,
            event_name="Singapore GP",
            round_number=17,
            season=2026,
            weekend_type="sprint",
        )
        Qualifying.objects.create(weekend=weekend, type="sprint")

    def _run(self):
        call_command(
            "insert_quali_result", season=2026, round=17, type="sprint", stdout=StringIO()
        )

    def test_sprint_asks_openf1_for_sprint_qualifying(self):
        with patch(f"{self.COMMAND}.get_qualifying_result", return_value=[]) as get:
            self._run()
        self.assertEqual(get.call_args.args[1], "Sprint Qualifying")

    def test_sprint_not_available_means_retry_later(self):
        from .services.sources.base import ResultsNotAvailable

        with patch(f"{self.COMMAND}.get_qualifying_result", side_effect=ResultsNotAvailable):
            with self.assertRaises(CommandError) as ctx:
                self._run()
        self.assertEqual(ctx.exception.returncode, 3)


class OpenF1RaceResultTests(TestCase):
    """Shape of OpenF1 session_result/laps rows, as seen for Singapore 2026."""

    SOURCE = "fantaApp.services.sources.openF1Source"
    FLAGS = {"dnf": False, "dns": False, "dsq": False}
    SESSION_RESULT = [
        {"position": 1, "driver_number": 3, "points": 25.0, **FLAGS, "gap_to_leader": 0},
        {"position": 2, "driver_number": 11, "points": 0.0, **FLAGS, "gap_to_leader": "+1 LAP"},
        {"position": 3, "driver_number": 23, "points": 0.0, **FLAGS, "dnf": True, "gap_to_leader": None},
        {"position": None, "driver_number": 18, "points": 0.0, **FLAGS, "dnf": True, "gap_to_leader": None},
        {"position": None, "driver_number": 5, "points": 0.0, **FLAGS, "dsq": True, "gap_to_leader": None},
    ]
    LAPS = [
        {"driver_number": 3, "lap_number": 1, "lap_duration": None},
        {"driver_number": 3, "lap_number": 2, "lap_duration": 95.5},
        {"driver_number": 3, "lap_number": 3, "lap_duration": 94.25},
    ]

    def test_maps_positions_status_and_fastest_lap(self):
        from .services.sources import openF1Source

        rows = {"session_result": self.SESSION_RESULT, "laps": self.LAPS}
        with patch(f"{self.SOURCE}._session_key", return_value=1), \
             patch(f"{self.SOURCE}._fetch", side_effect=lambda endpoint, _: [dict(r) for r in rows[endpoint]]):
            results = openF1Source.get_race_result(2026, "Race", None)

        self.assertEqual(
            [(r["driver_number"], r["position"], r["status"]) for r in results],
            [(3, 1, "Finished"), (11, 2, "Lapped"), (23, 3, "Retired"), (18, 4, "Retired"), (5, 5, "Disqualified")],
        )
        self.assertEqual(results[0]["points"], 25)
        self.assertEqual((results[0]["best_lap"], results[0]["fast_lap"]), (3, timedelta(seconds=94.25)))
        self.assertIsNone(results[1]["fast_lap"])


class LegacyUrlRedirectTests(TestCase):
    """#89: gli indirizzi vecchi rimasti in segnalibri e chat portano alle pagine nuove."""

    def test_old_paths_redirect_to_the_new_ones(self):
        cases = {
            "/dashboard/account/": reverse("user_dashboard"),
            "/dashboard/championships/7/": reverse("championship_dashboard", args=[7]),
            "/campionati/invito/abc123/": reverse("invite_accept", args=["abc123"]),
        }
        for old, new in cases.items():
            with self.subTest(old=old):
                self.assertRedirects(
                    self.client.get(old),
                    new,
                    status_code=301,
                    fetch_redirect_response=False,
                )

    def test_new_paths_are_in_english(self):
        self.assertEqual(reverse("user_dashboard"), "/championships/")
        self.assertEqual(
            reverse("championship_league_standings", args=[7]),
            "/championships/7/standings/league/",
        )
        self.assertEqual(
            reverse("weekend_details", args=[7, 3]), "/championships/7/weekends/3/"
        )


@override_settings(STORAGES=TEST_STORAGES)
class GameRulesPageTests(WeekendPagesFixture, TestCase):
    """#81, #230: il regolamento è una pagina pubblica del gioco, letta da
    rules.py; la scheda Info del campionato porta lì."""

    def test_open_to_everyone_with_the_tables(self):
        response = self.client.get(reverse("game_rules"))

        self.assertContains(response, "Regolamento")
        self.assertContains(response, 'id="qualifiche-classico"')
        self.assertContains(response, 'href="#costi"')
        credit = ChampionshipPlayer._meta.get_field("available_credit").default
        self.assertContains(response, f"Ogni giocatore ha {credit} fantamilioni")

    def test_numbers_come_from_the_rules(self):
        from .services import rules

        with patch.object(rules, "PUPILLO_DISCOUNT_STEP", 7), patch.dict(
            rules.MULTI_CHOICE_SLOT_SIZES, {"q1_pass": 9}
        ):
            response = self.client.get(reverse("game_rules"))

        self.assertContains(response, "sconta 7 fantamilioni")
        self.assertContains(response, "Si pronosticano 9 piloti che passano il Q1")

    def test_championship_info_links_to_the_rules(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("championship_info", args=[self.championship.id])
        )

        self.assertContains(response, f'href="{reverse("game_rules")}"')
        self.assertNotContains(response, "Costo dei piloti")
        self.assertNotIn("rulebook", response.context)


@override_settings(STORAGES=TEST_STORAGES)
class SiteHeaderTests(TestCase):
    """Header e footer uguali ovunque, menu accessibili (#93). Nell'header solo il
    logo, il tema e accesso/iscrizione o il menu utente, anche su mobile (#131)."""

    def _parts(self, response):
        html = response.content.decode()
        header = html[html.index("<header") : html.index("</header>")]
        footer = html[html.index("<footer") : html.index("</footer>")]
        return header, footer

    def test_anonymous_visitor_gets_the_logo_and_the_login_links_only(self):
        header, footer = self._parts(self.client.get(reverse("game")))

        self.assertEqual(header.count(f'href="{reverse("home")}"'), 1)  # il logo
        self.assertIn(f'href="{reverse("login")}"', header)
        self.assertIn(f'href="{reverse("register")}"', header)
        for name in ("f1_drivers_standings", "game", "user_dashboard"):
            with self.subTest(route=name):
                self.assertNotIn(f'href="{reverse(name)}"', header)
        # Niente pannello mobile: non c'è più niente da metterci.
        self.assertNotIn("nav-toggle", header)
        self.assertNotIn('id="user-menu"', header)
        # Le pagine tolte dall'header restano raggiungibili dal footer.
        for name in ("home", "f1_drivers_standings", "game"):
            with self.subTest(footer=name):
                self.assertIn(f'href="{reverse(name)}"', footer)

    def test_logged_in_user_gets_the_user_menu_only(self):
        user = get_user_model().objects.create_user(
            username="pilota", email="pilota@example.com", password="password123"
        )
        self.client.force_login(user)

        header, _ = self._parts(self.client.get(reverse("user_dashboard")))

        self.assertIn('aria-controls="user-menu" aria-expanded="false"', header)
        self.assertIn(f'href="{reverse("account")}"', header)
        # La voce della sezione aperta è evidenziata anche nel menu utente.
        self.assertIn(
            f'<a href="{reverse("user_dashboard")}" class="nav-link" '
            'aria-current="page">',
            header,
        )
        self.assertIn(f'action="{reverse("logout")}"', header)
        self.assertEqual(header.count(f'href="{reverse("home")}"'), 1)  # il logo
        for name in ("login", "register", "f1_drivers_standings", "game"):
            with self.subTest(route=name):
                self.assertNotIn(f'href="{reverse(name)}"', header)
        self.assertNotIn("nav-toggle", header)

    def test_toasts_are_announced_and_errors_are_alerts(self):
        html = render_to_string(
            "fantaApp/base.html",
            {
                "messages": [
                    Message(messages.SUCCESS, "Scelta salvata"),
                    Message(messages.ERROR, "Credito insufficiente"),
                ]
            },
        )

        self.assertIn('role="status" aria-live="polite"', html)
        self.assertEqual(html.count('role="alert"'), 1)


@override_settings(STORAGES=TEST_STORAGES)
class F1RaceResultsPageTests(WeekendPagesFixture, TestCase):
    """#134: risultati F1 di un weekend, pagina pubblica; dalla home ci si arriva
    dai weekend già corsi con i risultati importati."""

    def test_open_to_everyone_with_the_grand_prix(self):
        response = self.client.get(reverse("f1_race_results", args=[2026, 1]))

        self.assertContains(response, "Gran Premio")
        self.assertContains(response, "Smoke1")
        self.assertContains(response, "Pos.")
        # Weekend classico: niente sezione Sprint.
        labels = [race["label"] for race in response.context["races"]]
        self.assertEqual(labels, ["Gran Premio"])

    def test_sprint_weekend_shows_both_races(self):
        response = self.client.get(reverse("f1_race_results", args=[2026, 2]))

        self.assertEqual(
            [r["label"] for r in response.context["races"]], ["Gran Premio", "Sprint"]
        )
        # Il GP del weekend sprint non ha ancora risultati nel fixture.
        self.assertContains(response, "Risultati non ancora disponibili.")

    def test_unknown_round_is_not_found(self):
        response = self.client.get(reverse("f1_race_results", args=[2026, 99]))

        self.assertEqual(response.status_code, 404)

    def test_home_links_past_weekends_with_results(self):
        past = timezone.now() - timedelta(days=30)
        for weekend in (self.regular_weekend, self.sprint_weekend):
            for field in (
                "sprint_qualifying_start",
                "sprint_start",
                "qualifying_start",
                "race_start",
            ):
                if getattr(weekend, field):
                    setattr(weekend, field, past)
            weekend.save()

        response = self.client.get(reverse("home"))

        self.assertContains(
            response, f'href="{reverse("f1_race_results", args=[2026, 1])}"'
        )
        # Il GP del weekend sprint non ha risultati: niente link.
        self.assertNotContains(
            response, f'href="{reverse("f1_race_results", args=[2026, 2])}"'
        )


@override_settings(STORAGES=TEST_STORAGES)
class DriversStandingsTests(TestCase):
    """#95: classifica piloti F1 dopo l'ultimo round importato, aperta a tutti."""

    def setUp(self):
        circuit = Circuit.objects.create(
            name="Suzuka", country="Japan", location="Suzuka", api_id="suzuka"
        )
        self.round_1 = Weekend.objects.create(
            circuit=circuit,
            event_name="Australian Grand Prix",
            round_number=1,
            season=2026,
        )
        self.round_2 = Weekend.objects.create(
            circuit=circuit,
            event_name="Japanese Grand Prix",
            round_number=2,
            season=2026,
        )
        self.ferrari = Team.objects.create(
            name="Ferrari", short_name="FER", api_id="ferrari", nationality="Italian"
        )
        self.mclaren = Team.objects.create(
            name="McLaren", short_name="MCL", api_id="mclaren", nationality="British"
        )
        self.leclerc = Driver.objects.create(
            first_name="Charles",
            last_name="Leclerc",
            short_name="LEC",
            team=self.ferrari,
            season=2026,
            api_id="leclerc",
        )
        self.norris = Driver.objects.create(
            first_name="Lando",
            last_name="Norris",
            short_name="NOR",
            team=self.mclaren,
            season=2026,
            api_id="norris",
        )

    def test_shows_a_message_when_there_are_no_standings_yet(self):
        response = self.client.get(reverse("f1_drivers_standings"))

        self.assertContains(response, "La classifica non è ancora disponibile")

    def test_shows_the_latest_round_in_position_order(self):
        DriverStanding.objects.create(
            weekend=self.round_1, driver=self.leclerc, position=1, points=25, wins=1
        )
        DriverStanding.objects.create(
            weekend=self.round_2, driver=self.norris, position=1, points=43, wins=1
        )
        DriverStanding.objects.create(
            weekend=self.round_2, driver=self.leclerc, position=2, points=37, wins=1
        )

        response = self.client.get(reverse("f1_drivers_standings"))

        self.assertContains(response, "Dopo il round 2 · Japanese Grand Prix")
        self.assertEqual(
            [row["driver"] for row in response.context["rows"]],
            [self.norris, self.leclerc],
        )
        self.assertNotContains(response, ">25<")

    def test_team_is_the_one_of_that_weekend(self):
        # Pilota passato in McLaren: la riga segue il roster del weekend, non Driver.team.
        WeekendParticipant.objects.create(
            weekend=self.round_2, driver=self.leclerc, team=self.mclaren
        )
        DriverStanding.objects.create(
            weekend=self.round_2, driver=self.leclerc, position=1, points=25, wins=1
        )

        response = self.client.get(reverse("f1_drivers_standings"))

        self.assertEqual(response.context["rows"][0]["team"], self.mclaren)
        self.assertContains(response, 'class="team-mcl"')


@override_settings(STORAGES=TEST_STORAGES)
class SiteHomeTests(TestCase):
    """#92: home del sito per tutti, con il programma della stagione corrente."""

    def setUp(self):
        self.circuit = Circuit.objects.create(
            name="Monza", country="Italy", location="Monza", api_id="monza"
        )
        self.now = timezone.now()

    def _weekend(self, round_number, race_in_days, season=2026, **fields):
        return Weekend.objects.create(
            circuit=self.circuit,
            event_name=f"Round {round_number} Grand Prix",
            round_number=round_number,
            season=season,
            race_start=self.now + timedelta(days=race_in_days),
            **fields,
        )

    def test_logged_in_users_see_the_home_instead_of_a_redirect(self):
        user = get_user_model().objects.create_user(
            username="pilota", email="pilota@example.com", password="password123"
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "fantaApp/site/home.html")
        self.assertContains(response, f'href="{reverse("game")}"')

    def test_next_grand_prix_comes_first_and_past_weekends_are_apart(self):
        self._weekend(1, race_in_days=-7)
        upcoming = self._weekend(2, race_in_days=3)
        self._weekend(3, race_in_days=10)
        self._weekend(24, race_in_days=-400, season=2025)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.context["season"], 2026)
        self.assertEqual(response.context["next_weekend"]["weekend"], upcoming)
        self.assertEqual(
            [i["weekend"].round_number for i in response.context["upcoming"]], [2, 3]
        )
        self.assertEqual(
            [i["weekend"].round_number for i in response.context["past"]], [1]
        )
        self.assertContains(response, "Prossimo Gran Premio")
        self.assertNotContains(response, "Round 24 Grand Prix")

    def test_sessions_are_listed_in_time_order_with_italian_names(self):
        race = self.now + timedelta(days=3)
        self._weekend(
            1,
            race_in_days=3,
            weekend_type="sprint",
            fp1_start=race - timedelta(days=2),
            sprint_qualifying_start=race - timedelta(days=2, hours=-4),
            sprint_start=race - timedelta(days=1, hours=4),
            qualifying_start=race - timedelta(days=1),
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(
            [s["label"] for s in response.context["next_weekend"]["sessions"]],
            ["Libere 1", "Qualifiche Sprint", "Sprint", "Qualifiche", "Gran Premio"],
        )
        self.assertContains(response, "Weekend sprint")

    def test_season_over_and_empty_calendar_messages(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Calendario non ancora disponibile")

        self._weekend(1, race_in_days=-7)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "La stagione 2026 è conclusa")

    def test_number_of_queries_does_not_grow_with_the_weekends(self):
        self._weekend(1, race_in_days=3)
        with CaptureQueriesContext(connection) as few:
            self.client.get(reverse("home"))

        for round_number in range(2, 12):
            self._weekend(round_number, race_in_days=round_number * 7)
        with CaptureQueriesContext(connection) as many:
            self.client.get(reverse("home"))

        self.assertEqual(len(many), len(few))


@override_settings(STORAGES=TEST_STORAGES)
class AuthPagesTests(TestCase):
    """#94: iscrizione e accesso, testi e regole in italiano."""

    def _register(self, **overrides):
        data = {
            "username": "nuovo",
            "email": "nuovo@example.com",
            "password": "Pista-Monza-1922",
            "password2": "Pista-Monza-1922",
            **overrides,
        }
        return self.client.post(reverse("register"), data)

    def test_sign_up_page_shows_the_password_rules_in_italian(self):
        response = self.client.get(reverse("register"))

        self.assertContains(
            response, "La tua password deve contenere almeno 8 caratteri."
        )
        self.assertContains(response, 'aria-describedby="id_password_help"')

    def test_sign_up_logs_in_and_lands_on_my_championships(self):
        response = self._register()

        self.assertRedirects(response, reverse("user_dashboard"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_weak_passwords_are_rejected_in_italian(self):
        response = self._register(password="password123", password2="password123")

        self.assertContains(response, "Questa password è troppo comune.")
        self.assertFalse(get_user_model().objects.filter(username="nuovo").exists())

    def test_email_is_required(self):
        response = self._register(email="")

        self.assertContains(response, "Questo campo è obbligatorio.")
        self.assertFalse(get_user_model().objects.filter(username="nuovo").exists())

    def test_login_error_does_not_reveal_whether_the_user_exists(self):
        get_user_model().objects.create_user(
            username="esiste", email="esiste@example.com", password="Pista-Monza-1922"
        )

        unknown = self.client.post(
            reverse("login"), {"identifier": "nessuno", "password": "x"}
        )
        wrong = self.client.post(
            reverse("login"), {"identifier": "esiste", "password": "sbagliata"}
        )

        for response in (unknown, wrong):
            self.assertContains(response, "Username, email o password non corretti.")
@override_settings(STORAGES=TEST_STORAGES)
class AccountOverviewTests(TestCase):
    """#96: area account, panoramica raggiungibile dal menu utente."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="pilota", email="pilota@example.com", password="Pista-Monza-1922"
        )

    def test_requires_login(self):
        url = reverse("account")

        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_shows_the_account_data_and_the_championships_link(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("account"))

        self.assertContains(response, "pilota@example.com")
        self.assertContains(response, "Non giochi ancora in nessun campionato.")
        self.assertContains(response, f'href="{reverse("user_dashboard")}"')
        # La voce Account del menu utente e quella del menu laterale sono evidenziate.
        self.assertContains(
            response,
            f'<a href="{reverse("account")}" class="nav-link" aria-current="page">',
        )
@override_settings(STORAGES=TEST_STORAGES)
class AccountPersonalDataTests(TestCase):
    """#97: Account → Dati personali, username, nome e cognome."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="pilota", email="pilota@example.com", password="Pista-Monza-1922"
        )
        get_user_model().objects.create_user(
            username="occupato",
            email="occupato@example.com",
            password="Pista-Monza-1922",
        )
        self.client.force_login(self.user)

    def _save(self, **data):
        return self.client.post(
            reverse("account_profile"),
            {"username": "pilota", "first_name": "", "last_name": "", **data},
            follow=True,
        )

    def test_saves_the_data_with_a_confirmation(self):
        response = self._save(
            username="pilota-nuovo", first_name="Ada", last_name="Rossi"
        )

        self.user.refresh_from_db()
        self.assertEqual(
            (self.user.username, self.user.first_name, self.user.last_name),
            ("pilota-nuovo", "Ada", "Rossi"),
        )
        self.assertContains(response, "Dati personali salvati.")

    def test_username_already_taken_is_rejected_in_italian(self):
        response = self._save(username="occupato")

        self.assertContains(response, "Questo username è già in uso.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "pilota")

    def test_player_names_in_championships_do_not_change(self):
        championship = Championship.objects.create(name="Coppa", year=2026)
        league = League.objects.create(championship=championship, name="Lega")
        player = ChampionshipPlayer.objects.create(
            user=self.user,
            championship=championship,
            league=league,
            player_name="Pilota",
        )

        self._save(username="pilota-nuovo")

        player.refresh_from_db()
        self.assertEqual(player.player_name, "Pilota")

    def test_email_is_shown_but_not_editable(self):
        response = self.client.get(reverse("account_profile"))

        self.assertContains(response, "pilota@example.com")
        self.assertNotContains(response, 'name="email"')
@override_settings(STORAGES=TEST_STORAGES)
class AccountChangePasswordTests(TestCase):
    """#98: Account → Sicurezza, cambio password restando collegati."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="pilota", email="pilota@example.com", password="Pista-Monza-1922"
        )
        self.client.force_login(self.user)

    def _change(self, old, new1, new2=None):
        return self.client.post(
            reverse("account_security"),
            {"old_password": old, "new_password1": new1, "new_password2": new2 or new1},
            follow=True,
        )

    def test_success_keeps_the_user_logged_in(self):
        response = self._change("Pista-Monza-1922", "Curva-Parabolica-71")

        self.assertContains(response, "Password cambiata.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Curva-Parabolica-71"))
        # Ancora dentro: la pagina dell'account si apre senza passare dal login.
        self.assertEqual(self.client.get(reverse("account")).status_code, 200)

    def test_wrong_current_password_is_an_error(self):
        response = self._change("sbagliata", "Curva-Parabolica-71")

        self.assertContains(response, "La password attuale non è corretta.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Pista-Monza-1922"))

    def test_rules_and_errors_are_in_italian(self):
        page = self.client.get(reverse("account_security"))
        self.assertContains(page, "La tua password deve contenere almeno 8 caratteri.")

        response = self._change("Pista-Monza-1922", "password123")
        self.assertContains(response, "Questa password è troppo comune.")


@override_settings(STORAGES=TEST_STORAGES)
class ChampionshipEntryTests(WeekendPagesFixture, TestCase):
    """#155: si entra in un campionato per giocare (o per gestirlo); le schede
    sono Gioca · Classifiche · Info · Gestione."""

    def _open(self, user):
        self.client.force_login(user)
        return self.client.get(
            reverse("championship_dashboard", args=[self.championship.id])
        )

    def _guest(self):
        return get_user_model().objects.create_user(
            username="ospite", email="ospite@example.com", password="password123"
        )

    def test_player_lands_on_the_next_weekend(self):
        response = self._open(self.user)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_section"], "next_weekend")
        self.assertContains(response, "GP Regular")

    def test_manager_who_does_not_play_lands_on_the_manage_tab(self):
        manager = self._guest()
        ChampionshipManager.objects.create(user=manager, championship=self.championship)

        response = self._open(manager)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_section"], "manage_players")

    def test_user_who_does_not_play_lands_on_the_general_standings(self):
        response = self._open(self._guest())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_section"], "standings_general")

    def test_tabs_are_play_then_standings_then_info_then_manage(self):
        html = self._open(self.user).content.decode()
        c = self.championship.id

        positions = [
            html.index(f'href="{reverse(name, args=[c])}"')
            for name in (
                "championship_next_weekend",
                "championship_league_standings",
                "championship_info",
                "championship_manage_players",
            )
        ]
        self.assertEqual(positions, sorted(positions))

    def test_standings_tab_opens_the_general_standings_for_users_who_do_not_play(self):
        html = self._open(self._guest()).content.decode()
        c = self.championship.id

        # La scheda viene prima delle sotto-schede: il primo link alle
        # classifiche è quello della scheda, e porta alla Generale.
        general = html.index(
            f'href="{reverse("championship_general_standings", args=[c])}"'
        )
        league = html.index(
            f'href="{reverse("championship_league_standings", args=[c])}"'
        )
        self.assertLess(general, league)

    def test_play_tab_counts_the_choices_left_for_the_next_weekend(self):
        # Primo weekend della fixture: qualifica e Gran Premio, nessuna scelta fatta.
        response = self._open(self.user)

        self.assertEqual(response.context["play_pending"], 2)
        self.assertContains(
            response, "2<span class=\"sr-only\"> scelte da fare nel prossimo weekend"
        )

    def test_no_counter_for_users_who_do_not_play(self):
        response = self._open(self._guest())

        self.assertEqual(response.context["play_pending"], 0)
        self.assertNotContains(response, "da fare nel prossimo weekend")

    def test_next_weekend_has_its_own_address(self):
        self.assertEqual(
            reverse("championship_next_weekend", args=[7]), "/championships/7/play/"
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("championship_next_weekend", args=[self.championship.id])
        )

        self.assertEqual(response.context["active_section"], "next_weekend")
        self.assertContains(response, "GP Regular")


@override_settings(STORAGES=TEST_STORAGES)
class LeaveChampionshipTests(WeekendPagesFixture, TestCase):
    """#160: un giocatore che non è manager lascia il campionato scrivendone il nome."""

    def setUp(self):
        super().setUp()
        self.leaver = ChampionshipPlayer.objects.create(
            user=self.outsider,
            championship=self.championship,
            league=self.league,
            player_name="Uscente",
        )
        PlayerRaceResult.objects.create(
            player=self.leaver,
            race=self.regular_race,
            credit_spent=50,
            fia_points=10,
            total_points=10,
        )
        self.url = reverse("championship_leave", args=[self.championship.id])

    def _leave(self, user, name):
        self.client.force_login(user)
        return self.client.post(self.url, {"championship_name": name}, follow=True)

    def test_tab_is_shown_only_to_players_who_are_not_managers(self):
        self.client.force_login(self.outsider)
        self.assertContains(self.client.get(self.url), f'href="{self.url}"')

        self.client.force_login(self.user)  # gioca ed è manager
        page = self.client.get(
            reverse("championship_info", args=[self.championship.id])
        )
        self.assertNotContains(page, f'href="{self.url}"')

    def test_right_name_removes_the_player_with_choices_and_results(self):
        response = self._leave(self.outsider, f"  {self.championship.name} ")

        self.assertRedirects(response, reverse("user_dashboard"))
        self.assertContains(response, "Disiscrizione da «Smoke Cup» completata.")
        self.assertFalse(ChampionshipPlayer.objects.filter(pk=self.leaver.pk).exists())
        self.assertFalse(
            PlayerRaceResult.objects.filter(player_id=self.leaver.pk).exists()
        )

        standings = self.client.get(
            reverse("championship_general_standings", args=[self.championship.id])
        )
        self.assertNotContains(standings, "Uscente")

    def test_wrong_name_leaves_everything_as_it_was(self):
        response = self._leave(self.outsider, "Smoke")

        self.assertContains(response, "la disiscrizione non è avvenuta")
        self.assertTrue(ChampionshipPlayer.objects.filter(pk=self.leaver.pk).exists())

    def test_manager_cannot_leave(self):
        response = self._leave(self.user, self.championship.name)

        self.assertContains(response, "I manager non possono disiscriversi")
        self.assertTrue(
            ChampionshipPlayer.objects.filter(
                user=self.user, championship=self.championship
            ).exists()
        )

    def test_user_not_enrolled_gets_a_clear_error(self):
        guest = get_user_model().objects.create_user(
            username="ospite", email="ospite@example.com", password="password123"
        )

        response = self._leave(guest, self.championship.name)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Non sei iscritto a «Smoke Cup».")


@override_settings(STORAGES=TEST_STORAGES)
class WeekendBreadcrumbTests(WeekendPagesFixture, TestCase):
    """#63: percorso campionato › partenza › weekend › sessione sulle pagine del
    weekend; #156: il secondo livello è la pagina da cui si è partiti."""

    WEEKEND_PAGES = (
        "weekend_details",
        "sprint_race_qualifying_choice",
        "race_qualifying_choice",
        "race_qualifying_multi_choice",
        "sprint_race_choice",
        "regular_race_choice",
        "sprint_race_results",
        "regular_race_results",
        "race_qualifying_results",
    )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        c = self.championship.id
        self.choice_url = reverse(
            "regular_race_choice",
            args=[c, self.regular_weekend.id, self.regular_race.id],
        )
        self.championship_url = reverse("championship_dashboard", args=[c])
        self.play_url = reverse("championship_next_weekend", args=[c])
        self.calendar_url = reverse("championship_calendar", args=[c])
        self.weekend_url = reverse("weekend_details", args=[c, self.regular_weekend.id])

    def _crumbs(self, page):
        return [(crumb["label"], crumb["url"]) for crumb in page.context["breadcrumb"]]

    def test_every_weekend_page_has_the_breadcrumb_and_no_back_link(self):
        pages = self.pages()
        for name in self.WEEKEND_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name, args=pages[name]))

                self.assertContains(response, '<nav aria-label="Percorso"', count=1)
                self.assertContains(response, '<span aria-current="page"', count=1)
                self.assertNotContains(response, "← Eventi del weekend")

    def test_next_weekend_links_to_choices_and_weekend_with_from_play(self):
        response = self.client.get(self.play_url)

        self.assertContains(response, f'href="{self.choice_url}?from=play"')
        self.assertContains(response, f'href="{self.weekend_url}?from=play"')

    def test_from_play_goes_straight_back_to_the_next_weekend_even_after_saving(self):
        page = self.client.get(f"{self.choice_url}?from=play")
        self.assertEqual(
            self._crumbs(page),
            [
                ("Smoke Cup 2026", self.championship_url),
                ("Prossimo weekend", self.play_url),
                ("Gran Premio", None),
            ],
        )

        drivers = [grid.driver_id for grid in self.regular_race.starting_grid.all()]
        response = self.client.post(
            f"{self.choice_url}?from=play",
            {"drivers": drivers, "pupillo_driver_id": drivers[0]},
        )

        self.assertRedirects(
            response, f"{self.choice_url}?from=play", fetch_redirect_response=False
        )
        self.assertEqual(self.regular_race.playerracechoice_set.count(), 2)

    def test_otherwise_goes_through_the_calendar(self):
        page = self.client.get(self.choice_url)

        self.assertEqual(
            self._crumbs(page),
            [
                ("Smoke Cup 2026", self.championship_url),
                ("Calendario gare", self.calendar_url),
                ("R1 GP Regular", self.weekend_url),
                ("Gran Premio", None),
            ],
        )

    def test_unknown_from_is_ignored(self):
        page = self.client.get(f"{self.choice_url}?from=https://example.com")

        self.assertEqual(self._crumbs(page)[1], ("Calendario gare", self.calendar_url))
        self.assertNotContains(page, "example.com")

    def test_weekend_page_keeps_the_origin_in_its_links(self):
        page = self.client.get(f"{self.weekend_url}?from=play")

        self.assertEqual(
            self._crumbs(page),
            [
                ("Smoke Cup 2026", self.championship_url),
                ("Prossimo weekend", self.play_url),
                ("R1 GP Regular", None),
            ],
        )
        self.assertContains(page, f'href="{self.choice_url}?from=play"')
        results_url = reverse(
            "regular_race_results",
            args=[self.championship.id, self.regular_weekend.id, self.regular_race.id],
        )
        self.assertContains(page, f'href="{results_url}?from=play"')


class SucateMagateTests(WeekendPagesFixture, TestCase):
    """#167: sucata = 5 punti o meno, magata = 43 punti o più (regolamento C.2, E.2)."""

    def _result(self, player, race, total_points):
        PlayerRaceResult.objects.create(
            player=player,
            race=race,
            credit_spent=0,
            fia_points=0,
            total_points=total_points,
        )

    def _stats(self):
        players = ChampionshipPlayer.objects.filter(
            championship=self.championship
        ).order_by("player_name")
        rows, _, _ = dashboard._season_standings_rows(self.championship, players)
        return {
            row["player"].player_name: (
                row["values"]["magate"],
                row["values"]["sucate"],
            )
            for row in rows
        }

    def test_thresholds_are_included(self):
        player = ChampionshipPlayer.objects.get(user=self.user)
        other = ChampionshipPlayer.objects.create(
            user=self.outsider,
            championship=self.championship,
            league=self.league,
            player_name="Altro",
        )
        sprint_weekend_race = Race.objects.get(
            weekend=self.sprint_weekend, type="regular"
        )

        self._result(player, self.regular_race, 43)  # magata
        self._result(player, self.sprint_race, 5)  # sucata, anche se sprint
        self._result(player, sprint_weekend_race, 6)  # né l'una né l'altra
        self._result(other, self.regular_race, 42.9)
        self._result(other, self.sprint_race, 5.1)

        self.assertEqual(self._stats(), {"Giocatore": ("1", "1"), "Altro": ("0", "0")})


@override_settings(STORAGES=TEST_STORAGES)
class WeekendTeamColourTests(WeekendPagesFixture, TestCase):
    """#82: colore ed etichetta del pilota vengono dalla scuderia del weekend
    (WeekendParticipant), non da quella di inizio stagione (Driver.team)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        # Nel weekend regular il pilota 2 corre per un'altra scuderia (come Lawson
        # in Red Bull in Olanda); nel weekend sprint torna nella sua.
        self.loan_team = Team.objects.create(
            name="Alfa Prestito",
            short_name="PRS",
            api_id="team-loan",
            nationality="IT",
        )
        self.moved = Driver.objects.get(api_id="drv-smoke-2")
        self.season_team = self.moved.team
        WeekendParticipant.objects.filter(
            weekend=self.regular_weekend, driver=self.moved
        ).update(team=self.loan_team)

    def _get(self, name, weekend, event):
        return self.client.get(
            reverse(name, args=[self.championship.id, weekend.id, event.id])
        )

    def test_race_results_use_the_team_of_that_weekend(self):
        regular = self._get(
            "regular_race_results", self.regular_weekend, self.regular_race
        )
        sprint = self._get("sprint_race_results", self.sprint_weekend, self.sprint_race)

        self.assertContains(regular, 'class="team-prs"')
        self.assertNotContains(sprint, "team-prs")

    def test_race_choice_uses_the_team_of_that_weekend(self):
        response = self._get(
            "regular_race_choice", self.regular_weekend, self.regular_race
        )

        self.assertContains(response, 'data-driver-team-slug="prs"')

    def test_qualifying_picker_groups_the_driver_under_the_weekend_team(self):
        response = self._get(
            "race_qualifying_choice", self.regular_weekend, self.regular_qualifying
        )

        html = response.content.decode()
        loan_group = html.split('team-group team-prs">', 1)[1].split("</section>")[0]
        self.assertIn("Smoke2", loan_group)
        self.assertNotIn("Smoke1", loan_group)

    def test_my_choices_use_the_team_of_each_weekend(self):
        player = ChampionshipPlayer.objects.get(user=self.user)
        for race in (self.regular_race, self.sprint_race):
            PlayerRaceChoice.objects.create(
                player=player, race=race, driver=self.moved, spent_amount=10
            )

        response = self.client.get(
            reverse("championship_my_choices", args=[self.championship.id])
        )

        self.assertContains(response, "team-chip team-prs", count=1)
        self.assertContains(response, "team-chip team-smk", count=1)

    def test_the_season_team_is_not_changed(self):
        self._get("regular_race_results", self.regular_weekend, self.regular_race)
        self._get(
            "race_qualifying_choice", self.regular_weekend, self.regular_qualifying
        )

        self.moved.refresh_from_db()
        self.assertEqual(self.moved.team, self.season_team)


@override_settings(STORAGES=TEST_STORAGES)
class GrandPrixResultsStateTests(WeekendPagesFixture, TestCase):
    """#191: i risultati del GP si aprono dal via, con la propria scelta e lo
    stato della gara finché i risultati non sono importati."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse(
            "regular_race_results",
            args=[self.championship.id, self.regular_weekend.id, self.regular_race.id],
        )
        player = ChampionshipPlayer.objects.get(user=self.user)
        PlayerRaceChoice.objects.create(
            player=player,
            race=self.regular_race,
            driver=Driver.objects.get(api_id="drv-smoke-1"),
            spent_amount=120,
            is_pupillo=True,
        )

    def _race_started(self, ago, *, with_results=False):
        self.regular_weekend.race_start = timezone.now() - ago
        self.regular_weekend.save()
        if not with_results:
            self.regular_race.entries.all().delete()

    def test_before_the_start_goes_back_to_the_weekend(self):
        self.regular_race.entries.all().delete()

        response = self.client.get(f"{self.url}?from=play")

        self.assertRedirects(
            response,
            reverse(
                "weekend_details",
                args=[self.championship.id, self.regular_weekend.id],
            )
            + "?from=play",
            fetch_redirect_response=False,
        )

    def test_during_the_race_shows_the_choice_and_race_in_progress(self):
        self._race_started(timedelta(hours=2, minutes=59))

        response = self.client.get(self.url)

        self.assertContains(response, "Gara in corso")
        self.assertContains(response, "La tua gara")
        self.assertContains(response, "Smoke1")
        self.assertContains(response, "★ Pupillo")
        self.assertNotContains(response, "Punti guadagnati")

    def test_after_three_hours_without_results_says_not_published(self):
        self._race_started(timedelta(hours=3, minutes=1))

        response = self.client.get(self.url)

        self.assertContains(response, "Risultati non ancora pubblicati")
        self.assertNotContains(response, "Gara in corso")
        self.assertContains(response, "Smoke1")

    def test_with_results_shows_the_classification(self):
        self._race_started(timedelta(hours=1), with_results=True)

        response = self.client.get(self.url)

        self.assertEqual(response.context["session_state"], "results")
        self.assertNotContains(response, "Gara in corso")
        self.assertContains(response, "Punti guadagnati")

    def test_non_players_see_only_the_race_state(self):
        self._race_started(timedelta(hours=1))
        self.client.force_login(self.outsider)

        response = self.client.get(self.url)

        self.assertContains(response, "Gara in corso")
        self.assertNotContains(response, "La tua gara")



@override_settings(STORAGES=TEST_STORAGES)
class GrandPrixChoiceAccessTests(WeekendPagesFixture, TestCase):
    """Scelta del GP: dopo il via porta ai risultati (#184), senza griglia
    rimanda al weekend (#189), ha il pulsante dei risultati della qualifica (#198)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        c, w = self.championship.id, self.regular_weekend.id
        self.url = reverse("regular_race_choice", args=[c, w, self.regular_race.id])
        self.results_url = reverse(
            "regular_race_results", args=[c, w, self.regular_race.id]
        )
        self.weekend_url = reverse("weekend_details", args=[c, w])
        self.qualifying_results_url = reverse(
            "race_qualifying_results", args=[c, w, self.regular_qualifying.id]
        )

    def _start_race(self):
        self.regular_weekend.race_start = timezone.now() - timedelta(minutes=5)
        self.regular_weekend.save()

    def test_after_the_start_goes_to_the_results(self):
        self._start_race()

        response = self.client.get(f"{self.url}?from=play")

        self.assertRedirects(
            response, f"{self.results_url}?from=play", fetch_redirect_response=False
        )

    def test_a_post_after_the_start_saves_nothing(self):
        self._start_race()
        drivers = [grid.driver_id for grid in self.regular_race.starting_grid.all()]

        response = self.client.post(
            self.url, {"drivers": drivers, "pupillo_driver_id": drivers[0]}
        )

        self.assertRedirects(response, self.results_url, fetch_redirect_response=False)
        self.assertFalse(self.regular_race.playerracechoice_set.exists())

    def test_without_the_grid_goes_back_to_the_weekend(self):
        self.regular_race.starting_grid.all().delete()

        response = self.client.get(self.url)

        self.assertRedirects(response, self.weekend_url, fetch_redirect_response=False)
        self.assertIn(
            "non è ancora disponibile",
            str(list(messages.get_messages(response.wsgi_request))[0]),
        )

    def test_links_to_the_qualifying_results(self):
        response = self.client.get(self.url)

        self.assertContains(response, f'href="{self.qualifying_results_url}"')

    def test_qualifying_results_button_is_greyed_out_without_results(self):
        self.regular_qualifying.qualifying_entries.all().delete()

        response = self.client.get(self.url)

        self.assertNotContains(response, f'href="{self.qualifying_results_url}"')
        self.assertContains(response, 'aria-disabled="true"')


@override_settings(STORAGES=TEST_STORAGES)
class SprintChoiceAccessTests(WeekendPagesFixture, TestCase):
    """Scelta della Sprint: dopo il via porta ai risultati (#185), senza griglia
    rimanda al weekend (#190)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        c, w = self.championship.id, self.sprint_weekend.id
        self.url = reverse("sprint_race_choice", args=[c, w, self.sprint_race.id])
        self.results_url = reverse(
            "sprint_race_results", args=[c, w, self.sprint_race.id]
        )
        self.weekend_url = reverse("weekend_details", args=[c, w])

    def _start_sprint(self):
        self.sprint_weekend.sprint_start = timezone.now() - timedelta(minutes=5)
        self.sprint_weekend.save()

    def test_opens_while_you_can_choose(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_after_the_start_goes_to_the_results(self):
        self._start_sprint()

        response = self.client.get(f"{self.url}?from=play")

        self.assertRedirects(
            response, f"{self.results_url}?from=play", fetch_redirect_response=False
        )

    def test_a_post_after_the_start_saves_nothing(self):
        self._start_sprint()
        driver = self.sprint_race.starting_grid.first().driver_id

        response = self.client.post(self.url, {"drivers": [driver]})

        self.assertRedirects(response, self.results_url, fetch_redirect_response=False)
        self.assertFalse(self.sprint_race.playerracechoice_set.exists())

    def test_without_the_grid_goes_back_to_the_weekend(self):
        self.sprint_race.starting_grid.all().delete()

        response = self.client.get(self.url)

        self.assertRedirects(response, self.weekend_url, fetch_redirect_response=False)


@override_settings(STORAGES=TEST_STORAGES)
class GrandPrixStartingGridTests(WeekendPagesFixture, TestCase):
    """#182: i piloti del GP si scelgono da una griglia di partenza, non da una tabella."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse(
            "regular_race_choice",
            args=[self.championship.id, self.regular_weekend.id, self.regular_race.id],
        )

    def test_drivers_follow_the_starting_grid_with_their_costs(self):
        response = self.client.get(self.url)

        html = response.content.decode()
        self.assertNotIn("<table", html)
        self.assertIn('class="start-grid"', html)
        self.assertLess(html.index("Smoke1"), html.index("Smoke2"))
        for option in response.context["driver_options"]:
            with self.subTest(position=option["grid_position"]):
                self.assertIn(f"P{option['grid_position']}</span>", html)
                self.assertIn(f"Griglia <strong>{option['grid_cost']}</strong>", html)
                self.assertIn(
                    f"Classifica <strong>{option['standings_cost']}</strong>", html
                )

    def test_every_slot_is_a_button_with_its_pupillo_star(self):
        response = self.client.get(self.url)

        self.assertContains(
            response, 'data-select-driver aria-pressed="false"', count=2
        )
        self.assertContains(response, "data-set-pupillo=", count=2)

    def test_drivers_beyond_the_budget_are_switched_off(self):
        player = ChampionshipPlayer.objects.get(user=self.user)
        player.available_credit = 0
        player.save()

        response = self.client.get(self.url)

        expensive = [o for o in response.context["driver_options"] if o["cost"] > 0]
        self.assertTrue(expensive)
        self.assertTrue(all(o["over_budget"] for o in expensive))
        self.assertContains(response, 'data-over-budget="true"')
        self.assertContains(response, "fuori budget")


@override_settings(STORAGES=TEST_STORAGES)
class SprintStartingGridTests(WeekendPagesFixture, TestCase):
    """#183: il pilota della Sprint si sceglie dalla griglia di partenza, con il
    solo costo e senza pupillo."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse(
            "sprint_race_choice",
            args=[self.championship.id, self.sprint_weekend.id, self.sprint_race.id],
        )

    def test_drivers_follow_the_starting_grid_with_one_cost(self):
        response = self.client.get(self.url)

        html = response.content.decode()
        self.assertNotIn("<table", html)
        self.assertIn('class="start-grid"', html)
        self.assertLess(html.index("Smoke1"), html.index("Smoke2"))
        self.assertNotIn("Classifica <strong>", html)
        self.assertIn("Scuderia Smoke", html)
        self.assertContains(
            response, 'data-select-driver aria-pressed="false"', count=2
        )
        self.assertNotContains(response, "data-set-pupillo=")

    def test_the_sprint_qualifying_discount_reaches_the_summary(self):
        response = self.client.get(self.url)

        discount = response.context["sprint_qualifying_bonus"]["credit_discount"]
        self.assertContains(
            response, f'data-qualifying-bonus-credit-discount="{discount}"'
        )

    def test_drivers_beyond_the_budget_are_switched_off(self):
        player = ChampionshipPlayer.objects.get(user=self.user)
        player.available_credit = 0
        player.save()

        response = self.client.get(self.url)

        expensive = [o for o in response.context["driver_options"] if o["cost"] > 0]
        self.assertTrue(expensive)
        self.assertTrue(all(o["over_budget"] for o in expensive))
        self.assertContains(response, "fuori budget")


@override_settings(STORAGES=TEST_STORAGES)
class NextWeekendClickableNamesTests(WeekendPagesFixture, TestCase):
    """#102: in Prossimo weekend i weekend si aprono cliccando il nome, senza
    i pulsanti «Dettaglio weekend →» e «Apri →»."""

    def test_weekend_names_open_the_weekend(self):
        self.client.force_login(self.user)
        c = self.championship.id

        response = self.client.get(reverse("championship_next_weekend", args=[c]))

        for weekend in (self.regular_weekend, self.sprint_weekend):
            url = reverse("weekend_details", args=[c, weekend.id])
            self.assertContains(response, f'href="{url}?from=play"')
        self.assertNotContains(response, "Dettaglio weekend")
        self.assertNotContains(response, "Apri →")


@override_settings(STORAGES=TEST_STORAGES)
class SaturdayQualifyingChoiceAccessTests(WeekendPagesFixture, TestCase):
    """#186: dopo il via la scelta della qualifica del sabato porta ai risultati."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        c, w, q = (
            self.championship.id,
            self.regular_weekend.id,
            self.regular_qualifying.id,
        )
        self.url = reverse("race_qualifying_choice", args=[c, w, q])
        self.results_url = reverse("race_qualifying_results", args=[c, w, q])

    def _start(self):
        self.regular_weekend.qualifying_start = timezone.now() - timedelta(minutes=5)
        self.regular_weekend.save()

    def test_opens_before_the_start(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_after_the_start_goes_to_the_results(self):
        self._start()

        response = self.client.get(f"{self.url}?from=play")

        self.assertRedirects(
            response, f"{self.results_url}?from=play", fetch_redirect_response=False
        )

    def test_a_post_after_the_start_saves_nothing(self):
        self._start()
        driver = Driver.objects.get(api_id="drv-smoke-1")

        response = self.client.post(self.url, {"driver": driver.id})

        self.assertRedirects(response, self.results_url, fetch_redirect_response=False)
        self.assertFalse(PlayerQualifyingChoice.objects.exists())


@override_settings(STORAGES=TEST_STORAGES)
class SprintWeekendQualifyingChoiceAccessTests(WeekendPagesFixture, TestCase):
    """#187: dopo il via la qualifica a slot dei weekend sprint porta ai risultati;
    #200: pulsante «Risultati Sprint», la Sprint è già corsa."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        c, w, q = (
            self.championship.id,
            self.sprint_weekend.id,
            self.sprint_weekend_qualifying.id,
        )
        self.url = reverse("race_qualifying_multi_choice", args=[c, w, q])
        self.results_url = reverse("race_qualifying_results", args=[c, w, q])
        self.sprint_results_url = reverse(
            "sprint_race_results", args=[c, w, self.sprint_race.id]
        )

    def _start(self):
        self.sprint_weekend.qualifying_start = timezone.now() - timedelta(minutes=5)
        self.sprint_weekend.save()

    def test_after_the_start_goes_to_the_results(self):
        self._start()

        response = self.client.get(f"{self.url}?from=play")

        self.assertRedirects(
            response, f"{self.results_url}?from=play", fetch_redirect_response=False
        )

    def test_a_post_after_the_start_saves_nothing(self):
        self._start()
        driver = Driver.objects.get(api_id="drv-smoke-1")

        response = self.client.post(self.url, {"drivers_q1_pass": [driver.id]})

        self.assertRedirects(response, self.results_url, fetch_redirect_response=False)
        self.assertFalse(PlayerQualifyingMultiChoice.objects.exists())

    def test_links_to_the_sprint_results(self):
        response = self.client.get(self.url)

        self.assertContains(response, f'href="{self.sprint_results_url}"')

    def test_sprint_results_button_is_greyed_out_without_results(self):
        self.sprint_race.entries.all().delete()

        response = self.client.get(self.url)

        self.assertNotContains(response, f'href="{self.sprint_results_url}"')
        self.assertContains(response, 'aria-disabled="true"')


@override_settings(STORAGES=TEST_STORAGES)
class NextWeekendSessionsTests(WeekendPagesFixture, TestCase):
    """Prossimo weekend: pulsanti secondo lo stato della sessione (#193) e quanti
    giocatori hanno già scelto (#201)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        c, w = self.championship.id, self.regular_weekend.id
        self.url = reverse("championship_next_weekend", args=[c])
        self.race_choice_url = reverse(
            "regular_race_choice", args=[c, w, self.regular_race.id]
        )
        self.qualifying_results_url = reverse(
            "race_qualifying_results", args=[c, w, self.regular_qualifying.id]
        )

    def _player(self, username, league):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.com", password="pw123456!"
        )
        return ChampionshipPlayer.objects.create(
            user=user,
            championship=self.championship,
            league=league,
            player_name=username,
        )

    def test_open_sessions_lead_to_the_choice(self):
        response = self.client.get(self.url)

        self.assertContains(response, f'href="{self.race_choice_url}?from=play"')

    def test_without_the_grid_the_choice_is_switched_off(self):
        self.regular_race.starting_grid.all().delete()

        response = self.client.get(self.url)

        self.assertNotContains(response, f'href="{self.race_choice_url}?from=play"')
        self.assertContains(response, "griglia non ancora disponibile")
        self.assertContains(response, 'aria-disabled="true"')

    def test_started_sessions_lead_to_the_results(self):
        self.regular_weekend.qualifying_start = timezone.now() - timedelta(hours=1)
        self.regular_weekend.save()

        response = self.client.get(self.url)

        self.assertContains(response, f'href="{self.qualifying_results_url}?from=play"')
        self.assertContains(response, "Scelte chiuse")
        # La gara del weekend è ancora da scegliere.
        self.assertContains(response, f'href="{self.race_choice_url}?from=play"')

    def test_counts_who_has_chosen_in_the_league_and_in_the_championship(self):
        other_league = League.objects.create(championship=self.championship, name="B")
        teammate = self._player("compagno", self.league)
        rival = self._player("rivale", other_league)
        driver = Driver.objects.get(api_id="drv-smoke-1")
        for player in (teammate, rival):
            PlayerRaceChoice.objects.create(
                player=player, race=self.regular_race, driver=driver, spent_amount=10
            )

        response = self.client.get(self.url)

        gp = next(
            s
            for s in response.context["next_weekend"]["all_sessions"]
            if s["label"] == "Gran Premio"
        )
        self.assertEqual((gp["chosen_league"], gp["chosen_total"]), (1, 2))
        self.assertEqual(
            response.context["choice_counts"], {"league_size": 2, "total": 3}
        )
        self.assertContains(
            response, '<strong class="text-ink">1/2</strong> nella tua lega'
        )
        self.assertContains(response, "2/3 nel campionato")
        # Solo numeri: nessun nome di chi ha scelto.
        self.assertNotContains(response, "rivale")

    def test_queries_do_not_grow_with_the_players(self):
        with CaptureQueriesContext(connection) as few:
            self.client.get(self.url)
        for n in range(3):
            self._player(f"extra{n}", self.league)
        with CaptureQueriesContext(connection) as many:
            self.client.get(self.url)

        self.assertEqual(len(few.captured_queries), len(many.captured_queries))

    def _weekend_with_sprint_qualifying_without_time(self, race_start):
        # Come R7 nel calendario di sviluppo (#242): weekend regular con una
        # Sprint Qualifying che non ha orario.
        weekend = Weekend.objects.create(
            circuit=self.regular_weekend.circuit,
            event_name="GP Senza Orario",
            round_number=0,
            season=2026,
            weekend_type="regular",
            qualifying_start=race_start and race_start - timedelta(days=1),
            race_start=race_start,
        )
        Qualifying.objects.create(weekend=weekend, type="sprint")
        Qualifying.objects.create(weekend=weekend, type="regular")
        Race.objects.create(weekend=weekend, type="regular")
        return weekend

    def test_a_session_without_time_does_not_keep_a_past_weekend_open(self):
        past = self._weekend_with_sprint_qualifying_without_time(
            timezone.now() - timedelta(days=30)
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.context["next_weekend"]["weekend"], self.regular_weekend
        )
        self.assertNotIn(
            past, [w["weekend"] for w in response.context["open_weekends"]]
        )

    def test_without_the_gp_time_the_weekend_stays_open(self):
        # Calendario non ancora completo: il weekend resta da giocare.
        undated = self._weekend_with_sprint_qualifying_without_time(None)

        response = self.client.get(self.url)

        self.assertEqual(response.context["next_weekend"]["weekend"], undated)


@override_settings(STORAGES=TEST_STORAGES)
class SaturdayQualifyingResultsTests(WeekendPagesFixture, TestCase):
    """#195: risultati della qualifica del sabato, con il proprio pronostico."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse(
            "race_qualifying_results",
            args=[
                self.championship.id,
                self.regular_weekend.id,
                self.regular_qualifying.id,
            ],
        )

    def _pick(self, api_id="drv-smoke-1"):
        PlayerQualifyingChoice.objects.create(
            player=ChampionshipPlayer.objects.get(user=self.user),
            qualifying=self.regular_qualifying,
            driver=Driver.objects.get(api_id=api_id),
        )

    def _started(self, ago):
        self.regular_qualifying.qualifying_entries.all().delete()
        self.regular_weekend.qualifying_start = timezone.now() - ago
        self.regular_weekend.save()

    def test_shows_classification_and_the_pick(self):
        self._pick()

        response = self.client.get(self.url)

        self.assertContains(response, "1:21.123")
        pick = response.context["pick"]
        rule = bonuses.get_regular_qualifying_bonus_rule(1)
        self.assertEqual(pick["position"], 1)
        self.assertEqual(pick["qualifying_points"], rule["qualifying_points"])
        # Sconto e moltiplicatore seguono la griglia del GP (P1 nel fixture).
        self.assertEqual(pick["grid_position"], 1)
        self.assertEqual(pick["credit_change"], rule["credit_change"])
        self.assertContains(response, "Punti qualifica")
        self.assertContains(response, "Griglia del Gran Premio")

    def test_without_a_pick_says_so(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Nessuna scelta per questa qualifica.")

    def test_during_the_session_says_qualifying_in_progress(self):
        self._pick()
        self._started(timedelta(hours=1, minutes=59))

        response = self.client.get(self.url)

        self.assertContains(response, "Qualifica in corso")
        self.assertContains(response, "Smoke1")
        self.assertNotContains(response, "Punti qualifica")

    def test_after_two_hours_without_results_says_not_published(self):
        self._started(timedelta(hours=2, minutes=1))

        response = self.client.get(self.url)

        self.assertContains(response, "Risultati non ancora pubblicati")

    def test_before_the_start_goes_back_to_the_weekend(self):
        self.regular_qualifying.qualifying_entries.all().delete()

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse(
                "weekend_details",
                args=[self.championship.id, self.regular_weekend.id],
            ),
            fetch_redirect_response=False,
        )

    def test_non_players_see_only_the_classification(self):
        self.client.force_login(self.outsider)

        response = self.client.get(self.url)

        self.assertContains(response, "1:21.123")
        self.assertNotContains(response, "Il tuo pronostico")


@override_settings(STORAGES=TEST_STORAGES)
class SprintWeekendQualifyingResultsTests(WeekendPagesFixture, TestCase):
    """#196: qualifica a slot dei weekend sprint. Livelli a cascata sulla
    classifica (punti qualifica) e sulla griglia del GP (sconto e moltiplicatore)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse(
            "race_qualifying_results",
            args=[
                self.championship.id,
                self.sprint_weekend.id,
                self.sprint_weekend_qualifying.id,
            ],
        )
        team = Team.objects.create(
            name="Scuderia Slot", short_name="SLT", api_id="team-slot", nationality="IT"
        )
        drivers = [
            Driver.objects.create(
                first_name=f"Slot{n}",
                last_name=f"Pilota{n:02d}",
                number=40 + n,
                short_name=f"S{n:02d}",
                team=team,
                season=2026,
                api_id=f"drv-slot-{n}",
            )
            for n in range(1, 15)
        ]
        q1, q2, q3 = drivers[:6], drivers[6:11], drivers[11:]
        player = ChampionshipPlayer.objects.get(user=self.user)
        lap = timedelta(minutes=1, seconds=20)
        for position, driver in enumerate(drivers, start=1):
            # In classifica tutti i pronostici di Q1 e Q2 passano il Q1 (tempo in
            # Q2), nessuno passa il Q2 (niente tempo in Q3): livello Q1.
            QualifyingResult.objects.create(
                qualifying=self.sprint_weekend_qualifying,
                driver=driver,
                position=position,
                q1_time=lap,
                q2_time=lap if driver in q1 + q2 else None,
            )
        for slot, slot_drivers in (("q1_pass", q1), ("q2_pass", q2), ("q3_top3", q3)):
            for driver in slot_drivers:
                PlayerQualifyingMultiChoice.objects.create(
                    player=player,
                    qualifying=self.sprint_weekend_qualifying,
                    driver=driver,
                    selection_slot=slot,
                )
        # Sulla griglia del GP i Q2 partono nei primi 10 e i Q1 entro il 16°,
        # ma la top 3 è sbagliata: livello Q2.
        gp = Race.objects.get(weekend=self.sprint_weekend, type="regular")
        grid_order = q2 + q1 + q3
        for position, driver in enumerate(grid_order, start=1):
            RaceStartingGrid.objects.create(race=gp, driver=driver, position=position)

    def test_levels_follow_the_classification_and_the_grid(self):
        response = self.client.get(self.url)

        pick = response.context["pick"]
        self.assertEqual(
            pick["qualifying_ticks"], [("Q1", True), ("Q2", False), ("Top 3", False)]
        )
        q1_rule = bonuses.get_qualifying_multichoice_bonus_rule("q1_pass")
        self.assertEqual(pick["qualifying_points"], q1_rule["qualifying_points"])
        self.assertEqual(
            pick["grid_ticks"], [("Q1", True), ("Q2", True), ("Top 3", False)]
        )
        rule = bonuses.get_qualifying_multichoice_bonus_rule("q2_pass")
        self.assertEqual(pick["credit_discount"], rule["credit_discount"])
        self.assertEqual(pick["points_multiplier"], rule["points_multiplier"])
        self.assertContains(response, "Passano il Q1")
        self.assertContains(response, "Pilota01")
        self.assertContains(response, "In qualifica")

    def test_without_the_grid_the_gp_bonus_waits(self):
        RaceStartingGrid.objects.filter(race__weekend=self.sprint_weekend).delete()

        response = self.client.get(self.url)

        self.assertFalse(response.context["pick"]["grid_available"])
        self.assertContains(response, "si conoscono con la griglia di partenza")

    def test_without_a_pick_says_so(self):
        PlayerQualifyingMultiChoice.objects.all().delete()

        response = self.client.get(self.url)

        self.assertContains(response, "Nessuna scelta per questa qualifica.")


@override_settings(STORAGES=TEST_STORAGES)
class GrandPrixResultsStartingGridTests(WeekendPagesFixture, TestCase):
    """#233: nei risultati del GP la griglia di partenza in sola lettura, in una
    seconda scheda con i risultati, da sola durante la gara."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse(
            "regular_race_results",
            args=[self.championship.id, self.regular_weekend.id, self.regular_race.id],
        )
        self.pupillo = Driver.objects.get(api_id="drv-smoke-2")
        PlayerRaceChoice.objects.create(
            player=ChampionshipPlayer.objects.get(user=self.user),
            race=self.regular_race,
            driver=self.pupillo,
            spent_amount=50,
            is_pupillo=True,
        )

    def test_with_results_the_grid_is_the_second_tab(self):
        response = self.client.get(self.url)

        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, 'href="#arrivo"')
        self.assertContains(response, 'href="#griglia"')
        self.assertEqual(
            [o["grid_position"] for o in response.context["start_grid"]], [1, 2]
        )

    def test_the_grid_is_read_only_and_shows_the_picks(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, "data-select-driver")
        self.assertContains(response, " is-selected", count=1)
        self.assertContains(
            response, '<span class="grid-pupillo is-pupillo">★ Pupillo</span>'
        )

    def test_during_the_race_only_the_grid_is_shown(self):
        self.regular_race.entries.all().delete()
        self.regular_weekend.race_start = timezone.now() - timedelta(hours=1)
        self.regular_weekend.save()

        response = self.client.get(self.url)

        self.assertContains(response, "Gara in corso")
        self.assertContains(response, 'class="start-grid"')
        self.assertNotContains(response, 'role="tablist"')



@override_settings(STORAGES=TEST_STORAGES)
class SprintResultsStartingGridTests(WeekendPagesFixture, TestCase):
    """#234: come il GP (#233), con il solo costo e senza pupillo."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse(
            "sprint_race_results",
            args=[self.championship.id, self.sprint_weekend.id, self.sprint_race.id],
        )
        PlayerRaceChoice.objects.create(
            player=ChampionshipPlayer.objects.get(user=self.user),
            race=self.sprint_race,
            driver=Driver.objects.get(api_id="drv-smoke-1"),
            spent_amount=30,
        )

    def test_with_results_the_grid_is_the_second_tab(self):
        response = self.client.get(self.url)

        self.assertContains(response, 'href="#griglia"')
        self.assertEqual(
            [o["grid_position"] for o in response.context["start_grid"]], [1, 2]
        )
        self.assertContains(response, " is-selected", count=1)
        self.assertNotContains(response, "Classifica <strong>")
        self.assertNotContains(response, "grid-pupillo")

    def test_during_the_sprint_only_the_grid_is_shown(self):
        self.sprint_race.entries.all().delete()
        self.sprint_weekend.sprint_start = timezone.now() - timedelta(hours=1)
        self.sprint_weekend.save()

        response = self.client.get(self.url)

        self.assertContains(response, "Gara in corso")
        self.assertContains(response, 'class="start-grid"')
        self.assertNotContains(response, 'role="tablist"')


@override_settings(STORAGES=TEST_STORAGES)
class SprintResultsStateTests(WeekendPagesFixture, TestCase):
    """#192: come il GP (#191), ma la Sprint resta «in corso» per 2 ore."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse(
            "sprint_race_results",
            args=[self.championship.id, self.sprint_weekend.id, self.sprint_race.id],
        )
        PlayerRaceChoice.objects.create(
            player=ChampionshipPlayer.objects.get(user=self.user),
            race=self.sprint_race,
            driver=Driver.objects.get(api_id="drv-smoke-2"),
            spent_amount=60,
        )

    def _sprint_started(self, ago, *, with_results=False):
        self.sprint_weekend.sprint_start = timezone.now() - ago
        self.sprint_weekend.save()
        if not with_results:
            self.sprint_race.entries.all().delete()

    def test_before_the_start_goes_back_to_the_weekend(self):
        self.sprint_race.entries.all().delete()

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse(
                "weekend_details", args=[self.championship.id, self.sprint_weekend.id]
            ),
            fetch_redirect_response=False,
        )

    def test_during_the_sprint_shows_the_choice_and_race_in_progress(self):
        self._sprint_started(timedelta(hours=1, minutes=59))

        response = self.client.get(self.url)

        self.assertContains(response, "Gara in corso")
        self.assertContains(response, "Smoke2")
        self.assertNotContains(response, "Punti guadagnati")

    def test_after_two_hours_without_results_says_not_published(self):
        self._sprint_started(timedelta(hours=2, minutes=1))

        response = self.client.get(self.url)

        self.assertContains(response, "Risultati non ancora pubblicati")
        self.assertNotContains(response, "Gara in corso")

    def test_with_results_shows_the_classification(self):
        self._sprint_started(timedelta(hours=1), with_results=True)

        response = self.client.get(self.url)

        self.assertEqual(response.context["session_state"], "results")
        self.assertContains(response, "Punti guadagnati")


@override_settings(STORAGES=TEST_STORAGES)
class WeekendDetailSessionsTests(WeekendPagesFixture, TestCase):
    """#61: pagina del weekend con orario, stato della scelta e un solo pulsante
    per sessione, secondo lo stato, come Prossimo weekend (#193)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        c = self.championship.id
        rw, sw = self.regular_weekend.id, self.sprint_weekend.id
        self.url = reverse("weekend_details", args=[c, rw])
        self.sprint_url = reverse("weekend_details", args=[c, sw])
        self.race_choice_url = reverse(
            "regular_race_choice", args=[c, rw, self.regular_race.id]
        )
        self.qualifying_choice_url = reverse(
            "race_qualifying_choice", args=[c, rw, self.regular_qualifying.id]
        )
        self.qualifying_results_url = reverse(
            "race_qualifying_results", args=[c, rw, self.regular_qualifying.id]
        )

    def _start_qualifying(self):
        self.regular_weekend.qualifying_start = timezone.now() - timedelta(hours=1)
        self.regular_weekend.save()

    def test_open_sessions_lead_to_the_choice(self):
        response = self.client.get(self.url)

        self.assertContains(response, f'href="{self.race_choice_url}"')
        self.assertContains(response, "Da scegliere")

    def test_a_saved_choice_can_be_changed(self):
        PlayerRaceChoice.objects.create(
            player=ChampionshipPlayer.objects.get(user=self.user),
            race=self.regular_race,
            driver=Driver.objects.get(api_id="drv-smoke-1"),
            spent_amount=10,
        )

        response = self.client.get(self.url)

        self.assertContains(response, "✓ Scelta effettuata")
        self.assertContains(response, "Modifica")

    def test_without_the_grid_the_choice_is_switched_off(self):
        self.regular_race.starting_grid.all().delete()

        response = self.client.get(self.url)

        self.assertNotContains(response, f'href="{self.race_choice_url}"')
        self.assertContains(response, "griglia non ancora disponibile")
        self.assertContains(response, 'aria-disabled="true"')

    def test_started_sessions_lead_to_the_results(self):
        self._start_qualifying()

        response = self.client.get(self.url)

        self.assertContains(response, f'href="{self.qualifying_results_url}"')
        self.assertNotContains(response, f'href="{self.qualifying_choice_url}"')
        self.assertContains(response, "Scelte chiuse")
        # Il GP del weekend è ancora da scegliere.
        self.assertContains(response, f'href="{self.race_choice_url}"')

    def test_non_players_see_the_results_but_not_the_choices(self):
        self._start_qualifying()
        self.client.force_login(self.outsider)

        response = self.client.get(self.url)

        self.assertContains(response, f'href="{self.qualifying_results_url}"')
        self.assertNotContains(response, "Scegli")
        self.assertNotContains(response, "Scelte chiuse")

    def test_links_keep_the_way_back_to_next_weekend(self):
        self._start_qualifying()

        response = self.client.get(f"{self.url}?from=play")

        self.assertContains(response, f'href="{self.qualifying_results_url}?from=play"')
        self.assertContains(response, f'href="{self.race_choice_url}?from=play"')

    def test_queries_do_not_grow_with_the_sessions(self):
        # Il weekend regular ha 2 sessioni, quello sprint 4.
        with CaptureQueriesContext(connection) as regular:
            self.client.get(self.url)
        with CaptureQueriesContext(connection) as sprint:
            self.client.get(self.sprint_url)

        self.assertEqual(len(regular.captured_queries), len(sprint.captured_queries))


@override_settings(STORAGES=TEST_STORAGES)
class DynamicTextsTests(WeekendPagesFixture, TestCase):
    """#101: i testi con un numero si scrivono per intero al singolare e al
    plurale, verificati con 0, 1 e 2 o più elementi."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.player = ChampionshipPlayer.objects.get(user=self.user)
        self.drivers = list(Driver.objects.filter(api_id__startswith="drv-smoke"))

    def _other_player(self, championship, username="secondo"):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.com", password="pw123456!"
        )
        return ChampionshipPlayer.objects.create(
            user=user,
            championship=championship,
            league=championship.leagues.first(),
            player_name=username,
        )

    def _choose_all_but_the_sprint_weekend_gp(self):
        d1, d2 = self.drivers
        for driver in (d1, d2):
            PlayerRaceChoice.objects.create(
                player=self.player,
                race=self.regular_race,
                driver=driver,
                spent_amount=10,
            )
        PlayerQualifyingChoice.objects.create(
            player=self.player, qualifying=self.regular_qualifying, driver=d1
        )
        PlayerSprintQualifyingChoice.objects.create(
            player=self.player,
            qualifying=self.sprint_qualifying,
            driver=d1,
            selection_slot="sq1",
        )
        PlayerRaceChoice.objects.create(
            player=self.player, race=self.sprint_race, driver=d1, spent_amount=10
        )
        PlayerQualifyingMultiChoice.objects.create(
            player=self.player,
            qualifying=self.sprint_weekend_qualifying,
            driver=d1,
            selection_slot="q1_pass",
        )

    def test_next_weekend_choices_to_make(self):
        url = reverse("championship_next_weekend", args=[self.championship.id])

        page = self.client.get(url)
        self.assertContains(page, "2 scelte da fare")
        self.assertContains(page, "6 scelte aperte in tutto")

        PlayerQualifyingChoice.objects.create(
            player=self.player,
            qualifying=self.regular_qualifying,
            driver=self.drivers[0],
        )
        page = self.client.get(url)
        self.assertContains(page, "1 scelta da fare")
        self.assertContains(page, "5 scelte aperte in tutto")

    def test_one_choice_left_in_the_other_weekends(self):
        self._choose_all_but_the_sprint_weekend_gp()

        page = self.client.get(
            reverse("championship_next_weekend", args=[self.championship.id])
        )

        self.assertContains(page, "1 scelta aperta in tutto")
        self.assertNotContains(page, "scelte da fare")

    def test_players_in_the_standings(self):
        url = reverse("championship_general_standings", args=[self.championship.id])

        self.assertContains(self.client.get(url), "1 giocatore<")
        self._other_player(self.championship)
        self.assertContains(self.client.get(url), "2 giocatori<")

    def test_players_on_the_join_page(self):
        url = reverse("join_championship", args=[self.open_championship.id])

        self.assertContains(self.client.get(url), "0 giocatori")
        self._other_player(self.open_championship)
        page = self.client.get(url)
        self.assertContains(page, "1 giocatore")
        self.assertNotContains(page, "1 giocatori")
        self.assertContains(page, "Iscrizione al campionato")

    def test_weekends_not_played(self):
        past = timezone.now() - timedelta(days=1)
        for weekend in (self.regular_weekend, self.sprint_weekend):
            for field in (
                "sprint_qualifying_start",
                "sprint_start",
                "qualifying_start",
                "race_start",
            ):
                if getattr(weekend, field):
                    setattr(weekend, field, past)
            weekend.save()
        url = reverse("championship_my_choices", args=[self.championship.id])

        self.assertContains(self.client.get(url), "2 weekend non giocati")
        PlayerRaceChoice.objects.create(
            player=self.player,
            race=self.regular_race,
            driver=self.drivers[0],
            spent_amount=10,
        )
        self.assertContains(self.client.get(url), "1 weekend non giocato")

    def test_season_legend_races(self):
        def description(term, total, remaining):
            legend = dashboard._season_standings_legend(total, remaining)
            return next(item["description"] for item in legend if item["term"] == term)

        self.assertIn("le 2 gare ancora", description("Budget/gara", 24, 2))
        self.assertIn("l'unica gara ancora", description("Budget/gara", 24, 1))
        self.assertIn("Non disponibile", description("Budget/gara", 24, 0))
        self.assertIn("alle 24 gare", description("Proiezione", 24, 0))
        self.assertIn("all'unica gara", description("Proiezione", 1, 0))

    def test_pupillo_streak(self):
        def title(streak):
            option = SimpleNamespace(
                driver=self.drivers[0],
                previous_pupillo_streak=streak,
                over_budget=False,
                grid_position=1,
                cost=10,
            )
            return render_to_string(
                "fantaApp/_start_grid.html",
                {"driver_options": [option], "with_pupillo": True},
            )

        self.assertIn('title="Pupillo nella gara precedente"', title(1))
        self.assertIn('title="Pupillo da 3 gare consecutive"', title(3))
        self.assertNotIn('title="Pupillo', title(0))

    def test_my_choices_slot_names_in_italian(self):
        self._choose_all_but_the_sprint_weekend_gp()

        page = self.client.get(
            reverse("championship_my_choices", args=[self.championship.id])
        )

        self.assertContains(page, "SQ1 – eliminato")
        self.assertContains(page, "Passano il Q1")
        self.assertNotContains(page, "Out in SQ1")
        self.assertNotContains(page, "Pass Q1")


@override_settings(STORAGES=TEST_STORAGES)
class ManagerPendingPicksTests(WeekendPagesFixture, TestCase):
    """#71: in Gestione → Giocatori il manager vede chi deve ancora fare le
    scelte del prossimo weekend, sessione per sessione."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)  # manager e giocatore nel fixture
        self.url = reverse("championship_manage_players", args=[self.championship.id])
        self.player = ChampionshipPlayer.objects.get(user=self.user)
        self.driver = Driver.objects.get(api_id="drv-smoke-1")

    def _player(self, username):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.com", password="pw123456!"
        )
        return ChampionshipPlayer.objects.create(
            user=user,
            championship=self.championship,
            league=self.league,
            player_name=username,
        )

    def _choose_gp(self, player):
        PlayerRaceChoice.objects.create(
            player=player, race=self.regular_race, driver=self.driver, spent_amount=10
        )

    def _choose_qualifying(self, player):
        PlayerQualifyingChoice.objects.create(
            player=player, qualifying=self.regular_qualifying, driver=self.driver
        )

    def _rows(self, response):
        return {
            row["player"].player_name: row["cells"]
            for row in response.context["board"]["rows"]
        }

    def test_shows_who_still_has_to_choose(self):
        self._choose_gp(self._player("secondo"))

        response = self.client.get(self.url)

        board = response.context["board"]
        self.assertEqual(board["weekend"], self.regular_weekend)
        self.assertEqual(
            [s["label"] for s in board["sessions"]], ["Qualifiche", "Gran Premio"]
        )
        self.assertEqual(
            self._rows(response),
            {"Giocatore": [False, False], "secondo": [False, True]},
        )
        self.assertContains(response, "2 giocatori devono ancora scegliere")

    def test_who_has_chosen_everything_goes_last(self):
        done = self._player("aaa")
        self._choose_gp(done)
        self._choose_qualifying(done)

        response = self.client.get(self.url)

        names = [row["player"].player_name for row in response.context["board"]["rows"]]
        self.assertEqual(names, ["Giocatore", "aaa"])
        self.assertContains(response, "1 giocatore deve ancora scegliere")

    def test_everyone_up_to_date(self):
        self._choose_gp(self.player)
        self._choose_qualifying(self.player)

        response = self.client.get(self.url)

        self.assertContains(response, "Tutti in pari")

    def test_started_sessions_are_left_out(self):
        self.regular_weekend.qualifying_start = timezone.now() - timedelta(hours=1)
        self.regular_weekend.save()

        response = self.client.get(self.url)

        self.assertEqual(
            [s["label"] for s in response.context["board"]["sessions"]],
            ["Gran Premio"],
        )

    def test_a_race_without_grid_is_marked(self):
        self.regular_race.starting_grid.all().delete()

        self.assertContains(self.client.get(self.url), "senza griglia")

    def test_queries_do_not_grow_with_the_players(self):
        with CaptureQueriesContext(connection) as few:
            self.client.get(self.url)
        for n in range(3):
            self._choose_gp(self._player(f"extra{n}"))
        with CaptureQueriesContext(connection) as many:
            self.client.get(self.url)

        self.assertEqual(len(few.captured_queries), len(many.captured_queries))


@override_settings(STORAGES=TEST_STORAGES)
class UserDashboardTests(TestCase):
    """#62: i campionati gestiti li prepara la view, senza schede doppie e con un
    numero di query che non cresce con i campionati."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="manager", email="manager@example.com", password="password123"
        )
        self.client.force_login(self.user)

    def _championship(self, name, *, plays, manages, leagues=1, others=0, active=True):
        championship = Championship.objects.create(name=name, year=2026, active=active)
        league_objs = [
            League.objects.create(championship=championship, name=f"Lega {n}")
            for n in range(leagues)
        ]
        if plays:
            ChampionshipPlayer.objects.create(
                user=self.user,
                championship=championship,
                league=league_objs[0],
                player_name="Io",
            )
        if manages:
            ChampionshipManager.objects.create(
                user=self.user, championship=championship
            )
        for n in range(others):
            other = get_user_model().objects.create_user(
                username=f"{name}-g{n}",
                email=f"{name}-g{n}@example.com",
                password="password123",
            )
            ChampionshipPlayer.objects.create(
                user=other,
                championship=championship,
                league=league_objs[n % leagues],
                player_name=f"Giocatore {n}",
            )
        return championship

    def test_played_and_managed_championship_is_one_card_with_the_badge(self):
        self._championship("Doppio", plays=True, manages=True)
        self._championship("Solo gioco", plays=True, manages=False)
        managed_only = self._championship("Solo gestione", plays=False, manages=True)

        response = self.client.get(reverse("user_dashboard"))

        self.assertContains(response, "Doppio", count=1)
        badges = {
            e.championship.name: e.is_manager for e in response.context["championship"]
        }
        self.assertEqual(badges, {"Doppio": True, "Solo gioco": False})
        self.assertEqual(
            list(response.context["managed_championships"]), [managed_only]
        )

    def test_managed_cards_count_leagues_and_players_in_full_words(self):
        self._championship("Una lega", plays=False, manages=True, leagues=1, others=1)
        self._championship("Due leghe", plays=False, manages=True, leagues=2, others=3)

        response = self.client.get(reverse("user_dashboard"))

        html = " ".join(response.content.decode().split())
        self.assertIn('<strong class="text-ink">1</strong> lega', html)
        self.assertIn('<strong class="text-ink">1</strong> giocatore', html)
        self.assertIn('<strong class="text-ink">2</strong> leghe', html)
        self.assertIn('<strong class="text-ink">3</strong> giocatori', html)
        self.assertNotIn("legha", html)

    def test_number_of_queries_does_not_grow_with_the_championships(self):
        self._championship("A", plays=True, manages=True)
        self._championship("B", plays=False, manages=True, others=1)
        with CaptureQueriesContext(connection) as few:
            self.client.get(reverse("user_dashboard"))

        for n in range(4):
            self._championship(f"Gioco {n}", plays=True, manages=n % 2 == 0)
            self._championship(f"Gestione {n}", plays=False, manages=True, others=2)
        with CaptureQueriesContext(connection) as many:
            self.client.get(reverse("user_dashboard"))

        self.assertEqual(len(many), len(few))


@override_settings(STORAGES=TEST_STORAGES)
class ErrorPagesTests(TestCase):
    """#68: pagine d'errore con lo stile del sito. Nei test DEBUG è False, come
    in produzione, quindi Django usa 404.html e 500.html."""

    def test_unknown_address_shows_the_404_page(self):
        response = self.client.get("/pagina-che-non-esiste/")

        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Pagina non trovata", status_code=404)
        self.assertContains(response, f'href="{reverse("home")}"', status_code=404)
        self.assertNotContains(response, "I miei campionati", status_code=404)

    def test_logged_in_users_can_go_back_to_their_championships(self):
        user = get_user_model().objects.create_user(
            username="perso", email="perso@example.com", password="pw123456!"
        )
        self.client.force_login(user)

        # Anche i 404 delle view (get_object_or_404) usano la stessa pagina.
        response = self.client.get(reverse("championship_dashboard", args=[999]))

        self.assertContains(response, "Pagina non trovata", status_code=404)
        self.assertContains(
            response, f'href="{reverse("user_dashboard")}"', status_code=404
        )

    def test_server_error_shows_the_500_page(self):
        self.client.raise_request_exception = False

        with patch("fantaApp.views.site.home.render", side_effect=RuntimeError):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Qualcosa è andato storto", status_code=500)
        self.assertContains(response, 'href="/"', status_code=500)
