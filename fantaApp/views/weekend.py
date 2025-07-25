from django.shortcuts import render, redirect, get_object_or_404
from ..models import Championship, Weekend


def weekend_detail(request, championship_id, weekend_id):
    championship = get_object_or_404(Championship, pk=championship_id)
    weekend = get_object_or_404(Weekend, pk=weekend_id)

    events = []
    # Sprint-Qualifying
    sq = weekend.Qualifying.filter(type="sprint").first()
    if sq:
        events.append({"label": "Sprint Qualifying",
                       "event_type": "sprint-qualifying",
                       "event_id": sq.id})
    # Sprint Race
    sr = weekend.Race.filter(type="sprint").first()
    if sr:
        events.append({"label": "Sprint Race",
                       "event_type": "sprint",
                       "event_id": sr.id})
    # Qualifying (gara regolare)
    q = weekend.Qualifying.filter(type="regular").first()
    if q:
        events.append({"label": "Qualifying",
                       "event_type": "qualifying",
                       "event_id": q.id})
    # Race
    r = weekend.Race.filter(type="regular").first()
    if r:
        events.append({"label": "Grand Prix",
                       "event_type": "race",
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