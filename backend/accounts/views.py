
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django import forms
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils.http import url_has_allowed_host_and_scheme

from orders.models import Order


class CustomerRegistrationForm(UserCreationForm):

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


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            messages.success(
                request,
                "Account created successfully!"
            )
            return redirect("home")

        messages.error(
            request,
            "Please correct the errors in the registration form."
        )

    else:
        form = CustomerRegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form}
    )


def login_view(request):
    redirect_to = request.POST.get("next") or request.GET.get("next") or ""

    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("admin:index")
        return redirect("dashboard")

    if request.method == "POST":
        form = AuthenticationForm(
            request,
            data=request.POST
        )

        if form.is_valid():
            user = form.get_user()
            login(request, user)

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
