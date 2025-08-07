from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from ..forms import creations

@login_required
def logout(request):
    auth_logout(request)
    return redirect("home")

def register(request):
    if request.method == "POST":
        form_register = creations.CustomUserRegistrationForm(request.POST)
        if form_register.is_valid():
            form_register.save()
            return redirect("login")  # oppure "home"
    else: form_register= creations.CustomUserRegistrationForm()

    return render(request, "fantaApp/register.html", {
    "form_register": form_register
})

def login(request):
    if request.method == "POST":
        form_login = creations.UsernameOrEmailAuthenticationForm(request.POST)
        if form_login.is_valid():
            user = form_login.get_user()
            auth_login(request, user)
            return redirect("user_dashboard")
    else:
        form_login = creations.UsernameOrEmailAuthenticationForm()

    return render(request, "fantaApp/login.html", {
        "form_login": form_login
    })
