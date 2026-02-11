from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render

from .models import Expense
from .forms import ExpenseForm

GROUP_NAME = "майстер"


def master_required(view_func):
    """Allow access only to superusers or members of the 'майстер' group."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.is_superuser or request.user.groups.filter(name=GROUP_NAME).exists():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped


@master_required
def expense_list(request):
    expenses = Expense.objects.filter(created_by=request.user)

    total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    monthly = (
        expenses.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("-month")
    )

    return render(request, "expense_log/expense_list.html", {
        "expenses": expenses,
        "total": total,
        "monthly": monthly,
    })


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
