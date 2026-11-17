from django.shortcuts import render

from ...services import rules
from ..rulebook import rulebook

# Gran Premi della stagione, per la media dei fantamilioni a weekend nei consigli
# (#260): 24 sia nel 2026 sia nel 2027.
SEASON_GRANDS_PRIX = 24


def _tips(book):
    """Numeri dei consigli (#260), letti dalle tabelle del regolamento: se le
    regole cambiano, i consigli le seguono."""
    grid = rules.REGULAR_RACE_COST_BY_GRID_POSITION
    sprint_grid = rules.SPRINT_RACE_COST_BY_GRID_POSITION
    standings = rules.COST_BY_STANDINGS_POSITION
    qualifying = rules.REGULAR_QUALIFYING_BONUS_BY_POSITION
    top3 = rules.QUALIFYING_MULTICHOICE_BONUS_RULES["q3_top3"]
    sprint_free_from = min(p for p, cost in sprint_grid.items() if not cost)
    multiplied = {p: v for p, v in qualifying.items() if v["points_multiplier"] > 1}
    return {
        "grands_prix": SEASON_GRANDS_PRIX,
        "per_weekend": book["starting_credit"] // SEASON_GRANDS_PRIX,
        "pole_cost": grid[1],
        "standings_first": standings[1],
        "standings_last_position": max(standings),
        "pole_with_leader": grid[1] + standings[1],
        "grid_free_from": min(p for p, cost in grid.items() if not cost),
        "pole": qualifying[1],
        "last": qualifying[max(qualifying)],
        # Prima casella (dal fondo) da cui la qualifica moltiplica i punti del GP.
        "multiplier_from": max(multiplied),
        "first_multiplier": multiplied[max(multiplied)]["points_multiplier"],
        "top3": top3,
        "example_points": 25,
        "example_points_doubled": 25 * top3["points_multiplier"],
        # Pupillo a sconto pieno che costa il doppio dello sconto: lo paghi metà.
        "pupillo_example_cost": 2 * book["pupillo_max"],
        "seventh_cost": grid[7],
        "sprint_pole_cost": sprint_grid[1],
        "sprint_free_from": sprint_free_from,
        "sprint_example_position": sprint_free_from + 1,
        "shootout_max_discount": max(
            v["credit_discount"] for v in rules.SPRINT_BONUS_RULES.values()
        ),
        "shootout_max_points": max(
            v["points_modifier"] for v in rules.SPRINT_BONUS_RULES.values()
        ),
    }


def faq(request):
    """Domande frequenti sul gioco (#229), aperte a tutti. Le risposte seguono
    il regolamento 2026 e i numeri vengono dalle stesse tabelle del regolamento
    pubblico (#81); ogni risposta porta alla sezione che la spiega per intero."""
    book = rulebook()
    return render(
        request,
        "fantaApp/game_faq.html",
        {
            "rulebook": book,
            "tips": _tips(book),
            # Extra da classifica piloti: il primo e l'ultimo posto che costano.
            "standings_extra_first": rules.COST_BY_STANDINGS_POSITION[1],
            "standings_extra_last_position": max(rules.COST_BY_STANDINGS_POSITION),
            "standings_extra_last": rules.COST_BY_STANDINGS_POSITION[
                max(rules.COST_BY_STANDINGS_POSITION)
            ],
        },
    )
