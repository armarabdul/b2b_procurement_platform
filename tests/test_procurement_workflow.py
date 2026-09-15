from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
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


class ProcurementWorkflowTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.password = "TestPassword123!"

        # Create Category
        self.category = Category.objects.create(
            name="IT Equipment",
            icon="server",
            description="Laptops, servers, switches"
        )

        # Create Admin
        self.admin_user = User.objects.create_user(
            username="admin@test.ae",
            email="admin@test.ae",
            password=self.password,
            role=UserRole.ADMIN,
            approval_status=ApprovalStatus.APPROVED,
            is_staff=True
        )

        # Create Approved Buyer
        self.buyer_user = User.objects.create_user(
            username="buyer@test.ae",
            email="buyer@test.ae",
            password=self.password,
            role=UserRole.CUSTOMER,
            approval_status=ApprovalStatus.APPROVED,
            company_name="Etisalat Procurement PJSC"
        )
        CustomerProfile.objects.create(
            user=self.buyer_user,
            trade_license_number="CN-112233",
            emirate=UAEEmirate.DUBAI,
            office_address="Al Kifaf Commercial Bldg, Dubai"
        )

        # Create Pending Buyer
        self.pending_buyer = User.objects.create_user(
            username="pending_buyer@test.ae",
            email="pending_buyer@test.ae",
            password=self.password,
            role=UserRole.CUSTOMER,
            approval_status=ApprovalStatus.PENDING,
            company_name="Pending Corp LLC"
        )

        # Create 2 Approved Suppliers
        self.supplier1 = User.objects.create_user(
            username="supplier1@test.ae",
            email="supplier1@test.ae",
            password=self.password,
            role=UserRole.SUPPLIER,
            approval_status=ApprovalStatus.APPROVED,
            company_name="Gulf Tech Hardware LLC"
        )
        SupplierProfile.objects.create(
            user=self.supplier1,
            trade_license_number="DED-445566",
            emirate=UAEEmirate.DUBAI,
            office_address="Al Quoz 1, Dubai",
            supplier_rating=Decimal('4.80'),
            business_categories="IT Equipment"
        )

        self.supplier2 = User.objects.create_user(
            username="supplier2@test.ae",
            email="supplier2@test.ae",
            password=self.password,
            role=UserRole.SUPPLIER,
            approval_status=ApprovalStatus.APPROVED,
            company_name="Emirates Cloud Systems FZCO"
        )
        SupplierProfile.objects.create(
            user=self.supplier2,
            trade_license_number="DED-778899",
            emirate=UAEEmirate.DUBAI,
            office_address="Silicon Oasis, Dubai",
            supplier_rating=Decimal('4.50'),
            business_categories="IT Equipment"
        )

    def test_approval_gate_prevents_unapproved_buyer(self):
        """Unapproved buyers cannot access buyer dashboard or publish RFQs."""
        self.client.login(username="pending_buyer@test.ae", password=self.password)
        resp = self.client.get(reverse('customer_portal:dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/pending-approval/', resp.url)

    def test_role_based_access_control(self):
        """Suppliers cannot access customer RFQ creation endpoints."""
        self.client.login(username="supplier1@test.ae", password=self.password)
        resp = self.client.get(reverse('customer_portal:rfq_create'))
        # RoleRequiredMixin raises PermissionDenied (403)
        self.assertEqual(resp.status_code, 403)

    def test_rfq_creation_and_line_items(self):
        """Customer creates an RFQ with multiple items."""
        rfq = RFQ.objects.create(
            customer=self.buyer_user,
            title="Enterprise Server Infrastructure",
            category=self.category,
            description="5 Server racks and 20 switches",
            delivery_location="Dubai Internet City Bldg 2",
            emirate=UAEEmirate.DUBAI,
            delivery_deadline=timezone.now().date() + timezone.timedelta(days=20),
            submission_deadline=timezone.now() + timezone.timedelta(days=7),
            status=RFQStatus.PUBLISHED,
            preferred_terms="Net 30"
        )
        item1 = RFQItem.objects.create(
            rfq=rfq,
            item_name="42U Server Rack",
            quantity=Decimal('5.00'),
            unit="Units",
            specifications="Heavy duty"
        )
        item2 = RFQItem.objects.create(
            rfq=rfq,
            item_name="48-Port Gigabit Switch",
            quantity=Decimal('20.00'),
            unit="Pcs",
            specifications="Cisco or equivalent"
        )

        self.assertEqual(rfq.items.count(), 2)
        self.assertTrue(rfq.rfq_number.startswith("RFQ-"))
        self.assertFalse(rfq.is_expired)

    def test_quotation_decimal_calculations_with_uae_vat(self):
        """Quotation math calculates subtotal, discount, 5% UAE VAT and grand total with Decimal precision."""
        rfq = RFQ.objects.create(
            customer=self.buyer_user,
            title="Network Hardware",
            category=self.category,
            description="Switches",
            delivery_location="Dubai Internet City",
            delivery_deadline=timezone.now().date() + timezone.timedelta(days=20),
            submission_deadline=timezone.now() + timezone.timedelta(days=7),
            status=RFQStatus.PUBLISHED
        )
        item = RFQItem.objects.create(
            rfq=rfq,
            item_name="Gigabit Switch",
            quantity=Decimal('10.00'),
            unit="Pcs",
            specifications="Layer 3"
        )

        quote = Quotation.objects.create(
            rfq=rfq,
            supplier=self.supplier1,
            validity_date=timezone.now().date() + timezone.timedelta(days=30),
            delivery_days=5,
            payment_terms="Net 30 Days",
            status=QuotationStatus.SUBMITTED
        )

        # 10 switches @ 1000 AED = 10,000 AED. Discount: 500 AED. Taxable: 9,500. VAT 5%: 475. Grand: 9,975.00
        QuotationItem.objects.create(
            quotation=quote,
            rfq_item=item,
            quantity=Decimal('10.00'),
            unit_price=Decimal('1000.00'),
            discount=Decimal('500.00'),
            tax_rate=Decimal('5.00')
        )
        quote.calculate_totals()

        self.assertEqual(quote.subtotal, Decimal('10000.00'))
        self.assertEqual(quote.discount_amount, Decimal('500.00'))
        self.assertEqual(quote.tax_amount, Decimal('475.00'))
        self.assertEqual(quote.grand_total, Decimal('9975.00'))

    def test_quotation_comparison_and_scoring(self):
        """Evaluation engine scores submitted quotes across price, delivery, rating, and terms."""
        rfq = RFQ.objects.create(
            customer=self.buyer_user,
            title="Office Laptops",
            category=self.category,
            description="50 Laptops",
            delivery_location="Business Bay",
            delivery_deadline=timezone.now().date() + timezone.timedelta(days=30),
            submission_deadline=timezone.now() + timezone.timedelta(days=10),
            status=RFQStatus.QUOTATIONS_RECEIVED
        )
        item = RFQItem.objects.create(
            rfq=rfq,
            item_name="Laptop Core i7",
            quantity=Decimal('10.00'),
            unit="Pcs"
        )

        q1 = Quotation.objects.create(
            rfq=rfq,
            supplier=self.supplier1,
            validity_date=timezone.now().date() + timezone.timedelta(days=30),
            delivery_days=7,
            payment_terms="Net 30 Days",
            status=QuotationStatus.SUBMITTED
        )
        QuotationItem.objects.create(quotation=q1, rfq_item=item, quantity=Decimal('10.00'), unit_price=Decimal('3500.00'), discount=Decimal('0.00'), tax_rate=Decimal('5.00'))
        q1.calculate_totals()

        q2 = Quotation.objects.create(
            rfq=rfq,
            supplier=self.supplier2,
            validity_date=timezone.now().date() + timezone.timedelta(days=30),
            delivery_days=14,
            payment_terms="100% Advance",
            status=QuotationStatus.SUBMITTED
        )
        QuotationItem.objects.create(quotation=q2, rfq_item=item, quantity=Decimal('10.00'), unit_price=Decimal('3900.00'), discount=Decimal('0.00'), tax_rate=Decimal('5.00'))
        q2.calculate_totals()

        evaluations = evaluate_rfq_quotations(rfq)
        self.assertEqual(len(evaluations), 2)

        q1.refresh_from_db()
        q2.refresh_from_db()

        # q1 has lower price, faster delivery, better rating, and Net 30 terms -> should have higher score and be recommended
        self.assertGreater(q1.evaluation.overall_score, q2.evaluation.overall_score)
        self.assertTrue(q1.evaluation.is_recommended)
        self.assertFalse(q2.evaluation.is_recommended)

    def test_award_creates_po_and_auto_rejects_competing_quotes(self):
        """Awarding a quote marks it ACCEPTED, others REJECTED, and auto-generates a Purchase Order."""
        rfq = RFQ.objects.create(
            customer=self.buyer_user,
            title="Industrial Routers",
            category=self.category,
            description="5 Routers",
            delivery_location="JAFZA Dubai",
            delivery_deadline=timezone.now().date() + timezone.timedelta(days=15),
            submission_deadline=timezone.now() + timezone.timedelta(days=5),
            status=RFQStatus.QUOTATIONS_RECEIVED
        )
        item = RFQItem.objects.create(
            rfq=rfq,
            item_name="Industrial 5G Router",
            quantity=Decimal('5.00'),
            unit="Pcs"
        )

        q1 = Quotation.objects.create(
            rfq=rfq,
            supplier=self.supplier1,
            validity_date=timezone.now().date() + timezone.timedelta(days=20),
            delivery_days=5,
            payment_terms="Net 30 Days",
            status=QuotationStatus.SUBMITTED
        )
        QuotationItem.objects.create(quotation=q1, rfq_item=item, quantity=Decimal('5.00'), unit_price=Decimal('2000.00'), discount=Decimal('0.00'), tax_rate=Decimal('5.00'))
        q1.calculate_totals()

        q2 = Quotation.objects.create(
            rfq=rfq,
            supplier=self.supplier2,
            validity_date=timezone.now().date() + timezone.timedelta(days=20),
            delivery_days=10,
            payment_terms="50% Advance",
            status=QuotationStatus.SUBMITTED
        )
        QuotationItem.objects.create(quotation=q2, rfq_item=item, quantity=Decimal('5.00'), unit_price=Decimal('2200.00'), discount=Decimal('0.00'), tax_rate=Decimal('5.00'))
        q2.calculate_totals()

        # Award q1
        award, po = award_quotation(q1, awarded_by_user=self.buyer_user, justification="Best price & delivery speed")

        q1.refresh_from_db()
        q2.refresh_from_db()
        rfq.refresh_from_db()

        # Check statuses
        self.assertEqual(rfq.status, RFQStatus.AWARDED)
        self.assertEqual(q1.status, QuotationStatus.ACCEPTED)
        self.assertEqual(q2.status, QuotationStatus.REJECTED)

        # Check PO
        self.assertEqual(po.po_number.startswith("PO-"), True)
        self.assertEqual(po.supplier, self.supplier1)
        self.assertEqual(po.customer, self.buyer_user)
        self.assertEqual(po.total_amount, q1.grand_total)
        self.assertEqual(po.items.count(), 1)

        # Check Notifications
        winning_notif = Notification.objects.filter(recipient=self.supplier1, title__icontains="Awarded").exists()
        losing_notif = Notification.objects.filter(recipient=self.supplier2, title__icontains="Status Update").exists()
        self.assertTrue(winning_notif)
        self.assertTrue(losing_notif)

    def test_mock_payment_plan_and_simulation(self):
        """Simulating payment updates payment status from PENDING to PARTIALLY_PAID then PAID."""
        rfq = RFQ.objects.create(
            customer=self.buyer_user,
            title="Fiber Optic Cables",
            category=self.category,
            description="Cabling",
            delivery_location="Dubai Silicon Oasis",
            delivery_deadline=timezone.now().date() + timezone.timedelta(days=15),
            submission_deadline=timezone.now() + timezone.timedelta(days=5),
            status=RFQStatus.QUOTATIONS_RECEIVED
        )
        item = RFQItem.objects.create(
            rfq=rfq,
            item_name="Fiber Roll 1000m",
            quantity=Decimal('2.00'),
            unit="Pcs"
        )
        q = Quotation.objects.create(
            rfq=rfq,
            supplier=self.supplier1,
            validity_date=timezone.now().date() + timezone.timedelta(days=20),
            delivery_days=5,
            payment_terms="40% Advance + 60% Balance",
            status=QuotationStatus.SUBMITTED
        )
        QuotationItem.objects.create(quotation=q, rfq_item=item, quantity=Decimal('2.00'), unit_price=Decimal('5000.00'), discount=Decimal('0.00'), tax_rate=Decimal('5.00'))
        q.calculate_totals()

        _, po = award_quotation(q, awarded_by_user=self.buyer_user)

        payment_service = get_payment_service()
        payment = payment_service.setup_payment_plan(po, PaymentPlanType.ADVANCE_BALANCE)

        self.assertEqual(payment.installments.count(), 2)
        inst1 = payment.installments.first()
        inst2 = payment.installments.last()

        # Simulate Advance Payment (40%)
        payment_service.process_installment_payment(inst1, payer_user=self.buyer_user)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PARTIALLY_PAID)

        # Simulate Balance Payment (60%)
        payment_service.process_installment_payment(inst2, payer_user=self.buyer_user)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(payment.amount_paid, payment.total_amount)
