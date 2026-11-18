from django.http import Http404
from django.shortcuts import render

from fantaApp.models import Weekend
from fantaApp.views.race_classification import race_classification
from fantaApp.views.weekend_teams import use_weekend_teams

# Gare mostrate, nell'ordine della pagina: prima il Gran Premio, poi la Sprint.
RACES = (("regular", "Gran Premio"), ("sprint", "Sprint"))


def race_results(request, season, round_number):
    """Risultati F1 di un weekend (#134), aperti a tutti: Gran Premio e, nei
    weekend sprint, Sprint. Le scuderie sono quelle del weekend (roster, #82)."""
    weekend = (
        Weekend.objects.filter(
            season=season, round_number=round_number, deleted_at__isnull=True
        )
        .select_related("circuit")
        .prefetch_related("races")
        .order_by("id")
        .first()
    )
    if weekend is None:
        raise Http404("Weekend non trovato")

    by_type = {race.type: race for race in weekend.races.all()}
    races = []
    for race_type, label in RACES:
        race = by_type.get(race_type)
        if race is None:
            continue
        results = race_classification(race)
        use_weekend_teams(weekend, [entry.driver for entry in results])
        races.append({"label": label, "results": results})

    # Anteprima del link nelle chat (#295), letta da _share_meta.html.
    share_description = f"Risultati F1 del {weekend.event_name} {weekend.season}"
    if races:
        share_description += ": ordine d'arrivo " + " e ".join(
            "del Gran Premio" if race["label"] == "Gran Premio" else "della Sprint"
            for race in races
        )

    return render(
        request,
        "fantaApp/site/race_results.html",
        {
            "weekend": weekend,
            "races": races,
            "share_title": f"{weekend.event_name} {weekend.season} · Risultati — Fanta F1",
            "share_description": f"{share_description}.",
        },
    )
