from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
	Championship,
	ChampionshipManager,
	ChampionshipPlayer,
	Circuit,
	Driver,
	League,
	Qualifying,
	QualifyingResult,
	Race,
	Team,
	Weekend,
	PlayerRaceChoice,
)
from .services import player_choices as pc
from .services import scheduled_updates as su


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
		self.league = League.objects.create(championship=self.championship, name="League 1")
		ChampionshipManager.objects.create(user=self.user, championship=self.championship)
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
		self.sprint_qualifying = Qualifying.objects.create(weekend=self.weekend, type="sprint")
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

		response = self.client.post(url, {"drivers": [self.driver_1.id, self.driver_2.id]})

		self.assertRedirects(response, url)
		self.assertFalse(PlayerRaceChoice.objects.filter(player=self.player, race=self.sprint_race).exists())

	def test_sprint_race_choice_can_be_changed_before_event_start_without_scaling_credit(self):
		self.player.available_credit = 40
		self.player.save(update_fields=["available_credit"])

		pc.choose_sprint_race_drivers(
			player=self.player,
			race=self.sprint_race,
			drivers=[self.driver_2, self.driver_3],
		)

		self.player.refresh_from_db()
		self.assertEqual(self.player.available_credit, 40)

		reserved_before_change = pc.get_player_reserved_credit(player=self.player)
		self.assertEqual(
			reserved_before_change,
			pc.get_sprint_race_driver_cost(2) + pc.get_sprint_race_driver_cost(20),
		)

		pc.choose_sprint_race_drivers(
			player=self.player,
			race=self.sprint_race,
			drivers=[self.driver_1, self.driver_3],
		)

		selected_driver_ids = set(
			PlayerRaceChoice.objects.filter(player=self.player, race=self.sprint_race).values_list("driver_id", flat=True)
		)
		self.assertSetEqual(selected_driver_ids, {self.driver_1.id, self.driver_3.id})
		self.assertEqual(self.player.available_credit, 40)
		self.assertEqual(
			pc.get_player_reserved_credit(player=self.player),
			pc.get_sprint_race_driver_cost(1) + pc.get_sprint_race_driver_cost(20),
		)

	def test_started_sprint_race_applies_credit_only_once(self):
		self.player.available_credit = 40
		self.player.save(update_fields=["available_credit"])
		pc.choose_sprint_race_drivers(
			player=self.player,
			race=self.sprint_race,
			drivers=[self.driver_1, self.driver_3],
		)

		self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
		self.weekend.save(update_fields=["sprint_start"])

		su.apply_started_sprint_race_credits(player=self.player)
		self.player.refresh_from_db()

		expected_credit = 40 - (
			pc.get_sprint_race_driver_cost(1) + pc.get_sprint_race_driver_cost(20)
		)
		self.assertEqual(self.player.available_credit, expected_credit)
		self.assertEqual(
			PlayerRaceChoice.objects.filter(player=self.player, race=self.sprint_race, credit_applied=True).count(),
			2,
		)

		su.apply_started_sprint_race_credits(player=self.player)
		self.player.refresh_from_db()
		self.assertEqual(self.player.available_credit, expected_credit)
