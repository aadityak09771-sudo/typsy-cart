import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from products.models import Product, Category, Subcategory
from Homepage.models import StoreSetting, HeroBanner, FAQItem

def run_sync():
    print("Synchronizing Categories from existing products...")
    initial_categories = [
        ("Daily Essentials", 1, "Everyday essentials for home and lifestyle."),
        ("Groceries", 2, "Fresh groceries, snacks, beverages and staples."),
        ("Personal Care", 3, "Bath, hygiene and grooming personal care items."),
        ("Period Care", 4, "Quality feminine hygiene and comfort products."),
        ("Safety", 5, "Personal safety alarms and protection devices."),
    ]

    for name, order, desc in initial_categories:
        cat, created = Category.objects.get_or_create(
            name=name,
            defaults={"display_order": order, "description": desc, "is_active": True}
        )
        if created:
            print(f"Created Category: {name}")

    # Link existing products to Category & Subcategory
    synced_products = 0
    for p in Product.objects.all():
        cat = Category.objects.filter(name__iexact=p.category).first()
        if not cat and p.category:
            cat = Category.objects.create(name=p.category, is_active=True)
        if cat:
            p.category_ref = cat

        if p.subcategory and cat:
            subcat, _ = Subcategory.objects.get_or_create(
                category=cat,
                name=p.subcategory.strip(),
                defaults={"is_active": True}
            )
            p.subcategory_ref = subcat

        if not p.original_price or p.original_price <= 0:
            p.original_price = p.price

        p.save(update_fields=["category_ref", "subcategory_ref", "original_price"])
        synced_products += 1

    print(f"Synced {synced_products} existing products to Category and Subcategory!")
    print(f"Total Categories in DB: {Category.objects.count()}")
    print(f"Total Subcategories in DB: {Subcategory.objects.count()}")

    # Initialize default StoreSetting if not exists
    StoreSetting.get_settings()
    print("StoreSetting initialized: OK")

    # Initialize default HeroBanner if not exists
    if not HeroBanner.objects.exists():
        HeroBanner.objects.create(
            title="Everything you need, all in one cart.",
            subtitle="From fresh groceries to personal care and safety essentials, shop what matters with TipsyCart.",
            badge_text="KANPUR'S HYPERLOCAL LIFESTYLE STORE",
            button_text="Explore Products",
            button_link="/shop/",
            is_active=True,
        )
        print("Default HeroBanner created: OK")

    # Initialize default FAQs if empty
    if not FAQItem.objects.exists():
        faqs = [
            ("What are TipsyCart's delivery hours in Kanpur?", "We deliver every day between 7:00 AM and 11:00 PM across Kanpur.", "Ordering & Delivery", 1),
            ("How long does delivery usually take?", "Hyperlocal orders within Kanpur city typically arrive within 30 to 45 minutes.", "Ordering & Delivery", 2),
            ("Is packaging discreet for personal care items?", "Yes, 100%. All feminine hygiene and safety items are shipped in opaque, tamper-evident packaging.", "General", 3),
            ("What payment methods are supported?", "We accept UPI (Google Pay, PhonePe, Paytm), Net Banking, Cards, and Cash on Delivery (COD).", "Payments", 4),
            ("What is the return policy?", "Unopened and damaged-in-transit items can be replaced or refunded within 24 hours of delivery.", "Returns & Refunds", 5),
        ]
        for q, a, c, o in faqs:
            FAQItem.objects.create(question=q, answer=a, category=c, display_order=o, is_active=True)
        print("Default FAQs created: OK")

if __name__ == "__main__":
    run_sync()
