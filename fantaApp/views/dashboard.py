from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from ..forms import ChampionshipForm, LeagueFormSet
from ..models import League, ChampionshipManager, ChampionshipPlayer, Championship, Weekend

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