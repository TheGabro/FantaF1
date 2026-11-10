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

    return render(
        request,
        "fantaApp/site/race_results.html",
        {"weekend": weekend, "races": races},
    )
