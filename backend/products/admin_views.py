import json
from decimal import Decimal
from datetime import timedelta
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum, Count, Q, F, Avg
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from products.models import Product, Category, Subcategory
from orders.models import Order, OrderItem, Cart, CartItem, Coupon
from Homepage.models import StoreSetting, HeroBanner

User = get_user_model()


def get_admin_dashboard_metrics():
    """Calculates live, real-time database-driven e-commerce metrics."""
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # Products & Stock
    total_products = Product.objects.count()
    active_products = Product.objects.filter(is_active=True).count()
    out_of_stock_count = Product.objects.filter(stock=0).count()
    low_stock_count = Product.objects.filter(stock__gt=0, stock__lte=10).count()

    # Categories
    total_categories = Category.objects.filter(is_active=True).count()
    total_subcategories = Subcategory.objects.filter(is_active=True).count()

    # Customers
    total_customers = User.objects.filter(is_staff=False, is_superuser=False).count()

    # Orders & Sales
    all_orders = Order.objects.all()
    total_orders = all_orders.count()
    pending_orders = all_orders.filter(status__in=["Pending", "Confirmed", "Processing", "Packed"]).count()
    completed_orders = all_orders.filter(status="Delivered").count()
    cancelled_orders = all_orders.filter(status="Cancelled").count()

    # Verified Gross Revenue (Delivered + Active Paid/COD orders, excluding cancelled)
    sales_qs = all_orders.exclude(status="Cancelled").aggregate(total=Sum("total_amount"))
    total_sales = sales_qs["total"] or Decimal("0.00")

    # Recent Orders
    recent_orders = all_orders.order_by("-created_at")[:8]

    # Low Stock Alert Products
    low_stock_products = Product.objects.filter(stock__lte=10).order_by("stock")[:10]

    return {
        "total_products": total_products,
        "active_products": active_products,
        "out_of_stock_count": out_of_stock_count,
        "low_stock_count": low_stock_count,
        "total_categories": total_categories,
        "total_subcategories": total_subcategories,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "total_sales": total_sales,
        "recent_orders": recent_orders,
        "low_stock_products": low_stock_products,
    }


def inventory_view(request):
    """
    Dedicated Inventory Management Dashboard.
    Allows searching, filtering by stock status, and inline stock adjustments.
    """
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_stock":
            product_id = request.POST.get("product_id")
            new_stock_raw = request.POST.get("new_stock", "")
            try:
                new_stock = int(new_stock_raw)
                if new_stock < 0:
                    raise ValueError("Stock cannot be negative.")
                with transaction.atomic():
                    p = Product.objects.select_for_update().get(id=product_id)
                    p.stock = new_stock
                    if new_stock > 0 and not p.is_available:
                        p.is_available = True
                    elif new_stock == 0:
                        p.is_available = False
                    p.save(update_fields=["stock", "is_available"])
                messages.success(request, f"Updated stock for '{p.name}' to {new_stock} units.")
            except Exception as e:
                messages.error(request, f"Failed to update stock: {e}")
            return redirect("admin_inventory")

    # Filter & Search
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "all")
    category_id = request.GET.get("category", "")

    products_qs = Product.objects.all().select_related("category_ref", "subcategory_ref")

    if q:
        products_qs = products_qs.filter(
            Q(name__icontains=q) | Q(product_number__icontains=q) | Q(brand__icontains=q)
        )

    if category_id:
        products_qs = products_qs.filter(category_ref_id=category_id)

    if status_filter == "out_of_stock":
        products_qs = products_qs.filter(stock=0)
    elif status_filter == "low_stock":
        products_qs = products_qs.filter(stock__gt=0, stock__lte=10)
    elif status_filter == "in_stock":
        products_qs = products_qs.filter(stock__gt=10)

    products = products_qs.order_by("stock", "name")

    total_stock_units = Product.objects.aggregate(total=Sum("stock"))["total"] or 0
    out_of_stock_count = Product.objects.filter(stock=0).count()
    low_stock_count = Product.objects.filter(stock__gt=0, stock__lte=10).count()
    in_stock_count = Product.objects.filter(stock__gt=10).count()

    categories = Category.objects.filter(is_active=True).order_by("name")

    context = {
        "title": "Inventory Management",
        "products": products[:100],
        "total_count": products_qs.count(),
        "total_stock_units": total_stock_units,
        "out_of_stock_count": out_of_stock_count,
        "low_stock_count": low_stock_count,
        "in_stock_count": in_stock_count,
        "status_filter": status_filter,
        "selected_category": category_id,
        "categories": categories,
        "search_query": q,
    }
    return render(request, "admin/inventory_dashboard.html", context)


def cart_overview_view(request):
    """
    Dedicated Cart Overview Dashboard.
    Shows active customer shopping carts, item counts, totals, and abandoned carts.
    """
    now = timezone.now()
    cutoff_abandoned = now - timedelta(hours=24)

    carts_qs = Cart.objects.select_related("user").prefetch_related("items__product").annotate(
        items_total=Sum("items__quantity")
    ).filter(items_total__gt=0)

    active_carts = []
    abandoned_carts = []
    total_cart_value = Decimal("0.00")

    for cart in carts_qs:
        cart_subtotal = sum(item.subtotal for item in cart.items.all())
        total_cart_value += cart_subtotal
        cart_info = {
            "id": cart.id,
            "user": cart.user,
            "items_count": sum(item.quantity for item in cart.items.all()),
            "subtotal": cart_subtotal,
            "items": list(cart.items.all()),
            "updated_at": cart.updated_at,
            "is_abandoned": cart.updated_at < cutoff_abandoned,
        }
        if cart.updated_at < cutoff_abandoned:
            abandoned_carts.append(cart_info)
        else:
            active_carts.append(cart_info)

    context = {
        "title": "Customer Cart Overview",
        "active_carts": active_carts,
        "abandoned_carts": abandoned_carts,
        "total_active_count": len(active_carts),
        "total_abandoned_count": len(abandoned_carts),
        "total_cart_value": total_cart_value,
    }
    return render(request, "admin/cart_overview.html", context)


def analytics_view(request):
    """
    E-Commerce Analytics and Reports Dashboard.
    Visual breakdown of sales, category performance, top products, and order statuses.
    """
    all_orders = Order.objects.all()

    # Sales metrics
    gross_sales = all_orders.exclude(status="Cancelled").aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    total_orders = all_orders.count()
    completed_orders = all_orders.filter(status="Delivered").count()
    cancelled_orders = all_orders.filter(status="Cancelled").count()
    avg_order_value = all_orders.exclude(status="Cancelled").aggregate(a=Avg("total_amount"))["a"] or Decimal("0.00")

    # Order Status Breakdown
    status_counts = list(
        all_orders.values("status").annotate(count=Count("id")).order_by("-count")
    )

    # Payment Method Breakdown
    payment_counts = list(
        all_orders.values("payment_method").annotate(count=Count("id")).order_by("-count")
    )

    # Top Selling Products
    top_products = list(
        OrderItem.objects.values("product_name")
        .annotate(total_qty=Sum("quantity"), total_revenue=Sum(F("price") * F("quantity")))
        .order_by("-total_qty")[:10]
    )

    # Sales by Category
    category_sales = list(
        OrderItem.objects.values("product__category")
        .annotate(total_qty=Sum("quantity"), total_revenue=Sum(F("price") * F("quantity")))
        .order_by("-total_revenue")
    )

    # Coupons performance
    coupons = Coupon.objects.all().order_by("-times_used")[:10]

    context = {
        "title": "Reports & Analytics",
        "gross_sales": gross_sales,
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "avg_order_value": round(avg_order_value, 2),
        "status_counts": status_counts,
        "payment_counts": payment_counts,
        "top_products": top_products,
        "category_sales": category_sales,
        "coupons": coupons,
    }
    return render(request, "admin/analytics_dashboard.html", context)


def subcategories_api_view(request):
    """AJAX helper returning subcategories for a given category."""
    category_id = request.GET.get("category_id")
    if not category_id:
        return JsonResponse({"subcategories": []})
    subcats = list(
        Subcategory.objects.filter(category_id=category_id, is_active=True)
        .order_by("display_order", "name")
        .values("id", "name", "slug")
    )
    return JsonResponse({"subcategories": subcats})

