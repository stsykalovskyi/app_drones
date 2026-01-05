from django.db.models import Q
from django.views.generic import DetailView, ListView

from .models import Article, Topic


class TopicContextMixin:
    """Adds commonly used topic data to the template context."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        topics = Topic.objects.order_by("name").values("name", "slug", "icon")
        context["topics"] = topics
        context["active_topic"] = getattr(self, "topic_obj", None)
        return context


class ArticleListView(TopicContextMixin, ListView):
    template_name = "wiki/article_list.html"
    context_object_name = "articles"
    paginate_by = 12
    topic_obj = None

    def get_queryset(self):
        queryset = Article.objects.select_related("topic").order_by("title")

        topic_slug = self.kwargs.get("topic_slug")
        if topic_slug:
            self.topic_obj = Topic.objects.filter(slug=topic_slug).first()
            if self.topic_obj:
                queryset = queryset.filter(topic=self.topic_obj)

        query = self.request.GET.get("q")
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(summary__icontains=query)
                | Q(body__icontains=query)
                | Q(tags__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        return context


class ArticleDetailView(TopicContextMixin, DetailView):
    template_name = "wiki/article_detail.html"
    context_object_name = "article"
    model = Article
    slug_field = "slug"
    slug_url_kwarg = "slug"
