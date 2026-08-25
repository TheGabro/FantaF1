import logging

from fantaApp.models import Driver, Team
from django.core.management.base import CommandError

logger = logging.getLogger(__name__)


def find_driver(*, season: int, api_id=None, number=None,
                first_name=None, last_name=None) -> Driver | None:
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
            season=season, first_name=first_name, last_name=last_name,
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
            logger.warning("api_id riconciliato per %s %s: %s -> %s",
                           driver.first_name, driver.last_name, driver.api_id, api_id)
            driver.api_id = api_id

        for field, value in defaults.items():
            setattr(driver, field, value)
        driver.save(update_fields=["api_id", *defaults.keys()])

    
def resolve_fastf1_driver(*, season: int, data: dict) -> Driver:
    queryset = Driver.objects.filter(season=season)

    short_name = data.get("short_name")
    if short_name:
        driver = queryset.filter(short_name__iexact=short_name).first()
        if driver:
            return driver

    number = data.get("number")
    if number:
        driver = queryset.filter(number=number).first()
        if driver:
            return driver

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    if first_name and last_name:
        driver = queryset.filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name,
        ).first()
        if driver:
            return driver

    raise CommandError(
        "Impossibile fare match del pilota FastF1: "
        f"short_name={short_name}, number={number}, "
        f"first_name={first_name}, last_name={last_name}, "
        f"fastf1_driver_id={data.get('fastf1_driver_id')}, season={season}"
    )
