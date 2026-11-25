from decimal import Decimal
from django.db import models


class StoreSetting(models.Model):
    store_name = models.CharField(max_length=150, default="TipsyCart")
    tagline = models.CharField(max_length=200, default="Care • Comfort • Confidence")
    contact_email = models.EmailField(default="support@tipsycart.in")
    contact_phone = models.CharField(max_length=20, default="+91 98765 43210")
    store_address = models.TextField(default="Kanpur, Uttar Pradesh, India - 208001")
    instagram_url = models.URLField(blank=True, default="https://www.instagram.com/tipsycart7/")
    facebook_url = models.URLField(blank=True, default="")
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Flat delivery fee in INR")
    free_delivery_threshold = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("299.00"), help_text="Cart total above which delivery is free")
    is_store_open = models.BooleanField(default=True, help_text="Toggle store accepting orders")
    operating_hours = models.CharField(max_length=100, default="7:00 AM - 11:00 PM")
    announcement_text = models.CharField(max_length=255, blank=True, default="⚡ Fast 30-45 min delivery in Kanpur • Order your everyday essentials now!")
    updated_at = models.DateTimeField(auto_now=True)

    # Today's Deals Admin Controls
    DEALS_TIMER_MODES = [
        ("daily_midnight", "Daily Midnight Reset (24-Hour Cycle)"),
        ("fixed_datetime", "Fixed End Date & Time (Custom Offer Deadline)"),
    ]
    deals_title = models.CharField(
        max_length=100,
        default="Today's Deals",
        help_text="Heading shown on the homepage for deals section"
    )
    deals_timer_mode = models.CharField(
        max_length=30,
        choices=DEALS_TIMER_MODES,
        default="daily_midnight",
        help_text="Choose how the countdown timer operates on the homepage"
    )
    deals_end_datetime = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Custom deal expiry date & time (used when Fixed End Date & Time is selected)"
    )

    class Meta:
        verbose_name = "Store Settings"
        verbose_name_plural = "Store Settings"

    def __str__(self):
        return f"{self.store_name} Settings ({'Open' if self.is_store_open else 'Closed'})"

    @classmethod
    def get_settings(cls):
        setting = cls.objects.first()
        if not setting:
            setting = cls.objects.create()
        return setting


class HeroBanner(models.Model):
    title = models.CharField(max_length=200, default="Everything you need, all in one cart.")
    subtitle = models.CharField(max_length=300, blank=True, default="From fresh groceries to personal care and safety essentials, shop what matters with TipsyCart.")
    badge_text = models.CharField(max_length=100, blank=True, default="KANPUR'S HYPERLOCAL LIFESTYLE STORE")
    image = models.ImageField(upload_to="banners/", blank=True, null=True, help_text="Upload custom banner image")
    image_url = models.CharField(max_length=500, blank=True, default="/static/home/images/shop-banner-desktop.png")
    button_text = models.CharField(max_length=50, default="Explore Products")
    button_link = models.CharField(max_length=200, default="/shop/")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "-created_at"]
        verbose_name = "Homepage Banner"
        verbose_name_plural = "Homepage Banners"

    def __str__(self):
        return f"Banner #{self.id}: {self.title[:50]}"

    def save(self, *args, **kwargs):
        if self.image and self.image_url and self.image_url.startswith("/media/"):
            self.image_url = ""
        super().save(*args, **kwargs)

    def get_image_url(self):
        if self.image:
            try:
                return self.image.url
            except Exception:
                pass
        return self.image_url or "/static/home/images/shop-banner-desktop.png"


class FAQItem(models.Model):
    CATEGORY_CHOICES = [
        ("General", "General"),
        ("Ordering & Delivery", "Ordering & Delivery"),
        ("Payments", "Payments"),
        ("Returns & Refunds", "Returns & Refunds"),
        ("Account & Security", "Account & Security"),
    ]

    question = models.CharField(max_length=300)
    answer = models.TextField()
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default="General")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "display_order", "id"]
        verbose_name = "FAQ Item"
        verbose_name_plural = "FAQ Items"

    def __str__(self):
        return f"[{self.category}] {self.question[:60]}"
