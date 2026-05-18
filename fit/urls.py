from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-panel/', views.admin_panel_view, name='admin_panel'),
    path('admin-panel/toggle-status/<int:user_id>/', views.toggle_user_status_view, name='toggle_user_status'),
]
