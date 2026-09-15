from django.urls import path
from . import admin_views

app_name = 'admin_portal'

urlpatterns = [
    path('dashboard/', admin_views.admin_dashboard_view, name='dashboard'),
    path('customers/', admin_views.admin_customers_view, name='customers'),
    path('suppliers/', admin_views.admin_suppliers_view, name='suppliers'),
    path('users/<int:user_id>/<str:action>/', admin_views.admin_update_user_status_view, name='update_user_status'),
    path('rfqs/', admin_views.admin_rfqs_view, name='rfqs'),
    path('rfqs/<int:rfq_id>/status/<str:new_status>/', admin_views.admin_rfq_toggle_status_view, name='rfq_toggle_status'),
    path('quotations/', admin_views.admin_quotations_view, name='quotations'),
    path('orders/', admin_views.admin_orders_view, name='orders'),
    path('payments/', admin_views.admin_payments_view, name='payments'),
    path('audit-logs/', admin_views.admin_audit_logs_view, name='audit_logs'),
]
