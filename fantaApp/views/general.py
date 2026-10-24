from django.shortcuts import render, redirect


def home(request):
    """Vetrina per chi non e' autenticato; per gli altri la casa e' la dashboard.

    Senza il redirect la home mostrava un saluto e due bottoni che duplicavano
    la dashboard: un passaggio a vuoto per chi apre il sito dal segnalibro o
    clicca il logo in header. Finché non arriva la home del sito (#92) mostra la
    presentazione del gioco, la stessa di /game/.
    """
    if request.user.is_authenticated:
        return redirect("user_dashboard")
    return render(request, "fantaApp/game_landing.html", {})
