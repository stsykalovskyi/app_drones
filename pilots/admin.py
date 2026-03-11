from django.contrib import admin

from .models import DroneOrder, StrikeReport


@admin.register(StrikeReport)
class StrikeReportAdmin(admin.ModelAdmin):
    list_display = ('pilot', 'strike_date', 'crew', 'weapon_type', 'target_type', 'result_type', 'reported_at')
    list_filter = ('strike_date', 'pilot', 'weapon_type', 'result_type')
    search_fields = ('pilot__username', 'crew', 'notes')
    date_hierarchy = 'strike_date'


@admin.register(DroneOrder)
class DroneOrderAdmin(admin.ModelAdmin):
    list_display = ('pilot', 'drone_type_name', 'quantity', 'status', 'created_at', 'handled_by')
    list_filter = ('status', 'created_at')
    search_fields = ('pilot__username', 'notes')
    readonly_fields = ('created_at', 'updated_at', 'drone_type_name')
