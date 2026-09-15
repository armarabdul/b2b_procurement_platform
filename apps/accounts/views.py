from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import User, UserRole, ApprovalStatus
from .forms import LoginForm, CustomerRegistrationForm, SupplierRegistrationForm
from apps.audit.models import ActivityLog


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            ActivityLog.log(
                user=user,
                action='LOGIN',
                description=f"User {user.email} logged into portal",
                request=request
            )
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect('accounts:dashboard_redirect')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.user.is_authenticated:
        ActivityLog.log(
            user=request.user,
            action='LOGOUT',
            description=f"User {request.user.email} logged out",
            request=request
        )
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('landing')


def register_customer_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')

    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            ActivityLog.log(
                user=user,
                action='REGISTER_CUSTOMER',
                description=f"New buyer registered: {user.company_name} ({user.email})",
                request=request
            )
            login(request, user)
            messages.success(
                request,
                "Registration successful! Your corporate buyer account is pending administrative verification."
            )
            return redirect('accounts:pending_approval')
    else:
        form = CustomerRegistrationForm()

    return render(request, 'accounts/register_customer.html', {'form': form})


def register_supplier_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')

    if request.method == 'POST':
        form = SupplierRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            ActivityLog.log(
                user=user,
                action='REGISTER_SUPPLIER',
                description=f"New vendor registered: {user.company_name} ({user.email})",
                request=request
            )
            login(request, user)
            messages.success(
                request,
                "Registration submitted! Your supplier profile is pending verification by the procurement committee."
            )
            return redirect('accounts:pending_approval')
    else:
        form = SupplierRegistrationForm()

    return render(request, 'accounts/register_supplier.html', {'form': form})


@login_required
def pending_approval_view(request):
    if request.user.is_approved:
        return redirect('accounts:dashboard_redirect')
    return render(request, 'accounts/pending_approval.html', {'user': request.user})


@login_required
def dashboard_redirect_view(request):
    user = request.user
    if user.is_admin_user:
        return redirect('admin_portal:dashboard')
    elif user.is_customer:
        if not user.is_approved:
            return redirect('accounts:pending_approval')
        return redirect('customer_portal:dashboard')
    elif user.is_supplier:
        if not user.is_approved:
            return redirect('accounts:pending_approval')
        return redirect('supplier_portal:dashboard')
    return redirect('landing')


def quick_switch_view(request, role_code):
    """
    Demo convenience switcher: allows 1-click instant login into demo persona accounts.
    """
    email_map = {
        'admin': 'admin@procurehub.demo',
        'customer': 'customer@procurehub.demo',
        'supplier1': 'supplier1@procurehub.demo',
        'supplier2': 'supplier2@procurehub.demo',
        'supplier3': 'supplier3@procurehub.demo',
        'pending_customer': 'pending_buyer@procurehub.demo',
        'pending_supplier': 'pending_vendor@procurehub.demo',
    }
    target_email = email_map.get(role_code)
    if target_email:
        user = User.objects.filter(email=target_email).first()
        if user:
            login(request, user)
            messages.info(request, f"Switched persona to: {user.get_full_name() or user.username} [{user.role}]")
            return redirect('accounts:dashboard_redirect')

    messages.warning(request, "Target demo user not found. Please run 'python manage.py seed_demo' first.")
    return redirect('accounts:login')


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})
