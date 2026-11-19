"""Join requests for private championships (#75).

A private championship is not joined directly: the user sends a request with
a player name, and a manager of that championship accepts it (choosing the
league) or rejects it. Accepting creates the ChampionshipPlayer.

ValidationError messages are shown to players and managers, so they stay in
Italian.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from fantaApp.models import (
    ChampionshipJoinRequest,
    ChampionshipManager,
    ChampionshipPlayer,
)
from fantaApp.services import enrollment


def _check_player_name_free(championship, player_name):
    if ChampionshipPlayer.objects.filter(
        championship=championship, player_name=player_name
    ).exists():
        raise ValidationError(
            "Questo nome giocatore è già stato usato in questo campionato."
        )


def _check_manager(join_request, user):
    if not ChampionshipManager.objects.filter(
        user=user, championship=join_request.championship
    ).exists():
        raise PermissionDenied("Only a manager of the championship can decide join requests.")


def request_join(*, user, championship, player_name) -> ChampionshipJoinRequest:
    """Opens a pending request to join a private championship."""
    if not championship.is_private:
        raise ValidationError("Questo campionato è pubblico: puoi iscriverti direttamente.")
    if not championship.active:
        raise ValidationError(f"«{championship.name}» è concluso: non accetta più iscrizioni.")
    if not enrollment.enrollment_open(championship):
        raise ValidationError(f"Le iscrizioni a «{championship.name}» sono chiuse: il campionato sta per iniziare.")
    if ChampionshipPlayer.objects.filter(user=user, championship=championship).exists():
        raise ValidationError(f"Sei già iscritto a «{championship.name}».")
    if ChampionshipJoinRequest.objects.filter(
        user=user, championship=championship, status=ChampionshipJoinRequest.Status.PENDING
    ).exists():
        raise ValidationError("Hai già una richiesta in attesa per questo campionato.")
    _check_player_name_free(championship, player_name)

    return ChampionshipJoinRequest.objects.create(
        user=user, championship=championship, player_name=player_name
    )


@transaction.atomic
def approve(join_request, *, by, league) -> ChampionshipPlayer:
    """Accepts a pending request and enrolls the player in the league chosen by the manager."""
    _check_manager(join_request, by)
    if league.championship_id != join_request.championship_id:
        raise ValidationError("La lega scelta non fa parte di questo campionato.")
    # Lock the row: two managers clicking "accept" together must not create
    # the player twice.
    join_request = ChampionshipJoinRequest.objects.select_for_update().get(pk=join_request.pk)
    if join_request.status != ChampionshipJoinRequest.Status.PENDING:
        raise ValidationError("Questa richiesta è già stata gestita.")

    championship = join_request.championship
    if not enrollment.approval_open(championship):
        raise ValidationError(f"«{championship.name}» è già iniziato: non si possono più accettare richieste.")
    # The checks of request_join can be stale: the name may have been taken,
    # or the user enrolled in another way, while the request was pending.
    if ChampionshipPlayer.objects.filter(
        user=join_request.user, championship=championship
    ).exists():
        raise ValidationError(f"{join_request.user.username} è già iscritto a «{championship.name}».")
    _check_player_name_free(championship, join_request.player_name)

    player = ChampionshipPlayer.objects.create(
        user=join_request.user,
        championship=championship,
        league=league,
        player_name=join_request.player_name,
    )
    join_request.status = ChampionshipJoinRequest.Status.ACCEPTED
    join_request.save(update_fields=["status"])
    return player


@transaction.atomic
def reject(join_request, *, by) -> None:
    """Rejects a pending request. The user can send a new one later."""
    _check_manager(join_request, by)
    join_request = ChampionshipJoinRequest.objects.select_for_update().get(pk=join_request.pk)
    if join_request.status != ChampionshipJoinRequest.Status.PENDING:
        raise ValidationError("Questa richiesta è già stata gestita.")

    join_request.status = ChampionshipJoinRequest.Status.REJECTED
    join_request.save(update_fields=["status"])
