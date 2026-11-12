"""Ingressi alle pagine delle scelte di tutti (epica #202) dalle altre pagine e
percorsi fra loro (#271).

Qui e non in views/weekend.py, che ha già superato le ~1000 righe (#55). Il
modulo non importa da views.weekend: è weekend.py a usarlo.
"""

from urllib.parse import urlencode

from django.urls import reverse

from ...services import helper
from ..dashboard import _weekend_sessions

# Pagina delle scelte di tutti di ogni sessione, per (entity, subtype) come in
# dashboard._weekend_sessions. Le Qualifiche Sprint avranno la loro con #207.
SESSION_PAGES = {
    ("race", "sprint"): "sprint_race_all_choices",
    ("qualifying", "regular"): "race_qualifying_all_choices",
    ("race", "regular"): "regular_race_all_choices",
}
# Il riepilogo del weekend (#208) nella barra delle sessioni.
SUMMARY = "summary"


def session_nav(request, championship, weekend, current, sessions=None):
    """Percorsi di una pagina delle scelte di tutti (#271, #282).

    - session_bar: la barra delle sessioni sotto il titolo, stessa pagina per
      un'altra sessione del weekend e in fondo il riepilogo. Le sessioni non
      ancora iniziate e quelle senza pagina (Qualifiche Sprint, #207) restano
      spente, col motivo. I link tengono la lega scelta e la pagina di partenza
      del percorso (?from=play).
    - results_url: i risultati della stessa sessione, dal via; None per il
      riepilogo, che non ha una pagina di risultati gemella.

    current è (entity, subtype) della sessione aperta, oppure SUMMARY.
    """
    if sessions is None:
        sessions = _weekend_sessions(weekend)
    from_play = request.GET.get("from") == "play"
    params = {}
    if request.GET.get("league"):
        params["league"] = request.GET["league"]
    if from_play:
        params["from"] = "play"
    query = "?" + urlencode(params) if params else ""

    bar = []
    results_url = None
    for session in sessions:
        key = (session["entity"], session["subtype"])
        url_name = SESSION_PAGES.get(key)
        args = [championship.pk, weekend.pk, session["event"].id]
        item = {"label": session["label"], "active": key == current, "url": None}
        if item["active"]:
            if session["has_started"] and session["results_url_name"]:
                results_url = reverse(session["results_url_name"], args=args) + (
                    "?from=play" if from_play else ""
                )
        elif url_name is None:
            item["reason"] = "In arrivo"
        elif not session["has_started"]:
            item["reason"] = "Dal via"
        else:
            item["url"] = reverse(url_name, args=args) + query
        bar.append(item)

    summary = {"label": "Riepilogo", "active": current == SUMMARY, "url": None}
    if summary["active"]:
        pass
    elif any(session["has_started"] for session in sessions):
        summary["url"] = (
            reverse("weekend_all_choices", args=[championship.pk, weekend.pk]) + query
        )
    else:
        summary["reason"] = "Dal via"
    bar.append(summary)
    return {"session_bar": bar, "results_url": results_url}


def weekend_page_links(request, championship, weekend, player, sessions, origin):
    """Card «Scelte dei giocatori» della pagina del weekend (#214): una riga per
    sessione con la sua pagina e in fondo il riepilogo del weekend (#208). Il
    link c'è solo dal via; prima la riga dice «dal via». None per chi non gioca
    e non gestisce il campionato: le pagine lo rimanderebbero indietro."""
    if player is None and not helper.is_championship_manager(
        request.user, championship
    ):
        return None
    links = []
    for session in sessions:
        url_name = SESSION_PAGES.get((session["entity"], session["subtype"]))
        if url_name is None:
            continue
        args = [championship.pk, weekend.pk, session["event"].id]
        links.append(
            {
                "label": session["label"],
                "url": (
                    reverse(url_name, args=args) + origin
                    if session["has_started"]
                    else None
                ),
            }
        )
    links.append(
        {
            "label": "Riepilogo del weekend",
            "url": (
                reverse("weekend_all_choices", args=[championship.pk, weekend.pk])
                + origin
                if any(session["has_started"] for session in sessions)
                else None
            ),
        }
    )
    return links
