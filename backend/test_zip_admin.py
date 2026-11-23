import io
import os
import sys
import zipfile
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from products.models import Product

def run_admin_zip_test():
    print("Running Admin ZIP Import integration test...")
    admin_user, _ = User.objects.get_or_create(
        username="test_admin_zip",
        defaults={"email": "admin@tipsycart.com", "is_staff": True, "is_superuser": True}
    )
    admin_user.set_password("AdminPass123!")
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()

    client = Client()
    client.login(username="test_admin_zip", password="AdminPass123!")

    # 1. Test GET /admin/products/product/import-zip/
    resp = client.get("/admin/products/product/import-zip/")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert b"Bulk Import Products (ZIP" in resp.content
    print("GET import-zip page: OK (200)")

    # 2. Build test ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        csv_data = "Product Number,Product Name,Image Filename,Price (INR)\nTC-ZIP-01,Handmade Natural Soap,soap.jpg,85.00\n"
        zf.writestr("Products.csv", csv_data)
        zf.writestr("product_images/soap.jpg", b"\xff\xd8\xff\xe0dummy_soap_bytes")
    buf.seek(0)

    uploaded = SimpleUploadedFile("products_test.zip", buf.getvalue(), content_type="application/zip")

    # Clean up prior test
    Product.objects.filter(product_number="TC-ZIP-01").delete()

    # 3. Test POST preview
    resp_prev = client.post(
        "/admin/products/product/import-zip/",
        {"action": "preview", "zip_file": uploaded, "default_category": "Personal Care", "default_stock": "40"}
    )
    assert resp_prev.status_code == 200, f"Expected 200 on preview, got {resp_prev.status_code}"
    assert b"Handmade Natural Soap" in resp_prev.content
    assert b"TC-ZIP-01" in resp_prev.content
    assert b"Confirm" in resp_prev.content
    print("POST preview action: OK (200 with table and confirm button)")

    # Extract cached token from response HTML
    import re
    match = re.search(r'name="cached_token" value="([^"]+)"', resp_prev.content.decode("utf-8"))
    assert match, "cached_token not found in preview form"
    token = match.group(1)

    # 4. Test POST confirm
    resp_conf = client.post(
        "/admin/products/product/import-zip/",
        {"action": "confirm", "cached_token": token, "default_category": "Personal Care", "default_stock": "40"},
        follow=True
    )
    assert resp_conf.status_code == 200
    p = Product.objects.get(product_number="TC-ZIP-01")
    assert p.name == "Handmade Natural Soap"
    assert p.category == "Personal Care"
    assert p.price == Decimal("85.00")
    assert p.stock == 40
    assert p.image_url == "/static/home/images/products/soap.jpg"
    print("POST confirm action: OK (Product saved to DB, image extracted)")

    # Clean up
    p.delete()
    admin_user.delete()
    print("ALL ADMIN ZIP IMPORT INTEGRATION TESTS PASSED 100%!")

if __name__ == "__main__":
    run_admin_zip_test()
