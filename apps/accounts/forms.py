from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, UserRole, ApprovalStatus
from apps.customers.models import CustomerProfile, UAEEmirate
from apps.suppliers.models import SupplierProfile


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 text-sm transition',
            'placeholder': 'name@company.com or username',
            'autocomplete': 'username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 text-sm transition',
            'placeholder': '••••••••',
            'autocomplete': 'current-password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                # Try authenticating by email
                try:
                    user_obj = User.objects.get(email=username)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user = None

            if not user:
                raise forms.ValidationError("Invalid email/username or password. Please try again.")
            if not user.is_active:
                raise forms.ValidationError("This account has been deactivated. Contact support.")
            cleaned_data['user'] = user

        return cleaned_data


class CustomerRegistrationForm(forms.Form):
    # User Details
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'e.g. Tariq'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'e.g. Al-Mansoor'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-input-field', 'placeholder': 'tariq@alfuttaim-procurement.ae'}))
    company_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'e.g. Al-Futtaim Logistics LLC'}))
    phone = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': '+971 4 123 4567'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input-field', 'placeholder': 'Min 6 characters'}))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input-field', 'placeholder': 'Confirm password'}))

    # Business Information
    trade_license_number = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'CN-1234567 / DED-98765'}))
    tax_registration_number = forms.CharField(required=False, max_length=50, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': '100XXXXXXXXX003 (Optional)'}))
    industry = forms.CharField(max_length=100, initial='General Enterprise / Logistics', widget=forms.TextInput(attrs={'class': 'form-input-field'}))
    contact_person_designation = forms.CharField(max_length=100, initial='Head of Procurement', widget=forms.TextInput(attrs={'class': 'form-input-field'}))
    emirate = forms.ChoiceField(choices=UAEEmirate.choices, initial=UAEEmirate.DUBAI, widget=forms.Select(attrs={'class': 'form-input-field'}))
    office_address = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-input-field', 'rows': 2, 'placeholder': 'Tower 2, Business Bay, Dubai, UAE'}))

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Passwords do not match.")
        if p1:
            try:
                validate_password(p1)
            except forms.ValidationError as e:
                self.add_error('password', e)
        return cleaned_data

    def save(self):
        cd = self.cleaned_data
        username = cd['email']
        user = User.objects.create_user(
            username=username,
            email=cd['email'],
            password=cd['password'],
            first_name=cd['first_name'],
            last_name=cd['last_name'],
            company_name=cd['company_name'],
            phone=cd['phone'],
            role=UserRole.CUSTOMER,
            approval_status=ApprovalStatus.PENDING
        )
        CustomerProfile.objects.create(
            user=user,
            trade_license_number=cd['trade_license_number'],
            tax_registration_number=cd.get('tax_registration_number', ''),
            industry=cd['industry'],
            contact_person_designation=cd['contact_person_designation'],
            emirate=cd['emirate'],
            office_address=cd['office_address']
        )
        return user


class SupplierRegistrationForm(forms.Form):
    # User Details
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'e.g. Rashid'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'e.g. Khan'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-input-field', 'placeholder': 'rashid@emiratesoffice.ae'}))
    company_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'e.g. Emirates Commercial Supplies LLC'}))
    phone = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': '+971 4 765 4321'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input-field', 'placeholder': 'Min 6 characters'}))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input-field', 'placeholder': 'Confirm password'}))

    # Supplier Details
    trade_license_number = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'DED-Commercial-782910'}))
    business_categories = forms.CharField(
        max_length=255,
        initial="Office Furniture, Electrical Equipment, IT Equipment",
        widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': 'Comma-separated categories'})
    )
    emirate = forms.ChoiceField(choices=UAEEmirate.choices, initial=UAEEmirate.DUBAI, widget=forms.Select(attrs={'class': 'form-input-field'}))
    office_address = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-input-field', 'rows': 2, 'placeholder': 'Warehouse 14, Al Quoz Industrial 3, Dubai, UAE'}))
    years_in_business = forms.IntegerField(initial=5, min_value=1, widget=forms.NumberInput(attrs={'class': 'form-input-field'}))
    tax_registration_number = forms.CharField(required=False, max_length=50, widget=forms.TextInput(attrs={'class': 'form-input-field', 'placeholder': '100XXXXXXXXX003'}))

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Passwords do not match.")
        if p1:
            try:
                validate_password(p1)
            except forms.ValidationError as e:
                self.add_error('password', e)
        return cleaned_data

    def save(self):
        cd = self.cleaned_data
        username = cd['email']
        user = User.objects.create_user(
            username=username,
            email=cd['email'],
            password=cd['password'],
            first_name=cd['first_name'],
            last_name=cd['last_name'],
            company_name=cd['company_name'],
            phone=cd['phone'],
            role=UserRole.SUPPLIER,
            approval_status=ApprovalStatus.PENDING
        )
        SupplierProfile.objects.create(
            user=user,
            trade_license_number=cd['trade_license_number'],
            business_categories=cd['business_categories'],
            emirate=cd['emirate'],
            office_address=cd['office_address'],
            years_in_business=cd['years_in_business'],
            tax_registration_number=cd.get('tax_registration_number', '')
        )
        return user
