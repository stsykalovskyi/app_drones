from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
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
    Background thread flow:
      1. Enqueue WA message with local video path.
      2. Poll OutgoingMessage.status until SENT/FAILED (max 10 min).
      3. Upload local video to B2 via boto3.
      4. Delete local file.
    """
    import os
    import time
    import logging
    from django.conf import settings
    from django.db import connection

    logger = logging.getLogger(__name__)
    try:
        connection.close()

        from pilots.models import StrikeReport
        from whatsapp_monitor.models import OutgoingMessage

        group = getattr(settings, 'WHATSAPP_STRIKE_GROUP', '')
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

        local_path = (
            os.path.join(str(settings.MEDIA_ROOT), report.video.name)
            if report.video else None
        )

        # 1. Enqueue WA message
        if group:
            msg = OutgoingMessage.objects.create(
                group_name=group,
                media_path=local_path or '',
                message_text=text,
            )

            # 2. Wait until sender processes the message (max 10 min)
            if local_path:
                for _ in range(120):  # 120 × 5 s = 10 min
                    time.sleep(5)
                    msg.refresh_from_db()
                    if msg.status in (OutgoingMessage.Status.SENT, OutgoingMessage.Status.FAILED):
                        break

        # 3. Upload to B2 and delete local file
        b2_key_id = os.getenv('B2_KEY_ID')
        if local_path and os.path.exists(local_path) and b2_key_id:
            try:
                import boto3
                client = boto3.client(
                    's3',
                    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=getattr(settings, 'AWS_S3_REGION_NAME', None),
                )
                with open(local_path, 'rb') as f:
                    client.upload_fileobj(f, settings.AWS_STORAGE_BUCKET_NAME, report.video.name)
                os.remove(local_path)
                logger.info('Strike report #%s: video uploaded to B2, local file removed.', report_id)
            except Exception as e:
                logger.error('B2 upload failed for strike report #%s: %s', report_id, e)

    except Exception as e:
        logger.exception('Strike report bg task failed #%s: %s', report_id, e)


@login_required
def strike_report_create(request):
    if request.method == 'POST':
        form = StrikeReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.pilot = request.user
            # Always save video locally first (B2 upload happens after WA send)
            if 'video' in request.FILES:
                from django.core.files.storage import FileSystemStorage
                fss = FileSystemStorage()
                video_file = request.FILES['video']
                from django.utils import timezone
                now = timezone.now()
                rel_path = f'strikes/videos/{now.year}/{now.month:02d}/{video_file.name}'
                saved_name = fss.save(rel_path, video_file)
                report.video = saved_name
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
def strike_report_delete(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    report = get_object_or_404(StrikeReport, pk=pk)
    if request.method == 'POST':
        if report.video:
            # delete from storage backend (B2 or local)
            try:
                report.video.delete(save=False)
            except Exception:
                pass
            # also remove local file if it still exists on disk
            from django.conf import settings as _s
            import os as _os
            local_path = _s.MEDIA_ROOT / report.video.name
            if _os.path.exists(local_path):
                _os.remove(local_path)
        report.delete()
        messages.success(request, 'Звіт видалено.')
        return redirect('pilots:strike_report_list')
    raise PermissionDenied


@login_required
def strike_video(request, pk):
    """Return a presigned URL (B2) or serve local file for video playback."""
    report = get_object_or_404(StrikeReport, pk=pk)
    if not (request.user == report.pilot or request.user.has_perm('pilots.change_strikereport')):
        raise PermissionDenied
    if not report.video:
        raise Http404

    import os
    from django.conf import settings
    local_path = settings.MEDIA_ROOT / report.video.name
    if os.path.exists(local_path):
        from django.http import FileResponse
        return FileResponse(open(local_path, 'rb'), content_type='video/mp4')

    # B2: generate presigned URL valid for 1 hour
    import boto3
    client = boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, 'AWS_S3_REGION_NAME', None),
    )
    url = client.generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': report.video.name},
        ExpiresIn=3600,
    )
    return HttpResponseRedirect(url)


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
