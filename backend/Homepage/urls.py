
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("categories/", views.categories, name="categories"),
    path("shop/", views.shop, name="shop"),
    path("search/", views.search_view, name="search"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),

    # Checkout and Cart
    path("checkout/", views.checkout, name="checkout"),
    path("cart/", views.cart_view, name="cart"),

    # Product Details
    path("product/<int:pk>/", views.product_detail, name="product_detail"),
    path("products/<int:pk>/", views.product_detail, name="product_detail_plural"),

    # Customer Support & Legal Pages
    path("help-center/", views.help_center, name="help_center"),
    path("track-order/", views.track_order, name="track_order"),
    path("returns-refunds/", views.returns_refunds, name="returns_refunds"),
    path("faqs/", views.faqs, name="faqs"),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("terms-conditions/", views.terms_conditions, name="terms_conditions"),
    path("shipping-delivery/", views.shipping_delivery, name="shipping_delivery"),

    # Newsletter Subscription Endpoint
    path("newsletter/subscribe/", views.subscribe_newsletter, name="newsletter_subscribe"),
]
