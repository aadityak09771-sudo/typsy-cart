import csv
import io
import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Sum, F, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Category,
    Subcategory,
    Product,
    ColorMaster,
    ProductImage,
    ProductColour,
    ProductColourImage,
    ProductSize,
    ProductVariant,
)
from .services.zip_importer import ZipProductImporter, sanitize_zip_path
from .services.excel_exporter import (
    generate_products_excel,
    generate_category_subcategory_excel,
    VALID_ORDER_STATUSES,
)
from .services.excel_importer import (
    parse_and_validate_excel,
    commit_excel_import,
    generate_import_error_excel,
    generate_sample_excel_template,
)


MAX_CSV_SIZE = 10 * 1024 * 1024


def validate_direct_image_url(url_val):
    """Validates that a URL is a direct image link and not a search engine or HTML page."""
    if not url_val:
        return url_val
    clean_val = str(url_val).strip()
    if not clean_val:
        return clean_val
    invalid_patterns = [
        "google.com/search",
        "google.com/imgres",
        "bing.com/images/search",
        "yahoo.com/search",
        "pinterest.com/pin/",
        "facebook.com",
        "instagram.com",
    ]
    for pattern in invalid_patterns:
        if pattern in clean_val.lower():
            raise forms.ValidationError(
                "Please enter a direct public image link (e.g. ending in .jpg, .png, .webp), not a search engine or social media link."
            )
    if not (
        clean_val.startswith("http://")
        or clean_val.startswith("https://")
        or clean_val.startswith("/static/")
        or clean_val.startswith("/media/")
    ):
        raise forms.ValidationError(
            "Image URL must start with http://, https://, /static/, or /media/."
        )
    return clean_val


# ---------------------------------------------------------------------------
# CUSTOM ADMIN FILTERS
# ---------------------------------------------------------------------------

class StockLevelFilter(admin.SimpleListFilter):
    title = "Stock Status"
    parameter_name = "stock_status"

    def lookups(self, request, model_admin):
        return [
            ("out_of_stock", "Out of Stock (0)"),
            ("low_stock", "Low Stock (1 – 10)"),
            ("in_stock", "Healthy Stock (> 10)"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "out_of_stock":
            return queryset.filter(stock=0)
        if self.value() == "low_stock":
            return queryset.filter(stock__gt=0, stock__lte=10)
        if self.value() == "in_stock":
            return queryset.filter(stock__gt=10)
        return queryset


class DiscountStatusFilter(admin.SimpleListFilter):
    title = "Discount Status"
    parameter_name = "discount_status"

    def lookups(self, request, model_admin):
        return [
            ("discounted", "Discount Active"),
            ("regular", "Regular Price (No Discount)"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "discounted":
            return queryset.filter(discount_enabled=True, discount_value__gt=0)
        if self.value() == "regular":
            return queryset.filter(discount_enabled=False)
        return queryset


class ProductQuickFilter(admin.SimpleListFilter):
    title = "Quick Filter"
    parameter_name = "quick_filter"

    def lookups(self, request, model_admin):
        return [
            ("all", "All Products"),
            ("simple", "Simple Products"),
            ("variable", "Variable Products"),
            ("in_stock", "In Stock (> 10)"),
            ("low_stock", "Low Stock (1 – 10)"),
            ("out_of_stock", "Out of Stock (0)"),
            ("active", "Active Products"),
            ("inactive", "Inactive Products"),
        ]

    def queryset(self, request, queryset):
        val = self.value()
        if val == "all":
            return queryset
        elif val == "simple":
            return queryset.filter(product_type="simple")
        elif val == "variable":
            return queryset.filter(product_type="variable")
        elif val == "in_stock":
            return queryset.filter(stock__gt=10)
        elif val == "low_stock":
            return queryset.filter(stock__gt=0, stock__lte=10)
        elif val == "out_of_stock":
            return queryset.filter(stock=0)
        elif val == "active":
            return queryset.filter(is_active=True)
        elif val == "inactive":
            return queryset.filter(is_active=False)
        return queryset


# ---------------------------------------------------------------------------
# CATEGORY ADMIN FORM & ADMIN
# ---------------------------------------------------------------------------

class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = "__all__"

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if img and isinstance(img, UploadedFile):
            if img.size > 12 * 1024 * 1024:
                raise forms.ValidationError("Category image file must be smaller than 12 MB.")
            ext = os.path.splitext(img.name)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
                raise forms.ValidationError("Supported image formats are JPG, PNG, WEBP, GIF, and SVG.")
        return img

    def clean_image_url(self):
        return validate_direct_image_url(self.cleaned_data.get("image_url"))

    def clean(self):
        cleaned_data = super().clean()
        image = cleaned_data.get("image") or (self.instance and self.instance.image)
        image_url = cleaned_data.get("image_url")
        if image and image_url and image_url.startswith("/media/"):
            cleaned_data["image_url"] = ""
        return cleaned_data


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = (
        "image_thumb",
        "name",
        "slug",
        "display_order",
        "show_on_homepage",
        "homepage_display_order",
        "homepage_card_size",
        "homepage_display_style",
        "is_featured",
        "product_count_badge",
        "subcategory_count_badge",
        "is_active",
        "created_at",
    )
    list_display_links = ("image_thumb", "name")
    list_editable = (
        "display_order",
        "show_on_homepage",
        "homepage_display_order",
        "is_featured",
        "is_active",
    )
    list_filter = (
        "show_on_homepage",
        "is_featured",
        "homepage_card_size",
        "homepage_display_style",
        "is_active",
        "created_at",
    )
    search_fields = ("name", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("homepage_display_order", "display_order", "name")
    readonly_fields = ("image_preview_large", "created_at")

    fieldsets = (
        ("Category Details", {"fields": ("name", "slug", "description")}),
        ("Option 1: Upload Image from Computer", {
            "fields": ("image", "image_preview_large"),
            "description": "Upload an image file directly from your computer (JPG, PNG, WEBP, GIF, SVG). Maximum 12 MB.",
        }),
        ("Option 2: Enter External Direct Image URL", {
            "fields": ("image_url",),
            "description": "Or enter a public direct image link (e.g. https://.../photo.jpg). Leave blank if uploading an image file above.",
        }),
        ("Homepage Display Controls (Homepage Only)", {
            "fields": (
                "show_on_homepage",
                "homepage_display_order",
                "homepage_card_size",
                "homepage_display_style",
                "is_featured",
            ),
            "description": "Control whether and how this category appears on the TipsyCart Home Page. These settings only affect the Home Page and do not change the Categories or Shop pages.",
        }),
        ("Global Display & Status", {"fields": ("display_order", "is_active")}),
    )

    class Media:
        js = ("products/admin_dynamic.js",)
        css = {"all": ("products/admin_dynamic.css",)}

    @admin.display(description="Image")
    def image_thumb(self, obj):
        url = obj.get_image_url() if obj else ""
        if not url:
            url = "/static/home/images/tipsycart-logo.png"
        return format_html(
            '<img src="{}" style="width: 36px; height: 36px; object-fit: cover; border-radius: 6px; border: 1px solid #e5e7eb;" onerror="this.onerror=null;this.src=\'/static/home/images/tipsycart-logo.png\';" />',
            url,
        )

    @admin.display(description="Current Image")
    def image_preview_large(self, obj):
        if not obj or not obj.pk:
            return "Save category first to view saved image."
        url = obj.get_image_url()
        if obj.image:
            source_badge = format_html(
                '<span style="color: #0284c7; font-weight: 600;">✓ Uploaded from Computer:</span> {}',
                obj.image.name
            )
        elif obj.image_url:
            source_badge = format_html(
                '<span style="color: #7c3aed; font-weight: 600;">✓ External Direct URL:</span> {}',
                obj.image_url
            )
        else:
            source_badge = mark_safe('<span style="color: #64748b;">Using Default Store Image</span>')

        return format_html(
            '<div class="tc-current-image-container" data-current-url="{}" style="margin-top: 6px;">'
            '<img src="{}" style="max-width: 200px; max-height: 150px; object-fit: contain; border-radius: 8px; border: 1px solid #e2e8f0; padding: 4px; background: #fff0f5;" /><br>'
            '<small style="display: block; margin-top: 6px; font-size: 11px;">{}</small>'
            '</div>',
            url,
            url,
            source_badge,
        )

    @admin.display(description="Active Products")
    def product_count_badge(self, obj):
        count = obj.products.filter(is_active=True).count()
        bg = "#e8f5e9" if count > 0 else "#f3f4f6"
        color = "#2e7d32" if count > 0 else "#6b7280"
        return format_html(
            '<span style="background: {}; color: {}; padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 11px;">{} products</span>',
            bg, color, count,
        )

    @admin.display(description="Subcategories")
    def subcategory_count_badge(self, obj):
        count = obj.subcategories.count()
        return format_html(
            '<span style="background: #fdf2f8; color: #a51655; padding: 2px 8px; border-radius: 10px; font-weight: 700; font-size: 11px;">{} subcats</span>',
            count,
        )

    def delete_model(self, request, obj):
        prod_count = obj.products.count()
        subcat_count = obj.subcategories.count()
        if prod_count > 0 or subcat_count > 0:
            self.message_user(
                request,
                f"Cannot delete category '{obj.name}' because it contains {prod_count} products and {subcat_count} subcategories. Please deactivate the category instead (uncheck Active) or reassign items first.",
                level=messages.ERROR,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        blocked = []
        for cat in queryset:
            p_count = cat.products.count()
            s_count = cat.subcategories.count()
            if p_count > 0 or s_count > 0:
                blocked.append(f"{cat.name} ({p_count} products, {s_count} subcategories)")
        if blocked:
            self.message_user(
                request,
                f"Cannot delete the following categories because they contain products or subcategories: {', '.join(blocked)}. Please deactivate them instead.",
                level=messages.ERROR,
            )
            return
        super().delete_queryset(request, queryset)


# ---------------------------------------------------------------------------
# SUBCATEGORY ADMIN FORM & ADMIN
# ---------------------------------------------------------------------------

class SubcategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Subcategory
        fields = "__all__"

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if img and isinstance(img, UploadedFile):
            if img.size > 12 * 1024 * 1024:
                raise forms.ValidationError("Subcategory image file must be smaller than 12 MB.")
            ext = os.path.splitext(img.name)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
                raise forms.ValidationError("Supported image formats are JPG, PNG, WEBP, GIF, and SVG.")
        return img

    def clean_image_url(self):
        return validate_direct_image_url(self.cleaned_data.get("image_url"))

    def clean(self):
        cleaned_data = super().clean()
        image = cleaned_data.get("image") or (self.instance and self.instance.image)
        image_url = cleaned_data.get("image_url")
        if image and image_url and image_url.startswith("/media/"):
            cleaned_data["image_url"] = ""
        return cleaned_data


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    form = SubcategoryAdminForm
    list_display = (
        "image_thumb",
        "name",
        "category_badge",
        "display_order",
        "product_count_badge",
        "is_active",
        "created_at",
    )
    list_display_links = ("image_thumb", "name")
    list_editable = ("display_order", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "category__name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("category__display_order", "display_order", "name")
    readonly_fields = ("image_preview_large", "created_at")

    fieldsets = (
        ("Subcategory Info", {"fields": ("category", "name", "slug", "description")}),
        ("Option 1: Upload Image from Computer", {
            "fields": ("image", "image_preview_large"),
            "description": "Upload a subcategory image file directly from your computer (JPG, PNG, WEBP, GIF, SVG). Maximum 12 MB.",
        }),
        ("Option 2: Enter External Direct Image URL", {
            "fields": ("image_url",),
            "description": "Or enter a public direct image link (e.g. https://.../photo.jpg). Leave blank if uploading an image file above.",
        }),
        ("Display & Status", {"fields": ("display_order", "is_active")}),
    )

    class Media:
        js = ("products/admin_dynamic.js",)
        css = {"all": ("products/admin_dynamic.css",)}

    @admin.display(description="Image")
    def image_thumb(self, obj):
        url = obj.get_image_url() if obj else ""
        if not url:
            url = "/static/home/images/tipsycart-logo.png"
        return format_html(
            '<img src="{}" style="width: 36px; height: 36px; object-fit: cover; border-radius: 6px; border: 1px solid #e5e7eb;" onerror="this.onerror=null;this.src=\'/static/home/images/tipsycart-logo.png\';" />',
            url,
        )

    @admin.display(description="Current Image")
    def image_preview_large(self, obj):
        if not obj or not obj.pk:
            return "Save subcategory first to view saved image."
        url = obj.get_image_url()
        if obj.image:
            source_badge = format_html(
                '<span style="color: #0284c7; font-weight: 600;">✓ Uploaded from Computer:</span> {}',
                obj.image.name
            )
        elif obj.image_url:
            source_badge = format_html(
                '<span style="color: #7c3aed; font-weight: 600;">✓ External Direct URL:</span> {}',
                obj.image_url
            )
        else:
            source_badge = mark_safe('<span style="color: #64748b;">Using Default Store Image</span>')

        return format_html(
            '<div class="tc-current-image-container" data-current-url="{}" style="margin-top: 6px;">'
            '<img src="{}" style="max-width: 200px; max-height: 150px; object-fit: contain; border-radius: 8px; border: 1px solid #e2e8f0; padding: 4px; background: #fff0f5;" /><br>'
            '<small style="display: block; margin-top: 6px; font-size: 11px;">{}</small>'
            '</div>',
            url,
            url,
            source_badge,
        )

    @admin.display(description="Parent Category")
    def category_badge(self, obj):
        return format_html(
            '<span style="background: #fdf2f8; color: #a51655; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 11px;">{}</span>',
            obj.category.name,
        )

    @admin.display(description="Products")
    def product_count_badge(self, obj):
        count = obj.products.filter(is_active=True).count()
        return format_html(
            '<span style="background: #f3f4f6; color: #374151; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 11px;">{} items</span>',
            count,
        )

    def delete_model(self, request, obj):
        prod_count = obj.products.count()
        if prod_count > 0:
            self.message_user(
                request,
                f"Cannot delete subcategory '{obj.name}' because it contains {prod_count} products. Please deactivate the subcategory instead (uncheck Active) or reassign products first.",
                level=messages.ERROR,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        blocked = []
        for sub in queryset:
            p_count = sub.products.count()
            if p_count > 0:
                blocked.append(f"{sub.name} ({p_count} products)")
        if blocked:
            self.message_user(
                request,
                f"Cannot delete the following subcategories because they contain products: {', '.join(blocked)}. Please deactivate them instead.",
                level=messages.ERROR,
            )
            return
        super().delete_queryset(request, queryset)


# ---------------------------------------------------------------------------
# PRODUCT ADMIN FORM & ADMIN
# ---------------------------------------------------------------------------

class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(d, initial) for d in data]
        return single_clean(data, initial)


class ProductAdminForm(forms.ModelForm):
    bulk_gallery_images = MultipleFileField(
        required=False,
        label="Bulk Upload Gallery Images",
        help_text="Select and upload multiple gallery images together at once (hold Ctrl/Cmd or Shift).",
    )

    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "discount_value" in self.fields:
            self.fields["discount_value"].required = False
            if self.fields["discount_value"].initial is None:
                self.fields["discount_value"].initial = Decimal("0.00")

    def clean_image(self):
        uploaded_image = self.cleaned_data.get("image")
        if uploaded_image and isinstance(uploaded_image, UploadedFile):
            if uploaded_image.size > 12 * 1024 * 1024:
                raise forms.ValidationError("Product image file must be smaller than 12 MB.")
            ext = os.path.splitext(uploaded_image.name)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                raise forms.ValidationError("Supported image formats are JPG, PNG, WEBP, and GIF.")
        return uploaded_image

    def clean_image_url(self):
        return validate_direct_image_url(self.cleaned_data.get("image_url"))

    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get("price")
        orig_price = cleaned_data.get("original_price")
        discount_enabled = cleaned_data.get("discount_enabled")
        discount_val = cleaned_data.get("discount_value")
        discount_type = cleaned_data.get("discount_type")
        category_ref = cleaned_data.get("category_ref")
        subcategory_ref = cleaned_data.get("subcategory_ref")

        # Validate Category-Subcategory Relationship
        if category_ref and subcategory_ref:
            if subcategory_ref.category_id != category_ref.id:
                self.add_error(
                    "subcategory_ref",
                    f"Subcategory '{subcategory_ref.name}' belongs to category '{subcategory_ref.category.name}', not '{category_ref.name}'. Please choose a matching subcategory."
                )

        if orig_price is None or orig_price <= 0:
            if price and price > 0:
                cleaned_data["original_price"] = price
                orig_price = price

        if orig_price and price and orig_price > price:
            cleaned_data["discount_enabled"] = True
            cleaned_data["discount_type"] = "percentage"
            diff = orig_price - price
            cleaned_data["discount_value"] = round((diff / orig_price) * Decimal("100.00"), 2)
        elif discount_enabled and discount_val and discount_val > 0:
            if discount_type == "percentage" and discount_val > 99:
                self.add_error("discount_value", "Percentage discount cannot exceed 99%.")
            elif discount_type == "fixed" and orig_price and discount_val >= orig_price:
                self.add_error("discount_value", "Fixed discount cannot equal or exceed original price.")

        if cleaned_data.get("discount_value") is None:
            cleaned_data["discount_value"] = Decimal("0.00")

        # Clean up redundant /media/ string from external image_url if a local image exists
        image = cleaned_data.get("image") or (self.instance and self.instance.image)
        image_url = cleaned_data.get("image_url")
        if image and image_url and image_url.startswith("/media/"):
            cleaned_data["image_url"] = ""

        return cleaned_data


# ---------------------------------------------------------------------------
# VARIANT INLINES & ADMINS
# ---------------------------------------------------------------------------

class ProductColourImageInline(admin.TabularInline):
    model = ProductColourImage
    extra = 1
    fields = ("image_preview_small", "image", "image_url", "is_primary", "display_order")
    readonly_fields = ("image_preview_small",)

    def image_preview_small(self, obj):
        url = obj.get_image_url() if obj and obj.pk else ""
        if not url:
            url = "/static/home/images/tipsycart-logo.png"
        return format_html(
            '<img src="{}" style="width: 38px; height: 38px; object-fit: cover; border-radius: 6px; border: 1px solid #e2e8f0;" onerror="this.onerror=null;this.src=\'/static/home/images/tipsycart-logo.png\';" />',
            url
        )
    image_preview_small.short_description = "Preview"


# ---------------------------------------------------------------------------
# GLOBAL COLOUR MASTER LIBRARY ADMIN
# ---------------------------------------------------------------------------

@admin.register(ColorMaster)
class ColorMasterAdmin(admin.ModelAdmin):
    list_display = (
        "color_swatch_badge",
        "name",
        "hex_code",
        "display_order",
        "product_count_badge",
        "is_active",
        "created_at",
    )
    list_display_links = ("color_swatch_badge", "name")
    list_editable = ("display_order", "is_active", "hex_code")
    search_fields = ("name", "hex_code")
    ordering = ("display_order", "name")
    list_filter = ("is_active",)

    @admin.display(description="Colour Swatch")
    def color_swatch_badge(self, obj):
        code = obj.hex_code or "#000000"
        return format_html(
            '<div style="display:inline-flex; align-items:center; gap:8px;">'
            '<span style="display:inline-block; width:22px; height:22px; border-radius:50%; background-color:{}; border:2px solid #cbd5e1; box-shadow:0 1px 3px rgba(0,0,0,0.12); vertical-align:middle;"></span>'
            '<span style="font-family:monospace; font-weight:700; font-size:12px; color:#334155;">{}</span>'
            '</div>',
            code, code
        )

    @admin.display(description="Used in Products")
    def product_count_badge(self, obj):
        count = obj.product_colours.count()
        return format_html(
            '<span style="background:#f0fdf4; color:#166534; padding:2px 8px; border-radius:12px; font-weight:700; font-size:11px;">{} assigned</span>',
            count
        )


# ---------------------------------------------------------------------------
# VARIANT INLINES & ADMINS
# ---------------------------------------------------------------------------

class ProductColourImageInline(admin.TabularInline):
    model = ProductColourImage
    extra = 1
    fields = ("image_preview_small", "image", "image_url", "is_primary", "display_order")
    readonly_fields = ("image_preview_small",)

    def image_preview_small(self, obj):
        url = obj.get_image_url() if obj and obj.pk else ""
        if not url:
            url = "/static/home/images/tipsycart-logo.png"
        return format_html(
            '<img src="{}" style="width: 38px; height: 38px; object-fit: cover; border-radius: 6px; border: 1px solid #e2e8f0;" onerror="this.onerror=null;this.src=\'/static/home/images/tipsycart-logo.png\';" />',
            url
        )
    image_preview_small.short_description = "Preview"


@admin.register(ProductColour)
class ProductColourAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "color_code_badge", "color_master", "image_count_badge", "display_order", "is_active")
    list_filter = ("product", "is_active", "color_master")
    search_fields = ("name", "product__name", "color_code")
    inlines = [ProductColourImageInline]

    @admin.display(description="Swatch")
    def color_code_badge(self, obj):
        code = obj.color_code or "#000000"
        return format_html(
            '<span style="display:inline-block; width:16px; height:16px; border-radius:50%; background-color:{}; vertical-align:middle; margin-right:6px; border:1px solid #ccc;"></span>{}',
            code, code
        )

    @admin.display(description="Images")
    def image_count_badge(self, obj):
        count = obj.images.count()
        return format_html('<span style="font-weight:600; color:#a51655;">{} image(s)</span>', count)


@admin.register(ProductSize)
class ProductSizeAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "display_order", "is_active")
    list_filter = ("product", "is_active")
    search_fields = ("name", "product__name")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image_preview", "image", "image_url", "alt_text", "is_primary", "display_order")
    readonly_fields = ("image_preview",)
    show_change_link = True
    verbose_name = "Gallery Image"
    verbose_name_plural = "5. Additional Gallery Images (Upload & Reorder)"

    @admin.display(description="Preview")
    def image_preview(self, obj):
        url = obj.get_image_url() if obj else ""
        if url:
            return format_html('<img src="{}" style="width: 44px; height: 44px; object-fit: contain; border-radius: 6px; border: 1px solid #e2e8f0;" />', url)
        return "—"


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("image_preview", "product", "is_primary", "display_order", "created_at")
    list_filter = ("is_primary", "product")
    search_fields = ("product__name", "alt_text")

    @admin.display(description="Preview")
    def image_preview(self, obj):
        url = obj.get_image_url() if obj else ""
        if url:
            return format_html('<img src="{}" style="width: 44px; height: 44px; object-fit: contain; border-radius: 6px;" />', url)
        return "—"


class ColourImagesWidget(forms.Widget):
    """
    Custom rich widget for managing multiple images per Product Colour:
    - Lists existing saved photos with thumbnails, primary (★) radio selector, order input, and remove checkbox.
    - Multiple file upload button (supports selecting multiple photos at once).
    - Client-side instant live previews container via FileReader before save.
    """
    def __init__(self, instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

    def render(self, name, value, attrs=None, renderer=None):
        prefix = name.replace("-colour_images_manager", "")
        colour = self.instance

        html = []
        html.append(f'<div class="tc-colour-images-manager-wrap" data-prefix="{prefix}">')

        # 1. Header / Action bar
        html.append('  <div class="tc-cim-bar">')
        html.append('    <span class="tc-cim-icon">📸</span>')
        html.append('    <span class="tc-cim-title">Colour Photo Gallery (Multiple Photos for This Colour)</span>')
        html.append('    <span class="tc-cim-badge">Upload front, side, close-up &amp; packaging photos</span>')
        html.append('  </div>')

        # 2. Existing Saved Images Grid
        if colour and colour.pk:
            images = list(colour.images.all().order_by("-is_primary", "display_order", "id"))
            if images:
                html.append('  <div class="tc-cim-existing-grid">')
                for img in images:
                    img_url = img.get_image_url()
                    is_prim = img.is_primary
                    checked_attr = "checked" if is_prim else ""
                    primary_class = "is-primary" if is_prim else ""
                    primary_badge = "<span class='tc-cim-primary-tag'>★ PRIMARY</span>" if is_prim else ""
                    html.append(f'''
                    <div class="tc-cim-card {primary_class}" id="tc-cim-card-{img.id}">
                      <div class="tc-cim-card-img-wrap">
                        <img src="{img_url}" alt="Colour photo" onerror="this.src=\'/static/home/images/tipsycart-logo.png\';" />
                        {primary_badge}
                      </div>
                      <div class="tc-cim-card-controls">
                        <label class="tc-cim-primary-lbl" title="Set this photo as the main default view for this colour">
                          <input type="radio" name="colour_primary_{prefix}" value="{img.id}" {checked_attr} onchange="window.tcHandleColourPrimaryChange(this, \'{prefix}\')" />
                          <strong>Primary (★)</strong>
                        </label>
                        <div class="tc-cim-order-row">
                          <span class="tc-cim-lbl">Order:</span>
                          <input type="number" name="colour_img_order_{img.id}" value="{img.display_order}" min="0" class="tc-cim-order-input" title="Display sequence order" />
                        </div>
                        <label class="tc-cim-delete-lbl" title="Check to delete this photo upon saving">
                          <input type="checkbox" name="colour_delete_img_{img.id}" value="1" onchange="window.tcHandleColourDeleteToggle(this, {img.id})" />
                          <span>🗑 Remove</span>
                        </label>
                      </div>
                    </div>
                    ''')
                html.append('  </div>')
            else:
                html.append('  <div class="tc-cim-empty-notice">ℹ️ No photos uploaded for this colour yet. Choose multiple files below to attach photos.</div>')
        else:
            html.append('  <div class="tc-cim-empty-notice">✨ New Colour: Select multiple images below to upload together when saving this product.</div>')

        # 3. Multiple File Upload Input
        file_input_id = f"id_colour_bulk_files_{prefix}"
        html.append('  <div class="tc-cim-upload-box">')
        html.append(f'    <label for="{file_input_id}" class="tc-cim-upload-btn">')
        html.append('      <span>📸 Choose Multiple Photos for this Colour</span>')
        html.append('    </label>')
        html.append(f'    <input type="file" name="colour_bulk_files_{prefix}" id="{file_input_id}" multiple accept="image/*" class="tc-cim-file-input" onchange="window.tcHandleColourFilesPicked(this, \'{prefix}\')" />')
        html.append('    <span class="tc-cim-hint">Select multiple image files at once (JPG, PNG, WEBP). They will be automatically saved to this colour.</span>')
        html.append('  </div>')

        # 4. Instant Live Preview container for pending files
        html.append(f'  <div id="tc-colour-pending-previews-{prefix}" class="tc-colour-pending-previews"></div>')

        html.append('</div>')
        return mark_safe("".join(html))


class ProductColourInlineForm(forms.ModelForm):
    colour_images_manager = forms.CharField(
        required=False,
        label="Colour Photos & Multi-Image Gallery",
        help_text="Upload multiple photos for this specific colour (front, side, close-up, packaging). Select primary photo and adjust display sequence.",
    )

    class Meta:
        model = ProductColour
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["colour_images_manager"].widget = ColourImagesWidget(instance=self.instance)
        if "name" in self.fields:
            self.fields["name"].widget.attrs.update({
                "placeholder": "e.g. Red, Pink, Nude, Sky Blue",
                "style": "font-weight: 700; min-width: 160px;",
            })
        if "color_code" in self.fields:
            self.fields["color_code"].widget.attrs.update({
                "placeholder": "#FF0000",
                "style": "min-width: 90px; text-transform: uppercase;",
            })


class ProductColourInlineFormSet(forms.BaseInlineFormSet):
    """
    Prevents validation crashes when duplicate colour names are submitted.
    Auto-deduplicates empty accidental duplicates or auto-disambiguates names so
    the product save succeeds and the user's uploaded images are never lost.
    """
    def clean(self):
        super().clean()
        seen = {}
        if hasattr(self, "instance") and getattr(self.instance, "pk", None):
            existing_pks = [f.instance.pk for f in self.forms if getattr(f.instance, "pk", None)]
            for existing_name in self.instance.colours.exclude(pk__in=existing_pks).values_list("name", flat=True):
                if existing_name:
                    seen[existing_name.strip().lower()] = 1

        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            name = (form.cleaned_data.get("name") or "").strip()
            if not name:
                continue
            name_lower = name.lower()
            if name_lower in seen:
                prefix = form.prefix
                bulk_files = form.files.getlist(f"colour_bulk_files_{prefix}") if form.files else []
                if not bulk_files and not getattr(form.instance, "pk", None):
                    form.cleaned_data["DELETE"] = True
                else:
                    count = seen[name_lower] + 1
                    seen[name_lower] = count
                    disambiguated = f"{name} #{count}"
                    form.cleaned_data["name"] = disambiguated
                    form.instance.name = disambiguated
                    if hasattr(form, "_errors") and "name" in form._errors:
                        del form._errors["name"]
            else:
                seen[name_lower] = 1

    def validate_unique(self):
        # Disambiguate duplicate names across forms before validation
        seen = {}
        for form in self.forms:
            if hasattr(form, "cleaned_data") and not form.cleaned_data.get("DELETE"):
                name = (form.cleaned_data.get("name") or "").strip()
                if name:
                    name_lower = name.lower()
                    if name_lower in seen:
                        count = seen[name_lower] + 1
                        seen[name_lower] = count
                        disambiguated = f"{name} #{count}"
                        form.cleaned_data["name"] = disambiguated
                        form.instance.name = disambiguated
                        if hasattr(form, "_errors") and "name" in form._errors:
                            del form._errors["name"]
                    else:
                        seen[name_lower] = 1

        try:
            super().validate_unique()
        except forms.ValidationError:
            pass

        for form in self.forms:
            if hasattr(form, "cleaned_data") and form.cleaned_data.get("DELETE"):
                form._errors = {}
            elif hasattr(form, "_errors") and "__all__" in form._errors:
                filtered_errs = [
                    e for e in form._errors["__all__"]
                    if "with this Product and Name already exists" not in str(e)
                ]
                if filtered_errs:
                    form._errors["__all__"] = form.error_class(filtered_errs)
                else:
                    del form._errors["__all__"]


class ProductColourInline(admin.StackedInline):
    model = ProductColour
    form = ProductColourInlineForm
    formset = ProductColourInlineFormSet
    extra = 1
    fields = (
        ("color_master", "name", "color_code", "swatch_preview", "display_order", "is_active"),
        "colour_images_manager",
    )
    readonly_fields = ("swatch_preview",)
    show_change_link = True
    verbose_name = "Product Colour"
    verbose_name_plural = "6. Product Colours (Multiple Images per Colour, Swatches & Display Settings)"

    @admin.display(description="Swatch")
    def swatch_preview(self, obj):
        code = (obj.color_code if obj else None) or (obj.color_master.hex_code if obj and obj.color_master else "#000000")
        return format_html(
            '<span class="tc-colour-swatch-circle" style="display:inline-block; width:22px; height:22px; border-radius:50%; background-color:{}; border:2px solid #94a3b8; vertical-align:middle; box-shadow: 0 1px 3px rgba(0,0,0,0.1);"></span>',
            code
        )


class ProductSizeInlineForm(forms.ModelForm):
    class Meta:
        model = ProductSize
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "name" in self.fields:
            self.fields["name"].widget.attrs.update({
                "placeholder": "e.g. 250g, 500g, 1kg, S, M, L",
                "style": "min-width: 180px; font-weight: 600;",
            })
            self.fields["name"].help_text = "Enter weight or size only (e.g. 250g, 1kg). Do not enter product name."


class ProductSizeInlineFormSet(forms.BaseInlineFormSet):
    """
    Prevents validation crashes when duplicate size/weight names are submitted.
    """
    def clean(self):
        super().clean()
        seen = {}
        if hasattr(self, "instance") and getattr(self.instance, "pk", None):
            existing_pks = [f.instance.pk for f in self.forms if getattr(f.instance, "pk", None)]
            for existing_name in self.instance.sizes.exclude(pk__in=existing_pks).values_list("name", flat=True):
                if existing_name:
                    seen[existing_name.strip().lower()] = 1

        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            name = (form.cleaned_data.get("name") or "").strip()
            if not name:
                continue
            name_lower = name.lower()
            if name_lower in seen:
                if not getattr(form.instance, "pk", None):
                    form.cleaned_data["DELETE"] = True
                else:
                    count = seen[name_lower] + 1
                    seen[name_lower] = count
                    disambiguated = f"{name} #{count}"
                    form.cleaned_data["name"] = disambiguated
                    form.instance.name = disambiguated
                    if hasattr(form, "_errors") and "name" in form._errors:
                        del form._errors["name"]
            else:
                seen[name_lower] = 1

    def validate_unique(self):
        # Disambiguate duplicate names across forms before validation
        seen = {}
        for form in self.forms:
            if hasattr(form, "cleaned_data") and not form.cleaned_data.get("DELETE"):
                name = (form.cleaned_data.get("name") or "").strip()
                if name:
                    name_lower = name.lower()
                    if name_lower in seen:
                        count = seen[name_lower] + 1
                        seen[name_lower] = count
                        disambiguated = f"{name} #{count}"
                        form.cleaned_data["name"] = disambiguated
                        form.instance.name = disambiguated
                        if hasattr(form, "_errors") and "name" in form._errors:
                            del form._errors["name"]
                    else:
                        seen[name_lower] = 1

        try:
            super().validate_unique()
        except forms.ValidationError:
            pass

        for form in self.forms:
            if hasattr(form, "cleaned_data") and form.cleaned_data.get("DELETE"):
                form._errors = {}
            elif hasattr(form, "_errors") and "__all__" in form._errors:
                filtered_errs = [
                    e for e in form._errors["__all__"]
                    if "with this Product and Name already exists" not in str(e)
                ]
                if filtered_errs:
                    form._errors["__all__"] = form.error_class(filtered_errs)
                else:
                    del form._errors["__all__"]


class ProductSizeInline(admin.TabularInline):
    model = ProductSize
    form = ProductSizeInlineForm
    formset = ProductSizeInlineFormSet
    extra = 1
    fields = ("name", "display_order", "is_active")
    show_change_link = True
    verbose_name = "Product Size / Weight Option"
    verbose_name_plural = "6. Product Sizes & Weight Options (e.g. 250g, 500g, 1kg, S, M, L) — Enter units/weights ONLY, do NOT enter product names"


class ProductVariantInlineForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "price" in self.fields:
            self.fields["price"].required = False
            self.fields["price"].help_text = "Variant Selling Price (₹)"
            self.fields["price"].widget.attrs.update({"placeholder": "Selling Price (₹)", "style": "min-width: 100px;"})
        if "original_price" in self.fields:
            self.fields["original_price"].widget.attrs.update({"placeholder": "MRP (₹)", "style": "min-width: 90px;"})
        if "stock" in self.fields:
            self.fields["stock"].widget.attrs.update({"placeholder": "Stock", "style": "min-width: 70px;"})
        if "sku" in self.fields:
            self.fields["sku"].widget.attrs.update({"placeholder": "Variant SKU", "style": "min-width: 120px;"})
        if "variant_name" in self.fields:
            self.fields["variant_name"].widget.attrs.update({"placeholder": "Variant Title", "style": "min-width: 130px;"})
        if "discount_value" in self.fields:
            self.fields["discount_value"].required = False
            if self.fields["discount_value"].initial is None:
                self.fields["discount_value"].initial = Decimal("0.00")
            self.fields["discount_value"].widget.attrs.update({"placeholder": "Discount", "style": "min-width: 70px;"})
        if "image" in self.fields:
            self.fields["image"].required = False
            self.fields["image"].help_text = "Optional"
        if "image_url" in self.fields:
            self.fields["image_url"].required = False
            self.fields["image_url"].widget.attrs.update({"placeholder": "Image URL (opt)", "style": "min-width: 110px;"})

    def clean_image(self):
        uploaded_image = self.cleaned_data.get("image")
        if uploaded_image and isinstance(uploaded_image, UploadedFile):
            if uploaded_image.size > 12 * 1024 * 1024:
                raise forms.ValidationError("Variant image must be smaller than 12 MB.")
            ext = os.path.splitext(uploaded_image.name)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                raise forms.ValidationError("Supported formats: JPG, PNG, WEBP, GIF.")
        return uploaded_image

    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get("price")
        orig_price = cleaned_data.get("original_price")
        if orig_price and price:
            if orig_price > price:
                cleaned_data["discount_enabled"] = True
                cleaned_data["discount_type"] = "percentage"
                diff = orig_price - price
                cleaned_data["discount_value"] = round((diff / orig_price) * Decimal("100.00"), 2)
            else:
                cleaned_data["discount_enabled"] = False
                cleaned_data["discount_value"] = Decimal("0.00")
        elif cleaned_data.get("discount_value") is None:
            cleaned_data["discount_value"] = Decimal("0.00")
        return cleaned_data


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    form = ProductVariantInlineForm
    extra = 0
    fields = (
        "image_preview_small",
        "colour",
        "size",
        "variant_name",
        "image",
        "original_price",
        "price",
        "stock",
        "sku",
        "is_active",
    )
    readonly_fields = ("image_preview_small",)
    show_change_link = True
    verbose_name = "Independently Sold Variant"
    verbose_name_plural = "7. Product Variants (Independent Pricing, Discounts, SKU & Stock)"

    @admin.display(description="Preview")
    def image_preview_small(self, obj):
        url = obj.get_image_url() if obj else ""
        if url:
            return format_html(
                '<img src="{}" style="width: 36px; height: 36px; object-fit: contain; border-radius: 6px; border: 1px solid #e2e8f0; background: #fff; padding: 2px;" onerror="this.onerror=null;this.src=\'/static/home/images/tipsycart-logo.png\';" />',
                url
            )
        return "—"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        object_id = None
        if request and request.resolver_match and "object_id" in request.resolver_match.kwargs:
            object_id = request.resolver_match.kwargs["object_id"]

        if db_field.name == "size":
            if object_id:
                kwargs["queryset"] = ProductSize.objects.filter(product_id=object_id).order_by("display_order", "id")
            else:
                kwargs["queryset"] = ProductSize.objects.none()
        elif db_field.name == "colour":
            if object_id:
                kwargs["queryset"] = ProductColour.objects.filter(product_id=object_id).order_by("display_order", "id")
            else:
                kwargs["queryset"] = ProductColour.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("get_full_name", "product", "colour", "size", "sku", "price", "original_price", "stock", "is_active")
    list_filter = ("product", "is_active", "colour", "size")
    search_fields = ("sku", "barcode", "product__name", "colour__name", "size__name")
    list_editable = ("price", "stock", "is_active")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ("size", "colour"):
            variant_id = request.resolver_match.kwargs.get("object_id") if request.resolver_match else None
            if variant_id:
                variant = ProductVariant.objects.filter(pk=variant_id).first()
                if variant:
                    if db_field.name == "size":
                        kwargs["queryset"] = ProductSize.objects.filter(product_id=variant.product_id).order_by("display_order", "id")
                    elif db_field.name == "colour":
                        kwargs["queryset"] = ProductColour.objects.filter(product_id=variant.product_id).order_by("display_order", "id")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ---------------------------------------------------------------------------
# PRODUCT ADMIN
# ---------------------------------------------------------------------------

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm

    inlines = [ProductImageInline, ProductColourInline, ProductSizeInline, ProductVariantInline]
    actions = [
        "export_selected_to_excel",
        "activate_products",
        "deactivate_products",
        "mark_available",
        "mark_unavailable",
        "generate_variants_action",
    ]

    list_display = (
        "image_preview",
        "product_number_display",
        "name",
        "brand_display",
        "category_badge",
        "product_type_badge",
        "pricing_display",
        "stock_badge",
        "units_sold_display",
        "sales_revenue_display",
        "status_badge",
        "is_available",
        "is_deal_of_the_day",
        "is_featured",
        "updated_at_display",
    )

    list_filter = (
        ProductQuickFilter,
        ("category_ref", admin.RelatedOnlyFieldListFilter),
        ("subcategory_ref", admin.RelatedOnlyFieldListFilter),
        StockLevelFilter,
        "product_type",
        "is_active",
        "is_available",
        "is_deal_of_the_day",
        "is_featured",
        DiscountStatusFilter,
        "created_at",
    )

    search_fields = (
        "product_number",
        "name",
        "brand",
        "description",
        "category",
        "subcategory",
        "variants__sku",
        "variants__variant_name",
    )

    list_editable = (
        "is_available",
        "is_deal_of_the_day",
        "is_featured",
    )

    list_display_links = ("image_preview", "product_number_display", "name")
    ordering = ("-created_at",)
    list_per_page = 25
    date_hierarchy = "created_at"
    filter_horizontal = ("similar_products",)

    change_list_template = "admin/products/product/change_list.html"

    fieldsets = (
        (
            "1. Basic Information",
            {
                "fields": (
                    "name",
                    "product_number",
                    "brand",
                    "description",
                ),
                "description": "Enter the product name, SKU / product number, brand, and detailed description.",
            },
        ),
        (
            "2. Category & Subcategory",
            {
                "fields": (
                    "category_ref",
                    "subcategory_ref",
                ),
                "description": "Assign this product to an active category and matching subcategory from your store database.",
            },
        ),
        (
            "3. Product Type & Units",
            {
                "fields": (
                    "product_type",
                    "variant_display_style",
                    ("unit_type", "unit", "unit_value"),
                    "variant_generator_link",
                ),
                "description": "Choose Simple Product for standard items with a single price & stock. Choose Variable Product to unlock options (Weights, Volumes, Packs, Colours, Sizes) with independent pricing & inventory below.",
            },
        ),
        (
            "4. Pricing & Inventory",
            {
                "fields": (
                    ("original_price", "price"),
                    ("discount_enabled", "discount_type", "discount_value"),
                    ("stock", "is_available"),
                ),
                "description": "Set MRP, discount rules, and selling price. For simple products, this is the final price charged to shoppers. For variable products, this acts as the base starting price.",
            },
        ),
        (
            "5. Product Images & Gallery",
            {
                "fields": (
                    "image",
                    "image_preview_large",
                    "image_url",
                    "bulk_gallery_images",
                ),
                "description": "Upload a primary image or enter direct image link. Use 'Bulk Upload Gallery Images' to select multiple photos at once. Additional gallery images can also be reviewed and reordered in the table below.",
            },
        ),
        (
            "6. Similar Products & Linked Styles (Meesho / Amazon Style Designs)",
            {
                "fields": (
                    "similar_products",
                ),
                "description": "Select different styles, pendant designs, or matching products. These will appear as clickable style thumbnail cards under the product image on the customer site (just like Meesho / Amazon), allowing shoppers to switch between designs with their own images and prices.",
            },
        ),
        (
            "8. Store Visibility, Preview & Save",
            {
                "fields": (
                    ("is_deal_of_the_day", "is_featured", "is_active"),
                    "live_product_preview",
                ),
                "description": "Mark 'Deal of the day' to feature in Today's Deals. 'Featured' products appear on homepage showcases. Inactive products are hidden from the store. Review the live product card preview before saving.",
            },
        ),
    )

    readonly_fields = ("image_preview_large", "variant_generator_link", "live_product_preview", "created_at")

    class Media:
        js = ("products/admin_dynamic.js",)
        css = {"all": ("products/admin_dynamic.css",)}

    # -----------------------------------------------------------------------
    # DISPLAY METHODS
    # -----------------------------------------------------------------------

    @admin.display(description="Image")
    def image_preview(self, obj):
        url = obj.get_image_url() if obj else ""
        if not url:
            url = "/static/home/images/tipsycart-logo.png"
        return format_html(
            '<img src="{}" style="width: 44px; height: 44px; object-fit: cover; border-radius: 8px; border: 1px solid #e2e8f0; background: #fff;" onerror="this.onerror=null;this.src=\'/static/home/images/tipsycart-logo.png\';" />',
            url,
        )

    @admin.display(description="Current Image")
    def image_preview_large(self, obj):
        if not obj or not obj.pk:
            return "Save product first to view image preview."
        url = obj.get_image_url()
        if obj.image:
            source_badge = format_html(
                '<span style="color: #0284c7; font-weight: 600;">✓ Uploaded from Computer:</span> {}',
                obj.image.name
            )
        elif obj.image_url:
            source_badge = format_html(
                '<span style="color: #7c3aed; font-weight: 600;">✓ External Direct URL:</span> {}',
                obj.image_url
            )
        else:
            source_badge = mark_safe('<span style="color: #64748b;">Using Default Store Image</span>')

        return format_html(
            '<div class="tc-current-image-container" data-current-url="{}" style="margin-top: 6px;">'
            '<img src="{}" style="max-width: 220px; max-height: 220px; object-fit: contain; border-radius: 10px; border: 1px solid #e2e8f0; padding: 6px; background: #fff0f5;" onerror="this.onerror=null;this.src=\'/static/home/images/tipsycart-logo.png\';" /><br>'
            '<small style="display: block; margin-top: 6px; font-size: 11px;">{}</small>'
            '</div>',
            url,
            url,
            source_badge,
        )

    @admin.display(description="Product Card Live Preview")
    def live_product_preview(self, obj):
        url = obj.get_image_url() if obj and obj.pk else "/static/home/images/tipsycart-logo.png"
        p_name = obj.name if obj and obj.pk else "Product Name"
        p_brand = obj.brand if obj and obj.pk else "TipsyCart"
        p_price = f"₹{obj.price}" if obj and obj.pk and obj.price else "₹0.00"
        p_mrp = f"₹{obj.original_price}" if obj and obj.pk and obj.original_price and obj.original_price > (obj.price or 0) else ""
        p_disc = f"{obj.discount_percentage}% OFF" if obj and obj.pk and obj.discount_percentage else ""
        p_stock = "In Stock" if (not obj or not obj.pk or obj.is_available) else "Out of Stock"
        unit_disp = f"{obj.unit_value:g} {obj.unit}" if (obj and obj.pk and obj.unit_value and obj.unit) else (obj.unit if obj and obj.pk and obj.unit else "")

        return format_html(
            '<div class="tc-admin-preview-container">'
            '  <div class="tc-preview-card">'
            '    <div class="tc-preview-card-img-wrap">'
            '      <img id="tc-card-preview-img" src="{}" alt="{}" onerror="this.onerror=null;this.src=\'/static/home/images/tipsycart-logo.png\';" />'
            '      <span id="tc-card-preview-discount" class="tc-preview-badge-disc" style="{}">{}</span>'
            '    </div>'
            '    <div class="tc-preview-card-body">'
            '      <span id="tc-card-preview-brand" class="tc-preview-brand">{}</span>'
            '      <div id="tc-card-preview-name" class="tc-preview-title">{}</div>'
            '      <div id="tc-card-preview-unit" class="tc-preview-unit" style="{}">{}</div>'
            '      <div class="tc-preview-price-row">'
            '        <span id="tc-card-preview-price" class="tc-preview-price">{}</span>'
            '        <del id="tc-card-preview-mrp" class="tc-preview-mrp" style="{}">{}</del>'
            '      </div>'
            '      <div id="tc-card-preview-stock" class="tc-preview-stock">{}</div>'
            '    </div>'
            '  </div>'
            '  <p class="tc-preview-note">💡 Real-time card preview of how your product will be displayed to shoppers across the store.</p>'
            '</div>',
            url, p_name,
            "display:inline-block;" if p_disc else "display:none;", p_disc,
            p_brand or "TipsyCart",
            p_name,
            "display:inline-block;" if unit_disp else "display:none;", unit_disp,
            p_price,
            "display:inline-block;" if p_mrp else "display:none;", p_mrp,
            p_stock,
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            units_sold_annotated=Coalesce(
                Sum("orderitem__quantity", filter=Q(orderitem__order__status__in=VALID_ORDER_STATUSES)),
                Value(0)
            ),
            sales_revenue_annotated=Coalesce(
                Sum(F("orderitem__price") * F("orderitem__quantity"), filter=Q(orderitem__order__status__in=VALID_ORDER_STATUSES)),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).select_related("category_ref", "subcategory_ref").prefetch_related("variants", "variants__size", "variants__colour")

    @admin.display(description="Product ID / SKU", ordering="product_number")
    def product_number_display(self, obj):
        sku = obj.product_number or f"TC-PRD-{obj.id}"
        return format_html('<span style="font-family: monospace; font-weight: 700; color: #475569; font-size: 11px;">{}</span>', sku)

    @admin.display(description="Brand", ordering="brand")
    def brand_display(self, obj):
        return obj.brand or "TipsyCart"

    @admin.display(description="Category & Subcategory", ordering="category")
    def category_badge(self, obj):
        cat_name = obj.category_ref.name if obj.category_ref else (obj.category or "Unassigned")
        sub_name = obj.subcategory_ref.name if obj.subcategory_ref else (obj.subcategory or "")
        if sub_name:
            sub_element = format_html('<br><small style="color: #6b7280;">↳ {}</small>', sub_name)
        else:
            sub_element = ""
        return format_html(
            '<span style="background: #fdf2f8; color: #a51655; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 11px;">{}</span>{}',
            cat_name, sub_element
        )

    @admin.display(description="Type & Variants", ordering="product_type")
    def product_type_badge(self, obj):
        if obj.is_variable:
            variants = list(obj.variants.all())
            count = len(variants)
            preview = []
            for v in variants[:3]:
                s_name = v.size.name if v.size else (f"{v.unit_value} {v.unit}".strip() if v.unit_value else (v.unit or ""))
                if s_name:
                    preview.append(s_name)
            preview_str = ", ".join(preview)
            if count > 3:
                preview_str += f" +{count - 3} more"
            return format_html(
                '<span style="background: #fdf2f8; color: #a51655; border: 1px solid #fbcfe8; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 11px;">Variable ({})</span><br><small style="color: #64748b; font-size: 10px;">{}</small>',
                count, preview_str if preview_str else "Configured"
            )
        unit_str = f"{obj.unit_value:g} {obj.unit}".strip() if obj.unit_value else (obj.unit or "")
        return format_html(
            '<span style="background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; padding: 2px 8px; border-radius: 12px; font-weight: 600; font-size: 11px;">Simple</span><br><small style="color: #64748b; font-size: 10px;">{}</small>',
            unit_str or "Standard"
        )

    @admin.display(description="Pricing (MRP / Sell)")
    def pricing_display(self, obj):
        has_discount = (obj.discount_enabled or (obj.original_price and obj.price and obj.original_price > obj.price))
        if has_discount and obj.original_price and obj.original_price > obj.price:
            pct = obj.discount_percentage
            return format_html(
                '<del style="color: #94a3b8; font-size: 11px;">₹{}</del> '
                '<strong style="color: #15803d; font-size: 13px;">₹{}</strong> '
                '<span style="background: #fee2e2; color: #b91c1c; font-size: 10px; font-weight: 800; padding: 1px 5px; border-radius: 4px;">{}% OFF</span>',
                obj.original_price, obj.price, pct
            )
        return format_html('<strong style="color: #1e293b; font-size: 13px;">₹{}</strong>', obj.price)

    @admin.display(description="Stock", ordering="stock")
    def stock_badge(self, obj):
        if obj.stock == 0:
            return format_html(
                '<span style="background: #fee2e2; color: #991b1b; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700;">{}</span>',
                "OUT OF STOCK"
            )
        elif obj.stock <= 10:
            return format_html(
                '<span style="background: #fef3c7; color: #92400e; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700;">LOW: {} left</span>',
                obj.stock,
            )
        return format_html(
            '<span style="background: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700;">{} units</span>',
            obj.stock,
        )

    @admin.display(description="Units Sold", ordering="units_sold_annotated")
    def units_sold_display(self, obj):
        qty = getattr(obj, "units_sold_annotated", 0)
        return format_html(
            '<span style="font-weight: 700; color: #0284c7; font-size: 12px;">{}</span>',
            f"{qty:,}"
        )

    @admin.display(description="Sales Revenue", ordering="sales_revenue_annotated")
    def sales_revenue_display(self, obj):
        rev = getattr(obj, "sales_revenue_annotated", Decimal("0.00"))
        return format_html(
            '<strong style="color: #a51655; font-size: 12px;">₹{}</strong>',
            f"{rev:,.2f}"
        )

    @admin.display(description="Status", ordering="is_active")
    def status_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span style="background: #dcfce7; color: #15803d; padding: 2px 7px; border-radius: 8px; font-weight: 700; font-size: 11px;">Active</span>')
        return mark_safe('<span style="background: #f3f4f6; color: #6b7280; padding: 2px 7px; border-radius: 8px; font-weight: 600; font-size: 11px;">Inactive</span>')

    @admin.display(description="Created Date", ordering="created_at")
    def updated_at_display(self, obj):
        dt = getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)
        if dt:
            return timezone.localtime(dt).strftime("%d %b %Y, %I:%M %p")
        return "—"

    # -----------------------------------------------------------------------
    # BULK ADMIN ACTIONS
    # -----------------------------------------------------------------------

    @admin.action(description="📥 Export selected products to Excel (.xlsx)")
    def export_selected_to_excel(self, request, queryset):
        date_str = timezone.now().strftime("%Y%m%d")
        filename = f"TipsyCart_Selected_Products_{date_str}.xlsx"
        buffer = generate_category_subcategory_excel(
            queryset,
            filter_description=f"Admin Selected ({queryset.count()} Products)",
        )
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @admin.action(description="✓ Mark selected products as In Stock / Available")
    def mark_available(self, request, queryset):
        updated = queryset.update(is_available=True)
        self.message_user(request, f"{updated} products marked as Available.", level=messages.SUCCESS)

    @admin.action(description="✗ Mark selected products as Unavailable")
    def mark_unavailable(self, request, queryset):
        updated = queryset.update(is_available=False)
        self.message_user(request, f"{updated} products marked as Unavailable.", level=messages.SUCCESS)

    @admin.action(description="★ Mark selected products as Featured on Homepage")
    def mark_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f"{updated} products featured on store.", level=messages.SUCCESS)

    @admin.action(description="☆ Remove Featured status from selected products")
    def unmark_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f"{updated} products unfeatured.", level=messages.SUCCESS)

    @admin.display(description="Type", ordering="product_type")
    def product_type_badge(self, obj):
        if obj.is_variable:
            count = obj.variants.count()
            return format_html(
                '<span style="background: #fdf2f8; color: #a51655; border: 1px solid #fbcfe8; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 11px;">Variable ({})</span>',
                count,
            )
        return mark_safe(
            '<span style="background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; padding: 2px 8px; border-radius: 12px; font-weight: 600; font-size: 11px;">Simple</span>'
        )

    @admin.display(description="Variant Tools")
    def variant_generator_link(self, obj):
        if not obj or not obj.pk:
            return mark_safe(
                '<div style="background: #eff6ff; padding: 14px 18px; border-radius: 10px; border: 1px solid #bfdbfe; margin-top: 6px;">'
                '<div style="font-weight: 700; color: #1e40af; font-size: 13px; margin-bottom: 6px;">'
                'ℹ️ Variable Product Setup Guide:'
                '</div>'
                '<ol style="margin: 0; padding-left: 20px; color: #1e3a8a; font-size: 12px; line-height: 1.6;">'
                '<li>Select <strong>Variable Product</strong> above, then enter Basic Info (Name, Category, Base Price).</li>'
                '<li>Click <strong>"Save and continue editing"</strong> at the bottom of the page.</li>'
                '<li>In <strong>Section 6</strong> below, add your Sizes/Weights (e.g. <code>250g</code>, <code>500g</code>, <code>1 kg</code>).</li>'
                '<li>Click <strong>"⚡ Auto-Generate All Variant Combinations"</strong> here to automatically create all variant rows!</li>'
                '</ol>'
                '</div>'
            )
        url = reverse("admin:products_product_generate_variants", args=[obj.pk])
        var_count = obj.variants.count()
        col_count = obj.colours.count()
        size_count = obj.sizes.count()
        return format_html(
            '<div style="background: #fff0f5; padding: 14px 18px; border-radius: 10px; border: 1px solid #fbcfe8; margin-top: 6px;">'
            '<p style="margin: 0 0 10px 0; color: #831843; font-weight: 600; font-size: 13px;">'
            'Colours added: <strong>{}</strong> &nbsp;|&nbsp; Sizes added: <strong>{}</strong> &nbsp;|&nbsp; Active Variants: <strong>{}</strong>'
            '</p>'
            '<a href="{}" class="button" style="background: linear-gradient(135deg, #ec4899, #a51655); color: white !important; font-weight: 700; padding: 9px 18px; border-radius: 8px; text-decoration: none; display: inline-block; box-shadow: 0 4px 12px rgba(165, 22, 85, 0.2);">'
            '⚡ Auto-Generate All Variant Combinations'
            '</a>'
            '<p style="margin: 8px 0 0 0; font-size: 11px; color: #9d174d; line-height: 1.4;">'
            'Click to automatically create Cartesian combinations (Colours × Sizes) with default pricing and stock. Then edit individual prices, discounts, and inventory in the Product Variants section below.'
            '</p>'
            '</div>',
            col_count, size_count, var_count, url
        )

    @admin.action(description="👁️ Activate selected products (Visible in Store)")
    def activate_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} products activated.", level=messages.SUCCESS)

    @admin.action(description="🚫 Deactivate selected products (Hide from Store)")
    def deactivate_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} products hidden from store.", level=messages.SUCCESS)

    @admin.action(description="⚡ Generate Variant Combinations for selected products")
    def generate_variants_action(self, request, queryset):
        total_created = 0
        for product in queryset:
            if product.product_type != "variable":
                product.product_type = "variable"
                product.save(update_fields=["product_type"])
            created, _ = self._generate_combinations_for_product(product)
            total_created += created
        self.message_user(
            request,
            f"⚡ Generated {total_created} new variant combinations for selected products.",
            level=messages.SUCCESS
        )

    def _generate_combinations_for_product(self, product):
        colours = list(product.colours.filter(is_active=True))
        sizes = list(product.sizes.filter(is_active=True))
        if not colours and not sizes:
            return 0, 0

        c_list = colours if colours else [None]
        s_list = sizes if sizes else [None]
        created_count = 0
        existing_count = 0

        for c in c_list:
            for s in s_list:
                v_name = ""
                if c and s:
                    v_name = f"{c.name} / {s.name}"
                elif s:
                    v_name = s.name
                elif c:
                    v_name = c.name
                else:
                    v_name = "Standard"

                var, created = ProductVariant.objects.get_or_create(
                    product=product,
                    colour=c,
                    size=s,
                    defaults={
                        "price": product.price,
                        "original_price": product.original_price or product.price,
                        "discount_enabled": product.discount_enabled,
                        "discount_type": product.discount_type,
                        "discount_value": product.discount_value,
                        "stock": product.stock,
                        "is_active": True,
                        "unit": product.unit or "",
                        "variant_name": v_name,
                    }
                )
                if created:
                    created_count += 1
                else:
                    existing_count += 1
        return created_count, existing_count

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.save()
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        # 1. Main Product Bulk Gallery Images
        bulk_files = request.FILES.getlist("bulk_gallery_images")
        if bulk_files and form.instance and form.instance.pk:
            current_max_order = form.instance.gallery_images.count()
            for idx, f in enumerate(bulk_files):
                ProductImage.objects.create(
                    product=form.instance,
                    image=f,
                    alt_text=form.instance.name,
                    display_order=current_max_order + idx + 1,
                )
            self.message_user(
                request,
                f"📸 Successfully uploaded {len(bulk_files)} gallery image(s) for {form.instance.name}.",
                level=messages.SUCCESS
            )

        # 2. Multi-Image Management for Product Colours (Per-Colour Multi-Uploads, Primary & Deletions)
        if form.instance and form.instance.pk:
            product = form.instance
            for formset in formsets:
                if getattr(formset, "model", None) == ProductColour:
                    for colour_form in formset.forms:
                        if not colour_form.cleaned_data or colour_form.cleaned_data.get("DELETE"):
                            continue
                        colour = colour_form.instance
                        if not colour or not colour.pk:
                            continue
                        prefix = colour_form.prefix

                        # A. Update Primary Photo Selection
                        primary_img_id = request.POST.get(f"colour_primary_{prefix}")
                        if primary_img_id:
                            try:
                                p_id = int(primary_img_id)
                                colour.images.filter(is_primary=True).exclude(id=p_id).update(is_primary=False)
                                colour.images.filter(id=p_id).update(is_primary=True)
                            except (ValueError, TypeError):
                                pass

                        # B. Deletions and Reordering for existing photos
                        for img in list(colour.images.all()):
                            if request.POST.get(f"colour_delete_img_{img.id}") == "1":
                                img.delete()
                            else:
                                order_val = request.POST.get(f"colour_img_order_{img.id}")
                                if order_val is not None and str(order_val).strip() != "":
                                    try:
                                        new_order = int(order_val)
                                        if img.display_order != new_order:
                                            img.display_order = new_order
                                            img.save(update_fields=["display_order"])
                                    except (ValueError, TypeError):
                                        pass

                        # C. Bulk Multiple Files Uploaded for this Colour
                        new_files = request.FILES.getlist(f"colour_bulk_files_{prefix}")
                        if new_files:
                            has_primary = colour.images.filter(is_primary=True).exists()
                            current_max = colour.images.count()
                            for idx, f in enumerate(new_files):
                                is_prim = (not has_primary and idx == 0)
                                ProductColourImage.objects.create(
                                    colour=colour,
                                    image=f,
                                    display_order=current_max + idx + 1,
                                    is_primary=is_prim,
                                )
                            self.message_user(
                                request,
                                f"🎨 Uploaded {len(new_files)} photo(s) for colour '{colour.name}'.",
                                level=messages.SUCCESS
                            )

                        # D. Ensure at least one image is primary if images exist
                        if colour.images.exists() and not colour.images.filter(is_primary=True).exists():
                            first_img = colour.images.order_by("display_order", "id").first()
                            if first_img:
                                first_img.is_primary = True
                                first_img.save(update_fields=["is_primary"])

    def generate_variants_view(self, request, product_id):
        product = self.get_object(request, product_id)
        if not product:
            messages.error(request, "Product not found.")
            return redirect("admin:products_product_changelist")

        if product.product_type != "variable":
            product.product_type = "variable"
            product.save(update_fields=["product_type"])

        created, existing = self._generate_combinations_for_product(product)
        if created == 0 and existing == 0:
            messages.warning(
                request,
                f"Please add at least one Colour or Size in the sections below before generating combinations."
            )
        elif created > 0:
            messages.success(
                request,
                f"⚡ Successfully generated {created} new variant combinations for '{product.name}'! (Existing: {existing})"
            )
        else:
            messages.info(
                request,
                f"All {existing} variant combinations already exist for '{product.name}'."
            )
        return redirect("admin:products_product_change", product_id)

    # -----------------------------------------------------------------------
    # CUSTOM URLS
    # -----------------------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "export-excel/",
                self.admin_site.admin_view(self.export_excel_view),
                name="products_product_export_excel",
            ),
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name="products_product_import_excel",
            ),
            path(
                "import-excel/confirm/",
                self.admin_site.admin_view(self.confirm_import_excel_view),
                name="products_product_import_excel_confirm",
            ),
            path(
                "import-excel/download-sample/",
                self.admin_site.admin_view(self.download_sample_excel_view),
                name="products_product_sample_excel",
            ),
            path(
                "import-excel/download-errors/",
                self.admin_site.admin_view(self.download_import_errors_view),
                name="products_product_import_errors",
            ),
            path(
                "<int:product_id>/generate-variants/",
                self.admin_site.admin_view(self.generate_variants_view),
                name="products_product_generate_variants",
            ),
            path(
                "import-csv/",
                self.admin_site.admin_view(self.import_csv),
                name="products_product_import",
            ),
            path(
                "import-zip/",
                self.admin_site.admin_view(self.import_zip),
                name="products_product_zip_import",
            ),
            path(
                "api/subcategories/",
                self.admin_site.admin_view(self.subcategories_api),
                name="products_subcategories_api",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        # Preload active categories and their subcategories for the dynamic Excel export modal
        categories_data = []
        for cat in Category.objects.filter(is_active=True).prefetch_related("subcategories").order_by("display_order", "name"):
            subcats = [
                {"id": sub.id, "name": sub.name}
                for sub in cat.subcategories.filter(is_active=True).order_by("display_order", "name")
            ]
            categories_data.append({
                "id": cat.id,
                "name": cat.name,
                "subcategories": subcats,
            })
        extra_context["export_categories_json"] = json.dumps(categories_data)
        extra_context["export_categories"] = categories_data
        return super().changelist_view(request, extra_context=extra_context)

    def export_excel_view(self, request):
        """
        Dynamically exports products to a professional 3-worksheet Excel (.xlsx) file.
        Supports:
        - All Products
        - Category-wise export (includes all subcategories)
        - Subcategory-wise export
        - Simple products only (all / within category / within subcategory)
        - Variable products only (all / within category / within subcategory)
        - Respects active changelist filters, searches, and stock statuses.
        - Generates clean, dynamic filenames based on exported data.
        """
        queryset = self.get_queryset(request)

        # 1. Resolve Category and Subcategory
        cat_id = request.GET.get("category_id") or request.GET.get("category_ref__id__exact")
        subcat_id = request.GET.get("subcategory_id") or request.GET.get("subcategory_ref__id__exact")

        category_obj = None
        subcategory_obj = None

        if cat_id:
            try:
                category_obj = Category.objects.filter(id=int(cat_id)).first()
            except (ValueError, TypeError):
                category_obj = None

        if subcat_id:
            try:
                subcategory_obj = Subcategory.objects.filter(id=int(subcat_id)).first()
                if subcategory_obj and not category_obj:
                    category_obj = subcategory_obj.category
            except (ValueError, TypeError):
                subcategory_obj = None

        # Filter by Category / Subcategory
        if subcategory_obj:
            queryset = queryset.filter(
                Q(subcategory_ref=subcategory_obj) | Q(subcategory__iexact=subcategory_obj.name)
            )
        elif category_obj:
            queryset = queryset.filter(
                Q(category_ref=category_obj) | Q(category__iexact=category_obj.name)
            )

        # 2. Resolve Product Type (Simple / Variable / All)
        product_type = request.GET.get("product_type")
        if not product_type:
            q_filter = request.GET.get("quick_filter")
            if q_filter in ("simple", "variable"):
                product_type = q_filter

        if product_type in ("simple", "variable"):
            queryset = queryset.filter(product_type=product_type)

        # 3. Quick Filter (if not already handled by product_type)
        quick_filter = request.GET.get("quick_filter")
        if quick_filter:
            if quick_filter == "in_stock":
                queryset = queryset.filter(stock__gt=10)
            elif quick_filter == "low_stock":
                queryset = queryset.filter(stock__gt=0, stock__lte=10)
            elif quick_filter == "out_of_stock":
                queryset = queryset.filter(stock=0)
            elif quick_filter == "active":
                queryset = queryset.filter(is_active=True)
            elif quick_filter == "inactive":
                queryset = queryset.filter(is_active=False)

        # 4. Stock status filter
        stock_status = request.GET.get("stock_status")
        if stock_status == "out_of_stock":
            queryset = queryset.filter(stock=0)
        elif stock_status == "low_stock":
            queryset = queryset.filter(stock__gt=0, stock__lte=10)
        elif stock_status == "in_stock":
            queryset = queryset.filter(stock__gt=10)

        # 5. Search query
        search_query = request.GET.get("q")
        if search_query:
            search_query = search_query.strip()
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(product_number__icontains=search_query)
                | Q(brand__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        # 6. Active status filter
        is_active_param = request.GET.get("is_active__exact")
        if is_active_param in ("1", "true", "True"):
            queryset = queryset.filter(is_active=True)
        elif is_active_param in ("0", "false", "False"):
            queryset = queryset.filter(is_active=False)

        # 7. Construct dynamic description for report banner
        filter_parts = []
        if category_obj:
            filter_parts.append(f"Category: {category_obj.name}")
        if subcategory_obj:
            filter_parts.append(f"Subcategory: {subcategory_obj.name}")
        if product_type in ("simple", "variable"):
            filter_parts.append(f"Product Type: {product_type.title()} Products Only")
        if quick_filter and quick_filter not in ("simple", "variable"):
            filter_parts.append(f"Filter: {quick_filter.replace('_', ' ').title()}")
        if search_query:
            filter_parts.append(f"Search: '{search_query}'")

        filter_desc = " | ".join(filter_parts) if filter_parts else "All Products (Full Catalog)"

        # 8. Construct dynamic filename (Requirement 8)
        date_str = timezone.now().strftime("%Y%m%d")
        filename_parts = ["TipsyCart"]

        def _clean_for_filename(name_str):
            cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", str(name_str).strip())
            return cleaned.strip("_")

        if category_obj:
            filename_parts.append(_clean_for_filename(category_obj.name))
            if subcategory_obj:
                filename_parts.append(_clean_for_filename(subcategory_obj.name))
        else:
            filename_parts.append("All_Products")

        if product_type == "simple":
            filename_parts.append("Simple_Products")
        elif product_type == "variable":
            filename_parts.append("Variable_Products")

        filename_parts.append(date_str)
        filename = "_".join(filename_parts) + ".xlsx"

        # 9. Generate 3-worksheet workbook
        cat_name_str = category_obj.name if category_obj else None
        subcat_name_str = subcategory_obj.name if subcategory_obj else None
        buffer = generate_category_subcategory_excel(
            queryset,
            filter_description=filter_desc,
            category_name=cat_name_str,
            subcategory_name=subcat_name_str,
            product_type=product_type,
        )

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def download_sample_excel_view(self, request):
        """Downloads a formatted sample template for importing products."""
        buffer = generate_sample_excel_template()
        filename = "tipsycart_products_import_template.xlsx"
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def download_import_errors_view(self, request):
        """Downloads rejected rows from the last Excel validation in .xlsx format."""
        token = request.GET.get("token")
        import_data = request.session.get(f"excel_import_{token}") if token else None
        if not import_data or not import_data.get("invalid_rows"):
            self.message_user(request, "No rejected rows found or import session expired.", level=messages.WARNING)
            return redirect("admin:products_product_changelist")

        buffer = generate_import_error_excel(import_data["invalid_rows"])
        filename = f"tipsycart_import_rejected_rows_{token[:8]}.xlsx"
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def import_excel_view(self, request):
        """
        Handles upload and validation preview of product spreadsheets.
        Supports both:
        1. Standalone Excel files (.xlsx)
        2. ZIP packages (.zip) containing an Excel file (.xlsx) + folder of product images.
           Images are staged in a secure temp folder and automatically mapped by filename.
        """
        if request.method == "POST":
            # Collect all files uploaded across single or multiple inputs
            all_files = []
            for k in ("excel_file", "zip_file", "zip_images_file", "files"):
                all_files.extend(request.FILES.getlist(k))

            if not all_files:
                return render(
                    request,
                    "admin/products/product/excel_import.html",
                    {
                        **self.admin_site.each_context(request),
                        "title": "Import Products from Excel (.xlsx or .zip)",
                        "opts": self.model._meta,
                        "error_message": "Please select a valid .xlsx Excel file or .zip package to upload.",
                    }
                )

            excel_upload = None
            zip_upload = None

            for f in all_files:
                fn = f.name.lower()
                if fn.endswith((".xlsx", ".xls", ".csv")) and not excel_upload:
                    excel_upload = f
                elif fn.endswith(".zip") and not zip_upload:
                    zip_upload = f

            token = f"tc_imp_{uuid.uuid4().hex[:12]}"
            image_files_map = {}
            excel_bytes = None
            temp_img_dir = None

            # Case 1: Separate Excel file + separate ZIP archive of images uploaded together in one go
            if excel_upload and zip_upload:
                excel_bytes = excel_upload
                try:
                    zf = zipfile.ZipFile(zip_upload)
                    temp_img_dir = os.path.join(tempfile.gettempdir(), f"tc_import_imgs_{token}")
                    os.makedirs(temp_img_dir, exist_ok=True)
                    for info in zf.infolist():
                        if info.is_dir() or "__macosx" in info.filename.lower() or info.filename.startswith("."):
                            continue
                        clean_path = sanitize_zip_path(info.filename)
                        base_name = os.path.basename(clean_path).strip()
                        _, ext = os.path.splitext(base_name.lower())
                        if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
                            img_data = zf.read(info.filename)
                            save_path = os.path.join(temp_img_dir, base_name.lower())
                            with open(save_path, "wb") as f_img:
                                f_img.write(img_data)
                            image_files_map[base_name.lower()] = img_data
                except Exception as e:
                    if temp_img_dir and os.path.exists(temp_img_dir):
                        shutil.rmtree(temp_img_dir, ignore_errors=True)
                    return render(
                        request,
                        "admin/products/product/excel_import.html",
                        {
                            **self.admin_site.each_context(request),
                            "title": "Import Products from Excel (.xlsx or .zip)",
                            "opts": self.model._meta,
                            "error_message": f"Failed to extract product images ZIP archive: {str(e)}",
                        }
                    )

            # Case 2: Only a ZIP was uploaded (could contain spreadsheet + images)
            elif zip_upload and not excel_upload:
                try:
                    zf = zipfile.ZipFile(zip_upload)
                    spreadsheet_name = None
                    temp_img_dir = os.path.join(tempfile.gettempdir(), f"tc_import_imgs_{token}")
                    os.makedirs(temp_img_dir, exist_ok=True)

                    for info in zf.infolist():
                        if info.is_dir() or "__macosx" in info.filename.lower() or info.filename.startswith("."):
                            continue
                        clean_path = sanitize_zip_path(info.filename)
                        base_name = os.path.basename(clean_path).strip()
                        _, ext = os.path.splitext(base_name.lower())

                        if ext in (".xlsx", ".csv"):
                            if not spreadsheet_name or "product" in base_name.lower():
                                spreadsheet_name = info.filename
                        elif ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
                            img_data = zf.read(info.filename)
                            save_path = os.path.join(temp_img_dir, base_name.lower())
                            with open(save_path, "wb") as f_img:
                                f_img.write(img_data)
                            image_files_map[base_name.lower()] = img_data

                    if not spreadsheet_name:
                        if os.path.exists(temp_img_dir):
                            shutil.rmtree(temp_img_dir, ignore_errors=True)
                        return render(
                            request,
                            "admin/products/product/excel_import.html",
                            {
                                **self.admin_site.each_context(request),
                                "title": "Import Products from Excel (.xlsx or .zip)",
                                "opts": self.model._meta,
                                "error_message": "No .xlsx or .csv spreadsheet found inside this ZIP archive. If your images are in this ZIP, please also select your Excel (.xlsx) file in the spreadsheet box below.",
                            }
                        )

                    excel_bytes = io.BytesIO(zf.read(spreadsheet_name))
                except Exception as e:
                    if temp_img_dir and os.path.exists(temp_img_dir):
                        shutil.rmtree(temp_img_dir, ignore_errors=True)
                    return render(
                        request,
                        "admin/products/product/excel_import.html",
                        {
                            **self.admin_site.each_context(request),
                            "title": "Import Products from Excel (.xlsx or .zip)",
                            "opts": self.model._meta,
                            "error_message": f"Failed to extract ZIP archive: {str(e)}",
                        }
                    )

            # Case 3: Only an Excel file was uploaded
            elif excel_upload:
                excel_bytes = excel_upload

            else:
                return render(
                    request,
                    "admin/products/product/excel_import.html",
                    {
                        **self.admin_site.each_context(request),
                        "title": "Import Products from Excel (.xlsx or .zip)",
                        "opts": self.model._meta,
                        "error_message": "Unsupported file format. Please upload a .xlsx Excel file and/or a .zip archive.",
                    }
                )

            preview_res = parse_and_validate_excel(excel_bytes, image_files_map=image_files_map)
            if not preview_res.get("success"):
                if temp_img_dir and os.path.exists(temp_img_dir):
                    shutil.rmtree(temp_img_dir, ignore_errors=True)
                return render(
                    request,
                    "admin/products/product/excel_import.html",
                    {
                        **self.admin_site.each_context(request),
                        "title": "Import Products from Excel (.xlsx or .zip)",
                        "opts": self.model._meta,
                        "error_message": preview_res.get("error"),
                    }
                )

            token = preview_res["token"]
            request.session[f"excel_import_{token}"] = preview_res
            if temp_img_dir:
                request.session[f"excel_import_imgdir_{token}"] = temp_img_dir
                preview_res["images_attached_count"] = len(image_files_map)
            request.session.modified = True

            context = {
                **self.admin_site.each_context(request),
                "title": "Excel Import Preview & Verification",
                "opts": self.model._meta,
                "preview": preview_res,
                "is_zip": bool(temp_img_dir),
                "images_count": len(image_files_map),
            }
            return render(request, "admin/products/product/excel_import_preview.html", context)

        context = {
            **self.admin_site.each_context(request),
            "title": "Import Products from Excel (.xlsx or .zip)",
            "opts": self.model._meta,
        }
        return render(request, "admin/products/product/excel_import.html", context)

    def confirm_import_excel_view(self, request):
        """Executes the verified rows into the database atomically upon admin confirmation."""
        if request.method != "POST":
            return redirect("admin:products_product_changelist")

        token = request.POST.get("token")
        auto_cats = request.POST.get("auto_create_categories") == "on"

        import_data = request.session.get(f"excel_import_{token}") if token else None
        if not import_data or not import_data.get("valid_rows"):
            self.message_user(request, "Import session expired. Please re-upload your Excel file.", level=messages.ERROR)
            return redirect("admin:products_product_import_excel")

        temp_img_dir = request.session.get(f"excel_import_imgdir_{token}")
        image_files_map = {}
        if temp_img_dir and os.path.exists(temp_img_dir):
            try:
                for fname in os.listdir(temp_img_dir):
                    fpath = os.path.join(temp_img_dir, fname)
                    if os.path.isfile(fpath):
                        with open(fpath, "rb") as f_img:
                            image_files_map[fname.lower()] = f_img.read()
            except Exception as e:
                pass

        valid_rows = import_data["valid_rows"]
        stats = commit_excel_import(
            valid_rows,
            auto_create_missing_categories=auto_cats,
            image_files_map=image_files_map,
        )

        if temp_img_dir and os.path.exists(temp_img_dir):
            shutil.rmtree(temp_img_dir, ignore_errors=True)

        if f"excel_import_{token}" in request.session:
            del request.session[f"excel_import_{token}"]
        if f"excel_import_imgdir_{token}" in request.session:
            del request.session[f"excel_import_imgdir_{token}"]

        created = stats.get("created", 0)
        updated = stats.get("updated", 0)
        variants = stats.get("variants_created", 0)
        gallery = stats.get("gallery_images_added", 0)
        errors = stats.get("errors", [])

        summary_msg = f"🎉 Bulk import complete! {created} new products created, {updated} updated."
        if variants > 0:
            summary_msg += f" {variants} variants/weights created."
        if gallery > 0:
            summary_msg += f" {gallery} gallery images attached."
        if image_files_map:
            summary_msg += f" Cloudinary images uploaded successfully."

        if errors:
            self.message_user(
                request,
                f"{summary_msg} (Warnings: {len(errors)} items had minor issues).",
                level=messages.WARNING
            )
        else:
            self.message_user(request, summary_msg, level=messages.SUCCESS)
        return redirect("admin:products_product_changelist")

    def subcategories_api(self, request):
        category_id = request.GET.get("category_id")
        if not category_id:
            return JsonResponse({"subcategories": []})
        subcats = list(
            Subcategory.objects.filter(category_id=category_id, is_active=True)
            .order_by("display_order", "name")
            .values("id", "name")
        )
        return JsonResponse({"subcategories": subcats})

    # -----------------------------------------------------------------------
    # CSV IMPORTER
    # -----------------------------------------------------------------------

    def validate_csv(self, uploaded_file):
        if uploaded_file.size > MAX_CSV_SIZE:
            raise ValueError("CSV file must be smaller than 10 MB.")

        if not uploaded_file.name.lower().endswith(".csv"):
            raise ValueError("Only CSV files are allowed.")

        content = uploaded_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))

        required_columns = {"name", "price"}

        if not reader.fieldnames:
            raise ValueError("CSV file is empty.")

        reader.fieldnames = [(field or "").strip().lower() for field in reader.fieldnames]

        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise ValueError("Missing columns: " + ", ".join(sorted(missing)))

        valid_rows = []
        errors = []
        duplicate_count = 0
        seen_in_file = set()

        for row_number, row in enumerate(reader, start=2):
            try:
                name = (row.get("name") or "").strip()
                description = (row.get("description") or "").strip()
                cat_name = (row.get("category") or "Daily Essentials").strip()
                subcategory = (row.get("subcategory") or "").strip()
                brand = (row.get("brand") or "TipsyCart").strip()
                image_url = (row.get("image_url") or "").strip()
                pnum = (row.get("product_number") or "").strip()

                if not name:
                    raise ValueError("Product name is required.")

                price_raw = (row.get("price") or "").strip().replace("₹", "")
                price = Decimal(price_raw)
                if not price.is_finite() or price < 0:
                    raise ValueError("Price must be non-negative.")

                stock = int((row.get("stock") or "50").strip())

                duplicate_key = (name.casefold(), brand.casefold())
                if duplicate_key in seen_in_file or Product.objects.filter(name__iexact=name, brand__iexact=brand).exists():
                    duplicate_count += 1
                    continue

                seen_in_file.add(duplicate_key)

                valid_rows.append({
                    "name": name,
                    "product_number": pnum,
                    "description": description,
                    "category": cat_name,
                    "subcategory": subcategory,
                    "brand": brand,
                    "price": price,
                    "original_price": price,
                    "stock": stock,
                    "image_url": image_url,
                    "is_active": True,
                })

            except (ValueError, InvalidOperation, ValidationError, TypeError) as error:
                errors.append(f"Row {row_number}: {error}")

        return valid_rows, duplicate_count, errors

    def import_csv(self, request):
        if request.method == "POST":
            uploaded_file = request.FILES.get("csv_file")
            action = request.POST.get("action")

            if not uploaded_file:
                self.message_user(request, "Please select the CSV file.", level=messages.ERROR)
                return redirect("..")

            try:
                valid_rows, duplicate_count, errors = self.validate_csv(uploaded_file)
            except Exception as error:
                context = {
                    **self.admin_site.each_context(request),
                    "title": "Import Products from CSV",
                    "opts": self.model._meta,
                    "fatal_error": str(error),
                }
                return render(request, "admin/product_import.html", context)

            if action == "preview":
                context = {
                    **self.admin_site.each_context(request),
                    "title": "Import Products from CSV",
                    "opts": self.model._meta,
                    "preview": True,
                    "valid_count": len(valid_rows),
                    "duplicate_count": duplicate_count,
                    "error_count": len(errors),
                    "errors": errors[:50],
                }
                return render(request, "admin/product_import.html", context)

            if errors:
                self.message_user(request, "Import stopped because of CSV errors.", level=messages.ERROR)
                return redirect("..")

            imported = 0
            with transaction.atomic():
                for row in valid_rows:
                    cat, _ = Category.objects.get_or_create(name=row["category"], defaults={"is_active": True})
                    p = Product(**row)
                    p.category_ref = cat
                    p.save()
                    imported += 1

            self.message_user(
                request,
                f"Successfully imported {imported} products. {duplicate_count} duplicates skipped.",
                level=messages.SUCCESS,
            )
            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "title": "Import Products from CSV",
            "opts": self.model._meta,
        }
        return render(request, "admin/product_import.html", context)

    # -----------------------------------------------------------------------
    # BULK ZIP IMPORTER (CSV/XLSX + IMAGES)
    # -----------------------------------------------------------------------

    def import_zip(self, request):
        if request.method == "POST":
            action = request.POST.get("action", "preview")
            default_category = request.POST.get("default_category", "Daily Essentials")
            default_stock = request.POST.get("default_stock", "50")

            if action == "preview":
                uploaded_file = request.FILES.get("zip_file")
                if not uploaded_file:
                    self.message_user(request, "Please select a ZIP file to upload.", level=messages.ERROR)
                    return redirect("..")

                if not uploaded_file.name.lower().endswith(".zip"):
                    self.message_user(request, "Only .zip archive files are supported.", level=messages.ERROR)
                    return redirect("..")

                token = f"tc_{request.user.id}_{uuid.uuid4().hex[:12]}"
                temp_zip_path = os.path.join(tempfile.gettempdir(), f"{token}.zip")
                try:
                    with open(temp_zip_path, "wb") as f:
                        for chunk in uploaded_file.chunks():
                            f.write(chunk)

                    importer = ZipProductImporter(
                        open(temp_zip_path, "rb"),
                        default_category=default_category,
                        default_stock=default_stock,
                    )
                    analysis = importer.parse_and_validate()
                except Exception as e:
                    if os.path.exists(temp_zip_path):
                        try:
                            os.remove(temp_zip_path)
                        except Exception:
                            pass
                    context = {
                        **self.admin_site.each_context(request),
                        "title": "Bulk Import Products (ZIP)",
                        "opts": self.model._meta,
                        "fatal_error": str(e),
                        "category_choices": [(c.name, c.name) for c in Category.objects.all()],
                    }
                    return render(request, "admin/product_zip_import.html", context)

                context = {
                    **self.admin_site.each_context(request),
                    "title": "Bulk Import Products (ZIP) - Preview",
                    "opts": self.model._meta,
                    "preview": True,
                    "spreadsheet_name": analysis["spreadsheet_name"],
                    "valid_count": analysis["valid_count"],
                    "duplicate_count": analysis["duplicate_count"],
                    "error_count": analysis["error_count"],
                    "valid_products": analysis["valid_products"],
                    "duplicate_products": analysis["duplicate_products"],
                    "invalid_rows": analysis["invalid_rows"],
                    "unmatched_images": analysis["unmatched_images"],
                    "cached_token": token,
                    "selected_category": default_category,
                    "selected_stock": default_stock,
                    "category_choices": [(c.name, c.name) for c in Category.objects.all()],
                }
                return render(request, "admin/product_zip_import.html", context)

            elif action == "confirm":
                token = request.POST.get("cached_token", "")
                temp_zip_path = os.path.join(tempfile.gettempdir(), f"{token}.zip") if token else None

                if not temp_zip_path or not os.path.exists(temp_zip_path):
                    uploaded_file = request.FILES.get("zip_file")
                    if not uploaded_file:
                        self.message_user(
                            request,
                            "Import session expired or file not found. Please upload the ZIP file again.",
                            level=messages.ERROR,
                        )
                        return redirect(".")
                    with open(temp_zip_path, "wb") as f:
                        for chunk in uploaded_file.chunks():
                            f.write(chunk)

                try:
                    importer = ZipProductImporter(
                        open(temp_zip_path, "rb"),
                        default_category=default_category,
                        default_stock=default_stock,
                    )
                    result = importer.execute_import(
                        selected_category=default_category,
                        default_stock=int(default_stock or 50),
                    )
                    imported_count = result["imported_count"]
                    dup_count = result["skipped_duplicates"]
                    self.message_user(
                        request,
                        f"🎉 Success! {imported_count} products were successfully imported and published to TipsyCart. {dup_count} duplicates skipped.",
                        level=messages.SUCCESS,
                    )
                except Exception as e:
                    self.message_user(request, f"Import failed: {e}", level=messages.ERROR)
                finally:
                    if temp_zip_path and os.path.exists(temp_zip_path):
                        try:
                            os.remove(temp_zip_path)
                        except Exception:
                            pass

                return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk Import Products (ZIP: CSV/XLSX + Images)",
            "opts": self.model._meta,
            "category_choices": [(c.name, c.name) for c in Category.objects.all()],
        }
        return render(request, "admin/product_zip_import.html", context)
