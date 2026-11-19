"""Find a championship to join (#72): every championship that still accepts players."""

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from fantaApp.models import ChampionshipJoinRequest, ChampionshipPlayer
from fantaApp.services import enrollment


@login_required
def search(request):
    query = request.GET.get("q", "").strip()
    open_championships = enrollment.open_championships()
    championships = open_championships.annotate(players=Count("participants"))
    if query:
        championships = championships.filter(name__icontains=query)

    return render(request, "fantaApp/championship_search.html", {
        "query": query,
        "championships": championships.order_by("year", "name"),
        # Suggestions while typing, through a native <datalist>.
        # ponytail: every open name goes in the page; switch to a JSON endpoint
        # if open championships grow to the hundreds.
        "suggestions": open_championships.order_by("name").values_list("name", flat=True).distinct(),
        # Sets: the template checks membership once per card.
        "enrolled_ids": set(
            ChampionshipPlayer.objects.filter(user=request.user).values_list("championship_id", flat=True)
        ),
        "pending_ids": set(
            ChampionshipJoinRequest.objects.filter(
                user=request.user, status=ChampionshipJoinRequest.Status.PENDING
            ).values_list("championship_id", flat=True)
        ),
    })
