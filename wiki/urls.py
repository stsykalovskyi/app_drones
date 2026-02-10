from django.urls import path

from .views import ArticleDetailView, ArticleListView, toggle_user_approved

app_name = "wiki"

urlpatterns = [
    path("", ArticleListView.as_view(), name="article_list"),
    path("topics/<slug:topic_slug>/", ArticleListView.as_view(), name="topic_articles"),
    path("articles/<slug:slug>/", ArticleDetailView.as_view(), name="article_detail"),
    path("users/<int:user_id>/toggle-approved/", toggle_user_approved, name="toggle_user_approved"),
]
