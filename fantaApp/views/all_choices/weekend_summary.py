"""Riepilogo del weekend per giocatore (#208).

Una riga per giocatore con le somme del weekend: fantamilioni spesi (GP, più
Sprint nei weekend sprint), punti del weekend e punti qualifica. Sotto ogni riga
il dettaglio per sessione, con gli stessi numeri delle pagine delle sessioni:
- Qualifiche Sprint: il bonus sulla Sprint (point_modifier del risultato della
  Sprint: si conosce quando la Sprint è calcolata);
- Sprint: fantamilioni e punti F1, senza il bonus;
- Qualifiche: punti qualifica, come la pagina #205/#206;
- Gran Premio: fantamilioni e totale (punti F1 × moltiplicatore).
I punti del weekend sono la somma dei total_points di Sprint e GP, come nelle
classifiche: punti F1 della Sprint + bonus + totale del GP.

Si apre dal via della prima sessione; le sessioni non ancora iniziate restano
«da disputare», senza nessun dato, così le scelte non si copiano.
"""

from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from ...models import PlayerRaceChoice, PlayerRaceResult, PlayerSprintQualifyingChoice
from ..dashboard import _weekend_sessions
from ._common import PLAYER_SORTS, page_access, page_context, sort_headers, sort_rows
from .links import SUMMARY
from .race_qualifying import qualifying_outcomes, qualifying_picks, qualifying_row

SORTS = {
    **PLAYER_SORTS,
    "spent": (lambda row: row["spent"], "desc"),
    "points": (lambda row: row["points"], "desc"),
    "qualifying_points": (lambda row: row["qualifying_points"], "desc"),
}
# «dal via …» nel testo prima della prima sessione.
SESSION_OF = {
    "Qualifiche Sprint": "delle Qualifiche Sprint",
    "Sprint": "della Sprint",
    "Qualifiche": "delle Qualifiche",
    "Gran Premio": "del Gran Premio",
}


@login_required
def weekend_all_choices(request, championship_id, weekend_id):
    champ, weekend, player, denied = page_access(request, championship_id, weekend_id)
    if denied:
        return denied
    sessions = _weekend_sessions(weekend)
    if not sessions:
        raise Http404

    # Scelte di tutte le sessioni, una query per tipo.
    spent_by_race_player = defaultdict(list)
    for race_id, player_id, spent in PlayerRaceChoice.objects.filter(
        race__weekend=weekend, player__championship=champ
    ).values_list("race_id", "player_id", "spent_amount"):
        spent_by_race_player[(race_id, player_id)].append(spent)
    for session in sessions:
        event = session["event"]
        if session["entity"] == "race":
            # Come le pagine #203/#204: i fantamilioni delle scelte.
            session["spent"] = {
                player_id: sum(amounts)
                for (race_id, player_id), amounts in spent_by_race_player.items()
                if race_id == event.id
            }
            session["chosen"] = set(session["spent"])
        elif session["subtype"] == "sprint":
            session["chosen"] = set(
                PlayerSprintQualifyingChoice.objects.filter(
                    qualifying=event, player__championship=champ
                ).values_list("player_id", flat=True)
            )
        else:
            session["picks"] = qualifying_picks(event, champ)
            session["chosen"] = set(session["picks"])

    # La prima sessione con un orario (#242: a volte le Qualifiche Sprint non
    # ce l'hanno); il riepilogo si apre appena una qualsiasi è iniziata.
    first = next((s for s in sessions if s["start"]), sessions[0])
    context = page_context(
        request,
        champ,
        weekend,
        player,
        first["event"],
        label="Riepilogo del weekend",
        chose=lambda p: any(p.id in s["chosen"] for s in sessions),
        current=SUMMARY,
        sessions=sessions,
    )
    shown = context["shown"]
    context.update(
        {
            "started": any(s["has_started"] for s in sessions),
            "session_of": SESSION_OF[first["label"]],
            "session_counts": [
                {
                    "label": s["label"],
                    "chosen": sum(1 for p in shown if p.id in s["chosen"]),
                }
                for s in sessions
            ],
        }
    )
    if not context["started"]:
        # Prima del via solo i numeri: chi ha scelto cosa resta nascosto.
        return render(request, "fantaApp/all_choices/weekend.html", context)

    results = {
        (result.race_id, result.player_id): result
        for result in PlayerRaceResult.objects.filter(
            race__weekend=weekend, player__championship=champ
        )
    }
    sprint = next(
        (
            s["event"]
            for s in sessions
            if s["entity"] == "race" and s["subtype"] == "sprint"
        ),
        None,
    )
    for session in sessions:
        if "picks" in session and session["has_started"]:
            session["outcomes"] = qualifying_outcomes(session["event"])

    # Nel dettaglio il nome della sessione porta alle sue scelte di tutti,
    # come la barra delle sessioni (#282).
    urls = {item["label"]: item["url"] for item in context["session_bar"]}
    rows = [_row(p, sessions, results, sprint, urls) for p in shown]
    sort, direction = sort_rows(request, rows, SORTS)
    context.update(
        {
            "rows": rows,
            "headers": sort_headers(
                request, context["league_param"], sort, direction, SORTS
            ),
        }
    )
    return render(request, "fantaApp/all_choices/weekend.html", context)


def _row(player, sessions, results, sprint, urls):
    """Somme del weekend e dettaglio per sessione di un giocatore. Le sessioni
    non ancora iniziate non danno nessun dato. `urls`: pagina delle scelte di
    tutti di ogni sessione, per nome."""
    row = {
        "player": player,
        "sessions": [],
        "spent": None,
        "points": None,
        "qualifying_points": None,
    }
    for session in sessions:
        event = session["event"]
        detail = {
            "label": session["label"],
            "started": session["has_started"],
            "url": urls.get(session["label"]),
        }
        row["sessions"].append(detail)
        if not session["has_started"]:
            continue
        detail["chose"] = player.id in session["chosen"]

        if session["entity"] == "race":
            if detail["chose"]:
                detail["spent"] = session["spent"][player.id]
                row["spent"] = (row["spent"] or 0) + detail["spent"]
            result = results.get((event.id, player.id))
            detail["result"] = result
            if result is not None:
                detail["points"] = (
                    result.fia_points
                    if session["subtype"] == "sprint"
                    else result.total_points
                )
                row["points"] = (row["points"] or 0) + result.total_points
        elif session["subtype"] == "sprint":
            # Il bonus delle Qualifiche Sprint sta sul risultato della Sprint.
            result = results.get((sprint.id, player.id)) if sprint else None
            detail["bonus"] = result.point_modifier if result else None
        else:
            outcome = qualifying_row(
                event,
                player,
                session["picks"].get(player.id),
                *session["outcomes"],
            )
            detail["qualifying_points"] = outcome["qualifying_points"]
            row["qualifying_points"] = outcome["qualifying_points"]
    return row
