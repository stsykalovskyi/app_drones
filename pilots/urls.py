from django.urls import path

from . import views

app_name = 'pilots'

urlpatterns = [
    path('strikes/', views.strike_report_list, name='strike_report_list'),
    path('strikes/new/', views.strike_report_create, name='strike_report_create'),
    path('strikes/<int:pk>/delete/', views.strike_report_delete, name='strike_report_delete'),
    path('strikes/<int:pk>/video/', views.strike_video, name='strike_video'),
    path('orders/', views.drone_order_list, name='drone_order_list'),
    path('orders/new/', views.drone_order_create, name='drone_order_create'),
    path('orders/review/', views.order_review, name='order_review'),
    path('workshop/', views.workshop_orders, name='workshop_orders'),
    path('workshop/archive/', views.workshop_orders_archive, name='workshop_orders_archive'),
    path('workshop/<int:pk>/update/', views.workshop_order_update, name='workshop_order_update'),
]
