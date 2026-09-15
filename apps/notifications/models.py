from django.db import models
from django.conf import settings


class NotificationType(models.TextChoices):
    INFO = 'INFO', 'Information'
    SUCCESS = 'SUCCESS', 'Success'
    WARNING = 'WARNING', 'Warning'
    AWARD = 'AWARD', 'Quotation Awarded'
    PO = 'PO', 'Purchase Order'
    PAYMENT = 'PAYMENT', 'Payment Update'


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.INFO
    )
    link = models.CharField(max_length=255, blank=True, help_text="Relative URL to target page")
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"To: {self.recipient.email} | {self.title}"

    @classmethod
    def send(cls, recipient, title, message, notification_type=NotificationType.INFO, link=''):
        return cls.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )
