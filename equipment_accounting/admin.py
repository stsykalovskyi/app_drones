from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from unfold.admin import ModelAdmin

from .models import (
    BatteryType,
    Component,
    DroneModel,
    DronePurpose,
    FPVDroneType,
    Frequency,
    Manufacturer,
    OpticalDroneType,
    OtherComponentType,
    PowerTemplate,
    SpoolType,
    UAVInstance,
    VideoTemplate,
)


# ============== ДОВІДНИКИ ==============

@admin.register(Manufacturer)
class ManufacturerAdmin(ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(DroneModel)
class DroneModelAdmin(ModelAdmin):
    list_display = ("name", "manufacturer", "created_at")
    list_filter = ("manufacturer",)
    search_fields = ("name", "manufacturer__name")


@admin.register(DronePurpose)
class DronePurposeAdmin(ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Frequency)
class FrequencyAdmin(ModelAdmin):
    list_display = ("value", "unit")
    list_filter = ("unit",)
    search_fields = ("value",)


# ============== ШАБЛОНИ СУМІСНОСТІ ==============

@admin.register(PowerTemplate)
class PowerTemplateAdmin(ModelAdmin):
    list_display = ("name", "connector", "configuration", "capacity")
    list_filter = ("connector", "configuration")
    search_fields = ("name",)


@admin.register(VideoTemplate)
class VideoTemplateAdmin(ModelAdmin):
    list_display = ("name", "is_analog", "max_distance")
    list_filter = ("is_analog",)
    search_fields = ("name",)


# ============== ТИПИ БПЛА ==============

@admin.register(FPVDroneType)
class FPVDroneTypeAdmin(ModelAdmin):
    list_display = ("model", "prop_size", "control_frequency", "video_frequency", "has_thermal", "is_unusable")
    list_filter = ("prop_size", "has_thermal", "is_unusable")
    search_fields = ("model__name", "model__manufacturer__name")


@admin.register(OpticalDroneType)
class OpticalDroneTypeAdmin(ModelAdmin):
    list_display = ("model", "prop_size", "control_frequency", "video_template", "has_thermal", "is_unusable")
    list_filter = ("prop_size", "has_thermal", "is_unusable")
    search_fields = ("model__name", "model__manufacturer__name")


# ============== КОМПЛЕКТУЮЧІ ==============

@admin.register(BatteryType)
class BatteryTypeAdmin(ModelAdmin):
    list_display = ("model", "power_template")
    search_fields = ("model",)


@admin.register(SpoolType)
class SpoolTypeAdmin(ModelAdmin):
    list_display = ("model", "video_template")
    search_fields = ("model",)


@admin.register(OtherComponentType)
class OtherComponentTypeAdmin(ModelAdmin):
    list_display = ("model", "category")
    list_filter = ("category",)
    search_fields = ("model",)


@admin.register(Component)
class ComponentAdmin(ModelAdmin):
    list_display = ("component_type", "status", "assigned_to_uav", "created_at")
    list_filter = ("status",)


# ============== ІНВЕНТАРНІ ЕКЗЕМПЛЯРИ ==============

@admin.register(UAVInstance)
class UAVInstanceAdmin(ModelAdmin):
    list_display = ("serial_number", "uav_type", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("serial_number",)
    raw_id_fields = ("created_by",)
