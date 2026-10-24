from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from fantaApp.forms.account import ChangePasswordForm
from fantaApp.forms.creations import password_rules


@login_required
def security(request):
    """Account → Sicurezza: cambio password, restando collegati (#98)."""
    if request.method == "POST":
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Senza questo il cambio password chiuderebbe la sessione in corso.
            update_session_auth_hash(request, user)
            messages.success(request, "Password cambiata.")
            return redirect("account_security")
    else:
        form = ChangePasswordForm(request.user)

    return render(
        request,
        "fantaApp/account/security.html",
        {"account_page": "security", "form": form, "password_rules": password_rules()},
    )
