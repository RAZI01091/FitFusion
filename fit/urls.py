from django.urls import path
from . import views
from .views import unlock, first_time

urlpatterns = [
    # Root entry point
   path('', views.home_view, name='home'),

    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('admin-panel/', views.admin_panel_view, name='admin_panel'),

    path(
        'admin-panel/toggle-status/<int:user_id>/',
        views.toggle_user_status_view,
        name='toggle_user_status'
    ),

    path('unlock/', unlock, name='unlock'),
    path('first-time/', first_time, name='first_time'),

    path('start-payment/', views.start_payment, name='start_payment'),
    path('confirm-payment/', views.confirm_payment, name='confirm_payment'),

    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
]