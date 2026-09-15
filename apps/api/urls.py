from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    RFQViewSet,
    QuotationViewSet,
    PurchaseOrderViewSet,
    PaymentViewSet,
    NotificationViewSet
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'rfqs', RFQViewSet, basename='rfq')
router.register(r'quotations', QuotationViewSet, basename='quotation')
router.register(r'orders', PurchaseOrderViewSet, basename='order')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]
