
import logging
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

from products.models import Product, Category, Subcategory
from Homepage.models import StoreSetting, HeroBanner, FAQItem

logger = logging.getLogger(__name__)


def ensure_categories_exist():
    """Ensure core categories exist in DB; auto-sync from catalog if empty."""
    try:
        if not Category.objects.filter(is_active=True).exists():
            from sync_initial_data import run_sync
            run_sync()
    except Exception as e:
        logger.warning("Could not auto-seed categories: %s", e)


def home(request):
    try:
        ensure_categories_exist()
        if not Product.objects.exists():
            from django.core.management import call_command
            try:
                call_command("loaddata", "initial_products.json", verbosity=0)
            except Exception as se:
                logger.warning("Could not auto-seed initial products: %s", se)

        hero_banner = HeroBanner.objects.filter(is_active=True).first()
        categories_qs = Category.objects.filter(is_active=True).order_by("display_order")
        categories_list = list(categories_qs)
        categories_data = [
            {
                "id": c.id,
                "title": c.name,
                "name": c.name,
                "slug": c.slug,
                "description": c.description or f"{c.name} essentials at TipsyCart.",
                "image_url": c.get_image_url(),
            }
            for c in categories_list
        ]

        # Prioritize featured products, fallback to recent
        featured_qs = Product.objects.filter(is_active=True, is_featured=True)
        if not featured_qs.exists():
            featured_qs = Product.objects.filter(is_active=True)

        featured_products = [
            {
                "id": p.id,
                "product_number": p.product_number or "",
                "name": p.name,
                "category": p.category,
                "subcategory": p.subcategory,
                "price": str(p.price),
                "original_price": str(p.original_price or p.price),
                "discount_enabled": bool(p.discount_enabled or (p.original_price and p.original_price > p.price)),
                "discount_type": p.discount_type,
                "discount_value": str(p.discount_value),
                "discount_percentage": p.discount_percentage,
                "savings_amount": str(p.savings_amount),
                "stock": p.stock,
                "image_url": p.get_image_url(),
            }
            for p in featured_qs.order_by("-created_at")[:12]
        ]
    except Exception as e:
        logger.exception("Error fetching featured products for homepage: %s", e)
        featured_products = []
        hero_banner = None
        categories_list = []
        categories_data = []

    return render(request, "home/index.html", {
        "featured_products": featured_products,
        "hero_banner": hero_banner,
        "categories_list": categories_list,
        "categories_data": categories_data,
    })


def categories(request):
    try:
        ensure_categories_exist()
        categories_list = Category.objects.filter(is_active=True).prefetch_related("subcategories").order_by("display_order")
    except Exception as e:
        logger.exception("Error fetching categories: %s", e)
        categories_list = []
    return render(request, "home/categories.html", {
        "categories_list": categories_list
    })


def shop(request):
    try:
        ensure_categories_exist()
        if not Product.objects.exists():
            from django.core.management import call_command
            try:
                call_command("loaddata", "initial_products.json", verbosity=0)
            except Exception as se:
                logger.warning("Could not auto-seed initial products: %s", se)

        products = Product.objects.filter(
            is_active=True
        ).order_by("-created_at")
        categories_list = Category.objects.filter(is_active=True).order_by("display_order")
    except Exception as e:
        logger.exception("Error fetching products for shop page: %s", e)
        products = []
        categories_list = []

    return render(request, "home/shop.html", {
        "products": products,
        "categories_list": categories_list,
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
    try:
        faq_items = FAQItem.objects.filter(is_active=True).order_by("display_order", "id")
    except Exception as e:
        logger.exception("Error fetching FAQs: %s", e)
        faq_items = []
    return render(request, "home/faqs.html", {
        "faq_items": faq_items
    })


def privacy_policy(request):
    return render(request, "home/privacy_policy.html")


def terms_conditions(request):
    return render(request, "home/terms_conditions.html")


def shipping_delivery(request):
    return render(request, "home/shipping_delivery.html")


def cart_view(request):
    return redirect("checkout")


def product_detail(request, pk):
    from django.shortcuts import get_object_or_404
    product = get_object_or_404(Product, pk=pk, is_active=True)
    return render(request, "home/product_detail.html", {"product": product})


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


def health_check(request):
    """
    Production health-check endpoint for Render zero-downtime deploys and uptime monitors.
    Returns 200 OK when the web service and database are operational.
    """
    from django.db import connection
    db_ok = False
    error_msg = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if row and row[0] == 1:
                db_ok = True
    except Exception as exc:
        logger.error("Health check database error: %s", exc)
        error_msg = str(exc)

    status_code = 200 if db_ok else 503
    return JsonResponse(
        {
            "status": "healthy" if db_ok else "unhealthy",
            "service": "TipsyCart",
            "database": "connected" if db_ok else "disconnected",
            "database_error": error_msg if not db_ok else None,
        },
        status=status_code,
    )


def robots_txt(request):
    """
    Search engine robots directives. Allows indexing of public storefront pages
    while strictly disallowing crawling of admin, accounts, dashboard, delivery portal,
    and checkout/cart endpoints.
    """
    from django.http import HttpResponse
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /shop/",
        "Allow: /categories/",
        "Allow: /about/",
        "Allow: /contact/",
        "Allow: /help-center/",
        "Allow: /faqs/",
        "Allow: /returns-refunds/",
        "Allow: /privacy-policy/",
        "Allow: /terms-conditions/",
        "Allow: /shipping-delivery/",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /dashboard/",
        "Disallow: /delivery/",
        "Disallow: /orders/checkout/",
        "Disallow: /orders/cart/",
        "Disallow: /login/",
        "Disallow: /register/",
        "Disallow: /api/",
        "",
        f"Sitemap: {scheme}://{host}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    """
    XML sitemap for Google and search engines.
    Dynamically includes all active storefront pages, category landing pages,
    and active catalog products with proper lastmod and priorities.
    Excludes all private customer and order endpoints.
    """
    from django.http import HttpResponse
    from django.utils.html import escape
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    base_url = f"{scheme}://{host}"

    static_urls = [
        {"loc": f"{base_url}/", "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base_url}/shop/", "changefreq": "daily", "priority": "0.9"},
        {"loc": f"{base_url}/categories/", "changefreq": "weekly", "priority": "0.8"},
        {"loc": f"{base_url}/about/", "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{base_url}/contact/", "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{base_url}/help-center/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/faqs/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/returns-refunds/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/privacy-policy/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/terms-conditions/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/shipping-delivery/", "changefreq": "monthly", "priority": "0.5"},
    ]

    category_slugs = [
        "period-care",
        "personal-safety",
        "personal-care",
        "daily-essentials",
    ]
    for cat in category_slugs:
        static_urls.append(
            {
                "loc": f"{base_url}/shop/?category={cat}",
                "changefreq": "daily",
                "priority": "0.85",
            }
        )

    product_entries = []
    try:
        active_products = Product.objects.filter(is_active=True).order_by("-created_at")[:100]
        for p in active_products:
            lastmod = p.created_at.strftime("%Y-%m-%d") if p.created_at else ""
            product_entries.append(
                {
                    "loc": f"{base_url}/shop/?category={p.category.lower().replace(' ', '-')}",
                    "lastmod": lastmod,
                    "changefreq": "weekly",
                    "priority": "0.7",
                }
            )
    except Exception as e:
        logger.warning("Could not fetch products for sitemap: %s", e)

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for item in static_urls + product_entries:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{item['loc']}</loc>")
        if item.get("lastmod"):
            xml_lines.append(f"    <lastmod>{item['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{item['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{item['priority']}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")

    return HttpResponse("\n".join(xml_lines), content_type="application/xml; charset=utf-8")

