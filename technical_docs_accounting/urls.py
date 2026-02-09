from django.urls import path
from . import views

app_name = 'technical_docs_accounting'

urlpatterns = [
    path('', views.technical_docs_accounting_view, name='technical_docs_accounting_page'),
]