from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/buyer/', views.register_customer_view, name='register_customer'),
    path('register/supplier/', views.register_supplier_view, name='register_supplier'),
    path('pending-approval/', views.pending_approval_view, name='pending_approval'),
    path('dashboard/', views.dashboard_redirect_view, name='dashboard_redirect'),
    path('quick-switch/<str:role_code>/', views.quick_switch_view, name='quick_switch'),
    path('profile/', views.profile_view, name='profile'),
]
