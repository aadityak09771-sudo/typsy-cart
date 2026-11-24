
import json
import re
import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from delivery.models import DeliveryAssignment, OrderStatusHistory
from products.models import Product, Category, Subcategory, ProductVariant, ProductColour, ProductSize

from .models import Cart, CartItem, Order, OrderItem, Coupon


logger = logging.getLogger(__name__)


def read_json_object(request):
    """Parse JSON and require an object/dictionary."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    return data if isinstance(data, dict) else None


def get_cart_count(cart):
    return sum(item.quantity for item in cart.items.all())


def validate_delivery_details(data):
    """Validate delivery fields shared by checkout endpoints."""
    fields = (
        "full_name",
        "phone",
        "address",
        "city",
        "state",
        "pincode",
    )

    values = {}

    for field in fields:
        value = data.get(field)

        if not isinstance(value, str):
            return None, "Please provide valid delivery details."

        value = value.strip()

        if not value:
            return None, "Please fill all delivery address fields."

        values[field] = value

    if len(values["full_name"]) > 150:
        return None, "Name is too long."

    if len(values["phone"]) > 15 or not re.fullmatch(
        r"[0-9]{10}", values["phone"]
    ):
        return None, "Enter a valid 10-digit phone number."

    if len(values["address"]) > 255:
        return None, "Address is too long."

    if len(values["city"]) > 100 or len(values["state"]) > 100:
        return None, "City or state is too long."

    if not re.fullmatch(r"[0-9]{6}", values["pincode"]):
        return None, "Enter a valid 6-digit PIN code."

    return values, None


def validate_mobile_order_items(raw_items):
    """Validate mobile and guest checkout product IDs, variant IDs, and quantities."""
    if not isinstance(raw_items, list) or not raw_items:
        return None, "Your cart is empty."

    if len(raw_items) > 50:
        return None, "Too many different products in one order."

    requested_items = []
    seen_keys = set()

    for entry in raw_items:
        if not isinstance(entry, dict):
            return None, "Invalid cart item."

        product_id = entry.get("product_id") or entry.get("id")
        quantity = entry.get("quantity")
        variant_id = entry.get("variant_id")

        if (
            isinstance(product_id, bool)
            or not isinstance(product_id, int)
            or product_id < 1
        ):
            return None, "Invalid product ID."

        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity < 1
            or quantity > 100
        ):
            return None, "Quantity must be between 1 and 100."

        v_id = None
        if variant_id is not None and str(variant_id).strip() != "":
            try:
                v_id = int(variant_id)
            except (ValueError, TypeError):
                v_id = None

        key = (product_id, v_id)
        if key in seen_keys:
            return None, "Duplicate items in cart request."
        seen_keys.add(key)

        requested_items.append({
            "product_id": product_id,
            "variant_id": v_id,
            "quantity": quantity,
        })

    return requested_items, None



# PUBLIC API: Active products for the mobile app.
@require_GET
def products_json(request):
    try:
        if not Product.objects.exists():
            from django.core.management import call_command
            try:
                call_command("loaddata", "initial_products.json", verbosity=0)
            except Exception as se:
                logger.warning("Could not auto-seed initial products: %s", se)

        if not Category.objects.filter(is_active=True).exists():
            try:
                from sync_initial_data import run_sync
                run_sync()
            except Exception as se:
                logger.warning("Could not sync categories: %s", se)

        products = Product.objects.filter(
            is_active=True
        ).select_related("category_ref", "subcategory_ref").prefetch_related(
            "colours",
            "colours__images",
            "sizes",
            "variants",
            "variants__colour",
            "variants__size",
        ).order_by("id")

        items = []
        for product in products:
            is_var = product.is_variable
            p_data = {
                "id": product.id,
                "product_number": product.product_number or "",
                "product_type": product.product_type,
                "is_variable": is_var,
                "name": product.name,
                "description": product.description,
                "category": product.category,
                "subcategory": product.subcategory,
                "category_id": product.category_ref_id,
                "category_slug": product.category_ref.slug if product.category_ref else "",
                "subcategory_id": product.subcategory_ref_id,
                "subcategory_slug": product.subcategory_ref.slug if product.subcategory_ref else "",
                "brand": product.brand,
                "image_url": product.get_image_url(),
                "price": str(product.min_price if is_var else product.price),
                "original_price": str(product.original_price or product.price),
                "min_price": str(product.min_price),
                "max_price": str(product.max_price),
                "price_range_display": product.price_range_display,
                "discount_enabled": bool(product.discount_enabled or (product.original_price and product.original_price > product.price)),
                "discount_type": product.discount_type,
                "discount_value": str(product.discount_value),
                "discount_percentage": product.discount_percentage,
                "savings_amount": str(product.savings_amount),
                "is_featured": product.is_featured,
                "is_available": product.total_stock > 0 and product.is_available if is_var else (product.is_available and product.stock > 0),
                "stock": product.total_stock if is_var else product.stock,
                "colours": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "color_code": c.color_code,
                        "image_url": c.get_primary_image_url(),
                    }
                    for c in product.colours.all() if c.is_active
                ] if is_var else [],
                "sizes": [
                    {
                        "id": s.id,
                        "name": s.name,
                    }
                    for s in product.sizes.all() if s.is_active
                ] if is_var else [],
                "variants": [
                    {
                        "id": v.id,
                        "colour_id": v.colour_id,
                        "size_id": v.size_id,
                        "colour_name": v.colour.name if v.colour else "",
                        "size_name": v.size.name if v.size else "",
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
                    for v in product.variants.all() if v.is_active
                ] if is_var else [],
            }
            items.append(p_data)
    except Exception as e:
        logger.exception("Error in products_json: %s", e)
        items = []

    return JsonResponse({
        "products": items
    })


# PUBLIC API: Active categories & subcategories
@require_GET
def categories_json(request):
    try:
        if not Category.objects.filter(is_active=True).exists():
            try:
                from sync_initial_data import run_sync
                run_sync()
            except Exception as se:
                logger.warning("Could not sync categories: %s", se)

        categories = (
            Category.objects.filter(is_active=True)
            .prefetch_related("subcategories")
            .order_by("display_order", "name")
        )
        data = [
            {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "description": cat.description,
                "image_url": cat.get_image_url(),
                "display_order": cat.display_order,
                "subcategories": [
                    {
                        "id": sub.id,
                        "name": sub.name,
                        "slug": sub.slug,
                        "description": sub.description,
                        "image_url": sub.get_image_url(),
                        "display_order": sub.display_order,
                    }
                    for sub in cat.subcategories.filter(is_active=True).order_by("display_order", "name")
                ],
            }
            for cat in categories
        ]
        return JsonResponse({"categories": data})
    except Exception as e:
        logger.exception("Error in categories_json: %s", e)
        return JsonResponse({"categories": []})



# LOGIN REQUIRED: Customer's server-side cart.
@login_required
@require_GET
def cart_json(request):
    cart = Cart.objects.filter(user=request.user).first()
    items = []
    total = Decimal("0.00")
    total_count = 0

    if cart:
        for item in cart.items.select_related("product", "variant", "variant__colour", "variant__size").all():
            unit_price = item.variant.price if item.variant else item.product.price
            sub = unit_price * item.quantity
            total += sub
            total_count += item.quantity
            var_title = item.variant.get_title() if item.variant else ""
            var_img = item.variant.get_image_url() if item.variant else item.product.get_image_url()
            items.append({
                "product_id": item.product_id,
                "id": item.product_id,
                "variant_id": item.variant_id,
                "cart_item_id": item.id,
                "name": item.product.name,
                "variant_title": var_title,
                "variant_name": var_title,
                "full_name": f"{item.product.name} ({var_title})" if var_title else item.product.name,
                "colour": item.variant.colour.name if (item.variant and item.variant.colour) else "",
                "size": item.variant.size.name if (item.variant and item.variant.size) else "",
                "sku": item.variant.sku if item.variant else (item.product.product_number or ""),
                "price": str(unit_price),
                "quantity": item.quantity,
                "subtotal": str(sub),
                "image_url": var_img,
            })

    return JsonResponse({
        "items": items,
        "total": str(total),
        "count": total_count,
    })


@login_required
@require_POST
def add_to_cart(request):
    data = read_json_object(request)

    if data is None:
        return JsonResponse(
            {"error": "Invalid JSON request."},
            status=400,
        )

    try:
        product_id = int(data.get("product_id", 0))
        quantity = int(data.get("quantity", 1))
        variant_id = data.get("variant_id")
        if variant_id is not None and str(variant_id).strip() != "":
            variant_id = int(variant_id)
        else:
            variant_id = None
    except (ValueError, TypeError, OverflowError):
        return JsonResponse(
            {"error": "Invalid product, variant, or quantity."},
            status=400,
        )

    if product_id < 1 or quantity < 1:
        return JsonResponse(
            {"error": "Invalid product or quantity."},
            status=400,
        )

    try:
        with transaction.atomic():
            product = Product.objects.select_for_update().get(
                id=product_id,
                is_active=True,
            )

            variant = None
            if product.is_variable:
                if not variant_id:
                    return JsonResponse(
                        {"error": "Please select a colour and size before adding to cart."},
                        status=400,
                    )
                try:
                    variant = ProductVariant.objects.select_for_update().get(
                        id=variant_id,
                        product=product,
                        is_active=True,
                    )
                except ProductVariant.DoesNotExist:
                    return JsonResponse(
                        {"error": "The selected product variant is unavailable or inactive."},
                        status=404,
                    )
                max_stock = variant.stock
            else:
                max_stock = product.stock

            cart, _ = Cart.objects.get_or_create(user=request.user)

            item, _ = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                variant=variant,
                defaults={"quantity": 0},
            )

            new_quantity = item.quantity + quantity

            if new_quantity > max_stock:
                return JsonResponse(
                    {"error": f"Not enough stock available. Only {max_stock} units available."},
                    status=400,
                )

            item.quantity = new_quantity
            item.save(update_fields=["quantity"])

            cart_count = get_cart_count(cart)

    except Product.DoesNotExist:
        return JsonResponse(
            {"error": "Product not found or inactive."},
            status=404,
        )

    item_label = f"{product.name} ({variant.get_title()})" if variant else product.name
    return JsonResponse({
        "success": True,
        "message": f"{item_label} added to cart.",
        "cart_count": cart_count,
    })


@login_required
@require_POST
def remove_from_cart(request):
    data = read_json_object(request)

    if data is None:
        return JsonResponse(
            {"error": "Invalid JSON request."},
            status=400,
        )

    try:
        product_id = int(data.get("product_id", 0))
        variant_id = data.get("variant_id")
        if variant_id is not None and str(variant_id).strip() != "":
            variant_id = int(variant_id)
        else:
            variant_id = None
        cart_item_id = data.get("cart_item_id")
        if cart_item_id is not None and str(cart_item_id).strip() != "":
            cart_item_id = int(cart_item_id)
        else:
            cart_item_id = None
    except (ValueError, TypeError, OverflowError):
        return JsonResponse(
            {"error": "Invalid product or variant ID."},
            status=400,
        )

    if product_id < 1 and not cart_item_id:
        return JsonResponse(
            {"error": "Invalid product ID."},
            status=400,
        )

    with transaction.atomic():
        cart = Cart.objects.select_for_update().filter(
            user=request.user
        ).first()

        if not cart:
            cart_count = 0
        else:
            if cart_item_id:
                item = cart.items.filter(id=cart_item_id).first()
            elif variant_id is not None:
                item = cart.items.filter(product_id=product_id, variant_id=variant_id).first()
            else:
                item = cart.items.filter(product_id=product_id, variant__isnull=True).first()
                if not item:
                    item = cart.items.filter(product_id=product_id).first()

            if item:
                if item.quantity > 1:
                    item.quantity -= 1
                    item.save(update_fields=["quantity"])
                else:
                    item.delete()

            cart_count = get_cart_count(cart)

    return JsonResponse({
        "success": True,
        "message": "Cart item updated.",
        "cart_count": cart_count,
    })


@login_required
@require_POST
def clear_cart(request):
    with transaction.atomic():
        cart = Cart.objects.select_for_update().filter(
            user=request.user
        ).first()

        if cart:
            cart.items.all().delete()

    return JsonResponse({
        "success": True,
        "message": "Your cart has been cleared.",
        "cart_count": 0,
    })


# PUBLIC / LOGGED-IN: Validate and apply coupon code
@require_POST
def apply_coupon(request):
    data = read_json_object(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON request."}, status=400)

    code = str(data.get("code", "")).strip().upper()
    if not code:
        return JsonResponse({"error": "Please enter a coupon code."}, status=400)

    try:
        cart_total = Decimal(str(data.get("cart_total", "0.00")))
    except Exception:
        cart_total = Decimal("0.00")

    coupon = Coupon.objects.filter(code__iexact=code).first()
    if not coupon:
        return JsonResponse({"error": f"Coupon '{code}' does not exist."}, status=404)

    valid, reason = coupon.is_valid(cart_total)
    if not valid:
        return JsonResponse({"error": reason}, status=400)

    discount = coupon.calculate_discount(cart_total)
    new_total = max(Decimal("0.00"), cart_total - discount)

    return JsonResponse({
        "success": True,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": str(coupon.discount_value),
        "discount_amount": str(discount),
        "new_total": str(new_total),
        "message": f"Coupon {coupon.code} applied successfully! You saved ₹{discount}.",
    })


# EXISTING WEBSITE LOGGED-IN CHECKOUT.
@login_required
@require_POST
def place_order(request):
    data = read_json_object(request)

    if data is None:
        return JsonResponse(
            {"error": "Invalid JSON request."},
            status=400,
        )

    delivery, error = validate_delivery_details(data)

    if error:
        return JsonResponse({"error": error}, status=400)

    try:
        with transaction.atomic():
            cart = Cart.objects.select_for_update().filter(
                user=request.user
            ).first()

            if not cart:
                return JsonResponse(
                    {"error": "Your cart is empty."},
                    status=400,
                )

            cart_items = list(
                cart.items.select_related("product", "variant", "variant__colour", "variant__size").all()
            )

            if not cart_items:
                return JsonResponse(
                    {"error": "Your cart is empty."},
                    status=400,
                )

            product_ids = sorted({
                item.product_id for item in cart_items
            })
            variant_ids = sorted({
                item.variant_id for item in cart_items if item.variant_id
            })

            locked_products = {
                product.id: product
                for product in Product.objects.select_for_update()
                .filter(
                    id__in=product_ids,
                    is_active=True,
                )
                .order_by("id")
            }

            locked_variants = {
                variant.id: variant
                for variant in ProductVariant.objects.select_for_update()
                .filter(
                    id__in=variant_ids,
                    is_active=True,
                )
                .order_by("id")
            } if variant_ids else {}

            total = Decimal("0.00")
            checked_items = []

            for item in cart_items:
                product = locked_products.get(item.product_id)

                if product is None:
                    return JsonResponse(
                        {
                            "error": (
                                "A product in your cart is unavailable."
                            )
                        },
                        status=400,
                    )

                variant = None
                if item.variant_id:
                    variant = locked_variants.get(item.variant_id)
                    if variant is None or variant.product_id != product.id or not variant.is_active:
                        return JsonResponse(
                            {"error": f"A selected variant for {product.name} is unavailable."},
                            status=400,
                        )
                    available_stock = variant.stock
                    item_price = variant.price
                else:
                    available_stock = product.stock
                    item_price = product.price

                if item.quantity < 1 or item.quantity > available_stock:
                    item_label = f"{product.name} ({variant.get_title()})" if variant else product.name
                    return JsonResponse(
                        {
                            "error": (
                                f"Insufficient stock for {item_label}. "
                                f"Only {available_stock} available. Please update your cart."
                            )
                        },
                        status=400,
                    )

                total += item_price * item.quantity
                checked_items.append((item, product, variant, item_price))

            # Apply coupon discount if provided
            coupon_code = str(data.get("coupon_code", "")).strip().upper()
            applied_coupon = None
            discount_amount = Decimal("0.00")

            if coupon_code:
                c = Coupon.objects.filter(code__iexact=coupon_code, is_active=True).first()
                if c:
                    valid, _ = c.is_valid(total)
                    if valid:
                        discount_amount = c.calculate_discount(total)
                        applied_coupon = c

            final_total = max(Decimal("0.00"), total - discount_amount)

            order = Order.objects.create(
                user=request.user,
                **delivery,
                total_amount=final_total,
                discount_amount=discount_amount,
                coupon=applied_coupon,
                payment_method="COD",
                status="Pending",
            )

            if applied_coupon:
                Coupon.objects.filter(id=applied_coupon.id).update(times_used=F("times_used") + 1)

            for item, product, variant, item_price in checked_items:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    variant=variant,
                    variant_name=variant.get_title() if variant else "",
                    variant_sku=variant.sku if variant else (product.product_number or ""),
                    product_name=product.name,
                    price=item_price,
                    quantity=item.quantity,
                )

                if variant:
                    variant.stock -= item.quantity
                    variant.save(update_fields=["stock"])
                else:
                    product.stock -= item.quantity
                    product.save(update_fields=["stock"])

            cart.items.all().delete()

            # Record initial order placed status in audit history
            OrderStatusHistory.objects.create(
                order=order,
                previous_status="",
                new_status=order.status,
                changed_by=request.user,
                remarks="Order placed successfully by customer via checkout.",
            )

            items_summary = [
                {
                    "name": item.product_name,
                    "variant_name": item.variant_name,
                    "quantity": item.quantity,
                    "price": str(item.price),
                    "subtotal": str(item.subtotal),
                    "image_url": item.image_url,
                }
                for item in order.items.all()
            ]

        return JsonResponse({
            "success": True,
            "message": "Order placed successfully!",
            "order_id": order.id,
            "total_amount": str(order.total_amount),
            "status": order.status,
            "payment_method": order.payment_method,
            "delivery_address": f"{order.full_name}, {order.address}, {order.city} - {order.pincode}",
            "phone": order.phone,
            "items": items_summary,
            "eta": "Within 30-45 mins",
            "step_info": order.step_info,
            "redirect_url": f"/dashboard/?order_placed={order.id}#active-tracking",
        }, status=201)

    except Exception:
        logger.exception("Logged-in order placement failed.")

        return JsonResponse(
            {
                "error": (
                    "We could not place your order. Please try again."
                )
            },
            status=500,
        )


# TOKEN-AUTHENTICATED MOBILE CHECKOUT.
@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_place_order(request):
    data = request.data

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Invalid JSON request."},
            status=400,
        )

    delivery, error = validate_delivery_details(data)

    if error:
        return JsonResponse({"error": error}, status=400)

    requested_items, error = validate_mobile_order_items(
        data.get("items")
    )

    if error:
        return JsonResponse({"error": error}, status=400)

    payment_method = data.get("payment_method", "COD")

    if payment_method not in ("COD", "UPI"):
        return JsonResponse(
            {"error": "Choose COD or UPI as your payment method."},
            status=400,
        )

    try:
        with transaction.atomic():
            product_ids = sorted({item["product_id"] for item in requested_items})
            variant_ids = sorted({item["variant_id"] for item in requested_items if item["variant_id"]})

            locked_products = {
                product.id: product
                for product in Product.objects.select_for_update()
                .filter(
                    id__in=product_ids,
                    is_active=True,
                )
                .order_by("id")
            }

            locked_variants = {
                variant.id: variant
                for variant in ProductVariant.objects.select_for_update()
                .filter(
                    id__in=variant_ids,
                    is_active=True,
                )
                .order_by("id")
            } if variant_ids else {}

            if len(locked_products) != len(product_ids):
                return JsonResponse(
                    {
                        "error": (
                            "One or more products are unavailable. "
                            "Refresh your cart and try again."
                        )
                    },
                    status=400,
                )

            total = Decimal("0.00")
            checked_items = []

            for item_req in requested_items:
                product = locked_products[item_req["product_id"]]
                v_id = item_req["variant_id"]
                quantity = item_req["quantity"]

                variant = None
                if v_id:
                    variant = locked_variants.get(v_id)
                    if variant is None or variant.product_id != product.id or not variant.is_active:
                        return JsonResponse(
                            {"error": f"A selected variant for {product.name} is unavailable."},
                            status=400,
                        )
                    avail_stock = variant.stock
                    price = variant.price
                else:
                    avail_stock = product.stock
                    price = product.price

                if avail_stock < quantity:
                    item_label = f"{product.name} ({variant.get_title()})" if variant else product.name
                    return JsonResponse(
                        {
                            "error": (
                                f"Insufficient stock for {item_label}. "
                                "Please update your cart."
                            )
                        },
                        status=400,
                    )

                total += price * quantity
                checked_items.append((product, variant, price, quantity))

            order = Order.objects.create(
                user=request.user,
                **delivery,
                total_amount=total,
                payment_method=payment_method,
                status="Pending",
            )

            for product, variant, price, quantity in checked_items:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    variant=variant,
                    variant_name=variant.get_title() if variant else "",
                    variant_sku=variant.sku if variant else (product.product_number or ""),
                    product_name=product.name,
                    price=price,
                    quantity=quantity,
                )

                if variant:
                    variant.stock -= quantity
                    variant.save(update_fields=["stock"])
                else:
                    product.stock -= quantity
                    product.save(update_fields=["stock"])

        return JsonResponse({
            "success": True,
            "message": "Your order has been received.",
            "order_id": order.id,
            "total_amount": str(order.total_amount),
            "status": order.status,
            "payment_method": order.payment_method,
            "payment_status": (
                "Payment not completed"
                if payment_method == "UPI"
                else "Pay on delivery"
            ),
        }, status=201)

    except Exception:
        logger.exception("Mobile authenticated order placement failed.")

        return JsonResponse(
            {
                "error": (
                    "We could not place your order. Please try again."
                )
            },
            status=500,
        )


# PUBLIC GUEST CHECKOUT API.
@csrf_exempt
@require_POST
def guest_place_order(request):
    content_type = request.headers.get("Content-Type", "")

    if "application/json" not in content_type.lower():
        return JsonResponse(
            {"error": "Content-Type must be application/json."},
            status=415,
        )

    data = read_json_object(request)

    if data is None:
        return JsonResponse(
            {"error": "Invalid JSON request."},
            status=400,
        )

    delivery, error = validate_delivery_details(data)

    if error:
        return JsonResponse({"error": error}, status=400)

    requested_items, error = validate_mobile_order_items(
        data.get("items")
    )

    if error:
        return JsonResponse({"error": error}, status=400)

    payment_method = data.get("payment_method", "COD")

    if payment_method not in ("COD", "UPI"):
        return JsonResponse(
            {"error": "Choose COD or UPI as your payment method."},
            status=400,
        )

    try:
        with transaction.atomic():
            product_ids = sorted({item["product_id"] for item in requested_items})
            variant_ids = sorted({item["variant_id"] for item in requested_items if item["variant_id"]})

            locked_products = {
                product.id: product
                for product in Product.objects.select_for_update()
                .filter(
                    id__in=product_ids,
                    is_active=True,
                )
                .order_by("id")
            }

            locked_variants = {
                variant.id: variant
                for variant in ProductVariant.objects.select_for_update()
                .filter(
                    id__in=variant_ids,
                    is_active=True,
                )
                .order_by("id")
            } if variant_ids else {}

            if len(locked_products) != len(product_ids):
                return JsonResponse(
                    {
                        "error": (
                            "One or more products are unavailable. "
                            "Refresh your cart and try again."
                        )
                    },
                    status=400,
                )

            total = Decimal("0.00")
            checked_items = []

            for item_req in requested_items:
                product = locked_products[item_req["product_id"]]
                v_id = item_req["variant_id"]
                quantity = item_req["quantity"]

                variant = None
                if v_id:
                    variant = locked_variants.get(v_id)
                    if variant is None or variant.product_id != product.id or not variant.is_active:
                        return JsonResponse(
                            {"error": f"A selected variant for {product.name} is unavailable."},
                            status=400,
                        )
                    avail_stock = variant.stock
                    price = variant.price
                else:
                    avail_stock = product.stock
                    price = product.price

                if avail_stock < quantity:
                    item_label = f"{product.name} ({variant.get_title()})" if variant else product.name
                    return JsonResponse(
                        {
                            "error": (
                                f"Insufficient stock for {item_label}. "
                                "Please update your cart."
                            )
                        },
                        status=400,
                    )

                total += price * quantity
                checked_items.append((product, variant, price, quantity))

            user = request.user if request.user.is_authenticated else None

            order = Order.objects.create(
                user=user,
                **delivery,
                total_amount=total,
                payment_method=payment_method,
                status="Pending",
            )

            for product, variant, price, quantity in checked_items:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    variant=variant,
                    variant_name=variant.get_title() if variant else "",
                    variant_sku=variant.sku if variant else (product.product_number or ""),
                    product_name=product.name,
                    price=price,
                    quantity=quantity,
                )

                if variant:
                    variant.stock -= quantity
                    variant.save(update_fields=["stock"])
                else:
                    product.stock -= quantity
                    product.save(update_fields=["stock"])

            # Record initial order placed status in audit history
            OrderStatusHistory.objects.create(
                order=order,
                previous_status="",
                new_status=order.status,
                changed_by=user,
                remarks="Order placed successfully by customer.",
            )

        return JsonResponse({
            "success": True,
            "message": "Your order has been received.",
            "order_id": order.id,
            "total_amount": str(order.total_amount),
            "status": order.status,
            "payment_method": order.payment_method,
            "payment_status": (
                "Payment not completed"
                if payment_method == "UPI"
                else "Pay on delivery"
            ),
            "redirect_url": f"/dashboard/?order_placed={order.id}#active-tracking",
        }, status=201)

    except Exception:
        logger.exception("Guest order placement failed.")

        return JsonResponse(
            {
                "error": (
                    "We could not place your order. Please try again."
                )
            },
            status=500,
        )


@login_required
@require_POST
def cancel_order(request, order_id):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            id=order_id,
            user=request.user,
        )

        if order.status not in ["Pending", "Confirmed"]:
            messages.error(
                request,
                "Sorry! This order can no longer be cancelled."
            )
            return redirect("dashboard")

        assignment = (
            DeliveryAssignment.objects.select_for_update()
            .filter(order=order)
            .first()
        )

        if assignment and assignment.status in [
            "Out for Delivery",
            "Delivered",
        ]:
            messages.error(
                request,
                "This order is already out for delivery."
            )
            return redirect("dashboard")

        order.status = "Cancelled"
        order.save(update_fields=["status"])

        for item in order.items.all():
            Product.objects.filter(
                id=item.product_id
            ).update(
                stock=F("stock") + item.quantity
            )

        if assignment:
            assignment.status = "Cancelled"
            assignment.save(
                update_fields=["status", "updated_at"]
            )

    messages.success(
        request,
        f"Order #{order.id} cancelled successfully. Stock restored."
    )

    return redirect("dashboard")


@require_GET
def search_autocomplete(request):
    """
    Real-time autocomplete search API.
    Matches active products by name, brand, category, subcategory, SKU and keywords.
    Returns top matching products with thumbnail, pricing, and availability.
    """
    query = request.GET.get("q", "").strip()
    if not query or len(query) < 1:
        return JsonResponse({"results": [], "query": query, "total": 0})

    try:
        from django.db.models import Q
        words = query.split()
        q_filter = Q()
        for w in words[:4]:
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

        products = Product.objects.filter(
            q_filter,
            is_active=True
        ).select_related(
            "category_ref", "subcategory_ref"
        ).prefetch_related(
            "variants"
        ).distinct()[:10]

        results = []
        for p in products:
            is_var = p.is_variable
            p_price = p.min_price if is_var else p.price
            results.append({
                "id": p.id,
                "name": p.name,
                "brand": p.brand or "",
                "category": p.category or (p.category_ref.name if p.category_ref else ""),
                "subcategory": p.subcategory or (p.subcategory_ref.name if p.subcategory_ref else ""),
                "price": str(p_price),
                "original_price": str(p.original_price or p.price),
                "price_range_display": p.price_range_display,
                "discount_percentage": p.discount_percentage,
                "is_variable": is_var,
                "stock": p.total_stock if is_var else p.stock,
                "is_available": p.is_available and (p.total_stock > 0 if is_var else p.stock > 0),
                "image_url": p.get_image_url(),
                "url": f"/product/{p.id}/",
            })

        return JsonResponse({
            "results": results,
            "query": query,
            "total": len(results),
        })
    except Exception as e:
        logger.exception("Error in search_autocomplete: %s", e)
        return JsonResponse({"results": [], "query": query, "error": str(e)}, status=500)

