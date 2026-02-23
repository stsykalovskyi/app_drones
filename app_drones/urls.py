"""
URL configuration for app_drones project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path, re_path
from django.views.static import serve
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from user_management.views import CustomLoginView

from .views import home_view


from django.http import HttpResponse

def robots_txt(request):
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")

urlpatterns = [
    path('robots.txt', robots_txt),
    path('admin/', admin.site.urls),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/', include('allauth.urls')),
]

urlpatterns += [
    path('', login_required(home_view), name='home'),
    path('wiki/', include('wiki.urls')),
    path('documentation/', include('documentation.urls')), # New line
    path('equipment-accounting/', include('equipment_accounting.urls')), # New line
    path('expenses/', include('expense_log.urls')),
    path('user-management/', include('user_management.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
