from datetime import date
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    UAVInstanceForm, ComponentForm, PowerTemplateForm, VideoTemplateForm,
    FPVDroneTypeForm, OpticalDroneTypeForm,
)
from .models import (
    UAVInstance, Component, PowerTemplate, VideoTemplate,
    FPVDroneType, OpticalDroneType,
    BatteryType, SpoolType,
)

def _list_url(tab="drones"):
    return reverse("equipment_accounting:equipment_list") + f"?tab={tab}"


GROUP_NAME = "майстер"
COMMANDER_GROUP = "командир майстерні"


def master_required(view_func):
    """Allow access only to superusers or members of the master/commander groups."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.is_superuser or request.user.groups.filter(
            name__in=[GROUP_NAME, COMMANDER_GROUP]
        ).exists():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped


# ── Main list view ──────────────────────────────────────────────────

@master_required
def equipment_list(request):
    tab = request.GET.get("tab", "drones")

    # Drones with filtering (exclude soft-deleted)
    uavs = UAVInstance.objects.select_related("content_type", "created_by", "created_by__profile").prefetch_related(
        "components", "components__content_type"
    ).filter(status__in=UAVInstance.ACTIVE_STATUSES)

    status_filter = request.GET.get("status", "")
    category_filter = request.GET.get("category", "")
    type_filter = request.GET.get("type", "")
    kit_filter = request.GET.get("kit", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    search_q = request.GET.get("q", "")

    if status_filter:
        uavs = uavs.filter(status=status_filter)

    if category_filter:
        if category_filter == "fpv":
            ct = ContentType.objects.get_for_model(FPVDroneType)
        elif category_filter == "optical":
            ct = ContentType.objects.get_for_model(OpticalDroneType)
        else:
            ct = None
        if ct:
            uavs = uavs.filter(content_type=ct)

    if type_filter:
        try:
            ct_id, obj_id = type_filter.split("-")
            uavs = uavs.filter(content_type_id=int(ct_id), object_id=int(obj_id))
        except (ValueError, TypeError):
            pass

    if date_from:
        try:
            uavs = uavs.filter(created_at__date__gte=date.fromisoformat(date_from))
        except ValueError:
            pass

    if date_to:
        try:
            uavs = uavs.filter(created_at__date__lte=date.fromisoformat(date_to))
        except ValueError:
            pass

    if search_q:
        uavs = uavs.filter(Q(notes__icontains=search_q))

    # Kit filter requires Python-level evaluation per object
    if kit_filter in (UAVInstance.KIT_FULL, UAVInstance.KIT_PARTIAL, UAVInstance.KIT_NONE):
        filtered_ids = [u.pk for u in uavs if u.get_kit_status() == kit_filter]
        uavs = uavs.filter(pk__in=filtered_ids)

    paginator = Paginator(uavs.order_by("-created_at"), 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Build drone type choices for filter
    type_choices = []
    fpv_ct = ContentType.objects.get_for_model(FPVDroneType)
    for dt in FPVDroneType.objects.select_related("model", "model__manufacturer"):
        type_choices.append((f"{fpv_ct.pk}-{dt.pk}", f"[Радіо] {dt}"))
    opt_ct = ContentType.objects.get_for_model(OpticalDroneType)
    for dt in OpticalDroneType.objects.select_related("model", "model__manufacturer"):
        type_choices.append((f"{opt_ct.pk}-{dt.pk}", f"[Оптика] {dt}"))

    # Summary counts (exclude soft-deleted)
    all_uavs = UAVInstance.objects.filter(status__in=UAVInstance.ACTIVE_STATUSES)
    total_drones = all_uavs.count()
    status_counts = {}
    for code, label in UAVInstance.STATUS_CHOICES:
        if code == 'deleted':
            continue
        status_counts[code] = {"label": label, "count": all_uavs.filter(status=code).count()}

    # Components
    components = Component.objects.select_related("content_type", "assigned_to_uav").order_by("-created_at")

    # Drone types
    fpv_drone_types = FPVDroneType.objects.select_related(
        "model", "model__manufacturer", "purpose",
        "video_frequency", "power_template",
    ).prefetch_related("control_frequencies")
    optical_drone_types = OpticalDroneType.objects.select_related(
        "model", "model__manufacturer", "purpose",
        "video_template", "power_template",
    ).prefetch_related("control_frequencies")

    # Templates
    power_templates = PowerTemplate.objects.all()
    video_templates = VideoTemplate.objects.all()

    ctx = {
        "tab": tab,
        "page_obj": page_obj,
        "status_filter": status_filter,
        "category_filter": category_filter,
        "type_filter": type_filter,
        "kit_filter": kit_filter,
        "kit_choices": list(UAVInstance.KIT_LABELS.items()),
        "date_from": date_from,
        "date_to": date_to,
        "search_q": search_q,
        "type_choices": type_choices,
        "total_drones": total_drones,
        "status_counts": status_counts,
        "status_choices": [c for c in UAVInstance.STATUS_CHOICES if c[0] != 'deleted'],
        "components": components,
        "fpv_drone_types": fpv_drone_types,
        "optical_drone_types": optical_drone_types,
        "power_templates": power_templates,
        "video_templates": video_templates,
    }

    return render(request, "equipment_accounting/equipment_list.html", ctx)


# ── Bulk actions ────────────────────────────────────────────────────

@master_required
def uav_bulk_action(request):
    """Handle bulk status change or bulk delete for selected UAVs."""
    if request.method != "POST":
        return redirect("equipment_accounting:equipment_list")

    ids = request.POST.getlist("selected")
    action = request.POST.get("bulk_action", "")

    if not ids:
        messages.warning(request, "Нічого не обрано.")
        return redirect("equipment_accounting:equipment_list")

    qs = UAVInstance.objects.filter(pk__in=ids)
    count = qs.count()

    if action == "delete":
        qs.update(status='deleted')
        messages.success(request, f"Видалено {count} БПЛА.")
    elif action in dict(UAVInstance.STATUS_CHOICES):
        qs.update(status=action)
        label = dict(UAVInstance.STATUS_CHOICES)[action]
        messages.success(request, f"Статус {count} БПЛА змінено на \"{label}\".")
    else:
        messages.error(request, "Невідома дія.")

    return redirect("equipment_accounting:equipment_list")


# ── UAV CRUD ────────────────────────────────────────────────────────

def _create_kit_components(uav, drone_type_obj):
    """Create matching components (battery, spool) for a UAV based on its drone type."""
    # Battery for all drone types (matched by power_template)
    battery_type = BatteryType.objects.filter(
        power_template=drone_type_obj.power_template
    ).first()
    if battery_type:
        Component.objects.create(
            content_type=ContentType.objects.get_for_model(BatteryType),
            object_id=battery_type.pk,
            status="in_use",
            assigned_to_uav=uav,
        )

    # Spool for optical drones (matched by video_template)
    if isinstance(drone_type_obj, OpticalDroneType):
        spool_type = SpoolType.objects.filter(
            video_template=drone_type_obj.video_template
        ).first()
        if spool_type:
            Component.objects.create(
                content_type=ContentType.objects.get_for_model(SpoolType),
                object_id=spool_type.pk,
                status="in_use",
                assigned_to_uav=uav,
            )


@master_required
def uav_create(request):
    if request.method == "POST":
        form = UAVInstanceForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data.get("quantity", 1)
            with_kit = form.cleaned_data.get("with_kit", True)
            ct_id, obj_id = form.cleaned_data["drone_type"].split("-")
            notes = form.cleaned_data.get("notes", "")
            ct = ContentType.objects.get(pk=int(ct_id))
            drone_type_obj = ct.get_object_for_this_type(pk=int(obj_id))
            for _ in range(quantity):
                uav = UAVInstance.objects.create(
                    content_type_id=int(ct_id),
                    object_id=int(obj_id),
                    status="inspection",
                    created_by=request.user,
                    notes=notes,
                )
                if with_kit:
                    _create_kit_components(uav, drone_type_obj)
            msg = f"Додано {quantity} БПЛА." if quantity > 1 else "БПЛА додано."
            messages.success(request, msg)
            return redirect("equipment_accounting:equipment_list")
    else:
        form = UAVInstanceForm()
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Додати БПЛА",
    })


@master_required
def uav_edit(request, pk):
    uav = get_object_or_404(UAVInstance, pk=pk)
    if request.method == "POST":
        form = UAVInstanceForm(request.POST, instance=uav)
        if form.is_valid():
            form.save()
            messages.success(request, "БПЛА оновлено.")
            return redirect("equipment_accounting:equipment_list")
    else:
        form = UAVInstanceForm(instance=uav)
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Редагувати БПЛА",
    })


@master_required
def uav_delete(request, pk):
    uav = get_object_or_404(UAVInstance, pk=pk)
    if request.method == "POST":
        # Soft-delete: mark as deleted instead of removing from DB
        uav.status = 'deleted'
        uav.save(update_fields=['status', 'updated_at'])
        messages.success(request, "БПЛА видалено.")
        return redirect("equipment_accounting:equipment_list")
    return render(request, "equipment_accounting/equipment_confirm_delete.html", {
        "object": uav, "title": "Видалити БПЛА",
        "cancel_url": _list_url("drones"),
    })


# ── FPV Drone Type CRUD ─────────────────────────────────────────────

@master_required
def fpv_type_create(request):
    if request.method == "POST":
        form = FPVDroneTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Тип радіо дрона додано.")
            return redirect(_list_url("types"))
    else:
        form = FPVDroneTypeForm()
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Додати тип радіо дрона", "tab_redirect": "types",
    })


@master_required
def fpv_type_edit(request, pk):
    drone_type = get_object_or_404(FPVDroneType, pk=pk)
    if request.method == "POST":
        form = FPVDroneTypeForm(request.POST, instance=drone_type)
        if form.is_valid():
            form.save()
            messages.success(request, "Тип радіо дрона оновлено.")
            return redirect(_list_url("types"))
    else:
        form = FPVDroneTypeForm(instance=drone_type)
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Редагувати тип радіо дрона", "tab_redirect": "types",
    })


@master_required
def fpv_type_delete(request, pk):
    drone_type = get_object_or_404(FPVDroneType, pk=pk)
    if request.method == "POST":
        drone_type.delete()
        messages.success(request, "Тип радіо дрона видалено.")
        return redirect(_list_url("types"))
    return render(request, "equipment_accounting/equipment_confirm_delete.html", {
        "object": drone_type, "title": "Видалити тип радіо дрона",
        "cancel_url": _list_url("types"),
    })


# ── Optical Drone Type CRUD ────────────────────────────────────────

@master_required
def optical_type_create(request):
    if request.method == "POST":
        form = OpticalDroneTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Тип оптичного дрона додано.")
            return redirect(_list_url("types"))
    else:
        form = OpticalDroneTypeForm()
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Додати тип оптичного дрона", "tab_redirect": "types",
    })


@master_required
def optical_type_edit(request, pk):
    drone_type = get_object_or_404(OpticalDroneType, pk=pk)
    if request.method == "POST":
        form = OpticalDroneTypeForm(request.POST, instance=drone_type)
        if form.is_valid():
            form.save()
            messages.success(request, "Тип оптичного дрона оновлено.")
            return redirect(_list_url("types"))
    else:
        form = OpticalDroneTypeForm(instance=drone_type)
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Редагувати тип оптичного дрона", "tab_redirect": "types",
    })


@master_required
def optical_type_delete(request, pk):
    drone_type = get_object_or_404(OpticalDroneType, pk=pk)
    if request.method == "POST":
        drone_type.delete()
        messages.success(request, "Тип оптичного дрона видалено.")
        return redirect(_list_url("types"))
    return render(request, "equipment_accounting/equipment_confirm_delete.html", {
        "object": drone_type, "title": "Видалити тип оптичного дрона",
        "cancel_url": _list_url("types"),
    })


# ── Component CRUD ──────────────────────────────────────────────────

@master_required
def component_create(request):
    if request.method == "POST":
        form = ComponentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Комплектуючу додано.")
            return redirect(_list_url("components"))
    else:
        form = ComponentForm()
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Додати комплектуючу", "tab_redirect": "components",
    })


@master_required
def component_edit(request, pk):
    component = get_object_or_404(Component, pk=pk)
    if request.method == "POST":
        form = ComponentForm(request.POST, instance=component)
        if form.is_valid():
            form.save()
            messages.success(request, "Комплектуючу оновлено.")
            return redirect(_list_url("components"))
    else:
        form = ComponentForm(instance=component)
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Редагувати комплектуючу", "tab_redirect": "components",
    })


@master_required
def component_delete(request, pk):
    component = get_object_or_404(Component, pk=pk)
    if request.method == "POST":
        component.delete()
        messages.success(request, "Комплектуючу видалено.")
        return redirect(_list_url("components"))
    return render(request, "equipment_accounting/equipment_confirm_delete.html", {
        "object": component, "title": "Видалити комплектуючу",
        "cancel_url": _list_url("components"),
    })


# ── PowerTemplate CRUD ──────────────────────────────────────────────

@master_required
def power_template_create(request):
    if request.method == "POST":
        form = PowerTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Шаблон живлення додано.")
            return redirect(_list_url("templates"))
    else:
        form = PowerTemplateForm()
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Додати шаблон живлення", "tab_redirect": "templates",
    })


@master_required
def power_template_edit(request, pk):
    template = get_object_or_404(PowerTemplate, pk=pk)
    if request.method == "POST":
        form = PowerTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "Шаблон живлення оновлено.")
            return redirect(_list_url("templates"))
    else:
        form = PowerTemplateForm(instance=template)
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Редагувати шаблон живлення", "tab_redirect": "templates",
    })


@master_required
def power_template_delete(request, pk):
    template = get_object_or_404(PowerTemplate, pk=pk)
    if request.method == "POST":
        template.delete()
        messages.success(request, "Шаблон живлення видалено.")
        return redirect(_list_url("templates"))
    return render(request, "equipment_accounting/equipment_confirm_delete.html", {
        "object": template, "title": "Видалити шаблон живлення",
        "cancel_url": _list_url("templates"),
    })


# ── VideoTemplate CRUD ──────────────────────────────────────────────

@master_required
def video_template_create(request):
    if request.method == "POST":
        form = VideoTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Шаблон відео додано.")
            return redirect(_list_url("templates"))
    else:
        form = VideoTemplateForm()
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Додати шаблон відео", "tab_redirect": "templates",
    })


@master_required
def video_template_edit(request, pk):
    template = get_object_or_404(VideoTemplate, pk=pk)
    if request.method == "POST":
        form = VideoTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "Шаблон відео оновлено.")
            return redirect(_list_url("templates"))
    else:
        form = VideoTemplateForm(instance=template)
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Редагувати шаблон відео", "tab_redirect": "templates",
    })


@master_required
def video_template_delete(request, pk):
    template = get_object_or_404(VideoTemplate, pk=pk)
    if request.method == "POST":
        template.delete()
        messages.success(request, "Шаблон відео видалено.")
        return redirect(_list_url("templates"))
    return render(request, "equipment_accounting/equipment_confirm_delete.html", {
        "object": template, "title": "Видалити шаблон відео",
        "cancel_url": _list_url("templates"),
    })
