from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models import UserRole, ApprovalStatus


def role_required(allowed_roles):
    """
    Decorator for views that checks whether a user has one of the allowed roles.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if request.user.role not in allowed_roles:
                messages.error(request, "Access denied: You do not have permission to view this resource.")
                raise PermissionDenied("You do not have the required role to access this page.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def approved_required(view_func):
    """
    Decorator checking if the user's account is approved by an administrator.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if request.user.is_superuser or request.user.role == UserRole.ADMIN:
            return view_func(request, *args, **kwargs)
        if request.user.approval_status != ApprovalStatus.APPROVED:
            return redirect('accounts:pending_approval')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
