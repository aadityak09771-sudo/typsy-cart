import os
from decimal import Decimal
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    image_url = models.CharField(max_length=500, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if self.image and self.image_url and self.image_url.startswith("/media/"):
            self.image_url = ""
        super().save(*args, **kwargs)

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()

    def get_image_url(self):
        if self.image:
            try:
                return self.image.url
            except Exception:
                pass
        if self.image_url:
            return self.image_url
        slug_map = {
            "period-care": "/static/home/images/cat-period-care.jpg",
            "personal-safety": "/static/home/images/cat-personal-safety.jpg",
            "safety": "/static/home/images/cat-personal-safety.jpg",
            "personal-care": "/static/home/images/cat-personal-care.jpg",
            "daily-essentials": "/static/home/images/cat-daily-essentials.jpg",
            "groceries": "/static/home/images/cat-groceries.jpg",
        }
        return slug_map.get(self.slug, "/static/home/images/tipsycart-logo.png")


class Subcategory(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="subcategories",
    )
    name = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=120, blank=True)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="subcategories/", blank=True, null=True)
    image_url = models.CharField(max_length=500, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Subcategory"
        verbose_name_plural = "Subcategories"
        ordering = ["category", "display_order", "name"]
        unique_together = [["category", "name"]]

    def __str__(self):
        return f"{self.category.name} → {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.category.name}-{self.name}")
        if self.image and self.image_url and self.image_url.startswith("/media/"):
            self.image_url = ""
        super().save(*args, **kwargs)

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()

    def get_image_url(self):
        if self.image:
            try:
                return self.image.url
            except Exception:
                pass
        if self.image_url:
            return self.image_url
        if self.category:
            return self.category.get_image_url()
        return "/static/home/images/tipsycart-logo.png"


class Product(models.Model):
    CATEGORY_CHOICES = [
        ("Period Care", "Period Care"),
        ("Safety", "Personal Safety"),
        ("Personal Care", "Personal Care"),
        ("Daily Essentials", "Daily Essentials"),
        ("Groceries", "Groceries"),
    ]

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage (%)"),
        ("fixed", "Fixed Amount (₹)"),
    ]

    product_number = models.CharField(
        max_length=60,
        blank=True,
        default="",
        db_index=True,
        help_text="Product Number / SKU code (e.g. TC-0001)",
    )

    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)

    # Legacy category CharField maintained for 100% backward compatibility
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        db_index=True,
    )
    subcategory = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
    )

    # New relational foreign keys linking to dynamic Category and Subcategory
    category_ref = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    subcategory_ref = models.ForeignKey(
        Subcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    brand = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    # Selling price (final price charged to customer)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Final selling price in INR (used in cart and checkout)",
    )

    # Original MRP before discount
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original MRP before discount in INR",
    )

    # Discount settings
    discount_enabled = models.BooleanField(
        default=False,
        help_text="Enable promotional discount on this product",
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default="percentage",
        blank=True,
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Discount percentage (e.g. 15 for 15%) or fixed discount amount in INR",
    )

    stock = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(
        default=True,
        help_text="Product availability (auto-disabled if stock is 0)",
    )

    # Direct image file upload + URL fallback
    image = models.ImageField(
        upload_to="products/",
        blank=True,
        null=True,
        help_text="Upload image file directly from computer",
    )
    image_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="URL or static path (e.g. /static/home/images/products/...)",
    )

    is_featured = models.BooleanField(
        default=False,
        help_text="Display in Featured Products section on Homepage and Shop",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["is_featured", "is_active"]),
            models.Index(fields=["is_available", "stock"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.product_number or f'ID {self.id}'})"

    def save(self, *args, **kwargs):
        # 1. Sync category names
        if self.category_ref:
            self.category = self.category_ref.name
        if self.subcategory_ref:
            self.subcategory = self.subcategory_ref.name

        # Clean up redundant /media/ string from external image_url if a local image exists
        if self.image and self.image_url and self.image_url.startswith("/media/"):
            self.image_url = ""

        # 2. Original price fallback
        if self.original_price is None or self.original_price <= 0:
            self.original_price = self.price

        # 4. Calculate selling price if discount is enabled
        if self.discount_enabled and self.discount_value and self.discount_value > 0 and self.original_price:
            if self.discount_type == "percentage":
                pct = min(Decimal("99.00"), max(Decimal("0.00"), self.discount_value))
                calc_price = self.original_price * (Decimal("100.00") - pct) / Decimal("100.00")
                self.price = max(Decimal("1.00"), round(calc_price, 2))
            else:
                calc_price = self.original_price - self.discount_value
                self.price = max(Decimal("1.00"), round(calc_price, 2))

        # 5. Availability sync with stock
        if self.stock == 0:
            self.is_available = False

        super().save(*args, **kwargs)

    def get_image_url(self):
        if self.image:
            try:
                return self.image.url
            except Exception:
                pass
        if self.image_url:
            return self.image_url
        if self.category_ref:
            return self.category_ref.get_image_url()
        return "/static/home/images/tipsycart-logo.png"

    @property
    def discount_percentage(self):
        if not self.discount_enabled or not self.original_price or self.original_price <= self.price:
            return 0
        diff = self.original_price - self.price
        return int(round((diff / self.original_price) * 100))

    @property
    def savings_amount(self):
        if not self.discount_enabled or not self.original_price or self.original_price <= self.price:
            return Decimal("0.00")
        return round(self.original_price - self.price, 2)
