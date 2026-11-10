from django.shortcuts import render

from ...services import rules
from ..rulebook import rulebook


def faq(request):
    """Domande frequenti sul gioco (#229), aperte a tutti. Le risposte seguono
    il regolamento 2026 e i numeri vengono dalle stesse tabelle del regolamento
    pubblico (#81); ogni risposta porta alla sezione che la spiega per intero."""
    return render(
        request,
        "fantaApp/game_faq.html",
        {
            "rulebook": rulebook(),
            # Extra da classifica piloti: il primo e l'ultimo posto che costano.
            "standings_extra_first": rules.COST_BY_STANDINGS_POSITION[1],
            "standings_extra_last_position": max(rules.COST_BY_STANDINGS_POSITION),
            "standings_extra_last": rules.COST_BY_STANDINGS_POSITION[
                max(rules.COST_BY_STANDINGS_POSITION)
            ],
        },
    )
