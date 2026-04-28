from django.urls import path
from tiktaktuk.views import ticket_views

urlpatterns = [
    path('my-tickets/', ticket_views.my_tickets, name='my_tickets'),
    path('create/', ticket_views.create_ticket, name='create_ticket'),
    path('update/<str:ticket_id>/', ticket_views.update_ticket, name='update_ticket'),
    path('delete/<str:ticket_id>/', ticket_views.delete_ticket, name='delete_ticket'),
]