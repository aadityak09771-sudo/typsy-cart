# Generated for TipsyCart Realistic Cosmetic & Foundation Shades Seeding

from django.db import migrations

REALISTIC_SHADES = [
    # Realistic Lipstick Shades (Accurate cosmetic pigment HEX codes)
    ("Red", "#D0112B", 3),
    ("Young Pink", "#DE5B7B", 20),
    ("Cherry Red", "#B8142A", 21),
    ("Tree Oil", "#9C5B3E", 22),
    ("Marron Mature", "#6B2026", 23),
    ("Dark Orange", "#C84B22", 24),
    ("Chrome Red", "#9E1228", 25),
    ("Poppy Red", "#D4222E", 26),
    ("Skin Kiss", "#C97A7E", 27),
    ("Grape", "#68255F", 28),
    ("Blood Red", "#850B18", 29),
    ("Dark Purple", "#42163E", 30),
    ("Nude", "#C99B7D", 31),
    ("Rose Pink", "#DC5E84", 32),
    ("Coral", "#E86358", 33),
    # Foundation Glow Shades (Requested by user)
    ("Ivory Glow", "#F5E0CD", 40),
    ("Creme Glow", "#E8C8A6", 41),
    ("Nude Glow", "#D1A57B", 42),
]


def update_and_seed_shades(apps, schema_editor):
    ColorMaster = apps.get_model("products", "ColorMaster")
    ProductColour = apps.get_model("products", "ProductColour")

    hex_map = {}
    for name, hex_code, order in REALISTIC_SHADES:
        hex_map[name.lower()] = hex_code
        obj, created = ColorMaster.objects.get_or_create(
            name=name,
            defaults={
                "hex_code": hex_code,
                "display_order": order,
                "is_active": True,
            },
        )
        if not created:
            obj.hex_code = hex_code
            obj.display_order = order
            obj.is_active = True
            obj.save(update_fields=["hex_code", "display_order", "is_active"])

    # Update existing ProductColour entries to reflect vibrant realistic hex codes
    for pc in ProductColour.objects.all():
        name_key = pc.name.strip().lower()
        if name_key in hex_map:
            new_hex = hex_map[name_key]
            if pc.color_code != new_hex:
                pc.color_code = new_hex
                pc.save(update_fields=["color_code"])


def reverse_shades(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0018_seed_lipstick_shades"),
    ]

    operations = [
        migrations.RunPython(update_and_seed_shades, reverse_shades),
    ]
