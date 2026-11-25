import csv
import io
import json
import os
import tempfile
import uuid
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
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
from .services.zip_importer import ZipProductImporter


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


# ---------------------------------------------------------------------------
# CATEGORY ADMIN FORM & ADMIN
# ---------------------------------------------------------------------------

class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = "__all__"

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if img and hasattr(img, "size"):
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
        "product_count_badge",
        "subcategory_count_badge",
        "is_active",
        "created_at",
    )
    list_display_links = ("image_thumb", "name")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("display_order", "name")
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
        if img and hasattr(img, "size"):
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

    def clean_image(self):
        uploaded_image = self.cleaned_data.get("image")
        if uploaded_image and hasattr(uploaded_image, "size"):
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

        if discount_enabled and discount_val and discount_val > 0:
            if discount_type == "percentage" and discount_val > 99:
                self.add_error("discount_value", "Percentage discount cannot exceed 99%.")
            elif discount_type == "fixed" and orig_price and discount_val >= orig_price:
                self.add_error("discount_value", "Fixed discount cannot equal or exceed original price.")

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


class ProductColourInline(admin.TabularInline):
    model = ProductColour
    extra = 1
    fields = ("color_master", "name", "color_code", "swatch_preview", "display_order", "is_active")
    readonly_fields = ("swatch_preview",)
    show_change_link = True
    verbose_name = "Product Colour"
    verbose_name_plural = "6. Product Colours (Select from Global Colour Library or Type Custom)"

    @admin.display(description="Swatch")
    def swatch_preview(self, obj):
        code = (obj.color_code if obj else None) or (obj.color_master.hex_code if obj and obj.color_master else "#000000")
        return format_html(
            '<span class="tc-colour-swatch-circle" style="display:inline-block; width:20px; height:20px; border-radius:50%; background-color:{}; border:1px solid #94a3b8; vertical-align:middle;"></span>',
            code
        )


class ProductSizeInline(admin.TabularInline):
    model = ProductSize
    extra = 1
    fields = ("name", "display_order", "is_active")
    show_change_link = True
    verbose_name = "Product Size / Weight Option"
    verbose_name_plural = "6. Product Sizes & Options (e.g. S, M, L, XL or 250 g, 500 g, 1 kg)"


class ProductVariantInlineForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "price" in self.fields:
            self.fields["price"].required = False
            self.fields["price"].help_text = "Leave blank to inherit product price"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    form = ProductVariantInlineForm
    extra = 0
    fields = (
        "colour",
        "size",
        "variant_name",
        "unit_value",
        "unit",
        "sku",
        "original_price",
        "discount_enabled",
        "discount_value",
        "price",
        "stock",
        "is_active",
    )
    show_change_link = True
    verbose_name = "Independently Sold Variant"
    verbose_name_plural = "7. Product Variants (Independent Pricing, Discounts, SKU & Stock)"

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
    actions = ["activate_products", "deactivate_products", "generate_variants_action"]

    list_display = (
        "image_preview",
        "product_number",
        "name",
        "category_badge",
        "product_type_badge",
        "pricing_display",
        "stock_badge",
        "is_available",
        "is_featured",
        "is_active",
        "created_at",
    )

    list_filter = (
        "product_type",
        "category_ref",
        "subcategory_ref",
        "is_available",
        "is_featured",
        "discount_enabled",
        "is_active",
        StockLevelFilter,
        DiscountStatusFilter,
        "created_at",
    )

    search_fields = (
        "product_number",
        "name",
        "description",
        "brand",
        "subcategory",
        "category",
    )

    list_editable = (
        "is_available",
        "is_featured",
        "is_active",
    )

    list_display_links = ("image_preview", "name")
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
                    ("is_featured", "is_active"),
                    "live_product_preview",
                ),
                "description": "Featured products appear on homepage showcases. Inactive products are hidden from the store. Review the live product card preview before saving.",
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

    @admin.display(description="Category", ordering="category")
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

    # -----------------------------------------------------------------------
    # BULK ADMIN ACTIONS
    # -----------------------------------------------------------------------

    actions = [
        "mark_available",
        "mark_unavailable",
        "mark_featured",
        "unmark_featured",
        "activate_products",
        "deactivate_products",
    ]

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
            return "Save this product first to configure colours, sizes and auto-generate variants."
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
                        "variant_name": s.name if s else (c.name if c else "Standard"),
                    }
                )
                if created:
                    created_count += 1
                else:
                    existing_count += 1
        return created_count, existing_count

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
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
