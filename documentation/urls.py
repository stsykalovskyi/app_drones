from django.urls import path
from . import views

app_name = 'documentation'

urlpatterns = [
    path('', views.documentation_view, name='documentation_page'),
]