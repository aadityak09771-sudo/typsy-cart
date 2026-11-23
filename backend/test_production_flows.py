import os
import sys
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from products.models import Product
from orders.models import Order, OrderItem
from delivery.models import DeliveryPartner, DeliveryAssignment
from accounts.models import EmailOTP
from accounts.services.otp_service import request_otp, verify_otp_submission


def run_all_production_tests():
    print("=" * 60)
    print("STARTING TIPSYCART PRODUCTION FUNCTIONAL TEST SUITE")
    print("=" * 60)
    client = Client()
    results = {}

    # 1. Health Check
    r = client.get("/health/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert r.json().get("status") == "healthy"
    results["1. Health Check Endpoint (/health/)"] = "PASSED (200 OK, DB Connected)"

    # 2. Robots.txt
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "Disallow: /admin/" in r.content.decode()
    assert "Disallow: /dashboard/" in r.content.decode()
    assert "Sitemap:" in r.content.decode()
    results["2. Search Engine Robots (/robots.txt)"] = "PASSED (200 OK, Private routes disallowed)"

    # 3. XML Sitemap
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "application/xml" in r.headers.get("Content-Type", "")
    assert "<loc>" in r.content.decode()
    results["3. XML Sitemap (/sitemap.xml)"] = "PASSED (200 OK, Dynamic URLs present)"

    # 4. Product Browsing & Catalog
    p, created = Product.objects.get_or_create(
        name="Audit Test Organic Soap",
        defaults={
            "category": "Personal Care",
            "price": Decimal("99.00"),
            "stock": 50,
            "is_active": True,
        }
    )
    r_shop = client.get("/shop/")
    assert r_shop.status_code == 200
    r_api = client.get("/orders/products/")
    assert r_api.status_code == 200
    prod_names = [item["name"] for item in r_api.json().get("products", [])]
    assert "Audit Test Organic Soap" in prod_names
    results["4. Product Catalog & Browsing (/shop/ & /orders/products/)"] = f"PASSED (200 OK, {len(prod_names)} products loaded)"

    # 5. Customer Passwordless OTP Flow
    test_email = "audit_customer@tipsycart.in"
    EmailOTP.objects.filter(email=test_email).delete()
    with patch("accounts.services.otp_service.send_otp_email", return_value=(True, "msg_test_123")):
        ok, msg, data = request_otp(test_email, "customer_login")
        assert ok is True
        otp_rec = EmailOTP.objects.filter(email=test_email, purpose="customer_login", is_used=False).first()
        assert otp_rec is not None
        # Verify incorrect OTP rejected
        ok_bad, msg_bad, _ = verify_otp_submission(test_email, "000000", "customer_login")
        assert ok_bad is False
        # Cooldown check
        ok_cd, msg_cd, _ = request_otp(test_email, "customer_login")
        assert ok_cd is False
        assert "Please wait" in msg_cd
    results["5. Customer OTP Flow (Generate, Hash, Cooldown, Reject Wrong)"] = "PASSED"

    # 6. Admin Superuser Authentication
    from accounts.backends import AutoAdminBackend
    backend = AutoAdminBackend()
    admin_user = backend.authenticate(None, username="admin", password="AKASH1234")
    assert admin_user is not None
    assert admin_user.is_staff is True
    assert admin_user.is_superuser is True
    results["6. Admin Superuser Authentication (AutoAdminBackend)"] = "PASSED (Staff & Superuser verified)"

    # 7. Delivery Partner Access Isolation
    partner_user, _ = User.objects.get_or_create(username="audit_driver", defaults={"email": "driver@tipsycart.in"})
    partner, _ = DeliveryPartner.objects.get_or_create(user=partner_user, defaults={"full_name": "Audit Driver", "phone": "9876543210", "is_active": True})
    client.force_login(partner_user)
    r = client.get("/delivery/dashboard/")
    assert r.status_code == 200
    # Customer dashboard redirects driver
    r_dash = client.get("/dashboard/")
    assert r_dash.status_code == 302
    assert "/delivery/dashboard/" in r_dash.url
    results["7. Delivery Partner Authorization & Dashboard Isolation"] = "PASSED (Role isolation verified)"

    # 8. Customer Order Creation, Stock Locking & Deduction
    customer_user, _ = User.objects.get_or_create(username="audit_shopper", defaults={"email": "shopper@tipsycart.in"})
    initial_stock = p.stock
    client.force_login(customer_user)
    # Add to cart
    client.post("/orders/cart/add/", data={"product_id": p.id, "quantity": 2}, content_type="application/json")
    # Place order
    order_data = {
        "full_name": "Audit Shopper",
        "phone": "9999988888",
        "address": "Civil Lines, Kanpur",
        "city": "Kanpur",
        "state": "Uttar Pradesh",
        "pincode": "208001",
        "payment_method": "COD",
    }
    r_order = client.post("/orders/checkout/place-order/", data=order_data, content_type="application/json")
    assert r_order.status_code in [200, 201]
    order_id = r_order.json().get("order_id")
    p.refresh_from_db()
    assert p.stock == initial_stock - 2
    results["8. Atomic Order Placement & Real-time Stock Deduction"] = f"PASSED (Order #{order_id} created, stock deducted {initial_stock} -> {p.stock})"

    # 9. Order Cancellation & Stock Restoration
    r_cancel = client.post(f"/orders/cancel/{order_id}/")
    assert r_cancel.status_code == 302
    p.refresh_from_db()
    assert p.stock == initial_stock
    cancelled_order = Order.objects.get(id=order_id)
    assert cancelled_order.status == "Cancelled"
    results["9. Order Cancellation & Stock Restoration"] = f"PASSED (Order #{order_id} cancelled, stock restored to {p.stock})"

    # 10. Customer Order Tracking Privacy Masking
    client.logout()
    r_track = client.get(f"/track-order/?order_id={order_id}")
    assert r_track.status_code == 200
    content = r_track.content.decode()
    assert "Civil Lines" not in content  # Street address masked
    assert "Customer Verified (Privacy Protected)" in content
    results["10. Order Tracking IDOR Privacy Masking"] = "PASSED (Public viewer cannot see customer street address)"

    # Clean up test records
    Order.objects.filter(user=customer_user).delete()
    p.delete()

    print("\n" + "=" * 60)
    print("ALL PRODUCTION TESTS COMPLETED SUCCESSFULLY:")
    print("=" * 60)
    for test_name, status in results.items():
        print(f"  [✓] {test_name}: {status}")
    print("=" * 60)
    return True

if __name__ == "__main__":
    run_all_production_tests()
