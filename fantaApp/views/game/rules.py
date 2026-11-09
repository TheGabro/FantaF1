from django.shortcuts import render

from ..rulebook import rulebook


def rules(request):
    """Regolamento del gioco (#81), aperto a tutti: è lo stesso per ogni
    campionato, quindi si legge anche prima di iscriversi."""
    return render(request, "fantaApp/game_rules.html", {"rulebook": rulebook()})
