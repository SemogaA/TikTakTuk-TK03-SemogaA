from django.urls import path
from .views import ticket_category_views

urlpatterns = [
    path('', ticket_category_views.list_view, name='category_list'),
    path('create/', ticket_category_views.create_view, name='category_create'),
    path('update/<uuid:category_id>/', ticket_category_views.update_view, name='category_update'),
    path('delete/<uuid:category_id>/', ticket_category_views.delete_view, name='category_delete'),
]