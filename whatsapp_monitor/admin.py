from django.contrib import admin
from .models import StrikeReport


@admin.register(StrikeReport)
class StrikeReportAdmin(admin.ModelAdmin):
    list_display = (
        'received_at', 'sender_name', 'pozyvnyi', 'target',
        'result', 'parsed_ok', 'group_name',
    )
    list_filter = ('result', 'parsed_ok', 'group_name')
    search_fields = ('pozyvnyi', 'target', 'sender_name', 'raw_text')
    readonly_fields = ('whatsapp_msg_id', 'raw_text', 'created_at')
    date_hierarchy = 'received_at'
    ordering = ('-received_at',)
