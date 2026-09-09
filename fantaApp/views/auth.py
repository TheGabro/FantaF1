from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from ..forms import creations


def safe_next_url(request):
    """Destinazione richiesta con ?next=, se punta dentro al sito.

    Serve agli inviti: il link porta a una pagina protetta, quindi chi non è
    autenticato viene dirottato sul login e deve tornare all'invito, non alla
    dashboard. La validazione impedisce che un ?next= manomesso rimandi
    l'utente appena autenticato su un dominio esterno.
    """
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return None


def _with_next(url_name, next_url):
    """Rotta con il ?next= riagganciato, per non perderlo passando fra login e registrazione."""
    url = reverse(url_name)
    if next_url:
        url = f"{url}?{urlencode({'next': next_url})}"
    return url


@login_required
def logout(request):
    auth_logout(request)
    return redirect("home")


def register(request):
    next_url = safe_next_url(request)

    if request.method == "POST":
        form_register = creations.CustomUserRegistrationForm(request.POST)
        if form_register.is_valid():
            form_register.save()
            messages.success(request, "Account creato: accedi per iniziare.")
            # La registrazione non autentica: si passa dal login portandosi
            # dietro next, altrimenti chi arriva da un invito lo perde qui.
            return redirect(_with_next("login", next_url))
    else:
        form_register = creations.CustomUserRegistrationForm()

    return render(request, "fantaApp/register.html", {
        "form_register": form_register,
        "next": next_url,
    })


def login(request):
    next_url = safe_next_url(request)

    if request.method == "POST":
        form_login = creations.UsernameOrEmailAuthenticationForm(request.POST)
        if form_login.is_valid():
            user = form_login.get_user()
            auth_login(request, user)
            return redirect(next_url or "user_dashboard")
        # Credenziali errate: oltre al riquadro nel form si mostra un toast, cosi'
        # l'errore si nota anche senza rileggere la pagina.
        for error in form_login.non_field_errors():
            messages.error(request, error)
    else:
        form_login = creations.UsernameOrEmailAuthenticationForm()

    return render(request, "fantaApp/login.html", {
        "form_login": form_login,
        "next": next_url,
    })
