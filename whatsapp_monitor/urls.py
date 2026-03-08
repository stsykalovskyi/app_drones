from django.urls import path
from . import views

app_name = 'whatsapp_monitor'

urlpatterns = [
    path('', views.strike_stats, name='stats'),
]
