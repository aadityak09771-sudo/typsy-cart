from django.contrib import admin
from django.utils.html import format_html
from .models import StoreSetting, HeroBanner, FAQItem


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


@admin.register(HeroBanner)
class HeroBannerAdmin(admin.ModelAdmin):
    list_display = ("banner_preview", "title", "badge_text", "button_text", "button_link", "display_order", "is_active")
    list_display_links = ("banner_preview", "title")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "subtitle", "badge_text")

    fieldsets = (
        ("Banner Content", {"fields": ("badge_text", "title", "subtitle")}),
        ("Action Button", {"fields": ("button_text", "button_link")}),
        ("Image", {"fields": ("image", "image_url")}),
        ("Display & Visibility", {"fields": ("display_order", "is_active")}),
    )

    @admin.display(description="Preview")
    def banner_preview(self, obj):
        url = obj.image_url or (obj.image.url if obj.image else "")
        if url:
            return format_html(
                '<img src="{}" style="width: 80px; height: 35px; object-fit: cover; border-radius: 4px; border: 1px solid #e2e8f0;" />',
                url,
            )
        return "No Image"


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
