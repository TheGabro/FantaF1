from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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
	PlayerQualifyingMultiChoice,
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

		response = self.client.post(url, {"drivers": [self.driver_1.id]})

		self.assertRedirects(response, url)
		self.assertFalse(PlayerRaceChoice.objects.filter(player=self.player, race=self.sprint_race).exists())

	def test_sprint_race_choice_can_be_changed_before_event_start_without_scaling_credit(self):
		self.player.available_credit = 100
		self.player.save(update_fields=["available_credit"])

		pc.choose_sprint_race_drivers(
			player=self.player,
			race=self.sprint_race,
			drivers=[self.driver_3],
		)

		self.player.refresh_from_db()
		self.assertEqual(self.player.available_credit, 100)

		reserved_before_change = pc.get_player_reserved_credit(player=self.player)
		self.assertEqual(
			reserved_before_change,
			pc.get_sprint_race_driver_cost(20),
		)

		pc.choose_sprint_race_drivers(
			player=self.player,
			race=self.sprint_race,
			drivers=[self.driver_1],
		)

		selected_driver_ids = set(
			PlayerRaceChoice.objects.filter(player=self.player, race=self.sprint_race).values_list("driver_id", flat=True)
		)
		self.assertSetEqual(selected_driver_ids, {self.driver_1.id})
		self.assertEqual(self.player.available_credit, 100)
		self.assertEqual(
			pc.get_player_reserved_credit(player=self.player),
			pc.get_sprint_race_driver_cost(1),
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

		su.apply_started_sprint_race_credits(player=self.player)
		self.player.refresh_from_db()

		expected_credit = 40 - pc.get_sprint_race_driver_cost(20)
		self.assertEqual(self.player.available_credit, expected_credit)
		self.assertEqual(
			PlayerRaceChoice.objects.filter(player=self.player, race=self.sprint_race, credit_applied=True).count(),
			1,
		)

		su.apply_started_sprint_race_credits(player=self.player)
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

		self.championship = Championship.objects.create(name="Grand Prix Cup", year=2026)
		self.league = League.objects.create(championship=self.championship, name="League GP")
		ChampionshipManager.objects.create(user=self.user, championship=self.championship)
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

		self.driver_1 = self._create_driver(api_id="gp-drv-1", number=21, short_name="DDD")
		self.driver_2 = self._create_driver(api_id="gp-drv-2", number=22, short_name="EEE")
		self.driver_3 = self._create_driver(api_id="gp-drv-3", number=23, short_name="FFF")

		self.weekend_bundles = [self._create_regular_weekend_bundle(round_number) for round_number in range(1, 6)]

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

		QualifyingResult.objects.create(qualifying=qualifying, driver=self.driver_1, position=1)
		QualifyingResult.objects.create(qualifying=qualifying, driver=self.driver_2, position=2)
		QualifyingResult.objects.create(qualifying=qualifying, driver=self.driver_3, position=10)

		return {"weekend": weekend, "qualifying": qualifying, "race": race}

	def test_regular_race_choice_requires_pupillo_among_selected_drivers(self):
		race = self.weekend_bundles[0]["race"]

		with self.assertRaisesMessage(ValidationError, "Il pupillo deve essere uno dei 2 piloti selezionati."):
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

		self.assertEqual(pc.get_regular_race_pupillo_discount(player=self.player, race=fifth_race, driver=self.driver_1), 20)
		self.assertEqual(result["pupillo_discount"], 20)
		self.assertEqual(
			result["total_spent_amount"],
			pc.get_regular_race_driver_cost_breakdown(
				grid_position=1,
				driver=self.driver_1,
				weekend=fifth_race.weekend,
			)["total_cost"]
			- 20
			+
			pc.get_regular_race_driver_cost_breakdown(
				grid_position=2,
				driver=self.driver_2,
				weekend=fifth_race.weekend,
			)["total_cost"],
		)

		pupillo_choice = PlayerRaceChoice.objects.get(player=self.player, race=fifth_race, driver=self.driver_1)
		non_pupillo_choice = PlayerRaceChoice.objects.get(player=self.player, race=fifth_race, driver=self.driver_2)
		self.assertTrue(pupillo_choice.is_pupillo)
		self.assertEqual(
			pupillo_choice.spent_amount,
			pc.get_regular_race_driver_cost_breakdown(
				grid_position=1,
				driver=self.driver_1,
				weekend=fifth_race.weekend,
			)["total_cost"] - 20,
		)
		self.assertFalse(non_pupillo_choice.is_pupillo)
		self.assertEqual(
			non_pupillo_choice.spent_amount,
			pc.get_regular_race_driver_cost_breakdown(
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

		su.apply_started_regular_race_credits(player=self.player)
		self.player.refresh_from_db()

		expected_credit = 1300 - result["total_spent_amount"]
		self.assertEqual(self.player.available_credit, expected_credit)
		self.assertEqual(
			PlayerRaceChoice.objects.filter(player=self.player, race=first_race, credit_applied=True).count(),
			2,
		)

		su.apply_started_regular_race_credits(player=self.player)
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
		self.league = League.objects.create(championship=self.championship, name="Bonus League")
		ChampionshipManager.objects.create(user=self.user, championship=self.championship)
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
		self.qualifying = Qualifying.objects.create(weekend=self.weekend, type="regular")
		self.race = Race.objects.create(weekend=self.weekend, type="regular")

		for index, driver in enumerate(self.drivers, start=1):
			QualifyingResult.objects.create(
				qualifying=self.qualifying,
				driver=driver,
				q1_time=timedelta(minutes=1, seconds=index),
				q2_time=timedelta(minutes=1, seconds=10 + index) if index <= 15 else None,
				q3_time=timedelta(minutes=1, seconds=20 + index) if index <= 8 else None,
				position=index,
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

	def test_regular_race_bonus_reaches_q2_tier_when_top3_is_not_matched(self):
		for driver in (self.drivers[0], self.drivers[1], self.drivers[8]):
			PlayerQualifyingMultiChoice.objects.create(
				player=self.player,
				qualifying=self.qualifying,
				selection_slot="q3_top3",
				driver=driver,
			)

		bonus = pc.get_regular_race_bonus(player=self.player, race=self.race)

		self.assertEqual(bonus["level"], "q2_pass")
		self.assertEqual(bonus["credit_discount"], 20)
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
		self.assertEqual(result["qualifying_bonus_credit_discount"], 50)
		self.assertEqual(result["qualifying_bonus_points_multiplier"], Decimal("2"))
		self.assertEqual(result["total_spent_amount"], 200)
		self.assertEqual(
			sum(
				PlayerRaceChoice.objects.filter(player=self.player, race=self.race).values_list("spent_amount", flat=True)
			),
			200,
		)
