from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from fantaApp.views import dashboard


@login_required
def leave(request, championship_id):
    """Disiscrizione dal campionato (#160): pagina in GET, azione in POST.

    Cancellare il ChampionshipPlayer porta via a cascata scelte e risultati,
    e le classifiche si calcolano dagli iscritti: non serve altro. Un manager
    non può disiscriversi (può solo chiudere il campionato, #145): vede la
    pagina con il motivo, e una sua POST viene rifiutata. Il nome del
    campionato scritto dall'utente si ricontrolla qui, perché il controllo
    nel browser si può aggirare.
    """
    championship, player, context = dashboard._section_context(
        request, championship_id, "leave"
    )

    if player is None:
        messages.error(request, f"Non sei iscritto a «{championship.name}».")
        return redirect("championship_dashboard", championship_id=championship.id)

    if request.method == "POST":
        if context["is_manager"]:
            messages.error(
                request,
                "I manager non possono disiscriversi: possono solo chiudere il campionato.",
            )
            return redirect("championship_leave", championship_id=championship.id)

        typed_name = request.POST.get("championship_name", "").strip()
        if typed_name != championship.name.strip():
            messages.error(
                request,
                "Il nome non corrisponde a quello del campionato: la disiscrizione non è avvenuta.",
            )
            return redirect("championship_leave", championship_id=championship.id)

        player.delete()
        messages.success(request, f"Disiscrizione da «{championship.name}» completata.")
        return redirect("user_dashboard")

    return render(request, "fantaApp/championship_leave.html", context)
