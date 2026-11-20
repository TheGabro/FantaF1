"""
Logica di calcolo punti FantaF1 per le gare.
Le funzioni qui sono pensate per essere chiamate da task schedulati (Airflow/management command).
"""

from collections import defaultdict

from django.db import transaction
from django.db.models import Sum

from ..models import (
    ChampionshipPlayer,
    PlayerQualifyingChoice,
    PlayerQualifyingMultiChoice,
    PlayerQualifyingResult,
    PlayerRaceChoice,
    PlayerRaceResult,
    QualifyingResult,
    RaceResult,
)
from . import bonuses, rules


@transaction.atomic
def compute_player_qualifying_points(*, qualifying) -> int:
    """
    Save the qualifying points (∂, D.1.d) of every player who chose for this
    Saturday qualifying, from its classification (#166):
    - non-sprint weekend: the single pick, by its classified position;
    - sprint weekend: the multichoice level reached (Q1/Q2/top 3).

    Missed choices are worth 0 ∂ and get no row. The Sprint Qualifying
    (shootout) gives no ∂. Safe to run again: update_or_create.

    Returns:
        The number of rows saved.
    """
    if qualifying.type != "regular":
        return 0

    results_by_driver_id = {
        result.driver_id: result
        for result in QualifyingResult.objects.filter(qualifying=qualifying)
    }
    if not results_by_driver_id:
        return 0

    points_by_player_id = {}
    if qualifying.weekend.weekend_type == "sprint":
        choices_by_player_id = defaultdict(lambda: defaultdict(list))
        for player_id, slot, driver_id in PlayerQualifyingMultiChoice.objects.filter(
            qualifying=qualifying
        ).values_list("player_id", "selection_slot", "driver_id"):
            choices_by_player_id[player_id][slot].append(driver_id)
        for player_id, choices_by_slot in choices_by_player_id.items():
            level = bonuses.resolve_multichoice_level(
                choices_by_slot=choices_by_slot,
                results_by_driver_id=results_by_driver_id,
            )
            points_by_player_id[player_id] = bonuses.get_qualifying_multichoice_bonus_rule(
                level
            )["qualifying_points"]
    else:
        for player_id, driver_id in PlayerQualifyingChoice.objects.filter(
            qualifying=qualifying
        ).values_list("player_id", "driver_id"):
            result = results_by_driver_id.get(driver_id)
            points_by_player_id[player_id] = (
                bonuses.get_regular_qualifying_bonus_rule(result.position)[
                    "qualifying_points"
                ]
                if result is not None and result.position
                else 0
            )

    for player_id, points in points_by_player_id.items():
        PlayerQualifyingResult.objects.update_or_create(
            player_id=player_id,
            qualifying=qualifying,
            defaults={"qualifying_points": points},
        )
    return len(points_by_player_id)


def _get_fia_points_for_choices(choices: list[PlayerRaceChoice], race) -> int:
    """
    Somma i punti F1 ufficiali dei piloti scelti dal giocatore per quella gara.
    Se un pilota non ha un risultato (non classificato, DNS, ecc.) contribuisce 0.
    """
    driver_ids = [choice.driver_id for choice in choices]

    race_results_by_driver = {
        entry.driver_id: entry
        for entry in RaceResult.objects.filter(race=race, driver_id__in=driver_ids)
    }

    total = 0
    for choice in choices:
        result = race_results_by_driver.get(choice.driver_id)
        if result is not None:
            total += result.points
    return total


def compute_race_points(*, player, race) -> PlayerRaceResult:
    """
    Calcola i punti FantaF1 del giocatore per una singola gara e li persiste
    in PlayerRaceResult (upsert).

    Algoritmo:
      1. Legge le scelte del giocatore (PlayerRaceChoice)
      2. Somma i punti F1 ufficiali dei piloti scelti (fia_points)
      3. Applica il bonus qualifica: gara regular -> moltiplicatore, gara sprint -> additivo
      4. Salva/aggiorna PlayerRaceResult (inclusi point_multiplier e point_modifier)

    Returns:
        L'istanza PlayerRaceResult creata o aggiornata.

    Raises:
        ValueError: Se il giocatore non ha fatto scelte per questa gara.
    """
    choices = list(
        PlayerRaceChoice.objects.filter(player=player, race=race).select_related(
            "driver"
        )
    )

    if not choices:
        raise ValueError(
            f"Il giocatore '{player.player_name}' non ha scelte per la gara {race}."
        )

    fia_points = _get_fia_points_for_choices(choices, race)
    credit_spent = sum(choice.spent_amount for choice in choices)

    if race.type == "sprint":
        # Sprint race: il bonus si somma ai punti FIA (nessun moltiplicatore).
        sprint_bonus = bonuses.get_sprint_race_bonus(player=player, race=race)
        point_multiplier = 1.0
        point_modifier = sprint_bonus["points_modifier"]
        total_points = fia_points + point_modifier
    else:
        # Gara regular: il bonus è un moltiplicatore sui punti FIA.
        race_bonus = bonuses.get_race_bonus(player=player, race=race)
        point_multiplier = float(race_bonus["points_multiplier"])
        point_modifier = 0
        total_points = fia_points * point_multiplier

    result, _ = PlayerRaceResult.objects.update_or_create(
        player=player,
        race=race,
        defaults={
            "fia_points": fia_points,
            "point_multiplier": point_multiplier,
            "point_modifier": point_modifier,
            "total_points": total_points,
            "credit_spent": credit_spent,
        },
    )
    return result


@transaction.atomic
def compute_player_score_per_race(*, race) -> dict:
    """
    Calcola i punti per TUTTI i giocatori di TUTTI i campionati per una singola race.

    Chiamata dalla pipeline dopo aver importato i RaceResult ufficiali F1.
    Aggiorna automaticamente ChampionshipPlayer.total_score per ogni giocatore che ha fatto scelte.

    Una sola pass sul DB: molto efficiente.

    Args:
        race: L'istanza Race per cui calcolare i punti

    Returns:
        dict con statistiche: {'race': str, 'players_updated': int, 'errors': list}
    """
    # Prendi tutti i PlayerRaceChoice per questa race, raggruppati per player
    choices_by_player_id = {}
    for choice in PlayerRaceChoice.objects.filter(race=race).select_related(
        "player", "driver"
    ):
        player_id = choice.player_id
        if player_id not in choices_by_player_id:
            choices_by_player_id[player_id] = []
        choices_by_player_id[player_id].append(choice)

    errors = []
    players_updated = 0

    # Calcola punti per ogni giocatore che ha fatto scelte
    for player_id, choices in choices_by_player_id.items():
        player = choices[0].player  # Tutti hanno lo stesso player

        try:
            # Calcola e salva i punti per questa gara
            compute_race_points(player=player, race=race)

            _refresh_total_score(player)

            players_updated += 1
        except Exception as e:
            errors.append(
                {
                    "player": player.player_name,
                    "race": str(race),
                    "error": str(e),
                }
            )

    penalized = apply_missed_choice_penalties(race=race)
    for player in penalized:
        _refresh_total_score(player)

    return {
        "race": str(race),
        "players_updated": players_updated,
        "players_penalized": len(penalized),
        "errors": errors,
    }


def _refresh_total_score(player):
    # total_score = somma dei PlayerRaceResult di questo ChampionshipPlayer
    # (gia' scoping al singolo campionato: ChampionshipPlayer e' per-campionato)
    total = sum(r.total_points for r in PlayerRaceResult.objects.filter(player=player))
    player.total_score = int(total)
    player.save(update_fields=["total_score"])


def apply_missed_choice_penalties(*, race) -> list[ChampionshipPlayer]:
    """
    Penalize the players with no choice for a Grand Prix (C.3, #154).

    - Credits: the lowest spend among the players of the same championship who
      chose, plus the player's qualifying malus (discounts are lost). Nobody
      chose in the championship: only the malus. Credits never go below zero.
    - Points: from the (GRACE + 1)-th missed choice of the season,
      -STEP x (n - GRACE). The counter goes up even when nobody chose.
      A player with no credits left loses no points.
    - The missed qualifying malus is not part of it: it is charged on its own
      right after the qualifying (#153).

    Safe to run again: credits are charged only when the result is created.

    Returns:
        The penalized players.
    """
    if race.type != "regular":
        return []

    season = race.weekend.season
    spent_by_player_id = dict(
        PlayerRaceChoice.objects.filter(race=race)
        .values("player_id")
        .annotate(total=Sum("spent_amount"))
        .values_list("player_id", "total")
    )
    players = list(
        ChampionshipPlayer.objects.select_for_update().filter(
            championship__year=season
        )
    )

    min_spent_by_championship_id = {}
    for player in players:
        spent = spent_by_player_id.get(player.id)
        if spent is not None:
            current = min_spent_by_championship_id.get(player.championship_id, spent)
            min_spent_by_championship_id[player.championship_id] = min(current, spent)

    penalized = []
    for player in players:
        if player.id in spent_by_player_id:
            continue

        malus = max(bonuses.get_race_bonus(player=player, race=race)["credit_change"], 0)
        penalty = min_spent_by_championship_id.get(player.championship_id, 0) + malus

        missed = 1 + PlayerRaceResult.objects.filter(
            player=player,
            missed_choice=True,
            race__type="regular",
            race__weekend__season=season,
            race__weekend__round_number__lt=race.weekend.round_number,
        ).count()
        points = -rules.MISSED_GP_CHOICE_POINTS_STEP * max(
            missed - rules.MISSED_GP_CHOICE_GRACE, 0
        )
        # Out of credits: no points lost, even if discounts and pupillo could
        # still have made a 0-cost choice possible (game rule, by design)
        if player.available_credit <= 0:
            points = 0

        result, created = PlayerRaceResult.objects.get_or_create(
            player=player,
            race=race,
            defaults={
                "credit_spent": min(penalty, max(player.available_credit, 0)),
                "fia_points": 0,
                "total_points": points,
                "missed_choice": True,
            },
        )
        if created:
            player.available_credit -= result.credit_spent
            player.save(update_fields=["available_credit"])
        elif result.missed_choice:
            # An earlier race processed again can change the counter
            result.total_points = points
            result.save(update_fields=["total_points", "updated_at"])
        penalized.append(player)

    return penalized
