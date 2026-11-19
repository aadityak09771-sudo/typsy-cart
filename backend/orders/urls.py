
from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    # Public product listing
    path(
        "products/",
        views.products_json,
        name="products_json",
    ),

    # Existing logged-in cart
    path("cart/", views.cart_json, name="cart_json"),
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("cart/remove/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/clear/", views.clear_cart, name="clear_cart"),

    # Existing website logged-in checkout
    path(
        "checkout/place-order/",
        views.place_order,
        name="place_order",
    ),

    # New token-authenticated mobile checkout
    path(
        "checkout/mobile-order/",
        views.mobile_place_order,
        name="mobile_place_order",
    ),

    # Existing guest checkout
    path(
        "checkout/guest-order/",
        views.guest_place_order,
        name="guest_place_order",
    ),

    # Existing order cancellation
    path(
        "cancel/<int:order_id>/",
        views.cancel_order,
        name="cancel_order",
    ),
]
