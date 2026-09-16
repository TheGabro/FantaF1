import logging

from fantaApp.models import Driver, Weekend, WeekendParticipant

logger = logging.getLogger(__name__)

def sync_weekend_participants(*, season: int) -> int:
    """Garantisce un WeekendParticipant per ogni weekend della stagione.
    Se la gara e' gia' stata disputata, usa i piloti che hanno effettivamente
    corso (RaceResult) come fonte di verita' - altrimenti il roster stagionale
    (best-guess pre-evento, correggibile a mano via admin se arriva una sostituzione)."""
    season_drivers = Driver.objects.filter(season=season, active=True)
    created_count = 0

    for weekend in Weekend.objects.filter(season=season):
        race = weekend.races.filter(type="regular").first()
        results_exist = race is not None and race.entries.exists()

        if results_exist:
            for result in race.entries.select_related("driver__team"):
                _, created = WeekendParticipant.objects.update_or_create(
                    weekend=weekend,
                    driver=result.driver,
                    defaults={"team": result.driver.team},
                )
                created_count += 1 if created else 0
        else:
            for driver in season_drivers:
                if driver.number is None:
                    logger.warning(
                        f"Driver {driver} has no number assigned, skipping for weekend {weekend}"
                    )
                    continue
                _, created = WeekendParticipant.objects.get_or_create(
                    weekend=weekend,
                    driver=driver,
                    defaults={"team": driver.team},
                )
                created_count += 1 if created else 0

    return created_count

