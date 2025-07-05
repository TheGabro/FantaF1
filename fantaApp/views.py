from django.shortcuts import render, redirect
from django.http import HttpResponse
from .forms import CustomUserRegistrationForm, UsernameOrEmailAuthenticationForm, ChampionshipForm, LeagueFormSet
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required


def home(response):
    return render(response, "fantaApp/home.html", {})

@login_required
def dashboard(request):
    user = request.user
    context = {
        "user": user,
        "is_admin": user.user_type == "admin",
        "is_staff": user.user_type == "staff",
        "is_premium": user.user_type == "premium"
    }
    return render(request, "fantaApp/dashboard.html", context)

@login_required
def logout(request):
    auth_logout(request)
    return redirect("home")

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
        form_login = UsernameOrEmailAuthenticationForm(request.POST)
        if form_login.is_valid():
            user = form_login.get_user()
            auth_login(request, user)
            return redirect("dashboard")
    else:
        form_login = UsernameOrEmailAuthenticationForm()

    return render(request, "fantaApp/login.html", {
        "form_login": form_login
    })

@login_required
def create_championship(request):
    if request.method == 'POST':
        form = ChampionshipForm(request.POST)
        if form.is_valid():
            championship = form.save(commit=False)
            championship.created_by = request.user
            championship.save()  # ora ha la PK!

            formset = LeagueFormSet(request.POST, instance=championship)
            if formset.is_valid():
                formset.save()
                return redirect('dashboard')

            return redirect('dashboard')  # o altra pagina
    else:
        form = ChampionshipForm()
        formset = LeagueFormSet()

    return render(request, 'fantaApp/create_championship.html', {
        'form': form,
        'formset': formset
    })

