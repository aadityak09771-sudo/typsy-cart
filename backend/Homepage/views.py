
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from products.models import Product

logger = logging.getLogger(__name__)


def home(request):
    try:
        if not Product.objects.exists():
            from django.core.management import call_command
            try:
                call_command("loaddata", "initial_products.json", verbosity=0)
            except Exception as se:
                logger.warning("Could not auto-seed initial products: %s", se)

        featured_products = list(
            Product.objects.filter(
                is_active=True
            ).order_by("-created_at").values(
                "id",
                "name",
                "category",
                "subcategory",
                "price",
                "stock",
                "image_url"
            )
        )
    except Exception as e:
        logger.exception("Error fetching featured products for homepage: %s", e)
        featured_products = []

    return render(request, "home/index.html", {
        "featured_products": featured_products
    })


def categories(request):
    return render(request, "home/categories.html")


def shop(request):
    try:
        if not Product.objects.exists():
            from django.core.management import call_command
            try:
                call_command("loaddata", "initial_products.json", verbosity=0)
            except Exception as se:
                logger.warning("Could not auto-seed initial products: %s", se)

        products = Product.objects.filter(
            is_active=True
        ).order_by("-created_at")
    except Exception as e:
        logger.exception("Error fetching products for shop page: %s", e)
        products = []

    return render(request, "home/shop.html", {
        "products": products
    })


def about(request):
    return render(request, "home/about.html")


def contact(request):
    return render(request, "home/contact.html")


@login_required
def checkout(request):
    if hasattr(request.user, "delivery_profile"):
        return redirect("delivery:dashboard")
    return render(request, "home/checkout.html")
