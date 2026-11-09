"""Regolamento del gioco letto dalle tabelle di services/rules.py (#81).

È la stessa sorgente usata dal calcolo dei punti e dei costi: le tabelle mostrate
non possono divergere dal gioco vero. Lo usa la pagina pubblica del regolamento;
prima stava nella scheda Info di ogni campionato (#230).
"""

from ..models import ChampionshipPlayer
from ..services import rules
from .dashboard import MAGATA_POINTS, SUCATA_POINTS

# Etichette leggibili dei livelli bonus, per le tabelle del regolamento.
_SLOTS = rules.MULTI_CHOICE_SLOT_SIZES
_MULTICHOICE_LEVEL_LABELS = {
    "q1_pass": f"Tutti e {_SLOTS['q1_pass']} i piloti indicati passano il Q1",
    "q2_pass": f"…e tutti e {_SLOTS['q2_pass']} quelli del secondo slot passano il Q2",
    "q3_top3": f"…e la top {_SLOTS['q3_top3']} del Q3 è indovinata in pieno",
}
_SHOOTOUT_LEVEL_LABELS = {
    "made": "Pronostico fatto, nessuna fascia indovinata",
    "sq1_hit": "Indovinata la fascia oltre la 15ª",
    "sq2_hit": "Indovinata la fascia 11-15",
    "sq3_hit": "Indovinata la fascia 6-10",
}


def rulebook():
    """Tabelle e valori del regolamento, pronti per il template."""
    grid_costs = [
        {
            "position": position,
            "regular": cost,
            "sprint": rules.SPRINT_RACE_COST_BY_GRID_POSITION.get(position, 0),
            "standings_extra": rules.COST_BY_STANDINGS_POSITION.get(position),
        }
        for position, cost in sorted(rules.REGULAR_RACE_COST_BY_GRID_POSITION.items())
        # Oltre una certa casella il costo è zero ovunque: righe inutili da mostrare.
        if cost or rules.SPRINT_RACE_COST_BY_GRID_POSITION.get(position, 0)
    ]
    return {
        "regular_qualifying": [
            {"position": position, **values}
            for position, values in sorted(
                rules.REGULAR_QUALIFYING_BONUS_BY_POSITION.items()
            )
        ],
        "multichoice": [
            {
                "label": _MULTICHOICE_LEVEL_LABELS[level],
                **rules.QUALIFYING_MULTICHOICE_BONUS_RULES[level],
            }
            for level in ("q1_pass", "q2_pass", "q3_top3")
        ],
        "shootout": [
            {"label": _SHOOTOUT_LEVEL_LABELS[level], **rules.SPRINT_BONUS_RULES[level]}
            for level in ("made", "sq1_hit", "sq2_hit", "sq3_hit")
        ],
        "grid_costs": grid_costs,
        # Prima casella in cui il pilota non costa nulla, né nel GP né nella Sprint.
        "free_from_position": grid_costs[-1]["position"] + 1 if grid_costs else 1,
        "starting_credit": ChampionshipPlayer._meta.get_field(
            "available_credit"
        ).default,
        "pupillo_step": rules.PUPILLO_DISCOUNT_STEP,
        "pupillo_max": rules.PUPILLO_MAX_DISCOUNT,
        "max_picks_per_team": rules.REGULAR_QUALIFYING_MAX_PICKS_PER_TEAM,
        "magata_points": MAGATA_POINTS,
        "sucata_points": SUCATA_POINTS,
        "multi_choice_slot_sizes": rules.MULTI_CHOICE_SLOT_SIZES,
        "grid_q1_pass_max_position": rules.GRID_Q1_PASS_MAX_POSITION,
        "grid_q2_pass_max_position": rules.GRID_Q2_PASS_MAX_POSITION,
    }
