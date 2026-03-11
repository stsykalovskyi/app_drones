from django.urls import path

from . import views

app_name = 'pilots'

urlpatterns = [
    path('strikes/', views.strike_report_list, name='strike_report_list'),
    path('strikes/new/', views.strike_report_create, name='strike_report_create'),
    path('orders/', views.drone_order_list, name='drone_order_list'),
    path('orders/new/', views.drone_order_create, name='drone_order_create'),
    path('workshop/', views.workshop_orders, name='workshop_orders'),
    path('workshop/<int:pk>/update/', views.workshop_order_update, name='workshop_order_update'),
]
