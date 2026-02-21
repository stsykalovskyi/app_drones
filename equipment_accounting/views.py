from datetime import date
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import _get_available_uavs_for_kind
from .forms import (
    UAVInstanceForm, ComponentForm, PowerTemplateForm, VideoTemplateForm,
    FPVDroneTypeForm, OpticalDroneTypeForm,
    ManufacturerForm, DroneModelForm,
)
from .models import (
    UAVInstance, Component, PowerTemplate, VideoTemplate,
    FPVDroneType, OpticalDroneType,
    OtherComponentType,
    Manufacturer, DroneModel,
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

    # Components with filters
    comp_status_filter   = request.GET.get("comp_status", "")
    comp_category_filter = request.GET.get("comp_category", "")
    comp_assign_filter   = request.GET.get("comp_assign", "")

    components_qs = Component.objects.select_related(
        "power_template", "video_template", "other_type", "assigned_to_uav"
    ).order_by("-created_at")
    if comp_status_filter:
        components_qs = components_qs.filter(status=comp_status_filter)
    if comp_category_filter in ('battery', 'spool', 'other'):
        components_qs = components_qs.filter(kind=comp_category_filter)
    if comp_assign_filter == "assigned":
        components_qs = components_qs.filter(assigned_to_uav__isnull=False)
    elif comp_assign_filter == "free":
        components_qs = components_qs.filter(assigned_to_uav__isnull=True)

    comp_paginator  = Paginator(components_qs, 20)
    comp_page_obj   = comp_paginator.get_page(request.GET.get("cpage"))

    # Drone types
    fpv_drone_types = FPVDroneType.objects.select_related(
        "model", "model__manufacturer", "purpose",
        "video_frequency", "power_template",
    ).prefetch_related("control_frequencies")
    optical_drone_types = OpticalDroneType.objects.select_related(
        "model", "model__manufacturer", "purpose",
        "video_template", "power_template",
    ).prefetch_related("control_frequencies")

    # Templates (exclude soft-deleted)
    power_templates = PowerTemplate.objects.filter(is_deleted=False)
    video_templates = VideoTemplate.objects.filter(is_deleted=False)

    # Reference data
    manufacturers = Manufacturer.objects.all()
    drone_models = DroneModel.objects.select_related("manufacturer").all()

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
        "comp_page_obj": comp_page_obj,
        "comp_status_filter": comp_status_filter,
        "comp_category_filter": comp_category_filter,
        "comp_assign_filter": comp_assign_filter,
        "fpv_drone_types": fpv_drone_types,
        "optical_drone_types": optical_drone_types,
        "power_templates": power_templates,
        "video_templates": video_templates,
        "manufacturers": manufacturers,
        "drone_models": drone_models,
    }

    return render(request, "equipment_accounting/equipment_list.html", ctx)


# ── UAV Detail / Assembly ────────────────────────────────────────────

def _component_matches_uav_template(component, uav):
    """Return True if the component is compatible with the UAV's drone type."""
    drone_type = uav.uav_type
    if component.kind == 'battery':
        return component.power_template_id == drone_type.power_template_id
    if component.kind == 'spool':
        return (uav.content_type.model == 'opticaldronetype'
                and component.video_template.drone_model_id == drone_type.video_template.drone_model_id
                and component.video_template.is_analog == drone_type.video_template.is_analog)
    return True  # other — no template restriction


@login_required
def uav_detail(request, pk):
    uav = get_object_or_404(UAVInstance, pk=pk)
    assigned_components = list(
        uav.components.select_related('power_template', 'video_template', 'other_type').all()
    )
    for comp in assigned_components:
        comp.type_display = str(comp)

    filled_kinds = {comp.kind for comp in assigned_components}
    drone_type = uav.uav_type

    compatible_q = Q()
    if 'battery' not in filled_kinds:
        compatible_q |= Q(kind='battery', power_template=drone_type.power_template)
    if uav.content_type.model == 'opticaldronetype' and 'spool' not in filled_kinds:
        compatible_q |= Q(
            kind='spool',
            video_template__drone_model=drone_type.video_template.drone_model,
            video_template__is_analog=drone_type.video_template.is_analog,
        )

    if compatible_q:
        free_components = list(
            Component.objects.filter(compatible_q, assigned_to_uav=None)
            .exclude(status='damaged')
            .select_related('power_template', 'video_template', 'other_type')
        )
    else:
        free_components = []

    for comp in free_components:
        if comp.kind == 'battery':
            comp.type_display = f"Батарея: {comp.power_template}"
        elif comp.kind == 'spool':
            drone_model = comp.video_template.drone_model if comp.video_template else None
            comp.type_display = f"Котушка: {comp.video_template} ({drone_model or '—'})"
        else:
            comp.type_display = str(comp.other_type)

    kit_status = uav.get_kit_status()
    return render(request, 'equipment_accounting/uav_detail.html', {
        'uav': uav,
        'assigned_components': assigned_components,
        'free_components': free_components,
        'kit_status': kit_status,
    })


@master_required
def uav_attach_component(request, uav_pk, component_pk):
    if request.method != 'POST':
        return redirect('equipment_accounting:uav_detail', pk=uav_pk)
    uav = get_object_or_404(UAVInstance, pk=uav_pk)
    component = get_object_or_404(Component, pk=component_pk)
    if component.assigned_to_uav is not None:
        messages.error(request, 'Комплектуюча вже закріплена за іншим БПЛА.')
    elif not _component_matches_uav_template(component, uav):
        messages.error(request, 'Ця комплектуюча не сумісна з даним типом БПЛА.')
    elif component.kind in ('battery', 'spool') and uav.components.filter(kind=component.kind).exists():
        messages.error(request, 'БПЛА вже має комплектуючу цього типу.')
    elif not _component_matches_uav_template(component, uav):
        messages.error(request, 'Комплектуюча не підходить за шаблоном до цього БПЛА.')
    else:
        component.assigned_to_uav = uav
        component.status = 'in_use'
        component.save(update_fields=['assigned_to_uav', 'status', 'updated_at'])
        messages.success(request, 'Комплектуючу закріплено.')
    return redirect('equipment_accounting:uav_detail', pk=uav_pk)


@master_required
def uav_detach_component(request, uav_pk, component_pk):
    if request.method != 'POST':
        return redirect('equipment_accounting:uav_detail', pk=uav_pk)
    uav = get_object_or_404(UAVInstance, pk=uav_pk)
    component = get_object_or_404(Component, pk=component_pk)
    if component.assigned_to_uav_id != uav.pk:
        messages.error(request, 'Комплектуюча не закріплена за цим БПЛА.')
    else:
        component.assigned_to_uav = None
        component.status = 'disassembled'
        component.save(update_fields=['assigned_to_uav', 'status', 'updated_at'])
        messages.success(request, 'Комплектуючу відкріплено.')
    return redirect('equipment_accounting:uav_detail', pk=uav_pk)


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
    """Create battery (and spool for optical) components for a UAV."""
    Component.objects.create(
        kind='battery',
        power_template=drone_type_obj.power_template,
        status='in_use',
        assigned_to_uav=uav,
    )
    if isinstance(drone_type_obj, OpticalDroneType):
        Component.objects.create(
            kind='spool',
            video_template=drone_type_obj.video_template,
            status='in_use',
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
    components = list(uav.components.select_related('content_type').all())
    if request.method == "POST":
        delete_components = request.POST.get('delete_components') == '1'
        if components:
            if delete_components:
                uav.components.all().delete()
            else:
                uav.components.all().update(assigned_to_uav=None, status='disassembled')
        uav.status = 'deleted'
        uav.save(update_fields=['status', 'updated_at'])
        messages.success(request, "БПЛА видалено.")
        return redirect("equipment_accounting:equipment_list")
    for comp in components:
        comp.type_display = str(comp)
    return render(request, "equipment_accounting/equipment_confirm_delete.html", {
        "object": uav, "title": "Видалити БПЛА",
        "cancel_url": _list_url("drones"),
        "uav_components": components,
    })


# ── Manufacturer CRUD ───────────────────────────────────────────────

@master_required
def manufacturer_create(request):
    if request.method == "POST":
        form = ManufacturerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Виробника додано.")
            return redirect(_list_url("types"))
    else:
        form = ManufacturerForm()
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Додати виробника", "tab_redirect": "types",
    })


@master_required
def manufacturer_edit(request, pk):
    manufacturer = get_object_or_404(Manufacturer, pk=pk)
    if request.method == "POST":
        form = ManufacturerForm(request.POST, instance=manufacturer)
        if form.is_valid():
            form.save()
            messages.success(request, "Виробника оновлено.")
            return redirect(_list_url("types"))
    else:
        form = ManufacturerForm(instance=manufacturer)
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Редагувати виробника", "tab_redirect": "types",
    })


@master_required
def manufacturer_delete(request, pk):
    manufacturer = get_object_or_404(Manufacturer, pk=pk)
    if request.method == "POST":
        manufacturer.delete()
        messages.success(request, "Виробника видалено.")
        return redirect(_list_url("types"))
    return render(request, "equipment_accounting/equipment_confirm_delete.html", {
        "object": manufacturer, "title": "Видалити виробника",
        "cancel_url": _list_url("types"),
    })


# ── DroneModel CRUD ─────────────────────────────────────────────────

@master_required
def drone_model_create(request):
    if request.method == "POST":
        form = DroneModelForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Модель дрона додано.")
            return redirect(_list_url("types"))
    else:
        form = DroneModelForm()
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Додати модель дрона", "tab_redirect": "types",
    })


@master_required
def drone_model_edit(request, pk):
    drone_model = get_object_or_404(DroneModel, pk=pk)
    if request.method == "POST":
        form = DroneModelForm(request.POST, instance=drone_model)
        if form.is_valid():
            form.save()
            messages.success(request, "Модель дрона оновлено.")
            return redirect(_list_url("types"))
    else:
        form = DroneModelForm(instance=drone_model)
    return render(request, "equipment_accounting/equipment_form.html", {
        "form": form, "title": "Редагувати модель дрона", "tab_redirect": "types",
    })


@master_required
def drone_model_delete(request, pk):
    drone_model = get_object_or_404(DroneModel, pk=pk)
    if request.method == "POST":
        drone_model.delete()
        messages.success(request, "Модель дрона видалено.")
        return redirect(_list_url("types"))
    return render(request, "equipment_accounting/equipment_confirm_delete.html", {
        "object": drone_model, "title": "Видалити модель дрона",
        "cancel_url": _list_url("types"),
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

_COMPONENT_EXTRA = lambda: {
    "uav_filter_url": reverse("equipment_accounting:component_available_uavs")
}


@login_required
def component_available_uavs(request):
    """Return JSON list of UAVs available for a given component kind."""
    kind = request.GET.get("kind", "")
    exclude_pk = None
    try:
        exclude_pk = int(request.GET.get("exclude", ""))
    except (ValueError, TypeError):
        pass
    uavs = _get_available_uavs_for_kind(kind, exclude_component_pk=exclude_pk)
    return JsonResponse({
        "uavs": [{"id": u.pk, "text": str(u)} for u in uavs]
    })


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
        **_COMPONENT_EXTRA(),
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
        **_COMPONENT_EXTRA(),
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
    template = get_object_or_404(PowerTemplate, pk=pk, is_deleted=False)
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
    messages.error(request, "Видалення шаблонів живлення заборонено.")
    return redirect(_list_url("templates"))


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
    template = get_object_or_404(VideoTemplate, pk=pk, is_deleted=False)
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
    messages.error(request, "Видалення шаблонів відео заборонено.")
    return redirect(_list_url("templates"))
