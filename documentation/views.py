from functools import wraps

import bleach
import markdown
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CategoryForm, CommentForm, PageForm
from .gemini_service import ask_gemini
from .models import Category, KnowledgeDocument, Page, Question

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
    return user.has_perm('documentation.change_page')


def editor_required(view_func):
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


@require_POST
@login_required
def question_delete(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    question = get_object_or_404(Question, pk=pk)
    question.delete()
    return JsonResponse({'ok': True})


@login_required
def question_ask(request):
    import json
    recent_questions = Question.objects.filter(user=request.user).order_by('-created_at')[:20]
    history_json = json.dumps([
        {'q': item.question_text, 'a': item.answer_text, 'date': item.created_at.strftime('%d.%m.%Y %H:%M')}
        for item in recent_questions
    ], ensure_ascii=False)

    if request.method == 'POST':
        question_text = request.POST.get('question_text', '').strip()
        if not question_text:
            messages.error(request, 'Введіть питання.')
            return render(request, 'documentation/question_ask.html', {
                'title': 'Задати питання',
                'recent_questions': recent_questions,
            })

        answer_text = ask_gemini(question_text, is_superuser=request.user.is_superuser)
        question = Question.objects.create(
            user=request.user,
            question_text=question_text,
            answer_text=answer_text,
            is_answered=bool(answer_text),
        )
        recent_questions = Question.objects.filter(user=request.user).order_by('-created_at')[:20]
        history_json = json.dumps([
            {'q': item.question_text, 'a': item.answer_text, 'date': item.created_at.strftime('%d.%m.%Y %H:%M')}
            for item in recent_questions
        ], ensure_ascii=False)
        return render(request, 'documentation/question_ask.html', {
            'title': 'Задати питання',
            'answered': question,
            'answer_html': render_markdown(answer_text),
            'recent_questions': recent_questions,
            'history_json': history_json,
        })

    return render(request, 'documentation/question_ask.html', {
        'title': 'Задати питання',
        'recent_questions': recent_questions,
        'history_json': history_json,
    })


# ── Knowledge document management (superadmin only) ───────────────────────────

def _superadmin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped


def _process_document_bg(doc_id):
    """Extract text from document in background thread."""
    import logging
    import os
    from django.db import connection
    logger = logging.getLogger(__name__)
    try:
        connection.close()
        from documentation.models import KnowledgeDocument
        from documentation.gemini_service import _extract_pdf_text
        from pathlib import Path

        doc = KnowledgeDocument.objects.get(pk=doc_id)
        doc.status = KnowledgeDocument.STATUS_PROCESSING
        doc.error_message = ''
        doc.save(update_fields=['status', 'error_message'])

        file_path = Path(doc.file.path)
        suffix = file_path.suffix.lower()

        if suffix in ('.txt', '.md'):
            text = file_path.read_text(encoding='utf-8', errors='ignore').strip()
        elif suffix == '.pdf':
            text = _extract_pdf_text(file_path)
        else:
            text = ''

        doc.extracted_text = text
        doc.status = KnowledgeDocument.STATUS_READY if text else KnowledgeDocument.STATUS_ERROR
        doc.error_message = '' if text else 'Текст не вдалося витягти (порожній результат).'
        doc.save(update_fields=['extracted_text', 'status', 'error_message'])
        logger.info('KnowledgeDocument #%s processed: %d chars', doc_id, len(text))
    except Exception as e:
        logger.exception('KnowledgeDocument #%s processing failed: %s', doc_id, e)
        try:
            from documentation.models import KnowledgeDocument
            KnowledgeDocument.objects.filter(pk=doc_id).update(
                status=KnowledgeDocument.STATUS_ERROR,
                error_message=str(e),
            )
        except Exception:
            pass


@_superadmin_required
def knowledge_docs(request):
    docs = KnowledgeDocument.objects.all()
    return render(request, 'documentation/knowledge_docs.html', {
        'title': 'База знань — документи',
        'docs': docs,
    })


@_superadmin_required
def knowledge_doc_upload(request):
    if request.method != 'POST':
        return redirect('documentation:knowledge_docs')
    f = request.FILES.get('file')
    if not f:
        messages.error(request, 'Файл не вибрано.')
        return redirect('documentation:knowledge_docs')
    allowed = ('.pdf', '.txt', '.md')
    ext = f.name.lower().rsplit('.', 1)[-1]
    if f''.join(['.', ext]) not in allowed:
        messages.error(request, 'Дозволені формати: PDF, TXT, MD.')
        return redirect('documentation:knowledge_docs')
    title = request.POST.get('title', '').strip() or f.name
    doc = KnowledgeDocument.objects.create(
        title=title,
        file=f,
        file_size=f.size,
    )
    messages.success(request, f'Завантажено: {doc.title}')
    return redirect('documentation:knowledge_docs')


@require_POST
@_superadmin_required
def knowledge_doc_process(request, pk):
    doc = get_object_or_404(KnowledgeDocument, pk=pk)
    if doc.status == KnowledgeDocument.STATUS_PROCESSING:
        return JsonResponse({'error': 'Вже обробляється.'}, status=400)
    import threading
    threading.Thread(target=_process_document_bg, args=(doc.pk,), daemon=True).start()
    return JsonResponse({'ok': True, 'status': KnowledgeDocument.STATUS_PROCESSING})


@require_POST
@_superadmin_required
def knowledge_doc_toggle(request, pk):
    doc = get_object_or_404(KnowledgeDocument, pk=pk)
    doc.is_active = not doc.is_active
    doc.save(update_fields=['is_active'])
    return JsonResponse({'ok': True, 'is_active': doc.is_active})


@require_POST
@_superadmin_required
def knowledge_doc_delete(request, pk):
    doc = get_object_or_404(KnowledgeDocument, pk=pk)
    try:
        doc.file.delete(save=False)
    except Exception:
        pass
    doc.delete()
    return JsonResponse({'ok': True})


@_superadmin_required
def knowledge_doc_status(request, pk):
    doc = get_object_or_404(KnowledgeDocument, pk=pk)
    return JsonResponse({
        'status': doc.status,
        'status_display': doc.get_status_display(),
        'extracted_len': len(doc.extracted_text),
        'error_message': doc.error_message,
    })


@_superadmin_required
def knowledge_doc_text(request, pk):
    doc = get_object_or_404(KnowledgeDocument, pk=pk)
    return render(request, 'documentation/knowledge_doc_text.html', {
        'title': doc.title,
        'doc': doc,
    })
