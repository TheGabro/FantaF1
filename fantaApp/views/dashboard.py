from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import render, redirect, get_object_or_404
from ..forms import creations
from ..models import (
    League, ChampionshipManager, ChampionshipPlayer, Championship, Race, Weekend,
    PlayerQualifyingChoice, PlayerQualifyingMultiChoice, PlayerSprintQualifyingChoice,
    PlayerRaceChoice, PlayerRaceResult,
)
from ..services import player_choices as pc
from ..services import costs
from ..services import helper
from .invites import build_invite_url

# Soglie delle statistiche di campionato.
# Magata: Grand Prix sopra i 43 punti (le sprint non contano).
# Sucata: gara sotto i 5 punti (sprint incluse).
MAGATA_POINTS = 43
SUCATA_POINTS = 5

@login_required
def user_dashboard(request):
    user = request.user

    championship = ChampionshipPlayer.objects.filter(
        user=user
    ).select_related('championship', 'league').order_by('championship__active','-championship__year')

    context = {
        "user": user,
        "championship": championship,
        "is_admin": user.user_type == "admin",
        "is_staff": user.user_type == "staff",
        "is_premium": user.user_type == "premium"
    }
    return render(request, "fantaApp/user_dashboard.html", context)


@login_required
def create_championship(request):
    if request.method == 'POST':
        form = creations.ChampionshipForm(request.POST, user=request.user)
        formset = creations.LeagueFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            # Campionato, leghe, manager e iscrizione nascono insieme: senza
            # transazione un errore a metà lascerebbe un campionato senza leghe,
            # che il clean() del modello considera non valido.
            with transaction.atomic():
                championship = form.save()

                leagues = formset.save(commit=False)
                for league in leagues:
                    league.championship = championship
                    league.save()
                # If the user did not specify any league, create a default one
                if not leagues:
                    leagues = [League.objects.create(
                        championship=championship,
                        name="Lega Unica"
                    )]

                ChampionshipManager.objects.get_or_create(
                    user=request.user,
                    championship=championship
                )

                # Manager e giocatore restano ruoli distinti: si diventa
                # giocatori solo spuntando la casella nel form.
                if form.cleaned_data['join_as_player']:
                    index = form.cleaned_data.get('player_league_index') or 0
                    if not 0 <= index < len(leagues):
                        index = 0
                    ChampionshipPlayer.objects.create(
                        user=request.user,
                        championship=championship,
                        league=leagues[index],
                        player_name=form.cleaned_data['player_name'],
                    )

            messages.success(request, f"Campionato «{championship.name}» creato.")
            # Si atterra sulla sezione Info: è lì che sta il link d'invito.
            return redirect('championship_info', championship_id=championship.id)
    else:
        form = creations.ChampionshipForm(user=request.user)
        formset = creations.LeagueFormSet()

    return render(request, 'fantaApp/create_championship.html', {
        'form': form,
        'formset': formset
    })


# ───────────────────────────────────────────────────────────────────────────────
#  Sezioni della dashboard campionato
# ───────────────────────────────────────────────────────────────────────────────
def _section_context(request, championship_id, active_section):
    """
    Contesto comune a tutte le sezioni: campionato, giocatore corrente (None se
    l'utente non è iscritto) e sezione attiva per evidenziare la tab.
    """
    championship = get_object_or_404(Championship, pk=championship_id)

    current_championship_player = ChampionshipPlayer.objects.filter(
        user=request.user, championship=championship).select_related('league').first()

    context = {
        "championship": championship,
        "current_championship_player": current_championship_player,
        "active_section": active_section,
    }
    return championship, current_championship_player, context


def _credits_context(current_championship_player):
    """Crediti del giocatore: disponibili, prenotati su gare future, spendibili ora."""
    if current_championship_player is None:
        return {"reserved_credit": 0, "spendable_credit": 0}
    return {
        "reserved_credit": costs.get_player_reserved_credit(player=current_championship_player),
        "spendable_credit": costs.get_player_spendable_credit(player=current_championship_player),
    }


# ───────────────────────────────────────────────────────────────────────────────
#  Classifiche
# ───────────────────────────────────────────────────────────────────────────────
def _standings_rows(championship, players):
    """
    Statistiche di stagione per ogni giocatore in classifica.

    Tutto deriva da PlayerRaceResult con una sola aggregazione, quindi il costo
    non cresce col numero di giocatori. 'quali_points' resta None: le qualifiche
    non producono punti propri nel modello attuale (danno un moltiplicatore in
    gara regular e un additivo in sprint), serve una definizione lato backend.
    """
    stats_by_player = {
        row["player_id"]: row
        for row in (
            PlayerRaceResult.objects
            .filter(player__championship=championship)
            .values("player_id")
            .annotate(
                races_scored=Count("id"),
                spent=Sum("credit_spent"),
                magate=Count("id", filter=Q(race__type="regular", total_points__gt=MAGATA_POINTS)),
                sucate=Count("id", filter=Q(total_points__lt=SUCATA_POINTS)),
            )
        )
    }

    # Gare della stagione: quante in totale (proiezione) e quante ancora da correre
    # (budget residuo per gara). select_related evita una query per gara in event_start().
    races = list(
        Race.objects
        .filter(weekend__season=championship.year)
        .select_related("weekend")
    )
    total_races = len(races)
    remaining_races = sum(1 for race in races if not helper._event_has_started(race))

    rows = []
    for player in players:
        stats = stats_by_player.get(player.id) or {}
        races_scored = stats.get("races_scored") or 0
        spent = stats.get("spent") or 0
        rows.append({
            "player": player,
            "points": player.total_score,
            "quali_points": None,
            "projection": player.total_score / races_scored * total_races if races_scored else None,
            "credit_left": player.available_credit,
            "spent": spent,
            "avg_spent": spent / races_scored if races_scored else None,
            "budget_per_race": player.available_credit / remaining_races if remaining_races else None,
            "magate": stats.get("magate") or 0,
            "sucate": stats.get("sucate") or 0,
            "races_scored": races_scored,
        })
    return rows, {
        "total_races": total_races,
        "remaining_races": remaining_races,
        "magata_points": MAGATA_POINTS,
        "sucata_points": SUCATA_POINTS,
    }


@login_required
def championship_dashboard(request, championship_id):
    """Classifica generale: tutti i giocatori del campionato, tutte le leghe."""
    championship, current_championship_player, context = _section_context(
        request, championship_id, "standings_general")

    players = ChampionshipPlayer.objects.filter(
        championship=championship
    ).select_related('league').order_by('-total_score')

    rows, season = _standings_rows(championship, players)
    context.update(season)
    context.update({
        "standings_rows": rows,
        "standings_title": "Classifica generale",
        "standings_subtitle": "Tutte le leghe del campionato",
        "show_league_column": True,
    })

    return render(request, "fantaApp/championship_standings.html", context)


@login_required
def championship_league_standings(request, championship_id):
    """Classifica della sola lega in cui gioca l'utente."""
    championship, current_championship_player, context = _section_context(
        request, championship_id, "standings_league")

    players = ChampionshipPlayer.objects.none()
    if current_championship_player:
        players = ChampionshipPlayer.objects.filter(
            championship=championship,
            league=current_championship_player.league,
        ).select_related('league').order_by('-total_score')

    rows, season = _standings_rows(championship, players)
    context.update(season)
    context.update({
        "standings_rows": rows,
        "standings_title": (
            f"Classifica — {current_championship_player.league.name}"
            if current_championship_player else "Classifica di lega"
        ),
        "standings_subtitle": "Solo i giocatori della tua lega",
        "show_league_column": False,
    })

    return render(request, "fantaApp/championship_standings.html", context)


@login_required
def championship_info(request, championship_id):
    """Sezione info: leghe del campionato e manager che lo gestiscono."""
    championship, _, context = _section_context(request, championship_id, "info")

    user_managers = ChampionshipManager.objects.filter(
        championship=championship
    ).select_related('user')

    is_manager = any(m.user_id == request.user.id for m in user_managers)

    context.update({
        # annotate: evita una query per lega sul conteggio dei partecipanti
        "leagues": championship.leagues.annotate(participants_count=Count('participants')),
        "managers": ChampionshipPlayer.objects.filter(
            championship=championship,
            user__in=[m.user for m in user_managers],
        ).select_related('league'),
        "is_manager": is_manager,
        # Il link d'invito si genera al volo dal token firmato: nessuna riga da
        # salvare, ma nemmeno un elenco di chi è stato invitato.
        "invite_url": build_invite_url(request, championship) if is_manager else None,
    })

    return render(request, "fantaApp/championship_info.html", context)


@login_required
def championship_calendar(request, championship_id):
    """Sezione calendario: tutti i weekend della stagione del campionato."""
    championship, _, context = _section_context(request, championship_id, "calendar")

    # select_related: il template legge w.circuit.name per ogni weekend
    context["weekends"] = (
        Weekend.objects
        .filter(season=championship.year)
        .select_related('circuit')
        .order_by("round_number")
    )

    return render(request, "fantaApp/championship_calendar.html", context)


# ───────────────────────────────────────────────────────────────────────────────
#  Sessioni di un weekend
# ───────────────────────────────────────────────────────────────────────────────
# Ordine di svolgimento in pista, con la pagina di scelta corrispondente.
# Rispecchia l'elenco costruito in views.weekend.weekend_detail.
_SESSION_SPECS = (
    ("qualifyings", "sprint",  "Sprint Qualifying", "sprint_race_qualifying_choice"),
    ("races",       "sprint",  "Sprint Race",       "sprint_race_choice"),
    ("qualifyings", "regular", "Qualifying",        "race_qualifying_choice"),
    ("races",       "regular", "Grand Prix",        "regular_race_choice"),
)


def _weekend_sessions(weekend):
    """
    Sessioni presenti nel weekend, nell'ordine in cui si corrono.
    Legge dai prefetch di races/qualifyings: nessuna query per weekend.
    """
    sessions = []
    for related_name, subtype, label, url_name in _SESSION_SPECS:
        event = next(
            (e for e in getattr(weekend, related_name).all() if e.type == subtype),
            None,
        )
        if event is None:
            continue
        # Il prefetch non popola il FK inverso: lo si imposta a mano, così
        # helper.event_start() non emette una query per ogni sessione.
        event.weekend = weekend
        sessions.append({
            "label": label,
            "entity": "qualifying" if related_name == "qualifyings" else "race",
            "subtype": subtype,
            "event": event,
            "url_name": url_name,
            "start": helper.event_start(event),
            "has_started": helper._event_has_started(event),
        })
    return sessions


def _season_weekends(season):
    """Weekend della stagione, pronti per _weekend_sessions()."""
    return (
        Weekend.objects
        .filter(season=season)
        .select_related('circuit')
        .prefetch_related('races', 'qualifyings')
        .order_by("round_number")
    )


def _player_choice_index(player, season):
    """Coppie (entity, event_id) per cui il giocatore ha già registrato una scelta."""
    made = {
        ("race", race_id)
        for race_id in PlayerRaceChoice.objects
        .filter(player=player, race__weekend__season=season)
        .values_list("race_id", flat=True)
    }
    for queryset in (
        PlayerQualifyingChoice.objects.filter(player=player, qualifying__weekend__season=season),
        PlayerQualifyingMultiChoice.objects.filter(player=player, qualifying__weekend__season=season),
        PlayerSprintQualifyingChoice.objects.filter(player=player, qualifying__weekend__season=season),
    ):
        made.update(
            ("qualifying", qualifying_id)
            for qualifying_id in queryset.values_list("qualifying_id", flat=True)
        )
    return made


@login_required
def championship_next_races(request, championship_id):
    """Prossime gare: sessioni non ancora iniziate, con lo stato della scelta."""
    championship, current_championship_player, context = _section_context(
        request, championship_id, "next_races")
    context.update(_credits_context(current_championship_player))

    already_chosen = set()
    if current_championship_player:
        already_chosen = _player_choice_index(current_championship_player, championship.year)

    open_weekends = []
    pending_count = 0
    for weekend in _season_weekends(championship.year):
        sessions = []
        for session in _weekend_sessions(weekend):
            if session["has_started"]:
                continue  # sessione chiusa: la scelta non è più modificabile
            session["has_choice"] = (session["entity"], session["event"].id) in already_chosen
            if not session["has_choice"]:
                pending_count += 1
            sessions.append(session)
        if sessions:
            open_weekends.append({"weekend": weekend, "sessions": sessions})

    context.update({
        "open_weekends": open_weekends,
        "pending_count": pending_count,
    })
    return render(request, "fantaApp/championship_next_races.html", context)


@login_required
def championship_my_choices(request, championship_id):
    """Sezione riepilogo: scelte effettuate e punti ottenuti, weekend per weekend."""
    championship, current_championship_player, context = _section_context(
        request, championship_id, "my_choices")
    context.update(_credits_context(current_championship_player))

    if current_championship_player is None:
        context["weekend_summaries"] = []
        return render(request, "fantaApp/championship_my_choices.html", context)

    season = championship.year
    player = current_championship_player

    # Scelte e risultati della stagione, caricati in blocco e raggruppati per evento.
    race_choices = defaultdict(list)
    for choice in (
        PlayerRaceChoice.objects
        .filter(player=player, race__weekend__season=season)
        .select_related('driver', 'driver__team')
        .order_by('-is_pupillo', 'driver__last_name')
    ):
        race_choices[choice.race_id].append(choice)

    race_results = {
        result.race_id: result
        for result in PlayerRaceResult.objects.filter(player=player, race__weekend__season=season)
    }

    # Le scelte di qualifica si raggruppano per slot: un multi-choice può avere
    # sei piloti sullo stesso slot, ripetere l'etichetta per ognuno è illeggibile.
    slots_by_qualifying = defaultdict(dict)
    for choice in (
        PlayerQualifyingChoice.objects
        .filter(player=player, qualifying__weekend__season=season)
        .select_related('driver', 'driver__team')
    ):
        slots_by_qualifying[choice.qualifying_id].setdefault("Pilota scelto", []).append(choice)
    for model in (PlayerQualifyingMultiChoice, PlayerSprintQualifyingChoice):
        for choice in (
            model.objects
            .filter(player=player, qualifying__weekend__season=season)
            .select_related('driver', 'driver__team')
            .order_by('selection_slot', 'driver__last_name')
        ):
            (slots_by_qualifying[choice.qualifying_id]
             .setdefault(choice.get_selection_slot_display(), [])
             .append(choice))

    qualifying_slots = {
        qualifying_id: [
            {"slot": label, "choices": choices}
            for label, choices in labels.items()
        ]
        for qualifying_id, labels in slots_by_qualifying.items()
    }

    weekend_summaries = []
    skipped_weekends = []
    season_points = 0.0
    season_spent = 0
    for weekend in _season_weekends(season):
        sessions = []
        weekend_points = 0.0
        weekend_spent = 0
        has_activity = False
        has_started = False
        is_scored = False

        for session in _weekend_sessions(weekend):
            has_started = has_started or session["has_started"]
            event_id = session["event"].id

            if session["entity"] == "race":
                choices = race_choices.get(event_id, [])
                result = race_results.get(event_id)
                session["choices"] = choices
                session["result"] = result
                session["spent"] = sum(choice.spent_amount for choice in choices)
                weekend_spent += session["spent"]
                if result:
                    weekend_points += result.total_points
                    is_scored = True
                has_activity = has_activity or bool(choices) or result is not None
            else:
                session["slots"] = qualifying_slots.get(event_id, [])
                has_activity = has_activity or bool(session["slots"])

            sessions.append(session)

        if not has_activity:
            # Weekend già iniziato ma mai giocato: si riassume in una riga sola,
            # per non riempire la pagina di card vuote. Quelli futuri sono in "Da giocare".
            if has_started:
                skipped_weekends.append(weekend)
            continue

        season_points += weekend_points
        season_spent += weekend_spent
        weekend_summaries.append({
            "weekend": weekend,
            "sessions": sessions,
            "points": weekend_points,
            "spent": weekend_spent,
            # Senza PlayerRaceResult il punteggio non è "zero": non è ancora stato
            # calcolato, e il template deve dirlo invece di mostrare uno 0 grande.
            "is_scored": is_scored,
        })

    weekend_summaries.reverse()  # il weekend più recente per primo

    context.update({
        "weekend_summaries": weekend_summaries,
        "skipped_weekends": skipped_weekends,
        "season_points": season_points,
        "season_spent": season_spent,
        "played_count": len(weekend_summaries),
    })
    return render(request, "fantaApp/championship_my_choices.html", context)