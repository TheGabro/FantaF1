"""Parti comuni delle pagine «Scelte dei giocatori» (epica #202): accesso,
filtro per lega, ordinamento e righe delle gare (GP #203, Sprint #204). Le
qualifiche hanno righe proprie nei loro moduli (#205)."""

from collections import defaultdict
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from ...models import ChampionshipPlayer, PlayerRaceChoice, PlayerRaceResult, Race
from ...services import helper
from ..weekend import _base_context, _breadcrumb
from ..weekend_teams import use_weekend_teams
from .links import session_nav

# Colonne ordinabili: chiave -> (valore della riga, ordine di partenza).
# I numeri partono dal più alto; chi non ha un valore va sempre in fondo.
# Ogni pagina aggiunge le sue a queste due.
PLAYER_SORTS = {
    "name": (lambda row: row["player"].player_name.lower(), "asc"),
    "league": (lambda row: row["player"].league.name.lower(), "asc"),
}
RACE_SORTS = {
    **PLAYER_SORTS,
    "spent": (lambda row: row["spent"] if row["choices"] else None, "desc"),
    "points": (lambda row: row["points"], "desc"),
}


def page_access(request, championship_id, weekend_id):
    """(campionato, weekend, giocatore, rimando). Le scelte di tutti le vedono
    solo i giocatori e i manager del campionato: per gli altri il rimando alla
    pagina del campionato, già col messaggio; altrimenti None."""
    champ, weekend, player = _base_context(request, championship_id, weekend_id)
    if player is None and not helper.is_championship_manager(request.user, champ):
        messages.error(
            request,
            "Le scelte dei giocatori le vedono solo i giocatori e i manager del campionato.",
        )
        return (
            champ,
            weekend,
            player,
            redirect("championship_dashboard", championship_id=champ.pk),
        )
    return champ, weekend, player, None


def page_context(
    request, champ, weekend, player, event, *, label, chose, current, sessions=None
):
    """Contesto comune a tutte le pagine: percorso, barra delle sessioni e
    pulsante «Risultati» (#282), filtro per lega, conteggio di chi ha scelto e
    se la sessione è iniziata. `chose(giocatore)` dice se quel giocatore ha
    scelto; `current` è la sessione aperta, come in links.session_nav. Le
    righe da mostrare stanno in context["shown"]."""
    players = list(
        ChampionshipPlayer.objects.filter(championship=champ)
        .select_related("league")
        .order_by("player_name")
    )
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

    return {
        "championship": champ,
        "weekend": weekend,
        "breadcrumb": _breadcrumb(
            request, champ, weekend, f"Scelte dei giocatori · {label}"
        ),
        **session_nav(request, champ, weekend, current, sessions),
        "session_label": label,
        "event_start": helper.event_start(event),
        "started": helper._event_has_started(event),
        "player": player,
        "league_param": league_param,
        "league_filters": _league_filters(request, leagues, league_param),
        "shown": shown,
        "shown_count": len(shown),
        "chosen_count": sum(1 for p in shown if chose(p)),
    }


def render_race_all_choices(
    request, championship_id, weekend_id, event_id, *, race_type, label
):
    """Scelte di tutti i giocatori in una gara: dal via una riga per giocatore
    con piloti, fantamilioni spesi e punti; prima del via solo quanti hanno
    scelto. Solo per i giocatori e i manager del campionato (#202).

    I punti della riga sono quelli della sola gara: nel GP il totale (punti F1 ×
    moltiplicatore della qualifica), nella Sprint i punti F1, senza il bonus
    delle Qualifiche Sprint che ha la sua pagina (#207)."""
    champ, weekend, player, denied = page_access(request, championship_id, weekend_id)
    if denied:
        return denied
    race = get_object_or_404(Race, pk=event_id, weekend=weekend, type=race_type)

    choices_by_player = defaultdict(list)
    for choice in (
        PlayerRaceChoice.objects.filter(race=race, player__championship=champ)
        .select_related("driver", "driver__team")
        .order_by("-is_pupillo", "driver__last_name")
    ):
        choices_by_player[choice.player_id].append(choice)

    context = page_context(
        request,
        champ,
        weekend,
        player,
        race,
        label=label,
        chose=lambda p: bool(choices_by_player[p.id]),
        current=("race", race_type),
    )
    is_sprint = race_type == "sprint"
    context.update(
        {
            "race": race,
            "is_sprint": is_sprint,
            "session_of": "della Sprint" if is_sprint else "del Gran Premio",
        }
    )
    if not context["started"]:
        # Prima del via solo i numeri: chi ha scelto cosa resta nascosto.
        return render(request, "fantaApp/all_choices/race.html", context)

    shown = context["shown"]
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
    rows = []
    for p in shown:
        result = results.get(p.id)
        if result is None:
            points = None
        elif is_sprint:
            points = result.fia_points
        else:
            points = result.total_points
        rows.append(
            {
                "player": p,
                "choices": choices_by_player[p.id],
                "spent": sum(c.spent_amount for c in choices_by_player[p.id]),
                "result": result,
                "points": points,
            }
        )
    sort, direction = sort_rows(request, rows, RACE_SORTS)
    context.update(
        {
            "rows": rows,
            "headers": sort_headers(
                request, context["league_param"], sort, direction, RACE_SORTS
            ),
        }
    )
    return render(request, "fantaApp/all_choices/race.html", context)


def sort_rows(request, rows, sorts):
    """Ordina le righe secondo ?sort= e ?dir=; senza parametri per nome."""
    sort = request.GET.get("sort")
    if sort not in sorts:
        sort = "name"
    key, default_direction = sorts[sort]
    direction = request.GET.get("dir")
    if direction not in ("asc", "desc"):
        direction = default_direction
    # Prima per nome, poi per la colonna scelta: a parità resta l'ordine alfabetico.
    rows.sort(key=sorts["name"][0])
    with_value = [row for row in rows if key(row) is not None]
    without_value = [row for row in rows if key(row) is None]
    with_value.sort(key=key, reverse=direction == "desc")
    rows[:] = with_value + without_value
    return sort, direction


def sort_headers(request, league_param, sort, direction, sorts):
    """Intestazioni cliccabili: un clic ordina per quella colonna, un secondo
    clic sulla stessa inverte l'ordine. Il filtro di lega e la pagina di
    partenza del percorso restano."""
    origin = _origin_params(request)
    headers = {}
    for key, (_, default_direction) in sorts.items():
        if key == sort:
            next_direction = "asc" if direction == "desc" else "desc"
        else:
            next_direction = default_direction
        headers[key] = {
            "url": "?"
            + urlencode(
                {
                    "league": league_param,
                    "sort": key,
                    "dir": next_direction,
                    **origin,
                }
            ),
            "active": key == sort,
            "arrow": ("▲" if direction == "asc" else "▼") if key == sort else "",
        }
    return headers


def _origin_params(request):
    """{"from": "play"} se si è partiti da Prossimo weekend (#156), così il
    percorso in alto non cambia filtrando o ordinando."""
    return {"from": "play"} if request.GET.get("from") == "play" else {}


def _league_filters(request, leagues, league_param):
    """Pulsanti «Tutte · Lega A · …», mantenendo l'ordinamento scelto e la
    pagina di partenza del percorso."""
    keep = {k: request.GET[k] for k in ("sort", "dir") if request.GET.get(k)}
    keep.update(_origin_params(request))
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
