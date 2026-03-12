from django.urls import path
from . import views

app_name = 'user_management'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('approval-pending/', views.approval_pending_view, name='approval_pending'),
    path('users/', views.user_list_view, name='user_list'),
    path('impersonate/<int:user_id>/', views.impersonate_start, name='impersonate_start'),
    path('impersonate/stop/', views.impersonate_stop, name='impersonate_stop'),
]
