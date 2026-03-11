from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DroneOrderForm, OrderStatusForm, StrikeReportForm
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
    if request.method == 'POST':
        form = DroneOrderForm(request.POST)
        if form.is_valid():
            form.save(pilot=request.user)
            messages.success(request, 'Замовлення відправлено до майстерні.')
            return redirect('pilots:drone_order_list')
    else:
        form = DroneOrderForm()
    return render(request, 'pilots/order_form.html', {
        'form': form, 'title': 'Замовити дрон',
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
