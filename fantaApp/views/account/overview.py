from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def overview(request):
    """Account → Panoramica: i dati dell'account e i link alle altre sezioni (#96)."""
    return render(
        request,
        "fantaApp/account/overview.html",
        {
            "account_page": "overview",
            "championships_count": request.user.championshipplayer_set.count(),
        },
    )
