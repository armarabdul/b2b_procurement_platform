from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from apps.rfqs.models import RFQ, RFQStatus
from apps.quotations.models import Quotation, QuotationStatus
from .models import QuotationEvaluation, RFQAward, PurchaseOrder, PurchaseOrderItem, POStatus
from apps.notifications.models import Notification, NotificationType
from apps.audit.models import ActivityLog


def round_dec(val):
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def evaluate_rfq_quotations(rfq):
    """
    Evaluates all eligible quotations for an RFQ across 4 dimensions:
    - Price Score (Weight 40%)
    - Delivery Speed Score (Weight 25%)
    - Supplier Rating Score (Weight 20%)
    - Payment Terms Score (Weight 15%)
    """
    quotes = list(rfq.quotations.filter(
        status__in=[
            QuotationStatus.SUBMITTED,
            QuotationStatus.UNDER_REVIEW,
            QuotationStatus.SHORTLISTED,
            QuotationStatus.ACCEPTED
        ]
    ))
    if not quotes:
        return []

    min_price = min(q.grand_total for q in quotes if q.grand_total > Decimal('0.00')) or Decimal('1.00')
    min_delivery = min(q.delivery_days for q in quotes if q.delivery_days > 0) or 1

    evaluations = []
    best_quote = None
    highest_score = Decimal('-1.00')

    for q in quotes:
        # 1. Price Score: Relative to the lowest price
        if q.grand_total > 0:
            price_score = min(Decimal('100.00'), round_dec((min_price / q.grand_total) * Decimal('100.00')))
        else:
            price_score = Decimal('0.00')

        # 2. Delivery Speed Score: Relative to the fastest delivery
        if q.delivery_days > 0:
            delivery_score = min(Decimal('100.00'), round_dec((Decimal(min_delivery) / Decimal(q.delivery_days)) * Decimal('100.00')))
        else:
            delivery_score = Decimal('50.00')

        # 3. Supplier Rating Score
        supplier_profile = getattr(q.supplier, 'supplier_profile', None)
        if supplier_profile and supplier_profile.supplier_rating:
            rating_score = round_dec((Decimal(str(supplier_profile.supplier_rating)) / Decimal('5.00')) * Decimal('100.00'))
        else:
            rating_score = Decimal('80.00')

        # 4. Payment Terms Score
        terms_lower = (q.payment_terms or '').lower()
        if '60' in terms_lower or '90' in terms_lower:
            terms_score = Decimal('100.00')
        elif '30' in terms_lower or 'net 30' in terms_lower:
            terms_score = Decimal('85.00')
        elif '50%' in terms_lower or 'balance' in terms_lower:
            terms_score = Decimal('65.00')
        elif 'advance' in terms_lower or '100%' in terms_lower:
            terms_score = Decimal('35.00')
        else:
            terms_score = Decimal('70.00')

        # Weighted Overall Score: 40% Price + 25% Delivery + 20% Rating + 15% Terms
        overall = (
            (price_score * Decimal('0.40')) +
            (delivery_score * Decimal('0.25')) +
            (rating_score * Decimal('0.20')) +
            (terms_score * Decimal('0.15'))
        )
        overall = round_dec(overall)

        evaluation, _ = QuotationEvaluation.objects.get_or_create(quotation=q)
        evaluation.price_score = price_score
        evaluation.delivery_score = delivery_score
        evaluation.supplier_rating_score = rating_score
        evaluation.payment_terms_score = terms_score
        evaluation.overall_score = overall
        evaluation.is_recommended = False
        evaluation.save()

        evaluations.append(evaluation)

        if overall > highest_score:
            highest_score = overall
            best_quote = q

    # Mark the highest composite score as recommended
    if best_quote:
        best_eval = QuotationEvaluation.objects.get(quotation=best_quote)
        best_eval.is_recommended = True
        best_eval.recommendation_rationale = (
            f"Highest overall score ({highest_score} pts) balancing competitive AED {best_quote.grand_total:,.2f} "
            f"pricing, {best_quote.delivery_days}-day delivery lead time, and favorable commercial terms."
        )
        best_eval.save()

    return evaluations


@transaction.atomic
def award_quotation(quotation, awarded_by_user, justification="", request=None):
    """
    Executes the formal quotation award workflow:
    1. Sets winning quotation to ACCEPTED
    2. Sets competing quotations to REJECTED
    3. Sets RFQ to AWARDED
    4. Records RFQAward
    5. Automatically generates the official Purchase Order
    6. Dispatches notifications to buyer and all quoting suppliers
    7. Creates audit log
    """
    rfq = quotation.rfq

    if rfq.status == RFQStatus.AWARDED and hasattr(rfq, 'award'):
        raise ValueError("This RFQ has already been awarded.")

    # 1. Update winning quotation
    quotation.status = QuotationStatus.ACCEPTED
    quotation.save(update_fields=['status'])

    # 2. Reject other quotations
    other_quotes = rfq.quotations.exclude(id=quotation.id)
    other_quotes.update(status=QuotationStatus.REJECTED)

    # 3. Update RFQ status
    rfq.status = RFQStatus.AWARDED
    rfq.save(update_fields=['status'])

    # 4. Create Award record
    award = RFQAward.objects.create(
        rfq=rfq,
        awarded_quotation=quotation,
        awarded_by=awarded_by_user,
        justification=justification or f"Selected as best technical and commercial quotation under {quotation.quotation_number}."
    )

    # 5. Generate Purchase Order
    expected_delivery = None
    if quotation.delivery_days:
        expected_delivery = timezone.now().date() + timezone.timedelta(days=quotation.delivery_days)

    customer_profile = getattr(rfq.customer, 'customer_profile', None)
    delivery_addr = f"{rfq.delivery_location}, {rfq.get_emirate_display()}, UAE"
    if customer_profile and customer_profile.office_address:
        delivery_addr += f"\nBilling: {customer_profile.office_address}"

    po = PurchaseOrder.objects.create(
        rfq=rfq,
        quotation=quotation,
        customer=rfq.customer,
        supplier=quotation.supplier,
        currency=quotation.currency,
        subtotal=quotation.subtotal,
        tax_amount=quotation.tax_amount,
        discount_amount=quotation.discount_amount,
        total_amount=quotation.grand_total,
        delivery_address=delivery_addr,
        expected_delivery_date=expected_delivery,
        payment_terms=quotation.payment_terms,
        status=POStatus.CONFIRMED,
        special_instructions=f"Delivery as per quotation {quotation.quotation_number}. Reference RFQ {rfq.rfq_number}."
    )

    # Create PO items from quotation items
    for item in quotation.items.all():
        PurchaseOrderItem.objects.create(
            po=po,
            item_name=item.rfq_item.item_name,
            quantity=item.quantity,
            unit=item.rfq_item.unit,
            unit_price=item.unit_price,
            tax_rate=item.tax_rate,
            line_total=item.line_total
        )

    # 6. Notifications
    # To Winning Supplier
    Notification.send(
        recipient=quotation.supplier,
        title=f"Congratulations! Quotation Awarded ({rfq.rfq_number})",
        message=(
            f"Your quotation {quotation.quotation_number} for AED {quotation.grand_total:,.2f} has been accepted "
            f"by {rfq.customer.company_name or rfq.customer.username}. Purchase Order {po.po_number} has been generated."
        ),
        notification_type=NotificationType.AWARD,
        link=f"/portal/supplier/orders/{po.id}/"
    )

    # To Losing Suppliers
    for other_q in other_quotes:
        Notification.send(
            recipient=other_q.supplier,
            title=f"Quotation Status Update ({rfq.rfq_number})",
            message=(
                f"Thank you for submitting quotation {other_q.quotation_number} for '{rfq.title}'. "
                f"The buyer has selected another proposal for this procurement requirement."
            ),
            notification_type=NotificationType.INFO,
            link=f"/portal/supplier/rfqs/{rfq.id}/"
        )

    # To Buyer
    Notification.send(
        recipient=rfq.customer,
        title=f"RFQ Awarded & PO Created ({rfq.rfq_number})",
        message=(
            f"Successfully awarded to {quotation.supplier.company_name or quotation.supplier.username}. "
            f"Purchase Order {po.po_number} is ready for review and payment scheduling."
        ),
        notification_type=NotificationType.PO,
        link=f"/portal/customer/orders/{po.id}/"
    )

    # 7. Audit Log
    ActivityLog.log(
        user=awarded_by_user,
        action='AWARD_QUOTATION',
        description=(
            f"Awarded RFQ {rfq.rfq_number} to {quotation.supplier.company_name} "
            f"(Quotation: {quotation.quotation_number}, Grand Total: {quotation.currency} {quotation.grand_total:,.2f}). "
            f"Generated PO {po.po_number}."
        ),
        object_repr=po.po_number,
        request=request
    )

    return award, po
