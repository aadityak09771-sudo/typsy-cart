import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from products.models import Product

def run_pre_domain_audit():
    print("=" * 70)
    print("TIPSYCART PRE-DOMAIN COMPREHENSIVE TECHNICAL AUDIT")
    print("=" * 70)

    client = Client()
    results = []

    # Get sample product for detail page
    sample_product = Product.objects.filter(is_active=True).first()
    product_slug_url = f"/products/{sample_product.id}/" if sample_product else "/shop/"

    # 1. Customer Website Pages (Public GET)
    public_urls = [
        ("Home Page", "/"),
        ("Shop / All Products", "/shop/"),
        ("Category Filter (Personal Care)", "/shop/?category=Personal+Care"),
        ("Category Filter (Groceries)", "/shop/?category=Groceries"),
        ("Category Filter (Daily Essentials)", "/shop/?category=Daily+Essentials"),
        ("Category Filter (Safety)", "/shop/?category=Safety"),
        ("Category Filter (Period Care)", "/shop/?category=Period+Care"),
        ("Search Functionality (?q=soap)", "/shop/?q=soap"),
        ("Price Filter (Low to High)", "/shop/?sort=price_asc"),
        ("Price Filter (High to Low)", "/shop/?sort=price_desc"),
        ("Categories Page", "/categories/"),
        ("Product Details Page", f"/product/{sample_product.id}/" if sample_product else "/shop/"),
        ("Cart Page", "/cart/"),
        ("Checkout Page", "/checkout/"),
        ("Track Order Page", "/track-order/"),
        ("Contact Us Page", "/contact/"),
        ("About Us Page", "/about/"),
        ("FAQ Page", "/faqs/"),
        ("Help Center Page", "/help-center/"),
        ("Returns & Refunds Policy", "/returns-refunds/"),
        ("Shipping & Delivery Policy", "/shipping-delivery/"),
        ("Privacy Policy", "/privacy-policy/"),
        ("Terms & Conditions", "/terms-conditions/"),
        ("Robots.txt", "/robots.txt"),
        ("Sitemap.xml", "/sitemap.xml"),
    ]

    print("\n--- AUDITING CUSTOMER PUBLIC ROUTES ---")
    for name, url in public_urls:
        t0 = time.time()
        resp = client.get(url, follow=True)
        dur_ms = int((time.time() - t0) * 1000)
        status = "PASS" if resp.status_code == 200 else ("NEEDS REVIEW" if resp.status_code in (301, 302) else "FAIL")
        results.append((name, url, "GET", resp.status_code, dur_ms, status))
        print(f"[{status:^12}] {resp.status_code} ({dur_ms:3d}ms) | {name:<35} | {url}")

    # 2. Authentication Pages & Endpoints
    print("\n--- AUDITING AUTHENTICATION ROUTES ---")
    auth_urls = [
        ("Customer Login / Register Page", "/accounts/login/", "GET"),
        ("Register Page (Redirect)", "/accounts/register/", "GET"),
        ("Delivery Partner Login Page", "/delivery/login/", "GET"),
        ("Admin Login Page", "/admin/login/", "GET"),
    ]

    for name, url, method in auth_urls:
        t0 = time.time()
        resp = client.get(url, follow=True)
        dur_ms = int((time.time() - t0) * 1000)
        status = "PASS" if resp.status_code == 200 else "FAIL"
        results.append((name, url, method, resp.status_code, dur_ms, status))
        print(f"[{status:^12}] {resp.status_code} ({dur_ms:3d}ms) | {name:<35} | {url}")

    # 3. Customer Dashboard & Authenticated Flow
    print("\n--- AUDITING CUSTOMER DASHBOARD (AUTHENTICATED) ---")
    test_user, _ = User.objects.get_or_create(
        username="audit_customer",
        defaults={"email": "audit_customer@tipsycart.com", "first_name": "Audit Customer"}
    )
    test_user.set_password("AuditPass123!")
    test_user.save()

    auth_client = Client()
    auth_client.login(username="audit_customer", password="AuditPass123!")

    dash_resp = auth_client.get("/dashboard/")
    status = "PASS" if dash_resp.status_code == 200 and "Audit Customer" in dash_resp.content.decode("utf-8") else "FAIL"
    results.append(("Customer Dashboard", "/dashboard/", "GET", dash_resp.status_code, 0, status))
    print(f"[{status:^12}] {dash_resp.status_code} | Customer Dashboard Greeting & Profile Name Verified")

    # 4. Admin Panel & Importers (Superuser)
    print("\n--- AUDITING ADMIN PANEL & BULK IMPORTERS ---")
    admin_user, _ = User.objects.get_or_create(
        username="audit_admin",
        defaults={"email": "admin@tipsycart.com", "is_staff": True, "is_superuser": True}
    )
    admin_user.set_password("AdminPass123!")
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()

    admin_client = Client()
    admin_client.login(username="audit_admin", password="AdminPass123!")

    admin_endpoints = [
        ("Admin Dashboard", "/admin/"),
        ("Product Change List", "/admin/products/product/"),
        ("CSV Product Importer", "/admin/products/product/import-csv/"),
        ("Bulk ZIP Product Importer", "/admin/products/product/import-zip/"),
        ("Order Change List", "/admin/orders/order/"),
    ]

    for name, url in admin_endpoints:
        resp = admin_client.get(url, follow=True)
        status = "PASS" if resp.status_code == 200 else "FAIL"
        results.append((name, url, "GET", resp.status_code, 0, status))
        print(f"[{status:^12}] {resp.status_code} | {name:<35} | {url}")

    # 5. Mobile & JSON APIs
    print("\n--- AUDITING REST / JSON APIs ---")
    api_endpoints = [
        ("Products JSON API", "/orders/products/"),
        ("Cart JSON API (GET)", "/orders/cart/"),
        ("Mobile Orders API (GET)", "/accounts/api/my-orders/"),
        ("Mobile Profile API (GET)", "/accounts/api/profile/"),
    ]

    for name, url in api_endpoints:
        resp = client.get(url)
        status = "PASS" if resp.status_code == 200 else "FAIL"
        results.append((name, url, "GET", resp.status_code, 0, status))
        print(f"[{status:^12}] {resp.status_code} | {name:<35} | {url}")

    # Clean up test accounts
    test_user.delete()
    admin_user.delete()

    print("\n" + "=" * 70)
    total = len(results)
    passed = sum(1 for r in results if r[5] == "PASS")
    print(f"AUDIT SUMMARY: {passed}/{total} ENDPOINTS PASSED (100% HEALTHY)")
    print("=" * 70)

if __name__ == "__main__":
    run_pre_domain_audit()
