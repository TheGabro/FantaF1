from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("", views.home, name = "home"),
    path("register", views.register, name = 'register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path("account/dashboard/", views.dashboard, name = 'dashboard'),
    path("championships/create/", views.create_championship, name='create_championship')
]