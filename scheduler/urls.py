from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='scheduler/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='landing'), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('book/', views.book_appointment, name='book_appointment'),
    path('cancel/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),
    path('manager-dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('availability/add/', views.manage_availability, name='manage_availability'),
    path('availability/delete/<int:availability_id>/', views.delete_availability, name='delete_availability'),
    path('api/slots/', views.get_available_slots, name='get_available_slots'),
    path('api/notifications/', views.get_notifications_api, name='get_notifications_api'),
    path('api/notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('appointment/<int:appointment_id>/accept/', views.accept_appointment, name='accept_appointment'),
    path('appointment/<int:appointment_id>/decline/', views.decline_appointment, name='decline_appointment'),
    path('appointment/<int:appointment_id>/complete/', views.complete_appointment, name='complete_appointment'),
]
