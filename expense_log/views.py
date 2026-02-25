from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render

from .models import Expense
from .forms import ExpenseForm

GROUP_NAME = "майстер"
COMMANDER_GROUP = "командир майстерні"


def master_required(view_func):
    """Allow access only to superusers or members of the 'майстер' group."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.is_superuser or request.user.groups.filter(
            name__in=[GROUP_NAME, COMMANDER_GROUP]
        ).exists():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped


@master_required
def expense_list(request):
    expenses = Expense.objects.select_related("category").filter(created_by=request.user)

    total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    monthly = (
        expenses.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("-month")
    )

    is_commander = request.user.is_superuser or request.user.groups.filter(
        name=COMMANDER_GROUP
    ).exists()

    ctx = {
        "expenses": expenses,
        "total": total,
        "monthly": monthly,
        "is_commander": is_commander,
    }

    if is_commander:
        all_expenses = Expense.objects.select_related("created_by", "category")
        ctx["global_total"] = (
            all_expenses.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
        )
        ctx["global_count"] = all_expenses.count()
        ctx["global_monthly"] = (
            all_expenses.annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("-month")
        )

        # Per-user breakdown for the unit tab.
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


@master_required
def expense_create(request):
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


@master_required
def expense_detail(request, pk):
    is_commander = request.user.is_superuser or request.user.groups.filter(
        name=COMMANDER_GROUP
    ).exists()
    if is_commander:
        expense = get_object_or_404(Expense.objects.select_related("category", "created_by"), pk=pk)
    else:
        expense = get_object_or_404(Expense.objects.select_related("category", "created_by"), pk=pk, created_by=request.user)

    return render(request, "expense_log/expense_detail.html", {
        "expense": expense,
        "is_commander": is_commander,
        "can_edit": expense.created_by == request.user or is_commander,
    })


@master_required
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk, created_by=request.user)

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
