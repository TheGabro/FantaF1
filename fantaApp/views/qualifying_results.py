"""Risultati delle qualifiche dentro il campionato (epica #194).

Qualifica del sabato: classifica ufficiale e il proprio pronostico, a un pilota
nei weekend regular (#195), a slot nei weekend sprint (#196). Le pagine si
aprono dal via e, finché mancano i risultati, mostrano lo stato della sessione
(session_state, #103). Un modulo a parte perché views/weekend.py ha già superato
le ~1000 righe (#55).
"""

from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ..models import (
    PlayerQualifyingChoice,
    PlayerQualifyingMultiChoice,
    Qualifying,
    RaceStartingGrid,
)
from ..services import bonuses
from . import session_state as ss
from .weekend import _base_context, _breadcrumb, _origin_query
from .weekend_teams import use_weekend_teams

# Slot della qualifica dei weekend sprint, con i nomi della pagina di scelta.
MULTI_SLOTS = (
    ("q1_pass", "Passano il Q1"),
    ("q2_pass", "Passano il Q2"),
    ("q3_top3", "Top 3 in Q3"),
)
# Livelli a cascata: superare un livello vuol dire aver superato i precedenti.
MULTI_LEVELS = ("q1_pass", "q2_pass", "q3_top3")
MULTI_LEVEL_LABELS = {"q1_pass": "Q1", "q2_pass": "Q2", "q3_top3": "Top 3"}


def _lap_time(duration):
    """Tempo sul giro come sul cronometro: 1:23.456 (None se non c'è)."""
    if duration is None:
        return None
    milliseconds = round(duration.total_seconds() * 1000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{minutes}:{seconds:02d}.{milliseconds:03d}"


def _level_ticks(level):
    """[(etichetta, superato)] per Q1, Q2 e Top 3, a cascata dal livello raggiunto."""
    reached = MULTI_LEVELS.index(level) if level in MULTI_LEVELS else -1
    return [
        (MULTI_LEVEL_LABELS[code], index <= reached)
        for index, code in enumerate(MULTI_LEVELS)
    ]


def _regular_pick(player, qualifying, results):
    """Pronostico a un pilota (weekend regular, #195)."""
    choice = (
        PlayerQualifyingChoice.objects.filter(player=player, qualifying=qualifying)
        .select_related("driver", "driver__team")
        .first()
    )
    if choice is None:
        return None, []
    result = next((r for r in results if r.driver_id == choice.driver_id), None)
    position = result.position if result else None
    # Sconto e moltiplicatore sul GP dipendono dalla griglia del GP
    # (penalità incluse); i punti qualifica dalla classifica della qualifica,
    # con lo stesso calcolo della classifica qualifiche.
    bonus = bonuses.get_regular_qualifying_choice_bonus(
        player=player, qualifying=qualifying
    )
    pick = {
        "driver": choice.driver,
        "position": position,
        "qualifying_points": (
            bonuses.get_regular_qualifying_bonus_rule(position)["qualifying_points"]
            if position
            else 0
        ),
        "grid_position": bonus["position"],
        "credit_change": bonus["credit_change"],
        "points_multiplier": bonus["points_multiplier"],
    }
    return pick, [choice.driver]


def _multi_pick(player, qualifying, results):
    """Pronostico a slot (weekend sprint, #196). Come nel backend, i punti
    qualifica seguono la classifica della qualifica, sconto e moltiplicatore sul
    GP la griglia del GP: i due livelli possono essere diversi."""
    choices = list(
        PlayerQualifyingMultiChoice.objects.filter(player=player, qualifying=qualifying)
        .select_related("driver", "driver__team")
        .order_by("driver__last_name")
    )
    if not choices:
        return None, []
    drivers_by_slot = defaultdict(list)
    for choice in choices:
        drivers_by_slot[choice.selection_slot].append(choice.driver)

    qualifying_level = None
    if results:
        qualifying_level = bonuses.resolve_multichoice_level(
            choices_by_slot={
                slot: [driver.id for driver in drivers]
                for slot, drivers in drivers_by_slot.items()
            },
            results_by_driver_id={r.driver_id: r for r in results},
        )
    grid_bonus = bonuses.get_qualifying_multichoice_bonus(
        player=player, qualifying=qualifying
    )
    pick = {
        "slots": [
            {"label": label, "drivers": drivers_by_slot.get(code, [])}
            for code, label in MULTI_SLOTS
        ],
        "qualifying_ticks": _level_ticks(qualifying_level) if results else None,
        "qualifying_points": (
            bonuses.get_qualifying_multichoice_bonus_rule(qualifying_level)[
                "qualifying_points"
            ]
            if results
            else None
        ),
        "grid_available": RaceStartingGrid.objects.filter(
            race__weekend=qualifying.weekend, race__type="regular"
        ).exists(),
        "grid_ticks": _level_ticks(grid_bonus["level"]),
        "credit_discount": grid_bonus["credit_discount"],
        "points_multiplier": grid_bonus["points_multiplier"],
    }
    return pick, [choice.driver for choice in choices]


@login_required
def race_qualifying_results(request, championship_id, weekend_id, event_id):
    champ, weekend, player = _base_context(request, championship_id, weekend_id)
    qualifying = get_object_or_404(
        Qualifying, pk=event_id, weekend=weekend, type="regular"
    )

    results = list(
        qualifying.qualifying_entries.select_related("driver", "driver__team").order_by(
            F("position").asc(nulls_last=True), "driver__last_name"
        )
    )
    state = ss.session_state(qualifying, has_results=bool(results))
    if state == ss.NOT_STARTED:
        messages.info(request, "I risultati si vedono dal via.")
        return redirect(
            reverse("weekend_details", args=[champ.pk, weekend.pk])
            + _origin_query(request)
        )

    for entry in results:
        entry.q1 = _lap_time(entry.q1_time)
        entry.q2 = _lap_time(entry.q2_time)
        entry.q3 = _lap_time(entry.q3_time)

    is_sprint_weekend = weekend.weekend_type == "sprint"
    pick, picked_drivers = None, []
    if player:
        build_pick = _multi_pick if is_sprint_weekend else _regular_pick
        pick, picked_drivers = build_pick(player, qualifying, results)

    use_weekend_teams(weekend, [entry.driver for entry in results] + picked_drivers)

    return render(
        request,
        "fantaApp/race_qualifying_results.html",
        {
            "championship": champ,
            "weekend": weekend,
            "breadcrumb": _breadcrumb(request, champ, weekend, "Risultati qualifica"),
            "event": qualifying,
            "session_state": state,
            "results": results,
            # None per chi non gioca: vede solo la classifica ufficiale.
            "player": player,
            "pick": pick,
            "is_sprint_weekend": is_sprint_weekend,
            # Nei weekend sprint i piloti scelti sono 14: non si evidenziano.
            "selected_driver_id": (
                pick["driver"].id if pick and not is_sprint_weekend else None
            ),
        },
    )
