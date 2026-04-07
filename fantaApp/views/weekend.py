from django.forms import ValidationError
from django.contrib import messages
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from ..models import Championship, Weekend, Race, Qualifying, Driver, PlayerSprintQualifyingChoice, PlayerRaceChoice, PlayerQualifyingChoice, PlayerQualifyingMultiChoice,RaceResult
from ..services import player_choices as pc
from ..services import helper



@login_required
def weekend_detail(request, championship_id, weekend_id):
    championship = get_object_or_404(Championship, pk=championship_id)
    weekend = get_object_or_404(Weekend, pk=weekend_id)
    player = request.user.championshipplayer_set.filter(championship=championship).first()

    events = []
    # Sprint-Qualifying
    sq = weekend.qualifyings.filter(type="sprint").first()
    if sq:
        has_choice = False
        if player:
            has_choice = PlayerSprintQualifyingChoice.objects.filter(
                player=player,
                qualifying=sq,
            ).exists()
        events.append({"label": "Sprint Qualifying",
                       "entity": "qualifying",
                       "subtype": "sprint",
                       "event_id": sq.id,
                       "has_choice": has_choice})
        

    # Sprint Race
    sr = weekend.races.filter(type="sprint").first()
    if sr:
        has_choice = False
        if player:
            has_choice = PlayerRaceChoice.objects.filter(
                player=player,
                race=sr,
            ).exists()
        events.append({"label": "Sprint Race",
                       "entity": "race",
                       "subtype": "sprint",
                       "event_id": sr.id,
                       "has_choice": has_choice})    
    
    # Qualifying (gara regolare)
    q = weekend.qualifyings.filter(type="regular").first()
    if q:
        has_choice = False
        if player:
            has_choice = (
                PlayerQualifyingChoice.objects.filter(player=player, qualifying=q).exists()
                or PlayerQualifyingMultiChoice.objects.filter(player=player, qualifying=q).exists()
            )
        events.append({"label": "Qualifying",
                       "entity": "qualifying",
                       "subtype": "regular",
                       "event_id": q.id,
                       "has_choice": has_choice})
    # Race
    r = weekend.races.filter(type="regular").first()
    if r:
        has_choice = False
        if player:
            has_choice = PlayerRaceChoice.objects.filter(
                player=player,
                race=r,
            ).exists()
        events.append({"label": "Grand Prix",
                       "entity": "race",
                       "subtype": "regular",
                       "event_id": r.id,
                       "has_choice": has_choice})

    results = [] 
    #Sprint Race Results
    if sr and sr.entries.exists():
        results.append({
            "label": "Risultati Sprint Race",
            "subtype": "sprint",
            "event_id": sr.id,
            "url_name": "sprint_race_results",
        })

    #Grand Prix Results
    if r and r.entries.exists():
        results.append({
            "label": "Risultati Grand Prix ",
            "subtype": "regular",
            "event_id": r.id,
            "url_name": "regular_race_results",
        })

    return render(
        request,
        "fantaApp/weekend_details.html",
        {
            "championship": championship,
            "weekend": weekend,
            "events": events,
            "results" : results,
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
    if request.method == "POST" and not event_started:
        submitted_by_slot = {
            code: request.POST.get(f"driver_{code}") for code, _ in slots #DictCompenhension per estrarre i valori dei driver inviati, con chiavi come "sq1", "sq2", "sq3"
        }
        selections = list(submitted_by_slot.values())
        
        # Filtra via valori vuoti e controlla la lunghezza
        selected_clean = [s for s in selections if s]
        if len(selected_clean) != len(set(selected_clean)):
            # c’è un duplicato
            messages.error(request, "Non puoi selezionare lo stesso pilota più di una volta.")
            # tornare subito al form senza salvare
            return redirect(request.path)

        try:
            selected_ids = [int(s) for s in selected_clean]
        except (TypeError, ValueError):
            messages.error(request, "Formato pilota non valido.")
            return redirect(request.path)
        drivers_by_id = Driver.objects.filter(
            season=weekend.season,
            id__in=selected_ids,
        ).in_bulk()

        if len(drivers_by_id) != len(set(selected_ids)):
            messages.error(request, "Uno o più piloti selezionati non sono validi per questa stagione.")
            return redirect(request.path)

        for code, _ in slots:
            drv = submitted_by_slot.get(code)
            if drv:
                pc.choose_sprint_quali_driver(
                    player=player,
                    qualifying=qualifying,
                    driver=drivers_by_id[int(drv)],
                    slot=code,
                )
        messages.success(request, "Scelte salvate con successo.")
        return redirect(request.path)

    drivers_avail = (
        Driver.objects
        .filter(season=weekend.season)
        .select_related("team")
        .order_by("team__name", "first_name", "last_name")
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
    return render(request, "fantaApp/sprint_race_qualifying_choice.html", context)

# # ───────────────────────────────────────────────────────────────────────────────
# # 2) Regular Race Qualifying  (1 pilota)
# # ───────────────────────────────────────────────────────────────────────────────
@login_required
def race_qualifying_choice(request, championship_id, weekend_id, event_id):
    """
    Pagina che mostra il pilota scelto per la Qualifying regolare.
    L'utente può salvare una scelta in un solo submit.
    """
    champ, weekend, player = _base_context(request, championship_id, weekend_id)

    if weekend.weekend_type == 'regular':
        return regular_weekend_race_qualifying_choice(request, player, champ, weekend, event_id)
    elif weekend.weekend_type == 'sprint':
        return sprint_weekend_race_qualifying_choice(request, player, champ, weekend, event_id) 
        
# # ───────────────────────────────────────────────────────────────────────────────
# # 3) Sprint‑Race  (2 piloti, no pupillo)
# # ───────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def sprint_race_choice(request, championship_id, weekend_id, event_id):
    """
    Pagina che mostra 2 scelte per la Sprint Race, con relativi costi in crediti.
    L'utente deve salvare entrambe le scelte in un solo submit.
    """
    champ, weekend, player = _base_context(request, championship_id, weekend_id)
    race = get_object_or_404(Race, pk=event_id, weekend=weekend, type="sprint")

    # blocco modifiche se l'evento è già iniziato (solo UI)
    event_started = helper._event_has_started(race)
    
    driver_options = pc.get_sprint_race_driver_options(race=race)
    existing_choices = list(
        race.playerracechoice_set
        .filter(player=player)
        .select_related("driver", "driver__team")
        .order_by("driver__team__name", "driver__first_name", "driver__last_name")
    )

    if request.method == "POST" and not event_started:
        submitted_driver_ids = [value for value in request.POST.getlist("drivers") if value]

        if len(submitted_driver_ids) != 2:
            messages.error(request, "Devi selezionare esattamente 2 piloti per la Sprint Race.")
            return redirect(request.path)

        if len(submitted_driver_ids) != len(set(submitted_driver_ids)):
            messages.error(request, "Non puoi selezionare lo stesso pilota piu' di una volta.")
            return redirect(request.path)

        try:
            selected_ids = [int(value) for value in submitted_driver_ids]
        except (TypeError, ValueError):
            messages.error(request, "Pilota non valido.")
            return redirect(request.path)

        options_by_driver_id = {
            option["driver"].id: option
            for option in driver_options
        }
        if any(driver_id not in options_by_driver_id for driver_id in selected_ids):
            messages.error(request, "La griglia sprint non e' ancora disponibile per i piloti selezionati.")
            return redirect(request.path)

        try:
            total_spent_amount = pc.choose_sprint_race_drivers(
                player=player,
                race=race,
                drivers=[options_by_driver_id[driver_id]["driver"] for driver_id in selected_ids],
            )
            messages.success(
                request,
                f"Scelte salvate con successo. Costo totale prenotato: {total_spent_amount} crediti.",
            )
        except ValidationError as e:
            messages.error(request, e.message)

        return redirect(request.path)

    reserved_credit = pc.get_player_reserved_credit(player=player, exclude_race=race)
    spendable_credit = pc.get_player_spendable_credit(player=player, exclude_race=race)
    current_choice_total = sum(choice.spent_amount for choice in existing_choices)

    context = {
        "championship": champ,
        "weekend": weekend,
        "event": race,
        "driver_options": driver_options,
        "existing_choices": existing_choices,
        "reserved_credit": reserved_credit,
        "spendable_credit": spendable_credit,
        "current_choice_total": current_choice_total,
        "event_started": event_started,
        "grid_available": bool(driver_options),
    }
    return render(request, "fantaApp/sprint_race_choice.html", context)


# # ───────────────────────────────────────────────────────────────────────────────
# # 4) Grand Prix  (2 piloti + pupillo)
# # ───────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def grand_prix_choice(request, championship_id, weekend_id, event_id):
    champ, weekend, player = _base_context(request, championship_id, weekend_id)
    race = get_object_or_404(Race, pk=event_id, weekend=weekend, type="regular")

    event_started = helper._event_has_started(race)
    driver_options = pc.get_race_driver_options(race=race, player=player)
    existing_choices = list(
        race.playerracechoice_set
        .filter(player=player)
        .select_related("driver", "driver__team")
        .order_by("driver__team__name", "driver__first_name", "driver__last_name")
    )
    current_pupillo = next((choice for choice in existing_choices if choice.is_pupillo), None)

    if request.method == "POST" and not event_started:
        submitted_driver_ids = [value for value in request.POST.getlist("drivers") if value]
        pupillo_driver_id = request.POST.get("pupillo_driver_id")

        if len(submitted_driver_ids) != 2:
            messages.error(request, "Devi selezionare esattamente 2 piloti per il Grand Prix.")
            return redirect(request.path)

        if len(submitted_driver_ids) != len(set(submitted_driver_ids)):
            messages.error(request, "Non puoi selezionare lo stesso pilota piu' di una volta.")
            return redirect(request.path)

        if not pupillo_driver_id:
            messages.error(request, "Devi indicare quale dei 2 piloti e' il pupillo.")
            return redirect(request.path)

        try:
            selected_ids = [int(value) for value in submitted_driver_ids]
            pupillo_driver_id = int(pupillo_driver_id)
        except (TypeError, ValueError):
            messages.error(request, "Pilota non valido.")
            return redirect(request.path)

        if pupillo_driver_id not in selected_ids:
            messages.error(request, "Il pupillo deve essere uno dei 2 piloti selezionati.")
            return redirect(request.path)

        options_by_driver_id = {
            option["driver"].id: option
            for option in driver_options
        }
        if any(driver_id not in options_by_driver_id for driver_id in selected_ids):
            messages.error(request, "La griglia del Grand Prix non e' ancora disponibile per i piloti selezionati.")
            return redirect(request.path)

        try:
            result = pc.choose_regular_race_drivers(
                player=player,
                race=race,
                drivers=[options_by_driver_id[driver_id]["driver"] for driver_id in selected_ids],
                pupillo_driver=options_by_driver_id[pupillo_driver_id]["driver"],
            )
            if result["pupillo_discount"]:
                messages.success(
                    request,
                    f"Scelte salvate con successo. Sconto pupillo applicato: {result['pupillo_discount']} crediti. Costo totale prenotato: {result['total_spent_amount']} crediti.",
                )
            else:
                messages.success(
                    request,
                    f"Scelte salvate con successo. Costo totale prenotato: {result['total_spent_amount']} crediti.",
                )
        except ValidationError as e:
            messages.error(request, e.message)

        return redirect(request.path)

    reserved_credit = pc.get_player_reserved_credit(player=player, exclude_race=race)
    spendable_credit = pc.get_player_spendable_credit(player=player, exclude_race=race)
    current_choice_total = sum(choice.spent_amount for choice in existing_choices)

    context = {
        "championship": champ,
        "weekend": weekend,
        "event": race,
        "driver_options": driver_options,
        "existing_choices": existing_choices,
        "current_pupillo_id": current_pupillo.driver_id if current_pupillo else None,
        "reserved_credit": reserved_credit,
        "spendable_credit": spendable_credit,
        "current_choice_total": current_choice_total,
        "event_started": event_started,
        "grid_available": bool(driver_options),
    }
    return render(request, "fantaApp/grand_prix_choice.html", context)


def sprint_weekend_race_qualifying_choice(request, player, champ, weekend, event_id):
    qualifying = get_object_or_404(Qualifying, pk=event_id, weekend=weekend, type="regular")
    
    event_started = helper._event_has_started(qualifying)
    
    slots = [
        ("q1_pass", "Passano il Q1"),
        ("q2_pass", "Passano il Q2"),
        ("q3_top3", "Top 3 in Q3"),
    ]
    slot_limits = {
        "q1_pass": 6,
        "q2_pass": 5,
        "q3_top3": 3,
    }

    # Scelte già presenti (dict slot -> choice istanza)
    existing = {code: [] for code, _ in slots}
    for choice in (
        qualifying.playerqualifyingmultichoice_set
        .filter(player=player)
        .select_related("driver")
        .order_by("selection_slot", "driver__team__name", "driver__first_name", "driver__last_name")
    ):
        existing.setdefault(choice.selection_slot, []).append(choice)

    if request.method == "POST" and not event_started:
        submitted_by_slot = {
            code: [value for value in request.POST.getlist(f"drivers_{code}") if value]
            for code, _ in slots
        }

        for code, _ in slots:
            if len(submitted_by_slot[code]) > slot_limits[code]:
                messages.error(
                    request,
                    f"Hai superato il limite per {code}: massimo {slot_limits[code]} piloti.",
                )
                return redirect(request.path)

        selected_clean = [driver_id for values in submitted_by_slot.values() for driver_id in values]
        if len(selected_clean) != len(set(selected_clean)):
            messages.error(request, "Non puoi selezionare lo stesso pilota più di una volta.")
            return redirect(request.path)

        try:
            selected_ids = [int(s) for s in selected_clean]
        except (TypeError, ValueError):
            messages.error(request, "Formato pilota non valido.")
            return redirect(request.path)
        drivers_by_id = Driver.objects.filter(
            season=weekend.season,
            id__in=selected_ids,
        ).in_bulk()

        if len(drivers_by_id) != len(set(selected_ids)):
            messages.error(request, "Uno o più piloti selezionati non sono validi per questa stagione.")
            return redirect(request.path)

        for code, _ in slots:
            drv = submitted_by_slot.get(code)
            if drv:
                pc.choose_regular_quali_multi_driver(
                    player=player,
                    qualifying=qualifying,
                    driver=drivers_by_id[int(drv)],
                    slot=code,
                )

        messages.success(request, "Scelte salvate con successo.")
        return redirect(request.path)

    drivers_avail = (
        Driver.objects
        .filter(season=weekend.season)
        .select_related("team")
        .order_by("team__name", "first_name", "last_name")
    )

    context = {
        "championship": champ,
        "weekend": weekend,
        "event": qualifying,
        "slots": slots,
        "slot_limits": slot_limits,
        "existing": existing,        # dict slot -> choice
        "drivers": drivers_avail,    # per i select ancora vuoti
        "event_started": event_started,
    }
    return render(request, "fantaApp/regular_race_qualifying_multi_choice.html", context)
    
def regular_weekend_race_qualifying_choice(request, player, champ, weekend, event_id):

    qualifying = get_object_or_404(Qualifying, pk=event_id, weekend=weekend, type="regular")

        # blocco modifiche se l'evento è già iniziato (solo UI)
    event_started = helper._event_has_started(qualifying)

    drivers_taken = (
        PlayerQualifyingChoice.objects
        .filter(
            player=player,
            qualifying__weekend__season=weekend.season,
            qualifying__type="regular",
        )
        .exclude(qualifying=qualifying)  # permette eventuale modifica della stessa gara
        .values_list("driver_id", flat=True)
    )

    if request.method == "POST" and not event_started:
        driver_id = request.POST.get("driver")
        if not driver_id:
            messages.error(request, "Devi selezionare un pilota.")
            return redirect(request.path)
        try:
            driver_id = int(driver_id)
        except (TypeError, ValueError):
            messages.error(request, "Pilota non valido.")
            return redirect(request.path)

        driver = Driver.objects.filter(
            id=driver_id,
            season=weekend.season,
        ).exclude(id__in=drivers_taken).first()


        try:
            pc.choose_regular_quali_driver(
                player=player,
                qualifying=qualifying,
                driver=driver,
            )
            messages.success(request, "Scelte salvate con successo.")
        except ValidationError as e:
            messages.error(request, e.message)
        return redirect(request.path)
    
    drivers_available = (
        Driver.objects.filter(season=weekend.season).exclude(id__in=drivers_taken)
        .order_by("team__name", "first_name", "last_name")
    )

    existing = PlayerQualifyingChoice.objects.filter(
        player=player,
        qualifying=qualifying,
    ).first()


    context = {
        "championship": champ,
        "weekend": weekend,
        "event": qualifying,
        "existing": existing,
        "drivers": drivers_available,    # per i select ancora vuoti
        "event_started": event_started,
    }
    return render(request, "fantaApp/regular_race_qualifying_choice.html", context)

def _render_race_results_page(request, championship_id, weekend_id, event_id, *, race_type, race_label):
    champ, weekend, player = _base_context(request, championship_id, weekend_id)

    race = get_object_or_404(Race, pk=event_id, weekend=weekend, type=race_type)
    results = list(
        race.entries
        .select_related("driver", "driver__team")
        .order_by("position", "driver__team__name", "driver__first_name", "driver__last_name")
    )
    for entry in results:
        if entry.starting_grid is not None and entry.position is not None:
            entry.position_delta = entry.starting_grid - entry.position
        else:
            entry.position_delta = None
    classified_results = [entry for entry in results if entry.position is not None]
    player_choices = list(
        race.playerracechoice_set
        .filter(player=player)
        .select_related("driver", "driver__team")
        .order_by("driver__team__name", "driver__first_name", "driver__last_name")
    )
    selected_driver_ids = [choice.driver_id for choice in player_choices]
    player_credit_used = sum(choice.spent_amount for choice in player_choices)
    player_pupillo = next((choice for choice in player_choices if choice.is_pupillo), None)

    context = {
        "championship": champ,
        "weekend": weekend,
        "event": race,
        "race_label": race_label,
        "results": results,
        "classified_count": len(classified_results),
        "results_count": len(results),
        "total_points_awarded": sum(entry.points for entry in classified_results),
        "player_choices": player_choices,
        "selected_driver_ids": selected_driver_ids,
        "player_pupillo": player_pupillo,
        "player_weekend_points": None,
        "player_credit_used": player_credit_used,
    }
    return render(request, "fantaApp/race_results.html", context)

def sprint_race_results(request, championship_id, weekend_id, event_id):
    return _render_race_results_page(
        request,
        championship_id,
        weekend_id,
        event_id,
        race_type="sprint",
        race_label="Sprint Race",
    )

def regular_race_results(request, championship_id, weekend_id, event_id):
    return _render_race_results_page(
        request,
        championship_id,
        weekend_id,
        event_id,
        race_type="regular",
        race_label="Grand Prix",
    )