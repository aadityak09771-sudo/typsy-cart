from django.db import migrations
from django.utils.text import slugify


def seed_categories(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    Subcategory = apps.get_model('products', 'Subcategory')
    Product = apps.get_model('products', 'Product')

    initial_categories = [
        ("Daily Essentials", "daily-essentials", 1, "Everyday essentials for home and lifestyle."),
        ("Groceries", "groceries", 2, "Fresh groceries, snacks, beverages and staples."),
        ("Personal Care", "personal-care", 3, "Bath, hygiene and grooming personal care items."),
        ("Period Care", "period-care", 4, "Quality feminine hygiene and comfort products."),
        ("Safety", "personal-safety", 5, "Personal safety alarms and protection devices."),
    ]

    cat_map = {}
    for name, slug, order, desc in initial_categories:
        cat, created = Category.objects.get_or_create(
            name=name,
            defaults={"slug": slug, "display_order": order, "description": desc, "is_active": True}
        )
        if not cat.slug:
            cat.slug = slug
            cat.save(update_fields=["slug"])
        cat_map[name.lower()] = cat

    # Also map aliases
    if "safety" in cat_map:
        cat_map["personal safety"] = cat_map["safety"]

    # Link existing products to Category and Subcategory
    for p in Product.objects.all():
        cat = cat_map.get(str(p.category).lower())
        if not cat and p.category:
            cat, _ = Category.objects.get_or_create(
                name=p.category,
                defaults={"slug": slugify(p.category), "is_active": True}
            )
            cat_map[str(p.category).lower()] = cat

        if cat:
            p.category_ref = cat
            if p.subcategory:
                sub_name = p.subcategory.strip()
                subcat, _ = Subcategory.objects.get_or_create(
                    category=cat,
                    name=sub_name,
                    defaults={"slug": slugify(f"{cat.name}-{sub_name}"), "is_active": True}
                )
                p.subcategory_ref = subcat
            p.save(update_fields=["category_ref", "subcategory_ref"])


def unseed_categories(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('products', '0007_category_alter_product_options_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
