from django.urls import path
from . import views

app_name = 'equipment_accounting'

urlpatterns = [
    path('', views.equipment_list, name='equipment_list'),
    path('stats/', views.component_stats, name='component_stats'),
    path('stats/drones/', views.drone_location_stats, name='drone_location_stats'),
    path('stats/movements/', views.uav_movements, name='uav_movements'),

    # UAV bulk actions
    path('uav/bulk/', views.uav_bulk_action, name='uav_bulk_action'),

    # UAV instances
    path('uav/add/', views.uav_create, name='uav_create'),
    path('uav/<int:pk>/', views.uav_detail, name='uav_detail'),
    path('uav/<int:pk>/edit/', views.uav_edit, name='uav_edit'),
    path('uav/<int:pk>/toggle-given/', views.uav_toggle_given, name='uav_toggle_given'),
    path('uav/<int:pk>/delete/', views.uav_delete, name='uav_delete'),
    path('uav/<int:uav_pk>/attach/<int:component_pk>/', views.uav_attach_component, name='uav_attach_component'),
    path('uav/<int:uav_pk>/detach/<int:component_pk>/', views.uav_detach_component, name='uav_detach_component'),

    # Manufacturers
    path('manufacturer/add/', views.manufacturer_create, name='manufacturer_create'),
    path('manufacturer/<int:pk>/edit/', views.manufacturer_edit, name='manufacturer_edit'),
    path('manufacturer/<int:pk>/delete/', views.manufacturer_delete, name='manufacturer_delete'),

    # Drone models
    path('drone-model/add/', views.drone_model_create, name='drone_model_create'),
    path('drone-model/<int:pk>/edit/', views.drone_model_edit, name='drone_model_edit'),
    path('drone-model/<int:pk>/delete/', views.drone_model_delete, name='drone_model_delete'),

    # FPV drone types
    path('fpv-type/add/', views.fpv_type_create, name='fpv_type_create'),
    path('fpv-type/<int:pk>/edit/', views.fpv_type_edit, name='fpv_type_edit'),
    path('fpv-type/<int:pk>/delete/', views.fpv_type_delete, name='fpv_type_delete'),

    # Optical drone types
    path('optical-type/add/', views.optical_type_create, name='optical_type_create'),
    path('optical-type/<int:pk>/edit/', views.optical_type_edit, name='optical_type_edit'),
    path('optical-type/<int:pk>/delete/', views.optical_type_delete, name='optical_type_delete'),

    # Components
    path('component/bulk/', views.component_bulk_action, name='component_bulk_action'),
    path('component/available-uavs/', views.component_available_uavs, name='component_available_uavs'),
    path('component/add/', views.component_create, name='component_create'),
    path('component/<int:pk>/edit/', views.component_edit, name='component_edit'),
    path('component/<int:pk>/damaged/', views.component_mark_damaged, name='component_mark_damaged'),
    path('component/<int:pk>/restore/', views.component_restore, name='component_restore'),
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
