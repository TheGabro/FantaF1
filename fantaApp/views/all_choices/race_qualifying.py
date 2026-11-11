"""Scelte dei giocatori nelle Qualifiche del sabato, weekend regular (#205).

Per ogni giocatore il pilota scelto e com'è andato: posizione e punti qualifica
dalla classifica delle Qualifiche, sconto o malus e moltiplicatore sul GP dalla
griglia del Gran Premio (penalità incluse), come nella pagina dei risultati
(#195) e nella classifica qualifiche. I punti qualifica non sono salvati (#166):
si calcolano al volo con le tabelle di rules.py.
"""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from ...models import PlayerQualifyingChoice, Qualifying, RaceStartingGrid
from ...services import bonuses
from ..weekend_teams import use_weekend_teams
from ._common import PLAYER_SORTS, page_access, page_context, sort_headers, sort_rows

SORTS = {
    **PLAYER_SORTS,
    "position": (lambda row: row["position"], "asc"),
    "points": (lambda row: row["qualifying_points"], "desc"),
    "grid": (lambda row: row["grid_position"], "asc"),
}


@login_required
def race_qualifying_all_choices(request, championship_id, weekend_id, event_id):
    champ, weekend, player, denied = page_access(request, championship_id, weekend_id)
    if denied:
        return denied
    qualifying = get_object_or_404(
        Qualifying, pk=event_id, weekend=weekend, type="regular"
    )
    if weekend.weekend_type == "sprint":
        # La qualifica a slot dei weekend sprint avrà la sua pagina (#206).
        raise Http404

    choices = {
        choice.player_id: choice
        for choice in PlayerQualifyingChoice.objects.filter(
            qualifying=qualifying, player__championship=champ
        ).select_related("driver", "driver__team")
    }
    context = page_context(
        request,
        champ,
        weekend,
        player,
        qualifying,
        label="Qualifiche",
        chose=lambda p: p.id in choices,
    )
    context["session_of"] = "delle Qualifiche"
    if not context["started"]:
        # Prima del via solo i numeri: chi ha scelto cosa resta nascosto.
        return render(request, "fantaApp/all_choices/race_qualifying.html", context)

    results = {entry.driver_id: entry for entry in qualifying.qualifying_entries.all()}
    grid = {
        row.driver_id: row
        for row in RaceStartingGrid.objects.filter(
            race__weekend=weekend, race__type="regular"
        )
    }
    shown = context["shown"]
    use_weekend_teams(weekend, [choices[p.id].driver for p in shown if p.id in choices])

    rows = []
    for p in shown:
        choice = choices.get(p.id)
        row = {
            "player": p,
            "driver": choice.driver if choice else None,
            "position": None,
            "qualifying_points": None,
            "grid_position": None,
            "credit_change": None,
            "points_multiplier": None,
        }
        if choice and results:
            # Come la classifica qualifiche: 0 punti a un pilota non classificato.
            result = results.get(choice.driver_id)
            row["position"] = result.position if result else None
            row["qualifying_points"] = (
                bonuses.get_regular_qualifying_bonus_rule(row["position"])[
                    "qualifying_points"
                ]
                if row["position"]
                else 0
            )
        if choice and grid:
            # Come get_regular_qualifying_choice_bonus: fuori dalla griglia
            # nessuna variazione e moltiplicatore 1.
            grid_row = grid.get(choice.driver_id)
            row["grid_position"] = grid_row.position if grid_row else None
            rule = bonuses.get_regular_qualifying_bonus_rule(row["grid_position"])
            row["credit_change"] = rule["credit_change"]
            row["points_multiplier"] = rule["points_multiplier"]
        rows.append(row)

    sort, direction = sort_rows(request, rows, SORTS)
    context.update(
        {
            "rows": rows,
            "headers": sort_headers(context["league_param"], sort, direction, SORTS),
            "has_results": bool(results),
            "has_grid": bool(grid),
        }
    )
    return render(request, "fantaApp/all_choices/race_qualifying.html", context)
