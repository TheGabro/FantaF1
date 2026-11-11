"""Scelte dei giocatori nelle Qualifiche del sabato: a un pilota nei weekend
regular (#205), a slot nei weekend sprint (#206).

Gli stessi numeri della pagina dei risultati (#195, #196) e della classifica
qualifiche: i punti qualifica dalla classifica delle Qualifiche, sconto (o
malus) e moltiplicatore sul GP dalla griglia del Gran Premio, penalità incluse.
I punti qualifica non sono salvati (#166): si calcolano al volo con le tabelle
di rules.py.
"""

from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from ...models import (
    PlayerQualifyingChoice,
    PlayerQualifyingMultiChoice,
    Qualifying,
    RaceStartingGrid,
)
from ...services import bonuses
from ..qualifying_results import _level_ticks
from ..weekend_teams import use_weekend_teams
from ._common import PLAYER_SORTS, page_access, page_context, sort_headers, sort_rows

REGULAR_SORTS = {
    **PLAYER_SORTS,
    "position": (lambda row: row["position"], "asc"),
    "points": (lambda row: row["qualifying_points"], "desc"),
    "grid": (lambda row: row["grid_position"], "asc"),
}
# Nei weekend sprint i punti e lo sconto crescono col livello raggiunto.
MULTI_SORTS = {
    **PLAYER_SORTS,
    "points": (lambda row: row["qualifying_points"], "desc"),
    "discount": (lambda row: row["credit_discount"], "desc"),
}


@login_required
def race_qualifying_all_choices(request, championship_id, weekend_id, event_id):
    champ, weekend, player, denied = page_access(request, championship_id, weekend_id)
    if denied:
        return denied
    qualifying = get_object_or_404(
        Qualifying, pk=event_id, weekend=weekend, type="regular"
    )
    qualifying.weekend = weekend  # già caricato: niente query in più
    is_sprint_weekend = weekend.weekend_type == "sprint"
    picks = qualifying_picks(qualifying, champ)
    template = (
        "fantaApp/all_choices/race_qualifying_multi.html"
        if is_sprint_weekend
        else "fantaApp/all_choices/race_qualifying.html"
    )

    context = page_context(
        request,
        champ,
        weekend,
        player,
        qualifying,
        label="Qualifiche",
        chose=lambda p: p.id in picks,
    )
    context["session_of"] = "delle Qualifiche"
    if not context["started"]:
        # Prima del via solo i numeri: chi ha scelto cosa resta nascosto.
        return render(request, template, context)

    results, grid = qualifying_outcomes(qualifying)
    shown = context["shown"]
    if not is_sprint_weekend:
        use_weekend_teams(weekend, [picks[p.id].driver for p in shown if p.id in picks])
    rows = [
        qualifying_row(qualifying, p, picks.get(p.id), results, grid) for p in shown
    ]
    sorts = MULTI_SORTS if is_sprint_weekend else REGULAR_SORTS

    sort, direction = sort_rows(request, rows, sorts)
    context.update(
        {
            "rows": rows,
            "headers": sort_headers(context["league_param"], sort, direction, sorts),
            "has_results": bool(results),
            "has_grid": bool(grid),
        }
    )
    return render(request, template, context)


# Usate anche dal riepilogo del weekend (#208), così i punti qualifica sono
# gli stessi delle due pagine.
def qualifying_picks(qualifying, champ):
    """{player_id: scelta} dei giocatori del campionato. Nei weekend sprint la
    scelta è {slot: [driver_id]}: si mostrano solo gli esiti, bastano gli id."""
    if qualifying.weekend.weekend_type == "sprint":
        picks = defaultdict(lambda: defaultdict(list))
        for player_id, slot, driver_id in PlayerQualifyingMultiChoice.objects.filter(
            qualifying=qualifying, player__championship=champ
        ).values_list("player_id", "selection_slot", "driver_id"):
            picks[player_id][slot].append(driver_id)
        return picks
    return {
        choice.player_id: choice
        for choice in PlayerQualifyingChoice.objects.filter(
            qualifying=qualifying, player__championship=champ
        ).select_related("driver", "driver__team")
    }


def qualifying_outcomes(qualifying):
    """(classifica, griglia del GP), ognuna per driver_id: vuote finché non ci sono."""
    results = {entry.driver_id: entry for entry in qualifying.qualifying_entries.all()}
    grid = {
        row.driver_id: row
        for row in RaceStartingGrid.objects.filter(
            race__weekend=qualifying.weekend, race__type="regular"
        )
    }
    return results, grid


def qualifying_row(qualifying, player, pick, results, grid):
    """La riga del giocatore secondo il tipo di weekend."""
    if qualifying.weekend.weekend_type == "sprint":
        return _multi_row(player, pick, results, grid)
    return _regular_row(player, pick, results, grid)


def _regular_row(player, choice, results, grid):
    """Weekend regular (#205): il pilota scelto, posizione e punti qualifica in
    classifica, posizione in griglia con sconto o malus e moltiplicatore."""
    row = {
        "player": player,
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
    return row


def _multi_row(player, choices_by_slot, results, grid):
    """Weekend sprint (#206): solo gli esiti, Q1, Q2 e Top 3 a cascata. Due
    livelli come nel backend: in classifica per i punti qualifica, sulla
    griglia del GP per sconto e moltiplicatore."""
    row = {
        "player": player,
        "chose": choices_by_slot is not None,
        "qualifying_ticks": None,
        "qualifying_points": None,
        "grid_ticks": None,
        "credit_discount": None,
        "points_multiplier": None,
    }
    if choices_by_slot and results:
        level = bonuses.resolve_multichoice_level(
            choices_by_slot=choices_by_slot, results_by_driver_id=results
        )
        row["qualifying_ticks"] = _level_ticks(level)
        row["qualifying_points"] = bonuses.get_qualifying_multichoice_bonus_rule(level)[
            "qualifying_points"
        ]
    if choices_by_slot and grid:
        # Come get_qualifying_multichoice_bonus.
        level = bonuses.resolve_multichoice_level(
            choices_by_slot=choices_by_slot, results_by_driver_id=grid, on_grid=True
        )
        rule = bonuses.get_qualifying_multichoice_bonus_rule(level)
        row["grid_ticks"] = _level_ticks(level)
        row["credit_discount"] = rule["credit_discount"]
        row["points_multiplier"] = rule["points_multiplier"]
    return row
