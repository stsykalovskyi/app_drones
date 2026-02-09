from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from .models import Article, Topic


class ArticleViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        self.topic = Topic.objects.create(
            name="Mission Planning",
            description="Checklists and reference workflows",
            icon="🗂️",
        )
        self.article = Article.objects.create(
            topic=self.topic,
            title="Pre-flight Planning Checklist",
            summary="Standardized workflow for LZ selection and crew assignments.",
            tags="planning,checklist",
            body="1. Review NOTAMs\n2. Confirm weather window\n3. Assign crew call signs",
            references="https://example.com/checklist",
        )

    def test_article_list_view(self):
        url = reverse("wiki:article_list")
        response = self.client.get(url)
        self.assertContains(response, "Pre-flight Planning Checklist")

    def test_topic_filter(self):
        other_topic = Topic.objects.create(name="Maintenance", icon="🛠️")
        Article.objects.create(
            topic=other_topic,
            title="Battery Storage Guide",
            body="Store at 50% SOC in fire-safe cases.",
        )
        url = reverse("wiki:topic_articles", args=[other_topic.slug])
        response = self.client.get(url)
        self.assertContains(response, "Battery Storage Guide")
        self.assertNotContains(response, "Pre-flight Planning Checklist")

    def test_article_detail(self):
        url = reverse("wiki:article_detail", args=[self.article.slug])
        response = self.client.get(url)
        self.assertContains(response, "Pre-flight Planning Checklist")
        self.assertContains(response, "Review NOTAMs")
