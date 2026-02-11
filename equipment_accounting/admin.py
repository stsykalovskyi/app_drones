from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    ComponentCategory,
    ComponentType,
    Component,
    Drone,
    DroneCategory,
    DroneModel,
    DroneType,
    FlightLog,
    Frequency,
    MaintenanceRecord,
    Manufacturer,
)


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

@admin.register(Manufacturer)
class ManufacturerAdmin(ModelAdmin):
    list_display = ("name", "website", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(DroneModel)
class DroneModelAdmin(ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Frequency)
class FrequencyAdmin(ModelAdmin):
    """Registered for the autocomplete / popup add button.

    Not shown in the sidebar navigation.
    """
    list_display = ("value",)
    search_fields = ("value",)


# ---------------------------------------------------------------------------
# Drone hierarchy
# ---------------------------------------------------------------------------

@admin.register(DroneCategory)
class DroneCategoryAdmin(ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(DroneType)
class DroneTypeAdmin(ModelAdmin):
    list_display = (
        "name",
        "manufacturer",
        "model",
        "category",
        "has_thermal_camera",
        "is_night_capable",
        "has_optical_fiber",
        "has_guidance_system",
    )
    list_filter = (
        "category",
        "manufacturer",
        "has_thermal_camera",
        "is_night_capable",
        "has_optical_fiber",
        "has_guidance_system",
    )
    search_fields = (
        "manufacturer__name",
        "model__name",
    )
    autocomplete_fields = ("control_frequency", "video_frequency")


@admin.register(Drone)
class DroneAdmin(ModelAdmin):
    list_display = (
        "inventory_number",
        "drone_type",
        "serial_number",
        "status",
        "assigned_to",
        "current_location",
        "total_flights",
        "total_flight_hours",
    )
    list_filter = ("status", "drone_type__category")
    search_fields = ("inventory_number", "serial_number")
    raw_id_fields = ("assigned_to",)
    readonly_fields = ("total_flight_hours", "total_flights")


# ---------------------------------------------------------------------------
# Component hierarchy
# ---------------------------------------------------------------------------

@admin.register(ComponentCategory)
class ComponentCategoryAdmin(ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(ComponentType)
class ComponentTypeAdmin(ModelAdmin):
    list_display = ("name", "category", "manufacturer", "model")
    list_filter = ("category",)
    search_fields = ("name", "manufacturer", "model")
    filter_horizontal = ("compatible_drone_types",)


@admin.register(Component)
class ComponentAdmin(ModelAdmin):
    list_display = (
        "inventory_number",
        "component_type",
        "serial_number",
        "status",
        "assigned_to_drone",
        "current_location",
    )
    list_filter = ("status", "component_type__category")
    search_fields = ("inventory_number", "serial_number")
    raw_id_fields = ("assigned_to_drone",)


# ---------------------------------------------------------------------------
# Operational logs
# ---------------------------------------------------------------------------

@admin.register(FlightLog)
class FlightLogAdmin(ModelAdmin):
    list_display = (
        "drone",
        "pilot",
        "flight_date",
        "duration_minutes",
        "mission_type",
        "location",
    )
    list_filter = ("mission_type", "flight_date")
    search_fields = (
        "drone__inventory_number",
        "pilot__username",
        "location",
    )
    raw_id_fields = ("drone", "pilot")
    filter_horizontal = ("batteries_used",)


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(ModelAdmin):
    list_display = (
        "maintenance_type",
        "drone",
        "component",
        "date",
        "performed_by",
        "cost",
        "next_maintenance_date",
    )
    list_filter = ("maintenance_type", "date")
    search_fields = (
        "drone__inventory_number",
        "component__inventory_number",
        "description",
    )
    raw_id_fields = ("drone", "component", "performed_by")
