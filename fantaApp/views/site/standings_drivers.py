from django.shortcuts import render

from fantaApp.models import DriverStanding, WeekendParticipant


def standings_drivers(request):
    """Classifica piloti F1 dopo l'ultimo round importato, aperta a tutti.

    Il backend la importa round per round in DriverStanding: si mostrano le
    righe del weekend più recente che ne ha. La scuderia è quella del pilota in
    quel weekend (WeekendParticipant), come nelle altre pagine del weekend.
    """
    latest = (
        DriverStanding.objects.select_related("weekend")
        .order_by("-weekend__season", "-weekend__round_number")
        .first()
    )
    if latest is None:
        return render(
            request, "fantaApp/site/standings_drivers.html", {"weekend": None}
        )

    weekend = latest.weekend
    team_by_driver = {
        p.driver_id: p.team
        for p in WeekendParticipant.objects.filter(weekend=weekend).select_related(
            "team"
        )
    }
    standings = DriverStanding.objects.filter(weekend=weekend).select_related(
        "driver__team"
    )
    rows = [
        {
            "position": s.position,
            "driver": s.driver,
            "team": team_by_driver.get(s.driver_id, s.driver.team),
            "points": s.points,
            "wins": s.wins,
        }
        for s in standings.order_by("position")
    ]
    return render(
        request,
        "fantaApp/site/standings_drivers.html",
        {"weekend": weekend, "rows": rows},
    )
