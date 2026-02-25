from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Category, Expense


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Expense)
class ExpenseAdmin(ModelAdmin):
    list_display = ("date", "amount_display", "description", "created_by", "has_receipt")
    list_filter = ("date", "created_by")
    search_fields = ("description", "notes")
    readonly_fields = ("date",)
    exclude = ("created_by",)
    date_hierarchy = "date"

    def amount_display(self, obj):
        return f"{obj.amount:,.2f} грн"
    amount_display.short_description = "Сума"
    amount_display.admin_order_field = "amount"

    def has_receipt(self, obj):
        return bool(obj.receipt)
    has_receipt.boolean = True
    has_receipt.short_description = "Квитанція"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
