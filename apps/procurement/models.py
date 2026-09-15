import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.rfqs.models import RFQ
from apps.quotations.models import Quotation


class POStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Confirmation'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    PROCESSING = 'PROCESSING', 'Processing'
    SHIPPED = 'SHIPPED', 'Shipped'
    DELIVERED = 'DELIVERED', 'Delivered'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class RFQAward(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    award_reference = models.CharField(max_length=32, unique=True, editable=False)
    rfq = models.OneToOneField(RFQ, on_delete=models.CASCADE, related_name='award')
    awarded_quotation = models.OneToOneField(Quotation, on_delete=models.CASCADE, related_name='award')
    awarded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='awarded_rfqs')
    awarded_at = models.DateTimeField(auto_now_add=True)
    justification = models.TextField(blank=True, help_text="Commercial / Technical evaluation notes")

    def __str__(self):
        return f"{self.award_reference} - {self.rfq.rfq_number} -> {self.awarded_quotation.supplier.company_name}"

    def save(self, *args, **kwargs):
        if not self.award_reference:
            year = timezone.now().year
            count = RFQAward.objects.filter(awarded_at__year=year).count() + 1
            self.award_reference = f"AWD-{year}-{count:04d}"
            while RFQAward.objects.filter(award_reference=self.award_reference).exists():
                count += 1
                self.award_reference = f"AWD-{year}-{count:04d}"
        super().save(*args, **kwargs)


class QuotationEvaluation(models.Model):
    quotation = models.OneToOneField(Quotation, on_delete=models.CASCADE, related_name='evaluation')
    price_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))  # 0-100
    delivery_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))  # 0-100
    supplier_rating_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))  # 0-100
    payment_terms_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))  # 0-100
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))  # 0-100
    is_recommended = models.BooleanField(default=False)
    recommendation_rationale = models.CharField(max_length=255, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Eval for {self.quotation.quotation_number}: {self.overall_score} pts"


class PurchaseOrder(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    po_number = models.CharField(max_length=32, unique=True, editable=False, db_index=True)
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='purchase_orders')
    quotation = models.OneToOneField(Quotation, on_delete=models.CASCADE, related_name='purchase_order')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='customer_orders')
    supplier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='supplier_orders')

    currency = models.CharField(max_length=10, default="AED")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)

    delivery_address = models.TextField()
    expected_delivery_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=150)
    status = models.CharField(max_length=30, choices=POStatus.choices, default=POStatus.CONFIRMED, db_index=True)
    special_instructions = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'

    def __str__(self):
        return f"{self.po_number} - {self.supplier.company_name or self.supplier.username} ({self.currency} {self.total_amount:,.2f})"

    def save(self, *args, **kwargs):
        if not self.po_number:
            year = timezone.now().year
            count = PurchaseOrder.objects.filter(created_at__year=year).count() + 1
            self.po_number = f"PO-{year}-{count:04d}"
            while PurchaseOrder.objects.filter(po_number=self.po_number).exists():
                count += 1
                self.po_number = f"PO-{year}-{count:04d}"
        super().save(*args, **kwargs)


class PurchaseOrderItem(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, default='Pcs')
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.item_name} ({self.quantity} {self.unit})"
