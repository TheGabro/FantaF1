from django.urls import path

from fantaApp.views import auth, dashboard, general, invites, weekend

urlpatterns = [
    path("", general.home, name = "home"),
    path("auth/register", auth.register, name = 'register'),
    path('auth/login/', auth.login, name='login'),
    path('auth/logout/', auth.logout, name='logout'),
    path("dashboard/account/", dashboard.user_dashboard, name = 'user_dashboard'),
    path("championships/create/", dashboard.create_championship, name='create_championship'),
    path("championships/<int:championship_id>/iscriviti/", invites.join_championship, name='join_championship'),
    # Invito: il token va in fondo al percorso perché è quello che si incolla in chat.
    path("campionati/invito/", invites.invite_redeem, name='invite_redeem'),
    path("campionati/invito/<str:token>/", invites.invite_accept, name='invite_accept'),
    # Sezione Gioca: la radice del campionato e' il prossimo weekend da giocare.
    # Il nome 'championship_dashboard' resta: e' il bersaglio dei link dalla
    # dashboard utente, dagli inviti e dal banner.
    path("dashboard/championships/<int:championship_id>/", dashboard.championship_next_weekend, name='championship_dashboard'),
    path("dashboard/championships/<int:championship_id>/le-mie-scelte/", dashboard.championship_my_choices, name='championship_my_choices'),
    path("dashboard/championships/<int:championship_id>/calendario/", dashboard.championship_calendar, name='championship_calendar'),

    # Sezione Classifiche: lega, generale e i due minigiochi.
    path("dashboard/championships/<int:championship_id>/classifiche/lega/", dashboard.championship_league_standings, name='championship_league_standings'),
    path("dashboard/championships/<int:championship_id>/classifiche/generale/", dashboard.championship_general_standings, name='championship_general_standings'),
    path("dashboard/championships/<int:championship_id>/classifiche/qualifiche/", dashboard.championship_qualifying_standings, name='championship_qualifying_standings'),
    path("dashboard/championships/<int:championship_id>/classifiche/sprint/", dashboard.championship_sprint_standings, name='championship_sprint_standings'),

    path("dashboard/championships/<int:championship_id>/info/", dashboard.championship_info, name='championship_info'),
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