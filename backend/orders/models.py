
from django.conf import settings
from django.db import models
from products.models import Product


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart - {self.user}"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product} × {self.quantity}"

    @property
    def subtotal(self):
        return self.product.price * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Processing", "Processing"),
        ("Packed", "Packed"),
        ("Assigned", "Assigned"),
        ("Accepted", "Accepted"),
        ("Picked Up", "Picked Up"),
        ("Out for Delivery", "Out for Delivery"),
        ("Delivered", "Delivered"),
        ("Delivery Failed", "Delivery Failed"),
        ("Cancelled", "Cancelled"),
    ]

    PAYMENT_CHOICES = [
        ("COD", "Cash on Delivery"),
        ("UPI", "UPI / Online Payment"),
        ("Pending", "Payment Pending"),
    ]

    # Logged-in customers ke liye user linked hoga.
    # Guest checkout ke liye user None ho sakta hai.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )

    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending",
    )

    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_CHOICES,
        default="COD",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        customer = self.full_name or (
            str(self.user) if self.user else "Guest"
        )
        return f"Order #{self.id} - {customer}"

    @property
    def step_info(self):
        """
        Calculates the 6-step progress lifecycle for the order.
        Returns:
            - step_num (1..6)
            - total_steps (6)
            - remaining (5..0)
            - status_label
            - next_step_label
            - percent (5% to 100%)
            - is_delivered (bool)
            - is_cancelled (bool)
            - steps (list of dicts with step name, icon, desc, state)
        """
        current_status = self.status
        try:
            if hasattr(self, "delivery_assignment") and self.delivery_assignment:
                assign_status = self.delivery_assignment.status
                if assign_status == "Delivered":
                    current_status = "Delivered"
                elif assign_status == "Out for Delivery":
                    current_status = "Out for Delivery"
                elif assign_status == "Picked Up":
                    current_status = "Picked Up"
                elif assign_status in ("Assigned", "Accepted") and current_status not in (
                    "Picked Up", "Out for Delivery", "Delivered"
                ):
                    current_status = "Assigned"
        except Exception:
            pass

        if current_status == "Cancelled":
            return {
                "step_num": 0,
                "total_steps": 6,
                "remaining": 0,
                "status_label": "Order Cancelled",
                "next_step_label": "None",
                "percent": 0,
                "is_cancelled": True,
                "is_delivered": False,
                "steps": [],
            }

        if current_status == "Delivered":
            step_num = 6
            status_label = "Delivered at Doorstep"
            next_step_label = "Order Completed"
            percent = 100
        elif current_status == "Out for Delivery":
            step_num = 5
            status_label = "Out for Delivery (On The Way)"
            next_step_label = "Doorstep Handover"
            percent = 80
        elif current_status == "Picked Up":
            step_num = 4
            status_label = "Picked Up from Store"
            next_step_label = "Out for Delivery"
            percent = 60
        elif current_status in ("Assigned", "Accepted"):
            step_num = 3
            status_label = "Delivery Partner Assigned"
            next_step_label = "Pickup from Hub"
            percent = 40
        elif current_status in ("Confirmed", "Processing", "Packed"):
            step_num = 2
            status_label = "Order Confirmed & Packing"
            next_step_label = "Delivery Partner Assignment"
            percent = 20
        else:  # Pending or newly placed
            step_num = 1
            status_label = "Order Placed"
            next_step_label = "Store Confirmation & Packing"
            percent = 8

        remaining = max(0, 6 - step_num)

        step_definitions = [
            {"num": 1, "name": "Order Placed", "desc": "Order placed successfully by customer", "icon": "🛍️"},
            {"num": 2, "name": "Store Confirmed", "desc": "Confirmed & packed by store team", "icon": "📋"},
            {"num": 3, "name": "Partner Assigned", "desc": "Assigned to nearest delivery driver", "icon": "🛵"},
            {"num": 4, "name": "Picked Up", "desc": "Order collected from hub and in transit", "icon": "📦"},
            {"num": 5, "name": "Out for Delivery", "desc": "Driver is on the way to your address", "icon": "🚚"},
            {"num": 6, "name": "Delivered", "desc": "Safely delivered at customer doorstep", "icon": "🎉"},
        ]

        steps = []
        for s in step_definitions:
            if s["num"] < step_num:
                state = "completed"
            elif s["num"] == step_num:
                state = "active" if step_num < 6 else "completed"
            else:
                state = "pending"
            steps.append({**s, "state": state})

        return {
            "step_num": step_num,
            "total_steps": 6,
            "remaining": remaining,
            "status_label": status_label,
            "next_step_label": next_step_label,
            "percent": percent,
            "is_cancelled": False,
            "is_delivered": (step_num == 6),
            "steps": steps,
        }

    @property
    def eta_display(self):
        """Returns the dynamic ETA time and subtext based on live assignment status."""
        current_status = self.status
        try:
            if hasattr(self, "delivery_assignment") and self.delivery_assignment:
                assign_status = self.delivery_assignment.status
                if assign_status == "Delivered":
                    return {"time": "✅ Delivered", "sub": "Order delivered safely to your location"}
                elif assign_status == "Out for Delivery":
                    return {"time": "⚡ In 10 - 15 Mins", "sub": "Driver is on the way! Please keep your phone reachable"}
                elif assign_status == "Picked Up":
                    return {"time": "📦 In 15 - 25 Mins", "sub": "Parcel picked up from hub and in transit"}
                elif assign_status in ("Assigned", "Accepted"):
                    return {"time": "🚚 In 25 - 35 Mins", "sub": "Driver dispatched to store to collect your parcel"}
        except Exception:
            pass

        if current_status == "Delivered":
            return {"time": "✅ Delivered", "sub": "Order delivered safely to your location"}
        elif current_status == "Out for Delivery":
            return {"time": "⚡ In 10 - 15 Mins", "sub": "Driver is on the way! Please keep your phone reachable"}
        elif current_status == "Picked Up":
            return {"time": "📦 In 15 - 25 Mins", "sub": "Parcel picked up from hub and in transit"}
        elif current_status in ("Assigned", "Accepted"):
            return {"time": "🚚 In 25 - 35 Mins", "sub": "Driver dispatched to store to collect your parcel"}
        elif current_status in ("Confirmed", "Processing", "Packed", "Pending"):
            return {"time": "🕒 In 30 - 45 Mins", "sub": "Store is packing your everyday essentials"}
        elif current_status == "Cancelled":
            return {"time": "❌ Cancelled", "sub": "This order was cancelled"}
        return {"time": "🕒 Expected Today", "sub": "Processing your delivery"}


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
    )

    product_name = models.CharField(max_length=200)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    quantity = models.PositiveIntegerField()

    @property
    def subtotal(self):
        return self.price * self.quantity

    @property
    def image_url(self):
        if self.product and getattr(self.product, "image_url", None):
            return self.product.image_url
        return ""

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"
