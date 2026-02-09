from django.urls import path
from . import views

app_name = 'equipment_accounting'

urlpatterns = [
    path('', views.equipment_accounting_view, name='equipment_accounting_page'),
]