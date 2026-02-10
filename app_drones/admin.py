from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

admin.site.site_header = 'App Drones Admin'
admin.site.site_title = 'App Drones'
admin.site.index_title = 'Administration'

admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    list_editable = ('is_active',)
    ordering = ('-date_joined',)
    actions = ['approve_users', 'revoke_users']

    @admin.action(description='Approve selected users')
    def approve_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} user(s) approved.')

    @admin.action(description='Revoke approval for selected users')
    def revoke_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} user(s) revoked.')
