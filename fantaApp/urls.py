from django.urls import path
from . import views
from .views import auth, dashboard, general, weekend

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
    #TODO
    # path(
    #     "dashboard/championships/<int:championship_id>/weekend/<int:weekend_id>/event/<str:event_type>/<int:event_id>/choice/",
    #     views.choose_drivers_for_event,
    #     name="event_driver_choice",
    # ),
]