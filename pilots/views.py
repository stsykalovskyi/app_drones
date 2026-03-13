from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .forms import OrderStatusForm, StrikeReportForm
from .models import DroneOrder, StrikeReport

def master_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.has_perm('pilots.change_droneorder'):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped


# ── Strike reports ────────────────────────────────────────────────────────────

def _enqueue_strike_report_bg(report_id):
    """
    Run in a background thread: fetch the saved report and enqueue WhatsApp messages.
    Uses a fresh DB connection so it never blocks the request thread.
    """
    import os
    import logging
    from datetime import datetime, timezone, timedelta
    from django.conf import settings
    from django.db import connection

    logger = logging.getLogger(__name__)
    try:
        # Close the inherited connection so Django opens a fresh one in this thread
        connection.close()

        from pilots.models import StrikeReport
        from whatsapp_monitor.models import OutgoingMessage

        group = getattr(settings, 'WHATSAPP_STRIKE_GROUP', '')
        if not group:
            return

        report = StrikeReport.objects.select_related('pilot', 'pilot__profile').get(pk=report_id)

        lines = [
            f'Екіпаж: {report.crew}',
            f'Дата: {report.strike_date}',
            f'Засіб: {report.weapon_type} — {report.weapon_name}',
            f'БК: {report.ammo_type}',
            f'Ініціація: {report.initiation_type}',
            f'Ціль: {report.target_type}',
            f'Результат: {report.result_type}',
        ]
        if report.notes:
            lines.append(f'Примітки: {report.notes}')
        text = '\n'.join(lines)

        now = datetime.now(tz=timezone.utc)
        video_delay = getattr(settings, 'WHATSAPP_VIDEO_UPLOAD_DELAY', 30)

        if report.video:
            video_abs = os.path.join(str(settings.MEDIA_ROOT), report.video.name)
            OutgoingMessage.objects.create(
                group_name=group,
                media_path=video_abs,
                message_text='',
                send_after=None,
            )
            OutgoingMessage.objects.create(
                group_name=group,
                message_text=text,
                send_after=now + timedelta(seconds=video_delay),
            )
        else:
            OutgoingMessage.objects.create(
                group_name=group,
                message_text=text,
                send_after=None,
            )
    except Exception as e:
        logger.exception('WhatsApp enqueue failed for strike report #%s: %s', report_id, e)


@login_required
def strike_report_create(request):
    if request.method == 'POST':
        form = StrikeReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.pilot = request.user
            report.save()
            import threading
            threading.Thread(
                target=_enqueue_strike_report_bg,
                args=(report.pk,),
                daemon=True,
            ).start()
            messages.success(request, 'Звіт збережено.')
            return redirect('pilots:strike_report_list')
    else:
        form = StrikeReportForm()
    return render(request, 'pilots/strike_report_form.html', {
        'form': form, 'title': 'Новий звіт про удар',
    })


@login_required
def strike_report_list(request):
    if request.user.has_perm('pilots.change_strikereport'):
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

    # Group drone types by DronePurpose name.
    # For "FPV" purpose, split into "FPV Радіо" (FPVDroneType) and "FPV Оптика" (OpticalDroneType).
    from collections import defaultdict
    purpose_map = defaultdict(list)

    for t in fpv_qs:
        count = ready_counts.get((fpv_ct.id, t.pk), 0)
        if count:
            purpose = t.purpose.name if t.purpose_id else 'Без призначення'
            if purpose == 'FPV':
                purpose = 'FPV Радіо'
            purpose_map[purpose].append({'type': t, 'count': count, 'key': f'{fpv_ct.id}_{t.pk}'})

    for t in opt_qs:
        count = ready_counts.get((opt_ct.id, t.pk), 0)
        if count:
            purpose = t.purpose.name if t.purpose_id else 'Без призначення'
            if purpose == 'FPV':
                purpose = 'FPV Оптика'
            purpose_map[purpose].append({'type': t, 'count': count, 'key': f'{opt_ct.id}_{t.pk}'})

    _ORDER = {'FPV Радіо': 0, 'FPV Оптика': 1}
    # Sort: FPV Радіо → FPV Оптика → rest alphabetically, "Без призначення" last
    named = sorted(
        ((k, v) for k, v in purpose_map.items() if k != 'Без призначення'),
        key=lambda kv: (_ORDER.get(kv[0], 2), kv[0]),
    )
    bez = [('Без призначення', purpose_map['Без призначення'])] if 'Без призначення' in purpose_map else []
    sections = [{'label': k, 'cards': v} for k, v in named + bez]

    return render(request, 'pilots/order_form.html', {
        'sections': sections,
        'title': 'Замовити дрони',
    })


def _parse_qty_post(post):
    """Parse qty_<ct_id>_<obj_id> fields from POST. Returns list of (ct_id, obj_id, qty)."""
    from django.contrib.contenttypes.models import ContentType as CT
    result = []
    for key, val in post.items():
        if not key.startswith('qty_'):
            continue
        parts = key.split('_')
        if len(parts) != 3:
            continue
        try:
            qty = int(val)
            ct_id = int(parts[1])
            obj_id = int(parts[2])
        except (ValueError, TypeError):
            continue
        if qty <= 0:
            continue
        result.append((ct_id, obj_id, qty))
    return result


@login_required
def order_review(request):
    from django.contrib.contenttypes.models import ContentType as CT

    if request.method != 'POST':
        return redirect('pilots:drone_order_create')

    notes = request.POST.get('notes', '')

    # Confirm → create orders
    if 'confirm' in request.POST:
        import uuid as _uuid
        batch = _uuid.uuid4()
        created = 0
        for ct_id, obj_id, qty in _parse_qty_post(request.POST):
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
                batch_id=batch,
            )
            created += 1
        if created:
            messages.success(request, f'Замовлення відправлено до майстерні ({created} поз.).')
        else:
            messages.warning(request, 'Не вибрано жодного дрона.')
        return redirect('pilots:drone_order_list')

    # Build review items
    from equipment_accounting.models import FPVDroneType, OpticalDroneType, UAVInstance
    fpv_ct = CT.objects.get_for_model(FPVDroneType)
    opt_ct = CT.objects.get_for_model(OpticalDroneType)

    ready_counts = {}
    for uav in UAVInstance.objects.filter(status='ready').values('content_type_id', 'object_id'):
        k = (uav['content_type_id'], uav['object_id'])
        ready_counts[k] = ready_counts.get(k, 0) + 1

    items = []
    for ct_id, obj_id, qty in _parse_qty_post(request.POST):
        try:
            if ct_id == fpv_ct.id:
                obj = FPVDroneType.objects.select_related(
                    'model', 'purpose', 'video_frequency'
                ).prefetch_related('control_frequencies').get(id=obj_id)
            elif ct_id == opt_ct.id:
                obj = OpticalDroneType.objects.select_related(
                    'model', 'purpose', 'video_template'
                ).prefetch_related('control_frequencies').get(id=obj_id)
            else:
                ct = CT.objects.get(id=ct_id)
                obj = ct.get_object_for_this_type(id=obj_id)
        except Exception:
            continue

        freqs = list(obj.control_frequencies.all()) if hasattr(obj, 'control_frequencies') else []
        max_count = ready_counts.get((ct_id, obj_id), qty)
        items.append({
            'key': f'{ct_id}_{obj_id}',
            'qty': min(qty, max_count),
            'max': max_count,
            'type': obj,
            'freqs': freqs,
        })

    if not items:
        messages.warning(request, 'Не вибрано жодного дрона.')
        return redirect('pilots:drone_order_create')

    return render(request, 'pilots/order_review.html', {
        'items': items,
        'notes': notes,
        'title': 'Підтвердження замовлення',
    })


@login_required
def drone_order_list(request):
    from collections import OrderedDict
    qs = DroneOrder.objects.select_related(
        'pilot', 'pilot__profile', 'content_type', 'handled_by'
    ).filter(pilot=request.user).order_by('-created_at')

    # Group by batch_id; orders without batch treated as individual batches
    batches = OrderedDict()
    for order in qs:
        bid = str(order.batch_id) if order.batch_id else f'__{order.pk}'
        if bid not in batches:
            batches[bid] = {
                'created_at': order.created_at,
                'notes': order.notes,
                'orders': [],
            }
        batches[bid]['orders'].append(order)

    # Compute aggregate status per batch (worst = pending > in_progress > ready > delivered > cancelled)
    STATUS_RANK = {'pending': 0, 'in_progress': 1, 'ready': 2, 'delivered': 3, 'cancelled': 4}
    STATUS_COLORS = DroneOrder.STATUS_COLORS
    batch_list = []
    for b in batches.values():
        statuses = [o.status for o in b['orders']]
        agg = min(statuses, key=lambda s: STATUS_RANK.get(s, 99))
        b['agg_status'] = agg
        b['agg_status_display'] = dict(DroneOrder.STATUS_CHOICES).get(agg, agg)
        b['agg_status_color'] = STATUS_COLORS.get(agg, 'info')
        batch_list.append(b)

    return render(request, 'pilots/order_list.html', {
        'batch_list': batch_list,
        'title': 'Мої замовлення',
    })


# ── Workshop order management (masters only) ──────────────────────────────────

@master_required
def workshop_orders(request):
    from collections import OrderedDict
    qs = DroneOrder.objects.select_related(
        'pilot', 'pilot__profile', 'content_type', 'handled_by'
    ).filter(status__in=['pending', 'in_progress', 'ready']).order_by(
        'pilot__id', '-created_at'
    )

    # Group: pilot → batch → orders
    pilots = OrderedDict()
    for order in qs:
        pid = order.pilot_id
        if pid not in pilots:
            pilots[pid] = {'pilot': order.pilot, 'batches': OrderedDict()}
        bid = str(order.batch_id) if order.batch_id else f'__{order.pk}'
        batches = pilots[pid]['batches']
        if bid not in batches:
            batches[bid] = {
                'created_at': order.created_at,
                'notes': order.notes,
                'orders': [],
            }
        batches[bid]['orders'].append(order)

    # Convert inner dicts to lists
    pilot_groups = []
    for pg in pilots.values():
        pilot_groups.append({
            'pilot': pg['pilot'],
            'batches': list(pg['batches'].values()),
        })

    return render(request, 'pilots/workshop_orders.html', {
        'pilot_groups': pilot_groups,
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


@master_required
def workshop_orders_archive(request):
    qs = DroneOrder.objects.select_related(
        'pilot', 'pilot__profile', 'content_type', 'handled_by'
    ).filter(status__in=['delivered', 'cancelled']).order_by('-updated_at')
    return render(request, 'pilots/workshop_orders_archive.html', {
        'orders': qs,
        'title': 'Завершені замовлення',
    })
