import os
import secrets
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password

from accounts.models import EmailOTP
from accounts.services.email_service import send_otp_email

logger = logging.getLogger(__name__)
User = get_user_model()


def normalize_email(email: str) -> str:
    """Normalizes an email address consistently across the platform."""
    return str(email or "").strip().lower()


def get_client_ip(request) -> str | None:
    """Extracts client IP address from the request safely."""
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
        return ip
    return request.META.get("REMOTE_ADDR")


def generate_secure_otp() -> str:
    """Generates a 6-digit cryptographically secure numeric OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def request_otp(email_input: str, purpose: str, request=None) -> tuple[bool, str, dict]:
    """
    Validates email, enforces rate limits and resend cooldown, invalidates prior OTPs,
    creates a new hashed OTP and dispatches it via Resend.
    """
    email = normalize_email(email_input)

    # 1. Basic format validation
    if not email:
        return False, "Please enter your registered email address.", {}

    try:
        validate_email(email)
    except ValidationError:
        return False, "Please enter a valid email address.", {}

    valid_purposes = ["customer_login", "delivery_login", "forgot_password"]
    if purpose not in valid_purposes:
        return False, "Invalid verification purpose specified.", {}

    now = timezone.now()
    ip_address = get_client_ip(request)

    # 2. Account verification based on purpose
    target_user = None

    if purpose == "customer_login":
        target_user = User.objects.filter(email__iexact=email).first()
        if target_user:
            if not target_user.is_active:
                return False, "This customer account is deactivated. Please contact support.", {}

            if target_user.is_staff or target_user.is_superuser:
                return False, "Administrator accounts must use the Admin Portal at /admin/ to log in.", {}
        # New customers are welcome: OTP is dispatched and account is created seamlessly on verification!

    elif purpose == "delivery_login":
        from delivery.models import DeliveryPartner
        partner = DeliveryPartner.objects.filter(
            Q(email__iexact=email) | Q(user__email__iexact=email)
        ).select_related("user").first()

        if not partner:
            return False, "Access denied. No active Delivery Partner account found with this email.", {}

        if not partner.is_active or not partner.user.is_active:
            return False, "This delivery partner account is deactivated. Please contact store admin.", {}

        target_user = partner.user

    elif purpose == "forgot_password":
        target_user = User.objects.filter(email__iexact=email).first()
        if not target_user:
            # Privacy requirement: Do not reveal whether an email exists in the database
            return True, "If an account is associated with this email, a 6-digit verification code has been sent.", {
                "email": email,
                "cooldown": int(getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)),
            }

        if not target_user.is_active:
            return False, "This account has been deactivated. Please contact customer support.", {}

    # 3. Resend Cooldown Check (60 seconds)
    cooldown_seconds = int(getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60))
    recent_otp = EmailOTP.objects.filter(
        email=email,
        purpose=purpose,
        created_at__gte=now - timedelta(seconds=cooldown_seconds),
    ).first()

    if recent_otp:
        elapsed = (now - recent_otp.created_at).total_seconds()
        remaining = max(1, int(cooldown_seconds - elapsed))
        return False, f"Please wait {remaining} seconds before requesting a new verification code.", {
            "cooldown_remaining": remaining
        }

    # 4. Rate Limiting per Email (Max 5 requests per hour)
    one_hour_ago = now - timedelta(hours=1)
    email_hourly_count = EmailOTP.objects.filter(
        email=email,
        created_at__gte=one_hour_ago,
    ).count()

    if email_hourly_count >= 5:
        return False, "Too many OTP requests for this email. Please try again after an hour.", {}

    # 5. Rate Limiting per IP (Max 15 requests per hour)
    if ip_address:
        ip_hourly_count = EmailOTP.objects.filter(
            ip_address=ip_address,
            created_at__gte=one_hour_ago,
        ).count()
        if ip_hourly_count >= 15:
            return False, "Too many verification requests from your network. Please try again later.", {}

    # 6. Invalidate previous unverified OTPs for (email, purpose)
    EmailOTP.objects.filter(
        email=email,
        purpose=purpose,
        is_used=False,
    ).update(is_used=True)

    # 7. Generate cryptographically secure 6-digit OTP
    raw_otp = generate_secure_otp()
    expiry_seconds = int(getattr(settings, "OTP_EXPIRY_SECONDS", 300))
    expires_at = now + timedelta(seconds=expiry_seconds)

    otp_record = EmailOTP(
        email=email,
        purpose=purpose,
        expires_at=expires_at,
        ip_address=ip_address,
        max_attempts=int(getattr(settings, "OTP_MAX_ATTEMPTS", 5)),
    )
    otp_record.set_otp(raw_otp)

    # 8. Dispatch OTP via Resend
    send_success, send_info = send_otp_email(email, raw_otp, purpose)
    if not send_success:
        logger.error(f"Failed to dispatch OTP to {email}: {send_info}")
        return False, send_info, {}

    # Save OTP record only after successful dispatch
    otp_record.save()

    return True, f"A 6-digit verification code has been sent to {email}.", {
        "email": email,
        "cooldown": cooldown_seconds,
        "expires_in": expiry_seconds,
    }


def verify_otp_submission(email_input: str, raw_otp: str, purpose: str) -> tuple[bool, str, dict]:
    """
    Verifies an entered 6-digit OTP for a given normalized email and purpose.
    Enforces expiry, max attempt counter, one-time use, and secure hash check.
    """
    email = normalize_email(email_input)
    clean_otp = str(raw_otp or "").strip()

    if not email:
        return False, "Email address is required.", {}

    if not clean_otp or len(clean_otp) != 6 or not clean_otp.isdigit():
        return False, "Please enter a valid 6-digit numerical code.", {}

    otp_record = EmailOTP.objects.filter(
        email=email,
        purpose=purpose,
        is_used=False,
    ).order_by("-created_at").first()

    if not otp_record:
        return False, "No active verification code found for this email. Please request a new code.", {}

    is_valid, msg = otp_record.verify_otp(clean_otp)
    if not is_valid:
        return False, msg, {"attempts": otp_record.attempts, "max_attempts": otp_record.max_attempts}

    # Fetch associated user
    user = User.objects.filter(email__iexact=email).first()

    return True, "Verification successful.", {
        "email": email,
        "otp_id": otp_record.id,
        "user_id": user.id if user else None,
    }


def create_password_reset_token(user_id: int, email: str, otp_id: int) -> str:
    """Creates a cryptographically signed, tamper-proof reset token valid for 10 minutes."""
    data = {
        "user_id": user_id,
        "email": normalize_email(email),
        "otp_id": otp_id,
    }
    return signing.dumps(data, salt="tipsycart.password_reset")


def verify_and_apply_password_reset(token: str, new_password: str, confirm_password: str) -> tuple[bool, str]:
    """
    Verifies the reset token, validates password strength and confirmation match,
    and securely updates the user's password.
    """
    if not token:
        return False, "Missing or invalid password reset token. Please restart the reset process."

    try:
        data = signing.loads(token, salt="tipsycart.password_reset", max_age=600)
    except signing.SignatureExpired:
        return False, "The password reset session has expired (valid for 10 minutes). Please request a new code."
    except signing.BadSignature:
        return False, "Invalid or tampered reset token. Please request a new code."

    user_id = data.get("user_id")
    user = User.objects.filter(id=user_id, is_active=True).first()
    if not user:
        return False, "Associated user account was not found or is inactive."

    if not new_password or not confirm_password:
        return False, "Please fill in both new password and confirmation fields."

    if new_password != confirm_password:
        return False, "Passwords do not match. Please re-enter carefully."

    if len(new_password) < 8:
        return False, "Password must be at least 8 characters long."

    try:
        validate_password(new_password, user=user)
    except ValidationError as e:
        return False, "; ".join(e.messages)

    # Securely set new password
    user.set_password(new_password)
    user.save()
    logger.info(f"Password reset successfully completed for user {user.username} ({user.email})")

    return True, "Your password has been updated successfully! You can now log in."
