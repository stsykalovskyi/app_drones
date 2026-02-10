from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
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


class ArticleListView(LoginRequiredMixin, TopicContextMixin, ListView):
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
        if self.request.user.is_superuser:
            context["managed_users"] = (
                User.objects.exclude(is_superuser=True)
                .order_by("-date_joined")
            )
        return context


@require_POST
@user_passes_test(lambda u: u.is_superuser)
def toggle_user_approved(request, user_id):
    user = User.objects.get(pk=user_id)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    return JsonResponse({"is_approved": user.is_active})


class ArticleDetailView(LoginRequiredMixin, TopicContextMixin, DetailView):
    template_name = "wiki/article_detail.html"
    context_object_name = "article"
    model = Article
    slug_field = "slug"
    slug_url_kwarg = "slug"
