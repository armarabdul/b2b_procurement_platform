import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.rfqs.models import RFQ, RFQItem


def round_currency(val):
    if val is None:
        return Decimal('0.00')
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class QuotationStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    SHORTLISTED = 'SHORTLISTED', 'Shortlisted'
    ACCEPTED = 'ACCEPTED', 'Accepted (Awarded)'
    REJECTED = 'REJECTED', 'Rejected'
    EXPIRED = 'EXPIRED', 'Expired'
    WITHDRAWN = 'WITHDRAWN', 'Withdrawn'


class Quotation(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    quotation_number = models.CharField(max_length=32, unique=True, editable=False, db_index=True)
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='quotations')
    supplier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quotations'
    )
    validity_date = models.DateField(help_text="Offer valid until")
    delivery_days = models.PositiveIntegerField(default=7, help_text="Committed delivery timeframe in days")
    payment_terms = models.CharField(
        max_length=150,
        default="Net 30 Days",
        help_text="e.g. 100% Advance, Net 30, 50% Advance / 50% Delivery"
    )
    currency = models.CharField(max_length=10, default="AED")

    # Financial Summary (Strict Decimal precision)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField(
        max_length=30,
        choices=QuotationStatus.choices,
        default=QuotationStatus.DRAFT,
        db_index=True
    )
    notes = models.TextField(blank=True, help_text="Delivery conditions, warranty, commercial terms")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['grand_total', 'delivery_days', '-created_at']
        verbose_name = 'Quotation'
        verbose_name_plural = 'Quotations'
        unique_together = ('rfq', 'supplier')

    def __str__(self):
        return f"{self.quotation_number} - {self.supplier.company_name or self.supplier.username} ({self.currency} {self.grand_total:,.2f})"

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            year = timezone.now().year
            count = Quotation.objects.filter(created_at__year=year).count() + 1
            self.quotation_number = f"QUO-{year}-{count:04d}"
            while Quotation.objects.filter(quotation_number=self.quotation_number).exists():
                count += 1
                self.quotation_number = f"QUO-{year}-{count:04d}"
        super().save(*args, **kwargs)

    def calculate_totals(self):
        """
        Recalculates subtotal, taxes, discounts, and grand total from line items.
        """
        sub = Decimal('0.00')
        tax = Decimal('0.00')
        disc = Decimal('0.00')

        for item in self.items.all():
            qty = item.quantity
            price = item.unit_price
            line_sub = round_currency(qty * price)
            line_disc = round_currency(item.discount)
            taxable = max(Decimal('0.00'), line_sub - line_disc)
            line_tax = round_currency(taxable * (item.tax_rate / Decimal('100.00')))

            sub += line_sub
            disc += line_disc
            tax += line_tax

        self.subtotal = round_currency(sub)
        self.discount_amount = round_currency(disc)
        self.tax_amount = round_currency(tax)
        self.grand_total = round_currency(max(Decimal('0.00'), (self.subtotal - self.discount_amount) + self.tax_amount))
        self.save(update_fields=['subtotal', 'discount_amount', 'tax_amount', 'grand_total'])

    @property
    def is_editable(self):
        return self.status in [QuotationStatus.DRAFT, QuotationStatus.SUBMITTED] and not self.rfq.is_expired


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    rfq_item = models.ForeignKey(RFQItem, on_delete=models.CASCADE, related_name='quotation_items')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))  # UAE 5% VAT
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    remarks = models.CharField(max_length=255, blank=True, help_text="Brand model, warranty, lead time notes")

    class Meta:
        unique_together = ('quotation', 'rfq_item')

    def __str__(self):
        return f"{self.rfq_item.item_name} - {self.quantity} @ {self.unit_price}"

    def save(self, *args, **kwargs):
        qty = Decimal(str(self.quantity))
        price = Decimal(str(self.unit_price))
        sub = round_currency(qty * price)
        disc = round_currency(self.discount or Decimal('0.00'))
        taxable = max(Decimal('0.00'), sub - disc)
        tax = round_currency(taxable * (Decimal(str(self.tax_rate)) / Decimal('100.00')))
        self.line_total = round_currency(taxable + tax)
        super().save(*args, **kwargs)


class QuotationAttachment(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='quotation_attachments/')
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name
