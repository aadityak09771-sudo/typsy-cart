from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.urls import reverse
from .models import PushDevice, EmailOTP, Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "username",
        "customer_name",
        "email",
        "orders_count_badge",
        "is_active",
        "date_joined",
    )
    list_display_links = ("id", "username")
    list_filter = ("is_active", "date_joined")
    search_fields = ("username", "first_name", "last_name", "email")
    list_editable = ("is_active",)
    readonly_fields = ("username", "email", "date_joined", "last_login", "order_history_display")

    fieldsets = (
        ("Customer Account", {"fields": ("username", "first_name", "last_name", "email", "is_active")}),
        ("Security & Login Timestamps", {"fields": ("date_joined", "last_login")}),
        ("Customer Order History", {"fields": ("order_history_display",)}),
    )

    def get_queryset(self, request):
        # Exclude internal staff/superusers so only real customers are listed
        return super().get_queryset(request).filter(is_staff=False, is_superuser=False)

    @admin.display(description="Full Name", ordering="first_name")
    def customer_name(self, obj):
        return obj.get_full_name() or obj.first_name or "—"

    @admin.display(description="Orders Placed")
    def orders_count_badge(self, obj):
        count = obj.orders.count()
        bg = "#e0f2fe" if count > 0 else "#f3f4f6"
        color = "#0369a1" if count > 0 else "#6b7280"
        return format_html(
            '<span style="background: {}; color: {}; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 11px;">{} orders</span>',
            bg, color, count,
        )

    @admin.display(description="Recent Orders")
    def order_history_display(self, obj):
        orders = obj.orders.all().order_by("-created_at")[:10]
        if not orders.exists():
            return "No orders placed yet by this customer."
        rows_data = []
        for o in orders:
            order_url = reverse("admin:orders_order_change", args=[o.id])
            status_color = "#15803d" if o.status == "Delivered" else ("#b91c1c" if o.status == "Cancelled" else "#b45309")
            rows_data.append((
                order_url,
                o.id,
                o.created_at.strftime("%d %b %Y, %H:%M"),
                o.total_amount,
                status_color,
                o.status,
                o.payment_method,
            ))
        rows_html = format_html_join(
            "",
            '<tr>'
            '<td style="padding: 6px 12px;"><a href="{}" style="font-weight: 700; color: #a51655;">#{}</a></td>'
            '<td style="padding: 6px 12px;">{}</td>'
            '<td style="padding: 6px 12px; font-weight: 700;">₹{}</td>'
            '<td style="padding: 6px 12px; color: {}; font-weight: 700;">{}</td>'
            '<td style="padding: 6px 12px;">{}</td>'
            '</tr>',
            rows_data,
        )
        return format_html(
            '<table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px;">'
            '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
            '<tr><th style="padding: 6px 12px; text-align: left;">Order ID</th>'
            '<th style="padding: 6px 12px; text-align: left;">Date</th>'
            '<th style="padding: 6px 12px; text-align: left;">Amount</th>'
            '<th style="padding: 6px 12px; text-align: left;">Status</th>'
            '<th style="padding: 6px 12px; text-align: left;">Payment</th></tr>'
            '</thead><tbody>{}</tbody></table>',
            rows_html,
        )

    def has_add_permission(self, request):
        return False


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "platform",
        "expo_push_token",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__username",
        "user__email",
        "expo_push_token",
    )
    list_filter = ("platform", "created_at")
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "purpose",
        "attempts",
        "max_attempts",
        "is_used",
        "ip_address",
        "created_at",
        "expires_at",
    )
    list_filter = ("purpose", "is_used", "created_at")
    search_fields = ("email", "ip_address")
    readonly_fields = ("otp_hash", "created_at")
    list_per_page = 50
