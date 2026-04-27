from django.urls import path
from .views import promotion_views

urlpatterns = [
    path('', promotion_views.promotion_list_view, name='promotion_list'),
    path('update/<uuid:promotion_id>/', promotion_views.update_promotion_view, name='update_promotion'),
    path('delete/<uuid:promotion_id>/', promotion_views.delete_promotion_view, name='delete_promotion'),
]