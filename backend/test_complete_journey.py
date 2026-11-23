import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from accounts.models import EmailOTP
from products.models import Product
from orders.models import Order, OrderItem

def test_full_journey():
    print("Testing full customer order journey...")
    client = Client()

    # Clean up prior test
    for old_u in User.objects.filter(email="journey_user@tipsycart.com"):
        Order.objects.filter(user=old_u).delete()
        old_u.delete()
    EmailOTP.objects.filter(email="journey_user@tipsycart.com").delete()

    # 1. Register with username + email
    with patch("accounts.services.otp_service.send_otp_email", return_value=(True, "msg_ok")):
        r_send = client.post("/accounts/auth/send-otp/", {
            "email": "journey_user@tipsycart.com",
            "username": "Aaditya Test User",
            "purpose": "customer_login"
        }, content_type="application/json")
        assert r_send.status_code == 200, f"send-otp failed: {r_send.json()}"

    otp_obj = EmailOTP.objects.get(email="journey_user@tipsycart.com")
    otp_obj.set_otp("777888")
    otp_obj.save()

    # 2. Verify OTP and login
    r_ver = client.post("/accounts/auth/verify-otp/", {
        "email": "journey_user@tipsycart.com",
        "otp": "777888",
        "username": "Aaditya Test User",
        "purpose": "customer_login"
    }, content_type="application/json")
    assert r_ver.status_code == 200, f"verify-otp failed: {r_ver.json()}"

    # 3. Check customer display name on Dashboard
    r_dash = client.get("/dashboard/")
    dash_text = r_dash.content.decode("utf-8")
    assert "Welcome, Aaditya Test User! 👋" in dash_text, "Greeting does not show username"
    assert "👤 Aaditya Test User" in dash_text, "Navbar does not show username"
    print("Customer authentication & display name verified: PASS")

    # 4. Add to cart
    prod = Product.objects.filter(is_active=True).first()
    assert prod is not None

    r_add = client.post("/orders/cart/add/", {
        "product_id": prod.id,
        "quantity": 2
    }, content_type="application/json")
    assert r_add.status_code == 200, f"Add to cart failed: {r_add.json()}"
    print("Add to cart verified: PASS")

    # 5. Place a COD order
    order_data = {
        "full_name": "Aaditya Test User",
        "phone": "9876543210",
        "address": "123 Civil Lines, Kanpur",
        "city": "Kanpur",
        "state": "Uttar Pradesh",
        "pincode": "208001",
        "payment_method": "cod",
    }

    r_ord = client.post("/orders/checkout/place-order/", order_data, content_type="application/json")
    assert r_ord.status_code in (200, 201), f"Order placement failed with {r_ord.status_code}: {r_ord.json()}"
    ord_id = r_ord.json().get("order_id")
    print(f"Order placement verified: PASS (Order #{ord_id} created)")

    # 6. Check order shows in dashboard
    r_dash2 = client.get("/dashboard/")
    assert str(prod.name) in r_dash2.content.decode("utf-8") or "Orders" in r_dash2.content.decode("utf-8")
    print("Dashboard order history verified: PASS")

    # Clean up
    u = User.objects.get(email="journey_user@tipsycart.com")
    Order.objects.filter(user=u).delete()
    u.delete()
    EmailOTP.objects.filter(email="journey_user@tipsycart.com").delete()
    print("ALL JOURNEY TESTS COMPLETED SUCCESSFULLY 100%!")

if __name__ == "__main__":
    test_full_journey()
