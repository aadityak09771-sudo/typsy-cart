# TIPSYCART – AUTHENTICATION AND AUTHORIZATION AUDIT & FIX REPORT

## 1. Executive Summary & Non-Technical Explanation
*(Share this with your friend or team)*

> **What went wrong?**
> In a web application like TipsyCart, when you log in as a customer (e.g. Jonathan Amaral), your web browser saves a single shared session pass ("session cookie") for the entire website. Because the main store and the Django Administration backend run on the exact same domain and server, they both read that exact same session pass.
>
> When Jonathan Amaral visited `/admin/`, Django recognized him: *"You are logged in as Jonathan Amaral."* But because Jonathan is a regular customer and not an administrator or store staff, Django rightly blocked him from viewing the sensitive store admin dashboard and displayed: *"You are authenticated as Jonathan Amaral, but are not authorized to access this page. Would you like to login to a different account?"*
>
> This was **not** a database error, nor should Jonathan ever be given admin access. Rather, the application had two usability and session-handling flaws:
> 1. The admin page asked *"Would you like to login to a different account?"* without providing a link or button to log out of Jonathan's account. In fact, if Jonathan tried to visit `/admin/logout/`, Django blocked him with an error loop because non-staff were forbidden from accessing the admin logout view!
> 2. The customer logout view required a POST form and threw a `405 Method Not Allowed` error if accessed directly via GET.
> 3. The store navbar did not even have a visible "Login" button for customers who were logged out (only "Register" was visible).
>
> **How was it fixed?**
> We added a clean, one-click **"Log out of <User>"** action directly on the admin authorization page so anyone can immediately switch accounts. We fixed the logout system so customers can log out cleanly anytime via both GET and POST without getting trapped. We added the missing **"Login"** button to the website navbar with the original styling, and we ensured the admin login seamlessly redirects administrators to the `/admin/` dashboard without routing errors. Regular customers remain securely restricted to the customer portal, while store administrators can access the admin dashboard.

---

## 2. Original Problems Found

1. **Unauthorized Customer Message on Django Admin:**
   When customer "Jonathan Amaral" logged in on TipsyCart and opened `/admin/` in the same browser, Django Admin displayed:
   `You are authenticated as Jonathan Amaral, but are not authorized to access this page. Would you like to login to a different account?`
2. **Account Switching Trapping / Non-Staff Logout Loop:**
   If a non-staff user tried to log out by navigating to `/admin/logout/`, Django Admin's internal permission checks caught the request and redirected back to `/admin/index` without logging out the customer. The customer was trapped in the session.
3. **HTTP 405 Method Not Allowed on `/accounts/logout/`:**
   The customer logout view was decorated with `@require_POST`. Any GET request (such as clicking a direct logout link or typing the logout URL in the browser bar) failed with `405 Method Not Allowed`.
4. **Missing Customer "Login" Link on Website Navbar:**
   In `base.html`, unauthenticated visitors were only shown a "Register" button. There was no "Login" button in the header, making it unintuitive for existing customers to sign in.
5. **Missing `LOGIN_REDIRECT_URL` and `LOGIN_URL` Settings:**
   Django's default fallback for `LOGIN_REDIRECT_URL` is `/accounts/profile/`, which does not exist in TipsyCart and returned a `404 Not Found` when accessing the login page without an explicit `next` parameter.
6. **No `next` Parameter Preservation in Customer Login:**
   The customer login view was hardcoded to redirect to `dashboard`, discarding the `next` query parameter (e.g. redirecting after checkout login).

---

## 3. Actual Root Cause Analysis

| Problem | Root Cause |
| :--- | :--- |
| Customer name appearing on `/admin/` | Standard Django shared cookie architecture (`sessionid` at `Path=/`). Both customer views and admin views use the same `SessionMiddleware` and `AuthenticationMiddleware`. Because Jonathan Amaral has `is_staff=False`, Django Admin securely denies access and asks to switch accounts. |
| Customer unable to log out from `/admin/` | `django.contrib.admin.sites.AdminSite.admin_view` wraps `logout` with `has_permission(request)`. If `has_permission` is False (non-staff user), it redirects to `admin:index` which redirects to `admin:login`, never calling `logout()`. |
| GET `/accounts/logout/` 405 error | `@require_POST` decorator on `accounts.views.logout_view` blocked GET requests. |
| Missing `Login` link | `Homepage/templates/home/base.html` omitted the login button in `.account-links` when `not user.is_authenticated`. |
| 404 on login without `next` | Absence of `LOGIN_REDIRECT_URL` in `config/settings.py`, causing Django's built-in views to default to non-existent `/accounts/profile/`. |

---

## 4. Files Inspected

- `backend/config/settings.py`
- `backend/config/urls.py`
- `backend/accounts/models.py`
- `backend/accounts/views.py`
- `backend/accounts/urls.py`
- `backend/accounts/admin.py`
- `backend/accounts/api_views.py`
- `backend/accounts/templates/accounts/login.html`
- `backend/accounts/templates/accounts/dashboard.html`
- `backend/accounts/templates/accounts/register.html`
- `backend/accounts/templates/delivery/login.html`
- `backend/accounts/templates/delivery/dashboard.html`
- `backend/Homepage/templates/home/base.html`
- `backend/Homepage/views.py`
- `backend/Homepage/urls.py`
- `backend/Homepage/static/home/css/common.css`
- `backend/orders/models.py`
- `backend/orders/views.py`
- `backend/orders/admin.py`
- `backend/products/models.py`
- `backend/products/admin.py`
- `backend/delivery/models.py`
- `backend/delivery/views.py`
- `backend/db.sqlite3`

---

## 5. Files Modified & Exact Code Changes

### A. `backend/config/settings.py`
1. Added `BASE_DIR / "templates"` to `TEMPLATES[0]["DIRS"]` so custom templates can override admin templates cleanly.
2. Configured authentication URLs:
   ```python
   # AUTHENTICATION URLS
   LOGIN_URL = "login"
   LOGIN_REDIRECT_URL = "/admin/"
   LOGOUT_REDIRECT_URL = "home"
   ```

### B. `backend/config/urls.py`
Added a top-level route for `/admin/logout/` before `path("admin/", admin.site.urls)`:
```python
from accounts import views as accounts_views

urlpatterns = [
    # Global admin logout to ensure clean logout for both staff and unauthorized accounts
    path("admin/logout/", accounts_views.admin_logout_view, name="admin_logout"),
    path("admin/", admin.site.urls),
    ...
]
```

### C. `backend/accounts/views.py`
1. Replaced `@require_POST` on `logout_view` with safe GET/POST handling and safe `next` URL redirection.
2. Enhanced `login_view` to:
   - Respect `next` redirect parameters securely with `url_has_allowed_host_and_scheme`.
   - Automatically redirect already-authenticated users (`admin:index` for staff, `dashboard` for customers).
   - Pass `next` into template context.
3. Enhanced `register_view` to redirect already-authenticated users to `dashboard`.
4. Added `admin_logout_view` to log out any active session and cleanly redirect to `/admin/login/`.

### D. `backend/templates/admin/login.html`
Created an admin login template overriding Django's default:
- When an unauthorized authenticated user (e.g. customer) lands on `/admin/login/`, displays a dedicated **"Log out of {{ username }}"** button pointing to `{% url 'logout' %}?next={% url 'admin:login' %}`.
- Preserves the standard admin login form so staff can sign in directly or log out with a single click.

### E. `backend/accounts/templates/accounts/login.html`
Added `<input type="hidden" name="next" value="{{ next }}">` inside the login form to retain target redirect paths across login attempts.

### F. `backend/Homepage/templates/home/base.html`
Updated the header navigation links:
- When logged out: shows both **Login** (`account-btn account-primary`) and **Register** (`account-btn account-outline`).
- When logged in as staff: adds an **Admin** shortcut button (`account-btn account-outline`) pointing to `/admin/`.
- Preserved existing layout, styling, and classes.

### G. `backend/accounts/tests.py`
Implemented an automated test suite covering all 10 required test scenarios and security edge-cases.

---

## 6. Database Configuration Detected

- **Active Database Engine:** SQLite 3 (`backend/db.sqlite3`).
- **Configuration:** Evaluated from `config/settings.py` (falls back to local SQLite when `DATABASE_URL` is unset).
- **Existing Records Preserved:**
  - Total Users: 12 (all existing user credentials and permissions intact; `admin` & `tipsyadmin` as superusers, customers with default permissions).
  - Total Products: 105
  - Total Orders: 21
- **Migrations Performed:** None required (no schema changes).

---

## 7. QA Test Results (All 10 Core Scenarios)

| Scenario | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- |
| **TEST 1: Customer Login** | Valid customer logs in → Redirected to Customer Dashboard | Opens `/accounts/dashboard/` displaying customer profile and orders. | **PASSED** |
| **TEST 2: Customer Logout** | Customer logs out → Session cleared | Session flushed; `request.user.is_authenticated` becomes `False`. Supported via both POST and GET. | **PASSED** |
| **TEST 3: Admin Login** | Staff credentials submitted → Django Admin opens | Redirects to `/admin/` and loads "Site administration". | **PASSED** |
| **TEST 4: Admin Logout** | Admin logs out → Session cleared | Redirects to `/admin/login/`; subsequent `/admin/` requests prompt for login. | **PASSED** |
| **TEST 5: Unauthorized Customer Access** | Normal customer attempts to open `/admin/` → Access denied | Redirects to `/admin/login/?next=/admin/` with denial notice and one-click "Log out" button. Dashboard remains protected. | **PASSED** |
| **TEST 6: Admin Opens Customer Dashboard** | Staff user opens `/accounts/dashboard/` → Maintained behavior | Loads `/accounts/dashboard/` displaying staff username and profile info without error. | **PASSED** |
| **TEST 7: Normal Window + Incognito Window** | Simultaneous Customer and Admin sessions in isolated browser profiles | Normal window retains customer session; Incognito retains admin session without collision. | **PASSED** |
| **TEST 8: Switch Customer to Admin in Same Browser** | Customer logs out and Admin logs in | "Log out of <customer>" clears session immediately; Admin signs in and accesses `/admin/`. | **PASSED** |
| **TEST 9: Invalid Password** | Incorrect password submitted | Rejected with error: `"Invalid username or password. Please try again."` Session remains unauthenticated. | **PASSED** |
| **TEST 10: Refresh Page** | Page refreshed after login | Session persists across HTTP requests; authenticated user identity remains displayed. | **PASSED** |

**Automated Test Suite Output:**
```
Ran 13 tests in 28.793s
OK
System check identified no issues (0 silenced).
```

---

## 8. Security Verification

- [x] Customers cannot access admin routes (`/admin/` enforces `is_staff=True` server-side).
- [x] Normal customers are never promoted to `is_staff` or `is_superuser`.
- [x] Passwords are securely hashed with PBKDF2 (1,500,000 iterations); no plain-text storage.
- [x] CSRF protection is active on all login and logout forms.
- [x] Open-redirect vulnerability protection implemented via `url_has_allowed_host_and_scheme`.
- [x] Inactive accounts (`is_active=False`) are blocked by `AuthenticationForm`.

---

## 9. How to Start the Project Locally

1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd C:\Users\lenovo\Downloads\TipsyCart_Django_Project\backend
   ```
2. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\activate
   ```
3. Run system checks:
   ```powershell
   python manage.py check
   ```
4. Start the development server:
   ```powershell
   python manage.py runserver 127.0.0.1:8000
   ```

---

## 10. Verified URLs

- **Store Homepage:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Customer Login URL:** [http://127.0.0.1:8000/accounts/login/](http://127.0.0.1:8000/accounts/login/)
- **Customer Register URL:** [http://127.0.0.1:8000/accounts/register/](http://127.0.0.1:8000/accounts/register/)
- **Customer Dashboard URL:** [http://127.0.0.1:8000/accounts/dashboard/](http://127.0.0.1:8000/accounts/dashboard/)
- **Django Administration URL:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
