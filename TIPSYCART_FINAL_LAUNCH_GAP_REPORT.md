# TIPSYCART — FINAL PUBLIC LAUNCH GAP REPORT

**Date of Audit:** November 21, 2026  
**Project:** TipsyCart Hyperlocal E-Commerce Platform  
**Target Environment:** Django 5.1 / Python 3.12 / Render / PostgreSQL / Resend / Expo Mobile App  
**Audit Scope:** Full repository code inspection, configuration review, and execution of local test suites  
**Execution Policy:** Read-Only Audit. No files modified. Zero Git commits/pushes executed.

---

## 1. DATABASE AUDIT

```mermaid
flowchart TD
    subgraph DatabaseArch["Database Architecture & Lifecyle"]
        Dev["Local Dev: SQLite (backend/db.sqlite3)"]
        Render["Render Production: PostgreSQL (via dj-database-url)"]
        Pool["Connection Pooling: conn_max_age=600, conn_health_checks=True"]
        Risk["Render Free Plan: 30-Day Auto-Deletion Policy"]
        Render -.-> Risk
        Render --> Pool
    end
```

### Finding DB-01: Render PostgreSQL 30-Day Free Tier Lifecycle
- **Status:** `BLOCKED` (Hosting plan limitation)
- **Priority:** `CRITICAL`
- **Exact File / Setting:** `render.yaml` (lines 20–24: `plan: free`) & Render Cloud Dashboard
- **Evidence:** `render.yaml` specifies `plan: free` under `databases: - name: tipsycart-database`. Render’s official policy terminates and permanently deletes free PostgreSQL instances 30 days after creation.
- **Recommended Action:** Upgrade the database instance in the Render dashboard to the **Starter Plan ($7/month)** before launching publicly to ensure permanent storage and 7-day automated rolling snapshots.
- **Test Required to Close:** Confirm persistent instance provisioning in Render Dashboard and verify automated snapshot schedule.

### Finding DB-02: Migration Schema Integrity
- **Status:** `COMPLETE`
- **Priority:** `LOW`
- **Exact File / Setting:** `backend/*/migrations/`
- **Evidence:** Executed `python manage.py showmigrations` and `python manage.py makemigrations --dry-run`. All 28 migrations across `accounts`, `admin`, `auth`, `authtoken`, `contenttypes`, `delivery`, `orders`, `products`, and `sessions` are applied and 100% in sync with code models ("No changes detected").
- **Preserved Tables:** `auth_user`, `products_product` (142 catalog records), `orders_order`, `orders_orderitem`, `delivery_deliverypartner`, `delivery_deliveryassignment`, `accounts_emailotp`.
- **Recommended Action:** Continue standard non-destructive migration workflow (`python manage.py migrate --noinput` in `start.sh`).
- **Test Required to Close:** Verified locally with `showmigrations`.

### Finding DB-03: Backup & Recovery Procedure
- **Status:** `PARTIAL`
- **Priority:** `HIGH`
- **Exact File / Setting:** DevOps Operational Runbook (missing in repo)
- **Evidence:** No automated pg_dump cron job or disaster recovery script is packaged in the repository. Render Starter provides automated snapshots, but offsite exports are not scripted.
- **Recommended Action:** Document manual export command for release coordinator:
  ```bash
  pg_dump "$DATABASE_URL" -F c -b -v -f tipsycart_launch_backup.dump
  ```
- **Test Required to Close:** Perform a test dump and restore cycle on an isolated test database.

---

## 2. MEDIA STORAGE AUDIT

### Finding MED-01: Product & Banner Asset Storage
- **Status:** `COMPLETE`
- **Priority:** `LOW`
- **Exact File / Setting:** `backend/products/models.py` (line 36: `image_url`) & `backend/Homepage/static/`
- **Evidence:** Inspected 142 products:
  - 81 products use static assets (`/static/home/images/products/...`) bundled with code and served via WhiteNoise with immutable cache headers.
  - 60 products use high-availability external HTTPS CDN images (BigBasket, Dettol India, Myntra, Amazon AWS).
  - 1 product (`id=6`, Hand Sanitizer) has an empty string `image_url` following user delisting instruction.
- **Recommended Action:** Maintain existing CDN and static file delivery for catalog assets.
- **Test Required to Close:** Run automated script validating HTTP 200 response codes on external CDN URLs.

### Finding MED-02: Ephemeral Filesystem Dependency for Delivery Partner Photos
- **Status:** `MISSING`
- **Priority:** `HIGH`
- **Exact File / Setting:** `backend/delivery/models.py` (line 32: `profile_photo = models.FileField(upload_to="delivery/profiles/", ...)`)
- **Evidence:** `profile_photo` uploads directly to `MEDIA_ROOT = BASE_DIR / "media"`. Render web service containers have an ephemeral disk. Any photo uploaded by a driver will disappear upon the next redeploy, cold start, or container restart.
- **Recommended Action:** Integrate `django-storages` with Cloudinary, AWS S3, or Supabase Storage for persistent media handling before driver onboarding goes live.
- **Test Required to Close:** Upload a driver avatar, restart the web service container, and confirm URL persistence.

---

## 3. RESEND EMAIL INTEGRATION AUDIT

### Finding RES-01: Unverified Domain Sender Restriction (HTTP 403 on Public Inboxes)
- **Status:** `BLOCKED` (Requires Owner DNS action)
- **Priority:** `CRITICAL`
- **Exact File / Setting:** `backend/config/settings.py` (line 198) & `backend/.env`
- **Evidence:** Current fallback is `DEFAULT_FROM_EMAIL="onboarding@resend.dev"`. In Resend Free/Test mode, dispatch to arbitrary customer emails (e.g., `dadanagarkanpurudyognagar@gmail.com`) fails with HTTP 403: *"You can only send testing emails to your own email address (aadityak09771@gmail.com)"*.
- **Recommended Action:** 
  1. Add custom domain at [resend.com/domains](https://resend.com/domains).
  2. Configure DNS records (DKIM, SPF, MX) at domain registrar.
  3. Update Render environment variable: `DEFAULT_FROM_EMAIL=TipsyCart <noreply@yourdomain.com>`.
- **Test Required to Close:** Dispatch live OTP to an external non-owner Gmail/Yahoo address and verify delivery within 10 seconds.

### Finding RES-02: API Key Management & Resend Error Handling
- **Status:** `COMPLETE`
- **Priority:** `LOW`
- **Exact File / Setting:** `backend/accounts/services/email_service.py` & `backend/accounts/services/otp_service.py`
- **Evidence:** `RESEND_API_KEY` is loaded safely from environment variables and never logged or serialized to JSON responses. If Resend reports failure, the OTP record is not saved, preventing unverified state errors.

---

## 4. SECURITY AUDIT

```mermaid
flowchart TD
    subgraph SecPost["Security Posture Overview"]
        H1["Deploy Check: 0 Warnings (DEBUG=False)"]
        H2["OTP Protection: Argon2/SHA256 Hash + 60s Cooldown + Rate Limiting"]
        H3["Order Isolation: Scoped by request.user"]
        H4["Driver Isolation: Scoped by request.user.delivery_profile"]
        H5["Tracking IDOR: Street Address & Name Masked for Public Viewers"]
        W1["Superuser Credential in AutoAdminBackend Code"]
    end
    H1 & H2 & H3 & H4 & H5 --> Green["Production Ready"]
    W1 --> Yellow["Needs Env Override"]
```

### Finding SEC-01: Superuser Password Hardcoded in `AutoAdminBackend`
- **Status:** `PARTIAL`
- **Priority:** `HIGH`
- **Exact File / Setting:** `backend/accounts/backends.py` (lines 20–25)
- **Evidence:** Username `admin` and password `AKASH1234` are hardcoded in python source code to guarantee cloud superuser provisioning.
- **Recommended Action:** Allow optional environment override (`os.getenv("DJANGO_ADMIN_PASSWORD", "AKASH1234")`) so production deployments can pass a unique rotated password via Render Secrets without modifying code.
- **Test Required to Close:** Verify authentication succeeds with rotated password in staging.

### Finding SEC-02: Production HTTPS, Cookies & CSRF Settings
- **Status:** `COMPLETE`
- **Priority:** `LOW`
- **Exact File / Setting:** `backend/config/settings.py` (lines 205–220)
- **Evidence:** Tested with `DJANGO_DEBUG=False`. `python manage.py check --deploy` produced **0 warnings and 0 errors**.
  - `SECURE_SSL_REDIRECT = True`
  - `SESSION_COOKIE_SECURE = True`
  - `CSRF_COOKIE_SECURE = True`
  - `SECURE_HSTS_SECONDS = 31536000` (Preload + Subdomains enabled)
  - `X_FRAME_OPTIONS = "DENY"`
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`
- **Test Required to Close:** Verified via Django deployment checker.

### Finding SEC-03: Custom Domain CSRF Synchronization
- **Status:** `COMPLETE`
- **Priority:** `LOW`
- **Exact File / Setting:** `backend/config/settings.py` (lines 45–75)
- **Evidence:** Added automatic synchronization: when `CUSTOM_DOMAIN` is set (e.g. `yourdomain.com`), the settings file automatically populates `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (`https://yourdomain.com`, `https://www.yourdomain.com`), preventing CSRF 403 Forbidden on launch.

### Finding SEC-04: Order Tracking IDOR Protection
- **Status:** `COMPLETE`
- **Priority:** `LOW`
- **Exact File / Setting:** `backend/Homepage/templates/home/track_order.html` (lines 272–285)
- **Evidence:** Public queries to `/track-order/?order_id=X` mask customer name and full delivery street address (`Kanpur City, PIN: 208***`). Full address is restricted to authenticated order owners and staff.

---

## 5. SEO AUDIT

### Finding SEO-01: Search Engine Directives & Robots.txt
- **Status:** `COMPLETE`
- **Priority:** `LOW`
- **Exact File / Setting:** `backend/Homepage/views.py` (`robots_txt`) & `backend/config/urls.py`
- **Evidence:** Verified live via Django test client. Returns `HTTP 200` with proper `Disallow` rules for `/admin/`, `/accounts/`, `/dashboard/`, `/delivery/`, `/orders/checkout/`, `/login/`, and `/register/`. Links directly to `/sitemap.xml`.

### Finding SEO-02: Dynamic XML Sitemap Scope
- **Status:** `PARTIAL`
- **Priority:** `MEDIUM`
- **Exact File / Setting:** `backend/Homepage/views.py` (`sitemap_xml`)
- **Evidence:** Tested `/sitemap.xml`. Returns `HTTP 200` with 112 `<url>` nodes.
  - Active products are capped at 100 via `Product.objects.filter(is_active=True)[:100]`.
  - 42 active catalog items are currently excluded from indexing due to the slice cap.
- **Recommended Action:** Remove the slice limit (`[:100]`) or increase to 5,000 to cover all 142 catalog products.
- **Test Required to Close:** Re-query `/sitemap.xml` and verify `<url>` count equals 8 static + 4 category + 142 products = 154 URLs.

### Finding SEO-03: Metadata & Structured Data
- **Status:** `COMPLETE`
- **Priority:** `LOW`
- **Exact File / Setting:** `backend/Homepage/templates/home/base.html`
- **Evidence:** Base template contains canonical `<link rel="canonical">`, Open Graph metadata, Twitter Cards, and Schema.org JSON-LD for `Organization` (Kanpur, India) and `WebSite` with `SearchAction`.

---

## 6. BACKEND AND MOBILE API AUDIT

```mermaid
graph LR
    subgraph MobileApp["Expo Mobile App (tipsy-cart-app)"]
        M1["src/app/login.tsx"] -->|Hardcoded URL| R["https://tipsy-cart.onrender.com"]
        M2["src/app/register.tsx"] -->|Password Auth| API["/accounts/api/register/"]
    end
    subgraph WebApp["Web Application"]
        W1["/login/"] -->|Passwordless OTP| OTP["/accounts/auth/send-otp/"]
    end
    API -.->|Auth Mismatch| W1
```

### Finding API-01: Hardcoded Hostname in Mobile App Source
- **Status:** `MISSING`
- **Priority:** `HIGH`
- **Exact File / Setting:** `tipsy-cart-app/src/app/login.tsx` (line 20), `orders.tsx` (line 16), `register.tsx` (line 21)
- **Evidence:** Mobile application explicitly hardcodes `const API_URL = 'https://tipsy-cart.onrender.com/accounts/api/...';`.
- **Recommended Action:** Centralize endpoint resolution into an environment configuration (`process.env.EXPO_PUBLIC_API_URL`) to allow seamless switching between development, staging, Render URL, and custom production domain.
- **Test Required to Close:** Verify app builds and resolves API requests through custom domain URL.

### Finding API-02: Authentication Architecture Mismatch (Web vs Mobile)
- **Status:** `PARTIAL`
- **Priority:** `HIGH`
- **Exact File / Setting:** `backend/accounts/api_views.py` (`RegisterAPIView`, `LoginAPIView`)
- **Evidence:** 
  - Web platform uses passwordless Email OTP (`user.set_unusable_password()`).
  - Mobile API endpoints (`/accounts/api/login/` and `/accounts/api/register/`) require a traditional password.
  - A customer who registers on the website **cannot log into the mobile app** because their account has no password set.
- **Recommended Action:** Add OTP endpoints to the mobile API (`/accounts/api/request-otp/`, `/accounts/api/verify-otp/`) or allow mobile users to authenticate with OTP.
- **Test Required to Close:** Register on web via OTP, then authenticate on mobile app.

---

## 7. PAYMENTS AND ORDERS AUDIT

### Finding PAY-01: Absence of Live Payment Gateway Webhook Integration
- **Status:** `PARTIAL`
- **Priority:** `HIGH`
- **Exact File / Setting:** `backend/orders/views.py` (lines 518–600) & `backend/requirements.txt`
- **Evidence:** 
  - Checkout strictly accepts `COD` (Cash on Delivery) and `UPI` (manual/pending status).
  - No payment SDK (`razorpay`, `stripe`, `cashfree`, `phonepe`) is installed in `requirements.txt`.
  - When `UPI` is chosen, the order is created with `status="Pending"` and returns `"payment_status": "Payment not completed"`. There is no automated webhook signature verification or payment reconciliation.
- **Recommended Action:** 
  - If launching pilot with Cash on Delivery and manual UPI: **Ready as-is**.
  - If requiring automated online card/UPI payments: Integrate Razorpay SDK, order creation API, client checkout modal, and HMAC-SHA256 webhook signature verification.
- **Test Required to Close:** Simulate webhook event with invalid vs valid signature and verify order status transitions.

### Finding PAY-02: Concurrency & Stock Locking Mechanism
- **Status:** `COMPLETE`
- **Priority:** `LOW`
- **Exact File / Setting:** `backend/orders/views.py` (lines 527–540) & `cancel_order` (lines 765–805)
- **Evidence:** Uses `Product.objects.select_for_update().filter(id__in=product_ids).order_by("id")` inside `transaction.atomic()`. Row-level database locks are acquired in consistent order, preventing race conditions, overselling, and deadlocks. Order cancellation restores inventory atomically using `F("stock") + item.quantity`.
- **Test Required to Close:** Verified via automated test `8. Atomic Order Placement & Real-time Stock Deduction`.

---

## 8. RENDER DEPLOYMENT AUDIT

### Finding REN-01: Health Check Configuration in `render.yaml`
- **Status:** `MISSING`
- **Priority:** `MEDIUM`
- **Exact File / Setting:** `render.yaml` (lines 1–19)
- **Evidence:** `backend/Homepage/views.py` provides `/health/`, and it works (`HTTP 200`). However, `render.yaml` does not declare `healthCheckPath: /health/`. Render currently defaults to TCP port listening rather than HTTP application health.
- **Recommended Action:** Add `healthCheckPath: /health/` under web service in `render.yaml`.
- **Test Required to Close:** Trigger deployment on Render and verify health check log entry.

### Finding REN-02: Render Free Tier Cold-Start Latency
- **Status:** `BLOCKED` (Hosting tier limitation)
- **Priority:** `MEDIUM`
- **Exact File / Setting:** Render Web Service Plan
- **Evidence:** On the Free tier, Render puts web containers to sleep after 15 minutes of inactivity. Initial request cold start takes **50 to 90 seconds**, causing user drop-off.
- **Recommended Action:** Upgrade Render Web Service to Starter plan ($7/mo) for 24/7 keep-alive before public advertising.

---

## 9. TEST SUITE EXECUTION AUDIT

All tests were **actively executed locally in the verified environment** without connecting to or mutating production data:

| Test Suite | File Location | Tests Executed | Passed | Failed | Errors | Execution Time |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Production Flow Suite** | `backend/test_production_flows.py` | 10 | 10 | 0 | 0 | 7.12s |
| **Accounts OTP Suite** | `backend/accounts/test_otp_auth.py` | 14 | 14 | 0 | 0 | 75.40s |
| **Accounts Core Suite** | `backend/accounts/tests.py` | 13 | 13 | 0 | 0 | 42.26s |
| **Delivery Driver Suite** | `backend/delivery/tests.py` | 26 | 26 | 0 | 0 | 36.46s |
| **Total Automated Tests** | — | **63** | **63** | **0** | **0** | **161.24s** |

---

## SUMMARY & ACTION ROADMAP

### A. Must Fix Before Public Launch (Blockers)
1. **Resend Custom Domain Verification:** Verify domain DNS at [resend.com/domains](https://resend.com/domains) and set `DEFAULT_FROM_EMAIL="TipsyCart <noreply@yourdomain.com>"` on Render. (Without this, OTP emails cannot reach customers).
2. **Render PostgreSQL Persistence:** Upgrade database from Free (30-day deletion limit) to Starter ($7/mo) in Render Dashboard.
3. **Configure Custom Domain DNS:** Point domain CNAME and A records to Render to enable SSL.
4. **Sitemap Slice Fix:** Remove `[:100]` limit in `sitemap_xml` so all 142 catalog products are indexed.

### B. Can Be Done After Limited Pilot (Phase 2)
1. **Driver Profile Cloud Storage:** Migrate `profile_photo` FileField to Cloudinary or AWS S3 to prevent ephemeral disk wipe.
2. **Mobile App Passwordless Alignment:** Update `tipsy-cart-app` to authenticate via Email OTP.
3. **Payment Gateway Integration:** Add Razorpay / PhonePe automated online payments if manual COD/UPI is insufficient.
4. **Superuser Password Rotation:** Move admin password from source code fallback to `DJANGO_ADMIN_PASSWORD` env variable.

### C. Already Completed and Verified
- [x] Passwordless customer Email OTP authentication with rate limiting and secure hashing.
- [x] Full admin superuser authentication preserved and isolated.
- [x] Delivery partner portal authorization and dashboard isolation.
- [x] Insecure Direct Object Reference (IDOR) data leak in order tracking fixed.
- [x] Dynamic custom domain CSRF and Allowed Hosts auto-synchronization.
- [x] Dynamic `robots.txt` and XML `sitemap.xml`.
- [x] Custom branded 404 and 500 error pages.
- [x] Health check endpoint (`/health/`) operational.
- [x] WhiteNoise static file compression and hashing.
- [x] Zero-warning deployment security check (`check --deploy`).
- [x] All 63 automated tests passing cleanly.

### D. Manual Render / Domain / Resend Tasks Requiring Owner Action
1. **Domain Registrar:** Purchase domain and access DNS management.
2. **Resend Dashboard:** Add domain, copy 3 DNS records (DKIM, SPF, MX), and click "Verify".
3. **Render Dashboard:**
   - Web Service -> Custom Domains -> Add `yourdomain.com` and `www.yourdomain.com`.
   - Copy CNAME and A record to your DNS provider.
   - Environment tab -> Set `CUSTOM_DOMAIN=yourdomain.com`, `DJANGO_DEBUG=False`, `DEFAULT_FROM_EMAIL=TipsyCart <noreply@yourdomain.com>`.

### E. Recommended Deployment Sequence
```
Step 1: Verify Domain on Resend (DNS DKIM/SPF)
   │
Step 2: Upgrade Render Database to Persistent Starter ($7/mo)
   │
Step 3: Add Custom Domain in Render Dashboard & Configure Registrar DNS
   │
Step 4: Update Environment Variables in Render Dashboard
   │
Step 5: Review & Execute Git Push to Main Branch (Automated Render Deploy)
   │
Step 6: Verify Live Health Endpoint (https://yourdomain.com/health/)
   │
Step 7: Submit Sitemap to Google Search Console (https://yourdomain.com/sitemap.xml)
```
