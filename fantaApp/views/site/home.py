from django.shortcuts import render
from django.utils import timezone

from fantaApp.models import Weekend

# Sessioni del weekend: campo orario di Weekend -> nome nelle pagine (glossario in
# frontend/README.md). Si mostrano in ordine di orario, saltando quelle vuote.
SESSION_FIELDS = (
    ("fp1_start", "Libere 1"),
    ("fp2_start", "Libere 2"),
    ("fp3_start", "Libere 3"),
    ("sprint_qualifying_start", "Qualifiche Sprint"),
    ("sprint_start", "Sprint"),
    ("qualifying_start", "Qualifiche"),
    ("race_start", "Gran Premio"),
)


def _sessions(weekend):
    sessions = [
        {"label": label, "start": getattr(weekend, field)}
        for field, label in SESSION_FIELDS
        if getattr(weekend, field)
    ]
    return sorted(sessions, key=lambda s: s["start"])


def home(request):
    """Home del sito, aperta a tutti: banner del gioco, programma della stagione
    F1 con il prossimo Gran Premio in evidenza, classifiche F1 e news (#92).

    La stagione corrente è l'ultima con weekend nel database. Una sola query:
    gli orari delle sessioni sono campi di Weekend.
    """
    weekends = list(
        Weekend.objects.filter(deleted_at__isnull=True)
        .select_related("circuit")
        .order_by("-season", "round_number")
    )
    season = weekends[0].season if weekends else None
    now = timezone.now()

    programme = []
    next_weekend = None
    for weekend in weekends:
        if weekend.season != season:
            break
        sessions = _sessions(weekend)
        # Un weekend resta "prossimo" fino alla partenza del Gran Premio; senza
        # orario della gara si guarda all'ultima sessione nota.
        end = weekend.race_start or (sessions[-1]["start"] if sessions else None)
        is_past = end is not None and end < now
        item = {"weekend": weekend, "sessions": sessions, "is_past": is_past}
        if next_weekend is None and not is_past:
            next_weekend = item
        programme.append(item)

    return render(
        request,
        "fantaApp/site/home.html",
        {
            "season": season,
            "next_weekend": next_weekend,
            "upcoming": [w for w in programme if not w["is_past"]],
            "past": [w for w in programme if w["is_past"]],
        },
    )
