from django.urls import path
from .views import venue_views

urlpatterns = [
    path('', venue_views.list_view, name='venue_list'),
    path('create/', venue_views.create_view, name='venue_create'),
    path('update/<uuid:venue_id>/', venue_views.update_view, name='venue_update'),
    path('delete/<uuid:venue_id>/', venue_views.delete_view, name='venue_delete'),
    
]
