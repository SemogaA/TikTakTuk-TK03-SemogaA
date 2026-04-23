from django.urls import path
from . import views

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('orders/customer/',  views.order_list_customer,  name='order_list_customer'),
    path('orders/organizer/', views.order_list_organizer, name='order_list_organizer'),
    path('orders/admin/',     views.order_list_admin,     name='order_list_admin'),
]