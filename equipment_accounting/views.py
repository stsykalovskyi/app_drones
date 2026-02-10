from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def equipment_accounting_view(request):
    return render(request, 'equipment_accounting/equipment_accounting_page.html', {'title': 'Облік технічних засобів'})