"""Scelte dei giocatori nel Gran Premio (#203)."""

from django.contrib.auth.decorators import login_required

from ._common import render_race_all_choices


@login_required
def regular_race_all_choices(request, championship_id, weekend_id, event_id):
    return render_race_all_choices(
        request,
        championship_id,
        weekend_id,
        event_id,
        race_type="regular",
        label="Gran Premio",
    )
