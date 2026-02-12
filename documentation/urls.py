from django.urls import path

from . import views

app_name = "documentation"

urlpatterns = [
    path("", views.page_list, name="documentation_page"),
    path("create/", views.page_create, name="page_create"),
    path("category/create/", views.category_create, name="category_create"),
    path("<slug:slug>/", views.page_detail, name="page_detail"),
    path("<slug:slug>/edit/", views.page_edit, name="page_edit"),
    path("<slug:slug>/comment/", views.comment_create, name="comment_create"),
]
