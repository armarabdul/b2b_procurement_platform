from django.shortcuts import render
from apps.rfqs.models import RFQ, RFQStatus, Category
from apps.accounts.models import User, UserRole


def landing_view(request):
    """
    Public SaaS landing page showcasing ProcureHub UAE B2B value proposition.
    """
    recent_rfqs = RFQ.objects.filter(status__in=[RFQStatus.PUBLISHED, RFQStatus.QUOTATIONS_RECEIVED])[:4]
    categories = Category.objects.all()[:6]
    stats = {
        'active_rfqs': RFQ.objects.filter(status__in=[RFQStatus.PUBLISHED, RFQStatus.QUOTATIONS_RECEIVED]).count(),
        'suppliers_count': User.objects.filter(role=UserRole.SUPPLIER, approval_status='APPROVED').count(),
        'buyers_count': User.objects.filter(role=UserRole.CUSTOMER, approval_status='APPROVED').count(),
    }
    return render(request, 'landing.html', {
        'recent_rfqs': recent_rfqs,
        'categories': categories,
        'stats': stats,
    })


def handler400(request, exception=None):
    return render(request, 'errors/400.html', status=400)


def handler403(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def handler404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def handler500(request):
    return render(request, 'errors/500.html', status=500)
