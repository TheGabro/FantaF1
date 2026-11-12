from django.forms import ValidationError
from django.contrib import messages
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db import transaction
from ..models import (
    Championship,
    Weekend,
    Race,
    Qualifying,
    Driver,
    PlayerQualifyingChoice,
    RaceStartingGrid,
    PlayerRaceResult,
)
from ..services import player_choices as pc
from ..services import bonuses, costs, rules, helper
from .weekend_teams import use_weekend_teams
from .race_classification import race_classification
from .dashboard import _mark_missing_grids, _player_choice_index, _weekend_sessions
from .all_choices.links import results_session_bar, weekend_page_links
from . import session_state as ss
from django.db.models import Count


@login_required
def weekend_detail(request, championship_id, weekend_id):
    """Sessioni del weekend con orario, stato della scelta e i pulsanti secondo
    lo stato (#61), come Prossimo weekend (#193): «Scegli»/«Modifica» finché si
    può scegliere, spento senza griglia, «Risultati» e «Scelte di tutti» dal
    via (#284). Query costanti: sessioni e scelte arrivano dagli helper di
    dashboard."""
    championship = get_object_or_404(Championship, pk=championship_id)
    weekend = get_object_or_404(
        Weekend.objects.select_related("circuit").prefetch_related(
            "races", "qualifyings"
        ),
        pk=weekend_id,
    )
    player = request.user.championshipplayer_set.filter(
        championship=championship
    ).first()

    already_chosen = _player_choice_index(player, weekend.season) if player else set()
    sessions = _weekend_sessions(weekend)
    for session in sessions:
        session["has_choice"] = (
            session["entity"],
            session["event"].id,
        ) in already_chosen
    _mark_missing_grids(sessions)

    return render(
        request,
        "fantaApp/weekend_details.html",
        {
            "championship": championship,
            "weekend": weekend,
            "breadcrumb": _breadcrumb(request, championship, weekend),
            # Le sessioni restano nel percorso di partenza (#63, #156).
            "origin_query": _origin_query(request),
            "sessions": sessions,
            "player": player,
            "all_choices": weekend_page_links(
                request, championship, weekend, player, sessions, _origin_query(request)
            ),
        },
    )


# ───────────────────────────────────────────────────────────────────────────────
#  Base helper (DRY)
# ───────────────────────────────────────────────────────────────────────────────
def _base_context(request, championship_id: int, weekend_id: int):
    """Ritorna (championship, weekend, player) oppure solleva 404.

    player è None se l'utente non è iscritto al campionato (es. un manager
    che non gioca): sta alla view decidere cosa mostrargli.
    """
    championship = get_object_or_404(Championship, pk=championship_id)
    weekend = get_object_or_404(Weekend, pk=weekend_id)
    player = request.user.championshipplayer_set.filter(
        championship=championship
    ).first()
    return championship, weekend, player


def _not_enrolled_redirect(request, championship, weekend):
    """Le pagine di scelta servono solo ai giocatori: gli altri tornano al weekend."""
    messages.error(
        request, f"Non sei iscritto a «{championship.name}»: non puoi fare scelte."
    )
    return redirect(
        "weekend_details", championship_id=championship.pk, weekend_id=weekend.pk
    )


def _origin_query(request):
    """«?from=play» se si è arrivati da Prossimo weekend, altrimenti "".

    Il parametro accetta solo valori fissi, mai un indirizzo, così non si può
    usare per mandare l'utente su un altro sito. I form fanno il POST sullo
    stesso indirizzo e le view rimandano a request.get_full_path(), quindi il
    parametro resta anche dopo il salvataggio (#156).
    """
    return "?from=play" if request.GET.get("from") == "play" else ""


def _breadcrumb(request, championship, weekend, current=None):
    """
    Percorso in cima alle pagine del weekend (#63):
    - dal calendario: campionato › Calendario gare › weekend › sessione;
    - da Prossimo weekend (?from=play, #156): campionato › Prossimo weekend ›
      sessione, senza il weekend in mezzo.
    La pagina del weekend chiude il percorso col weekend. La pagina del weekend
    aperta da Prossimo weekend passa il parametro ai link delle sessioni, che
    quindi riportano anch'esse a Prossimo weekend. L'ultimo livello è la pagina
    aperta e non ha link.
    """
    origin_query = _origin_query(request)
    if origin_query:
        origin = {
            "label": "Prossimo weekend",
            "url": reverse("championship_next_weekend", args=[championship.pk]),
        }
    else:
        origin = {
            "label": "Calendario gare",
            "url": reverse("championship_calendar", args=[championship.pk]),
        }
    crumbs = [
        {
            "label": f"{championship.name} {championship.year}",
            "url": reverse("championship_dashboard", args=[championship.pk]),
        },
        origin,
    ]
    weekend_crumb = {
        "label": f"R{weekend.round_number} {weekend.event_name}",
        "url": reverse("weekend_details", args=[championship.pk, weekend.pk]),
    }
    if current is None:
        weekend_crumb["url"] = None
        return crumbs + [weekend_crumb]
    # Da Prossimo weekend si torna lì direttamente: il weekend è già nel titolo
    # della pagina, un livello in più allungherebbe solo la strada.
    if origin_query:
        return crumbs + [{"label": current, "url": None}]
    return crumbs + [weekend_crumb, {"label": current, "url": None}]


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
    if player is None:
        return _not_enrolled_redirect(request, champ, weekend)

    qualifying = get_object_or_404(
        Qualifying, pk=event_id, weekend=weekend, type="sprint"
    )

    # blocco modifiche se l'evento è già iniziato (solo UI)
    event_started = helper._event_has_started(qualifying)

    # slot codes in ordine
    slots = [
        ("sq1", "SQ1 – eliminato"),
        ("sq2", "SQ2 – eliminato"),
        ("sq3", "SQ3 – posizione 6‑10"),
    ]

    # Scelte già presenti (dict slot -> choice istanza)
    existing = {
        c.selection_slot: c
        for c in qualifying.playersprintqualifyingchoice_set.filter(
            player=player
        ).select_related("driver")
    }
    if request.method == "POST" and not event_started:
        submitted_by_slot = {
            code: request.POST.get(f"driver_{code}")
            for code, _ in slots  # DictCompenhension per estrarre i valori dei driver inviati, con chiavi come "sq1", "sq2", "sq3"
        }
        selections = list(submitted_by_slot.values())

        # Filtra via valori vuoti e controlla la lunghezza
        selected_clean = [s for s in selections if s]
        if len(selected_clean) != len(set(selected_clean)):
            # c’è un duplicato
            messages.error(
                request, "Non puoi selezionare lo stesso pilota più di una volta."
            )
            # tornare subito al form senza salvare
            return redirect(request.get_full_path())

        try:
            selected_ids = [int(s) for s in selected_clean]
        except (TypeError, ValueError):
            messages.error(request, "Formato pilota non valido.")
            return redirect(request.get_full_path())
        drivers_by_id = Driver.objects.filter(
            driver_participations__weekend=weekend,
            id__in=selected_ids,
        ).in_bulk()

        if len(drivers_by_id) != len(set(selected_ids)):
            messages.error(
                request,
                "Uno o più piloti selezionati non sono validi per questa stagione.",
            )
            return redirect(request.get_full_path())

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
        return redirect(request.get_full_path())

    drivers_avail = list(
        Driver.objects.filter(driver_participations__weekend=weekend)
        .select_related("team")
        .order_by("team__name", "first_name", "last_name")
    )
    # Colori ed etichette con la scuderia di questo weekend (#82).
    use_weekend_teams(
        weekend, [*drivers_avail, *(choice.driver for choice in existing.values())]
    )
    drivers_avail.sort(key=lambda driver: driver.team.name)

    context = {
        "championship": champ,
        "weekend": weekend,
        "breadcrumb": _breadcrumb(request, champ, weekend, "Qualifiche Sprint"),
        "event": qualifying,
        "slots": slots,
        "existing": existing,  # dict slot -> choice
        "drivers": drivers_avail,  # per i select ancora vuoti
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
    if player is None:
        return _not_enrolled_redirect(request, champ, weekend)

    if weekend.weekend_type == "regular":
        return regular_weekend_race_qualifying_choice(
            request, player, champ, weekend, event_id
        )
    elif weekend.weekend_type == "sprint":
        return sprint_weekend_race_qualifying_choice(
            request, player, champ, weekend, event_id
        )


# # ───────────────────────────────────────────────────────────────────────────────
# # 3) Sprint‑Race  (1 piloti, no pupillo)
# # ───────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def sprint_race_choice(request, championship_id, weekend_id, event_id):
    """
    Pagina che mostra 1 scelte per la Sprint Race, con relativi costi in crediti.
    L'utente deve salvare entrambe le scelte in un solo submit.
    """
    champ, weekend, player = _base_context(request, championship_id, weekend_id)
    if player is None:
        return _not_enrolled_redirect(request, champ, weekend)

    race = get_object_or_404(Race, pk=event_id, weekend=weekend, type="sprint")

    # Dal via la scelta è chiusa: si va ai risultati, anche con una POST (#185).
    if helper._event_has_started(race):
        if request.method == "POST":
            messages.error(request, "La Sprint è iniziata: le scelte sono chiuse.")
        return redirect(
            reverse("sprint_race_results", args=[champ.pk, weekend.pk, race.pk])
            + _origin_query(request)
        )
    # Senza griglia non c'è niente da scegliere: si torna al weekend (#190).
    if not RaceStartingGrid.objects.filter(race=race).exists():
        messages.info(
            request,
            "La griglia della Sprint non è ancora disponibile: "
            "la scelta si apre quando arriva.",
        )
        return redirect(
            reverse("weekend_details", args=[champ.pk, weekend.pk])
            + _origin_query(request)
        )

    driver_options = costs.get_sprint_race_driver_options(race=race)
    sprint_qualifying = weekend.qualifyings.filter(type="sprint").first()
    sprint_qualifying_bonus = bonuses.get_sprint_qualifying_bonus(
        player=player, qualifying=sprint_qualifying
    )
    existing_choices = list(
        race.playerracechoice_set.filter(player=player)
        .select_related("driver", "driver__team")
        .order_by("driver__team__name", "driver__first_name", "driver__last_name")
    )

    if request.method == "POST":
        submitted_driver_ids = [
            value for value in request.POST.getlist("drivers") if value
        ]

        if len(submitted_driver_ids) != 1:
            messages.error(
                request, "Devi selezionare esattamente 1 pilota per la Sprint."
            )
            return redirect(request.get_full_path())

        if len(submitted_driver_ids) != len(set(submitted_driver_ids)):
            messages.error(
                request, "Non puoi selezionare lo stesso pilota piu' di una volta."
            )
            return redirect(request.get_full_path())

        try:
            selected_ids = [int(value) for value in submitted_driver_ids]
        except (TypeError, ValueError):
            messages.error(request, "Pilota non valido.")
            return redirect(request.get_full_path())

        options_by_driver_id = {
            option["driver"].id: option for option in driver_options
        }
        if any(driver_id not in options_by_driver_id for driver_id in selected_ids):
            messages.error(
                request,
                "La griglia sprint non e' ancora disponibile per i piloti selezionati.",
            )
            return redirect(request.get_full_path())

        try:
            total_spent_amount = pc.choose_sprint_race_drivers(
                player=player,
                race=race,
                drivers=[
                    options_by_driver_id[driver_id]["driver"]
                    for driver_id in selected_ids
                ],
            )
            messages.success(
                request,
                f"Scelte salvate con successo. Costo totale prenotato: {total_spent_amount} fantamilioni.",
            )
        except ValidationError as e:
            messages.error(request, e.message)

        return redirect(request.get_full_path())

    reserved_credit = costs.get_player_reserved_credit(player=player, exclude_race=race)
    spendable_credit = costs.get_player_spendable_credit(
        player=player, exclude_race=race
    )
    current_choice_total = sum(choice.spent_amount for choice in existing_choices)

    # Colori ed etichette con la scuderia di questo weekend (#82).
    use_weekend_teams(
        weekend,
        [option["driver"] for option in driver_options]
        + [choice.driver for choice in existing_choices],
    )
    # Griglia di partenza (#183): spento chi, anche con lo sconto della Sprint
    # Qualifying, supera i fantamilioni spendibili. Solo un aiuto visivo.
    for option in driver_options:
        option["over_budget"] = (
            option["cost"] - sprint_qualifying_bonus["credit_discount"]
            > spendable_credit
        )
    context = {
        "championship": champ,
        "weekend": weekend,
        "breadcrumb": _breadcrumb(request, champ, weekend, "Sprint"),
        "event": race,
        "driver_options": driver_options,
        "sprint_qualifying_bonus": sprint_qualifying_bonus,
        "existing_choices": existing_choices,
        "reserved_credit": reserved_credit,
        "spendable_credit": spendable_credit,
        "current_choice_total": current_choice_total,
    }
    return render(request, "fantaApp/sprint_race_choice.html", context)


# # ───────────────────────────────────────────────────────────────────────────────
# # 4) Grand Prix  (2 piloti + pupillo)
# # ───────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def regular_race_choice(request, championship_id, weekend_id, event_id):
    champ, weekend, player = _base_context(request, championship_id, weekend_id)
    if player is None:
        return _not_enrolled_redirect(request, champ, weekend)

    race = get_object_or_404(Race, pk=event_id, weekend=weekend, type="regular")

    # Dal via la scelta è chiusa: si va ai risultati, anche con una POST (#184).
    if helper._event_has_started(race):
        if request.method == "POST":
            messages.error(request, "Il Gran Premio è iniziato: le scelte sono chiuse.")
        return redirect(
            reverse("regular_race_results", args=[champ.pk, weekend.pk, race.pk])
            + _origin_query(request)
        )
    # Senza griglia non c'è niente da scegliere: si torna al weekend (#189).
    if not RaceStartingGrid.objects.filter(race=race).exists():
        messages.info(
            request,
            "La griglia del Gran Premio non è ancora disponibile: "
            "la scelta si apre quando arriva.",
        )
        return redirect(
            reverse("weekend_details", args=[champ.pk, weekend.pk])
            + _origin_query(request)
        )

    driver_options = costs.get_race_driver_options(race=race, player=player)
    regular_race_bonus = bonuses.get_race_bonus(player=player, race=race)
    existing_choices = list(
        race.playerracechoice_set.filter(player=player)
        .select_related("driver", "driver__team")
        .order_by("driver__team__name", "driver__first_name", "driver__last_name")
    )
    current_pupillo = next(
        (choice for choice in existing_choices if choice.is_pupillo), None
    )

    if request.method == "POST":
        submitted_driver_ids = [
            value for value in request.POST.getlist("drivers") if value
        ]
        pupillo_driver_id = request.POST.get("pupillo_driver_id")

        if len(submitted_driver_ids) != 2:
            messages.error(
                request, "Devi selezionare esattamente 2 piloti per il Gran Premio."
            )
            return redirect(request.get_full_path())

        if len(submitted_driver_ids) != len(set(submitted_driver_ids)):
            messages.error(
                request, "Non puoi selezionare lo stesso pilota piu' di una volta."
            )
            return redirect(request.get_full_path())

        if not pupillo_driver_id:
            messages.error(request, "Devi indicare quale dei 2 piloti e' il pupillo.")
            return redirect(request.get_full_path())

        try:
            selected_ids = [int(value) for value in submitted_driver_ids]
            pupillo_driver_id = int(pupillo_driver_id)
        except (TypeError, ValueError):
            messages.error(request, "Pilota non valido.")
            return redirect(request.get_full_path())

        if pupillo_driver_id not in selected_ids:
            messages.error(
                request, "Il pupillo deve essere uno dei 2 piloti selezionati."
            )
            return redirect(request.get_full_path())

        options_by_driver_id = {
            option["driver"].id: option for option in driver_options
        }
        if any(driver_id not in options_by_driver_id for driver_id in selected_ids):
            messages.error(
                request,
                "La griglia del Gran Premio non è ancora disponibile per i piloti selezionati.",
            )
            return redirect(request.get_full_path())

        try:
            result = pc.choose_regular_race_drivers(
                player=player,
                race=race,
                drivers=[
                    options_by_driver_id[driver_id]["driver"]
                    for driver_id in selected_ids
                ],
                pupillo_driver=options_by_driver_id[pupillo_driver_id]["driver"],
            )

            # Costruisci il messaggio in base ai bonus applicati
            credit_change = result["qualifying_bonus_credit_change"]
            credit_msg = ""
            if credit_change < 0:
                credit_msg = f"Sconto qualifica: {abs(credit_change)} fantamilioni."
            elif credit_change > 0:
                credit_msg = f"Malus qualifica: +{credit_change} fantamilioni."

            if result["pupillo_discount"] and credit_msg:
                messages.success(
                    request,
                    f"Scelte salvate con successo. Sconto pupillo applicato: {result['pupillo_discount']} fantamilioni. {credit_msg} Costo totale prenotato: {result['total_spent_amount']} fantamilioni.",
                )
            elif result["pupillo_discount"]:
                messages.success(
                    request,
                    f"Scelte salvate con successo. Sconto pupillo applicato: {result['pupillo_discount']} fantamilioni. Costo totale prenotato: {result['total_spent_amount']} fantamilioni.",
                )
            elif credit_msg:
                messages.success(
                    request,
                    f"Scelte salvate con successo. {credit_msg} Costo totale prenotato: {result['total_spent_amount']} fantamilioni.",
                )
            else:
                messages.success(
                    request,
                    f"Scelte salvate con successo. Costo totale prenotato: {result['total_spent_amount']} fantamilioni.",
                )
        except ValidationError as e:
            messages.error(request, e.message)

        return redirect(request.get_full_path())

    reserved_credit = costs.get_player_reserved_credit(player=player, exclude_race=race)
    spendable_credit = costs.get_player_spendable_credit(
        player=player, exclude_race=race
    )
    current_choice_total = sum(choice.spent_amount for choice in existing_choices)

    # Colori ed etichette con la scuderia di questo weekend (#82).
    use_weekend_teams(
        weekend,
        [option["driver"] for option in driver_options]
        + [choice.driver for choice in existing_choices],
    )
    # Griglia di partenza (#182): un pilota che anche al prezzo più basso (da
    # pupillo e con lo sconto della qualifica) supera i fantamilioni spendibili
    # si mostra spento. È solo un aiuto: il controllo vero resta nel servizio.
    qualifying_discount = max(-regular_race_bonus["credit_change"], 0)
    for option in driver_options:
        lowest_cost = min(option["cost"], option.get("pupillo_cost", option["cost"]))
        option["over_budget"] = lowest_cost - qualifying_discount > spendable_credit
    # La qualifica è già corsa: dalla scelta si vedono i suoi risultati (#198).
    qualifying = weekend.qualifyings.filter(type="regular").first()
    context = {
        "championship": champ,
        "weekend": weekend,
        "breadcrumb": _breadcrumb(request, champ, weekend, "Gran Premio"),
        "event": race,
        "qualifying_results": qualifying
        and {
            "url": reverse(
                "race_qualifying_results", args=[champ.pk, weekend.pk, qualifying.pk]
            )
            + _origin_query(request),
            "available": qualifying.qualifying_entries.exists(),
        },
        "driver_options": driver_options,
        "regular_race_bonus": regular_race_bonus,
        "existing_choices": existing_choices,
        "current_pupillo_id": current_pupillo.driver_id if current_pupillo else None,
        "reserved_credit": reserved_credit,
        "spendable_credit": spendable_credit,
        "current_choice_total": current_choice_total,
    }
    return render(request, "fantaApp/regular_race_choice.html", context)


def sprint_weekend_race_qualifying_choice(request, player, champ, weekend, event_id):
    qualifying = get_object_or_404(
        Qualifying, pk=event_id, weekend=weekend, type="regular"
    )

    # Dal via la scelta è chiusa: si va ai risultati, anche con una POST (#187).
    if helper._event_has_started(qualifying):
        if request.method == "POST":
            messages.error(request, "La qualifica è iniziata: le scelte sono chiuse.")
        return redirect(
            reverse(
                "race_qualifying_results", args=[champ.pk, weekend.pk, qualifying.pk]
            )
            + _origin_query(request)
        )

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
        qualifying.playerqualifyingmultichoice_set.filter(player=player)
        .select_related("driver")
        .order_by(
            "selection_slot",
            "driver__team__name",
            "driver__first_name",
            "driver__last_name",
        )
    ):
        existing.setdefault(choice.selection_slot, []).append(choice)

    if request.method == "POST":
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
                return redirect(request.get_full_path())
            elif len(submitted_by_slot[code]) < slot_limits[code]:
                messages.error(
                    request,
                    f"Il numero di piloti non è sufficiente. Effeattua tutte le scelte",
                )
                return redirect(request.get_full_path())

        selected_clean = [
            driver_id for values in submitted_by_slot.values() for driver_id in values
        ]
        if len(selected_clean) != len(set(selected_clean)):
            messages.error(
                request, "Non puoi selezionare lo stesso pilota più di una volta."
            )
            return redirect(request.get_full_path())

        try:
            selected_ids = [int(s) for s in selected_clean]
        except (TypeError, ValueError):
            messages.error(request, "Formato pilota non valido.")
            return redirect(request.get_full_path())
        drivers_by_id = Driver.objects.filter(
            driver_participations__weekend=weekend,
            id__in=selected_ids,
        ).in_bulk()

        if len(drivers_by_id) != len(set(selected_ids)):
            messages.error(
                request,
                "Uno o più piloti selezionati non sono validi per questa stagione.",
            )
            return redirect(request.get_full_path())

        drivers_by_slot = {
            code: [
                drivers_by_id[int(driver_id)]
                for driver_id in submitted_by_slot.get(code, [])
            ]
            for code, _ in slots
        }

        pc.choose_regular_quali_multi_choices(
            player=player,
            qualifying=qualifying,
            selections_by_slot=drivers_by_slot,
        )

        messages.success(request, "Scelte salvate con successo.")
        return redirect(request.get_full_path())

    drivers_avail = list(
        Driver.objects.filter(driver_participations__weekend=weekend)
        .select_related("team")
        .order_by("team__name", "first_name", "last_name")
    )
    # Colori ed etichette con la scuderia di questo weekend (#82).
    use_weekend_teams(
        weekend,
        [
            *drivers_avail,
            *(choice.driver for choices in existing.values() for choice in choices),
        ],
    )
    drivers_avail.sort(key=lambda driver: driver.team.name)

    context = {
        "championship": champ,
        "weekend": weekend,
        "breadcrumb": _breadcrumb(request, champ, weekend, "Qualifiche"),
        "event": qualifying,
        "slots": slots,
        "slot_limits": slot_limits,
        "existing": existing,  # dict slot -> choice
        "drivers": drivers_avail,  # per i select ancora vuoti
        # La Sprint è già corsa: dalla scelta si vedono i suoi risultati (#200).
        "sprint_results": _results_button(
            request, champ, weekend, weekend.races.filter(type="sprint").first()
        ),
    }
    return render(
        request, "fantaApp/regular_race_qualifying_multi_choice.html", context
    )


def _results_button(request, championship, weekend, race):
    """Pulsante verso i risultati di una gara già corsa del weekend (#200):
    {url, available}, None se la gara non c'è. Senza risultati il template lo
    mostra ombreggiato."""
    if race is None:
        return None
    url_name = (
        "sprint_race_results" if race.type == "sprint" else "regular_race_results"
    )
    return {
        "url": reverse(url_name, args=[championship.pk, weekend.pk, race.pk])
        + _origin_query(request),
        "available": race.entries.exists(),
    }


def regular_weekend_race_qualifying_choice(request, player, champ, weekend, event_id):
    qualifying = get_object_or_404(
        Qualifying, pk=event_id, weekend=weekend, type="regular"
    )

    # Dal via la scelta è chiusa: si va ai risultati, anche con una POST (#186).
    if helper._event_has_started(qualifying):
        if request.method == "POST":
            messages.error(request, "La qualifica è iniziata: le scelte sono chiuse.")
        return redirect(
            reverse(
                "race_qualifying_results", args=[champ.pk, weekend.pk, qualifying.pk]
            )
            + _origin_query(request)
        )

    # Piloti già spesi in un'altra qualifica regular della stagione: restano in
    # griglia ma bloccati, con il GP in cui sono stati usati.
    locked_events_by_driver_id = {
        choice.driver_id: choice.qualifying.weekend.event_name
        for choice in (
            PlayerQualifyingChoice.objects.filter(
                player=player,
                qualifying__weekend__season=weekend.season,
                qualifying__type="regular",
            )
            .exclude(
                qualifying=qualifying
            )  # permette eventuale modifica della stessa gara
            .select_related("qualifying__weekend")
        )
    }

    teams_maxed_out = (
        PlayerQualifyingChoice.objects.filter(
            player=player,
            qualifying__weekend__season=weekend.season,
            qualifying__type="regular",
        )
        .exclude(qualifying=qualifying)
        .values("driver__team_id")
        .annotate(picks=Count("id"))
        .filter(picks__gte=rules.REGULAR_QUALIFYING_MAX_PICKS_PER_TEAM)
        .values_list("driver__team_id", flat=True)
    )

    if request.method == "POST":
        if request.POST.get("action") == "delete":
            PlayerQualifyingChoice.objects.filter(
                player=player, qualifying=qualifying
            ).delete()
            messages.success(
                request, "Scelta cestinata: puoi selezionare un altro pilota."
            )
            return redirect(request.get_full_path())

        driver_id = request.POST.get("driver")
        if not driver_id:
            messages.error(request, "Devi selezionare un pilota.")
            return redirect(request.get_full_path())
        try:
            driver_id = int(driver_id)
        except (TypeError, ValueError):
            messages.error(request, "Pilota non valido.")
            return redirect(request.get_full_path())

        driver = (
            Driver.objects.filter(
                driver_participations__weekend=weekend,
                id=driver_id,
            )
            .exclude(id__in=locked_events_by_driver_id.keys())
            .exclude(team_id__in=teams_maxed_out)
            .first()
        )

        if driver is None:
            messages.error(
                request, "Pilota non valido o già usato in un'altra qualifica."
            )
            return redirect(request.get_full_path())

        try:
            pc.choose_regular_quali_driver(
                player=player,
                qualifying=qualifying,
                driver=driver,
            )
            messages.success(request, "Scelte salvate con successo.")
        except ValidationError as e:
            messages.error(request, e.message)
        return redirect(request.get_full_path())

    existing = (
        PlayerQualifyingChoice.objects.filter(
            player=player,
            qualifying=qualifying,
        )
        .select_related("driver", "driver__team")
        .first()
    )

    # Solo i piloti in pista in questo weekend (WeekendParticipant): il roster
    # tiene già conto di riserve e sostituzioni.
    drivers_available = list(
        Driver.objects.filter(driver_participations__weekend=weekend)
        .select_related("team")
        .order_by("team__name", "number")
    )
    # I piloti non sceglibili restano in griglia ma bloccati, con il motivo.
    maxed_team_ids = set(teams_maxed_out)
    max_picks_per_team = rules.REGULAR_QUALIFYING_MAX_PICKS_PER_TEAM
    selected_driver_id = existing.driver_id if existing else None
    for driver in drivers_available:
        driver.is_selected = driver.id == selected_driver_id
        locked_event = locked_events_by_driver_id.get(driver.id)
        if locked_event:
            driver.locked_reason = f"già usato · {locked_event}"
        elif driver.team_id in maxed_team_ids:
            driver.locked_reason = f"scuderia già scelta {max_picks_per_team} volte"
        else:
            driver.locked_reason = None
    # Colori e gruppi della griglia con la scuderia di questo weekend (#82), solo
    # dopo i blocchi: il limite per scuderia resta su Driver.team.
    use_weekend_teams(
        weekend, [*drivers_available, *([existing.driver] if existing else [])]
    )
    drivers_available.sort(key=lambda driver: driver.team.name)

    context = {
        "championship": champ,
        "weekend": weekend,
        "breadcrumb": _breadcrumb(request, champ, weekend, "Qualifiche"),
        "event": qualifying,
        "existing": existing,
        "drivers": drivers_available,  # griglia raggruppata per scuderia
        # La griglia si spegne quando la scelta è già fatta (serve il cestino).
        "picker_locked": bool(existing),
        "max_picks_per_team": max_picks_per_team,
    }
    return render(request, "fantaApp/regular_race_qualifying_choice.html", context)


def _render_race_results_page(
    request, championship_id, weekend_id, event_id, *, race_type, race_label
):
    """Risultati di una gara: si aprono dal via e, finché mancano i risultati,
    mostrano la propria scelta e lo stato della gara (#191, #192)."""
    champ, weekend, player = _base_context(request, championship_id, weekend_id)

    race = get_object_or_404(Race, pk=event_id, weekend=weekend, type=race_type)
    results = race_classification(race)
    state = ss.session_state(race, has_results=bool(results))
    if state == ss.NOT_STARTED:
        messages.info(request, "I risultati si vedono dal via.")
        return redirect(
            reverse("weekend_details", args=[champ.pk, weekend.pk])
            + _origin_query(request)
        )
    classified_results = [entry for entry in results if entry.position is not None]
    # Con player None i filtri restano vuoti: nessuna scelta, nessun punteggio.
    player_choices = list(
        race.playerracechoice_set.filter(player=player)
        .select_related("driver", "driver__team")
        .order_by("driver__team__name", "driver__first_name", "driver__last_name")
    )
    selected_driver_ids = [choice.driver_id for choice in player_choices]
    player_credit_used = sum(choice.spent_amount for choice in player_choices)
    player_pupillo = next(
        (choice for choice in player_choices if choice.is_pupillo), None
    )

    player_race_result = PlayerRaceResult.objects.filter(
        player=player, race=race
    ).first()
    player_weekend_points = (
        player_race_result.total_points if player_race_result else None
    )
    # Griglia di partenza in sola lettura, come controprova della scelta (#233,
    # #234). I costi sono ricalcolati adesso: quanto pagato davvero è nel pannello.
    start_grid = costs.get_race_driver_options(race=race, player=player)
    # Colori ed etichette con la scuderia di questo weekend (#82).
    use_weekend_teams(
        weekend,
        [entry.driver for entry in results]
        + [choice.driver for choice in player_choices]
        + [option["driver"] for option in start_grid],
    )

    context = {
        "championship": champ,
        "weekend": weekend,
        "breadcrumb": _breadcrumb(request, champ, weekend, f"Risultati {race_label}"),
        "session_bar": results_session_bar(
            request, champ, weekend, ("race", race_type), _weekend_sessions(weekend)
        ),
        "event": race,
        "race_label": race_label,
        # Scelte di tutti i giocatori nella stessa gara (GP #209, Sprint #210),
        # solo per chi gioca o gestisce il campionato.
        "all_choices_url": (
            reverse(
                f"{race_type}_race_all_choices", args=[champ.pk, weekend.pk, race.pk]
            )
            + _origin_query(request)
            if player or helper.is_championship_manager(request.user, champ)
            else None
        ),
        "session_state": state,
        "start_grid": start_grid,
        # Nel GP costo griglia, costo classifica e pupillo; nella Sprint il costo.
        "start_grid_breakdown": race_type == "regular",
        # None per chi non gioca: vede solo la classifica ufficiale.
        "player": player,
        "results": results,
        "classified_count": len(classified_results),
        "results_count": len(results),
        "total_points_awarded": sum(entry.points for entry in classified_results),
        "player_choices": player_choices,
        "selected_driver_ids": selected_driver_ids,
        "player_pupillo": player_pupillo,
        "player_weekend_points": player_weekend_points,
        "player_credit_used": player_credit_used,
    }
    return render(request, "fantaApp/race_results.html", context)


@login_required
def sprint_race_results(request, championship_id, weekend_id, event_id):
    return _render_race_results_page(
        request,
        championship_id,
        weekend_id,
        event_id,
        race_type="sprint",
        race_label="Sprint",
    )


@login_required
def regular_race_results(request, championship_id, weekend_id, event_id):
    return _render_race_results_page(
        request,
        championship_id,
        weekend_id,
        event_id,
        race_type="regular",
        race_label="Gran Premio",
    )
