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

from products.models import Product, Category, Subcategory, ProductVariant
from orders.models import Order, OrderItem, Cart, CartItem, Coupon
from Homepage.models import StoreSetting, HeroBanner
from products.services.excel_exporter import generate_analytics_excel, VALID_ORDER_STATUSES
from django.http import HttpResponse

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


def product_analytics_view(request):
    """
    Dedicated Product Management, Inventory Tracking & Sales Analytics Dashboard.
    Provides real-time KPI cards, date range filtering, category filtering,
    top selling products, low-stock reorder alerts, category performance breakdown,
    and instantaneous Excel (.xlsx) export.
    """
    now = timezone.now()
    date_filter = request.GET.get("date_range", "30days")
    category_id = request.GET.get("category_id", "")

    start_date = None
    end_date = now

    if date_filter == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_filter == "7days":
        start_date = now - timedelta(days=7)
    elif date_filter == "30days":
        start_date = now - timedelta(days=30)
    elif date_filter == "this_month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif date_filter == "all_time":
        start_date = None
    elif date_filter == "custom":
        s_str = request.GET.get("start_date")
        e_str = request.GET.get("end_date")
        if s_str:
            try:
                start_date = timezone.datetime.strptime(s_str, "%Y-%m-%d").replace(tzinfo=timezone.get_current_timezone())
            except ValueError:
                pass
        if e_str:
            try:
                end_date = timezone.datetime.strptime(e_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.get_current_timezone())
            except ValueError:
                pass

    # Products Queryset
    products_qs = Product.objects.all()
    if category_id:
        products_qs = products_qs.filter(Q(category_ref_id=category_id) | Q(category__iexact=category_id))

    # Core Inventory KPIs
    total_products = products_qs.count()
    active_products = products_qs.filter(is_active=True).count()
    inactive_products = products_qs.filter(is_active=False).count()
    total_variants = ProductVariant.objects.filter(product__in=products_qs).count()
    total_stock = products_qs.aggregate(s=Sum("stock"))["s"] or 0
    inventory_val = products_qs.aggregate(v=Sum(F("price") * F("stock")))["v"] or Decimal("0.00")
    low_stock_count = products_qs.filter(stock__gt=0, stock__lte=10).count()
    out_of_stock_count = products_qs.filter(stock=0).count()

    # Order Item Queryset for Sales Metrics
    oi_qs = OrderItem.objects.filter(order__status__in=VALID_ORDER_STATUSES)
    if start_date:
        oi_qs = oi_qs.filter(order__created_at__gte=start_date)
    if end_date:
        oi_qs = oi_qs.filter(order__created_at__lte=end_date)
    if category_id:
        oi_qs = oi_qs.filter(Q(product__category_ref_id=category_id) | Q(product__category__iexact=category_id))

    sales_agg = oi_qs.aggregate(
        total_qty=Sum("quantity"),
        total_rev=Sum(F("price") * F("quantity"))
    )
    total_units_sold = sales_agg["total_qty"] or 0
    total_revenue = sales_agg["total_rev"] or Decimal("0.00")

    # Top Selling Products (Aggregated from OrderItem)
    top_selling_raw = list(
        oi_qs.values("product_id", "product_name")
        .annotate(
            units_sold=Sum("quantity"),
            revenue=Sum(F("price") * F("quantity"))
        )
        .order_by("-revenue")[:15]
    )

    top_products_list = []
    p_ids = [r["product_id"] for r in top_selling_raw if r["product_id"]]
    prod_id_map = {p.id: p for p in Product.objects.filter(id__in=p_ids).select_related("category_ref")}

    for rank, row in enumerate(top_selling_raw, start=1):
        p_obj = prod_id_map.get(row["product_id"])
        top_products_list.append({
            "rank": rank,
            "id": row["product_id"],
            "sku": (p_obj.product_number if p_obj else f"TC-PRD-{row['product_id']}") or "",
            "name": p_obj.name if p_obj else (row["product_name"] or "Unknown"),
            "category": (p_obj.category_ref.name if p_obj and p_obj.category_ref else (p_obj.category if p_obj else "")) or "General",
            "stock": p_obj.stock if p_obj else 0,
            "units_sold": row["units_sold"] or 0,
            "revenue": row["revenue"] or Decimal("0.00"),
            "status": "Active" if (p_obj and p_obj.is_active) else "Inactive",
            "image_url": p_obj.get_image_url() if p_obj else "",
        })

    # Low Stock & Reorder Alert (Stock <= 10)
    low_stock_products = []
    for p in products_qs.filter(stock__lte=10).select_related("category_ref").order_by("stock")[:25]:
        low_stock_products.append({
            "id": p.id,
            "sku": p.product_number or f"TC-PRD-{p.id}",
            "name": p.name,
            "category": p.category_ref.name if p.category_ref else (p.category or ""),
            "variant_name": "Base Product",
            "stock": p.stock,
            "price": p.price,
            "is_out_of_stock": p.stock == 0,
        })

    var_low = ProductVariant.objects.filter(product__in=products_qs, stock__lte=10).select_related("product", "product__category_ref", "size", "colour").order_by("stock")[:25]
    for v in var_low:
        v_size = v.size.name if v.size else (f"{v.unit_value} {v.unit}".strip() if v.unit_value else (v.unit or ""))
        v_title = f"{v.variant_name or ''} {v_size}".strip() or "Variant"
        low_stock_products.append({
            "id": v.product.id,
            "sku": v.sku or v.product.product_number or "",
            "name": v.product.name,
            "category": v.product.category_ref.name if v.product.category_ref else (v.product.category or ""),
            "variant_name": v_title,
            "stock": v.stock,
            "price": v.price,
            "is_out_of_stock": v.stock == 0,
        })
    low_stock_products.sort(key=lambda x: x["stock"])

    # Category Performance Breakdown
    all_categories = Category.objects.all().order_by("name")
    category_performance = []

    cat_sales_map = {}
    for r in oi_qs.values("product__category_ref_id", "product__category").annotate(
        qty=Sum("quantity"),
        rev=Sum(F("price") * F("quantity"))
    ):
        c_id = r["product__category_ref_id"]
        c_name = r["product__category"]
        key = c_id if c_id else c_name
        cat_sales_map[key] = {
            "qty": r["qty"] or 0,
            "rev": r["rev"] or Decimal("0.00")
        }

    for cat in all_categories:
        cat_prods = Product.objects.filter(category_ref=cat)
        c_stock = cat_prods.aggregate(s=Sum("stock"))["s"] or 0
        c_sales = cat_sales_map.get(cat.id, cat_sales_map.get(cat.name, {"qty": 0, "rev": Decimal("0.00")}))
        rev_val = c_sales["rev"]
        share = float((rev_val / total_revenue) * 100) if total_revenue > 0 else 0.0

        category_performance.append({
            "id": cat.id,
            "name": cat.name,
            "product_count": cat_prods.count(),
            "stock": c_stock,
            "units_sold": c_sales["qty"],
            "revenue": rev_val,
            "share_percentage": round(share, 1),
        })

    category_performance.sort(key=lambda x: x["revenue"], reverse=True)

    summary_data = {
        "total_products": total_products,
        "active_products": active_products,
        "inactive_products": inactive_products,
        "total_variants": total_variants,
        "total_stock": total_stock,
        "inventory_valuation": inventory_val,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_units_sold": total_units_sold,
        "total_revenue": total_revenue,
    }

    if request.GET.get("export") == "excel":
        filter_desc_parts = [f"Date Range: {date_filter.replace('_', ' ').title()}"]
        if category_id:
            sel_cat = Category.objects.filter(id=category_id).first()
            filter_desc_parts.append(f"Category: {sel_cat.name if sel_cat else category_id}")
        filter_desc = " | ".join(filter_desc_parts)

        excel_buf = generate_analytics_excel(
            summary_data=summary_data,
            top_products=top_products_list,
            low_stock_items=low_stock_products,
            category_performance=category_performance,
            filter_desc=filter_desc,
        )
        filename = f"tipsycart_analytics_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        resp = HttpResponse(
            excel_buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    context = {
        "title": "Product Management & Sales Analytics",
        "date_filter": date_filter,
        "category_id": category_id,
        "categories": all_categories,
        "summary": summary_data,
        "top_products": top_products_list,
        "low_stock_products": low_stock_products,
        "category_performance": category_performance,
        "start_date": request.GET.get("start_date", ""),
        "end_date": request.GET.get("end_date", ""),
    }
    return render(request, "admin/product_analytics.html", context)


