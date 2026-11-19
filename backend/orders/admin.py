import json
import logging
from urllib.request import Request, urlopen

from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.models import PushDevice
from delivery.models import DeliveryPartner, DeliveryAssignment, OrderStatusHistory
from .models import Cart, CartItem, Order, OrderItem

logger = logging.getLogger(__name__)


def send_order_status_notification(user_id, order_id, new_status):
    """
    Send order status notification to all registered devices
    belonging to the logged-in customer.
    """
    try:
        push_tokens = list(
            PushDevice.objects.filter(user_id=user_id)
            .values_list("expo_push_token", flat=True)
        )

        if not push_tokens:
            return

        messages_list = []

        for push_token in push_tokens:
            messages_list.append({
                "to": push_token,
                "sound": "default",
                "title": "Tipsy Cart - Order Update",
                "body": f"Your order #{order_id} is now {new_status}.",
                "channelId": "default",
                "priority": "high",
                "data": {
                    "orderId": order_id,
                    "status": new_status,
                },
            })

        for start in range(0, len(messages_list), 100):
            batch = messages_list[start:start + 100]
            payload = json.dumps(batch).encode("utf-8")

            request = Request(
                "https://exp.host/--/api/v2/push/send",
                data=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urlopen(request, timeout=15) as response:
                response.read()

    except Exception:
        logger.exception(
            "Failed to send order notification for order #%s",
            order_id,
        )


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    inlines = [CartItemInline]
    list_per_page = 25


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "quantity")
    search_fields = ("product__name", "cart__user__username")
    list_per_page = 25


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("product_name", "price", "quantity", "product")
    readonly_fields = ("product_name", "price", "quantity", "product")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    fields = ("previous_status", "new_status", "changed_by", "remarks", "created_at")
    readonly_fields = ("previous_status", "new_status", "changed_by", "remarks", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer_display",
        "phone",
        "city",
        "pincode",
        "total_amount",
        "payment_method",
        "order_status_badge",
        "delivery_partner_display",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_method",
        "delivery_assignment__partner",
        "delivery_assignment__status",
        "created_at",
    )

    search_fields = (
        "id",
        "full_name",
        "phone",
        "address",
        "city",
        "state",
        "pincode",
        "user__username",
        "user__email",
        "delivery_assignment__partner__full_name",
        "delivery_assignment__partner__phone",
    )

    readonly_fields = (
        "user",
        "full_name",
        "phone",
        "address",
        "city",
        "state",
        "pincode",
        "total_amount",
        "payment_method",
        "created_at",
        "delivery_management_display",
    )

    inlines = [OrderItemInline, OrderStatusHistoryInline]
    ordering = ("-created_at",)
    list_per_page = 25
    date_hierarchy = "created_at"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:order_id>/assign-delivery/",
                self.admin_site.admin_view(self.assign_delivery_view),
                name="orders_order_assign_delivery",
            ),
            path(
                "<int:order_id>/cancel-assignment/",
                self.admin_site.admin_view(self.cancel_assignment_view),
                name="orders_order_cancel_assignment",
            ),
        ]
        return custom_urls + urls

    def has_add_permission(self, request):
        return False

    @admin.display(description="Customer", ordering="full_name")
    def customer_display(self, obj):
        name = obj.full_name or (obj.user.username if obj.user else "Guest")
        return format_html("<strong>{}</strong>", name)

    @admin.display(description="Order Status", ordering="status")
    def order_status_badge(self, obj):
        colors = {
            "Pending": ("#fff3cd", "#856404"),
            "Confirmed": ("#d1ecf1", "#0c5460"),
            "Processing": ("#e2e3e5", "#383d41"),
            "Packed": ("#d4edda", "#155724"),
            "Assigned": ("#cce5ff", "#004085"),
            "Accepted": ("#d1e7dd", "#0f5132"),
            "Picked Up": ("#ffeeba", "#856404"),
            "Out for Delivery": ("#f8d7da", "#721c24"),
            "Delivered": ("#d4edda", "#155724"),
            "Delivery Failed": ("#f8d7da", "#842029"),
            "Cancelled": ("#e2e3e5", "#6c757d"),
        }
        bg, text = colors.get(obj.status, ("#eee", "#333"))
        return format_html(
            '<span style="background:{}; color:{}; padding:4px 9px; border-radius:12px; font-size:12px; font-weight:700;">{}</span>',
            bg, text, obj.status
        )

    @admin.display(description="Delivery Partner")
    def delivery_partner_display(self, obj):
        if hasattr(obj, "delivery_assignment") and obj.delivery_assignment:
            assignment = obj.delivery_assignment
            partner = assignment.partner
            reassign_url = reverse("admin:orders_order_assign_delivery", args=[obj.id])
            return format_html(
                "<strong>{}</strong><br><small>Status: <b>{}</b></small><br>"
                "<a href='{}' style='font-size:11px; color:#1a73e8; text-decoration:underline;'>🔄 Reassign</a>",
                partner.get_display_name(),
                assignment.status,
                reassign_url,
            )
        assign_url = reverse("admin:orders_order_assign_delivery", args=[obj.id])
        return format_html(
            '<a href="{}" class="button" style="padding:3px 9px; font-size:11px; background:#a52d55; color:#fff; border-radius:4px; text-decoration:none;">+ Assign Partner</a>',
            assign_url
        )

    @admin.display(description="Delivery Management")
    def delivery_management_display(self, obj):
        assign_url = reverse("admin:orders_order_assign_delivery", args=[obj.id])
        cancel_url = reverse("admin:orders_order_cancel_assignment", args=[obj.id])

        if hasattr(obj, "delivery_assignment") and obj.delivery_assignment:
            assign = obj.delivery_assignment
            p = assign.partner
            history_url = reverse("admin:delivery_deliverypartner_history", args=[p.id])
            html = f"""
            <div style="background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; padding:16px; max-width:650px;">
                <h4 style="margin:0 0 10px 0; color:#333;">🚚 Assigned Partner: <strong>{p.get_display_name()}</strong></h4>
                <p style="margin:4px 0;"><strong>Phone:</strong> {p.phone} &nbsp;|&nbsp; <strong>Vehicle:</strong> {p.get_vehicle_type_display()} ({p.vehicle_number or 'No plate'})</p>
                <p style="margin:4px 0;"><strong>Assignment Status:</strong> <span style="font-weight:bold; color:#004085;">{assign.status}</span></p>
                <p style="margin:4px 0;"><strong>Assigned At:</strong> {assign.assigned_at.strftime('%d %b %Y, %H:%M')}</p>
            """
            if assign.rejection_reason:
                html += f"<p style='color:#c5221f; margin:4px 0;'><strong>Rejection Reason:</strong> {assign.rejection_reason}</p>"
            if assign.failure_reason:
                html += f"<p style='color:#c5221f; margin:4px 0;'><strong>Failure Reason:</strong> {assign.failure_reason}</p>"

            html += f"""
                <div style="margin-top:14px; display:flex; gap:10px;">
                    <a href="{assign_url}" class="button" style="background:#1a73e8; color:white; padding:6px 14px; border-radius:4px; text-decoration:none;">🔄 Reassign to Another Partner</a>
                    <a href="{cancel_url}" class="button" style="background:#dc3545; color:white; padding:6px 14px; border-radius:4px; text-decoration:none;" onclick="return confirm('Cancel this delivery assignment?');">❌ Cancel Assignment</a>
                    <a href="{history_url}" class="button" style="background:#6c757d; color:white; padding:6px 14px; border-radius:4px; text-decoration:none;">Partner History</a>
                </div>
            </div>
            """
            return mark_safe(html)

        return format_html(
            '<div style="padding:10px 0;">'
            '<p style="color:#666; margin:0 0 10px 0;">No delivery partner is currently assigned to this order.</p>'
            '<a href="{}" class="button" style="background:#a52d55; color:white; font-size:13px; font-weight:bold; padding:8px 18px; border-radius:6px; text-decoration:none;">'
            '🚚 ASSIGN DELIVERY PARTNER'
            '</a>'
            '</div>',
            assign_url
        )

    def assign_delivery_view(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        partners = DeliveryPartner.objects.filter(is_active=True).select_related("user")

        partner_list = []
        for p in partners:
            serves_pin = p.serves_pincode(order.pincode)
            partner_list.append({
                "partner": p,
                "serves_pin": serves_pin,
                "active_count": p.active_assignments_count(),
                "completed_count": p.completed_assignments_count(),
            })

        # Sort: first partners who serve the PIN code, then by active workload
        partner_list.sort(key=lambda item: (not item["serves_pin"], item["active_count"]))

        current_assignment = getattr(order, "delivery_assignment", None)

        if request.method == "POST":
            partner_id = request.POST.get("partner_id")
            notes = request.POST.get("notes", "").strip()

            if not partner_id:
                messages.error(request, "Please select a delivery partner.")
                return redirect("admin:orders_order_assign_delivery", order_id=order.id)

            selected_partner = get_object_or_404(DeliveryPartner, pk=partner_id, is_active=True)

            with transaction.atomic():
                old_status = order.status
                assignment, created = DeliveryAssignment.objects.get_or_create(
                    order=order,
                    defaults={
                        "partner": selected_partner,
                        "status": "Assigned",
                        "assigned_by": request.user,
                        "notes": notes,
                    }
                )

                if not created:
                    assignment.partner = selected_partner
                    assignment.status = "Assigned"
                    assignment.rejection_reason = ""
                    assignment.failure_reason = ""
                    assignment.assigned_by = request.user
                    assignment.notes = notes
                    assignment.save()

                # Update order status to Assigned
                order.status = "Assigned"
                order.save(update_fields=["status"])

                # Log status history
                OrderStatusHistory.objects.create(
                    order=order,
                    previous_status=old_status,
                    new_status="Assigned",
                    changed_by=request.user,
                    remarks=f"Assigned to {selected_partner.get_display_name()} ({selected_partner.phone}). {notes}".strip(),
                )

            messages.success(
                request,
                f"Order #{order.id} was successfully assigned to delivery partner {selected_partner.get_display_name()}."
            )
            return redirect("admin:orders_order_change", order.id)

        context = {
            **self.admin_site.each_context(request),
            "title": f"Assign Delivery Partner - Order #{order.id}",
            "order": order,
            "partner_list": partner_list,
            "current_assignment": current_assignment,
        }
        return render(request, "admin/orders/order/assign_delivery.html", context)

    def cancel_assignment_view(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        if hasattr(order, "delivery_assignment") and order.delivery_assignment:
            with transaction.atomic():
                assignment = order.delivery_assignment
                old_status = order.status
                assignment.status = "Cancelled"
                assignment.save(update_fields=["status", "updated_at"])

                order.status = "Confirmed"
                order.save(update_fields=["status"])

                OrderStatusHistory.objects.create(
                    order=order,
                    previous_status=old_status,
                    new_status="Confirmed",
                    changed_by=request.user,
                    remarks=f"Assignment to {assignment.partner.get_display_name()} was cancelled by admin.",
                )

            messages.success(request, f"Delivery assignment for Order #{order.id} was cancelled. Order is now unassigned.")
        else:
            messages.warning(request, f"Order #{order.id} has no active assignment to cancel.")

        return redirect("admin:orders_order_change", order.id)

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = Order.objects.filter(pk=obj.pk).values_list("status", flat=True).first()

        super().save_model(request, obj, form, change)

        if old_status is not None and old_status != obj.status:
            OrderStatusHistory.objects.create(
                order=obj,
                previous_status=old_status,
                new_status=obj.status,
                changed_by=request.user,
                remarks="Status updated directly via Admin Panel",
            )

            if obj.user_id is not None:
                transaction.on_commit(
                    lambda user_id=obj.user_id,
                           order_id=obj.pk,
                           new_status=obj.status:
                        send_order_status_notification(
                            user_id,
                            order_id,
                            new_status,
                        )
                )
