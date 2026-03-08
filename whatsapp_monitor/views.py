from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate

from .models import StrikeReport


@login_required
def strike_stats(request):
    # Date filter
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')

    qs = StrikeReport.objects.filter(parsed_ok=True)
    if date_from:
        qs = qs.filter(received_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(received_at__date__lte=date_to)

    total = qs.count()

    # Result breakdown
    result_counts = {
        row['result']: row['cnt']
        for row in qs.values('result').annotate(cnt=Count('pk'))
    }

    # By date
    by_date = list(
        qs.annotate(day=TruncDate('received_at'))
          .values('day')
          .annotate(
              cnt=Count('pk'),
              destroyed=Count('pk', filter=Q(result='destroyed')),
              damaged=Count('pk', filter=Q(result='damaged')),
              missed=Count('pk', filter=Q(result='missed')),
          )
          .order_by('-day')
    )

    # Top operators (pozyvnyi)
    top_operators = list(
        qs.exclude(pozyvnyi='')
          .values('pozyvnyi')
          .annotate(
              cnt=Count('pk'),
              destroyed=Count('pk', filter=Q(result='destroyed')),
          )
          .order_by('-cnt')[:15]
    )

    # Top targets
    top_targets = list(
        qs.exclude(target='')
          .values('target')
          .annotate(cnt=Count('pk'))
          .order_by('-cnt')[:15]
    )

    # Top drone types (zasib)
    top_zasib = list(
        qs.exclude(zasib='')
          .values('zasib')
          .annotate(
              cnt=Count('pk'),
              destroyed=Count('pk', filter=Q(result='destroyed')),
          )
          .order_by('-cnt')[:15]
    )

    # Recent raw (unparsed)
    recent_raw = (
        StrikeReport.objects.filter(parsed_ok=False)
        .order_by('-received_at')[:20]
    )

    context = {
        'total': total,
        'result_counts': result_counts,
        'destroyed': result_counts.get('destroyed', 0),
        'damaged':   result_counts.get('damaged', 0),
        'missed':    result_counts.get('missed', 0),
        'unknown':   result_counts.get('unknown', 0),
        'by_date':        by_date,
        'top_operators':  top_operators,
        'top_targets':    top_targets,
        'top_zasib':      top_zasib,
        'recent_raw':     recent_raw,
        'date_from': date_from,
        'date_to':   date_to,
    }
    return render(request, 'whatsapp_monitor/stats.html', context)
