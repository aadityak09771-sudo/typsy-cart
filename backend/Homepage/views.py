
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


def help_center(request):
    return render(request, "home/help_center.html")


def track_order(request):
    order_query = request.GET.get("order_id", "").strip()
    found_order = None
    search_performed = False
    error_message = None

    if order_query:
        search_performed = True
        clean_id = order_query.lstrip("#").strip()
        try:
            from orders.models import Order
            found_order = Order.objects.filter(id=int(clean_id)).first()
            if not found_order:
                error_message = f"No order found with ID #{clean_id}. Please check the number and try again."
        except ValueError:
            error_message = "Please enter a valid numeric Order ID (e.g. 1 or #1042)."

    user_orders = []
    if request.user.is_authenticated and not hasattr(request.user, "delivery_profile"):
        try:
            from orders.models import Order
            user_orders = Order.objects.filter(user=request.user).order_by("-created_at")[:5]
        except Exception as e:
            logger.warning("Error fetching user orders for track_order: %s", e)

    return render(request, "home/track_order.html", {
        "order_query": order_query,
        "found_order": found_order,
        "search_performed": search_performed,
        "error_message": error_message,
        "user_orders": user_orders,
    })


def returns_refunds(request):
    return render(request, "home/returns_refunds.html")


def faqs(request):
    return render(request, "home/faqs.html")


def subscribe_newsletter(request):
    if request.method != "POST":
        from django.http import JsonResponse
        return JsonResponse({"success": False, "message": "Method not allowed."}, status=405)

    import json
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    from django.http import JsonResponse

    email = ""
    if request.content_type and "application/json" in request.content_type.lower():
        try:
            data = json.loads(request.body.decode("utf-8"))
            email = str(data.get("email", "")).strip()
        except Exception:
            return JsonResponse({"success": False, "message": "Invalid JSON format."}, status=400)
    else:
        email = str(request.POST.get("email", "")).strip()

    if not email:
        return JsonResponse({"success": False, "message": "Please enter your email address."}, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"success": False, "message": "Please enter a valid email address (e.g. name@example.com)."}, status=400)

    subscribers = request.session.get("newsletter_subscribers", [])
    if email.lower() not in [s.lower() for s in subscribers]:
        subscribers.append(email)
        request.session["newsletter_subscribers"] = subscribers

    logger.info("Newsletter subscriber recorded: %s", email)
    return JsonResponse({
        "success": True,
        "message": "Thank you for subscribing! You'll receive offers and updates from TipsyCart."
    })

