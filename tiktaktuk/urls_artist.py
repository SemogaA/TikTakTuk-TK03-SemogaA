from django.urls import path
from .views import artist_views

urlpatterns = [
    path('', artist_views.list_view, name='artist_list'),
    path('create/', artist_views.create_view, name='artist_create'),
    path('update/<uuid:artist_id>/',
         artist_views.update_view, name='artist_update'),
    path('delete/<uuid:artist_id>/',
         artist_views.delete_view, name='artist_delete'),
]
