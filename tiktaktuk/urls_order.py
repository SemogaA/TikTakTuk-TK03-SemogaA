# tiktaktuk/urls_order.py
from django.urls import path
from .views import order_views

urlpatterns = [
    # C - Order 
    path('<uuid:event_id>/checkout/', order_views.checkout_view,     name='checkout'),
    path('<uuid:event_id>/buy/',      order_views.create_order_view,  name='create_order'),
    path('promo/validate/',           order_views.validate_promo_ajax, name='validate_promo'),

    # R - Order
    path('',                          order_views.order_list_view,    name='order_list'),

    # UD - Order (admin only)
    path('<uuid:order_id>/update/',   order_views.update_order_view,  name='update_order'),
    path('<uuid:order_id>/delete/',   order_views.delete_order_view,  name='delete_order'),
]