
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from products.models import Product


def home(request):
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

    return render(request, "home/index.html", {
        "featured_products": featured_products
    })


def categories(request):
    return render(request, "home/categories.html")


def shop(request):
    products = Product.objects.filter(
        is_active=True
    ).order_by("-created_at")

    return render(request, "home/shop.html", {
        "products": products
    })


def about(request):
    return render(request, "home/about.html")


def contact(request):
    return render(request, "home/contact.html")


@login_required
def checkout(request):
    return render(request, "home/checkout.html")
