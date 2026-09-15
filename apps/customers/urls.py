from django.urls import path
from . import views

app_name = 'customer_portal'

urlpatterns = [
    path('dashboard/', views.customer_dashboard_view, name='dashboard'),
    path('rfqs/', views.rfq_list_view, name='rfq_list'),
    path('rfqs/create/', views.rfq_create_view, name='rfq_create'),
    path('rfqs/<int:rfq_id>/', views.rfq_detail_view, name='rfq_detail'),
    path('rfqs/<int:rfq_id>/publish/', views.rfq_publish_view, name='rfq_publish'),
    path('rfqs/<int:rfq_id>/compare/', views.quotation_comparison_view, name='quotation_comparison'),
    path('quotations/<int:quotation_id>/award/', views.award_quotation_action_view, name='award_quotation'),
    path('orders/', views.customer_orders_list_view, name='orders_list'),
    path('orders/<int:po_id>/', views.customer_po_detail_view, name='po_detail'),
    path('orders/<int:po_id>/update-plan/', views.update_payment_plan_view, name='update_payment_plan'),
    path('payments/simulate/<int:installment_id>/', views.simulate_installment_payment_view, name='simulate_payment'),
]
