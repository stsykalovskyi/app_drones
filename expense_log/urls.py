from django.urls import path

from . import views

app_name = "expense_log"

urlpatterns = [
    path("", views.expense_list, name="expense_list"),
    path("add/", views.expense_create, name="expense_create"),
    path("<int:pk>/", views.expense_detail, name="expense_detail"),
    path("<int:pk>/edit/", views.expense_edit, name="expense_edit"),
]
