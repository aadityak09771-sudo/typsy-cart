# TIPSYCART — Production-Ready Email OTP Authentication Implementation Report

**Document Date:** November 20, 2026  
**Status:** Implemented, Fully Tested, and Ready for Deployment  
**Repository State:** Local changes preserved; Git push held pending explicit user instruction  

---

## 1. Executive Summary & Root Cause Analysis

### 1.1 Background & Prior Architecture
Prior to this implementation, TipsyCart used standard Django username/password credential authentication for customers and delivery partners:
- Customers were required to remember their username and password. User registration had no enforced email field, meaning several legacy customer records lacked associated emails.
- Delivery Partners logged in via mobile number or username and password, but lacked a modern passwordless OTP mechanism.
- The Admin Portal (`/admin/`) relied on Django's built-in session authentication powered by `AutoAdminBackend`, which guaranteed the superuser (`admin` / `AKASH1234`) could always access administration even after fresh database provisioning.

### 1.2 Target Objectives
1. **Passwordless Customer Login & Registration:** Allow customers to log in or register instantly by simply entering their email and a 6-digit OTP sent via Resend. No name or password is ever required at registration—brand new users are auto-provisioned securely upon OTP verification.
2. **Authorized Delivery Partner Login:** Enable 6-digit OTP login for delivery drivers while strictly guaranteeing that only active, verified delivery partners can authenticate into the driver dashboard (`/delivery/dashboard/`).
3. **Forgot Password Flow:** Allow customers and delivery partners to reset their passwords securely via a 6-digit OTP, generating a cryptographically signed one-time reset token without leaking email existence.
4. **Admin Security Guarantee:** Leave Django admin (`/admin/`) untouched and guarantee that customers and delivery partners can never access administrative pages.
5. **OTP Security Hardening:** Implement 5-minute expiry, PBKDF2 cryptographic OTP hashing (raw OTP is never stored plain text in the database), 60-second resend cooldown, 5-attempt brute-force protection, and IP/email rate limiting.

---

## 2. Files Created & Modified

| File Path | Status | Purpose & Description |
|---|---|---|
| `backend/accounts/models.py` | Modified | Added `EmailOTP` model with PBKDF2 hashing, 5-min expiry, attempt tracking, and one-time verification. |
| `backend/accounts/migrations/0002_emailotp.py` | Created | Safe Django migration creating the `accounts_emailotp` database table. |
| `backend/accounts/services/__init__.py` | Created | Package marker for accounts domain services. |
| `backend/accounts/services/email_service.py` | Created | Resend API integration helper. Generates branded TipsyCart responsive HTML & plaintext emails with OTP, expiry, and security warnings. |
| `backend/accounts/services/otp_service.py` | Created | Core OTP lifecycle engine: rate limiting, cooldown, 6-digit cryptographic generation, email normalization, verification, and tamper-proof reset token signing. |
| `backend/accounts/views.py` | Modified | Added `send_otp_view`, `verify_otp_view`, `reset_password_view`. Updated `CustomerRegistrationForm` with unique email handling and preserved legacy password login fallback. |
| `backend/accounts/urls.py` | Modified | Registered routes `/accounts/auth/send-otp/`, `/accounts/auth/verify-otp/`, `/accounts/auth/reset-password/`. |
| `backend/accounts/admin.py` | Modified | Registered `EmailOTP` in Django admin with read-only fields (`otp_hash`, `created_at`) for security auditing. |
| `backend/accounts/templates/accounts/login.html` | Modified | Upgraded customer login page with email OTP input, 60s countdown, interactive Forgot Password flow, loading indicators, and TipsyCart brand styling. |
| `backend/templates/delivery/login.html` | Modified | Upgraded delivery partner login page with partner email OTP input, 60s countdown timer, Forgot Password modal, and driver badge styling. |
| `backend/accounts/templates/delivery/login.html` | Modified | Template proxy inclusion ensuring consistent rendering across template loaders. |
| `backend/config/settings.py` | Modified | Added configuration for `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL`, `OTP_EXPIRY_SECONDS`, `OTP_RESEND_COOLDOWN_SECONDS`, and `OTP_MAX_ATTEMPTS`. |
| `backend/requirements.txt` | Modified | Added `resend>=2.0.0` for cloud deployment dependencies. |
| `backend/accounts/test_otp_auth.py` | Created | Automated test suite validating all 15 requirements from Section F. |
| `TIPSYCART_AUTH_IMPLEMENTATION_REPORT.md` | Created | This comprehensive implementation and verification report. |

---

## 3. Database Migrations

### 3.1 Migration `accounts.0002_emailotp`
- **File:** `backend/accounts/migrations/0002_emailotp.py`
- **Operation:** `CreateModel(name='EmailOTP')`
- **Fields:**
  - `id`: Auto-incrementing primary key
  - `email`: `models.EmailField(db_index=True)`
  - `otp_hash`: `models.CharField(max_length=128)` (PBKDF2 SHA-256 hash)
  - `purpose`: `models.CharField(max_length=32, choices=PURPOSE_CHOICES, db_index=True)`
  - `attempts`: `models.PositiveSmallIntegerField(default=0)`
  - `max_attempts`: `models.PositiveSmallIntegerField(default=5)`
  - `is_used`: `models.BooleanField(default=False, db_index=True)`
  - `created_at`: `models.DateTimeField(auto_now_add=True, db_index=True)`
  - `expires_at`: `models.DateTimeField(db_index=True)`
  - `ip_address`: `models.GenericIPAddressField(null=True, blank=True)`
- **Composite Index:** `["email", "purpose", "is_used"]` for fast lookup during high-concurrency verification.
- **Safety Guarantee:** Purely additive table creation; zero modification to existing `auth_user`, `PushDevice`, `Order`, or `DeliveryPartner` tables.

---

## 4. Resend Email Integration Details

- **Backend-Only Execution:** All Resend API communications occur strictly within `backend/accounts/services/email_service.py`. The API key is never rendered into templates, JSON responses, or browser JavaScript.
- **Official Resend SDK:** Utilizes `resend.Emails.send(...)`.
- **Branded TipsyCart Email Template:**
  - Header: TipsyCart signature plum (`#a51655`) and pink (`#ec4899`) icon with tagline *"Care • Comfort • Confidence"*.
  - Purpose-Specific Subject & Headline:
    - Customer: *"Your TipsyCart Login Code"*
    - Delivery Partner: *"Your TipsyCart Delivery Partner Login Code"*
    - Forgot Password: *"Your TipsyCart Password Reset Code"*
  - High-visibility 6-digit code box (`font-size: 36px`, letter-spaced, monospaced font).
  - Explicit 5-minute validity badge and fraud warning (*"Never share this code with anyone. TipsyCart employees will never ask for your code."*).
- **Graceful Error Handling:**
  - Returns structured `(False, error_description)` tuples without exposing raw exceptions or secrets.
  - Automatically translates Resend sandbox domain restrictions (`403 testing emails`) into actionable user guidance.
  - The OTP record is committed to the database **only after** Resend confirms successful message dispatch (HTTP 200/201 with valid `id`).

---

## 5. Security Architecture

1. **Cryptographic Randomness:** OTPs are generated using Python's `secrets.randbelow(1_000_000)` formatted to 6 digits (`000000`–`999999`).
2. **One-Way Password Hashing:** OTPs are stored using Django's PBKDF2 SHA-256 password hasher (`make_password(otp)`). A database compromise reveals only salt and hash, never the raw OTP.
3. **One-Time Use Enforcement:** Upon successful verification, `is_used = True` is immediately saved. Any subsequent submission of the same code is rejected.
4. **Resend Cooldown:** Any request within 60 seconds of a previous request for the same email and purpose is rejected with the exact seconds remaining.
5. **Rate Limiting:**
   - Maximum 5 OTP requests per email per hour.
   - Maximum 15 OTP requests per client IP per hour.
6. **Brute-Force Lockout:** After 5 unsuccessful verification attempts, the OTP record is permanently marked `is_used = True` and invalidated.
7. **Previous OTP Invalidation:** When a new OTP is requested, all prior unverified OTPs for that `(email, purpose)` are marked `is_used = True`.
8. **Email Normalization:** All inputs are stripped of whitespace and converted to lowercase (`email.strip().lower()`).
9. **Tamper-Proof Password Reset:** After OTP verification for `forgot_password`, a signed token is generated with `django.core.signing` (10-minute validity). The user can only reset their password by presenting this valid cryptographic token.
10. **Role Protection:** Customers cannot log in as delivery partners, delivery partners cannot log in as admins, and admin superusers must use `/admin/`.

---

## 6. Required Environment Variables

### Local Development (`backend/.env`)
```env
DJANGO_SECRET_KEY=your-django-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
RESEND_API_KEY=<YOUR_RESEND_API_KEY>
DEFAULT_FROM_EMAIL=onboarding@resend.dev
OTP_EXPIRY_SECONDS=300
OTP_RESEND_COOLDOWN_SECONDS=60
OTP_MAX_ATTEMPTS=5
```

### Render Production Environment (`render.yaml` or Render Dashboard)
| Variable Name | Required Value / Description |
|---|---|
| `RESEND_API_KEY` | Set in Render Dashboard secrets (`<YOUR_RESEND_API_KEY>`) |
| `DEFAULT_FROM_EMAIL` | `onboarding@resend.dev` (or verified domain address e.g. `auth@tipsycart.in`) |
| `OTP_EXPIRY_SECONDS` | `300` |
| `OTP_RESEND_COOLDOWN_SECONDS` | `60` |
| `OTP_MAX_ATTEMPTS` | `5` |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECRET_KEY` | Managed securely by Render environment |
| `DATABASE_URL` | Connected to PostgreSQL instance |

> **Note on Resend Free Tier:** When sending from `onboarding@resend.dev`, Resend's free tier restricts outgoing emails to the account owner's email address or `delivered@resend.dev`. For production public delivery to any customer, verify a custom domain (e.g. `tipsycart.in`) in the Resend dashboard and update `DEFAULT_FROM_EMAIL`.

---

## 7. Verification & Test Results

### 7.1 Automated Test Suite (`accounts.test_otp_auth`)
A dedicated automated test suite (`backend/accounts/test_otp_auth.py`) was executed:

```
Ran 12 tests in 63.449s
OK
System check identified no issues (0 silenced).
```

| Test Name | Purpose Tested | Result |
|---|---|---|
| `test_01_customer_requests_otp_and_resend_sends_email` | 1. Customer requests OTP & 2. Resend dispatches email | **PASSED** (HTTP 200, PBKDF2 hash stored) |
| `test_03_04_customer_enters_correct_otp_and_redirects` | 3. Customer enters correct OTP & 4. Redirects to `/dashboard/` | **PASSED** (Session created, customer authenticated) |
| `test_05_incorrect_otp_rejected` | 5. Incorrect OTP is rejected with remaining attempts counter | **PASSED** (HTTP 400, attempts incremented to 1) |
| `test_06_expired_otp_rejected` | 6. Expired OTP (>5 min) is rejected | **PASSED** (HTTP 400, "expired" error) |
| `test_07_reused_otp_rejected` | 7. Reused OTP (`is_used=True`) is rejected | **PASSED** (HTTP 400, "no active code" error) |
| `test_08_resend_cooldown_and_max_attempts` | 8. 60s cooldown enforced & 5 incorrect attempts locks OTP | **PASSED** (Cooldown rejected, 5th attempt marked `is_used=True`) |
| `test_09_customer_cannot_access_delivery_or_admin_pages` | 9. Customer denied access to driver portal and Django admin | **PASSED** (Driver redirect 302, Admin denies access) |
| `test_10_delivery_partner_login_and_dashboard` | 10. Delivery Partner logs in via OTP & accesses driver dashboard | **PASSED** (Driver authenticated, dashboard rendered) |
| `test_11_inactive_or_unauthorized_driver_rejected` | 11. Deactivated or non-driver email rejected for driver login | **PASSED** (Deactivated driver 400, customer rejected) |
| `test_12_13_forgot_password_flow_and_old_password_invalidation` | 12. Forgot Password OTP works & 13. Old password invalidated | **PASSED** (Token verified, new password works, old password fails) |
| `test_14_admin_login_unchanged_and_functional` | 14. Admin logs into `/admin/` with username/password | **PASSED** (Superuser authenticated, Site administration opens) |
| `test_15_logout_and_session_cleared` | 15. Customer logs out and session destroyed | **PASSED** (Session destroyed, unauthenticated redirect) |

### 7.2 Existing Regression Test Suites
- **Accounts Tests (`accounts.tests`):** 13 tests executed, **13 PASSED** (0 failures).
- **Delivery Tests (`delivery.tests`):** 26 tests executed, **26 PASSED** (0 failures).

### 7.3 Live Resend Email Dispatch Test
A live API call was performed against the official Resend API using the credentials from `backend/.env`:
- **Recipient:** `delivered@resend.dev`
- **Result:** **Success**
- **Resend Message ID:** `01a1f9d8-424c-727b-bf98-6e427d77fa07`
- **HTTP Status:** 200 OK

---

## 8. Deployment Steps for Production (Render)

When ready to deploy:
1. Ensure the environment variables listed in Section 6 are configured in the Render Dashboard under **Environment**.
2. Run database migration in the Render deploy hook (already configured in `start.sh` via `python manage.py migrate --noinput`).
3. (Optional) In the Resend Console, verify the custom sending domain (e.g. `tipsycart.in`) and configure DNS records (DKIM, SPF, DMARC) to send to any public customer inbox.

---

## 9. Conclusion
The production-ready Email OTP Authentication system for TipsyCart is completely implemented, verified with 51 passing automated tests and a live Resend dispatch, and meets all functional, UI, and security criteria. All code modifications are maintained locally as requested and ready for deployment upon user approval.
