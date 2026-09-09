from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .views import invites

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
	League,
	PlayerQualifyingChoice,
	Qualifying,
	PlayerQualifyingMultiChoice,
	PlayerRaceResult,
	QualifyingResult,
	Race,
	RaceResult,
	Team,
	Weekend,
	PlayerRaceChoice,
)
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
			PlayerRaceChoice.objects.filter(player=self.player, race=self.sprint_race).values_list("driver_id", flat=True)
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
			PlayerRaceChoice.objects.filter(player=self.player, race=self.sprint_race, credit_applied=True).count(),
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

		self.assertEqual(costs.get_regular_race_pupillo_discount(player=self.player, race=fifth_race, driver=self.driver_1), 20)
		self.assertEqual(result["pupillo_discount"], 20)
		self.assertEqual(
			result["total_spent_amount"],
			costs.get_regular_race_driver_cost_breakdown(
				grid_position=1,
				driver=self.driver_1,
				weekend=fifth_race.weekend,
			)["total_cost"]
			- 20
			+
			costs.get_regular_race_driver_cost_breakdown(
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
			costs.get_regular_race_driver_cost_breakdown(
				grid_position=1,
				driver=self.driver_1,
				weekend=fifth_race.weekend,
			)["total_cost"] - 20,
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
			PlayerRaceChoice.objects.filter(player=self.player, race=first_race, credit_applied=True).count(),
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
		self.assertEqual(result["qualifying_bonus_credit_change"], -50)  # negativo = sconto
		self.assertEqual(result["qualifying_bonus_points_multiplier"], Decimal("2"))
		self.assertEqual(result["total_spent_amount"], 200)
		self.assertEqual(
			sum(
				PlayerRaceChoice.objects.filter(player=self.player, race=self.race).values_list("spent_amount", flat=True)
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
		self.championship_a = Championship.objects.create(name="Consolidation Cup A", year=2026)
		self.league_a = League.objects.create(championship=self.championship_a, name="League A")
		ChampionshipManager.objects.create(user=self.user_a, championship=self.championship_a)
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
		self.championship_b = Championship.objects.create(name="Consolidation Cup B", year=2026)
		self.league_b = League.objects.create(championship=self.championship_b, name="League B")
		ChampionshipManager.objects.create(user=self.user_b, championship=self.championship_b)
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
		choice = self._create_choice(player=self.player_a, race=self.sprint_race, spent_amount=30)

		updated_count = su.consolidate_race_credits(race=self.sprint_race)

		self.assertEqual(updated_count, 0)
		self.player_a.refresh_from_db()
		self.assertEqual(self.player_a.available_credit, 100)
		choice.refresh_from_db()
		self.assertFalse(choice.credit_applied)

	def test_consolidates_credit_once_race_has_started(self):
		self._create_choice(player=self.player_a, race=self.sprint_race, spent_amount=30)
		self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
		self.weekend.save(update_fields=["sprint_start"])

		updated_count = su.consolidate_race_credits(race=self.sprint_race)

		self.assertEqual(updated_count, 1)
		self.player_a.refresh_from_db()
		self.assertEqual(self.player_a.available_credit, 70)
		self.assertTrue(
			PlayerRaceChoice.objects.get(player=self.player_a, race=self.sprint_race).credit_applied
		)

	def test_consolidation_is_idempotent(self):
		self._create_choice(player=self.player_a, race=self.sprint_race, spent_amount=30)
		self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
		self.weekend.save(update_fields=["sprint_start"])

		first_run = su.consolidate_race_credits(race=self.sprint_race)
		second_run = su.consolidate_race_credits(race=self.sprint_race)

		self.assertEqual(first_run, 1)
		self.assertEqual(second_run, 0)
		self.player_a.refresh_from_db()
		self.assertEqual(self.player_a.available_credit, 70)

	def test_consolidates_multiple_players_across_different_championships(self):
		self._create_choice(player=self.player_a, race=self.sprint_race, spent_amount=30)
		self._create_choice(player=self.player_b, race=self.sprint_race, spent_amount=45)
		self.weekend.sprint_start = timezone.now() - timedelta(minutes=5)
		self.weekend.save(update_fields=["sprint_start"])

		updated_count = su.consolidate_race_credits(race=self.sprint_race)

		self.assertEqual(updated_count, 2)
		self.player_a.refresh_from_db()
		self.player_b.refresh_from_db()
		self.assertEqual(self.player_a.available_credit, 70)
		self.assertEqual(self.player_b.available_credit, 55)

	def test_consolidation_ignores_choices_from_other_races(self):
		self._create_choice(player=self.player_a, race=self.sprint_race, spent_amount=30)
		other_choice = self._create_choice(player=self.player_a, race=self.other_race, spent_amount=999)
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
		self.qualifying = Qualifying.objects.create(weekend=self.weekend, type="regular")
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
		self.second_qualifying = Qualifying.objects.create(weekend=self.second_weekend, type="regular")
		self.second_race = Race.objects.create(weekend=self.second_weekend, type="regular")

		self.driver_1 = self._create_driver(api_id="score-drv-1", number=51, short_name="SC1")
		self.driver_2 = self._create_driver(api_id="score-drv-2", number=52, short_name="SC2")

		self.user_a = get_user_model().objects.create_user(
			username="scoring-a",
			email="scoring-a@example.com",
			password="password123",
		)
		self.championship_a = Championship.objects.create(name="Scoring Cup A", year=2026)
		self.league_a = League.objects.create(championship=self.championship_a, name="League A")
		ChampionshipManager.objects.create(user=self.user_a, championship=self.championship_a)
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
		self.championship_b = Championship.objects.create(name="Scoring Cup B", year=2026)
		self.league_b = League.objects.create(championship=self.championship_b, name="League B")
		ChampionshipManager.objects.create(user=self.user_b, championship=self.championship_b)
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

	def _create_race_result(self, *, race, driver, position, points, starting_grid=None):
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
		self._create_race_result(race=self.race, driver=self.driver_1, position=1, points=25)
		self._create_race_result(race=self.race, driver=self.driver_2, position=3, points=15)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.race, driver=self.driver_2, spent_amount=60)

		result = player_scoring.compute_race_points(player=self.player_a, race=self.race)

		self.assertEqual(result.fia_points, 40)
		self.assertEqual(result.credit_spent, 160)
		self.assertEqual(result.point_multiplier, 1.0)
		self.assertEqual(result.total_points, 40.0)

	def test_compute_race_points_ignores_driver_without_race_result(self):
		self._create_race_result(race=self.race, driver=self.driver_1, position=1, points=25)
		# driver_2 e' stato scelto ma non ha ancora un RaceResult importato (es. DNS non ancora inserito)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.race, driver=self.driver_2, spent_amount=60)

		result = player_scoring.compute_race_points(player=self.player_a, race=self.race)

		self.assertEqual(result.fia_points, 25)

	def test_compute_race_points_applies_qualifying_multiplier(self):
		self._create_race_result(race=self.race, driver=self.driver_1, position=1, points=25)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100)
		QualifyingResult.objects.create(qualifying=self.qualifying, driver=self.driver_1, position=1)
		PlayerQualifyingChoice.objects.create(player=self.player_a, qualifying=self.qualifying, driver=self.driver_1)

		result = player_scoring.compute_race_points(player=self.player_a, race=self.race)

		self.assertEqual(result.point_multiplier, 2.0)  # P1 in qualifica regular -> x2 (rules.py)
		self.assertEqual(result.total_points, 50.0)

	def test_compute_race_points_upserts_existing_result(self):
		race_result = self._create_race_result(race=self.race, driver=self.driver_1, position=1, points=25)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100)

		player_scoring.compute_race_points(player=self.player_a, race=self.race)
		self.assertEqual(PlayerRaceResult.objects.filter(player=self.player_a, race=self.race).count(), 1)

		race_result.points = 18
		race_result.save(update_fields=["points"])
		player_scoring.compute_race_points(player=self.player_a, race=self.race)

		self.assertEqual(PlayerRaceResult.objects.filter(player=self.player_a, race=self.race).count(), 1)
		updated_result = PlayerRaceResult.objects.get(player=self.player_a, race=self.race)
		self.assertEqual(updated_result.fia_points, 18)

	def test_compute_player_score_per_race_only_updates_players_with_choices(self):
		self._create_race_result(race=self.race, driver=self.driver_1, position=1, points=25)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100)
		# player_b non ha fatto scelte per questa gara

		stats = player_scoring.compute_player_score_per_race(race=self.race)

		self.assertEqual(stats["players_updated"], 1)
		self.assertEqual(stats["errors"], [])
		self.player_a.refresh_from_db()
		self.player_b.refresh_from_db()
		self.assertEqual(self.player_a.total_score, 25)
		self.assertEqual(self.player_b.total_score, 0)
		self.assertFalse(PlayerRaceResult.objects.filter(player=self.player_b, race=self.race).exists())

	def test_compute_player_score_per_race_updates_players_across_different_championships(self):
		self._create_race_result(race=self.race, driver=self.driver_1, position=1, points=25)
		self._create_race_result(race=self.race, driver=self.driver_2, position=2, points=18)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100)
		PlayerRaceChoice.objects.create(player=self.player_b, race=self.race, driver=self.driver_2, spent_amount=90)

		stats = player_scoring.compute_player_score_per_race(race=self.race)

		self.assertEqual(stats["players_updated"], 2)
		self.player_a.refresh_from_db()
		self.player_b.refresh_from_db()
		self.assertEqual(self.player_a.total_score, 25)
		self.assertEqual(self.player_b.total_score, 18)

	def test_compute_player_score_per_race_aggregates_total_score_across_multiple_races(self):
		self._create_race_result(race=self.race, driver=self.driver_1, position=1, points=25)
		self._create_race_result(race=self.second_race, driver=self.driver_1, position=2, points=18)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.race, driver=self.driver_1, spent_amount=100)
		PlayerRaceChoice.objects.create(player=self.player_a, race=self.second_race, driver=self.driver_1, spent_amount=100)

		player_scoring.compute_player_score_per_race(race=self.race)
		player_scoring.compute_player_score_per_race(race=self.second_race)

		self.player_a.refresh_from_db()
		self.assertEqual(self.player_a.total_score, 43)
		self.assertEqual(PlayerRaceResult.objects.filter(player=self.player_a).count(), 2)


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
			{"identifier": "next-user", "password": "password123", "next": "https://evil.example.com/"},
		)

		self.assertRedirects(response, reverse("user_dashboard"))

	def test_register_carries_next_to_the_login_page(self):
		target = reverse("user_dashboard")
		response = self.client.post(
			reverse("register"),
			{
				"username": "brand-new",
				"email": "brand-new@example.com",
				"password": "password123",
				"password2": "password123",
				"next": target,
			},
		)

		self.assertRedirects(response, f"{reverse('login')}?next={target}")


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
		player = ChampionshipPlayer.objects.get(user=self.user, championship=championship)
		self.assertEqual(player.player_name, "Dave")
		self.assertEqual(player.league.name, "Serie B")
		self.assertEqual(player.available_credit, 2000)
		self.assertTrue(ChampionshipManager.objects.filter(user=self.user, championship=championship).exists())

	def test_player_name_defaults_to_username(self):
		self.client.post(reverse("create_championship"), self._payload(player_name=""))

		player = ChampionshipPlayer.objects.get(user=self.user)
		self.assertEqual(player.player_name, "organizzatore")

	def test_out_of_range_league_index_falls_back_to_the_first_league(self):
		self.client.post(reverse("create_championship"), self._payload(player_league_index="99"))

		player = ChampionshipPlayer.objects.get(user=self.user)
		self.assertEqual(player.league.name, "Serie A")

	def test_manager_can_stay_out_of_the_game(self):
		payload = self._payload()
		del payload["join_as_player"]
		self.client.post(reverse("create_championship"), payload)

		championship = Championship.objects.get(name="Coppa Amici")
		self.assertTrue(ChampionshipManager.objects.filter(user=self.user, championship=championship).exists())
		self.assertFalse(ChampionshipPlayer.objects.filter(user=self.user, championship=championship).exists())

	def test_failed_creation_leaves_nothing_behind(self):
		Championship.objects.create(name="Coppa Amici", year=2026)

		self.client.post(reverse("create_championship"), self._payload())

		self.assertEqual(Championship.objects.filter(name="Coppa Amici").count(), 1)
		self.assertFalse(ChampionshipPlayer.objects.filter(user=self.user).exists())


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

		self.championship = Championship.objects.create(name="Campionato Invitato", year=2026)
		self.league_a = League.objects.create(championship=self.championship, name="Serie A")
		self.league_b = League.objects.create(championship=self.championship, name="Serie B")
		ChampionshipManager.objects.create(user=self.organizer, championship=self.championship)

		self.other_championship = Championship.objects.create(name="Altro Campionato", year=2026)
		self.other_league = League.objects.create(championship=self.other_championship, name="Lega Estranea")

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

		response = self.client.post(self.join_url, {"player_name": "Ospite", "league": self.league_b.id})

		self.assertRedirects(response, reverse("championship_dashboard", args=[self.championship.id]))
		player = ChampionshipPlayer.objects.get(user=self.guest, championship=self.championship)
		self.assertEqual(player.league, self.league_b)

	def test_join_rejects_a_league_of_another_championship(self):
		self.client.force_login(self.guest)

		response = self.client.post(self.join_url, {"player_name": "Ospite", "league": self.other_league.id})

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

		response = self.client.post(self.join_url, {"player_name": "Ospite", "league": self.league_a.id})

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

		self.assertRedirects(response, reverse("championship_dashboard", args=[self.championship.id]))
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
		manager_response = self.client.get(reverse("championship_info", args=[self.championship.id]))
		self.assertContains(manager_response, "Invita i tuoi amici")

		self.client.force_login(self.guest)
		guest_response = self.client.get(reverse("championship_info", args=[self.championship.id]))
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

		response = self.client.post(reverse("invite_redeem"), {"invite_code": f"  {token}  "})

		self.assertRedirects(response, self.join_url)

	def test_empty_code_is_reported_without_crashing(self):
		self.client.force_login(self.guest)

		response = self.client.post(reverse("invite_redeem"), {"invite_code": "   "})

		self.assertRedirects(response, reverse("user_dashboard"))
