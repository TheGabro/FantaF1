from django.shortcuts import render, redirect
from django.http import HttpResponse
from .forms import CustomUserRegistrationForm, UsernameOrEmailAuthenticationForm, ChampionshipForm, LeagueFormSet
from .models import League, ChampionshipManager, ChampionshipPlayer, Championship, Weekend
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404


def home(response):
    return render(response, "fantaApp/home.html", {})

@login_required
def user_dashboard(request):
    user = request.user

    championship = ChampionshipPlayer.objects.filter(
        user=user
    ).select_related('championship', 'league').order_by('championship__active','-championship__year')

    context = {
        "user": user,
        "championship": championship,
        "is_admin": user.user_type == "admin",
        "is_staff": user.user_type == "staff",
        "is_premium": user.user_type == "premium"
    }
    return render(request, "fantaApp/user_dashboard.html", context)

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
            return redirect("user_dashboard")
    else:
        form_login = UsernameOrEmailAuthenticationForm()

    return render(request, "fantaApp/login.html", {
        "form_login": form_login
    })

@login_required
def create_championship(request):
    if request.method == 'POST':
        form = ChampionshipForm(request.POST)
        formset = LeagueFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            championship = form.save(commit=False)
            championship.created_by = request.user
            championship.save()  # ora ha la PK!

            leagues = formset.save(commit=False)
            for league in leagues:
                league.championship = championship
                league.save()
            # If the user did not specify any league, create a default one
            if not leagues:
                League.objects.create(
                    championship=championship,
                    name=f"Lega Unica"
                )
            
            ChampionshipManager.objects.get_or_create(
                user=request.user,
                championship=championship
            )


            return redirect('user_dashboard')
    else:
        form = ChampionshipForm()
        formset = LeagueFormSet()

    return render(request, 'fantaApp/create_championship.html', {
        'form': form,
        'formset': formset
    })

@login_required
def championship_dashboard(request, championship_id):
    championship = get_object_or_404(Championship, pk=championship_id)

    current_championship_player = ChampionshipPlayer.objects.filter(
        user=request.user, championship=championship).select_related('league').first()
    
    championship_participants = ChampionshipPlayer.objects.filter(
        championship=championship
    ).select_related('league') #carica in memoria anche la tabella per il quale league è chiave esterna

    user_managers = ChampionshipManager.objects.filter(
        championship=championship
    ).select_related('user') 

    managers = ChampionshipPlayer.objects.filter(
        championship=championship,
        user__in=[m.user for m in user_managers]
    ).select_related('league')
    
    weekends = Weekend.objects.filter(season=championship.year).order_by("round_number")



    context = {
        "championship": championship,
        "current_championship_player": current_championship_player,
        "championship_participants": championship_participants,
        "managers": managers,
        "weekends" : weekends
    }

    return render(request, "fantaApp/championship_dashboard.html", context)



def weekend_detail(request, championship_id, weekend_id):
    championship = get_object_or_404(Championship, pk=championship_id)
    weekend = get_object_or_404(Weekend, pk=weekend_id)

    events = []
    # Sprint-Qualifying
    sq = weekend.Qualifying.filter(type="sprint").first()
    if sq:
        events.append({"label": "Sprint Qualifying",
                       "event_type": "sprint-qualifying",
                       "event_id": sq.id})
    # Sprint Race
    sr = weekend.Race.filter(type="sprint").first()
    if sr:
        events.append({"label": "Sprint Race",
                       "event_type": "sprint",
                       "event_id": sr.id})
    # Qualifying (gara regolare)
    q = weekend.Qualifying.filter(type="regular").first()
    if q:
        events.append({"label": "Qualifying",
                       "event_type": "qualifying",
                       "event_id": q.id})
    # Race
    r = weekend.Race.filter(type="regular").first()
    if r:
        events.append({"label": "Grand Prix",
                       "event_type": "race",
                       "event_id": r.id})

    return render(
        request,
        "fantaApp/weekend_details.html",
        {
            "championship": championship,
            "weekend": weekend,
            "events": events,
        },
    )



