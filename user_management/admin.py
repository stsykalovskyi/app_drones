from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from unfold.admin import ModelAdmin, StackedInline

from .models import Profile

admin.site.unregister(User)


class ProfileInline(StackedInline):
    model = Profile
    can_delete = False
    fields = ("avatar",)


@admin.register(User)
class UserAdmin(ModelAdmin, BaseUserAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    list_editable = ('is_active',)
    ordering = ('-date_joined',)
    inlines = [ProfileInline]
    actions = ['approve_users', 'revoke_users']

    @admin.action(description='Підтвердити обраних користувачів')
    def approve_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} користувач(ів) підтверджено.')

    @admin.action(description='Скасувати доступ обраним користувачам')
    def revoke_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} користувач(ів) деактивовано.')
