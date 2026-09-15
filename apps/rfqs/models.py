import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from apps.customers.models import UAEEmirate


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    icon = models.CharField(max_length=50, default='box', help_text="Lucide icon name")
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class RFQStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    QUOTATIONS_RECEIVED = 'QUOTATIONS_RECEIVED', 'Quotations Received'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    AWARDED = 'AWARDED', 'Awarded'
    ORDER_CREATED = 'ORDER_CREATED', 'Order Created'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    EXPIRED = 'EXPIRED', 'Expired'


class RFQ(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    rfq_number = models.CharField(max_length=32, unique=True, editable=False, db_index=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rfqs'
    )
    title = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='rfqs')
    description = models.TextField()

    # UAE Logistics & Timelines
    delivery_location = models.CharField(max_length=255, help_text="Site / Office address (e.g. Dubai Internet City, Bldg 3)")
    emirate = models.CharField(max_length=50, choices=UAEEmirate.choices, default=UAEEmirate.DUBAI)
    delivery_deadline = models.DateField(help_text="Expected delivery date")
    submission_deadline = models.DateTimeField(help_text="Final timestamp to submit quotations")

    status = models.CharField(
        max_length=30,
        choices=RFQStatus.choices,
        default=RFQStatus.DRAFT,
        db_index=True
    )
    preferred_terms = models.CharField(max_length=150, blank=True, default="Net 30 Days")
    estimated_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target procurement budget in AED"
    )
    additional_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'RFQ'
        verbose_name_plural = 'RFQs'

    def __str__(self):
        return f"{self.rfq_number} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.rfq_number:
            year = timezone.now().year
            count = RFQ.objects.filter(created_at__year=year).count() + 1
            self.rfq_number = f"RFQ-{year}-{count:04d}"
            # Ensure uniqueness in case of race condition
            while RFQ.objects.filter(rfq_number=self.rfq_number).exists():
                count += 1
                self.rfq_number = f"RFQ-{year}-{count:04d}"
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        if self.submission_deadline:
            return timezone.now() > self.submission_deadline
        return False

    @property
    def can_submit_quotation(self):
        return (
            self.status in [RFQStatus.PUBLISHED, RFQStatus.QUOTATIONS_RECEIVED, RFQStatus.UNDER_REVIEW]
            and not self.is_expired
        )

    @property
    def total_items_count(self):
        return self.items.count()

    @property
    def total_quotations_count(self):
        return self.quotations.filter(status__in=['SUBMITTED', 'UNDER_REVIEW', 'SHORTLISTED', 'ACCEPTED', 'REJECTED']).count()


class RFQItem(models.Model):
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    unit = models.CharField(max_length=50, default='Pcs')
    specifications = models.TextField(help_text="Technical specifications, dimensions, material, standards")
    preferred_brand = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.item_name} ({self.quantity} {self.unit})"


class RFQAttachment(models.Model):
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='rfq_attachments/')
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name
