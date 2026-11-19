"""When a championship accepts new players (#148).

Every championship of a year starts with the first weekend of that season:
- joining, and sending a join request, closes ENROLLMENT_CLOSES_BEFORE the
  first qualifying of the season;
- managers can approve pending requests until FP1 of the first weekend.

If the calendar of the year is not loaded yet, the dates are unknown and
enrollment stays open.
"""

from django.utils import timezone

from fantaApp.models import Championship, Weekend
from fantaApp.services.rules import ENROLLMENT_CLOSES_BEFORE


def _first_weekend(year):
    return Weekend.objects.filter(season=year).order_by("round_number").first()


def enrollment_deadline(year):
    """Last moment to join a championship of `year`, or None if unknown."""
    weekend = _first_weekend(year)
    if weekend is None:
        return None
    # On a sprint weekend the first qualifying is the sprint one.
    starts = [d for d in (weekend.sprint_qualifying_start, weekend.qualifying_start) if d]
    return min(starts) - ENROLLMENT_CLOSES_BEFORE if starts else None


def approval_deadline(year):
    """Last moment for a manager to approve a join request, or None if unknown."""
    weekend = _first_weekend(year)
    return weekend.fp1_start if weekend else None


def _before(deadline):
    return deadline is None or timezone.now() < deadline


def enrollment_open(championship):
    return championship.active and _before(enrollment_deadline(championship.year))


def approval_open(championship):
    return championship.active and _before(approval_deadline(championship.year))


def open_championships():
    """Championships that still accept players, for the search page (#72)."""
    championships = Championship.objects.filter(active=True)
    open_years = [
        year
        for year in championships.values_list("year", flat=True).distinct()
        if _before(enrollment_deadline(year))
    ]
    return championships.filter(year__in=open_years)
