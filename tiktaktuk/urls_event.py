from django.urls import path
from .views import event_views

urlpatterns = [
    path('', event_views.list_view, name='event_list'),
    path('create/', event_views.create_view, name='event_create'),
    path('update/<uuid:event_id>/', event_views.update_view, name='event_update'),
]
