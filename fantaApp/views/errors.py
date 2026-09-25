from django.contrib import messages
from django.shortcuts import redirect


def csrf_failure(request, reason=""):
    """Sostituisce la pagina 403 di Django quando il token CSRF non è valido.

    Non è un errore di credenziali: succede quando il form viene inviato da una
    pagina rimasta aperta a lungo, ripescata dalla cache del browser, o con il
    cookie csrftoken sovrascritto da un altro progetto in ascolto su localhost
    (i cookie sono condivisi fra le porte dello stesso host).

    Si torna al form con un toast comprensibile: il nuovo GET rigenera un token
    valido, quindi al secondo tentativo l'invio funziona.
    """
    messages.error(
        request,
        "Sessione del modulo scaduta. La pagina è stata ricaricata: riprova a inviare i dati.",
    )
    return redirect(request.path or "home")
