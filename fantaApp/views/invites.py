"""Iscrizione a un campionato e inviti tramite link firmato.

L'invito non è salvato da nessuna parte: è un token firmato da Django che
contiene l'id del campionato e la data di emissione. Vale quanto il link di un
gruppo WhatsApp — chiunque lo riceva può entrare e non è revocabile se non
lasciandolo scadere. Per inviti nominali, revocabili o monouso serve un modello
dedicato (proposta B3 in docs/plans/piano-inviti-leghe.md).
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..forms import creations
from ..models import Championship, ChampionshipPlayer

# Salt dedicato: un token di invito non deve essere spendibile altrove nel sito.
INVITE_SALT = "fantaApp.invito-campionato"
INVITE_MAX_AGE = timedelta(days=30)


def make_invite_token(championship):
    """Token firmato che identifica il campionato. Non è segreto, è solo non falsificabile."""
    return signing.dumps({"championship_id": championship.pk}, salt=INVITE_SALT)


def build_invite_url(request, championship):
    """URL assoluto dell'invito, pronto da incollare in chat."""
    return request.build_absolute_uri(
        reverse("invite_accept", args=[make_invite_token(championship)])
    )


def _championship_from_token(token):
    """Ritorna (campionato, messaggio_di_errore). Uno dei due è sempre None."""
    try:
        payload = signing.loads(token, salt=INVITE_SALT, max_age=INVITE_MAX_AGE)
    except signing.SignatureExpired:
        return None, "Questo invito è scaduto: chiedi all'organizzatore un link nuovo."
    except signing.BadSignature:
        return None, "Invito non valido: controlla di aver copiato il link per intero."

    championship = Championship.objects.filter(pk=payload.get("championship_id")).first()
    if championship is None:
        return None, "Il campionato di questo invito non esiste più."
    return championship, None


@login_required
def invite_accept(request, token):
    """Apre un link d'invito: valida il token e consegna alla pagina di iscrizione.

    Protetta da login: chi arriva senza account viene mandato al login con
    ?next= su questa stessa pagina e ci torna appena autenticato.
    """
    championship, error = _championship_from_token(token)
    if error:
        messages.error(request, error)
        return redirect("user_dashboard")

    return redirect("join_championship", championship_id=championship.pk)


@login_required
@require_POST
def invite_redeem(request):
    """Codice invito incollato a mano dalla dashboard.

    Accetta sia il token da solo sia il link intero: chi apre il sito dal
    segnalibro invece che dal messaggio incolla quello che ha sottomano.
    """
    raw = (request.POST.get("invite_code") or "").strip()
    # Da un URL completo interessa solo l'ultimo segmento di percorso.
    token = raw.split("?")[0].split("#")[0].rstrip("/").rsplit("/", 1)[-1]

    if not token:
        messages.error(request, "Inserisci il codice o il link che hai ricevuto.")
        return redirect("user_dashboard")

    championship, error = _championship_from_token(token)
    if error:
        messages.error(request, error)
        return redirect("user_dashboard")

    return redirect("join_championship", championship_id=championship.pk)


@login_required
def join_championship(request, championship_id):
    """Iscrizione a un campionato esistente: nome giocatore e lega."""
    championship = get_object_or_404(Championship, pk=championship_id)

    # Già iscritto: si accoglie con un messaggio invece di far scattare il
    # vincolo unique_together ('user', 'championship') con un errore di database.
    if ChampionshipPlayer.objects.filter(user=request.user, championship=championship).exists():
        messages.success(request, f"Sei già iscritto a «{championship.name}».")
        return redirect("championship_dashboard", championship_id=championship.pk)

    if not championship.active:
        messages.error(request, f"«{championship.name}» è concluso: non accetta più iscrizioni.")
        return redirect("user_dashboard")

    if request.method == "POST":
        form = creations.ChampionshipPlayerForm(request.POST, championship=championship)
        if form.is_valid():
            player = form.save(commit=False)
            player.user = request.user
            player.championship = championship
            player.save()
            messages.success(request, f"Sei dentro: benvenuto in «{championship.name}».")
            return redirect("championship_dashboard", championship_id=championship.pk)
    else:
        form = creations.ChampionshipPlayerForm(
            championship=championship,
            initial={"player_name": request.user.username},
        )

    return render(request, "fantaApp/join_championship.html", {
        "championship": championship,
        "form": form,
    })
