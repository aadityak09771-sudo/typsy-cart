import os
import logging
from django.conf import settings
import resend

logger = logging.getLogger(__name__)

PURPOSE_TITLES = {
    "customer_login": "Your TipsyCart Login Code",
    "delivery_login": "Your TipsyCart Delivery Partner Login Code",
    "forgot_password": "Your TipsyCart Password Reset Code",
}

PURPOSE_DESCRIPTIONS = {
    "customer_login": "Use the 6-digit verification code below to securely log in to your TipsyCart customer account.",
    "delivery_login": "Use the 6-digit verification code below to access your TipsyCart Delivery Partner portal.",
    "forgot_password": "Use the 6-digit verification code below to verify your identity and set a new account password.",
}


def build_otp_email_html(otp: str, purpose: str, expiry_minutes: int = 5) -> str:
    title = PURPOSE_TITLES.get(purpose, "Your TipsyCart Verification Code")
    desc = PURPOSE_DESCRIPTIONS.get(purpose, "Use the verification code below to complete your action.")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin: 0; padding: 30px 15px; background-color: #fff7fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #30242c;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" align="center">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 520px; background-color: #ffffff; border: 1px solid #f7e3ec; border-radius: 20px; box-shadow: 0 10px 35px rgba(165, 22, 85, 0.08); overflow: hidden; padding: 35px 30px;" cellspacing="0" cellpadding="0" border="0">
          <!-- Header -->
          <tr>
            <td align="center" style="padding-bottom: 25px;">
              <div style="width: 50px; height: 50px; line-height: 50px; border-radius: 14px; background: linear-gradient(135deg, #ec4899, #a51655); color: #ffffff; font-size: 26px; font-weight: 800; text-align: center; margin: 0 auto 10px;">T</div>
              <h1 style="margin: 0; color: #a51655; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">TipsyCart</h1>
              <p style="margin: 4px 0 0; color: #a16a82; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;">Care • Comfort • Confidence</p>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="border-top: 1px solid #fce7f3; padding-top: 25px;">
              <h2 style="margin: 0 0 10px; color: #30242c; font-size: 20px; font-weight: 700; text-align: center;">{title}</h2>
              <p style="margin: 0 0 20px; color: #66525e; font-size: 14px; line-height: 1.6; text-align: center;">{desc}</p>
            </td>
          </tr>

          <!-- OTP Box -->
          <tr>
            <td align="center" style="padding: 15px 0 25px;">
              <div style="background-color: #fff0f5; border: 2px dashed #ec4899; border-radius: 14px; padding: 18px 30px; display: inline-block;">
                <span style="font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #a51655; font-family: 'Courier New', Courier, monospace; margin-left: 10px;">{otp}</span>
              </div>
              <p style="margin: 12px 0 0; color: #be185d; font-size: 12px; font-weight: 700;">⏱️ Valid for {expiry_minutes} minutes only</p>
            </td>
          </tr>

          <!-- Security Notice -->
          <tr>
            <td style="background-color: #fdf2f8; border-radius: 12px; padding: 16px 20px; margin-top: 10px;">
              <p style="margin: 0 0 6px; color: #9d174d; font-size: 12px; font-weight: 700;">🔒 Security Notice</p>
              <p style="margin: 0; color: #786b73; font-size: 12px; line-height: 1.5;">TipsyCart employees will never call or ask for your verification code. Never share this code with anyone. If you did not request this, please ignore this email or change your account credentials.</p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td align="center" style="padding-top: 30px; border-top: 1px solid #fce7f3; margin-top: 25px;">
              <p style="margin: 0; color: #9b8791; font-size: 11px;">Your everyday essentials, delivered faster in Kanpur.</p>
              <p style="margin: 6px 0 0; color: #b3a1ab; font-size: 11px;">&copy; 2026 TipsyCart. All Rights Reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def build_otp_email_text(otp: str, purpose: str, expiry_minutes: int = 5) -> str:
    title = PURPOSE_TITLES.get(purpose, "Your TipsyCart Verification Code")
    desc = PURPOSE_DESCRIPTIONS.get(purpose, "Use the verification code below.")
    return f"""TipsyCart - {title}

{desc}

Your 6-Digit Code: {otp}

This verification code expires in {expiry_minutes} minutes.

Security Notice:
Never share this code with anyone. TipsyCart will never ask for your verification code.
If you did not request this code, you can safely ignore this email.

(c) 2026 TipsyCart. All Rights Reserved.
"""


def send_otp_email(to_email: str, otp: str, purpose: str) -> tuple[bool, str]:
    """
    Sends a branded 6-digit OTP email via official Resend API.
    Returns (True, message_id) on success, or (False, error_description) on failure.
    Never exposes API keys or sensitive secrets.
    """
    api_key = getattr(settings, "RESEND_API_KEY", "") or os.getenv("RESEND_API_KEY", "")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or os.getenv("DEFAULT_FROM_EMAIL", "onboarding@resend.dev")

    if not api_key:
        error_msg = "Resend API key is not configured in backend environment."
        logger.error(error_msg)
        return False, error_msg

    resend.api_key = api_key

    subject = PURPOSE_TITLES.get(purpose, "Your TipsyCart Verification Code")
    html_content = build_otp_email_html(otp, purpose, expiry_minutes=5)
    text_content = build_otp_email_text(otp, purpose, expiry_minutes=5)

    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email.strip().lower()],
        "subject": subject,
        "html": html_content,
        "text": text_content,
    }

    try:
        response = resend.Emails.send(params)
        message_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
        logger.info(f"Successfully sent OTP email via Resend to {to_email} (purpose: {purpose}, id: {message_id})")
        return True, str(message_id or "sent")
    except Exception as exc:
        err_str = str(exc)
        logger.error(f"Resend email dispatch error for {to_email}: {err_str}")
        # User-friendly explanation for Resend's free tier domain restriction
        if "testing emails" in err_str.lower() or "verify a domain" in err_str.lower():
            return False, (
                "Resend Test Mode: Emails can currently only be sent to your registered Resend account email (aadityak09771@gmail.com). "
                "To send OTPs to any customer or other email addresses, please verify your custom domain at resend.com/domains."
            )
        return False, f"Failed to deliver verification email: {err_str}"
