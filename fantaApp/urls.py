from django.urls import path

from .services import player_choices
from fantaApp.views import auth, dashboard, general, weekend

urlpatterns = [
    path("", general.home, name = "home"),
    path("auth/register", auth.register, name = 'register'),
    path('auth/login/', auth.login, name='login'),
    path('auth/logout/', auth.logout, name='logout'),
    path("dashboard/account/", dashboard.user_dashboard, name = 'user_dashboard'),
    path("championships/create/", dashboard.create_championship, name='create_championship'),
    path("dashboard/championships/<int:championship_id>/", dashboard.championship_dashboard, name='championship_dashboard'),
    path(
        "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/",
        weekend.weekend_detail,
        name="weekend_details",
    ),

    path(
        "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/qualifying/sprint/<int:event_id>/choice/",
        weekend.sprint_qualifying_choice,
        name="sprint_qualifying_choice",
    ),

    #TODO
    # 2. Qualifying regolare (1 pilota)
    # path(
    #     "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/"
    #     "qualifying/regular/<int:event_id>/choice/",
    #     weekend.regular_qualifying_choice,
    #     name="regular_qualifying_choice",
    # ),

    # # 3. Sprint-Race (2 piloti, no pupillo)
    # path(
    #     "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/"
    #     "race/sprint/<int:event_id>/choice/",
    #     weekend.sprint_race_choice,
    #     name="sprint_race_choice",
    # ),

    # # 4. Grand Prix domenica (2 piloti + pupillo)
    # path(
    #     "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/"
    #     "race/regular/<int:event_id>/choice/",
    #     weekend.grand_prix_choice,
    #     name="grand_prix_choice",
    # ),
]