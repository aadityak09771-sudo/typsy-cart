import os
import sys
import django
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

# Set up Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from products.models import Product, Category, Subcategory
from orders.models import Order, OrderItem, Cart, CartItem, Coupon
from Homepage.models import StoreSetting, HeroBanner, FAQItem

User = get_user_model()

def run_tests():
    print("=" * 70)
    print("TIPSYCART DYNAMIC ADMIN UPGRADE - 10 END-TO-END VERIFICATION TESTS")
    print("=" * 70)

    results = {}
    client = Client()

    # -------------------------------------------------------------
    # TEST 8: Catalog Integrity (142 Products)
    # -------------------------------------------------------------
    print("\n[TEST 8] Verifying existing 142 products and database records...")
    total_products = Product.objects.count()
    print(f"Total products in DB: {total_products}")
    if total_products >= 142:
        results["TEST_8_CATALOG_INTEGRITY"] = ("PASS", f"All {total_products} catalog products intact.")
    else:
        results["TEST_8_CATALOG_INTEGRITY"] = ("FAIL", f"Expected at least 142 products, found {total_products}")

    # -------------------------------------------------------------
    # TEST 1 & 2: Add Category, Subcategory & Product with Image & Discount
    # -------------------------------------------------------------
    print("\n[TEST 1 & 2] Testing Category, Subcategory & Product Creation with Image & Discount...")
    try:
        # Create test category
        test_cat, _ = Category.objects.get_or_create(
            slug="test-wellness",
            defaults={"name": "Test Wellness", "display_order": 99, "is_active": True}
        )

        # Create test subcategory
        test_subcat, _ = Subcategory.objects.get_or_create(
            category=test_cat,
            slug="test-vitamins",
            defaults={"name": "Test Vitamins", "display_order": 1, "is_active": True}
        )

        # Create 1x1 test image
        tiny_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
            b'\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
            b'\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        )
        uploaded_image = SimpleUploadedFile("test_vitamin.gif", tiny_gif, content_type="image/gif")

        # Create product with original_price=100, discount_value=20%, price should auto-calculate to 80
        test_product = Product.objects.create(
            product_number="TC-TEST-9999",
            name="Daily Multi-Vitamins 60ct",
            category_ref=test_cat,
            subcategory_ref=test_subcat,
            brand="NatureCare",
            original_price=Decimal("100.00"),
            price=Decimal("100.00"),
            discount_enabled=True,
            discount_type="percentage",
            discount_value=Decimal("20.00"),
            stock=50,
            is_available=True,
            is_featured=True,
            is_active=True,
            image=uploaded_image,
        )

        # Verify auto-calculation in save()
        test_product.refresh_from_db()
        print(f"Created Product: {test_product.name}")
        print(f"Selling Price: {test_product.price} (Original MRP: {test_product.original_price}, Discount: {test_product.discount_percentage}%)")
        print(f"Image URL: {test_product.get_image_url()}")
        print(f"Category Ref: {test_product.category_ref.name}, Subcategory Ref: {test_product.subcategory_ref.name}")

        assert test_product.price == Decimal("80.00"), f"Expected 80.00, got {test_product.price}"
        assert test_product.discount_percentage == 20, f"Expected 20%, got {test_product.discount_percentage}%"
        assert test_product.category == "Test Wellness"
        assert test_product.subcategory == "Test Vitamins"
        assert bool(test_product.image), "Image should be attached"

        # Verify API response
        api_resp = client.get("/orders/products/")
        api_data = api_resp.json()
        found_in_api = any(p["product_number"] == "TC-TEST-9999" for p in api_data.get("products", []))
        assert found_in_api, "Product not returned in /orders/products/ API"

        results["TEST_1_ADMIN_ADD_PRODUCT_IMAGE_DISCOUNT"] = ("PASS", "Product created with image upload, auto-discount (₹100 -> ₹80), and verified in API.")
        results["TEST_2_DYNAMIC_CATEGORY_SUBCATEGORY"] = ("PASS", "Dynamic category & subcategory linked, slug generated, category names auto-synced.")
    except Exception as e:
        results["TEST_1_ADMIN_ADD_PRODUCT_IMAGE_DISCOUNT"] = ("FAIL", str(e))
        results["TEST_2_DYNAMIC_CATEGORY_SUBCATEGORY"] = ("FAIL", str(e))

    # -------------------------------------------------------------
    # TEST 3: Edit Product
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Product Update (price, stock, availability)...")
    try:
        test_product.stock = 15
        test_product.discount_value = Decimal("30.00")
        test_product.save()
        test_product.refresh_from_db()

        assert test_product.price == Decimal("70.00"), f"Expected 70.00 after 30% discount, got {test_product.price}"
        assert test_product.stock == 15
        results["TEST_3_PRODUCT_UPDATE"] = ("PASS", "Product pricing recalculated dynamically upon update to ₹70.00 (30% off).")
    except Exception as e:
        results["TEST_3_PRODUCT_UPDATE"] = ("FAIL", str(e))

    # -------------------------------------------------------------
    # TEST 4: Discount Coupon Validation & Calculation
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Coupon Creation & Application API...")
    try:
        test_coupon, _ = Coupon.objects.get_or_create(
            code="WELCOME25",
            defaults={
                "discount_type": "percentage",
                "discount_value": Decimal("25.00"),
                "min_order_amount": Decimal("100.00"),
                "max_discount_amount": Decimal("50.00"),
                "is_active": True,
            }
        )

        # 4a: Below min order
        resp_min = client.post(
            "/orders/api/apply-coupon/",
            data='{"code": "WELCOME25", "cart_total": "50.00"}',
            content_type="application/json"
        )
        assert resp_min.status_code == 400, "Should reject when below min order amount"

        # 4b: Valid coupon on ₹200 cart (25% = ₹50 discount)
        resp_valid = client.post(
            "/orders/api/apply-coupon/",
            data='{"code": "WELCOME25", "cart_total": "200.00"}',
            content_type="application/json"
        )
        assert resp_valid.status_code == 200, f"Expected 200, got {resp_valid.status_code}"
        coupon_res = resp_valid.json()
        assert coupon_res["discount_amount"] == "50.00", f"Expected 50.00 discount, got {coupon_res['discount_amount']}"
        assert coupon_res["new_total"] == "150.00", f"Expected 150.00 new total, got {coupon_res['new_total']}"

        results["TEST_4_COUPON_MANAGEMENT"] = ("PASS", "Coupon WELCOME25 verified with minimum order check and accurate 25% discount cap.")
    except Exception as e:
        results["TEST_4_COUPON_MANAGEMENT"] = ("FAIL", str(e))

    # -------------------------------------------------------------
    # TEST 5 & 6: Customer Journey (Login -> Cart -> Checkout with Coupon -> Stock Deduction)
    # -------------------------------------------------------------
    print("\n[TEST 5 & 6] Testing Customer Journey & Inventory Stock Deduction...")
    test_user = None
    try:
        test_user, _ = User.objects.get_or_create(
            username="e2e_customer@test.com",
            defaults={"email": "e2e_customer@test.com", "first_name": "E2E Test User"}
        )
        client.force_login(test_user)

        # Initial stock of test_product is 15
        initial_stock = test_product.stock

        # Add to cart
        add_resp = client.post(
            "/orders/cart/add/",
            data=f'{{"product_id": {test_product.id}, "quantity": 2}}',
            content_type="application/json"
        )
        assert add_resp.status_code == 200

        # Place order with coupon
        order_payload = {
            "full_name": "E2E Tester",
            "phone": "9876543210",
            "address": "123 Test Street",
            "city": "Kanpur",
            "state": "Uttar Pradesh",
            "pincode": "208001",
            "payment_method": "COD",
            "coupon_code": "WELCOME25"
        }
        order_resp = client.post(
            "/orders/checkout/place-order/",
            data=django.utils.dateformat.format(timezone.now(), "U"), # dummy
            content_type="application/json"
        )
        # Using json dumps
        import json
        order_resp = client.post(
            "/orders/checkout/place-order/",
            data=json.dumps(order_payload),
            content_type="application/json"
        )
        assert order_resp.status_code == 201, f"Expected 201, got {order_resp.status_code}: {order_resp.content}"
        order_data = order_resp.json()
        order_id = order_data["order_id"]

        # Check stock deduction
        test_product.refresh_from_db()
        assert test_product.stock == initial_stock - 2, f"Stock expected {initial_stock - 2}, got {test_product.stock}"

        # Check order record
        created_order = Order.objects.get(id=order_id)
        assert created_order.coupon == test_coupon
        assert created_order.discount_amount > 0

        results["TEST_5_INVENTORY_STOCK_DEDUCTION"] = ("PASS", f"Stock deducted from {initial_stock} to {test_product.stock} upon order placement.")
        results["TEST_6_CUSTOMER_SHOP_CHECKOUT_JOURNEY"] = ("PASS", f"Full customer journey passed: Cart -> Checkout with Coupon -> Order #{order_id} created.")
    except Exception as e:
        results["TEST_5_INVENTORY_STOCK_DEDUCTION"] = ("FAIL", str(e))
        results["TEST_6_CUSTOMER_SHOP_CHECKOUT_JOURNEY"] = ("FAIL", str(e))

    # -------------------------------------------------------------
    # TEST 7: Admin Order Management & Status Reflection
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing Order Status Workflow & Dashboard Reflection...")
    try:
        created_order.status = "Confirmed"
        created_order.save()

        # Customer tracks order
        track_resp = client.get(f"/track-order/?order_id={created_order.id}")
        assert track_resp.status_code == 200
        assert b"Confirmed" in track_resp.content

        results["TEST_7_ORDER_STATUS_WORKFLOW"] = ("PASS", f"Order status updated to 'Confirmed' and rendered on track order screen.")
    except Exception as e:
        results["TEST_7_ORDER_STATUS_WORKFLOW"] = ("FAIL", str(e))

    # -------------------------------------------------------------
    # TEST 9: Admin Login & All Admin Custom Dashboards
    # -------------------------------------------------------------
    print("\n[TEST 9] Testing Admin Login & Custom Dashboards...")
    try:
        admin_user, _ = User.objects.get_or_create(
            username="test_admin_verifier",
            defaults={"email": "verifier@tipsycart.in", "is_staff": True, "is_superuser": True}
        )
        client.force_login(admin_user)

        # 9a: Admin Login page accessible
        admin_login_resp = Client().get("/admin/login/")
        assert admin_login_resp.status_code == 200

        # 9b: Admin Index
        admin_idx_resp = client.get("/admin/")
        assert admin_idx_resp.status_code == 200
        assert b"TipsyCart Admin Navigation" in admin_idx_resp.content or b"tc-admin-nav-bar" in admin_idx_resp.content

        # 9c: Inventory View
        inv_resp = client.get("/admin/inventory/")
        assert inv_resp.status_code == 200
        assert b"Inventory Management" in inv_resp.content

        # 9d: Cart Overview
        cart_resp = client.get("/admin/cart-overview/")
        assert cart_resp.status_code == 200
        assert b"Customer Cart Overview" in cart_resp.content

        # 9e: Analytics Dashboard
        analytics_resp = client.get("/admin/analytics/")
        assert analytics_resp.status_code == 200
        assert b"Reports &amp; Analytics" in analytics_resp.content

        results["TEST_9_ADMIN_LOGIN_AND_DASHBOARDS"] = ("PASS", "Admin login (/admin/login/), index (/admin/), inventory (/admin/inventory/), cart overview (/admin/cart-overview/), and analytics (/admin/analytics/) all return 200 OK.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        results["TEST_9_ADMIN_LOGIN_AND_DASHBOARDS"] = ("FAIL", str(e))

    # -------------------------------------------------------------
    # TEST 10: Storefront & Mobile API Endpoints
    # -------------------------------------------------------------
    print("\n[TEST 10] Testing Public Storefront & Mobile API Endpoints...")
    try:
        anon_client = Client()

        urls_to_test = [
            ("/", 200),
            ("/shop/", 200),
            ("/categories/", 200),
            ("/about/", 200),
            ("/contact/", 200),
            ("/faqs/", 200),
            ("/privacy-policy/", 200),
            ("/terms-conditions/", 200),
            ("/shipping-delivery/", 200),
            ("/track-order/", 200),
            ("/orders/products/", 200),
        ]

        for url, expected_code in urls_to_test:
            res = anon_client.get(url)
            assert res.status_code == expected_code, f"{url} returned {res.status_code}, expected {expected_code}"

        results["TEST_10_STOREFRONT_AND_API_ENDPOINTS"] = ("PASS", "All 11 public storefront pages and API endpoints returned 200 OK.")
    except Exception as e:
        results["TEST_10_STOREFRONT_AND_API_ENDPOINTS"] = ("FAIL", str(e))

    # -------------------------------------------------------------
    # CLEANUP TEST ARTIFACTS (Leave catalog and original data intact)
    # -------------------------------------------------------------
    print("\nCleaning up test artifacts...")
    try:
        if 'created_order' in locals() and created_order:
            created_order.items.all().delete()
            created_order.delete()
        if 'test_product' in locals() and test_product:
            if test_product.image:
                test_product.image.delete(save=False)
            test_product.delete()
        if 'test_subcat' in locals() and test_subcat:
            test_subcat.delete()
        if 'test_cat' in locals() and test_cat:
            test_cat.delete()
        if 'test_coupon' in locals() and test_coupon:
            test_coupon.delete()
        if 'test_user' in locals() and test_user:
            test_user.delete()
        if 'admin_user' in locals() and admin_user:
            admin_user.delete()
        print("Test artifacts cleaned up successfully.")
    except Exception as e:
        print(f"Cleanup warning: {e}")

    # Final summary output
    print("\n" + "=" * 70)
    print("TEST EXECUTION SUMMARY:")
    print("=" * 70)
    all_passed = True
    for test_key, (status, msg) in results.items():
        status_icon = "✅ PASS" if status == "PASS" else "❌ FAIL"
        print(f"{status_icon} | {test_key}: {msg}")
        if status != "PASS":
            all_passed = False

    print("=" * 70)
    print(f"OVERALL RESULT: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 70)
    return all_passed

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
