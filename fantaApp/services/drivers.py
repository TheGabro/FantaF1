from fantaApp.models import Driver, Team
from django.core.management.base import CommandError


def save_driver(*, season: int, data: dict, team: Team) -> Driver:
        short_name = data["short_name"] or data["drivers_api_id"][:3].upper()
        defaults = {
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "number": data["number"],
            "short_name": short_name,
            "season": season,
            "team": team,
        }

        driver = Driver.objects.filter(api_id=data["drivers_api_id"]).first()
        if driver:
            for field, value in defaults.items():
                setattr(driver, field, value)
            driver.save(update_fields=[*defaults.keys()])
            return driver

        fallback_driver = None
        if data["number"] is not None:
            fallback_driver = Driver.objects.filter(season=season, number=data["number"]).first()

        if fallback_driver is None:
            fallback_driver = Driver.objects.filter(
                season=season,
                first_name=data["first_name"],
                last_name=data["last_name"],
            ).first()

        if fallback_driver:
            old_api_id = fallback_driver.api_id
            for field, value in defaults.items():
                setattr(fallback_driver, field, value)
            fallback_driver.api_id = data["drivers_api_id"]
            fallback_driver.save(update_fields=["api_id", *defaults.keys()])
            self.stdout.write(
                self.style.WARNING(
                    f"Updated existing driver match for {fallback_driver.first_name} {fallback_driver.last_name}: "
                    f"api_id {old_api_id} -> {fallback_driver.api_id}"
                )
            )
            return fallback_driver

        return Driver.objects.get_or_create(api_id=data["drivers_api_id"], **defaults)
    
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
