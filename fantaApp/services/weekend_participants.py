import logging

from fantaApp.models import Driver, Weekend, WeekendParticipant, Team

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


def set_seat(
    *,
    season: int,
    from_round: int,
    driver: Driver,
    team: Team,
    replaces: Driver | None = None,
) -> list[str]:
    """Assegna a `driver` il sedile in `team` per tutti i weekend della stagione
    dal round `from_round` in poi (anche quelli gia' disputati).
    Se `replaces` e' indicato, quel pilota viene tolto dagli stessi weekend.

    Restituisce l'elenco delle modifiche, da stampare nel comando (utile col --dry-run).
    """

    if replaces is not None and replaces.pk == driver.pk:
        raise ValueError("Driver cannot substitute himself")

    weekends = Weekend.objects.filter(
        season=season, round_number__gte=from_round
    ).order_by("round_number")
    if not weekends.exists():
        raise ValueError(
            f"No weekend in {season} from round {from_round}"
        )

    changes: list[str] = []

    for weekend in weekends:
        existing = WeekendParticipant.objects.filter(
            weekend=weekend, driver=driver
        ).first()
        WeekendParticipant.objects.update_or_create(
            weekend=weekend, driver=driver, defaults={"team": team}
        )

        label = f"R{weekend.round_number}: {driver.short_name}"
                
        if existing is not None:
            if existing.team_id != team.pk:
                changes.append(
                    f"{label} moved to {team.short_name.strip()}"
                )
        else:
            changes.append(
                f"{label} added in {team.short_name.strip()}"
            )

        if replaces:
            deleted, _ = WeekendParticipant.objects.filter(
                weekend=weekend, driver=replaces
            ).delete()

            if deleted:
                changes.append(f"R{weekend.round_number}: {replaces.short_name} removed")

    # TO-CHANGE after new version, team will no longer exists
    driver.team = team
    driver.active = True
    driver.save(update_fields=["team", "active"])

    if replaces is not None:
        replaces.active = False
        replaces.save(update_fields=["active"])

    return changes
