from django.shortcuts import render

def technical_docs_accounting_view(request):
    return render(request, 'technical_docs_accounting/technical_docs_accounting_page.html', {'title': 'Облік технічної документації'})