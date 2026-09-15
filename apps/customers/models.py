from django.db import models
from django.conf import settings


class UAEEmirate(models.TextChoices):
    DUBAI = 'DUBAI', 'Dubai'
    ABU_DHABI = 'ABU_DHABI', 'Abu Dhabi'
    SHARJAH = 'SHARJAH', 'Sharjah'
    AJMAN = 'AJMAN', 'Ajman'
    UMM_AL_QUWAIN = 'UMM_AL_QUWAIN', 'Umm Al Quwain'
    RAS_AL_KHAIMAH = 'RAS_AL_KHAIMAH', 'Ras Al Khaimah'
    FUJAIRAH = 'FUJAIRAH', 'Fujairah'


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_profile'
    )
    trade_license_number = models.CharField(max_length=100, help_text="UAE Commercial License / DED Number")
    tax_registration_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Federal Tax Authority TRN (15 digits)"
    )
    industry = models.CharField(max_length=100, default='General Commerce & Logistics')
    contact_person_designation = models.CharField(max_length=100, default='Procurement Manager')
    emirate = models.CharField(max_length=50, choices=UAEEmirate.choices, default=UAEEmirate.DUBAI)
    office_address = models.TextField(help_text="Building, Street, Area, Dubai/UAE")
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.company_name or self.user.username} ({self.get_emirate_display()})"
