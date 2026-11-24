
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
        featured_qs = Product.objects.filter(is_active=True, is_featured=True).prefetch_related(
            "gallery_images", "variants", "colours", "sizes"
        )
        if not featured_qs.exists():
            featured_qs = Product.objects.filter(is_active=True).prefetch_related(
                "gallery_images", "variants", "colours", "sizes"
            )

        featured_products = []
        for p in featured_qs.order_by("-created_at")[:12]:
            is_var = p.is_variable
            active_variants = [v for v in p.variants.all() if v.is_active] if is_var else []
            prod_sizes = [
                {"id": s.id, "name": s.name}
                for s in p.sizes.all() if s.is_active
            ] if is_var else []
            if is_var and not prod_sizes and active_variants:
                seen_opt_names = set()
                for v in active_variants:
                    opt_title = v.variant_name or v.get_title()
                    if opt_title and opt_title not in seen_opt_names:
                        seen_opt_names.add(opt_title)
                        prod_sizes.append({"id": v.size_id or v.id, "name": opt_title})

            featured_products.append({
                "id": p.id,
                "product_number": p.product_number or "",
                "name": p.name,
                "category": p.category,
                "subcategory": p.subcategory,
                "price": str(p.min_price if is_var else p.price),
                "original_price": str(p.original_price or p.price),
                "min_price": str(p.min_price),
                "max_price": str(p.max_price),
                "price_range_display": p.price_range_display,
                "is_variable": is_var,
                "has_variants": bool(active_variants),
                "discount_enabled": bool(p.discount_enabled or (p.original_price and p.original_price > p.price)),
                "discount_type": p.discount_type,
                "discount_value": str(p.discount_value),
                "discount_percentage": p.discount_percentage,
                "savings_amount": str(p.savings_amount),
                "stock": p.total_stock if is_var else p.stock,
                "is_available": p.is_available and (p.total_stock > 0 if is_var else p.stock > 0),
                "image_url": p.get_image_url(),
                "gallery_images": [img["url"] for img in p.get_all_images()],
                "unit_type": p.unit_type,
                "unit": p.unit or "",
                "unit_value": str(p.unit_value) if p.unit_value is not None else "",
                "unit_selector_label": p.unit_selector_label,
                "sizes": prod_sizes,
                "colours": [
                    {"id": c.id, "name": c.name, "color_code": c.color_code}
                    for c in p.colours.all() if c.is_active
                ] if is_var else [],
                "variants": [
                    {
                        "id": v.id,
                        "colour_id": v.colour_id,
                        "size_id": v.size_id or v.id,
                        "colour_name": v.colour.name if v.colour else "",
                        "size_name": v.size.name if v.size else (v.variant_name or v.get_title()),
                        "variant_name": v.variant_name or "",
                        "unit": v.unit or p.unit or "",
                        "unit_value": str(v.unit_value) if v.unit_value is not None else (str(p.unit_value) if p.unit_value is not None else ""),
                        "title": v.get_title(),
                        "sku": v.sku,
                        "price": str(v.price),
                        "original_price": str(v.original_price or v.price),
                        "discount_percentage": v.discount_percentage,
                        "savings_amount": str(v.savings_amount),
                        "stock": v.stock,
                        "is_available": v.is_in_stock,
                        "image_url": v.get_image_url(),
                    }
                    for v in active_variants
                ] if is_var else [],
            })
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
        categories_list = Category.objects.filter(is_active=True).prefetch_related("subcategories").order_by("display_order")

        # Dynamic SEO category & subcategory resolution
        category_slug = request.GET.get("category", "").strip().lower()
        subcategory_slug = request.GET.get("subcategory", "").strip().lower()

        selected_category = None
        selected_subcategory = None

        if category_slug:
            selected_category = Category.objects.filter(slug__iexact=category_slug, is_active=True).first()

        if subcategory_slug:
            selected_subcategory = Subcategory.objects.filter(slug__iexact=subcategory_slug, is_active=True).first()

    except Exception as e:
        logger.exception("Error fetching products for shop page: %s", e)
        products = []
        categories_list = []
        selected_category = None
        selected_subcategory = None

    return render(request, "home/shop.html", {
        "products": products,
        "categories_list": categories_list,
        "selected_category": selected_category,
        "selected_subcategory": selected_subcategory,
        "search_query": request.GET.get("search", "").strip() or request.GET.get("q", "").strip(),
    })


def search_view(request):
    """
    Search results page displaying matching products with full filters.
    """
    from django.db.models import Q
    query = request.GET.get("q", "").strip() or request.GET.get("search", "").strip()
    category_slug = request.GET.get("category", "").strip().lower()
    subcategory_slug = request.GET.get("subcategory", "").strip().lower()
    sort = request.GET.get("sort", "relevance").strip()

    products_qs = Product.objects.filter(is_active=True).select_related(
        "category_ref", "subcategory_ref"
    ).prefetch_related(
        "variants", "colours", "sizes", "gallery_images"
    )

    if query:
        words = query.split()
        q_filter = Q()
        for w in words[:5]:
            q_filter &= (
                Q(name__icontains=w) |
                Q(brand__icontains=w) |
                Q(category__icontains=w) |
                Q(subcategory__icontains=w) |
                Q(category_ref__name__icontains=w) |
                Q(subcategory_ref__name__icontains=w) |
                Q(product_number__icontains=w) |
                Q(description__icontains=w) |
                Q(variants__sku__icontains=w) |
                Q(variants__variant_name__icontains=w)
            )
        products_qs = products_qs.filter(q_filter).distinct()

    if category_slug and category_slug != "all":
        products_qs = products_qs.filter(
            Q(category_ref__slug__iexact=category_slug) | Q(category__iexact=category_slug)
        )

    if subcategory_slug and subcategory_slug != "all":
        products_qs = products_qs.filter(
            Q(subcategory_ref__slug__iexact=subcategory_slug) | Q(subcategory__iexact=subcategory_slug)
        )

    if sort == "price-low":
        products_qs = products_qs.order_by("price")
    elif sort == "price-high":
        products_qs = products_qs.order_by("-price")
    elif sort == "newest":
        products_qs = products_qs.order_by("-created_at")
    elif sort == "discount":
        products_qs = products_qs.order_by("-discount_value")
    else:
        products_qs = products_qs.order_by("-is_featured", "-created_at")

    categories_list = Category.objects.filter(is_active=True).prefetch_related("subcategories").order_by("display_order")

    return render(request, "home/search.html", {
        "products": products_qs,
        "query": query,
        "results_count": products_qs.count(),
        "categories_list": categories_list,
        "selected_category": category_slug,
        "selected_subcategory": subcategory_slug,
        "selected_sort": sort,
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
    import json
    from django.shortcuts import get_object_or_404
    product = get_object_or_404(
        Product.objects.select_related("category_ref", "subcategory_ref").prefetch_related(
            "gallery_images",
            "colours",
            "colours__images",
            "sizes",
            "variants",
            "variants__colour",
            "variants__size",
        ),
        pk=pk,
        is_active=True,
    )

    all_gallery_images = product.get_all_images()

    # -------------------------------------------------------------------------
    # SIMILAR / RELATED PRODUCTS QUERY
    # -------------------------------------------------------------------------
    similar_products = []
    try:
        base_qs = Product.objects.filter(is_active=True).exclude(pk=product.pk).select_related(
            "category_ref", "subcategory_ref"
        )
        subcat_matches = []
        if product.subcategory_ref:
            subcat_matches = list(base_qs.filter(subcategory_ref=product.subcategory_ref)[:8])
        elif product.subcategory:
            subcat_matches = list(base_qs.filter(subcategory=product.subcategory)[:8])

        cat_matches = []
        if len(subcat_matches) < 4:
            needed = 8 - len(subcat_matches)
            sub_ids = [p.id for p in subcat_matches]
            if product.category_ref:
                cat_matches = list(base_qs.filter(category_ref=product.category_ref).exclude(id__in=sub_ids)[:needed])
            elif product.category:
                cat_matches = list(base_qs.filter(category=product.category).exclude(id__in=sub_ids)[:needed])

        similar_products = (subcat_matches + cat_matches)[:8]
    except Exception as e:
        logger.warning("Error fetching similar products: %s", e)
        similar_products = []

    context = {
        "product": product,
        "is_variable": product.is_variable,
        "gallery_images": all_gallery_images,
        "gallery_images_json": json.dumps(all_gallery_images),
        "similar_products": similar_products,
        "unit_selector_label": product.unit_selector_label,
    }

    if product.is_variable:
        colours = list(product.colours.filter(is_active=True))
        sizes = list(product.sizes.filter(is_active=True))
        variants = list(product.variants.filter(is_active=True))

        if not sizes and variants:
            seen_names = set()
            sizes = []
            for v in variants:
                opt_name = v.variant_name or v.get_title()
                if opt_name and opt_name not in seen_names:
                    seen_names.add(opt_name)
                    sizes.append({
                        "id": v.size_id or v.id,
                        "name": opt_name,
                    })

        colours_data = [
            {
                "id": c.id,
                "name": c.name,
                "color_code": c.color_code,
                "images": [
                    img.get_image_url() for img in c.images.all()
                ] or [c.get_primary_image_url()],
            }
            for c in colours
        ]

        variants_data = [
            {
                "id": v.id,
                "colour_id": v.colour_id,
                "colour_name": v.colour.name if v.colour else "",
                "size_id": v.size_id or v.id,
                "size_name": v.size.name if v.size else (v.variant_name or v.get_title()),
                "variant_name": v.variant_name or "",
                "unit": v.unit or "",
                "unit_value": str(v.unit_value) if v.unit_value else "",
                "title": v.get_title(),
                "sku": v.sku,
                "price": str(v.price),
                "original_price": str(v.original_price or v.price),
                "discount_percentage": v.discount_percentage,
                "savings_amount": str(v.savings_amount),
                "stock": v.stock,
                "is_in_stock": v.is_in_stock,
                "image_url": v.get_image_url(),
            }
            for v in variants
        ]

        context.update({
            "colours": colours,
            "sizes": sizes,
            "variants": variants,
            "colours_json": json.dumps(colours_data),
            "variants_json": json.dumps(variants_data),
        })

    return render(request, "home/product_detail.html", context)


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
    import os
    from django.http import HttpResponse

    custom_domain = os.getenv("CUSTOM_DOMAIN", "").strip().lower()
    if custom_domain:
        custom_domain = custom_domain.replace("https://", "").replace("http://", "").strip("/")
        base_url = f"https://{custom_domain}"
    elif os.getenv("RENDER_EXTERNAL_HOSTNAME"):
        base_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME').strip().lower()}"
    elif request:
        scheme = "https" if request.is_secure() else "http"
        base_url = f"{scheme}://{request.get_host()}"
    else:
        base_url = "https://typsy-cart.onrender.com"

    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /shop/",
        "Allow: /categories/",
        "Allow: /product/",
        "Allow: /products/",
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
        "Disallow: /checkout/",
        "Disallow: /cart/",
        "Disallow: /login/",
        "Disallow: /register/",
        "Disallow: /track-order/",
        "Disallow: /api/",
        "",
        f"Sitemap: {base_url}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    """
    XML sitemap for Google and search engines.
    Dynamically includes all active storefront pages, category landing pages,
    and active catalog products with proper lastmod and priorities.
    Excludes all private customer, cart, and admin endpoints.
    """
    import os
    from django.http import HttpResponse
    from django.utils.html import escape

    custom_domain = os.getenv("CUSTOM_DOMAIN", "").strip().lower()
    if custom_domain:
        custom_domain = custom_domain.replace("https://", "").replace("http://", "").strip("/")
        base_url = f"https://{custom_domain}"
    elif os.getenv("RENDER_EXTERNAL_HOSTNAME"):
        base_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME').strip().lower()}"
    elif request:
        scheme = "https" if request.is_secure() else "http"
        base_url = f"{scheme}://{request.get_host()}"
    else:
        base_url = "https://typsy-cart.onrender.com"

    static_urls = [
        {"loc": f"{base_url}/", "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base_url}/shop/", "changefreq": "daily", "priority": "0.9"},
        {"loc": f"{base_url}/categories/", "changefreq": "weekly", "priority": "0.85"},
        {"loc": f"{base_url}/about/", "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{base_url}/contact/", "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{base_url}/help-center/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/faqs/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/returns-refunds/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/privacy-policy/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/terms-conditions/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/shipping-delivery/", "changefreq": "monthly", "priority": "0.5"},
    ]

    category_urls = []
    try:
        active_categories = Category.objects.filter(is_active=True).prefetch_related("subcategories").order_by("display_order")
        for cat in active_categories:
            category_urls.append(
                {
                    "loc": f"{base_url}/shop/?category={cat.slug}",
                    "changefreq": "daily",
                    "priority": "0.85",
                }
            )
            for sub in cat.subcategories.filter(is_active=True):
                category_urls.append(
                    {
                        "loc": f"{base_url}/shop/?category={cat.slug}&subcategory={sub.slug}",
                        "changefreq": "weekly",
                        "priority": "0.8",
                    }
                )
    except Exception as e:
        logger.warning("Could not fetch categories for sitemap: %s", e)

    product_entries = []
    try:
        active_products = Product.objects.filter(is_active=True).order_by("-created_at")[:500]
        for p in active_products:
            lastmod = p.created_at.strftime("%Y-%m-%d") if p.created_at else ""
            product_entries.append(
                {
                    "loc": f"{base_url}/product/{p.id}/",
                    "lastmod": lastmod,
                    "changefreq": "weekly",
                    "priority": "0.8",
                }
            )
    except Exception as e:
        logger.warning("Could not fetch products for sitemap: %s", e)

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for item in static_urls + category_urls + product_entries:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{escape(item['loc'])}</loc>")
        if item.get("lastmod"):
            xml_lines.append(f"    <lastmod>{item['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{item['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{item['priority']}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")

    return HttpResponse("\n".join(xml_lines), content_type="application/xml; charset=utf-8")

