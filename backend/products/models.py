
from django.db import models


class Product(models.Model):
    CATEGORY_CHOICES = [
        ("Period Care", "Period Care"),
        ("Safety", "Personal Safety"),
        ("Personal Care", "Personal Care"),
        ("Daily Essentials", "Daily Essentials"),
        ("Groceries", "Groceries"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
    )

    subcategory = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    brand = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="URL or static path (e.g. /static/home/images/products/...)",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
