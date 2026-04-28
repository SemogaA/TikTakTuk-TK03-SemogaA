from django.urls import path, include
from .views import auth_views

urlpatterns = [
    # auth & dashboard langsung diurus auth_views
    path('login/', auth_views.login_view, name='login'),
    path('register/', auth_views.register_view, name='register'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('', auth_views.home_view, name='home'),
    path('dashboard/', auth_views.dashboard_view, name='dashboard'),
    path('profile/', auth_views.profile_view, name='profile'),

    # modul spesifik di-include dari file urls pecahan
    path('venue/', include('tiktaktuk.urls_venue')),
    path('event/', include('tiktaktuk.urls_event')),
    path('artist/', include('tiktaktuk.urls_artist')),
    path('category/', include('tiktaktuk.urls_ticket_category')),
]
