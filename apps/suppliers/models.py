from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.customers.models import UAEEmirate


class SupplierProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='supplier_profile'
    )
    trade_license_number = models.CharField(max_length=100, help_text="UAE Commercial License / DED Number")
    trade_license_document = models.FileField(
        upload_to='trade_licenses/',
        blank=True,
        null=True,
        help_text="PDF or Image copy of UAE Trade License"
    )
    business_categories = models.CharField(
        max_length=255,
        default="Office Furniture, IT Equipment, Commercial Supplies",
        help_text="Comma-separated business capabilities"
    )
    emirate = models.CharField(max_length=50, choices=UAEEmirate.choices, default=UAEEmirate.DUBAI)
    office_address = models.TextField(help_text="Warehouse / Showroom address in UAE")
    years_in_business = models.PositiveIntegerField(default=5)
    supplier_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('4.80'),
        help_text="Supplier performance rating (1.00 - 5.00)"
    )
    completed_orders_count = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False, help_text="Verified DED/FTA supplier badge")
    tax_registration_number = models.CharField(max_length=50, blank=True, help_text="FTA TRN")
    bank_name = models.CharField(max_length=150, blank=True, default='Emirates NBD')
    iban = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.company_name or self.user.username} ({self.get_emirate_display()})"
