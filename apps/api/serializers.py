from rest_framework import serializers
from apps.accounts.models import User
from apps.rfqs.models import Category, RFQ, RFQItem
from apps.quotations.models import Quotation, QuotationItem
from apps.procurement.models import PurchaseOrder, PurchaseOrderItem
from apps.payments.models import Payment, PaymentInstallment
from apps.notifications.models import Notification


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'company_name', 'phone', 'approval_status']
        read_only_fields = ['approval_status']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class RFQItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFQItem
        fields = '__all__'


class RFQSerializer(serializers.ModelSerializer):
    items = RFQItemSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField(source='customer.company_name')

    class Meta:
        model = RFQ
        fields = '__all__'


class QuotationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationItem
        fields = '__all__'


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True, read_only=True)
    supplier_name = serializers.ReadOnlyField(source='supplier.company_name')

    class Meta:
        model = Quotation
        fields = '__all__'


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField(source='customer.company_name')
    supplier_name = serializers.ReadOnlyField(source='supplier.company_name')

    class Meta:
        model = PurchaseOrder
        fields = '__all__'


class PaymentInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentInstallment
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    installments = PaymentInstallmentSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
