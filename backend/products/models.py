import os
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils.text import slugify


def optimize_image_url(url):
    """
    Applies automatic format (WebP/AVIF) and automatic quality compression
    to Cloudinary URLs. Leaves non-Cloudinary and already-transformed URLs untouched.
    """
    if not url or not isinstance(url, str):
        return url
    if "res.cloudinary.com" in url and "/upload/" in url and "f_auto" not in url:
        return url.replace("/upload/", "/upload/f_auto,q_auto/")
    return url


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    image_url = models.CharField(max_length=500, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Homepage-specific display controls
    show_on_homepage = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Show or hide this category on the homepage category rail/grid."
    )
    homepage_display_order = models.PositiveIntegerField(
        default=0,
        help_text="Display order on the homepage (lower numbers appear first)."
    )
    HOMEPAGE_CARD_SIZES = [
        ("small", "Small"),
        ("medium", "Medium"),
        ("large", "Large"),
    ]
    homepage_card_size = models.CharField(
        max_length=20,
        choices=HOMEPAGE_CARD_SIZES,
        default="medium",
        help_text="Card size preference on the homepage."
    )
    HOMEPAGE_STYLES = [
        ("compact", "Compact Card"),
        ("standard", "Standard Card"),
        ("featured", "Featured Card"),
    ]
    homepage_display_style = models.CharField(
        max_length=20,
        choices=HOMEPAGE_STYLES,
        default="compact",
        help_text="Homepage visual card presentation style."
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Mark as a featured category on the homepage."
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "category"
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if self.image and self.image_url and self.image_url.startswith("/media/"):
            self.image_url = ""
        super().save(*args, **kwargs)

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()

    def get_image_url(self):
        slug = (self.slug or "").lower()
        name = (self.name or "").lower()
        slug_map = {
            "period-care": "/static/home/images/cat-period-care.jpg",
            "personal-safety": "/static/home/images/cat-personal-safety.jpg",
            "safety": "/static/home/images/cat-personal-safety.jpg",
            "personal-care": "/static/home/images/cat-personal-care.jpg",
            "daily-essentials": "/static/home/images/cat-daily-essentials.jpg",
            "groceries": "/static/home/images/cat-groceries.jpg",
            "plastic-items": "/static/home/images/cat-plastic-items.jpg",
        }
        fallback = slug_map.get(slug)
        if not fallback:
            if "plastic" in slug or "plastic" in name:
                fallback = "/static/home/images/cat-plastic-items.jpg"
            elif any(k in slug or k in name for k in ["period", "menstrual", "sanitary", "pad"]):
                fallback = "/static/home/images/cat-period-care.jpg"
            elif any(k in slug or k in name for k in ["safe", "alarm", "protect"]):
                fallback = "/static/home/images/cat-personal-safety.jpg"
            elif any(k in slug or k in name for k in ["personal", "skin", "body", "hair", "bath"]):
                fallback = "/static/home/images/cat-personal-care.jpg"
            elif any(k in slug or k in name for k in ["grocer", "vegetable", "fruit", "atta", "rice", "dal"]):
                fallback = "/static/home/images/cat-groceries.jpg"
            elif any(k in slug or k in name for k in ["daily", "essential", "household", "home", "clean"]):
                fallback = "/static/home/images/cat-daily-essentials.jpg"
            elif any(k in slug or k in name for k in ["sweet", "confectionery", "gajak", "chikki", "mithai"]):
                fallback = "/static/home/images/cat-daily-essentials.jpg"
            elif any(k in slug or k in name for k in ["fashion", "jewel", "apparel", "earring", "necklace"]):
                fallback = "/static/home/images/cat-daily-essentials.jpg"
            elif any(k in slug or k in name for k in ["cut", "meat", "fish", "chicken"]):
                fallback = "/static/home/images/cat-groceries.jpg"
            elif any(k in slug or k in name for k in ["mobile", "gadget", "accessori", "headphone"]):
                fallback = "/static/home/images/cat-daily-essentials.jpg"
            else:
                fallback = "/static/home/images/tipsycart-logo.png"

        if self.image:
            try:
                url = self.image.url
                if url and (url.startswith("http://") or url.startswith("https://")):
                    return optimize_image_url(url)
                if hasattr(self.image, "path"):
                    try:
                        if os.path.exists(self.image.path):
                            return optimize_image_url(url)
                    except (NotImplementedError, Exception):
                        return optimize_image_url(url)
                elif not hasattr(self.image, "path"):
                    return optimize_image_url(url)
            except Exception:
                pass
        if self.image_url and self.image_url.strip():
            url = self.image_url.strip()
            if url.startswith("http://") or url.startswith("https://"):
                return optimize_image_url(url)
            if url.startswith("/media/"):
                rel_path = url.replace("/media/", "").lstrip("/")
                full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                if os.path.exists(full_path):
                    return url
            else:
                return optimize_image_url(url)
        return fallback


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
            cat_name = self.category.name if self.category else "subcat"
            base_slug = slugify(f"{cat_name}-{self.name}") or "subcat"
            slug = base_slug
            counter = 1
            while Subcategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if self.image and self.image_url and self.image_url.startswith("/media/"):
            self.image_url = ""
        super().save(*args, **kwargs)

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()

    def get_image_url(self):
        if self.image:
            try:
                url = self.image.url
                if url and (url.startswith("http://") or url.startswith("https://")):
                    return optimize_image_url(url)
                if hasattr(self.image, "path"):
                    try:
                        if os.path.exists(self.image.path):
                            return optimize_image_url(url)
                    except (NotImplementedError, Exception):
                        return optimize_image_url(url)
                elif not hasattr(self.image, "path"):
                    return optimize_image_url(url)
            except Exception:
                pass
        if self.image_url and self.image_url.strip():
            url = self.image_url.strip()
            if url.startswith("http://") or url.startswith("https://"):
                return optimize_image_url(url)
            if url.startswith("/media/"):
                rel_path = url.replace("/media/", "").lstrip("/")
                full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                if os.path.exists(full_path):
                    return url
            else:
                return optimize_image_url(url)
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

    PRODUCT_TYPE_CHOICES = [
        ("simple", "Simple Product"),
        ("variable", "Variable Product"),
    ]

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage (%)"),
        ("fixed", "Fixed Amount (₹)"),
    ]

    UNIT_TYPE_CHOICES = [
        ("none", "Standard / Single Item"),
        ("weight", "Weight (mg, g, kg)"),
        ("volume", "Volume (ml, L)"),
        ("count", "Count / Pack (piece, pack, box, dozen, set)"),
        ("size", "Clothing Size (XS, S, M, L, XL, XXL)"),
        ("shoe_size", "Shoe Size"),
        ("custom", "Custom Unit"),
    ]

    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_TYPE_CHOICES,
        default="simple",
        db_index=True,
        help_text="Product Type: Simple (single price & stock) or Variable (multiple options)",
    )

    unit_type = models.CharField(
        max_length=20,
        choices=UNIT_TYPE_CHOICES,
        default="none",
        db_index=True,
        help_text="Selling unit category: Weight, Volume, Count/Pack, Clothing/Shoe size, etc.",
    )
    unit = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Unit name or abbreviation (e.g. g, kg, ml, L, piece, pack, box, dozen)",
    )
    unit_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Default/base numeric quantity (e.g. 250 for 250g, 1 for 1kg/1L)",
    )

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
    is_deal_of_the_day = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Prominently feature this product in Today's Deals section on Homepage",
    )
    is_active = models.BooleanField(default=True)

    # Linked similar products / styles (Meesho / Amazon style design/style switcher)
    similar_products = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=True,
        verbose_name="Similar Products / Styles",
        help_text="Link other styles, pendant designs, or similar products. They will appear as clickable style thumbnails on the product page.",
    )

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

        # 4. Smart discount sync (Manual Selling Price is KING):
        # If both original_price (MRP) and price (Selling Price) are provided:
        if self.original_price and self.price is not None:
            if self.original_price > self.price:
                self.discount_enabled = True
                self.discount_type = "percentage"
                diff = self.original_price - self.price
                self.discount_value = round((diff / self.original_price) * Decimal("100.00"), 2)
            elif self.discount_enabled and self.discount_value and self.discount_value > 0:
                # If price was not manually changed and discount is explicitly configured
                if self.discount_type == "percentage":
                    pct = min(Decimal("99.00"), max(Decimal("0.00"), self.discount_value))
                    calc_price = self.original_price * (Decimal("100.00") - pct) / Decimal("100.00")
                    self.price = max(Decimal("1.00"), round(calc_price, 2))
                else:
                    calc_price = self.original_price - self.discount_value
                    self.price = max(Decimal("1.00"), round(calc_price, 2))
            else:
                self.discount_enabled = False
                self.discount_value = Decimal("0.00")

        # 5. Availability sync with stock
        if self.stock == 0:
            self.is_available = False

        super().save(*args, **kwargs)

    def get_image_url(self):
        if self.image:
            try:
                url = self.image.url
                if url and (url.startswith("http://") or url.startswith("https://")):
                    return optimize_image_url(url)
                if hasattr(self.image, "path"):
                    try:
                        if os.path.exists(self.image.path):
                            return optimize_image_url(url)
                    except (NotImplementedError, Exception):
                        return optimize_image_url(url)
                elif not hasattr(self.image, "path"):
                    return optimize_image_url(url)
            except Exception:
                pass
            fname = os.path.basename(self.image.name or "")
            if fname and os.path.exists(os.path.join(settings.BASE_DIR, "Homepage/static/home/images/products", fname)):
                return f"/static/home/images/products/{fname}"

        if self.image_url and self.image_url.strip():
            url = self.image_url.strip()
            if url.startswith("http://") or url.startswith("https://"):
                return optimize_image_url(url)
            if url.startswith("/media/"):
                rel_path = url.replace("/media/", "").lstrip("/")
                full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                if os.path.exists(full_path):
                    return url
                fname = os.path.basename(rel_path)
                if fname and os.path.exists(os.path.join(settings.BASE_DIR, "Homepage/static/home/images/products", fname)):
                    return f"/static/home/images/products/{fname}"
            else:
                return optimize_image_url(url)

        if self.category_ref:
            return self.category_ref.get_image_url()
        cat_lower = (self.category or "").lower()
        if "plastic" in cat_lower:
            return "/static/home/images/cat-plastic-items.jpg"
        return "/static/home/images/tipsycart-logo.png"

    @property
    def discount_percentage(self):
        if not self.original_price or self.original_price <= self.price:
            return 0
        diff = self.original_price - self.price
        return int(round((diff / self.original_price) * 100))

    @property
    def savings_amount(self):
        if not self.original_price or self.original_price <= self.price:
            return Decimal("0.00")
        return round(self.original_price - self.price, 2)

    @property
    def is_variable(self):
        return self.product_type == "variable"

    @property
    def has_variants(self):
        if not self.is_variable:
            return False
        return self.variants.filter(is_active=True).exists()

    @property
    def min_price(self):
        if self.is_variable:
            active_vars = self.variants.filter(is_active=True)
            if active_vars.exists():
                return min(v.price for v in active_vars)
        return self.price

    @property
    def max_price(self):
        if self.is_variable:
            active_vars = self.variants.filter(is_active=True)
            if active_vars.exists():
                return max(v.price for v in active_vars)
        return self.price

    @property
    def total_stock(self):
        if self.is_variable:
            active_vars = self.variants.filter(is_active=True)
            if active_vars.exists():
                return sum(v.stock for v in active_vars)
        return self.stock

    @property
    def price_range_display(self):
        if self.is_variable and self.has_variants:
            p_min = self.min_price
            p_max = self.max_price
            if p_min == p_max:
                return f"₹{p_min}"
            return f"₹{p_min} – ₹{p_max}"
        return f"₹{self.price}"


    @property
    def unit_selector_label(self):
        labels = {
            "weight": "Select Weight",
            "volume": "Select Quantity / Volume",
            "count": "Select Pack / Quantity",
            "size": "Select Size",
            "shoe_size": "Select Shoe Size",
            "custom": "Select Option",
        }
        return labels.get(self.unit_type, "Select Option")

    def get_all_images(self, colour=None):
        """
        Returns list of image dicts:
        [{'url': ..., 'is_primary': bool, 'id': int, 'alt': str, 'source': str}]
        Prioritizes selected colour images, followed by product gallery images, and main cover.
        Guarantees that the primary image is first.
        """
        images = []
        seen = set()

        if colour:
            for cimg in colour.images.all().order_by("display_order", "id"):
                raw_url = cimg.get_image_url()
                url = optimize_image_url(raw_url) if raw_url else ""
                if url and url not in seen:
                    images.append({
                        "url": url,
                        "is_primary": cimg.is_primary,
                        "alt": f"{self.name} - {colour.name}",
                        "id": cimg.id,
                        "source": "colour",
                    })
                    seen.add(url)

        for gimg in self.gallery_images.all().order_by("display_order", "id"):
            raw_url = gimg.get_image_url()
            url = optimize_image_url(raw_url) if raw_url else ""
            if url and url not in seen:
                images.append({
                    "url": url,
                    "is_primary": gimg.is_primary,
                    "alt": gimg.alt_text or self.name,
                    "id": gimg.id,
                    "source": "gallery",
                })
                seen.add(url)

        raw_cover = self.get_image_url()
        cover_url = optimize_image_url(raw_cover) if raw_cover else ""
        if cover_url and cover_url not in seen:
            if not any(img["is_primary"] for img in images):
                images.insert(0, {
                    "url": cover_url,
                    "is_primary": True,
                    "alt": self.name,
                    "id": 0,
                    "source": "cover",
                })
            else:
                images.append({
                    "url": cover_url,
                    "is_primary": False,
                    "alt": self.name,
                    "id": 0,
                    "source": "cover",
                })
            seen.add(cover_url)

        if not images:
            images.append({
                "url": "/static/home/images/tipsycart-logo.png",
                "is_primary": True,
                "alt": self.name,
                "id": 0,
                "source": "default",
            })

        # Ensure the primary image is always at index 0
        primary_idx = next((i for i, img in enumerate(images) if img.get("is_primary")), 0)
        if primary_idx > 0:
            primary_item = images.pop(primary_idx)
            images.insert(0, primary_item)

        return images

    def get_similar_styles(self, limit=12):
        """
        Returns manually linked styles if defined; otherwise falls back to active products in same subcategory.
        """
        try:
            manual = list(self.similar_products.filter(is_active=True).select_related("category_ref", "subcategory_ref")[:limit])
            if manual:
                return manual
        except Exception:
            pass

        try:
            qs = Product.objects.filter(is_active=True).exclude(pk=self.pk).select_related("category_ref", "subcategory_ref")
            if self.subcategory_ref_id:
                matches = list(qs.filter(subcategory_ref_id=self.subcategory_ref_id)[:limit])
                if matches:
                    return matches
            elif self.subcategory:
                matches = list(qs.filter(subcategory__iexact=self.subcategory)[:limit])
                if matches:
                    return matches
            if self.category_ref_id:
                return list(qs.filter(category_ref_id=self.category_ref_id)[:limit])
            elif self.category:
                return list(qs.filter(category__iexact=self.category)[:limit])
        except Exception:
            pass
        return []

    def get_all_style_options(self, limit=12):
        """
        Returns list of style options (self + linked styles) for the Meesho-style thumbnail picker.
        """
        linked = self.get_similar_styles(limit=limit)
        if not linked:
            return []
        return [self] + [p for p in linked if p.id != self.id]


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ImageField(
        upload_to="products/gallery/",
        blank=True,
        null=True,
        help_text="Upload gallery image file directly from computer (Cloudinary/local)",
    )
    image_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Direct public image link or Cloudinary URL (e.g. https://...)",
    )
    alt_text = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Descriptive alt text for SEO and accessibility",
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Set as primary/cover image for the product",
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Gallery Image"
        verbose_name_plural = "Product Gallery Images"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.product.name} Gallery Image #{self.id}"

    def save(self, *args, **kwargs):
        if self.is_primary and self.product_id:
            ProductImage.objects.filter(product_id=self.product_id).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def get_image_url(self):
        if self.image:
            try:
                url = self.image.url
                if url and (url.startswith("http://") or url.startswith("https://")):
                    return optimize_image_url(url)
                if hasattr(self.image, "path"):
                    try:
                        if os.path.exists(self.image.path):
                            return optimize_image_url(url)
                    except (NotImplementedError, Exception):
                        return optimize_image_url(url)
                elif not hasattr(self.image, "path"):
                    return optimize_image_url(url)
            except Exception:
                pass
            fname = os.path.basename(self.image.name or "")
            if fname and os.path.exists(os.path.join(settings.BASE_DIR, "Homepage/static/home/images/products", fname)):
                return f"/static/home/images/products/{fname}"

        if self.image_url and self.image_url.strip():
            url = self.image_url.strip()
            if url.startswith("http://") or url.startswith("https://"):
                return optimize_image_url(url)
            if url.startswith("/media/"):
                rel_path = url.replace("/media/", "").lstrip("/")
                full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                if os.path.exists(full_path):
                    return url
                fname = os.path.basename(rel_path)
                if fname and os.path.exists(os.path.join(settings.BASE_DIR, "Homepage/static/home/images/products", fname)):
                    return f"/static/home/images/products/{fname}"
            else:
                return optimize_image_url(url)

        if self.product:
            return self.product.get_image_url()
        return "/static/home/images/tipsycart-logo.png"


class ColorMaster(models.Model):
    name = models.CharField(
        max_length=60,
        unique=True,
        db_index=True,
        help_text="Standard colour name (e.g. Black, White, Navy Blue, Crimson Red)",
    )
    hex_code = models.CharField(
        max_length=20,
        default="#000000",
        help_text="HEX color code (e.g. #000000, #FFFFFF, #2563EB)",
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active colours appear in selection dropdowns",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Global Colour"
        verbose_name_plural = "Colour Master Library"
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.hex_code})"

    def clean(self):
        if self.hex_code:
            code = self.hex_code.strip()
            if not code.startswith("#"):
                code = f"#{code}"
            self.hex_code = code.upper()


class ProductColour(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="colours",
    )
    color_master = models.ForeignKey(
        ColorMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_colours",
        help_text="Select from Global Colour Library to auto-fill name and HEX code",
    )
    name = models.CharField(
        max_length=60,
        help_text="Colour name e.g. Black, White, Sky Blue, Olive Green",
    )
    color_code = models.CharField(
        max_length=20,
        blank=True,
        default="#000000",
        help_text="HEX color code (e.g. #000000, #FFFFFF, #2563EB)",
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Colour"
        verbose_name_plural = "Product Colours"
        ordering = ["display_order", "id"]
        unique_together = [["product", "name"]]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.color_master:
            if not self.name:
                self.name = self.color_master.name
            if not self.color_code or self.color_code == "#000000":
                self.color_code = self.color_master.hex_code
        super().save(*args, **kwargs)

    def get_primary_image_url(self):
        primary_img = self.images.filter(is_primary=True).first()
        if not primary_img:
            primary_img = self.images.first()
        if primary_img:
            return primary_img.get_image_url()
        return self.product.get_image_url()


class ProductColourImage(models.Model):
    colour = models.ForeignKey(
        ProductColour,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(
        upload_to="products/variants/",
        blank=True,
        null=True,
        help_text="Upload image file directly from computer (Cloudinary/local)",
    )
    image_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Direct public image link or Cloudinary URL (e.g. https://...)",
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Set as primary thumbnail for this colour",
    )
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Colour Image"
        verbose_name_plural = "Colour Images"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.colour.name} Image #{self.id}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductColourImage.objects.filter(colour=self.colour).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def get_image_url(self):
        if self.image:
            try:
                url = self.image.url
                if url and (url.startswith("http://") or url.startswith("https://")):
                    return optimize_image_url(url)
                if hasattr(self.image, "path"):
                    try:
                        if os.path.exists(self.image.path):
                            return optimize_image_url(url)
                    except (NotImplementedError, Exception):
                        return optimize_image_url(url)
                elif not hasattr(self.image, "path"):
                    return optimize_image_url(url)
            except Exception:
                pass
            fname = os.path.basename(self.image.name or "")
            if fname and os.path.exists(os.path.join(settings.BASE_DIR, "Homepage/static/home/images/products", fname)):
                return f"/static/home/images/products/{fname}"

        if self.image_url and self.image_url.strip():
            url = self.image_url.strip()
            if url.startswith("http://") or url.startswith("https://"):
                return optimize_image_url(url)
            if url.startswith("/media/"):
                rel_path = url.replace("/media/", "").lstrip("/")
                full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                if os.path.exists(full_path):
                    return url
                fname = os.path.basename(rel_path)
                if fname and os.path.exists(os.path.join(settings.BASE_DIR, "Homepage/static/home/images/products", fname)):
                    return f"/static/home/images/products/{fname}"
            else:
                return optimize_image_url(url)

        if self.colour and self.colour.product:
            return self.colour.product.get_image_url()
        return "/static/home/images/tipsycart-logo.png"


class ProductSize(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="sizes",
    )
    name = models.CharField(
        max_length=50,
        help_text="Size name e.g. S, M, L, XL, XXL, UK 7, Free Size, 500g, 1L",
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Size"
        verbose_name_plural = "Product Sizes"
        ordering = ["display_order", "id"]
        unique_together = [["product", "name"]]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    colour = models.ForeignKey(
        ProductColour,
        on_delete=models.CASCADE,
        related_name="variants",
        null=True,
        blank=True,
    )
    size = models.ForeignKey(
        ProductSize,
        on_delete=models.CASCADE,
        related_name="variants",
        null=True,
        blank=True,
    )
    sku = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        help_text="Unique SKU for this variant (e.g. TC-BLK-M)",
    )
    variant_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Custom variant label (e.g. 250 g, 500 g, 1 kg, Pack of 2, Red / M)",
    )
    unit = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Variant unit (e.g. g, kg, ml, L, piece, pack, box)",
    )
    unit_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Numeric weight or quantity value (e.g. 250, 500, 1)",
    )
    barcode = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Optional EAN/UPC barcode",
    )
    image = models.ImageField(
        upload_to="products/variants/",
        null=True,
        blank=True,
        help_text="Optional custom photo for this variant (e.g. 250g pack photo, 1kg pack photo). If blank, uses main product photo.",
    )
    image_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="Optional external direct image URL for this variant",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Final selling price in INR",
    )
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original regular price / MRP in INR",
    )
    discount_enabled = models.BooleanField(default=False)
    discount_type = models.CharField(
        max_length=20,
        choices=Product.DISCOUNT_TYPE_CHOICES,
        default="percentage",
        blank=True,
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Variant"
        verbose_name_plural = "Product Variants"
        unique_together = [["product", "colour", "size"]]
        ordering = ["colour__display_order", "size__display_order", "id"]

    def __str__(self):
        return f"{self.product.name} ({self.get_title()}) - ₹{self.price}"

    def get_title(self):
        if self.variant_name:
            if self.colour and self.colour.name.lower() not in self.variant_name.lower():
                return f"{self.colour.name} - {self.variant_name}"
            return self.variant_name
        parts = []
        if self.colour:
            parts.append(self.colour.name)
        if self.size:
            parts.append(self.size.name)
        return " / ".join(parts) if parts else "Standard"

    def get_full_name(self):
        return f"{self.product.name} ({self.get_title()})"

    @property
    def is_in_stock(self):
        return self.is_active and self.stock > 0

    @property
    def discount_percentage(self):
        if not self.original_price or self.original_price <= self.price:
            return 0
        diff = self.original_price - self.price
        return int(round((diff / self.original_price) * 100))

    @property
    def savings_amount(self):
        if not self.original_price or self.original_price <= self.price:
            return Decimal("0.00")
        return round(self.original_price - self.price, 2)

    def get_image_url(self):
        if self.image:
            try:
                url = self.image.url
                if url:
                    return optimize_image_url(url)
            except Exception:
                pass
        if self.image_url:
            return optimize_image_url(self.image_url)
        if self.colour:
            c_url = self.colour.get_primary_image_url()
            if c_url:
                return optimize_image_url(c_url)
        return self.product.get_image_url()

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.price is None:
            if hasattr(self, "product") and self.product and getattr(self.product, "price", None) is not None:
                self.price = self.product.price
            elif getattr(self, "product_id", None):
                try:
                    p = Product.objects.filter(pk=self.product_id).first()
                    if p and p.price is not None:
                        self.price = p.price
                except Exception:
                    pass

        if self.price is not None and self.price < 0:
            raise ValidationError({"price": "Variant price cannot be negative."})
        if self.original_price is not None and self.original_price < 0:
            raise ValidationError({"original_price": "Variant original price cannot be negative."})
        if self.stock is not None and self.stock < 0:
            raise ValidationError({"stock": "Variant stock cannot be negative."})
        if self.discount_enabled and self.discount_value and self.discount_value > 0:
            if self.discount_type == "percentage" and self.discount_value > 99:
                raise ValidationError({"discount_value": "Percentage discount cannot exceed 99%."})
            elif self.discount_type == "fixed" and self.original_price and self.discount_value >= self.original_price:
                raise ValidationError({"discount_value": "Fixed discount cannot equal or exceed original price."})

    def save(self, *args, **kwargs):
        # 0. Fallback for price from product if not provided
        if self.price is None:
            if hasattr(self, "product") and self.product and getattr(self.product, "price", None) is not None:
                self.price = self.product.price
            elif getattr(self, "product_id", None):
                try:
                    p = Product.objects.filter(pk=self.product_id).first()
                    if p and p.price is not None:
                        self.price = p.price
                except Exception:
                    pass
            if self.price is None:
                self.price = Decimal("0.00")

        # 1. Fallback for original_price
        if self.original_price is None or self.original_price <= 0:
            self.original_price = self.price

        # 2. Smart discount sync (Manual Variant Selling Price is KING):
        # When store admin sets MRP and Selling Price on a variant, NEVER overwrite their selling price.
        # Auto-compute and sync the discount metadata directly from MRP and Selling Price.
        if self.original_price and self.price is not None:
            if self.original_price > self.price:
                self.discount_enabled = True
                self.discount_type = "percentage"
                diff = self.original_price - self.price
                self.discount_value = round((diff / self.original_price) * Decimal("100.00"), 2)
            else:
                self.discount_enabled = False
                self.discount_value = Decimal("0.00")

        # 3. Auto-generate readable variant_name if empty
        if not self.variant_name:
            parts = []
            if self.colour:
                parts.append(self.colour.name)
            if self.size:
                parts.append(self.size.name)
            elif self.unit_value and self.unit:
                val_str = f"{self.unit_value:g}" if isinstance(self.unit_value, Decimal) else str(self.unit_value)
                parts.append(f"{val_str} {self.unit}")
            elif self.unit:
                parts.append(self.unit)
            self.variant_name = " / ".join(parts) if parts else "Standard"

        # 4. Auto-generate SKU if empty
        if not self.sku:
            base_sku = self.product.product_number or f"TC-{self.product.id}"
            col_part = slugify(self.colour.name)[:3].upper() if self.colour else "DEF"
            sz_source = self.variant_name or (self.size.name if self.size else "STD")
            sz_part = slugify(sz_source)[:5].upper() or "STD"
            self.sku = f"{base_sku}-{col_part}-{sz_part}"

        super().save(*args, **kwargs)

