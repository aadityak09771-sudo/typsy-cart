# Generated for TipsyCart Lipstick & Beauty Shades Seeding

from django.db import migrations

LIPSTICK_SHADES = [
    ("Red", "#D32F2F", 3),
    ("Young Pink", "#E85D88", 20),
    ("Cherry Red", "#B31B32", 21),
    ("Tree Oil", "#8C533C", 22),
    ("Marron Mature", "#582424", 23),
    ("Dark Orange", "#BA4529", 24),
    ("Chrome Red", "#53232C", 25),
    ("Poppy Red", "#B52B2D", 26),
    ("Skin Kiss", "#BA6E73", 27),
    ("Grape", "#572F5F", 28),
    ("Blood Red", "#781B24", 29),
    ("Dark Purple", "#381F33", 30),
    ("Nude", "#C89D7C", 31),
    ("Rose Pink", "#E06A8B", 32),
    ("Coral", "#F88379", 33),
]


def seed_lipstick_shades(apps, schema_editor):
    ColorMaster = apps.get_model("products", "ColorMaster")
    for name, hex_code, order in LIPSTICK_SHADES:
        obj, created = ColorMaster.objects.get_or_create(
            name=name,
            defaults={
                "hex_code": hex_code,
                "display_order": order,
                "is_active": True,
            },
        )
        if not created and obj.hex_code != hex_code:
            obj.hex_code = hex_code
            obj.save(update_fields=["hex_code"])


def unseed_lipstick_shades(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0017_product_variant_display_style"),
    ]

    operations = [
        migrations.RunPython(seed_lipstick_shades, unseed_lipstick_shades),
    ]
