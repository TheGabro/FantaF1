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
    PlayerRaceChoice, PlayerRaceResult, QualifyingResult,
)
from ..services import player_choices as pc
from ..services import bonuses
from ..services import costs
from ..services import helper
from ..services import rules
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
# Navigazione a due livelli: gruppo (tab principale) → sezioni (sotto-tab).
# È l'unico posto dove la struttura è descritta: il template la legge da qui,
# quindi aggiungere una sezione resta una voce sola più view e URL.
CHAMPIONSHIP_NAV = (
    {
        "group": "play",
        "label": "Gioca",
        "sections": (
            {"section": "next_weekend", "label": "Prossimo weekend", "url_name": "championship_dashboard"},
            {"section": "my_choices", "label": "Le mie scelte", "url_name": "championship_my_choices"},
            {"section": "calendar", "label": "Calendario gare", "url_name": "championship_calendar"},
        ),
    },
    {
        "group": "standings",
        "label": "Classifiche",
        "sections": (
            {"section": "standings_league", "label": "Lega", "url_name": "championship_league_standings"},
            {"section": "standings_general", "label": "Generale", "url_name": "championship_general_standings"},
            {"section": "standings_qualifying", "label": "Qualifiche", "url_name": "championship_qualifying_standings"},
            {"section": "standings_sprint", "label": "Sprint", "url_name": "championship_sprint_standings"},
        ),
    },
    {
        "group": "info",
        "label": "Info",
        "sections": (
            {"section": "info", "label": "Info", "url_name": "championship_info"},
        ),
    },
)


def _nav_context(active_section):
    """Gruppo attivo e relativi sotto-tab (nessuno se il gruppo ha una sola sezione)."""
    active_group = next(
        (
            group for group in CHAMPIONSHIP_NAV
            if any(section["section"] == active_section for section in group["sections"])
        ),
        CHAMPIONSHIP_NAV[0],
    )
    return {
        "nav_groups": CHAMPIONSHIP_NAV,
        "active_group": active_group["group"],
        "nav_subsections": active_group["sections"] if len(active_group["sections"]) > 1 else (),
    }


def _section_context(request, championship_id, active_section):
    """
    Contesto comune a tutte le sezioni: campionato, giocatore corrente (None se
    l'utente non è iscritto), sezione attiva e navigazione.
    """
    championship = get_object_or_404(Championship, pk=championship_id)

    current_championship_player = ChampionshipPlayer.objects.filter(
        user=request.user, championship=championship).select_related('league').first()

    context = {
        "championship": championship,
        "current_championship_player": current_championship_player,
        "active_section": active_section,
    }
    context.update(_nav_context(active_section))
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
def _number(value, decimals=0):
    """Valore pronto da stampare in tabella: '—' quando il dato non c'è."""
    if value is None:
        return "—"
    return f"{value:.{decimals}f}"


def _render_standings(request, context, *, title, subtitle, groups, rows,
                      show_league_column=False, legend=(), empty_message=None):
    """
    Rende una qualsiasi delle quattro classifiche con lo stesso template.

    'groups' descrive le colonne (etichetta di gruppo + colonne), 'rows' porta
    per ogni giocatore i valori già formattati: così la tabella resta una sola
    e ogni classifica decide solo cosa mostrarci dentro.
    """
    context.update({
        "standings_title": title,
        "standings_subtitle": subtitle,
        "standings_groups": groups,
        "standings_rows": rows,
        "show_league_column": show_league_column,
        # colspan della riga "nessun dato": # + Giocatore (+ Lega) + le colonne
        "standings_colspan": (
            sum(len(group["columns"]) for group in groups) + (3 if show_league_column else 2)
        ),
        "standings_legend": legend,
        "standings_empty_message": empty_message or "Nessun partecipante iscritto.",
    })
    return render(request, "fantaApp/championship_standings.html", context)


# ── Classifiche generale e di lega ─────────────────────────────────────────────
def _season_standings_rows(championship, players):
    """
    Statistiche di stagione per ogni giocatore in classifica.

    Tutto deriva da PlayerRaceResult con una sola aggregazione, quindi il costo
    non cresce col numero di giocatori.
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
        projection = player.total_score / races_scored * total_races if races_scored else None
        rows.append({
            "player": player,
            "values": {
                "points": _number(player.total_score),
                "projection": _number(projection),
                "credit_left": _number(player.available_credit),
                "spent": _number(spent),
                "avg_spent": _number(spent / races_scored if races_scored else None),
                "budget_per_race": _number(
                    player.available_credit / remaining_races if remaining_races else None
                ),
                "magate": _number(stats.get("magate") or 0),
                "sucate": _number(stats.get("sucate") or 0),
            },
        })
    return rows, total_races, remaining_races


_SEASON_STANDINGS_GROUPS = (
    {"label": "Punti", "columns": (
        {"label": "Fatti", "key": "points", "kind": "num", "emphasis": True},
        {"label": "Proiezione", "key": "projection", "kind": "soft"},
    )},
    {"label": "Fantamilioni", "columns": (
        {"label": "Rimasti", "key": "credit_left", "kind": "num"},
        {"label": "Spesi", "key": "spent", "kind": "num"},
        {"label": "Media spesa", "key": "avg_spent", "kind": "soft"},
        {"label": "Budget/gara", "key": "budget_per_race", "kind": "soft"},
    )},
    {"label": "Gare", "columns": (
        {"label": "Magate", "key": "magate", "kind": "num", "tone": "ok"},
        {"label": "Sucate", "key": "sucate", "kind": "num", "tone": "accent"},
    )},
)


def _season_standings_legend(total_races, remaining_races):
    return (
        {"term": "Proiezione",
         "description": f"Punti attuali rapportati alle {total_races} gare della stagione, sul ritmo tenuto finora."},
        {"term": "Media spesa",
         "description": "Fantamilioni spesi diviso le gare già disputate dal giocatore."},
        {"term": "Budget/gara",
         "description": (
             f"Fantamilioni rimasti diviso le {remaining_races} gare ancora da correre. "
             "Non tiene conto delle prenotazioni già fatte."
             if remaining_races else
             "Non disponibile: non ci sono più gare da correre in questa stagione."
         )},
        {"term": "Magate e sucate",
         "description": (
             f"Grand Prix sopra i {MAGATA_POINTS} punti (le sprint non contano) "
             f"e gare sotto i {SUCATA_POINTS} punti."
         )},
        {"term": "Punti qualifica",
         "description": "Non entrano in questo totale: hanno una classifica loro, nella tab Qualifiche."},
    )


@login_required
def championship_general_standings(request, championship_id):
    """Classifica generale: tutti i giocatori del campionato, tutte le leghe."""
    championship, current_championship_player, context = _section_context(
        request, championship_id, "standings_general")

    players = ChampionshipPlayer.objects.filter(
        championship=championship
    ).select_related('league').order_by('-total_score')

    rows, total_races, remaining_races = _season_standings_rows(championship, players)
    return _render_standings(
        request, context,
        title="Classifica generale",
        subtitle="Tutte le leghe del campionato",
        groups=_SEASON_STANDINGS_GROUPS,
        rows=rows,
        show_league_column=True,
        legend=_season_standings_legend(total_races, remaining_races),
    )


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

    rows, total_races, remaining_races = _season_standings_rows(championship, players)
    return _render_standings(
        request, context,
        title=(
            f"Classifica — {current_championship_player.league.name}"
            if current_championship_player else "Classifica di lega"
        ),
        subtitle="Solo i giocatori della tua lega",
        groups=_SEASON_STANDINGS_GROUPS,
        rows=rows,
        legend=_season_standings_legend(total_races, remaining_races),
        empty_message=(
            "Nessun partecipante iscritto." if current_championship_player else
            "Non sei iscritto a questo campionato, quindi non hai una lega di cui vedere la classifica."
        ),
    )


# ── Classifica qualifiche ──────────────────────────────────────────────────────
def _qualifying_points_by_player(championship):
    """
    Punti qualifica di stagione per giocatore, calcolati al volo.

    Non esiste un PlayerQualifyingResult: i punti stanno solo nelle tabelle di
    rules.py e vengono ricavati qui da scelte + risultati, caricati in blocco
    (tre query in tutto, indipendenti dal numero di giocatori). Se un domani il
    backend li persiste, questa funzione si riduce a una query su quel modello.

    Ritorna {player_id: {"points": int, "played": int, "best": int}}, dove
    'played' conta solo le qualifiche con i risultati già disponibili.
    """
    season = championship.year

    results_by_qualifying = defaultdict(dict)
    for result in QualifyingResult.objects.filter(qualifying__weekend__season=season):
        results_by_qualifying[result.qualifying_id][result.driver_id] = result

    stats = defaultdict(lambda: {"points": 0, "played": 0, "best": 0})

    def record(player_id, points):
        entry = stats[player_id]
        entry["points"] += points
        entry["played"] += 1
        entry["best"] = max(entry["best"], points)

    # Weekend regular: un pilota solo, punti in base alla posizione ottenuta.
    for choice in (
        PlayerQualifyingChoice.objects
        .filter(
            player__championship=championship,
            qualifying__weekend__season=season,
            qualifying__type="regular",
        )
    ):
        results = results_by_qualifying.get(choice.qualifying_id)
        if not results:
            continue  # qualifica non ancora corsa o risultati non importati
        result = results.get(choice.driver_id)
        position = result.position if result else None
        record(
            choice.player_id,
            bonuses.get_regular_qualifying_bonus_rule(position)["qualifying_points"]
            if position else 0,
        )

    # Weekend sprint: multichoice Q1/Q2/Q3, punti in base al livello raggiunto.
    choices_by_player_qualifying = defaultdict(lambda: defaultdict(list))
    for player_id, qualifying_id, slot, driver_id in (
        PlayerQualifyingMultiChoice.objects
        .filter(
            player__championship=championship,
            qualifying__weekend__season=season,
            qualifying__weekend__weekend_type="sprint",
        )
        .values_list("player_id", "qualifying_id", "selection_slot", "driver_id")
    ):
        choices_by_player_qualifying[(player_id, qualifying_id)][slot].append(driver_id)

    for (player_id, qualifying_id), choices_by_slot in choices_by_player_qualifying.items():
        results = results_by_qualifying.get(qualifying_id)
        if not results:
            continue
        level = bonuses.resolve_multichoice_level(
            choices_by_slot=choices_by_slot,
            results_by_driver_id=results,
        )
        record(player_id, bonuses.get_qualifying_multichoice_bonus_rule(level)["qualifying_points"])

    return stats


@login_required
def championship_qualifying_standings(request, championship_id):
    """Minigioco qualifiche: somma dei punti ottenuti nelle qualifiche del sabato."""
    championship, current_championship_player, context = _section_context(
        request, championship_id, "standings_qualifying")

    stats = _qualifying_points_by_player(championship)
    players = ChampionshipPlayer.objects.filter(
        championship=championship).select_related('league')

    rows = []
    for player in players:
        entry = stats.get(player.id) or {"points": 0, "played": 0, "best": 0}
        played = entry["played"]
        rows.append({
            "player": player,
            "sort_key": entry["points"],
            "values": {
                "points": _number(entry["points"]),
                "average": _number(entry["points"] / played if played else None),
                "best": _number(entry["best"]) if played else "—",
                "played": _number(played),
            },
        })
    rows.sort(key=lambda row: row["sort_key"], reverse=True)

    return _render_standings(
        request, context,
        title="Classifica qualifiche",
        subtitle="Punti raccolti nelle qualifiche del sabato",
        groups=(
            {"label": "Punti qualifica", "columns": (
                {"label": "Totale", "key": "points", "kind": "num", "emphasis": True},
                {"label": "Media", "key": "average", "kind": "soft"},
                {"label": "Migliore", "key": "best", "kind": "soft"},
            )},
            {"label": "Qualifiche", "columns": (
                {"label": "Valutate", "key": "played", "kind": "num"},
            )},
        ),
        rows=rows,
        show_league_column=True,
        legend=(
            {"term": "Weekend regular",
             "description": "Punti in base alla posizione del pilota scelto: 10 al P16, 100 al P10, 1000 alla pole."},
            {"term": "Weekend sprint",
             "description": (
                 f"Punti in base al livello raggiunto col multichoice: "
                 f"{rules.QUALIFYING_MULTICHOICE_BONUS_RULES['q1_pass']['qualifying_points']} col Q1, "
                 f"{rules.QUALIFYING_MULTICHOICE_BONUS_RULES['q2_pass']['qualifying_points']} col Q2, "
                 f"{rules.QUALIFYING_MULTICHOICE_BONUS_RULES['q3_top3']['qualifying_points']} con l'en plein sulla top 3."
             )},
            {"term": "Valutate",
             "description": "Qualifiche giocate di cui sono già arrivati i risultati: le altre non contano ancora."},
            {"term": "Da sapere",
             "description": (
                 "Questi punti non entrano nel totale della classifica generale ed è un minigioco a sé. "
                 "Sono ricalcolati a ogni caricamento dalle tabelle del regolamento, non salvati a database."
             )},
        ),
    )


# ── Classifica campionato sprint ───────────────────────────────────────────────
@login_required
def championship_sprint_standings(request, championship_id):
    """Minigioco sprint: punti delle sole gare sprint, shootout incluso."""
    championship, current_championship_player, context = _section_context(
        request, championship_id, "standings_sprint")

    stats_by_player = {
        row["player_id"]: row
        for row in (
            PlayerRaceResult.objects
            .filter(player__championship=championship, race__type="sprint")
            .values("player_id")
            .annotate(
                points=Sum("total_points"),
                fia_points=Sum("fia_points"),
                bonus=Sum("point_modifier"),
                races=Count("id"),
                spent=Sum("credit_spent"),
            )
        )
    }

    players = ChampionshipPlayer.objects.filter(
        championship=championship).select_related('league')

    rows = []
    for player in players:
        stats = stats_by_player.get(player.id) or {}
        points = stats.get("points") or 0
        rows.append({
            "player": player,
            "sort_key": points,
            "values": {
                "points": _number(points),
                "fia_points": _number(stats.get("fia_points") or 0),
                "bonus": _number(stats.get("bonus") or 0),
                "races": _number(stats.get("races") or 0),
                "spent": _number(stats.get("spent") or 0),
            },
        })
    rows.sort(key=lambda row: row["sort_key"], reverse=True)

    return _render_standings(
        request, context,
        title="Classifica campionato sprint",
        subtitle="Solo le sprint: shootout del venerdì e sprint race",
        groups=(
            {"label": "Punti sprint", "columns": (
                {"label": "Totale", "key": "points", "kind": "num", "emphasis": True},
                {"label": "Punti FIA", "key": "fia_points", "kind": "soft"},
                {"label": "Bonus shootout", "key": "bonus", "kind": "soft", "tone": "ok"},
            )},
            {"label": "Gare", "columns": (
                {"label": "Disputate", "key": "races", "kind": "num"},
            )},
            {"label": "Fantamilioni", "columns": (
                {"label": "Spesi", "key": "spent", "kind": "num"},
            )},
        ),
        rows=rows,
        show_league_column=True,
        legend=(
            {"term": "Punti FIA",
             "description": "Punti ufficiali presi in sprint race dai piloti schierati."},
            {"term": "Bonus shootout",
             "description": (
                 "Punti aggiunti dal pronostico sullo sprint qualifying: "
                 "+1 indovinando la fascia 11-15, +2 indovinando la 6-10."
             )},
            {"term": "Da sapere",
             "description": "Il totale è già compreso nella classifica generale: qui è isolato il solo contributo delle sprint."},
        ),
    )


# Etichette leggibili dei livelli bonus, per le tabelle del regolamento.
_MULTICHOICE_LEVEL_LABELS = {
    "q1_pass": "Tutti e 6 i piloti indicati passano il Q1",
    "q2_pass": "…e tutti e 5 quelli del secondo slot passano il Q2",
    "q3_top3": "…e la top 3 del Q3 è indovinata in pieno",
}
_SHOOTOUT_LEVEL_LABELS = {
    "made": "Pronostico fatto, nessuna fascia indovinata",
    "sq1_hit": "Indovinata la fascia oltre la 15ª",
    "sq2_hit": "Indovinata la fascia 11-15",
    "sq3_hit": "Indovinata la fascia 6-10",
}


def _rulebook():
    """
    Il regolamento mostrato in Info, letto dalle tabelle di rules.py: essendo
    la stessa sorgente usata dal calcolo, non può divergere dal gioco vero.
    """
    return {
        "regular_qualifying": [
            {"position": position, **values}
            for position, values in sorted(rules.REGULAR_QUALIFYING_BONUS_BY_POSITION.items())
        ],
        "multichoice": [
            {"label": _MULTICHOICE_LEVEL_LABELS[level], **rules.QUALIFYING_MULTICHOICE_BONUS_RULES[level]}
            for level in ("q1_pass", "q2_pass", "q3_top3")
        ],
        "shootout": [
            {"label": _SHOOTOUT_LEVEL_LABELS[level], **rules.SPRINT_BONUS_RULES[level]}
            for level in ("made", "sq1_hit", "sq2_hit", "sq3_hit")
        ],
        "grid_costs": [
            {
                "position": position,
                "regular": cost,
                "sprint": rules.SPRINT_RACE_COST_BY_GRID_POSITION.get(position, 0),
                "standings_extra": rules.COST_BY_STANDINGS_POSITION.get(position),
            }
            for position, cost in sorted(rules.REGULAR_RACE_COST_BY_GRID_POSITION.items())
            # Oltre la decima il costo è zero ovunque: righe inutili da mostrare
            if cost or rules.SPRINT_RACE_COST_BY_GRID_POSITION.get(position, 0)
        ],
        "pupillo_step": rules.PUPILLO_DISCOUNT_STEP,
        "pupillo_max": rules.PUPILLO_MAX_DISCOUNT,
        "magata_points": MAGATA_POINTS,
        "sucata_points": SUCATA_POINTS,
        "multi_choice_slot_sizes": rules.MULTI_CHOICE_SLOT_SIZES,
    }


@login_required
def championship_info(request, championship_id):
    """Sezione info: regolamento, leghe del campionato e manager che lo gestiscono."""
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
        "rulebook": _rulebook(),
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
def championship_next_weekend(request, championship_id):
    """
    Landing del campionato: il prossimo weekend da giocare, in evidenza, e in
    coda gli altri weekend con scelte ancora aperte.
    """
    championship, current_championship_player, context = _section_context(
        request, championship_id, "next_weekend")
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
            open_weekends.append({
                "weekend": weekend,
                "sessions": sessions,
                "pending": sum(1 for session in sessions if not session["has_choice"]),
                # Prima sessione che chiude: è la scadenza vera del weekend.
                "deadline": sessions[0]["start"],
            })

    next_weekend = open_weekends[0] if open_weekends else None
    context.update({
        "next_weekend": next_weekend,
        "other_weekends": open_weekends[1:],
        "pending_count": pending_count,
    })
    return render(request, "fantaApp/championship_next_weekend.html", context)


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