# Generated for TipsyCart Colour Master Library seeding

from django.db import migrations

DEFAULT_COLOURS = [
    ("Black", "#000000", 1),
    ("White", "#FFFFFF", 2),
    ("Red", "#FF0000", 3),
    ("Blue", "#0000FF", 4),
    ("Green", "#008000", 5),
    ("Yellow", "#FFFF00", 6),
    ("Pink", "#FFC0CB", 7),
    ("Purple", "#800080", 8),
    ("Orange", "#FFA500", 9),
    ("Grey", "#808080", 10),
    ("Brown", "#A52A2A", 11),
    ("Navy Blue", "#000080", 12),
    ("Beige", "#F5F5DC", 13),
    ("Maroon", "#800000", 14),
    ("Cream", "#FFFDD0", 15),
    ("Sky Blue", "#87CEEB", 16),
]


def seed_colours(apps, schema_editor):
    ColorMaster = apps.get_model("products", "ColorMaster")
    for name, hex_code, order in DEFAULT_COLOURS:
        ColorMaster.objects.get_or_create(
            name=name,
            defaults={
                "hex_code": hex_code,
                "display_order": order,
                "is_active": True,
            },
        )


def unseed_colours(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0011_colormaster_productcolour_color_master"),
    ]

    operations = [
        migrations.RunPython(seed_colours, unseed_colours),
    ]
