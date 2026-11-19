from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import DeliveryPartner, DeliveryAssignment, OrderStatusHistory

User = get_user_model()


class DeliveryPartnerForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        required=False,
        help_text="Login username for this delivery partner.",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Set or change partner login password (minimum 8 characters).",
    )

    class Meta:
        model = DeliveryPartner
        fields = [
            "full_name",
            "phone",
            "email",
            "address",
            "profile_photo",
            "vehicle_type",
            "vehicle_number",
            "service_pincodes",
            "availability_status",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user:
            self.fields["username"].initial = self.instance.user.username
            self.fields["email"].initial = self.instance.email or self.instance.user.email
            self.fields["full_name"].initial = self.instance.full_name or self.instance.user.get_full_name()
        else:
            self.fields["username"].required = True
            self.fields["password"].required = True

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if not self.instance.pk and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_password(self):
        password = self.cleaned_data.get("password", "").strip()
        if not self.instance.pk and len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")
        return password

    def save(self, commit=True):
        partner = super().save(commit=False)
        username = self.cleaned_data.get("username", "").strip()
        password = self.cleaned_data.get("password", "").strip()
        email = self.cleaned_data.get("email", "").strip()
        full_name = self.cleaned_data.get("full_name", "").strip()

        with transaction.atomic():
            if not partner.pk:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                )
                if full_name:
                    parts = full_name.split(None, 1)
                    user.first_name = parts[0]
                    if len(parts) > 1:
                        user.last_name = parts[1]
                user.is_staff = False
                user.is_superuser = False
                user.save()
                partner.user = user
            else:
                user = partner.user
                if email and user.email != email:
                    user.email = email
                if full_name:
                    parts = full_name.split(None, 1)
                    user.first_name = parts[0]
                    if len(parts) > 1:
                        user.last_name = parts[1]
                if password:
                    user.set_password(password)
                user.save()

            if commit:
                partner.save()

        return partner


@admin.register(DeliveryPartner)
class DeliveryPartnerAdmin(admin.ModelAdmin):
    form = DeliveryPartnerForm
    list_display = (
        "id",
        "partner_name_display",
        "phone",
        "vehicle_badge",
        "service_areas_display",
        "availability_badge",
        "status_badge",
        "active_deliveries_badge",
        "completed_deliveries_badge",
        "actions_display",
    )

    list_filter = (
        "is_active",
        "availability_status",
        "vehicle_type",
        "created_at",
    )

    search_fields = (
        "id",
        "full_name",
        "user__username",
        "user__email",
        "phone",
        "service_pincodes",
        "vehicle_number",
    )

    ordering = ("-created_at",)
    list_per_page = 20

    actions = ["activate_partners", "deactivate_partners", "set_available", "set_offline"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:partner_id>/history/",
                self.admin_site.admin_view(self.partner_history_view),
                name="delivery_deliverypartner_history",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Partner Name", ordering="full_name")
    def partner_name_display(self, obj):
        name = obj.get_display_name()
        return format_html("<strong>{}</strong><br><small style='color:#666;'>User: @{}</small>", name, obj.user.username)

    @admin.display(description="Vehicle")
    def vehicle_badge(self, obj):
        v_icon = {
            "scooter": "🛵",
            "bike": "🏍️",
            "electric_scooter": "⚡🛵",
            "van": "🚐",
            "other": "🚶",
        }.get(obj.vehicle_type, "🚚")
        plate = f" ({obj.vehicle_number})" if obj.vehicle_number else ""
        return f"{v_icon} {obj.get_vehicle_type_display()}{plate}"

    @admin.display(description="Service Areas")
    def service_areas_display(self, obj):
        if not obj.service_pincodes:
            return mark_safe("<span style='color:#888;'>All Areas (Global)</span>")
        return format_html("<span title='{}'>{}</span>", obj.service_pincodes, obj.service_pincodes[:25] + ("..." if len(obj.service_pincodes) > 25 else ""))

    @admin.display(description="Availability")
    def availability_badge(self, obj):
        colors = {
            "available": ("#e6f4ea", "#137333", "🟢 Available"),
            "busy": ("#fef7e0", "#b06000", "🟡 Busy"),
            "offline": ("#f1f3f4", "#5f6368", "⚪ Offline"),
        }
        bg, text, label = colors.get(obj.availability_status, ("#eee", "#333", obj.availability_status))
        return format_html(
            '<span style="background:{}; color:{}; padding:4px 8px; border-radius:12px; font-size:12px; font-weight:600;">{}</span>',
            bg, text, label
        )

    @admin.display(description="Account")
    def status_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span style="color:#137333; font-weight:bold;">Active</span>')
        return mark_safe('<span style="color:#d93025; font-weight:bold;">Inactive</span>')

    @admin.display(description="Active Orders")
    def active_deliveries_badge(self, obj):
        count = obj.active_assignments_count()
        if count > 0:
            return format_html(
                '<a href="{}?partner__id__exact={}&status__in=Assigned,Accepted,Picked+Up,Out+for+Delivery" style="background:#e8f0fe; color:#1a73e8; padding:3px 8px; border-radius:10px; font-weight:bold; text-decoration:none;">{} active</a>',
                reverse("admin:delivery_deliveryassignment_changelist"),
                obj.id,
                count
            )
        return "0"

    @admin.display(description="Completed")
    def completed_deliveries_badge(self, obj):
        count = obj.completed_assignments_count()
        return format_html(
            '<a href="{}?partner__id__exact={}&status__exact=Delivered" style="color:#137333; font-weight:600; text-decoration:none;">{} delivered</a>',
            reverse("admin:delivery_deliveryassignment_changelist"),
            obj.id,
            count
        )

    @admin.display(description="Actions")
    def actions_display(self, obj):
        history_url = reverse("admin:delivery_deliverypartner_history", args=[obj.id])
        return format_html(
            '<a href="{}" class="button" style="padding:3px 8px; font-size:11px;">Delivery History</a>',
            history_url
        )

    @admin.action(description="Activate selected delivery partners")
    def activate_partners(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} delivery partner(s) activated successfully.", messages.SUCCESS)

    @admin.action(description="Deactivate selected delivery partners")
    def deactivate_partners(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} delivery partner(s) deactivated.", messages.WARNING)

    @admin.action(description="Mark selected partners as Available")
    def set_available(self, request, queryset):
        queryset.update(availability_status="available")
        self.message_user(request, "Selected partners marked as Available.", messages.SUCCESS)

    @admin.action(description="Mark selected partners as Offline")
    def set_offline(self, request, queryset):
        queryset.update(availability_status="offline")
        self.message_user(request, "Selected partners marked as Offline.", messages.SUCCESS)

    def partner_history_view(self, request, partner_id):
        partner = get_object_or_404(DeliveryPartner, pk=partner_id)
        assignments = (
            DeliveryAssignment.objects.filter(partner=partner)
            .select_related("order")
            .order_by("-assigned_at")
        )
        context = {
            **self.admin_site.each_context(request),
            "title": f"Delivery History - {partner.get_display_name()}",
            "partner": partner,
            "assignments": assignments,
            "total_count": assignments.count(),
            "active_count": partner.active_assignments_count(),
            "completed_count": partner.completed_assignments_count(),
            "failed_count": partner.failed_assignments_count(),
        }
        return render(request, "admin/delivery/partner_history.html", context)


@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_link",
        "customer_info",
        "partner_link",
        "assignment_status_badge",
        "assigned_at",
        "delivered_at",
    )

    list_filter = (
        "status",
        "assigned_at",
        "partner__is_active",
        "partner__vehicle_type",
    )

    search_fields = (
        "order__id",
        "order__full_name",
        "order__phone",
        "order__pincode",
        "partner__full_name",
        "partner__phone",
        "partner__user__username",
    )

    ordering = ("-assigned_at",)
    list_per_page = 25

    readonly_fields = (
        "assigned_at",
        "accepted_at",
        "picked_up_at",
        "delivered_at",
        "updated_at",
    )

    @admin.display(description="Order")
    def order_link(self, obj):
        url = reverse("admin:orders_order_change", args=[obj.order_id])
        return format_html('<a href="{}"><strong>Order #{}</strong></a><br>₹{} ({})', url, obj.order_id, obj.order.total_amount, obj.order.payment_method)

    @admin.display(description="Customer")
    def customer_info(self, obj):
        return format_html(
            "<strong>{}</strong><br>📞 {}<br><small>PIN: {}</small>",
            obj.order.full_name,
            obj.order.phone,
            obj.order.pincode,
        )

    @admin.display(description="Assigned Partner")
    def partner_link(self, obj):
        url = reverse("admin:delivery_deliverypartner_change", args=[obj.partner_id])
        return format_html('<a href="{}"><strong>{}</strong></a><br>📞 {}', url, obj.partner.get_display_name(), obj.partner.phone)

    @admin.display(description="Status")
    def assignment_status_badge(self, obj):
        colors = {
            "Assigned": ("#e8f0fe", "#1a73e8"),
            "Accepted": ("#e6f4ea", "#137333"),
            "Picked Up": ("#fef7e0", "#b06000"),
            "Out for Delivery": ("#feefe3", "#c5221f"),
            "Delivered": ("#ceead6", "#0d652d"),
            "Delivery Failed": ("#fce8e6", "#c5221f"),
            "Rejected": ("#fce8e6", "#c5221f"),
            "Cancelled": ("#f1f3f4", "#5f6368"),
        }
        bg, text = colors.get(obj.status, ("#eee", "#333"))
        return format_html(
            '<span style="background:{}; color:{}; padding:4px 9px; border-radius:12px; font-size:12px; font-weight:700;">{}</span>',
            bg, text, obj.status
        )


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_link",
        "status_transition",
        "changed_by",
        "created_at",
        "remarks",
    )
    list_filter = ("new_status", "created_at")
    search_fields = ("order__id", "order__full_name", "remarks", "changed_by__username")
    ordering = ("-created_at",)
    list_per_page = 30

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Order")
    def order_link(self, obj):
        url = reverse("admin:orders_order_change", args=[obj.order_id])
        return format_html('<a href="{}">Order #{}</a>', url, obj.order_id)

    @admin.display(description="Status Transition")
    def status_transition(self, obj):
        prev = obj.previous_status or "None"
        return format_html('<code>{}</code> &rarr; <strong>{}</strong>', prev, obj.new_status)
