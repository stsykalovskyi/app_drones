from functools import wraps

import bleach
import markdown
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoryForm, CommentForm, PageForm
from .models import Category, Page

GROUP_NAME = "майстер"
COMMANDER_GROUP = "командир майстерні"

ALLOWED_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "em", "del", "code", "pre",
    "ul", "ol", "li",
    "blockquote",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
]
ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
    "th": ["align"],
    "td": ["align"],
}


def render_markdown(text):
    """Convert Markdown to sanitised HTML."""
    html = markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "nl2br"],
    )
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)


def _is_editor(user):
    return user.is_superuser or user.groups.filter(
        name__in=[GROUP_NAME, COMMANDER_GROUP]
    ).exists()


def editor_required(view_func):
    """Allow access only to superusers, 'майстер' or 'командир майстерні'."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if _is_editor(request.user):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped


@login_required
def page_list(request):
    pages = Page.objects.select_related("category", "author", "author__profile")

    cat_slug = request.GET.get("cat")
    if cat_slug:
        pages = pages.filter(category__slug=cat_slug)

    query = request.GET.get("q", "").strip()
    if query:
        pages = pages.filter(Q(title__icontains=query) | Q(body__icontains=query))

    categories = Category.objects.all()

    return render(request, "documentation/page_list.html", {
        "title": "Документація",
        "pages": pages,
        "categories": categories,
        "current_cat": cat_slug,
        "query": query,
        "can_edit": _is_editor(request.user),
    })


@login_required
def page_detail(request, slug):
    page = get_object_or_404(
        Page.objects.select_related("category", "author", "author__profile"),
        slug=slug,
    )
    comments = page.comments.select_related("author", "author__profile")
    comment_form = CommentForm()

    return render(request, "documentation/page_detail.html", {
        "title": page.title,
        "page": page,
        "body_html": render_markdown(page.body),
        "comments": comments,
        "comment_form": comment_form,
        "can_edit": _is_editor(request.user),
    })


@editor_required
def page_create(request):
    if request.method == "POST":
        form = PageForm(request.POST)
        if form.is_valid():
            page = form.save(commit=False)
            page.author = request.user
            page.save()
            messages.success(request, "Сторінку створено.")
            return redirect("documentation:page_detail", slug=page.slug)
    else:
        form = PageForm()

    return render(request, "documentation/page_form.html", {
        "title": "Нова сторінка",
        "form": form,
    })


@editor_required
def page_edit(request, slug):
    page = get_object_or_404(Page, slug=slug)

    if request.method == "POST":
        form = PageForm(request.POST, instance=page)
        if form.is_valid():
            form.save()
            messages.success(request, "Сторінку оновлено.")
            return redirect("documentation:page_detail", slug=page.slug)
    else:
        form = PageForm(instance=page)

    return render(request, "documentation/page_form.html", {
        "title": "Редагувати сторінку",
        "form": form,
        "page": page,
    })


@editor_required
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Категорію створено.")
            return redirect("documentation:documentation_page")
    else:
        form = CategoryForm()

    return render(request, "documentation/category_form.html", {
        "title": "Нова категорія",
        "form": form,
    })


@login_required
def comment_create(request, slug):
    page = get_object_or_404(Page, slug=slug)

    if request.method != "POST":
        return redirect("documentation:page_detail", slug=slug)

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.page = page
        comment.author = request.user
        comment.save()
        messages.success(request, "Коментар додано.")

    return redirect("documentation:page_detail", slug=slug)
