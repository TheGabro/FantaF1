"""
Logica di calcolo bonus per qualifiche e gare.
Le costanti/tabelle sono definite in rules.py.
"""
from decimal import Decimal

from ..models import PlayerQualifyingChoice, PlayerQualifyingMultiChoice, QualifyingResult
from . import rules


# ============================================================================
# Helper functions per le qualifiche multichoice (weekend sprint)
# ============================================================================

def _passed_q1(result: QualifyingResult) -> bool:
    """Verifica se il pilota ha passato la Q1."""
    return result.q2_time is not None or result.q3_time is not None


def _passed_q2(result: QualifyingResult) -> bool:
    """Verifica se il pilota ha passato la Q2."""
    return result.q3_time is not None


# ============================================================================
# Bonus qualifiche multichoice (weekend sprint)
# ============================================================================

def get_qualifying_multichoice_bonus_rule(level: str) -> dict:
    """Restituisce i valori bonus per un livello multichoice."""
    return rules.QUALIFYING_MULTICHOICE_BONUS_RULES.get(
        level,
        rules.QUALIFYING_MULTICHOICE_BONUS_RULES["none"],
    ).copy()


def get_qualifying_multichoice_bonus(*, player, qualifying=None) -> dict:
    """
    Calcola il bonus dalla scelta multichoice (q1_pass, q2_pass, q3_top3).
    Si applica solo ai weekend sprint per la qualifica regular.
    """
    if qualifying is None:
        bonus = get_qualifying_multichoice_bonus_rule("none")
        return {
            "level": "none",
            "credit_discount": bonus["credit_discount"],
            "points_multiplier": bonus["points_multiplier"],
            "q1_pass_hit": False,
            "q2_pass_hit": False,
            "q3_top3_hit": False,
        }

    # Multichoice bonus solo per qualifiche regular in weekend sprint
    if not (qualifying.type == "regular" and qualifying.weekend.weekend_type == "sprint"):
        bonus = get_qualifying_multichoice_bonus_rule("none")
        return {
            "level": "none",
            "credit_discount": bonus["credit_discount"],
            "points_multiplier": bonus["points_multiplier"],
            "q1_pass_hit": False,
            "q2_pass_hit": False,
            "q3_top3_hit": False,
        }

    choices_by_slot = {slot: [] for slot in rules.VALID_MULTI_CHOICE_SLOTS}
    for choice in (
        PlayerQualifyingMultiChoice.objects
        .filter(player=player, qualifying=qualifying)
        .select_related("driver")
    ):
        choices_by_slot.setdefault(choice.selection_slot, []).append(choice.driver_id)

    results_by_driver_id = {
        result.driver_id: result
        for result in QualifyingResult.objects.filter(qualifying=qualifying)
    }

    q1_driver_ids = choices_by_slot["q1_pass"]
    q2_driver_ids = choices_by_slot["q2_pass"]
    q3_driver_ids = choices_by_slot["q3_top3"]

    q1_pass_hit = len(q1_driver_ids) == rules.MULTI_CHOICE_SLOT_SIZES["q1_pass"] and all(
        results_by_driver_id.get(driver_id) is not None and _passed_q1(results_by_driver_id[driver_id])
        for driver_id in q1_driver_ids
    )
    q2_pass_hit = q1_pass_hit and len(q2_driver_ids) == rules.MULTI_CHOICE_SLOT_SIZES["q2_pass"] and all(
        results_by_driver_id.get(driver_id) is not None and _passed_q2(results_by_driver_id[driver_id])
        for driver_id in q2_driver_ids
    )

    top_three_driver_ids = {
        result.driver_id
        for result in results_by_driver_id.values()
        if result.position in {1, 2, 3}
    }
    q3_top3_hit = (
        q2_pass_hit
        and len(q3_driver_ids) == rules.MULTI_CHOICE_SLOT_SIZES["q3_top3"]
        and set(q3_driver_ids) == top_three_driver_ids
    )

    if q3_top3_hit:
        level = "q3_top3"
    elif q2_pass_hit:
        level = "q2_pass"
    elif q1_pass_hit:
        level = "q1_pass"
    else:
        level = "none"

    bonus = get_qualifying_multichoice_bonus_rule(level)
    return {
        "level": level,
        "credit_discount": bonus["credit_discount"],
        "points_multiplier": bonus["points_multiplier"],
        "q1_pass_hit": q1_pass_hit,
        "q2_pass_hit": q2_pass_hit,
        "q3_top3_hit": q3_top3_hit,
    }


# ============================================================================
# Bonus qualifiche regular (weekend non-sprint)
# ============================================================================

def get_regular_qualifying_bonus_rule(position: int) -> dict:
    """Restituisce i valori bonus per una posizione in qualifica regular."""
    default = {"credit_change": 0, "qualifying_points": 0, "points_multiplier": Decimal("1")}
    return rules.REGULAR_QUALIFYING_BONUS_BY_POSITION.get(position, default).copy()


def get_regular_qualifying_choice_bonus(*, player, qualifying) -> dict:
    """
    Calcola il bonus per la scelta qualifica regular (weekend non-sprint).
    Basato sulla posizione in qualifica del pilota scelto dal giocatore.
    
    Per i weekend sprint si usa invece get_qualifying_multichoice_bonus().
    """
    default_result = {
        "credit_change": 0,
        "qualifying_points": 0,
        "points_multiplier": Decimal("1"),
        "driver": None,
        "position": None,
    }

    if qualifying is None:
        return default_result

    # Trova la scelta del giocatore
    choice = (
        PlayerQualifyingChoice.objects
        .filter(player=player, qualifying=qualifying)
        .select_related("driver")
        .first()
    )

    if choice is None:
        return default_result

    # Trova la posizione in qualifica del pilota scelto
    result = (
        QualifyingResult.objects
        .filter(qualifying=qualifying, driver=choice.driver)
        .first()
    )

    if result is None or result.position is None:
        return {
            **default_result,
            "driver": choice.driver,
        }

    bonus = get_regular_qualifying_bonus_rule(result.position)
    return {
        "credit_change": bonus["credit_change"],
        "qualifying_points": bonus["qualifying_points"],
        "points_multiplier": bonus["points_multiplier"],
        "driver": choice.driver,
        "position": result.position,
    }


# ============================================================================
# Bonus gara (unisce la logica per weekend sprint e regular)
# ============================================================================

def get_race_bonus(*, player, race) -> dict:
    """
    Restituisce il bonus per la gara.
    - Weekend sprint: bonus da multichoice (q1_pass, q2_pass, q3_top3)
    - Weekend regular: bonus da scelta singola pilota (PlayerQualifyingChoice)
    
    credit_change: positivo = malus (costo aumenta), negativo = sconto (costo diminuisce)
    """
    qualifying = race.weekend.qualifyings.filter(type="regular").first()
    
    if race.weekend.weekend_type == "sprint":
        # Weekend sprint: il bonus viene dalla qualifica multichoice
        multichoice_bonus = get_qualifying_multichoice_bonus(
            player=player,
            qualifying=qualifying,
        )
        # credit_discount del multichoice è uno sconto (positivo = sconto)
        # Lo convertiamo in credit_change (negativo = sconto)
        return {
            "level": multichoice_bonus["level"],
            "credit_change": -multichoice_bonus["credit_discount"],  # sconto → credit_change negativo
            "points_multiplier": multichoice_bonus["points_multiplier"],
            "qualifying_points": 0,
            "driver": None,
            "position": None,
        }
    else:
        # Weekend regular: il bonus viene dalla scelta singola del pilota
        bonus = get_regular_qualifying_choice_bonus(
            player=player,
            qualifying=qualifying,
        )
        return {
            "level": f"p{bonus['position']}" if bonus["position"] else "none",
            "credit_change": bonus["credit_change"],  # positivo = malus, negativo = sconto
            "points_multiplier": bonus["points_multiplier"],
            "qualifying_points": bonus["qualifying_points"],
            "driver": bonus["driver"],
            "position": bonus["position"],
        }


def get_regular_qualifying_bonus(*, player, qualifying) -> dict:
    """Alias per get_regular_qualifying_choice_bonus (retrocompatibilità)."""
    return get_regular_qualifying_choice_bonus(
        player=player,
        qualifying=qualifying,
    )


# ============================================================================
# Applicazione credit_change ai costi
# ============================================================================

def apply_race_credit_change(*, costs_by_driver_id: dict, credit_change: int) -> dict:
    """
    Applica il credit_change ai costi dei piloti.
    - credit_change positivo = malus (aumenta il costo totale)
    - credit_change negativo = sconto (riduce il costo totale)
    
    Lo sconto viene applicato partendo dal pilota più costoso.
    Il malus viene distribuito equamente tra i piloti.
    """
    adjusted_costs = dict(costs_by_driver_id)
    
    if credit_change < 0:
        # Sconto: riduce i costi partendo dal più costoso
        remaining_discount = min(abs(credit_change), sum(adjusted_costs.values()))
        
        for driver_id, current_cost in sorted(
            adjusted_costs.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            if remaining_discount <= 0:
                break
                
            applied_discount = min(current_cost, remaining_discount)
            adjusted_costs[driver_id] = current_cost - applied_discount
            remaining_discount -= applied_discount
    
    elif credit_change > 0:
        # Malus: aumenta il costo totale, distribuito equamente
        num_drivers = len(adjusted_costs)
        if num_drivers > 0:
            malus_per_driver = credit_change // num_drivers
            remainder = credit_change % num_drivers
            
            for i, driver_id in enumerate(adjusted_costs.keys()):
                extra = 1 if i < remainder else 0
                adjusted_costs[driver_id] += malus_per_driver + extra
    
    return adjusted_costs
