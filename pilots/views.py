from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .forms import OrderStatusForm, StrikeReportForm
from .models import DroneOrder, StrikeReport

MASTER_GROUPS = {'майстер', 'командир майстерні'}


def _is_master(user):
    return user.is_superuser or user.groups.filter(name__in=MASTER_GROUPS).exists()


def master_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if _is_master(request.user):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped


# ── Strike reports ────────────────────────────────────────────────────────────

@login_required
def strike_report_create(request):
    if request.method == 'POST':
        form = StrikeReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.pilot = request.user
            report.save()
            messages.success(request, 'Звіт збережено.')
            return redirect('pilots:strike_report_list')
    else:
        form = StrikeReportForm()
    return render(request, 'pilots/strike_report_form.html', {
        'form': form, 'title': 'Новий звіт про удар',
    })


@login_required
def strike_report_list(request):
    if _is_master(request.user):
        reports = StrikeReport.objects.select_related('pilot', 'pilot__profile').all()
    else:
        reports = StrikeReport.objects.select_related('pilot', 'pilot__profile').filter(
            pilot=request.user
        )
    return render(request, 'pilots/strike_report_list.html', {
        'reports': reports, 'title': 'Звіти про удари',
    })


# ── Drone orders ──────────────────────────────────────────────────────────────

@login_required
def drone_order_create(request):
    from django.contrib.contenttypes.models import ContentType
    from equipment_accounting.models import FPVDroneType, OpticalDroneType, UAVInstance

    fpv_ct = ContentType.objects.get_for_model(FPVDroneType)
    opt_ct = ContentType.objects.get_for_model(OpticalDroneType)

    # Count ready instances per type
    ready_counts = {}
    for uav in UAVInstance.objects.filter(status='ready').values('content_type_id', 'object_id'):
        k = (uav['content_type_id'], uav['object_id'])
        ready_counts[k] = ready_counts.get(k, 0) + 1

    fpv_qs = FPVDroneType.objects.select_related(
        'model', 'purpose', 'power_template', 'video_frequency'
    ).prefetch_related('control_frequencies').order_by('model__name', 'prop_size')

    opt_qs = OpticalDroneType.objects.select_related(
        'model', 'purpose', 'power_template', 'video_template'
    ).prefetch_related('control_frequencies').order_by('model__name', 'prop_size')

    # Group ALL drone types (FPV + Optical) by DronePurpose name
    from collections import defaultdict
    purpose_map = defaultdict(list)

    for t in fpv_qs:
        count = ready_counts.get((fpv_ct.id, t.pk), 0)
        if count:
            purpose = t.purpose.name if t.purpose_id else 'Без призначення'
            purpose_map[purpose].append({'type': t, 'count': count, 'key': f'{fpv_ct.id}_{t.pk}'})

    for t in opt_qs:
        count = ready_counts.get((opt_ct.id, t.pk), 0)
        if count:
            purpose = t.purpose.name if t.purpose_id else 'Без призначення'
            purpose_map[purpose].append({'type': t, 'count': count, 'key': f'{opt_ct.id}_{t.pk}'})

    # Sort: named purposes alphabetically, "Без призначення" last
    named = sorted((k, v) for k, v in purpose_map.items() if k != 'Без призначення')
    bez = [('Без призначення', purpose_map['Без призначення'])] if 'Без призначення' in purpose_map else []
    sections = [{'label': k, 'cards': v} for k, v in named + bez]

    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        created = 0
        for key, val in request.POST.items():
            if not key.startswith('qty_'):
                continue
            try:
                qty = int(val)
            except (ValueError, TypeError):
                continue
            if qty <= 0:
                continue
            parts = key.split('_')
            if len(parts) != 3:
                continue
            try:
                ct_id = int(parts[1])
                obj_id = int(parts[2])
            except ValueError:
                continue
            from django.contrib.contenttypes.models import ContentType as CT
            try:
                ct = CT.objects.get(id=ct_id)
            except CT.DoesNotExist:
                continue
            DroneOrder.objects.create(
                pilot=request.user,
                content_type=ct,
                object_id=obj_id,
                quantity=qty,
                notes=notes,
            )
            created += 1

        if created:
            messages.success(request, f'Замовлення відправлено до майстерні ({created} поз.).')
            return redirect('pilots:drone_order_list')
        else:
            messages.warning(request, 'Не вибрано жодного дрона.')

    return render(request, 'pilots/order_form.html', {
        'sections': sections,
        'title': 'Замовити дрони',
    })


@login_required
def drone_order_list(request):
    if _is_master(request.user):
        orders = DroneOrder.objects.select_related(
            'pilot', 'pilot__profile', 'content_type', 'handled_by'
        ).all()
    else:
        orders = DroneOrder.objects.select_related(
            'pilot', 'pilot__profile', 'content_type', 'handled_by'
        ).filter(pilot=request.user)
    return render(request, 'pilots/order_list.html', {
        'orders': orders, 'title': 'Мої замовлення',
    })


# ── Workshop order management (masters only) ──────────────────────────────────

@master_required
def workshop_orders(request):
    orders = DroneOrder.objects.select_related(
        'pilot', 'pilot__profile', 'content_type', 'handled_by'
    ).filter(status__in=['pending', 'in_progress', 'ready']).order_by('status', '-created_at')

    # Group by drone type for inventory overview
    from django.contrib.contenttypes.models import ContentType
    from equipment_accounting.models import FPVDroneType, OpticalDroneType, UAVInstance

    # Count available drones in workshop by type
    inventory = {}
    for ct_model in [FPVDroneType, OpticalDroneType]:
        ct = ContentType.objects.get_for_model(ct_model)
        for dtype in ct_model.objects.select_related('model').all():
            available = UAVInstance.objects.filter(
                content_type=ct,
                object_id=dtype.pk,
                status='ready',
            ).count()
            key = f'{ct.id}:{dtype.pk}'
            inventory[key] = {'type': str(dtype), 'available': available}

    return render(request, 'pilots/workshop_orders.html', {
        'orders': orders,
        'inventory': inventory,
        'title': 'Обробка замовлень',
    })


@master_required
def workshop_order_update(request, pk):
    order = get_object_or_404(DroneOrder, pk=pk)
    if request.method == 'POST':
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            updated = form.save(commit=False)
            if not updated.handled_by:
                updated.handled_by = request.user
            updated.save()
            messages.success(request, 'Статус оновлено.')
    return redirect('pilots:workshop_orders')
