"""
Logica di calcolo punti FantaF1 per le gare.
Le funzioni qui sono pensate per essere chiamate da task schedulati (Airflow/management command).
"""
from django.db import transaction

from ..models import PlayerRaceChoice, PlayerRaceResult, RaceResult
from . import bonuses


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
      3. Recupera il moltiplicatore dalla qualifica (bonus.get_regular_race_bonus)
      4. total_points = fia_points * point_multiplier
      5. Salva/aggiorna PlayerRaceResult

    Returns:
        L'istanza PlayerRaceResult creata o aggiornata.

    Raises:
        ValueError: Se il giocatore non ha fatto scelte per questa gara.
    """
    choices = list(
        PlayerRaceChoice.objects
        .filter(player=player, race=race)
        .select_related("driver")
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
        total_points = fia_points + sprint_bonus["points_modifier"]
    else:
        # Gara regular: il bonus è un moltiplicatore sui punti FIA.
        race_bonus = bonuses.get_race_bonus(player=player, race=race)
        point_multiplier = float(race_bonus["points_multiplier"])
        total_points = fia_points * point_multiplier

    result, _ = PlayerRaceResult.objects.update_or_create(
        player=player,
        race=race,
        defaults={
            "fia_points": fia_points,
            "point_multiplier": point_multiplier,
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
    
    # TODO Airflow: chiamare questa funzione da un DAG schedulato DOPO insert_race_result.py
    """
    # Prendi tutti i PlayerRaceChoice per questa race, raggruppati per player
    choices_by_player_id = {}
    for choice in (
        PlayerRaceChoice.objects
        .filter(race=race)
        .select_related("player", "driver")
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
            
            # Aggiorna total_score come somma di TUTTI i PlayerRaceResult del giocatore
            # (indipendentemente dal campionato)
            total = sum(
                r.total_points
                for r in PlayerRaceResult.objects.filter(player=player)
            )
            player.total_score = int(total)
            player.save(update_fields=["total_score"])
            
            players_updated += 1
        except Exception as e:
            errors.append({
                "player": player.player_name,
                "race": str(race),
                "error": str(e),
            })
    
    return {
        "race": str(race),
        "players_updated": players_updated,
        "errors": errors,
    }