"""Scelte dei giocatori nel Gran Premio (#203)."""

from collections import defaultdict
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ...models import ChampionshipPlayer, PlayerRaceChoice, PlayerRaceResult, Race
from ...services import helper
from ..weekend import _base_context, _breadcrumb
from ..weekend_teams import use_weekend_teams

# Colonne ordinabili: chiave -> (valore della riga, ordine di partenza).
# I numeri partono dal più alto; chi non ha un valore va sempre in fondo.
SORTS = {
    "name": (lambda row: row["player"].player_name.lower(), "asc"),
    "league": (lambda row: row["player"].league.name.lower(), "asc"),
    "spent": (lambda row: row["spent"] if row["choices"] else None, "desc"),
    "points": (
        lambda row: row["result"].total_points if row["result"] else None,
        "desc",
    ),
}


@login_required
def regular_race_all_choices(request, championship_id, weekend_id, event_id):
    """Scelte di tutti i giocatori nel GP: dal via, una riga per giocatore con
    piloti, pupillo, fantamilioni spesi e punti; prima del via solo quanti hanno
    scelto. Solo per i giocatori e i manager del campionato (#202)."""
    champ, weekend, player = _base_context(request, championship_id, weekend_id)
    if player is None and not helper.is_championship_manager(request.user, champ):
        messages.error(
            request,
            "Le scelte dei giocatori le vedono solo i giocatori e i manager del campionato.",
        )
        return redirect("championship_dashboard", championship_id=champ.pk)
    race = get_object_or_404(Race, pk=event_id, weekend=weekend, type="regular")

    players = list(
        ChampionshipPlayer.objects.filter(championship=champ)
        .select_related("league")
        .order_by("player_name")
    )
    choices_by_player = defaultdict(list)
    for choice in (
        PlayerRaceChoice.objects.filter(race=race, player__championship=champ)
        .select_related("driver", "driver__team")
        .order_by("-is_pupillo", "driver__last_name")
    ):
        choices_by_player[choice.player_id].append(choice)

    # Filtro per lega: la propria preselezionata, «Tutte» per chi non gioca.
    leagues = list(champ.leagues.order_by("id"))
    league_param = request.GET.get("league")
    if league_param is None:
        league_param = str(player.league_id) if player else "all"
    league_ids = {str(league.id) for league in leagues}
    if league_param != "all" and league_param not in league_ids:
        league_param = "all"
    shown = [
        p for p in players if league_param == "all" or str(p.league_id) == league_param
    ]

    started = helper._event_has_started(race)
    context = {
        "championship": champ,
        "weekend": weekend,
        "breadcrumb": _breadcrumb(
            request, champ, weekend, "Scelte dei giocatori · Gran Premio"
        ),
        "race": race,
        "race_start": helper.event_start(race),
        "started": started,
        "player": player,
        "league_param": league_param,
        "league_filters": _league_filters(request, leagues, league_param),
        "shown_count": len(shown),
        "chosen_count": sum(1 for p in shown if choices_by_player[p.id]),
    }
    if not started:
        # Prima del via solo i numeri: chi ha scelto cosa resta nascosto.
        return render(request, "fantaApp/all_choices/regular_race.html", context)

    results = {
        result.player_id: result
        for result in PlayerRaceResult.objects.filter(
            race=race, player__championship=champ
        )
    }
    use_weekend_teams(
        weekend,
        [c.driver for p in shown for c in choices_by_player[p.id]],
    )
    rows = [
        {
            "player": p,
            "choices": choices_by_player[p.id],
            "spent": sum(c.spent_amount for c in choices_by_player[p.id]),
            "result": results.get(p.id),
        }
        for p in shown
    ]
    sort, direction = _sort_rows(request, rows)
    context.update(
        {
            "rows": rows,
            "headers": _sort_headers(league_param, sort, direction),
        }
    )
    return render(request, "fantaApp/all_choices/regular_race.html", context)


def _sort_rows(request, rows):
    """Ordina le righe secondo ?sort= e ?dir=; senza parametri per nome."""
    sort = request.GET.get("sort")
    if sort not in SORTS:
        sort = "name"
    key, default_direction = SORTS[sort]
    direction = request.GET.get("dir")
    if direction not in ("asc", "desc"):
        direction = default_direction
    # Prima per nome, poi per la colonna scelta: a parità resta l'ordine alfabetico.
    rows.sort(key=SORTS["name"][0])
    with_value = [row for row in rows if key(row) is not None]
    without_value = [row for row in rows if key(row) is None]
    with_value.sort(key=key, reverse=direction == "desc")
    rows[:] = with_value + without_value
    return sort, direction


def _sort_headers(league_param, sort, direction):
    """Intestazioni cliccabili: un clic ordina per quella colonna, un secondo
    clic sulla stessa inverte l'ordine. Il filtro di lega resta."""
    headers = {}
    for key, (_, default_direction) in SORTS.items():
        if key == sort:
            next_direction = "asc" if direction == "desc" else "desc"
        else:
            next_direction = default_direction
        headers[key] = {
            "url": "?"
            + urlencode({"league": league_param, "sort": key, "dir": next_direction}),
            "active": key == sort,
            "arrow": ("▲" if direction == "asc" else "▼") if key == sort else "",
        }
    return headers


def _league_filters(request, leagues, league_param):
    """Pulsanti «Tutte · Lega A · …», mantenendo l'ordinamento scelto."""
    keep = {k: request.GET[k] for k in ("sort", "dir") if request.GET.get(k)}
    filters = [
        {
            "label": "Tutte",
            "url": "?" + urlencode({"league": "all", **keep}),
            "active": league_param == "all",
        }
    ]
    for league in leagues:
        filters.append(
            {
                "label": league.name,
                "url": "?" + urlencode({"league": league.id, **keep}),
                "active": league_param == str(league.id),
            }
        )
    return filters
