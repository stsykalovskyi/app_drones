from django.urls import path
from . import views

app_name = 'user_management'

urlpatterns = [
    path('approval-pending/', views.approval_pending_view, name='approval_pending'),
]
