import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.utils import timezone
from apps.procurement.models import PurchaseOrder


def round_dec(val):
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class PaymentPlanType(models.TextChoices):
    FULL = 'FULL', '100% Full Payment'
    ADVANCE_BALANCE = 'ADVANCE_BALANCE', 'Advance (40%) + Delivery Balance (60%)'
    INSTALLMENTS = 'INSTALLMENTS', '3 Structured Installments (33% / 33% / 34%)'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Payment'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
    PAID = 'PAID', 'Fully Paid'
    FAILED = 'FAILED', 'Payment Failed'
    REFUNDED = 'REFUNDED', 'Refunded'


class Payment(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    po = models.OneToOneField(PurchaseOrder, on_delete=models.CASCADE, related_name='payment')
    payment_plan = models.CharField(
        max_length=30,
        choices=PaymentPlanType.choices,
        default=PaymentPlanType.ADVANCE_BALANCE
    )
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default="AED")
    status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment for {self.po.po_number}: {self.currency} {self.amount_paid:,.2f} / {self.total_amount:,.2f} ({self.status})"

    def recalculate_status(self):
        paid_sum = sum((inst.amount for inst in self.installments.filter(is_paid=True)), Decimal('0.00'))
        self.amount_paid = round_dec(paid_sum)
        if self.amount_paid >= self.total_amount and self.total_amount > Decimal('0.00'):
            self.status = PaymentStatus.PAID
        elif self.amount_paid > Decimal('0.00'):
            self.status = PaymentStatus.PARTIALLY_PAID
        else:
            self.status = PaymentStatus.PENDING
        self.save(update_fields=['amount_paid', 'status', 'updated_at'])

    @property
    def remaining_balance(self):
        return max(Decimal('0.00'), round_dec(self.total_amount - self.amount_paid))

    @property
    def is_fully_paid(self):
        return self.status == PaymentStatus.PAID


class PaymentInstallment(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='installments')
    installment_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=120)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction_reference = models.CharField(max_length=64, blank=True)
    gateway_provider = models.CharField(max_length=50, default='Mock Telr/Stripe UAE Service')

    class Meta:
        ordering = ['installment_number']

    def __str__(self):
        status_text = "PAID" if self.is_paid else "PENDING"
        return f"{self.title} - {self.payment.currency} {self.amount:,.2f} [{status_text}]"
