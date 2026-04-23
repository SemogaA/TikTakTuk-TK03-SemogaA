from django.urls import path
from . import views

urlpatterns = [
    path('register/',           views.register_select_role, name='register'),
    path('register/customer/',  views.register_customer,    name='register_customer'),
    path('register/organizer/', views.register_organizer,   name='register_organizer'),
    path('register/admin/',     views.register_admin,       name='register_admin'),
]