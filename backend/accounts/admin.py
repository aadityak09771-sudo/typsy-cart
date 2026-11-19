
from django.contrib import admin
from .models import PushDevice


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "platform",
        "expo_push_token",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "expo_push_token",
    )

    list_filter = ("platform", "created_at")
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25
