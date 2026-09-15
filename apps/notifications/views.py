from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Notification


@login_required
def notifications_list_view(request):
    notifications = request.user.notifications.all()
    return render(request, 'notifications/list.html', {'notifications': notifications})


@login_required
def mark_as_read_view(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'status': 'ok'})

    if notif.link:
        return redirect(notif.link)
    return redirect('notifications:list')


@login_required
def mark_all_read_view(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('notifications:list')
