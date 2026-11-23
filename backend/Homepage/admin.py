import os
from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import StoreSetting, HeroBanner, FAQItem
from products.admin import validate_direct_image_url


class HeroBannerAdminForm(forms.ModelForm):
    class Meta:
        model = HeroBanner
        fields = "__all__"

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if img and hasattr(img, "size"):
            if img.size > 12 * 1024 * 1024:
                raise forms.ValidationError("Banner image file must be smaller than 12 MB.")
            ext = os.path.splitext(img.name)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                raise forms.ValidationError("Supported banner image formats are JPG, PNG, WEBP, and GIF.")
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


@admin.register(HeroBanner)
class HeroBannerAdmin(admin.ModelAdmin):
    form = HeroBannerAdminForm
    list_display = ("banner_preview", "title", "badge_text", "button_text", "button_link", "display_order", "is_active")
    list_display_links = ("banner_preview", "title")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "subtitle", "badge_text")
    readonly_fields = ("image_preview_large", "created_at")

    fieldsets = (
        ("Banner Content", {"fields": ("badge_text", "title", "subtitle")}),
        ("Action Button", {"fields": ("button_text", "button_link")}),
        ("Option 1: Upload Banner Image from Computer", {
            "fields": ("image", "image_preview_large"),
            "description": "Upload a custom banner photo directly from your computer (JPG, PNG, WEBP). Maximum 12 MB.",
        }),
        ("Option 2: Enter External Direct Image URL", {
            "fields": ("image_url",),
            "description": "Or enter an external direct image link. Leave blank if uploading an image file above.",
        }),
        ("Display & Visibility", {"fields": ("display_order", "is_active")}),
    )

    class Media:
        js = ("products/admin_dynamic.js",)
        css = {"all": ("products/admin_dynamic.css",)}

    @admin.display(description="Preview")
    def banner_preview(self, obj):
        url = obj.get_image_url()
        return format_html(
            '<img src="{}" style="width: 80px; height: 35px; object-fit: cover; border-radius: 4px; border: 1px solid #e2e8f0;" />',
            url,
        )

    @admin.display(description="Current Banner Image")
    def image_preview_large(self, obj):
        if not obj or not obj.pk:
            return "Save banner first to view saved image."
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
            source_badge = mark_safe('<span style="color: #64748b;">Using Default Banner</span>')

        return format_html(
            '<div class="tc-current-image-container" data-current-url="{}" style="margin-top: 6px;">'
            '<img src="{}" style="max-width: 280px; max-height: 140px; object-fit: cover; border-radius: 8px; border: 1px solid #e2e8f0; padding: 4px;" /><br>'
            '<small style="display: block; margin-top: 6px; font-size: 11px;">{}</small>'
            '</div>',
            url,
            url,
            source_badge,
        )


@admin.register(StoreSetting)
class StoreSettingAdmin(admin.ModelAdmin):
    list_display = ("store_name", "contact_phone", "contact_email", "delivery_fee", "free_delivery_threshold", "is_store_open", "updated_at")

    fieldsets = (
        ("Store Identity", {"fields": ("store_name", "tagline", "is_store_open", "announcement_text", "operating_hours")}),
        ("Contact & Location", {"fields": ("contact_email", "contact_phone", "store_address")}),
        ("Delivery & Checkout Fees", {"fields": ("delivery_fee", "free_delivery_threshold")}),
        ("Social Media Links", {"fields": ("instagram_url", "facebook_url")}),
    )

    def has_add_permission(self, request):
        if StoreSetting.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "display_order", "is_active")
    list_filter = ("category", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("question", "answer")
    ordering = ("category", "display_order", "id")

    fieldsets = (
        ("FAQ Info", {"fields": ("category", "question", "answer")}),
        ("Display", {"fields": ("display_order", "is_active")}),
    )
