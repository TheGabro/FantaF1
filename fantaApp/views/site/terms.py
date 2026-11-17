from datetime import date

from django.shortcuts import render

from .privacy import CONTACT_EMAIL

# Da aggiornare a ogni modifica del testo (in cima alla pagina).
LAST_UPDATED = date(2026, 11, 17)


def terms(request):
    """Termini e condizioni d'uso (#109), aperti a tutti senza login. Il testo
    segue la bozza approvata da Davide il 17/11/2026, che sostituisce quella
    del 2023 (niente quote né premi: il sito non gestisce denaro)."""
    return render(
        request,
        "fantaApp/site/terms.html",
        {"contact_email": CONTACT_EMAIL, "last_updated": LAST_UPDATED},
    )
