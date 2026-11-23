
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User


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


class EmailOTP(models.Model):
    PURPOSE_CHOICES = [
        ("customer_login", "Customer Login"),
        ("delivery_login", "Delivery Partner Login"),
        ("forgot_password", "Forgot Password"),
    ]

    email = models.EmailField(db_index=True)
    otp_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=32, choices=PURPOSE_CHOICES, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    is_used = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "purpose", "is_used"]),
        ]

    def __str__(self):
        status = "Used" if self.is_used else ("Expired" if timezone.now() > self.expires_at else "Active")
        return f"{self.email} [{self.purpose}] ({status})"

    def set_otp(self, raw_otp: str):
        self.otp_hash = make_password(str(raw_otp).strip())

    def verify_otp(self, raw_otp: str):
        if self.is_used:
            return False, "This verification code has already been used. Please request a new code."

        if timezone.now() > self.expires_at:
            return False, "This verification code has expired. Please request a new code."

        if self.attempts >= self.max_attempts:
            self.is_used = True
            self.save(update_fields=["is_used"])
            return False, "Maximum verification attempts exceeded. Please request a new code."

        clean_otp = str(raw_otp or "").strip()
        if check_password(clean_otp, self.otp_hash):
            self.is_used = True
            self.save(update_fields=["is_used"])
            return True, "Verification successful."

        self.attempts += 1
        if self.attempts >= self.max_attempts:
            self.is_used = True
            self.save(update_fields=["attempts", "is_used"])
            return False, "Invalid verification code. Maximum attempts reached. Please request a new code."

        self.save(update_fields=["attempts"])
        remaining = self.max_attempts - self.attempts
        return False, f"Invalid verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."


class Customer(User):
    class Meta:
        proxy = True
        verbose_name = "Customer"
        verbose_name_plural = "Customers"


