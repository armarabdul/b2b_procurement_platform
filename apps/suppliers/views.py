from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from apps.accounts.permissions import role_required, approved_required
from apps.accounts.models import UserRole
from apps.rfqs.models import RFQ, RFQItem, RFQStatus, Category
from apps.quotations.models import Quotation, QuotationItem, QuotationStatus, round_currency
from apps.procurement.models import PurchaseOrder, POStatus
from apps.customers.models import UAEEmirate
from apps.notifications.models import Notification, NotificationType
from apps.audit.models import ActivityLog


@login_required
@role_required([UserRole.SUPPLIER, UserRole.ADMIN])
@approved_required
def supplier_dashboard_view(request):
    vendor = request.user

    # Available published RFQs
    available_rfqs_count = RFQ.objects.filter(
        status__in=[RFQStatus.PUBLISHED, RFQStatus.QUOTATIONS_RECEIVED],
        submission_deadline__gte=timezone.now()
    ).count()

    my_quotes = vendor.quotations.all()
    submitted_quotes_count = my_quotes.filter(status__in=[QuotationStatus.SUBMITTED, QuotationStatus.UNDER_REVIEW]).count()
    awarded_quotes_count = my_quotes.filter(status=QuotationStatus.ACCEPTED).count()
    rejected_quotes_count = my_quotes.filter(status=QuotationStatus.REJECTED).count()

    my_orders = vendor.supplier_orders.all()
    active_orders_count = my_orders.filter(status__in=[POStatus.CONFIRMED, POStatus.PROCESSING, POStatus.SHIPPED]).count()

    # Total won contract value
    awarded_revenue = sum((po.total_amount for po in my_orders), Decimal('0.00'))

    recent_opportunities = RFQ.objects.filter(
        status__in=[RFQStatus.PUBLISHED, RFQStatus.QUOTATIONS_RECEIVED],
        submission_deadline__gte=timezone.now()
    ).select_related('category', 'customer')[:4]

    recent_orders = my_orders[:5]

    context = {
        'active_nav': 'supplier_dashboard',
        'stats': {
            'available_rfqs': available_rfqs_count,
            'submitted_quotes': submitted_quotes_count,
            'awarded_quotes': awarded_quotes_count,
            'rejected_quotes': rejected_quotes_count,
            'active_orders': active_orders_count,
            'awarded_revenue': awarded_revenue,
        },
        'recent_opportunities': recent_opportunities,
        'recent_orders': recent_orders,
    }
    return render(request, 'supplier/dashboard.html', context)


@login_required
@role_required([UserRole.SUPPLIER, UserRole.ADMIN])
@approved_required
def rfq_discovery_view(request):
    rfqs = RFQ.objects.filter(
        status__in=[RFQStatus.PUBLISHED, RFQStatus.QUOTATIONS_RECEIVED, RFQStatus.UNDER_REVIEW]
    ).select_related('category', 'customer')

    # Filters
    search_query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    emirate = request.GET.get('emirate', '')
    sort_by = request.GET.get('sort', 'newest')

    if search_query:
        rfqs = rfqs.filter(title__icontains=search_query)
    if category_id:
        rfqs = rfqs.filter(category_id=category_id)
    if emirate:
        rfqs = rfqs.filter(emirate=emirate)

    if sort_by == 'deadline':
        rfqs = rfqs.order_by('submission_deadline')
    elif sort_by == 'budget_desc':
        rfqs = rfqs.order_by('-estimated_budget')
    else:
        rfqs = rfqs.order_by('-created_at')

    categories = Category.objects.all()

    # Determine which RFQs this supplier has already quoted
    quoted_rfq_ids = set(request.user.quotations.values_list('rfq_id', flat=True))

    return render(request, 'supplier/rfq_discovery.html', {
        'active_nav': 'supplier_discovery',
        'rfqs': rfqs,
        'categories': categories,
        'emirates': UAEEmirate.choices,
        'quoted_rfq_ids': quoted_rfq_ids,
        'search_query': search_query,
        'selected_category': category_id,
        'selected_emirate': emirate,
        'selected_sort': sort_by,
    })


@login_required
@role_required([UserRole.SUPPLIER, UserRole.ADMIN])
@approved_required
def supplier_rfq_detail_view(request, rfq_id):
    rfq = get_object_or_404(RFQ, id=rfq_id)
    existing_quotation = Quotation.objects.filter(rfq=rfq, supplier=request.user).first()

    return render(request, 'supplier/rfq_detail.html', {
        'active_nav': 'supplier_discovery',
        'rfq': rfq,
        'existing_quotation': existing_quotation,
    })


@login_required
@role_required([UserRole.SUPPLIER, UserRole.ADMIN])
@approved_required
def submit_quotation_view(request, rfq_id):
    rfq = get_object_or_404(RFQ, id=rfq_id)

    if rfq.is_expired:
        messages.error(request, "Quotation submission is closed for this RFQ because the deadline has passed.")
        return redirect('supplier_portal:rfq_detail', rfq_id=rfq.id)

    if rfq.status not in [RFQStatus.PUBLISHED, RFQStatus.QUOTATIONS_RECEIVED, RFQStatus.UNDER_REVIEW]:
        messages.error(request, "This procurement requirement is no longer accepting quotations.")
        return redirect('supplier_portal:rfq_detail', rfq_id=rfq.id)

    existing_quotation = Quotation.objects.filter(rfq=rfq, supplier=request.user).first()
    if existing_quotation and not existing_quotation.is_editable:
        messages.warning(request, "Your quotation for this RFQ has already been submitted or locked.")
        return redirect('supplier_portal:my_quotations')

    if request.method == 'POST':
        validity_date = request.POST.get('validity_date')
        delivery_days = request.POST.get('delivery_days', 7)
        payment_terms = request.POST.get('payment_terms', 'Net 30 Days')
        notes = request.POST.get('notes', '')
        action = request.POST.get('action', 'submit')  # 'draft' or 'submit'

        with transaction.atomic():
            if existing_quotation:
                quotation = existing_quotation
                quotation.validity_date = validity_date
                quotation.delivery_days = int(delivery_days)
                quotation.payment_terms = payment_terms
                quotation.notes = notes
                quotation.status = QuotationStatus.SUBMITTED if action == 'submit' else QuotationStatus.DRAFT
                quotation.save()
                quotation.items.all().delete()
            else:
                quotation = Quotation.objects.create(
                    rfq=rfq,
                    supplier=request.user,
                    validity_date=validity_date,
                    delivery_days=int(delivery_days),
                    payment_terms=payment_terms,
                    notes=notes,
                    status=QuotationStatus.SUBMITTED if action == 'submit' else QuotationStatus.DRAFT
                )

            # Save line items
            for item in rfq.items.all():
                price_str = request.POST.get(f'unit_price_{item.id}', '0.00')
                disc_str = request.POST.get(f'discount_{item.id}', '0.00')
                remarks = request.POST.get(f'remarks_{item.id}', '')

                unit_price = Decimal(str(price_str or '0.00'))
                discount = Decimal(str(disc_str or '0.00'))

                QuotationItem.objects.create(
                    quotation=quotation,
                    rfq_item=item,
                    quantity=item.quantity,
                    unit_price=unit_price,
                    discount=discount,
                    tax_rate=Decimal('5.00'),  # Standard 5% UAE VAT
                    remarks=remarks
                )

            # Recalculate totals with Decimal precision
            quotation.calculate_totals()

            # Update RFQ status if first quotation received
            if rfq.status == RFQStatus.PUBLISHED and action == 'submit':
                rfq.status = RFQStatus.QUOTATIONS_RECEIVED
                rfq.save(update_fields=['status'])

            if action == 'submit':
                # Notify Buyer
                Notification.send(
                    recipient=rfq.customer,
                    title=f"New Quotation Submitted ({rfq.rfq_number})",
                    message=(
                        f"{request.user.company_name or request.user.username} submitted quotation "
                        f"{quotation.quotation_number} for AED {quotation.grand_total:,.2f}."
                    ),
                    notification_type=NotificationType.INFO,
                    link=f"/portal/customer/rfqs/{rfq.id}/compare/"
                )

            ActivityLog.log(
                user=request.user,
                action='SUBMIT_QUOTATION' if action == 'submit' else 'DRAFT_QUOTATION',
                description=(
                    f"Quotation {quotation.quotation_number} ({action}) submitted for {rfq.rfq_number}. "
                    f"Grand Total: AED {quotation.grand_total:,.2f}"
                ),
                object_repr=quotation.quotation_number,
                request=request
            )

        messages.success(
            request,
            f"Quotation {quotation.quotation_number} for AED {quotation.grand_total:,.2f} successfully "
            f"{'submitted to buyer' if action == 'submit' else 'saved as draft'}!"
        )
        return redirect('supplier_portal:my_quotations')

    return render(request, 'supplier/quotation_form.html', {
        'active_nav': 'supplier_discovery',
        'rfq': rfq,
        'existing_quotation': existing_quotation,
    })


@login_required
@role_required([UserRole.SUPPLIER, UserRole.ADMIN])
@approved_required
def my_quotations_list_view(request):
    quotations = request.user.quotations.select_related('rfq', 'rfq__customer').all()
    return render(request, 'supplier/my_quotations.html', {
        'active_nav': 'supplier_quotes',
        'quotations': quotations,
    })


@login_required
@role_required([UserRole.SUPPLIER, UserRole.ADMIN])
@approved_required
def supplier_orders_list_view(request):
    orders = request.user.supplier_orders.select_related('rfq', 'customer').all()
    return render(request, 'supplier/orders_list.html', {
        'active_nav': 'supplier_orders',
        'orders': orders,
    })


@login_required
@role_required([UserRole.SUPPLIER, UserRole.ADMIN])
@approved_required
def supplier_po_detail_view(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)
    if not request.user.is_admin_user and po.supplier != request.user:
        messages.error(request, "Access denied.")
        return redirect('supplier_portal:orders_list')

    payment = getattr(po, 'payment', None)

    return render(request, 'supplier/po_detail.html', {
        'active_nav': 'supplier_orders',
        'po': po,
        'payment': payment,
        'status_choices': POStatus.choices,
    })


@login_required
@role_required([UserRole.SUPPLIER, UserRole.ADMIN])
@approved_required
def update_order_status_view(request, po_id):
    if request.method != 'POST':
        return redirect('supplier_portal:supplier_po_detail', po_id=po_id)

    po = get_object_or_404(PurchaseOrder, id=po_id, supplier=request.user)
    new_status = request.POST.get('status')

    if new_status in dict(POStatus.choices):
        po.status = new_status
        po.save(update_fields=['status'])

        # Notify buyer
        Notification.send(
            recipient=po.customer,
            title=f"Order Status Updated: {po.get_status_display()}",
            message=f"Purchase Order {po.po_number} status was updated to '{po.get_status_display()}' by {request.user.company_name}.",
            notification_type=NotificationType.INFO,
            link=f"/portal/customer/orders/{po.id}/"
        )

        ActivityLog.log(
            user=request.user,
            action='UPDATE_ORDER_STATUS',
            description=f"Updated PO {po.po_number} status to {new_status}",
            object_repr=po.po_number,
            request=request
        )

        messages.success(request, f"Order status updated to: {po.get_status_display()}")

    return redirect('supplier_portal:supplier_po_detail', po_id=po.id)
