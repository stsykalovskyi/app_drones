from django.shortcuts import render

def equipment_accounting_view(request):
    return render(request, 'equipment_accounting/equipment_accounting_page.html', {'title': 'Облік технічних засобів'})