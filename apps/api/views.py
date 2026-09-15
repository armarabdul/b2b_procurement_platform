from rest_framework import viewsets, permissions
from apps.accounts.models import User, UserRole
from apps.rfqs.models import Category, RFQ
from apps.quotations.models import Quotation
from apps.procurement.models import PurchaseOrder
from apps.payments.models import Payment
from apps.notifications.models import Notification
from .serializers import (
    UserSerializer,
    CategorySerializer,
    RFQSerializer,
    QuotationSerializer,
    PurchaseOrderSerializer,
    PaymentSerializer,
    NotificationSerializer
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class RFQViewSet(viewsets.ModelViewSet):
    queryset = RFQ.objects.all()
    serializer_class = RFQSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return RFQ.objects.filter(status='PUBLISHED')
        if user.is_admin_user:
            return RFQ.objects.all()
        if user.is_customer:
            return RFQ.objects.filter(customer=user)
        # Supplier can see all published/active RFQs
        return RFQ.objects.filter(status__in=['PUBLISHED', 'QUOTATIONS_RECEIVED', 'UNDER_REVIEW'])


class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.all()
    serializer_class = QuotationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin_user:
            return Quotation.objects.all()
        if user.is_supplier:
            return Quotation.objects.filter(supplier=user)
        if user.is_customer:
            return Quotation.objects.filter(rfq__customer=user)
        return Quotation.objects.none()


class PurchaseOrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin_user:
            return PurchaseOrder.objects.all()
        if user.is_customer:
            return PurchaseOrder.objects.filter(customer=user)
        if user.is_supplier:
            return PurchaseOrder.objects.filter(supplier=user)
        return PurchaseOrder.objects.none()


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin_user:
            return Payment.objects.all()
        if user.is_customer:
            return Payment.objects.filter(po__customer=user)
        if user.is_supplier:
            return Payment.objects.filter(po__supplier=user)
        return Payment.objects.none()


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.request.user.notifications.all()
