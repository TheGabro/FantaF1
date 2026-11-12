"""Ingressi alle pagine delle scelte di tutti (epica #202) dalle altre pagine.

Qui e non in views/weekend.py, che ha già superato le ~1000 righe (#55). Il
modulo non importa da views.weekend: è weekend.py a usarlo.
"""

from django.urls import reverse

from ...services import helper

# Pagina delle scelte di tutti di ogni sessione, per (entity, subtype) come in
# dashboard._weekend_sessions. Le Qualifiche Sprint avranno la loro con #207.
SESSION_PAGES = {
    ("race", "sprint"): "sprint_race_all_choices",
    ("qualifying", "regular"): "race_qualifying_all_choices",
    ("race", "regular"): "regular_race_all_choices",
}


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
