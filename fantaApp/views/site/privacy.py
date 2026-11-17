from datetime import date

from django.shortcuts import render

# Casella per privacy e contatti, decisa il 17/11/2026 (#107): più avanti una
# sul dominio del sito.
CONTACT_EMAIL = "fantaf1.vpv@gmail.com"

# Da aggiornare a ogni modifica del testo (in cima alla pagina).
LAST_UPDATED = date(2026, 11, 17)


def privacy(request):
    """Informativa privacy (#107), aperta a tutti senza login. Il testo segue
    la bozza approvata da Davide il 17/11/2026; le parti ancora in sospeso
    (garanzie dei fornitori, durata dei log, classifiche dopo la cancellazione,
    #106 e #318) sono scritte in modo prudente e si precisano entro il 1/3/2027."""
    return render(
        request,
        "fantaApp/site/privacy.html",
        {"contact_email": CONTACT_EMAIL, "last_updated": LAST_UPDATED},
    )
