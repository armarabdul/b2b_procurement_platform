from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from apps.accounts.permissions import role_required, approved_required
from apps.accounts.models import UserRole
from apps.rfqs.models import RFQ, RFQItem, RFQStatus, Category
from apps.quotations.models import Quotation, QuotationStatus
from apps.procurement.models import PurchaseOrder, POStatus
from apps.procurement.services import evaluate_rfq_quotations, award_quotation
from apps.payments.models import PaymentPlanType, PaymentStatus
from apps.payments.services import get_payment_service
from apps.audit.models import ActivityLog


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def customer_dashboard_view(request):
    buyer = request.user
    rfqs = buyer.rfqs.all()

    active_rfqs_count = rfqs.filter(status__in=[RFQStatus.PUBLISHED, RFQStatus.QUOTATIONS_RECEIVED, RFQStatus.UNDER_REVIEW]).count()
    draft_rfqs_count = rfqs.filter(status=RFQStatus.DRAFT).count()
    awarded_rfqs_count = rfqs.filter(status=RFQStatus.AWARDED).count()

    # Total quotations across all buyer RFQs requiring review
    quotes_received_count = Quotation.objects.filter(
        rfq__customer=buyer,
        status__in=[QuotationStatus.SUBMITTED, QuotationStatus.UNDER_REVIEW]
    ).count()

    orders = buyer.customer_orders.all()
    active_orders_count = orders.filter(status__in=[POStatus.PENDING, POStatus.CONFIRMED, POStatus.PROCESSING, POStatus.SHIPPED]).count()

    # Total procurement spend
    total_spend = sum((po.total_amount for po in orders), Decimal('0.00'))

    # Pending payments
    pending_payments_count = sum(1 for po in orders if hasattr(po, 'payment') and po.payment.status != PaymentStatus.PAID)

    recent_rfqs = rfqs[:5]
    recent_orders = orders[:5]

    context = {
        'active_nav': 'customer_dashboard',
        'stats': {
            'active_rfqs': active_rfqs_count,
            'draft_rfqs': draft_rfqs_count,
            'awarded_rfqs': awarded_rfqs_count,
            'quotes_received': quotes_received_count,
            'active_orders': active_orders_count,
            'pending_payments': pending_payments_count,
            'total_spend': total_spend,
        },
        'recent_rfqs': recent_rfqs,
        'recent_orders': recent_orders,
    }
    return render(request, 'customer/dashboard.html', context)


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def rfq_list_view(request):
    buyer = request.user
    status_filter = request.GET.get('status', '')
    rfqs = buyer.rfqs.all()

    if status_filter:
        rfqs = rfqs.filter(status=status_filter)

    return render(request, 'customer/rfq_list.html', {
        'active_nav': 'customer_rfqs',
        'rfqs': rfqs,
        'selected_status': status_filter,
        'status_choices': RFQStatus.choices,
    })


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def rfq_create_view(request):
    categories = Category.objects.all()

    if request.method == 'POST':
        title = request.POST.get('title')
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        delivery_location = request.POST.get('delivery_location')
        emirate = request.POST.get('emirate', 'DUBAI')
        delivery_deadline = request.POST.get('delivery_deadline')
        submission_deadline = request.POST.get('submission_deadline')
        preferred_terms = request.POST.get('preferred_terms', 'Net 30 Days')
        estimated_budget = request.POST.get('estimated_budget') or None
        action = request.POST.get('action', 'publish')  # 'draft' or 'publish'

        item_names = request.POST.getlist('item_name[]')
        item_quantities = request.POST.getlist('item_quantity[]')
        item_units = request.POST.getlist('item_unit[]')
        item_specs = request.POST.getlist('item_specs[]')
        item_brands = request.POST.getlist('item_brand[]')

        if not title or not category_id or not delivery_location or not submission_deadline or not item_names:
            messages.error(request, "Please fill in all required fields and provide at least one requirement item.")
            return render(request, 'customer/rfq_form.html', {'categories': categories})

        category = get_object_or_404(Category, id=category_id)

        with transaction.atomic():
            rfq = RFQ.objects.create(
                customer=request.user,
                title=title,
                category=category,
                description=description,
                delivery_location=delivery_location,
                emirate=emirate,
                delivery_deadline=delivery_deadline,
                submission_deadline=submission_deadline,
                preferred_terms=preferred_terms,
                estimated_budget=Decimal(str(estimated_budget)) if estimated_budget else None,
                status=RFQStatus.PUBLISHED if action == 'publish' else RFQStatus.DRAFT
            )

            for i in range(len(item_names)):
                name = item_names[i].strip()
                if not name:
                    continue
                qty = item_quantities[i] if i < len(item_quantities) and item_quantities[i] else '1'
                unit = item_units[i] if i < len(item_units) and item_units[i] else 'Pcs'
                spec = item_specs[i] if i < len(item_specs) else ''
                brand = item_brands[i] if i < len(item_brands) else ''

                RFQItem.objects.create(
                    rfq=rfq,
                    item_name=name,
                    quantity=Decimal(str(qty)),
                    unit=unit,
                    specifications=spec,
                    preferred_brand=brand
                )

            ActivityLog.log(
                user=request.user,
                action='CREATE_RFQ',
                description=f"Created procurement requirement: {rfq.rfq_number} - '{rfq.title}' (Status: {rfq.status})",
                object_repr=rfq.rfq_number,
                request=request
            )

        messages.success(
            request,
            f"RFQ {rfq.rfq_number} has been {'published to approved UAE suppliers' if rfq.status == RFQStatus.PUBLISHED else 'saved as draft'}!"
        )
        return redirect('customer_portal:rfq_detail', rfq_id=rfq.id)

    return render(request, 'customer/rfq_form.html', {
        'categories': categories,
        'active_nav': 'customer_rfqs',
    })


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def rfq_detail_view(request, rfq_id):
    rfq = get_object_or_404(RFQ, id=rfq_id)
    if not request.user.is_admin_user and rfq.customer != request.user:
        messages.error(request, "Access denied.")
        return redirect('customer_portal:rfq_list')

    # Evaluate any submitted quotations for comparison preview
    evaluate_rfq_quotations(rfq)
    quotations = rfq.quotations.all()

    return render(request, 'customer/rfq_detail.html', {
        'rfq': rfq,
        'quotations': quotations,
        'active_nav': 'customer_rfqs',
    })


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def rfq_publish_view(request, rfq_id):
    rfq = get_object_or_404(RFQ, id=rfq_id, customer=request.user)
    if rfq.status == RFQStatus.DRAFT:
        rfq.status = RFQStatus.PUBLISHED
        rfq.save(update_fields=['status'])
        ActivityLog.log(
            user=request.user,
            action='PUBLISH_RFQ',
            description=f"Published RFQ {rfq.rfq_number} to marketplace",
            object_repr=rfq.rfq_number,
            request=request
        )
        messages.success(request, f"RFQ {rfq.rfq_number} is now published and open for quotations.")
    return redirect('customer_portal:rfq_detail', rfq_id=rfq.id)


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def quotation_comparison_view(request, rfq_id):
    """
    FLAGSHIP QUOTATION COMPARISON MATRIX:
    Displays all submitted quotes side-by-side, runs the 4-factor scoring algorithm,
    allows sorting, and facilitates quotation award.
    """
    rfq = get_object_or_404(RFQ, id=rfq_id)
    if not request.user.is_admin_user and rfq.customer != request.user:
        messages.error(request, "Access denied.")
        return redirect('customer_portal:rfq_list')

    # Run multi-criteria scoring
    evaluate_rfq_quotations(rfq)

    # Fetch submitted quotes with evaluations
    quotes = list(rfq.quotations.filter(
        status__in=[
            QuotationStatus.SUBMITTED,
            QuotationStatus.UNDER_REVIEW,
            QuotationStatus.SHORTLISTED,
            QuotationStatus.ACCEPTED,
            QuotationStatus.REJECTED
        ]
    ).select_related('supplier', 'supplier__supplier_profile', 'evaluation'))

    sort_by = request.GET.get('sort', 'overall_score')

    if sort_by == 'price_asc':
        quotes.sort(key=lambda q: q.grand_total)
    elif sort_by == 'delivery_asc':
        quotes.sort(key=lambda q: q.delivery_days)
    elif sort_by == 'rating_desc':
        quotes.sort(key=lambda q: getattr(q.supplier.supplier_profile, 'supplier_rating', Decimal('0.00')), reverse=True)
    else:  # default: highest overall score
        quotes.sort(key=lambda q: getattr(q.evaluation, 'overall_score', Decimal('0.00')), reverse=True)

    recommended_quote = next((q for q in quotes if hasattr(q, 'evaluation') and q.evaluation.is_recommended), None)

    return render(request, 'customer/quotation_comparison.html', {
        'rfq': rfq,
        'quotes': quotes,
        'recommended_quote': recommended_quote,
        'current_sort': sort_by,
        'active_nav': 'customer_rfqs',
    })


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def award_quotation_action_view(request, quotation_id):
    if request.method != 'POST':
        return redirect('customer_portal:rfq_list')

    quotation = get_object_or_404(Quotation, id=quotation_id)
    rfq = quotation.rfq

    if not request.user.is_admin_user and rfq.customer != request.user:
        messages.error(request, "Access denied.")
        return redirect('customer_portal:rfq_list')

    justification = request.POST.get('justification', '')

    try:
        award, po = award_quotation(
            quotation=quotation,
            awarded_by_user=request.user,
            justification=justification,
            request=request
        )

        # Setup initial payment plan automatically (Advance + Balance 40/60 default)
        payment_service = get_payment_service()
        payment_service.setup_payment_plan(po, PaymentPlanType.ADVANCE_BALANCE)

        messages.success(
            request,
            f"Quotation {quotation.quotation_number} awarded to {quotation.supplier.company_name or quotation.supplier.username}! "
            f"Purchase Order {po.po_number} has been created."
        )
        return redirect('customer_portal:po_detail', po_id=po.id)

    except ValueError as e:
        messages.error(request, str(e))
        return redirect('customer_portal:quotation_comparison', rfq_id=rfq.id)


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def customer_orders_list_view(request):
    buyer = request.user
    orders = buyer.customer_orders.all()
    return render(request, 'customer/orders_list.html', {
        'active_nav': 'customer_orders',
        'orders': orders,
    })


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def customer_po_detail_view(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)
    if not request.user.is_admin_user and po.customer != request.user:
        messages.error(request, "Access denied.")
        return redirect('customer_portal:orders_list')

    # Ensure payment plan exists
    if not hasattr(po, 'payment'):
        payment_service = get_payment_service()
        payment_service.setup_payment_plan(po, PaymentPlanType.ADVANCE_BALANCE)

    payment = getattr(po, 'payment', None)

    return render(request, 'customer/po_detail.html', {
        'active_nav': 'customer_orders',
        'po': po,
        'payment': payment,
        'plan_choices': PaymentPlanType.choices,
    })


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def update_payment_plan_view(request, po_id):
    if request.method != 'POST':
        return redirect('customer_portal:po_detail', po_id=po_id)

    po = get_object_or_404(PurchaseOrder, id=po_id, customer=request.user)
    plan_type = request.POST.get('payment_plan', PaymentPlanType.ADVANCE_BALANCE)

    payment_service = get_payment_service()
    payment_service.setup_payment_plan(po, plan_type)

    messages.success(request, f"Payment plan updated to: {dict(PaymentPlanType.choices).get(plan_type)}")
    return redirect('customer_portal:po_detail', po_id=po.id)


@login_required
@role_required([UserRole.CUSTOMER, UserRole.ADMIN])
@approved_required
def simulate_installment_payment_view(request, installment_id):
    """
    Simulates payment execution for a mock installment.
    """
    if request.method != 'POST':
        return redirect('customer_portal:orders_list')

    from apps.payments.models import PaymentInstallment
    installment = get_object_or_404(PaymentInstallment, id=installment_id)
    po = installment.payment.po

    if not request.user.is_admin_user and po.customer != request.user:
        messages.error(request, "Access denied.")
        return redirect('customer_portal:orders_list')

    payment_service = get_payment_service()
    payment_service.process_installment_payment(installment, payer_user=request.user, request=request)

    messages.success(
        request,
        f"DEMO PAYMENT SUCCESSFUL: AED {installment.amount:,.2f} transferred via UAE Mock Sandbox. Ref: {installment.transaction_reference}."
    )
    return redirect('customer_portal:po_detail', po_id=po.id)
