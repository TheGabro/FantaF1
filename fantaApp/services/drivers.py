import logging

from fantaApp.models import Driver, Team
from django.core.management.base import CommandError

logger = logging.getLogger(__name__)


class TeamNotFound(LookupError):
    pass


def find_driver(
    *, season: int, api_id=None, number=None, first_name=None, last_name=None
) -> Driver | None:
    """Cerca un pilota nel DB, dalla chiave più forte alla più debole."""
    if api_id:
        driver = Driver.objects.filter(api_id=api_id).first()
        if driver:
            return driver

    if number is not None:
        driver = Driver.objects.filter(season=season, number=number).first()
        if driver:
            return driver

    if first_name and last_name:
        driver = Driver.objects.filter(
            season=season,
            first_name=first_name,
            last_name=last_name,
        ).first()
        if driver:
            return driver

    return None


def save_driver(*, season: int, data: dict, team: Team) -> None:
    api_id = data["drivers_api_id"]
    defaults = {
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "number": data["number"],
        "short_name": data["short_name"] or api_id[:3].upper(),
        "season": season,
        "team": team,
    }

    driver = find_driver(
        season=season,
        api_id=api_id,
        number=data["number"],
        first_name=data["first_name"],
        last_name=data["last_name"],
    )

    if driver is None:
        Driver.objects.create(api_id=api_id, **defaults)
    else:
        if driver.api_id != api_id:
            logger.warning(
                "api_id riconciliato per %s %s: %s -> %s",
                driver.first_name,
                driver.last_name,
                driver.api_id,
                api_id,
            )
            driver.api_id = api_id

        for field, value in defaults.items():
            setattr(driver, field, value)
        driver.save(update_fields=["api_id", *defaults.keys()])


def save_drivers(*, season: int, payload: list[dict]) -> list[Driver]:
    teams_by_api_id = Team.objects.in_bulk(field_name="api_id")
    saved = []
    for data in payload:
        team = teams_by_api_id.get(data["team"])
        if team is None:
            raise TeamNotFound(
                f"Team '{data['team']}' non presente a DB: importa prima i team."
            )
        saved.append(save_driver(season=season, data=data, team=team))
    return saved


def get_driver_by_number(*, season: int, number: int) -> Driver:
    """OpenF1 identifies drivers by race number only."""
    driver = find_driver(season=season, number=number)
    if driver is None:
        raise CommandError(f"Driver #{number} not found for season {season}")
    return driver
