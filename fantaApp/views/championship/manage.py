from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from fantaApp.models import Championship, ChampionshipManager, ChampionshipPlayer
from fantaApp.services import helper
from fantaApp.views import dashboard


@login_required
def players(request, championship_id):
    """Manage → Players (#70): enrolled players grouped by league, managers only."""
    championship, _, context = dashboard._section_context(
        request, championship_id, "manage_players"
    )

    # Hiding the tab is not access control: anyone can type the URL.
    if not context["is_manager"]:
        messages.error(request, "Questa sezione è riservata ai manager del campionato.")
        return redirect("championship_dashboard", championship_id=championship.id)

    context.update(
        {
            # Two queries in total (leagues + players with their user), however
            # many leagues and players there are.
            "leagues": championship.leagues.order_by("id").prefetch_related(
                Prefetch(
                    "participants",
                    queryset=ChampionshipPlayer.objects.select_related("user").order_by(
                        "player_name"
                    ),
                )
            ),
            # A set: the template checks membership once per player row.
            "manager_user_ids": set(
                championship.managers.values_list("user_id", flat=True)
            ),
        }
    )
    return render(request, "fantaApp/championship_manage_players.html", context)


@login_required
@require_POST
def promote_manager(request, championship_id, player_id):
    """Make a player of this championship a manager. All managers are peers."""
    championship = get_object_or_404(Championship, pk=championship_id)

    if not helper.is_championship_manager(request.user, championship):
        messages.error(request, "Solo un manager può nominare altri manager.")
        return redirect("championship_dashboard", championship_id=championship.id)

    # Filtering by championship too: a manager of A must not be able to
    # promote someone by passing the id of a player of championship B.
    player = get_object_or_404(
        ChampionshipPlayer.objects.select_related("user"),
        pk=player_id,
        championship=championship,
    )

    _, created = ChampionshipManager.objects.get_or_create(
        user=player.user, championship=championship
    )
    if created:
        messages.success(request, f"{player.player_name} ora è manager del campionato.")
    else:
        messages.info(request, f"{player.player_name} era già manager del campionato.")

    return redirect("championship_manage_players", championship_id=championship.id)


@login_required
@require_POST
def demote_manager(request, championship_id, player_id):
    """Take the manager role away from a player. The last manager cannot leave."""
    championship = get_object_or_404(Championship, pk=championship_id)

    if not helper.is_championship_manager(request.user, championship):
        messages.error(request, "Solo un manager può togliere il ruolo a un altro manager.")
        return redirect("championship_dashboard", championship_id=championship.id)

    player = get_object_or_404(
        ChampionshipPlayer.objects.select_related("user"),
        pk=player_id,
        championship=championship,
    )

    with transaction.atomic():
        # Locking the championship row serializes demotions: two managers
        # removing each other at the same time cannot leave it with none.
        Championship.objects.select_for_update().get(pk=championship.pk)
        managers = ChampionshipManager.objects.filter(championship=championship)
        if not managers.filter(user=player.user).exists():
            messages.info(request, f"{player.player_name} non è manager del campionato.")
            return redirect("championship_manage_players", championship_id=championship.id)
        if managers.count() == 1:
            messages.error(
                request,
                "Il campionato deve avere almeno un manager: nominane un altro prima.",
            )
            return redirect("championship_manage_players", championship_id=championship.id)
        managers.filter(user=player.user).delete()

    if player.user == request.user:
        # The page is no longer theirs to see.
        messages.success(request, "Non sei più manager del campionato.")
        return redirect("championship_dashboard", championship_id=championship.id)

    messages.success(request, f"{player.player_name} non è più manager del campionato.")
    return redirect("championship_manage_players", championship_id=championship.id)
