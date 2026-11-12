"""Ingressi alle pagine delle scelte di tutti (epica #202) dalle altre pagine e
percorsi fra loro e fra i risultati del weekend (#271).

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
    query = _query(request, league=True)
    bar = _session_items(
        championship,
        weekend,
        sessions,
        current,
        lambda session: SESSION_PAGES.get((session["entity"], session["subtype"])),
        query,
    )

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

    results_url = None
    for session in sessions:
        if (session["entity"], session["subtype"]) != current:
            continue
        if session["has_started"] and session["results_url_name"]:
            args = [championship.pk, weekend.pk, session["event"].id]
            results_url = reverse(session["results_url_name"], args=args) + _query(
                request
            )
    return {"session_bar": bar, "results_url": results_url}


def results_session_bar(request, championship, weekend, current):
    """Barra delle sessioni nei risultati (#283): i risultati di un'altra
    sessione del weekend, senza il riepilogo (non ci sono risultati del weekend
    intero). Per tutti, come le pagine dei risultati; i link tengono la pagina
    di partenza del percorso. Le Qualifiche Sprint restano spente finché non
    hanno i loro risultati (#197)."""
    return _session_items(
        championship,
        weekend,
        _weekend_sessions(weekend),
        current,
        lambda session: session["results_url_name"],
        _query(request),
    )


def _query(request, league=False):
    """«?league=…&from=play» per i link fra le pagine: la lega scelta (solo
    nelle scelte di tutti) e la pagina di partenza del percorso (#156)."""
    params = {}
    if league and request.GET.get("league"):
        params["league"] = request.GET["league"]
    if request.GET.get("from") == "play":
        params["from"] = "play"
    return "?" + urlencode(params) if params else ""


def _session_items(championship, weekend, sessions, current, page_of, query):
    """Una voce della barra per sessione. `page_of(sessione)` è il nome della
    rotta della pagina, None se la sessione non ce l'ha ancora."""
    items = []
    for session in sessions:
        key = (session["entity"], session["subtype"])
        url_name = page_of(session)
        item = {"label": session["label"], "active": key == current, "url": None}
        if item["active"]:
            pass
        elif url_name is None:
            item["reason"] = "In arrivo"
        elif not session["has_started"]:
            item["reason"] = "Dal via"
        else:
            args = [championship.pk, weekend.pk, session["event"].id]
            item["url"] = reverse(url_name, args=args) + query
        items.append(item)
    return items


def weekend_page_links(request, championship, weekend, player, sessions, origin):
    """Scelte di tutti dalla pagina del weekend (#214, #284).

    Aggiunge a ogni sessione all_choices_url, la sua pagina delle scelte di
    tutti (None se non ce l'ha ancora, #207): la riga mostra «Scelte di tutti»
    accanto a «Risultati» dal via. Ritorna {"summary_url"}, il riepilogo del
    weekend (#208) dal via della prima sessione, None prima. Ritorna None per
    chi non gioca e non gestisce il campionato: le pagine lo rimanderebbero
    indietro, quindi niente pulsanti né riepilogo."""
    if player is None and not helper.is_championship_manager(
        request.user, championship
    ):
        return None
    for session in sessions:
        url_name = SESSION_PAGES.get((session["entity"], session["subtype"]))
        args = [championship.pk, weekend.pk, session["event"].id]
        session["all_choices_url"] = (
            reverse(url_name, args=args) + origin if url_name else None
        )
    return {
        "summary_url": (
            reverse("weekend_all_choices", args=[championship.pk, weekend.pk]) + origin
            if any(session["has_started"] for session in sessions)
            else None
        )
    }
