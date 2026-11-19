from django.conf import settings
from django.db import models


class DeliveryPartner(models.Model):

    VEHICLE_CHOICES = [
        ("scooter", "Scooter"),
        ("bike", "Motorcycle / Bike"),
        ("car", "Car"),
        ("electric_scooter", "Electric Scooter"),
        ("van", "Delivery Van"),
        ("other", "Other / Walking"),
    ]

    AVAILABILITY_CHOICES = [
        ("available", "Available"),
        ("busy", "Busy / On Delivery"),
        ("offline", "Offline"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delivery_profile",
    )

    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    profile_photo = models.FileField(
        upload_to="delivery_partners/",
        null=True,
        blank=True,
    )

    vehicle_type = models.CharField(
        max_length=30,
        choices=VEHICLE_CHOICES,
        default="scooter",
    )
    vehicle_number = models.CharField(max_length=30, blank=True)

    service_pincodes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated PIN codes served by this partner (e.g. 110001, 110002)",
    )

    availability_status = models.CharField(
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default="available",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def partner_id(self):
        return f"DP-{self.id:04d}" if self.id else "DP-NEW"

    def __str__(self):
        name = self.full_name or self.user.get_full_name() or self.user.username
        return f"[{self.partner_id}] {name} ({self.phone})"

    def get_display_name(self):
        return self.full_name or self.user.get_full_name() or self.user.username

    def active_assignments_count(self):
        return self.assignments.filter(
            status__in=["Assigned", "Accepted", "Picked Up", "Out for Delivery"]
        ).count()

    def completed_assignments_count(self):
        return self.assignments.filter(status="Delivered").count()

    def failed_assignments_count(self):
        return self.assignments.filter(status__in=["Delivery Failed", "Rejected"]).count()

    def serves_pincode(self, pincode):
        if not self.service_pincodes:
            return True  # If no specific pincodes set, partner can serve any pincode
        allowed = [p.strip() for p in self.service_pincodes.split(",") if p.strip()]
        return str(pincode).strip() in allowed


class DeliveryAssignment(models.Model):

    STATUS_CHOICES = [
        ("Assigned", "Assigned"),
        ("Accepted", "Accepted"),
        ("Rejected", "Rejected"),
        ("Picked Up", "Picked Up"),
        ("Out for Delivery", "Out for Delivery"),
        ("Delivered", "Delivered"),
        ("Delivery Failed", "Delivery Failed"),
        ("Cancelled", "Cancelled"),
    ]

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="delivery_assignment",
    )

    partner = models.ForeignKey(
        DeliveryPartner,
        on_delete=models.PROTECT,
        related_name="assignments",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="Assigned",
    )

    rejection_reason = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_deliveries",
    )

    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.order_id} - {self.partner.get_display_name()} [{self.status}]"


class OrderStatusHistory(models.Model):

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    previous_status = models.CharField(max_length=50, blank=True, null=True, default="")
    new_status = models.CharField(max_length=50)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
    )

    remarks = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order Status History"
        verbose_name_plural = "Order Status Histories"

    def save(self, *args, **kwargs):
        if self.previous_status is None:
            self.previous_status = ""
        super().save(*args, **kwargs)

    def __str__(self):
        prev = self.previous_status or "Initial"
        return f"Order #{self.order_id}: {prev} -> {self.new_status}"
