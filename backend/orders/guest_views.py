
import json
import logging
import re
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from products.models import Product
from .models import Order, OrderItem


logger = logging.getLogger(__name__)


def _clean_text(value, max_length):
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _normalize_phone(value):
    if not isinstance(value, str):
        return ""

    phone = re.sub(r"[\s().-]", "", value.strip())

    if phone.startswith("+91"):
        phone = phone[3:]
    elif phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]

    return phone if phone.isdigit() and len(phone) == 10 else ""


@csrf_exempt
@require_POST
def guest_place_order(request):
    """
    Guest and logged-in customer checkout API.

    POST /orders/checkout/guest-place-order/

    Requires JSON containing customer details and items:
    [{"product_id": 1, "quantity": 2}]
    """

    # This endpoint is for a JSON API, not browser form submissions.
    if request.content_type != "application/json":
        return JsonResponse(
            {"success": False, "message": "Send data as application/json."},
            status=415,
        )

    # Reject unusually large request bodies.
    if len(request.body) > 32 * 1024:
        return JsonResponse(
            {"success": False, "message": "Request is too large."},
            status=413,
        )

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"success": False, "message": "Invalid JSON request."},
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"success": False, "message": "Invalid request data."},
            status=400,
        )

    full_name = _clean_text(data.get("full_name"), 100)
    phone = _normalize_phone(data.get("phone"))
    address = _clean_text(data.get("address"), 500)
    city = _clean_text(data.get("city"), 100)
    state = _clean_text(data.get("state"), 100)
    pincode = _clean_text(data.get("pincode"), 6)
    payment_method = _clean_text(
        data.get("payment_method", "COD"), 10
    ).upper()
    items = data.get("items")

    if not all([full_name, phone, address, city, state, pincode]):
        return JsonResponse(
            {
                "success": False,
                "message": (
                    "Please provide name, valid phone, address, "
                    "city, state and pincode."
                ),
            },
            status=400,
        )

    if not pincode.isdigit() or len(pincode) != 6:
        return JsonResponse(
            {"success": False, "message": "Enter a valid 6-digit pincode."},
            status=400,
        )

    if payment_method not in ("COD", "UPI"):
        return JsonResponse(
            {"success": False, "message": "Payment method must be COD or UPI."},
            status=400,
        )

    if not isinstance(items, list) or not items or len(items) > 50:
        return JsonResponse(
            {
                "success": False,
                "message": "Cart is empty or contains too many items.",
            },
            status=400,
        )

    # Validate and combine duplicate product IDs.
    quantities = {}

    for item in items:
        if not isinstance(item, dict):
            return JsonResponse(
                {"success": False, "message": "Invalid cart item."},
                status=400,
            )

        product_id = item.get("product_id")
        quantity = item.get("quantity")

        # Reject booleans, strings and fractional quantities.
        if (
            isinstance(product_id, bool)
            or not isinstance(product_id, int)
            or product_id <= 0
            or isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity < 1
            or quantity > 99
        ):
            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Each item needs a valid product_id "
                        "and quantity from 1 to 99."
                    ),
                },
                status=400,
            )

        quantities[product_id] = quantities.get(product_id, 0) + quantity

        if quantities[product_id] > 99:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Maximum quantity per product is 99.",
                },
                status=400,
            )

    try:
        with transaction.atomic():
            # Lock products while checking stock and calculating the total.
            products = list(
                Product.objects.select_for_update()
                .filter(id__in=quantities.keys())
                .order_by("id")
            )

            products_by_id = {
                product.id: product for product in products
            }

            if len(products_by_id) != len(quantities):
                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "One or more products no longer exist. "
                            "Refresh your cart."
                        ),
                    },
                    status=400,
                )

            order_lines = []
            total_amount = Decimal("0.00")

            for product_id, quantity in quantities.items():
                product = products_by_id[product_id]

                if not product.is_active:
                    return JsonResponse(
                        {
                            "success": False,
                            "message": (
                                f"{product.name} is currently unavailable."
                            ),
                        },
                        status=400,
                    )

                if product.stock < quantity:
                    return JsonResponse(
                        {
                            "success": False,
                            "message": (
                                f"Insufficient stock for {product.name}. "
                                f"Available: {product.stock}."
                            ),
                        },
                        status=400,
                    )

                # Always use the database price, never a price sent by the app.
                unit_price = Decimal(str(product.price))
                total_amount += unit_price * quantity
                order_lines.append((product, quantity, unit_price))

            # Link the order to the logged-in customer.
            # If the customer is not logged in, keep it as a guest order.
            customer_user = (
                request.user
                if request.user.is_authenticated
                else None
            )

            order = Order.objects.create(
                user=customer_user,
                full_name=full_name,
                phone=phone,
                address=address,
                city=city,
                state=state,
                pincode=pincode,
                total_amount=total_amount,
                payment_method=payment_method,
                status="Pending",
            )

            for product, quantity, unit_price in order_lines:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    price=unit_price,
                    quantity=quantity,
                )

                # The product row is locked within this transaction.
                Product.objects.filter(pk=product.pk).update(
                    stock=F("stock") - quantity
                )

        return JsonResponse(
            {
                "success": True,
                "message": "Order placed successfully.",
                "order_id": order.id,
                "total": str(total_amount),
                "status": order.status,
                "payment_method": order.payment_method,
                "payment_status": (
                    "Pending" if payment_method == "UPI"
                    else "Pay on delivery"
                ),
            },
            status=201,
        )

    except Exception:
        logger.exception("Checkout failed.")

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "We could not place your order. Please try again."
                ),
            },
            status=500,
        )
