from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from apps.accounts.permissions import role_required
from apps.accounts.models import User, UserRole, ApprovalStatus
from apps.customers.models import CustomerProfile
from apps.suppliers.models import SupplierProfile
from apps.rfqs.models import RFQ, RFQStatus
from apps.quotations.models import Quotation, QuotationStatus
from apps.procurement.models import PurchaseOrder, POStatus
from apps.payments.models import Payment, PaymentInstallment, PaymentStatus
from apps.audit.models import ActivityLog
from apps.notifications.models import Notification, NotificationType


@login_required
@role_required([UserRole.ADMIN])
def admin_dashboard_view(request):
    total_customers = User.objects.filter(role=UserRole.CUSTOMER).count()
    total_suppliers = User.objects.filter(role=UserRole.SUPPLIER).count()
    pending_approvals = User.objects.filter(approval_status=ApprovalStatus.PENDING).count()

    active_rfqs = RFQ.objects.filter(status__in=[RFQStatus.PUBLISHED, RFQStatus.QUOTATIONS_RECEIVED, RFQStatus.UNDER_REVIEW]).count()
    total_quotes = Quotation.objects.count()
    awarded_rfqs = RFQ.objects.filter(status=RFQStatus.AWARDED).count()

    total_orders = PurchaseOrder.objects.count()
    total_procurement_value = sum((po.total_amount for po in PurchaseOrder.objects.all()), Decimal('0.00'))
    total_mock_payments_collected = sum((p.amount_paid for p in Payment.objects.all()), Decimal('0.00'))

    recent_users_pending = User.objects.filter(approval_status=ApprovalStatus.PENDING).order_by('-created_at')[:5]
    recent_rfqs = RFQ.objects.select_related('customer', 'category').order_by('-created_at')[:6]
    recent_audit_logs = ActivityLog.objects.select_related('user').order_by('-timestamp')[:8]

    context = {
        'active_nav': 'admin_dashboard',
        'stats': {
            'total_customers': total_customers,
            'total_suppliers': total_suppliers,
            'pending_approvals': pending_approvals,
            'active_rfqs': active_rfqs,
            'total_quotes': total_quotes,
            'awarded_rfqs': awarded_rfqs,
            'total_orders': total_orders,
            'procurement_value': total_procurement_value,
            'mock_payments': total_mock_payments_collected,
        },
        'recent_users_pending': recent_users_pending,
        'recent_rfqs': recent_rfqs,
        'recent_audit_logs': recent_audit_logs,
    }
    return render(request, 'admin/dashboard.html', context)


@login_required
@role_required([UserRole.ADMIN])
def admin_customers_view(request):
    customers = User.objects.filter(role=UserRole.CUSTOMER).select_related('customer_profile').order_by('-created_at')
    return render(request, 'admin/customers_list.html', {
        'active_nav': 'admin_customers',
        'customers': customers,
    })


@login_required
@role_required([UserRole.ADMIN])
def admin_suppliers_view(request):
    suppliers = User.objects.filter(role=UserRole.SUPPLIER).select_related('supplier_profile').order_by('-created_at')
    return render(request, 'admin/suppliers_list.html', {
        'active_nav': 'admin_suppliers',
        'suppliers': suppliers,
    })


@login_required
@role_required([UserRole.ADMIN])
def admin_update_user_status_view(request, user_id, action):
    target_user = get_object_or_404(User, id=user_id)

    status_map = {
        'approve': ApprovalStatus.APPROVED,
        'reject': ApprovalStatus.REJECTED,
        'suspend': ApprovalStatus.SUSPENDED,
        'activate': ApprovalStatus.APPROVED,
    }

    new_status = status_map.get(action)
    if new_status:
        target_user.approval_status = new_status
        target_user.save(update_fields=['approval_status'])

        # Notify user
        msg_action = "approved and activated" if action in ['approve', 'activate'] else f"{action}ed"
        Notification.send(
            recipient=target_user,
            title=f"Account Status Updated: {new_status}",
            message=f"Your ProcureHub enterprise account has been {msg_action} by the administrator.",
            notification_type=NotificationType.SUCCESS if new_status == ApprovalStatus.APPROVED else NotificationType.WARNING,
            link='/portal/customer/dashboard/' if target_user.is_customer else '/portal/supplier/dashboard/'
        )

        ActivityLog.log(
            user=request.user,
            action=f"ADMIN_{action.upper()}_USER",
            description=f"Admin {action}ed user {target_user.email} ({target_user.company_name}). Status: {new_status}",
            object_repr=target_user.email,
            request=request
        )
        messages.success(request, f"User {target_user.email} status updated to: {new_status}")

    redirect_url = 'admin_portal:suppliers' if target_user.is_supplier else 'admin_portal:customers'
    return redirect(redirect_url)


@login_required
@role_required([UserRole.ADMIN])
def admin_rfqs_view(request):
    rfqs = RFQ.objects.select_related('customer', 'category').prefetch_related('quotations').order_by('-created_at')
    return render(request, 'admin/rfqs_list.html', {
        'active_nav': 'admin_rfqs',
        'rfqs': rfqs,
    })


@login_required
@role_required([UserRole.ADMIN])
def admin_rfq_toggle_status_view(request, rfq_id, new_status):
    rfq = get_object_or_404(RFQ, id=rfq_id)
    if new_status in dict(RFQStatus.choices):
        rfq.status = new_status
        rfq.save(update_fields=['status'])
        ActivityLog.log(
            user=request.user,
            action='ADMIN_CHANGE_RFQ_STATUS',
            description=f"Admin set RFQ {rfq.rfq_number} status to {new_status}",
            object_repr=rfq.rfq_number,
            request=request
        )
        messages.success(request, f"RFQ {rfq.rfq_number} status set to: {rfq.get_status_display()}")
    return redirect('admin_portal:rfqs')


@login_required
@role_required([UserRole.ADMIN])
def admin_quotations_view(request):
    quotations = Quotation.objects.select_related('rfq', 'supplier').order_by('-created_at')
    return render(request, 'admin/quotations_list.html', {
        'active_nav': 'admin_quotations',
        'quotations': quotations,
    })


@login_required
@role_required([UserRole.ADMIN])
def admin_orders_view(request):
    orders = PurchaseOrder.objects.select_related('rfq', 'customer', 'supplier', 'payment').order_by('-created_at')
    return render(request, 'admin/orders_list.html', {
        'active_nav': 'admin_orders',
        'orders': orders,
    })


@login_required
@role_required([UserRole.ADMIN])
def admin_payments_view(request):
    payments = Payment.objects.select_related('po', 'po__customer', 'po__supplier').prefetch_related('installments').order_by('-created_at')
    return render(request, 'admin/payments_list.html', {
        'active_nav': 'admin_payments',
        'payments': payments,
    })


@login_required
@role_required([UserRole.ADMIN])
def admin_audit_logs_view(request):
    logs = ActivityLog.objects.select_related('user').order_by('-timestamp')[:100]
    return render(request, 'admin/audit_logs.html', {
        'active_nav': 'admin_audit',
        'logs': logs,
    })
