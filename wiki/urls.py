from django.urls import path

from .views import ArticleDetailView, ArticleListView

app_name = "wiki"

urlpatterns = [
    path("", ArticleListView.as_view(), name="article_list"),
    path("topics/<slug:topic_slug>/", ArticleListView.as_view(), name="topic_articles"),
    path("articles/<slug:slug>/", ArticleDetailView.as_view(), name="article_detail"),
]
