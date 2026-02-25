import io
from datetime import date
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse, JsonResponse
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
    OtherComponentType, Location, UAVMovement,
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

    status_filter = request.GET.get("status", "")
    category_filter = request.GET.get("category", "")
    type_filter = request.GET.get("type", "")
    kit_filter = request.GET.get("kit", "")
    _location_raw = request.GET.get("location", "")
    location_filter = int(_location_raw) if _location_raw.isdigit() else None
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    search_q = request.GET.get("q", "")

    base_qs = UAVInstance.objects.select_related(
        "content_type", "created_by", "created_by__profile", "current_location", "role"
    ).prefetch_related("components")

    # Include given drones only when explicitly filtering by location or by given status
    if location_filter or status_filter == 'given':
        uavs = base_qs.exclude(status='deleted')
    else:
        uavs = base_qs.filter(status__in=UAVInstance.ACTIVE_STATUSES)

    if location_filter:
        uavs = uavs.filter(current_location_id=location_filter)

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

    # Summary counts — only statuses visible in the list (excludes deleted and given)
    all_uavs = UAVInstance.objects.filter(status__in=UAVInstance.ACTIVE_STATUSES)
    total_drones = all_uavs.count()
    status_counts = {}
    for code, label in UAVInstance.STATUS_CHOICES:
        if code in ('deleted', 'given'):
            continue
        status_counts[code] = {"label": label, "count": all_uavs.filter(status=code).count()}

    # Components with filters
    comp_status_filter     = request.GET.get("comp_status", "")
    comp_category_filter   = request.GET.get("comp_category", "")
    comp_assign_filter     = request.GET.get("comp_assign", "")
    comp_model_filter      = request.GET.get("comp_model", "")
    comp_drone_type_filter = request.GET.get("comp_drone_type", "")

    components_qs = Component.objects.select_related(
        "power_template", "video_template", "other_type", "assigned_to_uav"
    ).exclude(status='given').order_by("-created_at")
    if comp_status_filter:
        components_qs = components_qs.filter(status=comp_status_filter)
    if comp_category_filter in ('battery', 'spool', 'other'):
        components_qs = components_qs.filter(kind=comp_category_filter)
    if comp_assign_filter == "assigned":
        components_qs = components_qs.filter(assigned_to_uav__isnull=False)
    elif comp_assign_filter == "free":
        components_qs = components_qs.filter(assigned_to_uav__isnull=True)
    if comp_model_filter:
        try:
            model_id = int(comp_model_filter)
        except ValueError:
            model_id = None
        if model_id:
            pt_ids = list(
                FPVDroneType.objects.filter(model_id=model_id).values_list('power_template_id', flat=True)
            ) + list(
                OpticalDroneType.objects.filter(model_id=model_id).values_list('power_template_id', flat=True)
            )
            components_qs = components_qs.filter(
                Q(kind='battery', power_template_id__in=pt_ids) |
                Q(kind='spool', video_template__drone_model_id=model_id)
            )
    if comp_drone_type_filter == 'fpv':
        fpv_pt_ids = FPVDroneType.objects.values_list('power_template_id', flat=True)
        components_qs = components_qs.filter(kind='battery', power_template_id__in=fpv_pt_ids)
    elif comp_drone_type_filter == 'optical':
        opt_pt_ids = OpticalDroneType.objects.values_list('power_template_id', flat=True)
        components_qs = components_qs.filter(
            Q(kind='battery', power_template_id__in=opt_pt_ids) |
            Q(kind='spool')
        )

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
        "location_filter": location_filter,
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
        "comp_model_filter": comp_model_filter,
        "comp_drone_type_filter": comp_drone_type_filter,
        "fpv_drone_types": fpv_drone_types,
        "optical_drone_types": optical_drone_types,
        "power_templates": power_templates,
        "video_templates": video_templates,
        "manufacturers": manufacturers,
        "drone_models": drone_models,
        "locations": Location.objects.all(),
    }

    return render(request, "equipment_accounting/equipment_list.html", ctx)


# ── Component Statistics ─────────────────────────────────────────────

@master_required
def component_stats(request):
    battery_stats = PowerTemplate.objects.filter(is_deleted=False).annotate(
        total=Count('battery_components',
            filter=~Q(battery_components__status='given')),
        cnt_in_use=Count('battery_components',
            filter=Q(battery_components__status='in_use')),
        cnt_free=Count('battery_components',
            filter=Q(battery_components__status='disassembled')),
        cnt_damaged=Count('battery_components',
            filter=Q(battery_components__status='damaged')),
    ).filter(total__gt=0).order_by('name')

    spool_stats = VideoTemplate.objects.filter(is_deleted=False).prefetch_related(
        Prefetch('opticaldronetype_set', queryset=OpticalDroneType.objects.select_related('model'))
    ).annotate(
        total=Count('spool_components',
            filter=~Q(spool_components__status='given')),
        cnt_in_use=Count('spool_components',
            filter=Q(spool_components__status='in_use')),
        cnt_free=Count('spool_components',
            filter=Q(spool_components__status='disassembled')),
        cnt_damaged=Count('spool_components',
            filter=Q(spool_components__status='damaged')),
    ).filter(total__gt=0).order_by('name')

    other_stats = OtherComponentType.objects.annotate(
        total=Count('components',
            filter=~Q(components__status='given')),
        cnt_in_use=Count('components',
            filter=Q(components__status='in_use')),
        cnt_free=Count('components',
            filter=Q(components__status='disassembled')),
        cnt_damaged=Count('components',
            filter=Q(components__status='damaged')),
    ).filter(total__gt=0).order_by('category', 'model')

    def _kind_summary(kind):
        qs = Component.objects.filter(kind=kind).exclude(status='given')
        return {
            'total':   qs.count(),
            'in_use':  qs.filter(status='in_use').count(),
            'free':    qs.filter(status='disassembled').count(),
            'damaged': qs.filter(status='damaged').count(),
        }

    return render(request, 'equipment_accounting/component_stats.html', {
        'battery_stats':   battery_stats,
        'spool_stats':     spool_stats,
        'other_stats':     other_stats,
        'battery_summary': _kind_summary('battery'),
        'spool_summary':   _kind_summary('spool'),
    })


# ── Drone location statistics ─────────────────────────────────────────

@master_required
def drone_location_stats(request):
    """Show drone counts grouped by current location and status."""
    locations = Location.objects.annotate(
        total=Count('current_uavs', filter=~Q(current_uavs__status='deleted')),
        cnt_ready=Count('current_uavs', filter=Q(current_uavs__status='ready')),
        cnt_inspection=Count('current_uavs', filter=Q(current_uavs__status='inspection')),
        cnt_repair=Count('current_uavs', filter=Q(current_uavs__status='repair')),
        cnt_deferred=Count('current_uavs', filter=Q(current_uavs__status='deferred')),
        cnt_given=Count('current_uavs', filter=Q(current_uavs__status='given')),
    ).order_by('location_type', 'name')

    total_all = UAVInstance.objects.exclude(status='deleted').count()

    return render(request, 'equipment_accounting/drone_location_stats.html', {
        'locations': locations,
        'total_all': total_all,
    })


# ── Excel export ─────────────────────────────────────────────────────

EXPORT_COLS = [
    ('name',       'Назва'),
    ('count',      'В наявності'),
    ('unit',       'шт'),
    ('messenger',  'Для мессенджера'),
    ('new',        'Нові'),
    ('repair',     'В ремонті'),
    ('mfr_repair', 'В ремонті у виробника'),
    ('total',      'Підсумок'),
]

_SECTION_PRIORITY = {
    'День': 0, 'Ніч': 1, 'Оптика': 2,
    'Носій': 3, 'Мінувальник': 4, 'Перехоплювач': 5, 'Бомбардувальник': 6,
}

_SECTION_STYLE = {
    'День':   {'bg': 'BDD7EE', 'fg': '1F3864'},
    'Ніч':    {'bg': '2C3E6B', 'fg': 'FFFFFF'},
    'Оптика': {'bg': 'E2EFDA', 'fg': '375623'},
}
_DEFAULT_SECTION_STYLE = {'bg': 'F2F2F2', 'fg': '333333'}


@master_required
def uav_export_excel(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    selected_cols = [c for c, _ in EXPORT_COLS if request.GET.get(f'col_{c}', '1') == '1']

    fpv_ct = ContentType.objects.get_for_model(FPVDroneType)
    opt_ct = ContentType.objects.get_for_model(OpticalDroneType)

    active_qs = UAVInstance.objects.exclude(status__in=['deleted', 'given']).select_related(
        'content_type', 'role'
    )

    fpv_pks = set(active_qs.filter(content_type=fpv_ct).values_list('object_id', flat=True))
    opt_pks = set(active_qs.filter(content_type=opt_ct).values_list('object_id', flat=True))

    fpv_type_map = (
        {dt.pk: dt for dt in FPVDroneType.objects.filter(pk__in=fpv_pks)
         .select_related('model', 'purpose', 'video_frequency')
         .prefetch_related('control_frequencies')} if fpv_pks else {}
    )
    opt_type_map = (
        {dt.pk: dt for dt in OpticalDroneType.objects.filter(pk__in=opt_pks)
         .select_related('model', 'purpose', 'video_template')
         .prefetch_related('control_frequencies')} if opt_pks else {}
    )

    sections = {}
    section_order = []

    for uav in active_qs:
        role_name = uav.role.name if uav.role_id else '—'

        if uav.content_type_id == fpv_ct.pk:
            dt = fpv_type_map.get(uav.object_id)
            if not dt:
                continue
            section_key = ('Ніч' if dt.has_thermal else 'День') if role_name == 'Ударні' else role_name
            type_label = _fmt_drone_type_name(dt, 'Радіо')
            type_key = ('fpv', dt.pk)
        elif uav.content_type_id == opt_ct.pk:
            dt = opt_type_map.get(uav.object_id)
            if not dt:
                continue
            section_key = 'Оптика'
            type_label = _fmt_drone_type_name(dt, 'Оптика')
            type_key = ('opt', dt.pk)
        else:
            continue

        if section_key not in sections:
            sections[section_key] = {'types': {}, 'type_order': []}
            section_order.append(section_key)

        if type_key not in sections[section_key]['types']:
            sections[section_key]['types'][type_key] = {
                'label': type_label,
                'ready': 0, 'inspection': 0, 'repair': 0, 'deferred': 0,
            }
            sections[section_key]['type_order'].append(type_key)

        t = sections[section_key]['types'][type_key]
        if uav.status in t:
            t[uav.status] += 1

    section_order.sort(key=lambda sk: (_SECTION_PRIORITY.get(sk, 99), sk))

    # Build workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'БПЛА'

    col_label_map = dict(EXPORT_COLS)
    col_map = {c: i + 1 for i, c in enumerate(selected_cols)}

    # Header row
    hdr_font = Font(bold=True, size=10, name='Calibri')
    hdr_fill = PatternFill(fill_type='solid', fgColor='D6DCE4')
    for col_key, col_idx in col_map.items():
        cell = ws.cell(row=1, column=col_idx, value=col_label_map[col_key])
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    ws.row_dimensions[1].height = 28

    row_num = 2
    for section_key in section_order:
        section = sections[section_key]
        style = _SECTION_STYLE.get(section_key, _DEFAULT_SECTION_STYLE)
        sec_fill = PatternFill(fill_type='solid', fgColor=style['bg'])
        sec_font = Font(bold=True, size=10, name='Calibri', color=style['fg'])

        # Section header row
        for col_key, col_idx in col_map.items():
            val = None
            if col_key == 'name':      val = section_key
            elif col_key == 'count':   val = 1
            elif col_key == 'messenger': val = section_key
            elif col_key == 'total':   val = 0
            cell = ws.cell(row=row_num, column=col_idx, value=val)
            cell.font = sec_font
            cell.fill = sec_fill
        row_num += 1

        # Drone type rows
        for type_key in section['type_order']:
            t = section['types'][type_key]
            count = t['ready'] + t['deferred']
            for col_key, col_idx in col_map.items():
                val = None
                if col_key == 'name':        val = t['label']
                elif col_key == 'count':     val = count
                elif col_key == 'unit':      val = 'шт'
                elif col_key == 'messenger': val = f"{t['label']} {count} шт" if count > 0 else None
                elif col_key == 'new':       val = t['inspection'] or None
                elif col_key == 'repair':    val = t['repair'] or None
                elif col_key == 'mfr_repair': val = None
                elif col_key == 'total':
                    c_count = col_map.get('count')
                    c_new = col_map.get('new')
                    c_repair = col_map.get('repair')
                    if c_count and c_new and c_repair:
                        val = f"={get_column_letter(c_count)}{row_num}+{get_column_letter(c_new)}{row_num}-{get_column_letter(c_repair)}{row_num}"
                    else:
                        val = count
                ws.cell(row=row_num, column=col_idx, value=val)
            row_num += 1

    # Column widths
    col_widths = {
        'name': 52, 'count': 13, 'unit': 6,
        'messenger': 58, 'new': 10, 'repair': 13,
        'mfr_repair': 24, 'total': 13,
    }
    for col_key, col_idx in col_map.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = col_widths.get(col_key, 15)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="drones.xlsx"'
    return response


# ── UAV movement history ──────────────────────────────────────────────

def _fmt_freq(f):
    """Format a Frequency object as e.g. '900gh' or '5.8gh'."""
    v = f.value
    val_str = str(int(v)) if v == int(v) else str(v)
    return f"{val_str}gh"


def _fmt_drone_type_name(dt, category):
    """Format drone type label.

    FPV  → 'ModelName (prop\') (freq1 freq2) (#purpose)'
    Optic → 'ModelName (prop\') distancekm [ніч]'
    """
    if category == 'Оптика':
        name = f"{dt.model.name} ({dt.prop_size}')"
        if getattr(dt, 'video_template_id', None):
            name += f" {dt.video_template.max_distance}км"
        if dt.has_thermal:
            name += " ніч"
        return name

    # FPV / radio drone
    name = f"{dt.model.name} ({dt.prop_size}')"
    freq_parts = [_fmt_freq(f) for f in dt.control_frequencies.all()]
    if getattr(dt, 'video_frequency_id', None):
        freq_parts.append(_fmt_freq(dt.video_frequency))
    if freq_parts:
        name += f" ({' '.join(freq_parts)})"
    if dt.purpose_id:
        name += f" (#{dt.purpose.name})"
    return name


def _build_role_groups(uav_objs, fpv_ct, opt_ct, fpv_types, opt_types):
    """Return hierarchical role_groups list.

    FPV drones are grouped by role (Ударні → День/Ніч sub-groups, others by
    role name).  Optical drones are appended as a single 'Оптика' section at
    the end, regardless of the UAV's assigned role.
    """
    fpv_rk_order = []
    fpv_rk_data = {}
    opt_type_order = []
    opt_type_data = {}

    for uav in uav_objs:
        if uav.content_type_id == fpv_ct.pk:
            dt = fpv_types.get(uav.object_id)
            role_name = uav.role.name if uav.role_id else '—'
            if role_name == 'Ударні' and dt is not None:
                sub_label = 'Ніч' if dt.has_thermal else 'День'
            else:
                sub_label = None
            rk = (role_name, sub_label)
            if rk not in fpv_rk_data:
                fpv_rk_data[rk] = {}
                fpv_rk_order.append(rk)
            type_key = dt.pk if dt else None
            if type_key not in fpv_rk_data[rk]:
                fpv_rk_data[rk][type_key] = {
                    'category': 'Радіо',
                    'type_label': _fmt_drone_type_name(dt, 'Радіо') if dt else '—',
                    'count': 0,
                }
            fpv_rk_data[rk][type_key]['count'] += 1

        elif uav.content_type_id == opt_ct.pk:
            dt = opt_types.get(uav.object_id)
            type_key = dt.pk if dt else None
            if type_key not in opt_type_data:
                opt_type_data[type_key] = {
                    'category': 'Оптика',
                    'type_label': _fmt_drone_type_name(dt, 'Оптика') if dt else '—',
                    'count': 0,
                }
                opt_type_order.append(type_key)
            opt_type_data[type_key]['count'] += 1

    role_groups = []
    for (role_name, sub_label) in fpv_rk_order:
        if not role_groups or role_groups[-1]['role_name'] != role_name:
            role_groups.append({'role_name': role_name, 'sub_groups': []})
        role_groups[-1]['sub_groups'].append({
            'sub_label': sub_label,
            'types': list(fpv_rk_data[(role_name, sub_label)].values()),
        })

    if opt_type_order:
        role_groups.append({
            'role_name': 'Оптика',
            'sub_groups': [{'sub_label': None, 'types': [opt_type_data[k] for k in opt_type_order]}],
        })

    return role_groups


@master_required
def uav_movements(request):
    """Show UAV movements grouped by calendar date; each date is expandable."""
    reason_filter = request.GET.get('reason', '')
    _loc_raw = request.GET.get('location', '')
    location_filter = int(_loc_raw) if _loc_raw.isdigit() else None
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    base_qs = UAVMovement.objects.select_related(
        'uav', 'uav__content_type', 'uav__role',
        'from_location', 'to_location',
        'moved_by', 'moved_by__profile',
    )
    if reason_filter:
        base_qs = base_qs.filter(reason=reason_filter)
    if location_filter:
        base_qs = base_qs.filter(
            Q(from_location_id=location_filter) | Q(to_location_id=location_filter)
        )
    if date_from:
        try:
            base_qs = base_qs.filter(created_at__date__gte=date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            base_qs = base_qs.filter(created_at__date__lte=date.fromisoformat(date_to))
        except ValueError:
            pass

    # Outer group: by calendar date.  Inner group: by (reason, from, to, user).
    reason_labels = dict(UAVMovement.REASON_CHOICES)
    date_seen = {}   # date → date_group
    date_order = []  # ordered list of date keys

    for m in base_qs.order_by('-created_at'):
        d = m.created_at.date()
        if d not in date_seen:
            dg = {'date': m.created_at, 'count': 0, '_bseen': {}, '_border': []}
            date_seen[d] = dg
            date_order.append(d)
        dg = date_seen[d]
        dg['count'] += 1

        bk = (m.reason, m.from_location_id, m.to_location_id, m.moved_by_id)
        if bk not in dg['_bseen']:
            dg['_bseen'][bk] = {
                'reason': m.reason,
                'reason_label': reason_labels.get(m.reason, m.reason),
                'from_location_name': m.from_location.name if m.from_location else None,
                'to_location_name': m.to_location.name,
                'user_name': m.moved_by.profile.display_name if m.moved_by else '—',
                'uav_objs': [],
            }
            dg['_border'].append(bk)
        dg['_bseen'][bk]['uav_objs'].append(m.uav)

    date_groups = []
    for d in date_order:
        dg = date_seen[d]
        bseen = dg.pop('_bseen')
        border = dg.pop('_border')
        dg['batches'] = [bseen[k] for k in border]
        date_groups.append(dg)

    # Paginate by date
    paginator = Paginator(date_groups, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Batch-fetch drone types for all UAVs on the current page
    fpv_ct = ContentType.objects.get_for_model(FPVDroneType)
    opt_ct = ContentType.objects.get_for_model(OpticalDroneType)
    fpv_pks, opt_pks = set(), set()
    for dg in page_obj.object_list:
        for batch in dg['batches']:
            for uav in batch['uav_objs']:
                if uav.content_type_id == fpv_ct.pk:
                    fpv_pks.add(uav.object_id)
                elif uav.content_type_id == opt_ct.pk:
                    opt_pks.add(uav.object_id)

    fpv_types = (
        {dt.pk: dt for dt in FPVDroneType.objects.filter(pk__in=fpv_pks)
         .select_related('model', 'power_template', 'purpose', 'video_frequency')
         .prefetch_related('control_frequencies')} if fpv_pks else {}
    )
    opt_types = (
        {dt.pk: dt for dt in OpticalDroneType.objects.filter(pk__in=opt_pks)
         .select_related('model', 'power_template', 'purpose', 'video_template')
         .prefetch_related('control_frequencies')} if opt_pks else {}
    )

    for dg in page_obj.object_list:
        for batch in dg['batches']:
            batch['role_groups'] = _build_role_groups(
                batch['uav_objs'], fpv_ct, opt_ct, fpv_types, opt_types
            )

    return render(request, 'equipment_accounting/uav_movements.html', {
        'page_obj': page_obj,
        'reason_filter': reason_filter,
        'location_filter': location_filter,
        'date_from': date_from,
        'date_to': date_to,
        'reason_choices': UAVMovement.REASON_CHOICES,
        'locations': Location.objects.all(),
    })


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

    free_qs_base = Component.objects.filter(
        assigned_to_uav=None, status__in=['in_use', 'disassembled']
    ).select_related('power_template', 'video_template', 'other_type')

    free_components = []
    if 'battery' not in filled_kinds:
        free_components += list(
            free_qs_base.filter(kind='battery', power_template_id=drone_type.power_template_id)
        )
    if uav.content_type.model == 'opticaldronetype' and 'spool' not in filled_kinds:
        free_components += list(
            free_qs_base.filter(
                kind='spool',
                video_template__drone_model_id=drone_type.video_template.drone_model_id,
                video_template__is_analog=drone_type.video_template.is_analog,
            )
        )

    for comp in free_components:
        if comp.kind == 'battery':
            comp.type_display = f"Батарея: {comp.power_template}"
        elif comp.kind == 'spool':
            drone_model = comp.video_template.drone_model if comp.video_template else None
            comp.type_display = f"Котушка: {comp.video_template} ({drone_model or '—'})"
        else:
            comp.type_display = str(comp.other_type)

    movements = uav.movements.select_related(
        'from_location', 'to_location', 'moved_by', 'moved_by__profile'
    ).order_by('-created_at')

    kit_status = uav.get_kit_status()
    return render(request, 'equipment_accounting/uav_detail.html', {
        'uav': uav,
        'assigned_components': assigned_components,
        'free_components': free_components,
        'kit_status': kit_status,
        'movements': movements,
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
def uav_toggle_given(request, pk):
    """Give away a ready UAV or return a given UAV to the workshop."""
    if request.method != "POST":
        return redirect(_list_url("drones"))
    uav = get_object_or_404(UAVInstance, pk=pk)
    workshop = Location.objects.filter(location_type='workshop').first()
    next_url = request.POST.get('next') or _list_url("drones")

    if uav.status == 'given':
        # Return: move back to workshop
        prev_location = uav.current_location
        uav.status = 'inspection'
        uav.current_location = workshop
        uav.save(update_fields=['status', 'current_location', 'updated_at'])
        UAVMovement.objects.create(
            uav=uav,
            from_location=prev_location,
            to_location=workshop,
            moved_by=request.user,
            reason='returned',
        )
    elif uav.status == 'ready':
        to_location_id = request.POST.get('to_location_id')
        to_location = None
        if to_location_id:
            to_location = Location.objects.filter(pk=to_location_id).first()
        prev_location = uav.current_location
        uav.status = 'given'
        uav.current_location = to_location
        uav.components.update(status='given', assigned_to_uav=None)
        uav.save(update_fields=['status', 'current_location', 'updated_at'])
        if to_location:
            UAVMovement.objects.create(
                uav=uav,
                from_location=prev_location,
                to_location=to_location,
                moved_by=request.user,
                reason='given',
            )
    else:
        messages.error(request, 'Віддати можна лише готовий дрон.')
    return redirect(next_url)


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

    to_location_id = request.POST.get('to_location_id')
    to_location = Location.objects.filter(pk=to_location_id).first() if to_location_id else None

    if action == "delete":
        qs.update(status='deleted')
        messages.success(request, f"Видалено {count} БПЛА.")
    elif action == "given":
        eligible = qs.filter(status='ready')
        skipped = count - eligible.count()
        for uav in eligible.select_related('current_location'):
            prev = uav.current_location
            Component.objects.filter(assigned_to_uav=uav).update(status='given', assigned_to_uav=None)
            uav.status = 'given'
            uav.current_location = to_location
            uav.save(update_fields=['status', 'current_location', 'updated_at'])
            if to_location:
                UAVMovement.objects.create(
                    uav=uav,
                    from_location=prev,
                    to_location=to_location,
                    moved_by=request.user,
                    reason='given',
                )
        given_count = eligible.count()
        msg = f"Віддано {given_count} БПЛА разом з комплектуючими."
        if skipped:
            msg += f" Пропущено {count - given_count} (не готові)."
        messages.success(request, msg)
    elif action == 'repair':
        prev_statuses = {uav.pk: uav.current_location for uav in qs.select_related('current_location')}
        qs.update(status='repair')
        if to_location:
            for uav in qs:
                uav.current_location = to_location
                uav.save(update_fields=['current_location', 'updated_at'])
                UAVMovement.objects.create(
                    uav=uav,
                    from_location=prev_statuses.get(uav.pk),
                    to_location=to_location,
                    moved_by=request.user,
                    reason='repair',
                )
        messages.success(request, f"Статус {count} БПЛА змінено на \"Ремонт\".")
    elif action in dict(UAVInstance.STATUS_CHOICES):
        qs.update(status=action)
        label = dict(UAVInstance.STATUS_CHOICES)[action]
        messages.success(request, f"Статус {count} БПЛА змінено на \"{label}\".")
    else:
        messages.error(request, "Невідома дія.")

    return redirect("equipment_accounting:equipment_list")


# ── UAV CRUD ────────────────────────────────────────────────────────

def _create_kit_components(uav, drone_type_obj, with_battery=True, with_spool=True):
    """Create battery and/or spool components for a UAV based on its drone type."""
    if with_battery:
        Component.objects.create(
            kind='battery',
            power_template=drone_type_obj.power_template,
            status='in_use',
            assigned_to_uav=uav,
        )
    if with_spool and isinstance(drone_type_obj, OpticalDroneType):
        Component.objects.create(
            kind='spool',
            video_template=drone_type_obj.video_template,
            status='in_use',
            assigned_to_uav=uav,
        )


def _build_drone_types_kit_data():
    """Return JSON-serialisable dict mapping 'ct_id-obj_id' to kit info."""
    import json
    data = {}
    fpv_ct = ContentType.objects.get_for_model(FPVDroneType)
    for dt in FPVDroneType.objects.select_related('power_template', 'model', 'model__manufacturer'):
        data[f"{fpv_ct.pk}-{dt.pk}"] = {
            "category": "fpv",
            "battery_name": str(dt.power_template),
            "spool_name": None,
        }
    opt_ct = ContentType.objects.get_for_model(OpticalDroneType)
    for dt in OpticalDroneType.objects.select_related(
        'power_template', 'video_template', 'model', 'model__manufacturer'
    ):
        data[f"{opt_ct.pk}-{dt.pk}"] = {
            "category": "optical",
            "battery_name": str(dt.power_template),
            "spool_name": str(dt.video_template),
        }
    return json.dumps(data)


@master_required
def uav_create(request):
    workshop = Location.objects.filter(location_type='workshop').first()

    if request.method == "POST":
        form = UAVInstanceForm(request.POST)
        if form.is_valid():
            quantity      = form.cleaned_data.get("quantity", 1)
            with_battery  = form.cleaned_data.get("with_battery", True)
            with_spool    = form.cleaned_data.get("with_spool", True)
            from_location = form.cleaned_data.get("from_location")
            role          = form.cleaned_data.get("role")
            ct_id, obj_id = form.cleaned_data["drone_type"].split("-")
            ct = ContentType.objects.get(pk=int(ct_id))
            drone_type_obj = ct.get_object_for_this_type(pk=int(obj_id))
            created = []
            for _ in range(quantity):
                uav = UAVInstance.objects.create(
                    content_type_id=int(ct_id),
                    object_id=int(obj_id),
                    status="inspection",
                    created_by=request.user,
                    current_location=workshop,
                    role=role,
                )
                if with_battery or with_spool:
                    _create_kit_components(
                        uav, drone_type_obj,
                        with_battery=with_battery,
                        with_spool=with_spool,
                    )
                # Record movement: from_location → workshop
                UAVMovement.objects.create(
                    uav=uav,
                    from_location=from_location,
                    to_location=workshop,
                    moved_by=request.user,
                    reason='created',
                )
                created.append(uav)
            msg = f"Додано {quantity} БПЛА." if quantity > 1 else "БПЛА додано."
            messages.success(request, msg)
            return redirect("equipment_accounting:equipment_list")
    else:
        form = UAVInstanceForm()

    return render(request, "equipment_accounting/uav_create_form.html", {
        "form": form,
        "title": "Додати БПЛА",
        "drone_types_kit_json": _build_drone_types_kit_data(),
        "locations": Location.objects.all(),
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
    """Return JSON list of UAVs available for a given component kind and template."""
    kind = request.GET.get("kind", "")
    power_template_id = request.GET.get("power_template") or None
    video_template_id = request.GET.get("video_template") or None
    exclude_pk = None
    try:
        exclude_pk = int(request.GET.get("exclude", ""))
    except (ValueError, TypeError):
        pass
    uavs = _get_available_uavs_for_kind(
        kind,
        exclude_component_pk=exclude_pk,
        power_template_id=power_template_id,
        video_template_id=video_template_id,
    )
    return JsonResponse({
        "uavs": [{"id": u.pk, "text": str(u)} for u in uavs]
    })


@master_required
def component_bulk_action(request):
    """Handle bulk delete for selected components."""
    if request.method != "POST":
        return redirect("equipment_accounting:equipment_list")

    ids = request.POST.getlist("selected")
    if not ids:
        messages.warning(request, "Нічого не обрано.")
        return redirect("equipment_accounting:equipment_list" + "?tab=components")

    qs = Component.objects.filter(pk__in=ids)
    count = qs.count()
    qs.delete()
    messages.success(request, f"Видалено {count} комплектуючих.")
    return redirect(f"{reverse('equipment_accounting:equipment_list')}?tab=components")


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
def component_mark_damaged(request, pk):
    """Mark a component as damaged and detach it from any UAV."""
    if request.method != "POST":
        return redirect(_list_url("components"))
    component = get_object_or_404(Component, pk=pk)
    component.status = "damaged"
    component.assigned_to_uav = None
    component.save(update_fields=["status", "assigned_to_uav", "updated_at"])
    messages.success(request, "Комплектуючу позначено як пошкоджену.")
    next_url = request.POST.get("next") or _list_url("components")
    return redirect(next_url)


@master_required
def component_restore(request, pk):
    """Restore a damaged or disassembled component to in_use status."""
    if request.method != "POST":
        return redirect(_list_url("components"))
    component = get_object_or_404(Component, pk=pk)
    component.status = "in_use"
    component.save(update_fields=["status", "updated_at"])
    messages.success(request, "Комплектуючу відновлено.")
    next_url = request.POST.get("next") or _list_url("components")
    return redirect(next_url)


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
