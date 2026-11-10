from django.shortcuts import render

from ...services import rules
from ..rulebook import rulebook

# Valori del regolamento che services/rules.py non ha ancora: restano qui, in un
# punto solo, finché il backend non li aggiunge (penalità C.3: #154; fasce delle
# Qualifiche Sprint: #257). Poi si leggono da rules.py come il resto.
PENALTY_POINTS_STEP = 5
PENALTY_FREE_MISSES = 2
SPRINT_SHOOTOUT_CUTS = {"sq1": 16, "sq2": 10, "sq3": 5}


def faq(request):
    """Domande frequenti sul gioco (#229), aperte a tutti. Le risposte seguono
    il regolamento 2026 e i numeri vengono dalle stesse tabelle del regolamento
    pubblico (#81); ogni risposta porta alla sezione che la spiega per intero."""
    return render(
        request,
        "fantaApp/game_faq.html",
        {
            "rulebook": rulebook(),
            "penalty_points_step": PENALTY_POINTS_STEP,
            "penalty_first_points_miss": PENALTY_FREE_MISSES + 1,
            "penalty_examples": [PENALTY_POINTS_STEP * n for n in (1, 2, 3)],
            "shootout_cuts": SPRINT_SHOOTOUT_CUTS,
            # Extra da classifica piloti: il primo e l'ultimo posto che costano.
            "standings_extra_first": rules.COST_BY_STANDINGS_POSITION[1],
            "standings_extra_last_position": max(rules.COST_BY_STANDINGS_POSITION),
            "standings_extra_last": rules.COST_BY_STANDINGS_POSITION[
                max(rules.COST_BY_STANDINGS_POSITION)
            ],
        },
    )
