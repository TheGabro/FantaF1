from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("", views.home, name = "home"),
    path("register", views.register, name = 'register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path("account/dashboard/", views.user_dashboard, name = 'user_dashboard'),
    path("championships/create/", views.create_championship, name='create_championship'),
    path("championships/<int:championship_id>", views.championship_dashboard, name='championship_dashboard')
]