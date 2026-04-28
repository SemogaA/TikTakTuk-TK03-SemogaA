from django.urls import path
from tiktaktuk.views import seat_views

urlpatterns = [
    path('', seat_views.seat_management_page, name='seat_management'),
    path('api/seats/', seat_views.api_create_seat, name='api_create_seat'),
    path('api/seats/<str:seat_id>/', seat_views.api_get_seat, name='api_get_seat'),
    path('api/seats/<str:seat_id>/update/', seat_views.api_update_seat, name='api_update_seat'),
    path('api/seats/<str:seat_id>/delete/', seat_views.api_delete_seat, name='api_delete_seat'),
]