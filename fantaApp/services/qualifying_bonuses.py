from ..models import PlayerQualifyingMultiChoice, QualifyingResult
from . import rules


VALID_MULTI_CHOICE_SLOTS = ("q1_pass", "q2_pass", "q3_top3")
MULTI_CHOICE_SLOT_SIZES = {
    "q1_pass": 6,
    "q2_pass": 5,
    "q3_top3": 3,
}


def _passed_q1(result: QualifyingResult) -> bool:
    return result.q2_time is not None or result.q3_time is not None


def _passed_q2(result: QualifyingResult) -> bool:
    return result.q3_time is not None


def get_qualifying_multichoice_bonus(*, player, qualifying=None, race=None) -> dict:
    if qualifying is None and race is not None:
        qualifying = race.weekend.qualifyings.filter(type="regular").first()

    if qualifying is None:
        bonus = rules.get_qualifying_multichoice_bonus_rule("none")
        return {
            "level": "none",
            "credit_discount": bonus["credit_discount"],
            "points_multiplier": bonus["points_multiplier"],
            "q1_pass_hit": False,
            "q2_pass_hit": False,
            "q3_top3_hit": False,
        }

    if qualifying.type != "regular" or qualifying.weekend.weekend_type != "sprint":
        bonus = rules.get_qualifying_multichoice_bonus_rule("none")
        return {
            "level": "none",
            "credit_discount": bonus["credit_discount"],
            "points_multiplier": bonus["points_multiplier"],
            "q1_pass_hit": False,
            "q2_pass_hit": False,
            "q3_top3_hit": False,
        }

    choices_by_slot = {slot: [] for slot in VALID_MULTI_CHOICE_SLOTS}
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

    q1_pass_hit = len(q1_driver_ids) == MULTI_CHOICE_SLOT_SIZES["q1_pass"] and all(
        results_by_driver_id.get(driver_id) is not None and _passed_q1(results_by_driver_id[driver_id])
        for driver_id in q1_driver_ids
    )
    q2_pass_hit = q1_pass_hit and len(q2_driver_ids) == MULTI_CHOICE_SLOT_SIZES["q2_pass"] and all(
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
        and len(q3_driver_ids) == MULTI_CHOICE_SLOT_SIZES["q3_top3"]
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

    bonus = rules.get_qualifying_multichoice_bonus_rule(level)
    return {
        "level": level,
        "credit_discount": bonus["credit_discount"],
        "points_multiplier": bonus["points_multiplier"],
        "q1_pass_hit": q1_pass_hit,
        "q2_pass_hit": q2_pass_hit,
        "q3_top3_hit": q3_top3_hit,
    }
