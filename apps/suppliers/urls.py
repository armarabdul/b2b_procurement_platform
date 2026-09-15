from django.urls import path
from . import views

app_name = 'supplier_portal'

urlpatterns = [
    path('dashboard/', views.supplier_dashboard_view, name='dashboard'),
    path('rfqs/', views.rfq_discovery_view, name='rfq_discovery'),
    path('rfqs/<int:rfq_id>/', views.supplier_rfq_detail_view, name='rfq_detail'),
    path('rfqs/<int:rfq_id>/quote/', views.submit_quotation_view, name='submit_quotation'),
    path('quotations/', views.my_quotations_list_view, name='my_quotations'),
    path('orders/', views.supplier_orders_list_view, name='orders_list'),
    path('orders/<int:po_id>/', views.supplier_po_detail_view, name='supplier_po_detail'),
    path('orders/<int:po_id>/status/', views.update_order_status_view, name='update_order_status'),
]
