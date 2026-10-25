from django.contrib.auth.decorators import login_required

from fantaApp.models import ChampionshipPlayer
from fantaApp.views import dashboard


@login_required
def entry(request, championship_id):
    """Ingresso del campionato: le classifiche (#113), anche a stagione finita.

    Chi gioca vede la classifica della sua lega, gli altri la generale. La
    pagina si mostra qui senza redirect: dopo l'iscrizione e dai vecchi
    indirizzi si arriva già con un rimando, e la scheda attiva resta quella
    giusta perché la disegna la view delle classifiche.
    """
    plays = ChampionshipPlayer.objects.filter(
        user=request.user, championship_id=championship_id
    ).exists()
    standings = (
        dashboard.championship_league_standings
        if plays
        else dashboard.championship_general_standings
    )
    return standings(request, championship_id)
