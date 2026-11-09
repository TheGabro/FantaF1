"""Risultati delle qualifiche dentro il campionato (epica #194).

Qualifica del sabato dei weekend regular (#195): classifica ufficiale e il
proprio pronostico. Le pagine si aprono dal via e, finché mancano i risultati,
mostrano lo stato della sessione (session_state, #103). Un modulo a parte
perché views/weekend.py ha già superato le ~1000 righe (#55).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ..models import PlayerQualifyingChoice, Qualifying
from ..services import bonuses
from . import session_state as ss
from .weekend import _base_context, _breadcrumb, _origin_query
from .weekend_teams import use_weekend_teams


def _lap_time(duration):
    """Tempo sul giro come sul cronometro: 1:23.456 (None se non c'è)."""
    if duration is None:
        return None
    milliseconds = round(duration.total_seconds() * 1000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{minutes}:{seconds:02d}.{milliseconds:03d}"


@login_required
def race_qualifying_results(request, championship_id, weekend_id, event_id):
    champ, weekend, player = _base_context(request, championship_id, weekend_id)
    qualifying = get_object_or_404(
        Qualifying, pk=event_id, weekend=weekend, type="regular"
    )
    # La qualifica a slot dei weekend sprint ha la sua pagina con #196.
    if weekend.weekend_type == "sprint":
        raise Http404

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

    choice = (
        PlayerQualifyingChoice.objects.filter(player=player, qualifying=qualifying)
        .select_related("driver", "driver__team")
        .first()
    )
    pick = None
    if choice:
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

    use_weekend_teams(
        weekend,
        [entry.driver for entry in results] + ([choice.driver] if choice else []),
    )

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
            "selected_driver_id": choice.driver_id if choice else None,
        },
    )
