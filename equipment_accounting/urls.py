from django.urls import path
from . import views

app_name = 'equipment_accounting'

urlpatterns = [
    path('', views.equipment_list, name='equipment_list'),

    # UAV bulk actions
    path('uav/bulk/', views.uav_bulk_action, name='uav_bulk_action'),

    # UAV instances
    path('uav/add/', views.uav_create, name='uav_create'),
    path('uav/<int:pk>/edit/', views.uav_edit, name='uav_edit'),
    path('uav/<int:pk>/delete/', views.uav_delete, name='uav_delete'),

    # Components
    path('component/add/', views.component_create, name='component_create'),
    path('component/<int:pk>/edit/', views.component_edit, name='component_edit'),
    path('component/<int:pk>/delete/', views.component_delete, name='component_delete'),

    # Power templates
    path('power-template/add/', views.power_template_create, name='power_template_create'),
    path('power-template/<int:pk>/edit/', views.power_template_edit, name='power_template_edit'),
    path('power-template/<int:pk>/delete/', views.power_template_delete, name='power_template_delete'),

    # Video templates
    path('video-template/add/', views.video_template_create, name='video_template_create'),
    path('video-template/<int:pk>/edit/', views.video_template_edit, name='video_template_edit'),
    path('video-template/<int:pk>/delete/', views.video_template_delete, name='video_template_delete'),
]
