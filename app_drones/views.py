from django.shortcuts import render

from equipment_accounting.models import Component, Drone
from expense_log.models import Expense
from wiki.models import Article


def home_view(request):
    return render(request, "home.html", {
        "drone_count": Drone.objects.count(),
        "component_count": Component.objects.count(),
        "expense_count": Expense.objects.filter(created_by=request.user).count(),
        "article_count": Article.objects.count(),
    })
