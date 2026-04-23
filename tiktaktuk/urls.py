from django.urls import path, include
from .views import auth_views

urlpatterns = [
    # auth & dashboard langsung diurus auth_views
    path('login/', auth_views.login_view, name='login'),
    path('register/', auth_views.register_view, name='register'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('', auth_views.home_view, name='home'),
    path('dashboard/', auth_views.dashboard_view, name='dashboard'),

    # modul spesifik di-include dari file urls pecahan
    path('venue/', include('tiktaktuk.urls_venue')),
    path('artist/', include('tiktaktuk.urls_artist')),
]
