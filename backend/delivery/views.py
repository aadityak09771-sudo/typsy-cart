from functools import wraps
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import DeliveryPartner, DeliveryAssignment, OrderStatusHistory
from .forms import DeliveryPartnerRegistrationForm


def delivery_partner_required(view_func):
    """
    Decorator to ensure the authenticated user is an active DeliveryPartner.
    Redirects unauthenticated users or customers attempting access.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please log in to your Delivery Partner account.")
            return redirect(f"/delivery/login/?next={request.path}")

        try:
            partner = request.user.delivery_profile
            if not partner.is_active:
                logout(request)
                messages.error(request, "Your delivery partner account has been deactivated. Please contact the administrator.")
                return redirect("delivery:login")
        except DeliveryPartner.DoesNotExist:
            messages.error(request, "Access denied. Your account is not authorized as a delivery partner.")
            return redirect("delivery:login")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def partner_login(request):
    redirect_to = request.POST.get("next") or request.GET.get("next") or "/delivery/dashboard/"

    if request.user.is_authenticated:
        if hasattr(request.user, "delivery_profile") and request.user.delivery_profile.is_active:
            return redirect("delivery:dashboard")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            try:
                partner = user.delivery_profile
                if not partner.is_active:
                    messages.error(request, "This delivery partner account is deactivated. Contact store admin.")
                    return render(request, "delivery/login.html", {"form": form})

                login(request, user, backend="accounts.backends.AutoAdminBackend")
                messages.success(request, f"Welcome back, {partner.get_display_name()}! 🛵")

                if redirect_to and url_has_allowed_host_and_scheme(
                    url=redirect_to,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(redirect_to)

                return redirect("delivery:dashboard")

            except DeliveryPartner.DoesNotExist:
                messages.error(request, "This account is not registered as a Delivery Partner. Please use your driver credentials.")
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = AuthenticationForm(request)

    return render(
        request,
        "delivery/login.html",
        {"form": form, "next": redirect_to if redirect_to != "/delivery/dashboard/" else ""},
    )


def partner_register(request):
    if request.user.is_authenticated:
        if hasattr(request.user, "delivery_profile") and request.user.delivery_profile.is_active:
            return redirect("delivery:dashboard")

    if request.method == "POST":
        form = DeliveryPartnerRegistrationForm(request.POST)
        if form.is_valid():
            partner = form.save()
            # Log the new partner in automatically
            login(request, partner.user, backend="accounts.backends.AutoAdminBackend")
            messages.success(
                request,
                f"🎉 Welcome aboard, {partner.get_display_name()}! Your driver account ({partner.partner_id}) has been created successfully."
            )
            return redirect("delivery:dashboard")
        else:
            messages.error(request, "Please check the form and correct the highlighted fields.")
    else:
        form = DeliveryPartnerRegistrationForm()

    return render(request, "delivery/register.html", {"form": form})


def partner_logout(request):
    logout(request)
    messages.success(request, "You have been logged out of the Delivery Partner portal.")
    return redirect("delivery:login")


@delivery_partner_required
def partner_dashboard(request):
    partner = request.user.delivery_profile
    tab = request.GET.get("tab", "all").strip().lower()

    all_assignments = (
        DeliveryAssignment.objects.filter(partner=partner)
        .select_related("order")
        .prefetch_related("order__items")
        .order_by("-assigned_at")
    )

    # Calculate real statistics
    counts = {
        "total": all_assignments.count(),
        "new_requests": all_assignments.filter(status="Assigned").count(),
        "accepted": all_assignments.filter(status="Accepted").count(),
        "picked_up": all_assignments.filter(status="Picked Up").count(),
        "out_for_delivery": all_assignments.filter(status="Out for Delivery").count(),
        "completed": all_assignments.filter(status="Delivered").count(),
        "failed": all_assignments.filter(status__in=["Delivery Failed", "Rejected"]).count(),
    }

    # Filter assignments by selected tab
    if tab == "new":
        assignments = all_assignments.filter(status="Assigned")
    elif tab == "accepted":
        assignments = all_assignments.filter(status="Accepted")
    elif tab == "picked_up":
        assignments = all_assignments.filter(status="Picked Up")
    elif tab == "out_for_delivery":
        assignments = all_assignments.filter(status="Out for Delivery")
    elif tab == "completed":
        assignments = all_assignments.filter(status="Delivered")
    elif tab == "failed":
        assignments = all_assignments.filter(status__in=["Delivery Failed", "Rejected"])
    else:
        tab = "all"
        assignments = all_assignments

    context = {
        "partner": partner,
        "counts": counts,
        "assignments": assignments,
        "active_tab": tab,
    }
    return render(request, "delivery/dashboard.html", context)


@delivery_partner_required
def partner_order_detail(request, order_id):
    partner = request.user.delivery_profile
    assignment = get_object_or_404(
        DeliveryAssignment.objects.select_related("order").prefetch_related("order__items"),
        order_id=order_id,
        partner=partner,
    )
    order = assignment.order
    history = order.status_history.all()

    context = {
        "partner": partner,
        "assignment": assignment,
        "order": order,
        "history": history,
    }
    return render(request, "delivery/order_detail.html", context)


@require_POST
@delivery_partner_required
def accept_assignment(request, assignment_id):
    partner = request.user.delivery_profile
    assignment = get_object_or_404(DeliveryAssignment, pk=assignment_id, partner=partner)

    if assignment.status != "Assigned":
        messages.error(request, f"Cannot accept order in '{assignment.status}' state.")
        return redirect("delivery:dashboard")

    with transaction.atomic():
        old_status = assignment.order.status
        assignment.status = "Accepted"
        assignment.accepted_at = timezone.now()
        assignment.save(update_fields=["status", "accepted_at", "updated_at"])

        assignment.order.status = "Accepted"
        assignment.order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(
            order=assignment.order,
            previous_status=old_status,
            new_status="Accepted",
            changed_by=request.user,
            remarks=f"Order accepted by delivery partner {partner.get_display_name()}",
        )

    messages.success(request, f"Order #{assignment.order_id} accepted successfully. Proceed to pickup.")
    return redirect("delivery:dashboard")


@require_POST
@delivery_partner_required
def reject_assignment(request, assignment_id):
    partner = request.user.delivery_profile
    assignment = get_object_or_404(DeliveryAssignment, pk=assignment_id, partner=partner)

    if assignment.status != "Assigned":
        messages.error(request, f"Cannot reject order in '{assignment.status}' state.")
        return redirect("delivery:dashboard")

    reason = request.POST.get("rejection_reason", "").strip()
    if not reason:
        messages.error(request, "Please provide a reason for rejecting this assignment.")
        return redirect("delivery:dashboard")

    with transaction.atomic():
        old_status = assignment.order.status
        assignment.status = "Rejected"
        assignment.rejection_reason = reason
        assignment.save(update_fields=["status", "rejection_reason", "updated_at"])

        assignment.order.status = "Confirmed"
        assignment.order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(
            order=assignment.order,
            previous_status=old_status,
            new_status="Confirmed",
            changed_by=request.user,
            remarks=f"Rejected by partner {partner.get_display_name()}. Reason: {reason}",
        )

    messages.warning(request, f"Order #{assignment.order_id} was rejected and returned to Admin queue.")
    return redirect("delivery:dashboard")


@require_POST
@delivery_partner_required
def pickup_assignment(request, assignment_id):
    partner = request.user.delivery_profile
    assignment = get_object_or_404(DeliveryAssignment, pk=assignment_id, partner=partner)

    if assignment.status != "Accepted":
        messages.error(request, f"Order must be accepted before it can be picked up.")
        return redirect("delivery:dashboard")

    with transaction.atomic():
        old_status = assignment.order.status
        assignment.status = "Picked Up"
        assignment.picked_up_at = timezone.now()
        assignment.save(update_fields=["status", "picked_up_at", "updated_at"])

        assignment.order.status = "Picked Up"
        assignment.order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(
            order=assignment.order,
            previous_status=old_status,
            new_status="Picked Up",
            changed_by=request.user,
            remarks=f"Order picked up from store by {partner.get_display_name()}",
        )

    messages.success(request, f"Order #{assignment.order_id} marked as Picked Up.")
    return redirect("delivery:dashboard")


@require_POST
@delivery_partner_required
def out_for_delivery_assignment(request, assignment_id):
    partner = request.user.delivery_profile
    assignment = get_object_or_404(DeliveryAssignment, pk=assignment_id, partner=partner)

    if assignment.status != "Picked Up":
        messages.error(request, "Order must be Picked Up before starting delivery.")
        return redirect("delivery:dashboard")

    with transaction.atomic():
        old_status = assignment.order.status
        assignment.status = "Out for Delivery"
        assignment.save(update_fields=["status", "updated_at"])

        assignment.order.status = "Out for Delivery"
        assignment.order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(
            order=assignment.order,
            previous_status=old_status,
            new_status="Out for Delivery",
            changed_by=request.user,
            remarks=f"Partner {partner.get_display_name()} is out for delivery to customer",
        )

    messages.success(request, f"Order #{assignment.order_id} is now Out for Delivery!")
    return redirect("delivery:dashboard")


@require_POST
@delivery_partner_required
def deliver_assignment(request, assignment_id):
    partner = request.user.delivery_profile
    assignment = get_object_or_404(DeliveryAssignment, pk=assignment_id, partner=partner)

    if assignment.status != "Out for Delivery":
        messages.error(request, "Order must be Out for Delivery before marking as Delivered.")
        return redirect("delivery:dashboard")

    with transaction.atomic():
        old_status = assignment.order.status
        now = timezone.now()
        assignment.status = "Delivered"
        assignment.delivered_at = now
        assignment.save(update_fields=["status", "delivered_at", "updated_at"])

        assignment.order.status = "Delivered"
        assignment.order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(
            order=assignment.order,
            previous_status=old_status,
            new_status="Delivered",
            changed_by=request.user,
            remarks=f"Order delivered successfully by {partner.get_display_name()}",
        )

    messages.success(request, f"🎉 Order #{assignment.order_id} was successfully delivered!")
    return redirect("delivery:dashboard")


@require_POST
@delivery_partner_required
def fail_assignment(request, assignment_id):
    partner = request.user.delivery_profile
    assignment = get_object_or_404(DeliveryAssignment, pk=assignment_id, partner=partner)

    if assignment.status not in ["Picked Up", "Out for Delivery"]:
        messages.error(request, "Cannot mark this order as failed at the current stage.")
        return redirect("delivery:dashboard")

    reason = request.POST.get("failure_reason", "").strip()
    if not reason:
        messages.error(request, "Please enter a specific reason why the delivery could not be completed.")
        return redirect("delivery:dashboard")

    with transaction.atomic():
        old_status = assignment.order.status
        assignment.status = "Delivery Failed"
        assignment.failure_reason = reason
        assignment.save(update_fields=["status", "failure_reason", "updated_at"])

        assignment.order.status = "Delivery Failed"
        assignment.order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(
            order=assignment.order,
            previous_status=old_status,
            new_status="Delivery Failed",
            changed_by=request.user,
            remarks=f"Delivery attempt failed. Reason: {reason}",
        )

    messages.warning(request, f"Order #{assignment.order_id} marked as Delivery Failed.")
    return redirect("delivery:dashboard")


@delivery_partner_required
def partner_profile(request):
    partner = request.user.delivery_profile

    if request.method == "POST":
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        vehicle_type = request.POST.get("vehicle_type", "").strip()
        vehicle_number = request.POST.get("vehicle_number", "").strip()
        availability_status = request.POST.get("availability_status", "").strip()

        if phone:
            partner.phone = phone
        partner.address = address
        if vehicle_type in dict(DeliveryPartner.VEHICLE_CHOICES):
            partner.vehicle_type = vehicle_type
        partner.vehicle_number = vehicle_number
        if availability_status in dict(DeliveryPartner.AVAILABILITY_CHOICES):
            partner.availability_status = availability_status

        partner.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("delivery:profile")

    context = {
        "partner": partner,
        "vehicle_choices": DeliveryPartner.VEHICLE_CHOICES,
        "availability_choices": DeliveryPartner.AVAILABILITY_CHOICES,
    }
    return render(request, "delivery/profile.html", context)
