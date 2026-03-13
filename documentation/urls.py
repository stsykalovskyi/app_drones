from django.urls import path

from . import views

app_name = "documentation"

urlpatterns = [
    path("", views.page_list, name="documentation_page"),
    path("ask/", views.question_ask, name="question_ask"),
    path("ask/<int:pk>/delete/", views.question_delete, name="question_delete"),
    path("docs/", views.knowledge_docs, name="knowledge_docs"),
    path("docs/upload/", views.knowledge_doc_upload, name="knowledge_doc_upload"),
    path("docs/<int:pk>/process/", views.knowledge_doc_process, name="knowledge_doc_process"),
    path("docs/<int:pk>/toggle/", views.knowledge_doc_toggle, name="knowledge_doc_toggle"),
    path("docs/<int:pk>/delete/", views.knowledge_doc_delete, name="knowledge_doc_delete"),
    path("docs/<int:pk>/status/", views.knowledge_doc_status, name="knowledge_doc_status"),
    path("docs/<int:pk>/text/", views.knowledge_doc_text, name="knowledge_doc_text"),
    path("create/", views.page_create, name="page_create"),
    path("category/create/", views.category_create, name="category_create"),
    path("<slug:slug>/", views.page_detail, name="page_detail"),
    path("<slug:slug>/edit/", views.page_edit, name="page_edit"),
    path("<slug:slug>/comment/", views.comment_create, name="comment_create"),
]
