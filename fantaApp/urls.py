from django.urls import path
from django.views.generic import RedirectView

from fantaApp.views import auth, dashboard, invites, weekend
from fantaApp.views.account import overview as account_overview
from fantaApp.views.game import landing as game_landing
from fantaApp.views.site import home, standings_drivers

urlpatterns = [
    path("", home.home, name="home"),
    path(
        "standings/drivers/",
        standings_drivers.standings_drivers,
        name="f1_drivers_standings",
    ),
    path("game/", game_landing.landing, name="game"),
    path("auth/register/", auth.register, name="register"),
    path("auth/login/", auth.login, name="login"),
    path("auth/logout/", auth.logout, name="logout"),
    path("account/", account_overview.overview, name="account"),
    path("championships/", dashboard.user_dashboard, name="user_dashboard"),
    path(
        "championships/create/",
        dashboard.create_championship,
        name="create_championship",
    ),
    path(
        "championships/<int:championship_id>/join/",
        invites.join_championship,
        name="join_championship",
    ),
    # Invito: il token va in fondo al percorso perché è quello che si incolla in chat.
    path("championships/invite/", invites.invite_redeem, name="invite_redeem"),
    path(
        "championships/invite/<str:token>/", invites.invite_accept, name="invite_accept"
    ),
    # Sezione Gioca: la radice del campionato e' il prossimo weekend da giocare.
    # Il nome 'championship_dashboard' resta: e' il bersaglio dei link dalla
    # dashboard utente, dagli inviti e dal banner.
    path(
        "championships/<int:championship_id>/",
        dashboard.championship_next_weekend,
        name="championship_dashboard",
    ),
    path(
        "championships/<int:championship_id>/my-choices/",
        dashboard.championship_my_choices,
        name="championship_my_choices",
    ),
    path(
        "championships/<int:championship_id>/calendar/",
        dashboard.championship_calendar,
        name="championship_calendar",
    ),
    # Sezione Classifiche: lega, generale e i due minigiochi.
    path(
        "championships/<int:championship_id>/standings/league/",
        dashboard.championship_league_standings,
        name="championship_league_standings",
    ),
    path(
        "championships/<int:championship_id>/standings/general/",
        dashboard.championship_general_standings,
        name="championship_general_standings",
    ),
    path(
        "championships/<int:championship_id>/standings/qualifying/",
        dashboard.championship_qualifying_standings,
        name="championship_qualifying_standings",
    ),
    path(
        "championships/<int:championship_id>/standings/sprint/",
        dashboard.championship_sprint_standings,
        name="championship_sprint_standings",
    ),
    path(
        "championships/<int:championship_id>/info/",
        dashboard.championship_info,
        name="championship_info",
    ),
    path(
        "championships/<int:championship_id>/weekends/<int:weekend_id>/",
        weekend.weekend_detail,
        name="weekend_details",
    ),
    # 1. Qualifying sprint (3 piloti)
    path(
        "championships/<int:championship_id>/weekends/<int:weekend_id>/qualifying/sprint/<int:event_id>/choice/",
        weekend.sprint_qualifying_choice,
        name="sprint_race_qualifying_choice",
    ),
    # 2.a. Qualifying weekend regular (1 pilota)
    path(
        "championships/<int:championship_id>/weekends/<int:weekend_id>/"
        "qualifying/race/<int:event_id>/choice/",
        weekend.race_qualifying_choice,
        name="race_qualifying_choice",
    ),
    # 2.b. Qualifying weekend sprint (slot driver / old format)
    path(
        "championships/<int:championship_id>/weekends/<int:weekend_id>/"
        "qualifying/old_format/<int:event_id>/choice/",
        weekend.race_qualifying_choice,
        name="race_qualifying_multi_choice",
    ),
    # 4. Sprint-Race (2 piloti, no pupillo)
    path(
        "championships/<int:championship_id>/weekends/<int:weekend_id>/"
        "race/sprint/<int:event_id>/choice/",
        weekend.sprint_race_choice,
        name="sprint_race_choice",
    ),
    # 5. Grand Prix domenica (2 piloti + pupillo)
    path(
        "championships/<int:championship_id>/weekends/<int:weekend_id>/"
        "race/regular/<int:event_id>/choice/",
        weekend.regular_race_choice,
        name="regular_race_choice",
    ),
    # 6a. Weekend sprint results
    path(
        "championships/<int:championship_id>/weekends/<int:weekend_id>/"
        "race/sprint/<int:event_id>/results/",
        weekend.sprint_race_results,
        name="sprint_race_results",
    ),
    # 6b. Weekend regular results
    path(
        "championships/<int:championship_id>/weekends/<int:weekend_id>/"
        "race/regular/<int:event_id>/results/",
        weekend.regular_race_results,
        name="regular_race_results",
    ),
    # Indirizzi vecchi (prima di #89) che possono stare nei segnalibri o nelle chat:
    # portano alla pagina nuova invece di dare 404.
    path(
        "dashboard/account/",
        RedirectView.as_view(pattern_name="user_dashboard", permanent=True),
        name="legacy_user_dashboard",
    ),
    path(
        "dashboard/championships/<int:championship_id>/",
        RedirectView.as_view(pattern_name="championship_dashboard", permanent=True),
        name="legacy_championship_dashboard",
    ),
    path(
        "campionati/invito/<str:token>/",
        RedirectView.as_view(pattern_name="invite_accept", permanent=True),
        name="legacy_invite_accept",
    ),
]
