from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render

from .models import Expense
from .forms import ExpenseForm

PERM_VIEW   = 'expense_log.view_expense'
PERM_ADD    = 'expense_log.add_expense'
PERM_CHANGE = 'expense_log.change_expense'
PERM_DELETE = 'expense_log.delete_expense'


@login_required
def expense_list(request):
    can_view = request.user.has_perm(PERM_VIEW)
    can_add  = request.user.has_perm(PERM_ADD)

    if not (can_view or can_add):
        raise PermissionDenied

    expenses = Expense.objects.select_related("category").filter(created_by=request.user)
    total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    monthly = (
        expenses.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("-month")
    )

    ctx = {
        "expenses": expenses,
        "total": total,
        "monthly": monthly,
        "can_view": can_view,
        "can_add": can_add,
        "can_change": request.user.has_perm(PERM_CHANGE),
        "can_delete": request.user.has_perm(PERM_DELETE),
    }

    if can_view:
        all_expenses = Expense.objects.select_related("created_by", "category")
        ctx["global_total"] = all_expenses.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
        ctx["global_count"] = all_expenses.count()
        ctx["global_monthly"] = (
            all_expenses.annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("-month")
        )
        users_with_expenses = (
            User.objects.filter(expenses__isnull=False)
            .select_related("profile")
            .distinct()
            .order_by("username")
        )
        per_user = []
        for u in users_with_expenses:
            user_qs = Expense.objects.select_related("category").filter(created_by=u)
            user_total = user_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
            per_user.append({
                "user": u,
                "total": user_total,
                "expenses": user_qs.order_by("-date", "-created_at"),
            })
        ctx["per_user"] = per_user
        ctx["all_expenses"] = all_expenses.order_by("-date", "-created_at")

    return render(request, "expense_log/expense_list.html", ctx)


@login_required
def expense_create(request):
    if not request.user.has_perm(PERM_ADD):
        raise PermissionDenied

    if request.method == "POST":
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.save()
            messages.success(request, "Витрату додано.")
            return redirect("expense_log:expense_list")
    else:
        form = ExpenseForm()

    return render(request, "expense_log/expense_form.html", {
        "form": form,
        "title": "Нова витрата",
    })


@login_required
def expense_detail(request, pk):
    can_view = request.user.has_perm(PERM_VIEW)
    if can_view:
        expense = get_object_or_404(Expense.objects.select_related("category", "created_by"), pk=pk)
    else:
        expense = get_object_or_404(Expense.objects.select_related("category", "created_by"), pk=pk, created_by=request.user)

    can_edit = expense.created_by == request.user or request.user.has_perm(PERM_CHANGE)

    return render(request, "expense_log/expense_detail.html", {
        "expense": expense,
        "can_view": can_view,
        "can_edit": can_edit,
    })


@login_required
def expense_edit(request, pk):
    can_change = request.user.has_perm(PERM_CHANGE)
    if can_change:
        expense = get_object_or_404(Expense, pk=pk)
    else:
        expense = get_object_or_404(Expense, pk=pk, created_by=request.user)

    if not (expense.created_by == request.user or can_change):
        raise PermissionDenied

    if request.method == "POST":
        form = ExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Витрату оновлено.")
            return redirect("expense_log:expense_list")
    else:
        form = ExpenseForm(instance=expense)

    return render(request, "expense_log/expense_form.html", {
        "form": form,
        "title": "Редагувати витрату",
        "expense": expense,
    })
