
import os
import json
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from products.models import Product

products = Product.objects.filter(
    category="Groceries"
).order_by("id")

count = products.count()

print("Grocery products found:", count)

if count != 42:
    raise SystemExit(
        f"STOP: Expected 42 products, found {count}. No export created."
    )

data = {
    "products": [
        {
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "subcategory": p.subcategory,
            "brand": p.brand,
            "price": str(p.price),
            "stock": p.stock,
            "image_url": p.image_url,
            "is_active": p.is_active,
        }
        for p in products
    ]
}

with open("grocery_export.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("SUCCESS: grocery_export.json created.")
print("Total products exported:", count)
