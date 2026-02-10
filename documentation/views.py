from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def documentation_view(request):
    return render(request, 'documentation/documentation_page.html', {'title': 'Документація'})