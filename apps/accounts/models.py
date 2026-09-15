import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', 'Procurement Admin'
    CUSTOMER = 'CUSTOMER', 'Customer / Buyer'
    SUPPLIER = 'SUPPLIER', 'Supplier / Vendor'


class ApprovalStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Approval'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    SUSPENDED = 'SUSPENDED', 'Suspended'


class User(AbstractUser):
    """
    Custom user model supporting Role-Based Access Control and verification approval state.
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        help_text="Primary platform role."
    )
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        help_text="Administrative approval state."
    )
    company_name = models.CharField(max_length=255, blank=True, help_text="Company / Legal Entity Name")
    phone = models.CharField(max_length=30, blank=True, help_text="Contact telephone / mobile (+971...)")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['role', 'approval_status']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        name = self.get_full_name() or self.username
        if self.company_name:
            return f"{name} ({self.company_name}) [{self.role}]"
        return f"{name} [{self.role}]"

    @property
    def is_admin_user(self):
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_customer(self):
        return self.role == UserRole.CUSTOMER

    @property
    def is_supplier(self):
        return self.role == UserRole.SUPPLIER

    @property
    def is_approved(self):
        return self.approval_status == ApprovalStatus.APPROVED or self.is_superuser
