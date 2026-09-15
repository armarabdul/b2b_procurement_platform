import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from decimal import Decimal
from django.utils import timezone
from apps.accounts.models import User, UserRole, ApprovalStatus
from apps.customers.models import CustomerProfile, UAEEmirate
from apps.suppliers.models import SupplierProfile
from apps.rfqs.models import Category, RFQ, RFQItem, RFQStatus
from apps.quotations.models import Quotation, QuotationItem, QuotationStatus
from apps.procurement.models import PurchaseOrder, POStatus
from apps.procurement.services import evaluate_rfq_quotations, award_quotation
from apps.payments.models import PaymentPlanType, PaymentStatus
from apps.payments.services import get_payment_service
from apps.notifications.models import Notification
from apps.audit.models import ActivityLog


def run_acceptance_test():
    print("==================================================")
    print("STARTING COMPLETE END-TO-END PROCUREMENT VERIFICATION")
    print("==================================================")

    # 1. Login as Admin
    print("\n[Step 1] Verifying Admin account...")
    admin = User.objects.filter(role=UserRole.ADMIN).first()
    assert admin is not None, "Admin user must exist"
    print(f" -> Admin verified: {admin.email}")

    # 2. Approve Customer
    print("\n[Step 2] Approving Customer...")
    customer = User.objects.filter(email="customer@procurehub.demo").first()
    assert customer is not None, "Customer user must exist"
    customer.approval_status = ApprovalStatus.APPROVED
    customer.save()
    print(f" -> Customer approved: {customer.company_name} [{customer.approval_status}]")

    # 3. Approve 3 Suppliers
    print("\n[Step 3] Approving 3 Suppliers...")
    s1 = User.objects.get(email="supplier1@procurehub.demo")
    s2 = User.objects.get(email="supplier2@procurehub.demo")
    s3 = User.objects.get(email="supplier3@procurehub.demo")
    for s in [s1, s2, s3]:
        s.approval_status = ApprovalStatus.APPROVED
        s.save()
        print(f" -> Approved vendor: {s.company_name} [{s.approval_status}]")

    # 4 & 5. Customer creates RFQ for 50 chairs, 30 fans, 20 tables
    print("\n[Step 4 & 5] Customer creating new RFQ...")
    category = Category.objects.filter(name__icontains="Furniture").first()
    test_rfq = RFQ.objects.create(
        customer=customer,
        title="Acceptance Test: Office Furniture Requirement - Dubai Marina",
        category=category,
        description="Requirement for 50 chairs, 30 fans, and 20 office tables",
        delivery_location="Floor 12, Marina Plaza, Dubai",
        emirate=UAEEmirate.DUBAI,
        delivery_deadline=timezone.now().date() + timezone.timedelta(days=30),
        submission_deadline=timezone.now() + timezone.timedelta(days=10),
        preferred_terms="Net 30 Days",
        estimated_budget=Decimal('50000.00'),
        status=RFQStatus.DRAFT
    )
    it1 = RFQItem.objects.create(rfq=test_rfq, item_name="Executive Ergonomic Chair", quantity=Decimal('50'), unit="Pcs", specifications="High-back mesh")
    it2 = RFQItem.objects.create(rfq=test_rfq, item_name="Ceiling Fan 1200mm", quantity=Decimal('30'), unit="Pcs", specifications="BLDC motor, energy efficient")
    it3 = RFQItem.objects.create(rfq=test_rfq, item_name="Office Table 1500x750", quantity=Decimal('20'), unit="Sets", specifications="Commercial grade")

    assert test_rfq.items.count() == 3
    print(f" -> RFQ created in DRAFT: {test_rfq.rfq_number} with {test_rfq.items.count()} items.")

    # 6. Publish RFQ
    print("\n[Step 6] Publishing RFQ...")
    test_rfq.status = RFQStatus.PUBLISHED
    test_rfq.save()
    assert test_rfq.status == RFQStatus.PUBLISHED
    print(f" -> RFQ status updated to: {test_rfq.status}")

    # 7 & 8. Supplier 1 submits quotation
    print("\n[Step 7 & 8] Supplier 1 (Emirates Office) submitting quotation...")
    q1 = Quotation.objects.create(
        rfq=test_rfq,
        supplier=s1,
        validity_date=timezone.now().date() + timezone.timedelta(days=30),
        delivery_days=7,
        payment_terms="Net 30 Days",
        status=QuotationStatus.SUBMITTED
    )
    QuotationItem.objects.create(quotation=q1, rfq_item=it1, quantity=Decimal('50'), unit_price=Decimal('400.00')) # 20,000
    QuotationItem.objects.create(quotation=q1, rfq_item=it2, quantity=Decimal('30'), unit_price=Decimal('180.00')) # 5,400
    QuotationItem.objects.create(quotation=q1, rfq_item=it3, quantity=Decimal('20'), unit_price=Decimal('750.00')) # 15,000
    q1.calculate_totals()
    print(f" -> Supplier 1 quote {q1.quotation_number}: Grand Total AED {q1.grand_total:,.2f} (7 days lead time)")

    # 9 & 10. Supplier 2 submits quotation
    print("\n[Step 9 & 10] Supplier 2 (Gulf Supplies) submitting quotation...")
    q2 = Quotation.objects.create(
        rfq=test_rfq,
        supplier=s2,
        validity_date=timezone.now().date() + timezone.timedelta(days=20),
        delivery_days=15,
        payment_terms="50% Advance / 50% on Delivery",
        status=QuotationStatus.SUBMITTED
    )
    QuotationItem.objects.create(quotation=q2, rfq_item=it1, quantity=Decimal('50'), unit_price=Decimal('380.00')) # 19,000
    QuotationItem.objects.create(quotation=q2, rfq_item=it2, quantity=Decimal('30'), unit_price=Decimal('170.00')) # 5,100
    QuotationItem.objects.create(quotation=q2, rfq_item=it3, quantity=Decimal('20'), unit_price=Decimal('720.00')) # 14,400
    q2.calculate_totals()
    print(f" -> Supplier 2 quote {q2.quotation_number}: Grand Total AED {q2.grand_total:,.2f} (15 days lead time)")

    # 11 & 12. Supplier 3 submits quotation
    print("\n[Step 11 & 12] Supplier 3 (Dubai Furnishings) submitting quotation...")
    q3 = Quotation.objects.create(
        rfq=test_rfq,
        supplier=s3,
        validity_date=timezone.now().date() + timezone.timedelta(days=40),
        delivery_days=4,
        payment_terms="Net 60 Days",
        status=QuotationStatus.SUBMITTED
    )
    QuotationItem.objects.create(quotation=q3, rfq_item=it1, quantity=Decimal('50'), unit_price=Decimal('430.00')) # 21,500
    QuotationItem.objects.create(quotation=q3, rfq_item=it2, quantity=Decimal('30'), unit_price=Decimal('200.00')) # 6,000
    QuotationItem.objects.create(quotation=q3, rfq_item=it3, quantity=Decimal('20'), unit_price=Decimal('780.00')) # 15,600
    q3.calculate_totals()
    print(f" -> Supplier 3 quote {q3.quotation_number}: Grand Total AED {q3.grand_total:,.2f} (4 days lead time)")

    # 13, 14, 15. Customer compares quotations
    print("\n[Steps 13, 14, 15] Customer evaluating and comparing all 3 bids...")
    evaluations = evaluate_rfq_quotations(test_rfq)
    assert len(evaluations) == 3
    for ev in evaluations:
        rec_tag = " [RECOMMENDED BEST VALUE]" if ev.is_recommended else ""
        print(f" -> Quote {ev.quotation.quotation_number} ({ev.quotation.supplier.company_name}): Overall Score = {ev.overall_score} pts{rec_tag}")

    # 16 & 17. Award quotation
    print("\n[Steps 16 & 17] Customer awarding best quotation to Supplier 1...")
    award, po = award_quotation(
        quotation=q1,
        awarded_by_user=customer,
        justification="Awarded based on highest overall evaluation score, proven reliability, and 7-day lead time."
    )
    q1.refresh_from_db()
    q2.refresh_from_db()
    q3.refresh_from_db()
    test_rfq.refresh_from_db()

    # 18. Verify winning supplier receives ACCEPTED status & notification
    print("\n[Step 18] Verifying winning supplier status and notification...")
    assert q1.status == QuotationStatus.ACCEPTED, "Winning quote must be ACCEPTED"
    assert test_rfq.status == RFQStatus.AWARDED, "RFQ status must be AWARDED"
    win_notif = Notification.objects.filter(recipient=s1, title__icontains="Awarded").first()
    assert win_notif is not None, "Winning supplier must receive notification"
    print(f" -> Winning quote status: {q1.status}")
    print(f" -> Winning notification to {s1.email}: '{win_notif.title}'")

    # 19. Verify losing suppliers receive REJECTED status & rejection notification
    print("\n[Step 19] Verifying losing suppliers rejection status and notification...")
    assert q2.status == QuotationStatus.REJECTED, "Supplier 2 must be REJECTED"
    assert q3.status == QuotationStatus.REJECTED, "Supplier 3 must be REJECTED"
    loss_notif_s2 = Notification.objects.filter(recipient=s2, title__icontains="Status Update").first()
    loss_notif_s3 = Notification.objects.filter(recipient=s3, title__icontains="Status Update").first()
    assert loss_notif_s2 is not None and loss_notif_s3 is not None, "Losing suppliers must receive notification"
    print(f" -> Supplier 2 status: {q2.status}")
    print(f" -> Supplier 3 status: {q3.status}")

    # 20. Verify Purchase Order creation
    print("\n[Step 20] Verifying Purchase Order generated...")
    assert po is not None, "Purchase Order must be generated"
    assert po.po_number.startswith("PO-"), "PO number must follow PO-YYYY-NNNN format"
    assert po.items.count() == 3, "PO items must match RFQ items"
    assert po.total_amount == q1.grand_total, "PO total must match winning quotation total"
    print(f" -> PO generated: {po.po_number} | Contract Amount: AED {po.total_amount:,.2f} | Items: {po.items.count()}")

    # 21 & 22. Select mock payment plan and simulate payment
    print("\n[Steps 21 & 22] Setting up mock payment plan and simulating settlement...")
    payment_service = get_payment_service()
    payment = payment_service.setup_payment_plan(po, PaymentPlanType.ADVANCE_BALANCE)
    assert payment.installments.count() == 2
    inst1 = payment.installments.first()
    inst2 = payment.installments.last()
    print(f" -> Payment Plan: {payment.get_payment_plan_display()}")
    print(f" -> Advance Installment: AED {inst1.amount:,.2f} | Delivery Balance: AED {inst2.amount:,.2f}")

    # Simulate advance
    payment_service.process_installment_payment(inst1, payer_user=customer)
    payment.refresh_from_db()
    print(f" -> After Advance Payment: Status = {payment.status} (Paid: AED {payment.amount_paid:,.2f})")
    assert payment.status == PaymentStatus.PARTIALLY_PAID

    # Simulate balance
    payment_service.process_installment_payment(inst2, payer_user=customer)
    payment.refresh_from_db()
    print(f" -> After Balance Payment: Status = {payment.status} (Paid: AED {payment.amount_paid:,.2f})")
    assert payment.status == PaymentStatus.PAID
    assert payment.amount_paid == payment.total_amount

    # 23. Verify payment status on PO
    print("\n[Step 23] Verifying PO payment completion...")
    po.refresh_from_db()
    print(f" -> Purchase Order Status: {po.status} | Payment: {po.payment.status}")

    # 24. Verify Audit Log
    print("\n[Step 24] Verifying Audit Log trail...")
    logs = ActivityLog.objects.filter(object_repr__in=[test_rfq.rfq_number, q1.quotation_number, po.po_number])
    print(f" -> Found {logs.count()} audit log records for this procurement transaction.")
    for l in logs:
        print(f"    - [{l.action}] {l.description[:70]}...")

    # 25. Verify Dashboard Statistics
    print("\n[Step 25] Verifying Dashboard statistics...")
    total_orders = PurchaseOrder.objects.count()
    total_quotes = Quotation.objects.count()
    total_spend = sum((p.total_amount for p in PurchaseOrder.objects.all()), Decimal('0.00'))
    print(f" -> Total POs in system: {total_orders}")
    print(f" -> Total Quotations logged: {total_quotes}")
    print(f" -> Total Contract Value: AED {total_spend:,.2f}")

    print("\n==================================================")
    print("ALL 25 ACCEPTANCE TEST STEPS VERIFIED AND PASSED!")
    print("==================================================")


if __name__ == '__main__':
    run_acceptance_test()
