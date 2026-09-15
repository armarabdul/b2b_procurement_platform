from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import landing_view, handler400, handler403, handler404, handler500

urlpatterns = [
    path('', landing_view, name='landing'),
    path('admin/', admin.site.urls),

    # Core portals
    path('portal/admin/', include('apps.core.admin_urls', namespace='admin_portal')),
    path('portal/customer/', include('apps.customers.urls', namespace='customer_portal')),
    path('portal/supplier/', include('apps.suppliers.urls', namespace='supplier_portal')),

    # Accounts & Auth
    path('auth/', include('apps.accounts.urls', namespace='accounts')),

    # In-App Notifications
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),

    # REST API
    path('api/', include('apps.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler400 = handler400
handler403 = handler403
handler404 = handler404
handler500 = handler500
