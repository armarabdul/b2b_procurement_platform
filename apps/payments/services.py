import uuid
from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction
from .models import Payment, PaymentInstallment, PaymentPlanType, PaymentStatus
from apps.procurement.models import PurchaseOrder, POStatus
from apps.notifications.models import Notification, NotificationType
from apps.audit.models import ActivityLog


def round_dec(val):
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class BasePaymentGatewayService(ABC):
    """
    Abstract Payment Gateway Interface.
    To integrate real UAE providers (Stripe UAE, Telr, Network International, Checkout.com),
    subclass this interface and configure it in settings.
    """

    @abstractmethod
    def setup_payment_plan(self, po: PurchaseOrder, plan_type: str) -> Payment:
        pass

    @abstractmethod
    def process_installment_payment(self, installment: PaymentInstallment, payer_user, request=None) -> bool:
        pass

    @abstractmethod
    def refund(self, payment: Payment, amount: Decimal) -> bool:
        pass


class MockPaymentGatewayService(BasePaymentGatewayService):
    """
    Demo/Mock payment gateway service simulating instantaneous AED transactions.
    Supports full payment, 40/60 advance balance, and 3-stage installment splits.
    """

    @transaction.atomic
    def setup_payment_plan(self, po: PurchaseOrder, plan_type: str) -> Payment:
        # Create or update payment record
        payment, created = Payment.objects.get_or_create(
            po=po,
            defaults={
                'total_amount': po.total_amount,
                'currency': po.currency,
                'payment_plan': plan_type,
                'status': PaymentStatus.PENDING
            }
        )
        if not created:
            payment.payment_plan = plan_type
            payment.total_amount = po.total_amount
            payment.currency = po.currency
            payment.save()
            # Clear any pending unpaid installments to regenerate according to new plan
            payment.installments.filter(is_paid=False).delete()

        # If installments already exist and are paid, keep them
        if payment.installments.exists():
            return payment

        total = po.total_amount
        today = timezone.now().date()

        if plan_type == PaymentPlanType.FULL:
            PaymentInstallment.objects.create(
                payment=payment,
                installment_number=1,
                title="100% Full Payment upon Order Confirmation",
                percentage=Decimal('100.00'),
                amount=total,
                due_date=today,
                gateway_provider="ProcureHub Mock Payment Gateway (UAE Central Bank Demo Sandbox)"
            )
        elif plan_type == PaymentPlanType.ADVANCE_BALANCE:
            advance_amount = round_dec(total * Decimal('0.40'))
            balance_amount = round_dec(total - advance_amount)
            PaymentInstallment.objects.create(
                payment=payment,
                installment_number=1,
                title="40% Mobilization / Advance Payment",
                percentage=Decimal('40.00'),
                amount=advance_amount,
                due_date=today,
                gateway_provider="ProcureHub Mock Payment Gateway (UAE Central Bank Demo Sandbox)"
            )
            PaymentInstallment.objects.create(
                payment=payment,
                installment_number=2,
                title="60% Final Balance upon Delivery & Inspection",
                percentage=Decimal('60.00'),
                amount=balance_amount,
                due_date=today + timezone.timedelta(days=14),
                gateway_provider="ProcureHub Mock Payment Gateway (UAE Central Bank Demo Sandbox)"
            )
        elif plan_type == PaymentPlanType.INSTALLMENTS:
            inst1 = round_dec(total * Decimal('0.3333'))
            inst2 = round_dec(total * Decimal('0.3333'))
            inst3 = round_dec(total - (inst1 + inst2))
            PaymentInstallment.objects.create(
                payment=payment,
                installment_number=1,
                title="Installment 1 of 3 (Contract Signing)",
                percentage=Decimal('33.33'),
                amount=inst1,
                due_date=today,
                gateway_provider="ProcureHub Mock Payment Gateway (UAE Central Bank Demo Sandbox)"
            )
            PaymentInstallment.objects.create(
                payment=payment,
                installment_number=2,
                title="Installment 2 of 3 (Dispatched from Warehouse)",
                percentage=Decimal('33.33'),
                amount=inst2,
                due_date=today + timezone.timedelta(days=10),
                gateway_provider="ProcureHub Mock Payment Gateway (UAE Central Bank Demo Sandbox)"
            )
            PaymentInstallment.objects.create(
                payment=payment,
                installment_number=3,
                title="Installment 3 of 3 (Final Handover & Acceptance)",
                percentage=Decimal('33.34'),
                amount=inst3,
                due_date=today + timezone.timedelta(days=21),
                gateway_provider="ProcureHub Mock Payment Gateway (UAE Central Bank Demo Sandbox)"
            )

        return payment

    @transaction.atomic
    def process_installment_payment(self, installment: PaymentInstallment, payer_user, request=None) -> bool:
        """
        Simulates payment completion for a specific installment.
        """
        if installment.is_paid:
            return True

        installment.is_paid = True
        installment.paid_at = timezone.now()
        installment.transaction_reference = f"MOCK-TXN-{uuid.uuid4().hex[:12].upper()}"
        installment.save()

        # Recalculate payment status
        payment = installment.payment
        payment.recalculate_status()

        # Update PO status if applicable
        po = payment.po
        if payment.status == PaymentStatus.PAID:
            po.status = POStatus.PROCESSING
            po.save(update_fields=['status'])
        elif payment.status == PaymentStatus.PARTIALLY_PAID and po.status == POStatus.PENDING:
            po.status = POStatus.CONFIRMED
            po.save(update_fields=['status'])

        # Notify supplier
        Notification.send(
            recipient=po.supplier,
            title=f"Payment Received: {installment.title} ({po.po_number})",
            message=(
                f"A mock payment of AED {installment.amount:,.2f} was released by {po.customer.company_name} "
                f"under PO {po.po_number}. Ref: {installment.transaction_reference}."
            ),
            notification_type=NotificationType.PAYMENT,
            link=f"/portal/supplier/orders/{po.id}/"
        )

        # Notify buyer
        Notification.send(
            recipient=po.customer,
            title=f"Payment Simulated: {installment.title}",
            message=(
                f"Successfully simulated payment of AED {installment.amount:,.2f} for PO {po.po_number}. "
                f"Transaction Ref: {installment.transaction_reference}."
            ),
            notification_type=NotificationType.PAYMENT,
            link=f"/portal/customer/orders/{po.id}/"
        )

        # Audit Log
        ActivityLog.log(
            user=payer_user,
            action='SIMULATE_PAYMENT',
            description=(
                f"Simulated {installment.title} of AED {installment.amount:,.2f} for PO {po.po_number} "
                f"(Txn: {installment.transaction_reference}). New payment status: {payment.status}."
            ),
            object_repr=installment.transaction_reference,
            request=request
        )

        return True

    def refund(self, payment: Payment, amount: Decimal) -> bool:
        payment.status = PaymentStatus.REFUNDED
        payment.save(update_fields=['status'])
        return True


# Factory to get active gateway service instance
def get_payment_service() -> BasePaymentGatewayService:
    return MockPaymentGatewayService()
