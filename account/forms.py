import re
import requests
from django import forms
from .models import User

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'password')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data.get("email")
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

class CustomAuthenticationForm(AuthenticationForm):
    def clean(self):
        username_input = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username_input is not None and password:
            user = None

            # Check if the input looks like an email address
            is_email = '@' in username_input

            if is_email:
                # Email login — for customers and sellers
                user = User.objects.filter(email__iexact=username_input).first()
                if user and user.role == 'ADMIN':
                    # Admin should not log in with email field
                    raise ValidationError(
                        "Please use your username (not email) to log in as admin.",
                        code='invalid_login',
                    )
            else:
                # Username login — ADMIN only
                user = User.objects.filter(username__iexact=username_input).first()
                if user and user.role != 'ADMIN':
                    raise ValidationError(
                        "Please use your email address to log in.",
                        code='invalid_login',
                    )

            if user and user.check_password(password) and getattr(user, 'is_active', True):
                self.user_cache = user
                self.user_cache.backend = 'django.contrib.auth.backends.ModelBackend'
                self.confirm_login_allowed(self.user_cache)
            else:
                raise self.get_invalid_login_error()

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.role == 'SELLER':
            if not hasattr(user, 'sellerprofile') or not user.sellerprofile.is_approved:
                raise ValidationError(
                    "Your seller account is pending admin approval.",
                    code='inactive',
                )


class SellerRegistrationForm(forms.Form):
    store_logo = forms.ImageField(required=False)
    store_name = forms.CharField(max_length=255)
    store_slug = forms.SlugField()
    
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=15, required=False)
    
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())
    
    gstin = forms.CharField(max_length=15, required=False)
    pan = forms.CharField(max_length=10, required=False)
    bank_ifsc = forms.CharField(max_length=11)
    account_no = forms.CharField(max_length=20)
    office_address = forms.CharField(widget=forms.Textarea)

    def clean_bank_ifsc(self):
        ifsc = self.cleaned_data.get("bank_ifsc")
        if ifsc:
            ifsc = ifsc.upper()
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
                raise forms.ValidationError("Invalid IFSC format.")
            
            try:
                res = requests.get(f"https://ifsc.razorpay.com/{ifsc}", timeout=3)
                if res.status_code != 200:
                    raise forms.ValidationError("Invalid IFSC code. Bank branch not found.")
            except requests.RequestException:
                pass
        return ifsc

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        email = cleaned_data.get("email")
        if email and User.objects.filter(email=email).exists():
            self.add_error('email', "Email already exists.")
            
        username = cleaned_data.get("username")
        if username and User.objects.filter(username=username).exists():
            self.add_error('username', "Username already exists.")
            
        from .models import SellerProfile
        store_slug = cleaned_data.get("store_slug")
        if store_slug and SellerProfile.objects.filter(store_slug=store_slug).exists():
            self.add_error('store_slug', "Store slug already taken.")
            
        return cleaned_data
