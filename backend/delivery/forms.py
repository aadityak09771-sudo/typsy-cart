from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import DeliveryPartner

User = get_user_model()


class DeliveryPartnerRegistrationForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        required=True,
        label="Full Name",
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "e.g. Rahul Sharma",
            "autocomplete": "name",
        }),
    )

    username = forms.CharField(
        max_length=150,
        required=True,
        label="Username",
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "e.g. rahul_delivery",
            "autocomplete": "username",
        }),
    )

    phone = forms.CharField(
        max_length=15,
        required=True,
        label="Mobile Phone Number",
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "e.g. 9876543210",
            "autocomplete": "tel",
        }),
    )

    email = forms.EmailField(
        required=False,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            "class": "form-input",
            "placeholder": "e.g. rahul@example.com",
            "autocomplete": "email",
        }),
    )

    vehicle_type = forms.ChoiceField(
        choices=DeliveryPartner.VEHICLE_CHOICES,
        initial="bike",
        required=True,
        label="Vehicle Type",
        widget=forms.Select(attrs={
            "class": "form-input",
        }),
    )

    vehicle_number = forms.CharField(
        max_length=30,
        required=False,
        label="Vehicle Registration Number",
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "e.g. MH 02 CZ 1234",
        }),
    )

    service_pincodes = forms.CharField(
        max_length=255,
        required=False,
        label="Preferred Delivery PIN Codes",
        help_text="Comma-separated PIN codes you can deliver to (e.g. 400001, 208002). Leave empty for all areas.",
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "e.g. 400001, 400002",
        }),
    )

    address = forms.CharField(
        max_length=300,
        required=False,
        label="Base Station / Operating Address",
        widget=forms.Textarea(attrs={
            "class": "form-input",
            "rows": 2,
            "placeholder": "e.g. Flat 12, Hub Road, Andheri West",
        }),
    )

    password = forms.CharField(
        required=True,
        label="Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "Create a strong password",
            "autocomplete": "new-password",
        }),
    )

    confirm_password = forms.CharField(
        required=True,
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "Re-enter your password",
            "autocomplete": "new-password",
        }),
    )

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if not username:
            raise ValidationError("Please provide a username.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken. Please choose another username.")
        return username

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        digits = "".join(filter(str.isdigit, phone))
        if len(digits) < 10:
            raise ValidationError("Please enter a valid phone number (at least 10 digits).")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match. Please re-enter carefully.")

        return cleaned_data

    def save(self):
        cleaned = self.cleaned_data
        full_name = cleaned["full_name"].strip()
        username = cleaned["username"].strip()
        phone = cleaned["phone"].strip()
        email = cleaned.get("email", "").strip()
        vehicle_type = cleaned["vehicle_type"]
        vehicle_number = cleaned.get("vehicle_number", "").strip()
        service_pincodes = cleaned.get("service_pincodes", "").strip()
        address = cleaned.get("address", "").strip()
        password = cleaned["password"]

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=full_name,
            )
            partner = DeliveryPartner.objects.create(
                user=user,
                full_name=full_name,
                phone=phone,
                email=email,
                vehicle_type=vehicle_type,
                vehicle_number=vehicle_number,
                service_pincodes=service_pincodes,
                address=address,
                availability_status="available",
                is_active=True,
            )
        return partner
