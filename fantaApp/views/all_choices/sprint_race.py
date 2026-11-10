"""Scelte dei giocatori nella Sprint (#204): solo i dati della gara, il bonus
delle Qualifiche Sprint sta nella sua pagina (#207)."""

from django.contrib.auth.decorators import login_required

from ._common import render_race_all_choices


@login_required
def sprint_race_all_choices(request, championship_id, weekend_id, event_id):
    return render_race_all_choices(
        request,
        championship_id,
        weekend_id,
        event_id,
        race_type="sprint",
        label="Sprint",
    )
