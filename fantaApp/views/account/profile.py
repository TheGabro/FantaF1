from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from fantaApp.forms.account import PersonalDataForm


@login_required
def profile(request):
    """Account → Dati personali: username, nome e cognome (#97)."""
    if request.method == "POST":
        form = PersonalDataForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Dati personali salvati.")
            return redirect("account_profile")
    else:
        form = PersonalDataForm(instance=request.user)

    return render(
        request,
        "fantaApp/account/profile.html",
        {"account_page": "profile", "form": form},
    )
