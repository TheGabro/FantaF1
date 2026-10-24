from django.shortcuts import render


def landing(request):
    """Presentazione del gioco, aperta a tutti: chi ha già un account trova il
    pulsante per i suoi campionati al posto delle schede di iscrizione e accesso."""
    return render(request, "fantaApp/game_landing.html")
