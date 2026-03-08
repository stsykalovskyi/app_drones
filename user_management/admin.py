from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import User, Group
from unfold.admin import ModelAdmin, StackedInline

from .models import Profile

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(ModelAdmin, BaseGroupAdmin):
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['permissions'].widget.attrs['size'] = 20
        return form


class ProfileInline(StackedInline):
    model = Profile
    can_delete = False
    fields = ("callsign", "phone_number", "telegram_chat_id", "avatar")


@admin.register(User)
class UserAdmin(ModelAdmin, BaseUserAdmin):
    list_display = ('username', 'email', 'get_phone_number', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    list_editable = ('is_active',)
    ordering = ('-date_joined',)
    inlines = [ProfileInline]

    @admin.display(description='Номер телефону', ordering='profile__phone_number')
    def get_phone_number(self, obj):
        return obj.profile.phone_number
    actions = ['approve_users', 'revoke_users']

    @admin.action(description='Підтвердити обраних користувачів')
    def approve_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} користувач(ів) підтверджено.')

    @admin.action(description='Скасувати доступ обраним користувачам')
    def revoke_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} користувач(ів) деактивовано.')
