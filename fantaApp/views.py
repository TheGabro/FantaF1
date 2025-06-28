from django.shortcuts import render, redirect
from django.http import HttpResponse
from .forms import CustomUserRegistrationForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login


def home(response):
    return render(response, "fantaApp/home.html", {})

def dashboard(response):
    return render(response, "fantaApp/dashboard.html", {
    })

def register(request):
    if request.method == "POST":
        form_register = CustomUserRegistrationForm(request.POST)
        if form_register.is_valid():
            form_register.save()
            return redirect("login")  # oppure "home"
    else: form_register= CustomUserRegistrationForm()

    return render(request, "fantaApp/register.html", {
    "form_register": form_register
})

def login(request):
    if request.method == "POST":
        form_login = AuthenticationForm(request, data=request.POST)
        if form_login.is_valid():
            user = form_login.get_user()
            auth_login(request, user)
            return redirect("dashboard")
    else:
        form_login = AuthenticationForm()

    return render(request, "fantaApp/login.html", {
        "form_login": form_login
    })
