from django.forms import ValidationError
from django.contrib import messages
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from ..models import Championship, Weekend, Race, Qualifying, Driver
from ..services import player_choices as pc
from ..services import helper



def weekend_detail(request, championship_id, weekend_id):
    championship = get_object_or_404(Championship, pk=championship_id)
    weekend = get_object_or_404(Weekend, pk=weekend_id)

    events = []
    # Sprint-Qualifying
    sq = weekend.qualifyings.filter(type="sprint").first()
    if sq:
        events.append({"label": "Sprint Qualifying",
                       "entity": "qualifying",
                       "subtype": "sprint",
                       "event_id": sq.id})
    # Sprint Race
    sr = weekend.races.filter(type="sprint").first()
    if sr:
        events.append({"label": "Sprint Race",
                       "entity": "race",
                       "subtype": "sprint",
                       "event_id": sr.id})
    # Qualifying (gara regolare)
    q = weekend.qualifyings.filter(type="regular").first()
    if q:
        events.append({"label": "Qualifying",
                       "entity": "qualifying",
                       "subtype": "regular",
                       "event_id": q.id})
    # Race
    r = weekend.races.filter(type="regular").first()
    if r:
        events.append({"label": "Grand Prix",
                       "entity": "race",
                       "subtype": "regular",
                       "event_id": r.id})

    return render(
        request,
        "fantaApp/weekend_details.html",
        {
            "championship": championship,
            "weekend": weekend,
            "events": events,
        },
    )
    

# ───────────────────────────────────────────────────────────────────────────────
#  Base helper (DRY)
# ───────────────────────────────────────────────────────────────────────────────
def _base_context(request, championship_id: int, weekend_id: int):
    """Ritorna (championship, weekend, player) oppure solleva 404."""
    championship = get_object_or_404(Championship, pk=championship_id)
    weekend      = get_object_or_404(Weekend, pk=weekend_id)
    player       = request.user.championshipplayer_set.get(championship=championship)
    return championship, weekend, player

# ───────────────────────────────────────────────────────────────────────────────
#  1) Sprint‑Qualifying
# ───────────────────────────────────────────────────────────────────────────────


@login_required
@transaction.atomic
def sprint_qualifying_choice(request, championship_id, weekend_id, event_id):
    """
    Pagina che mostra i 3 slot SQ1/SQ2/SQ3 contemporaneamente.
    L'utente può salvare una o più scelte in un solo submit.
    Ogni pilota può comparire in un solo slot.
    """
    champ, weekend, player = _base_context(request, championship_id, weekend_id)
    qualifying = get_object_or_404(Qualifying, pk=event_id, weekend=weekend, type="sprint")

    # blocco modifiche se l'evento è già iniziato (solo UI)
    event_started = helper._event_has_started(qualifying)

    # slot codes in ordine
    slots = [("sq1", "SQ1 – eliminato"),
             ("sq2", "SQ2 – eliminato"),
             ("sq3", "SQ3 – posizione 6‑10")]

    # Scelte già presenti (dict slot -> choice istanza)
    existing = {
        c.selection_slot: c
        for c in qualifying.playersprintqualifyingchoice_set
                     .filter(player=player)
                     .select_related("driver")
    }
    taken_ids = [c.driver_id for c in existing.values()]
    

    if request.method == "POST" and not event_started:
        
        selections = [
        request.POST.get(f"driver_{code}") for code, _ in slots
        ]
        
        # Filtra via valori vuoti e controlla la lunghezza
        selected_clean = [s for s in selections if s]
        if len(selected_clean) != len(set(selected_clean)):
            # c’è un duplicato
            messages.error(request, "Non puoi selezionare lo stesso pilota più di una volta.")
            # tornare subito al form senza salvare
            return render(request, "fantaApp/sprint_qualifying_choice.html", context)
        
        
        for code in ("sq1", "sq2", "sq3"):
            drv = request.POST.get(f"driver_{code}")
            if drv:
                pc.choose_sprint_quali_driver(
                    player=player,
                    qualifying=qualifying,
                    driver_id=int(drv),
                    slot=code,
                )
        messages.success(request, "Scelte registrate con successo.")
        return redirect("championship_dashboard", championship_id=champ.id)
            
    if event_started:
        drivers_avail = []
    else:
        drivers_avail = (
            Driver.objects
            .filter(season=weekend.season)
            .exclude(id__in=taken_ids)
            .select_related("team")
        )

    context = {
        "championship": champ,
        "weekend": weekend,
        "event": qualifying,
        "slots": slots,
        "existing": existing,        # dict slot -> choice
        "drivers": drivers_avail,    # per i select ancora vuoti
        "event_started": event_started,
    }
    return render(request, "fantaApp/sprint_qualifying_choice.html", context)


# # ───────────────────────────────────────────────────────────────────────────────
# # 2) Regular Qualifying  (1 pilota)
# # ───────────────────────────────────────────────────────────────────────────────
# @login_required
# def regular_qual_choice(request, championship_id, weekend_id, event_id):
#     champ, weekend, player = _base_context(request, championship_id, weekend_id)
#     qual = get_object_or_404(Qualifying, pk=event_id, weekend=weekend, type="regular")

#     if request.method == "POST":
#         try:
#             choose_driver_for_event(player=player, event=qual,
#                                     driver_id=int(request.POST["driver_id"]))
#             messages.success(request, "Scelta salvata.")
#             return redirect(request.path)
#         except ValidationError as e:
#             messages.error(request, e.message)

#     taken = qual.playerqualifyingchoice_set.filter(player=player).values_list("driver_id", flat=True)
#     drivers = Driver.objects.filter(season=weekend.season).exclude(id__in=taken)

#     return render(request, "event_choice_regular_quali.html", {
#         "championship": champ, "weekend": weekend, "event": qual,
#         "drivers": drivers,
#     })


# # ───────────────────────────────────────────────────────────────────────────────
# # 3) Sprint‑Race  (2 piloti, no pupillo)
# # ───────────────────────────────────────────────────────────────────────────────
# @login_required
# def sprint_race_choice(request, championship_id, weekend_id, event_id):
#     champ, weekend, player = _base_context(request, championship_id, weekend_id)
#     race = get_object_or_404(Race, pk=event_id, weekend=weekend, type="sprint")

#     if request.method == "POST":
#         try:
#             choose_driver_for_event(player=player, event=race,
#                                     driver_id=int(request.POST["driver_id"]))
#             messages.success(request, "Pilota registrato.")
#             return redirect(request.path)
#         except ValidationError as e:
#             messages.error(request, e.message)

#     taken = race.playerracechoice_set.filter(player=player).values_list("driver_id", flat=True)
#     drivers = Driver.objects.filter(season=weekend.season).exclude(id__in=taken)

#     return render(request, "event_choice_sprint_race.html", {
#         "championship": champ, "weekend": weekend, "event": race,
#         "drivers": drivers,
#     })


# # ───────────────────────────────────────────────────────────────────────────────
# # 4) Grand Prix  (2 piloti + pupillo)
# # ───────────────────────────────────────────────────────────────────────────────
# @login_required
# def race_choice(request, championship_id, weekend_id, event_id):
#     champ, weekend, player = _base_context(request, championship_id, weekend_id)
#     race = get_object_or_404(Race, pk=event_id, weekend=weekend, type="regular")

#     if request.method == "POST":
#         try:
#             choose_driver_for_event(
#                 player=player, event=race,
#                 driver_id=int(request.POST["driver_id"]),
#                 is_pupillo=request.POST.get("is_pupillo") == "on",
#             )
#             messages.success(request, "Scelta salvata.")
#             return redirect(request.path)
#         except ValidationError as e:
#             messages.error(request, e.message)

#     taken = race.playerracechoice_set.filter(player=player).values_list("driver_id", flat=True)
#     drivers = Driver.objects.filter(season=weekend.season).exclude(id__in=taken)

#     return render(request, "event_choice_race.html", {
#         "championship": champ, "weekend": weekend, "event": race,
#         "drivers": drivers,
#     })