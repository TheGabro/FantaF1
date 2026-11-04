from django.contrib.auth.decorators import login_required

from fantaApp.models import ChampionshipPlayer
from fantaApp.services import helper
from fantaApp.views import dashboard
from fantaApp.views.championship import manage


@login_required
def entry(request, championship_id):
    """Ingresso del campionato (#155): si entra per giocare o per gestire.

    Chi gioca vede il prossimo weekend, un manager che non gioca la scheda
    Gestione, gli altri la classifica generale. La pagina si mostra qui senza
    redirect: dopo l'iscrizione e dai vecchi indirizzi si arriva già con un
    rimando, e la scheda attiva resta quella giusta perché la disegna la view
    della sezione.
    """
    if ChampionshipPlayer.objects.filter(
        user=request.user, championship_id=championship_id
    ).exists():
        return dashboard.championship_next_weekend(request, championship_id)
    if helper.is_championship_manager(request.user, championship_id):
        return manage.players(request, championship_id)
    return dashboard.championship_general_standings(request, championship_id)
