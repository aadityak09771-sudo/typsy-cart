
from django.conf import settings
from django.db import models


class PushDevice(models.Model):
    PLATFORM_CHOICES = [
        ("android", "Android"),
        ("ios", "iOS"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_devices",
    )

    expo_push_token = models.CharField(
        max_length=255,
        unique=True,
    )

    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.platform}"
