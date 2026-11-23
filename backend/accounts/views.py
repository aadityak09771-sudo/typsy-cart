
import json
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django import forms
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q

from orders.models import Order
from .services.otp_service import (
    request_otp,
    verify_otp_submission,
    create_password_reset_token,
    verify_and_apply_password_reset,
    normalize_email,
)


class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            "placeholder": "e.g. yourname@example.com",
            "autocomplete": "email",
            "class": "form-input",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].validators = [
            RegexValidator(
                regex=r'^[A-Za-z]+(?: [A-Za-z]+)*$',
                message="Only letters and spaces are allowed."
            )
        ]

        self.fields["username"].help_text = (
            "Required. 150 characters or fewer. Letters and spaces only."
        )

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        exclude.add("username")
        return exclude

    def clean_username(self):
        username = self.cleaned_data.get("username")
        User = get_user_model()

        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError(
                "A user with that username already exists."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if email:
            User = get_user_model()
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError("An account with this email address already exists. Please log in.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data.get("email", "").strip().lower()
        if email:
            user.email = email
        if commit:
            user.save()
        return user



def register_view(request):
    """
    Seamless passwordless registration: redirects directly to OTP login/signup.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


def _parse_request_data(request):
    if request.content_type == "application/json" and request.body:
        try:
            return json.loads(request.body.decode("utf-8"))
        except Exception:
            return {}
    return request.POST


@require_POST
def send_otp_view(request):
    """
    Dispatches a 6-digit OTP code to the requested email via Resend.
    Works for customer_login, delivery_login, and forgot_password.
    """
    data = _parse_request_data(request)
    email = data.get("email", "").strip()
    username = data.get("username", "").strip() or data.get("name", "").strip() or data.get("full_name", "").strip()
    purpose = data.get("purpose", "customer_login").strip()

    if username and purpose == "customer_login":
        import re
        if not re.match(r"^[a-zA-Z0-9_.\s-]{2,40}$", username):
            return JsonResponse({
                "success": False,
                "error": "Name/Username must be 2-40 characters containing only letters, numbers, spaces, underscores, dots, or hyphens."
            }, status=400)

        # Validate username uniqueness across existing accounts with different emails
        clean_user = re.sub(r"[^\w.-]", "_", username.strip())
        User = get_user_model()
        existing_with_username = User.objects.filter(username__iexact=clean_user).first()
        if existing_with_username and email and existing_with_username.email.lower() != email.lower():
            return JsonResponse({
                "success": False,
                "error": "This username is already taken. Please choose another username."
            }, status=400)

        request.session["pending_otp_username"] = username.strip()
        request.session["pending_otp_name"] = username.strip()

    success, message, extra = request_otp(email, purpose, request=request)
    status_code = 200 if success else 400

    return JsonResponse({
        "success": success,
        "message": message if success else "",
        "error": "" if success else message,
        **extra
    }, status=status_code)


@require_POST
def verify_otp_view(request):
    """
    Verifies an entered 6-digit OTP for customer login, delivery login, or forgot password.
    Logs the user into their session if authenticating, or returns a password reset token.
    """
    data = _parse_request_data(request)
    email = data.get("email", "").strip()
    otp = data.get("otp", "").strip()
    submitted_username = data.get("username", "").strip() or data.get("name", "").strip() or request.session.get("pending_otp_username", "").strip() or request.session.get("pending_otp_name", "").strip()
    purpose = data.get("purpose", "customer_login").strip()
    redirect_to = data.get("next", "").strip()

    success, message, extra = verify_otp_submission(email, otp, purpose)
    if not success:
        return JsonResponse({"success": False, "error": message, **extra}, status=400)

    User = get_user_model()

    if purpose == "customer_login":
        user = User.objects.filter(email__iexact=email).first()
        is_new_user = False
        import re
        if not user:
            # Seamless passwordless account creation on OTP verification with Username
            clean_base = re.sub(r"[^\w.-]", "_", (submitted_username or email.split("@")[0]).strip()) or "customer"
            final_username = clean_base
            counter = 1
            while User.objects.filter(username__iexact=final_username).exists():
                final_username = f"{clean_base}_{counter}"
                counter += 1

            user = User.objects.create_user(
                username=final_username,
                email=email,
                first_name=(submitted_username or final_username).strip(),
            )
            user.set_unusable_password()
            user.save()
            is_new_user = True
        else:
            if not user.is_active:
                return JsonResponse({"success": False, "error": "Customer account not found or deactivated."}, status=400)

            if user.is_staff or user.is_superuser:
                return JsonResponse({"success": False, "error": "Administrator accounts must use the Admin Portal at /admin/."}, status=403)

            # Update display name / username if valid new name submitted
            if submitted_username:
                clean_base = re.sub(r"[^\w.-]", "_", submitted_username.strip())
                if clean_base and not User.objects.filter(username__iexact=clean_base).exclude(pk=user.pk).exists():
                    user.username = clean_base
                user.first_name = submitted_username.strip()
                user.save(update_fields=["username", "first_name"])

        login(request, user, backend="accounts.backends.AutoAdminBackend")
        display_name = user.first_name or user.username
        if is_new_user:
            messages.success(request, f"Welcome to TipsyCart, {display_name}! 🎉")
        else:
            messages.success(request, f"Welcome back, {display_name}!")

        target_url = "/dashboard/"
        if redirect_to and url_has_allowed_host_and_scheme(
            url=redirect_to,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            target_url = redirect_to

        return JsonResponse({
            "success": True,
            "message": "Login successful! Redirecting...",
            "redirect_url": target_url,
        })

    elif purpose == "delivery_login":
        from delivery.models import DeliveryPartner
        partner = DeliveryPartner.objects.filter(
            Q(email__iexact=email) | Q(user__email__iexact=email)
        ).select_related("user").first()

        if not partner or not partner.is_active or not partner.user.is_active:
            return JsonResponse({"success": False, "error": "Delivery partner account not found or deactivated."}, status=403)

        login(request, partner.user, backend="accounts.backends.AutoAdminBackend")
        messages.success(request, f"Welcome back, {partner.get_display_name()}! 🛵")

        target_url = "/delivery/dashboard/"
        if redirect_to and url_has_allowed_host_and_scheme(
            url=redirect_to,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            target_url = redirect_to

        return JsonResponse({
            "success": True,
            "message": f"Welcome back, {partner.get_display_name()}! Redirecting...",
            "redirect_url": target_url,
        })

    elif purpose == "forgot_password":
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return JsonResponse({"success": False, "error": "User account not found."}, status=400)

        reset_token = create_password_reset_token(user.id, email, extra.get("otp_id", 0))
        return JsonResponse({
            "success": True,
            "message": "Verification code verified successfully. Please enter your new password.",
            "reset_token": reset_token,
        })

    return JsonResponse({"success": False, "error": "Unsupported verification purpose."}, status=400)


@require_POST
def reset_password_view(request):
    """
    Applies a new password given a valid cryptographically signed reset token.
    """
    data = _parse_request_data(request)
    token = data.get("reset_token", "").strip()
    new_password = data.get("new_password", "").strip()
    confirm_password = data.get("confirm_password", "").strip()

    success, message = verify_and_apply_password_reset(token, new_password, confirm_password)
    status_code = 200 if success else 400

    return JsonResponse({
        "success": success,
        "message": message if success else "",
        "error": "" if success else message,
    }, status=status_code)


def login_view(request):
    redirect_to = request.POST.get("next") or request.GET.get("next") or ""

    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("admin:index")
        return redirect("dashboard")

    # If form submission with password
    if request.method == "POST" and (
        request.POST.get("login_type") == "password"
        or ("username" in request.POST and "password" in request.POST)
    ):
        form = AuthenticationForm(
            request,
            data=request.POST
        )

        if form.is_valid():
            user = form.get_user()
            login(request, user, backend="accounts.backends.AutoAdminBackend")

            messages.success(
                request,
                "Login successful!"
            )

            if redirect_to and url_has_allowed_host_and_scheme(
                url=redirect_to,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(redirect_to)

            if user.is_staff:
                return redirect("admin:index")

            return redirect("dashboard")

        messages.error(
            request,
            "Invalid username or password. Please try again."
        )

    else:
        form = AuthenticationForm(request)

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "next": redirect_to,
        }
    )


def logout_view(request):
    logout(request)

    messages.success(
        request,
        "You have logged out."
    )

    redirect_to = request.POST.get("next") or request.GET.get("next") or ""
    if redirect_to and url_has_allowed_host_and_scheme(
        url=redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(redirect_to)

    return redirect("home")


def admin_logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out of your session.")
    return redirect("admin:login")


@login_required(login_url="login")
def dashboard_view(request):
    # If authenticated user is a delivery partner, redirect to driver dashboard
    if hasattr(request.user, "delivery_profile"):
        return redirect("delivery:dashboard")

    customer_orders = (
        Order.objects
        .filter(user=request.user)
        .select_related("delivery_assignment", "delivery_assignment__partner")
        .prefetch_related("items", "items__product")
        .order_by("-created_at")
    )

    # Active order: prioritize orders that are actively in progress
    in_progress_statuses = [
        "Pending", "Confirmed", "Processing", "Packed",
        "Assigned", "Accepted", "Picked Up", "Out for Delivery"
    ]
    active_order = customer_orders.filter(status__in=in_progress_statuses).first()

    # If no active in-progress order, pick the latest order
    if not active_order and customer_orders.exists():
        active_order = customer_orders.first()

    context = {
        "customer_orders": customer_orders,
        "total_orders": customer_orders.count(),
        "active_order": active_order,
        "user": request.user,
    }

    return render(
        request,
        "accounts/dashboard.html",
        context
    )
