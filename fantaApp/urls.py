from django.urls import path

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

    # 1. Qualifying sprint (3 piloti)
    path(
        "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/qualifying/sprint/<int:event_id>/choice/",
        weekend.sprint_qualifying_choice,
        name="sprint_race_qualifying_choice",
    ),

    
    #2.a. Qualifying weekend regular (1 pilota)
    path(
        "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/"
        "qualifying/race/<int:event_id>/choice/",
        weekend.race_qualifying_choice,
        name="race_qualifying_choice",
    ),

    #2.b. Qualifying weekend sprint (slot driver / old format)
     path(
         "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/"
         "qualifying/old_format/<int:event_id>/choice/",
         weekend.race_qualifying_choice,
         name="race_qualifying_multi_choice",
    ),

    # 4. Sprint-Race (2 piloti, no pupillo)
    path(
        "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/"
        "race/sprint/<int:event_id>/choice/",
        weekend.sprint_race_choice,
        name="sprint_race_choice",
    ),

    # 5. Grand Prix domenica (2 piloti + pupillo)
    path(
        "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/"
        "race/regular/<int:event_id>/choice/",
        weekend.regular_race_choice,
        name="regular_race_choice",
    ),

    #6a. Weekend sprint results
    path(
        "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/"
        "race/sprint/<int:event_id>/results/",
        weekend.sprint_race_results,
        name="sprint_race_results",
    ),

    #6b. Weekend regular results
    path(
        "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/"
        "race/regular/<int:event_id>/results/",
        weekend.regular_race_results,
        name="regular_race_results",
    ),
]