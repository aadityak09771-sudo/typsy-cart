
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("categories/", views.categories, name="categories"),
    path("shop/", views.shop, name="shop"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),

    # Checkout page
    path("checkout/", views.checkout, name="checkout"),

    # Customer Support & Footer Pages
    path("help-center/", views.help_center, name="help_center"),
    path("track-order/", views.track_order, name="track_order"),
    path("returns-refunds/", views.returns_refunds, name="returns_refunds"),
    path("faqs/", views.faqs, name="faqs"),

    # Newsletter Subscription Endpoint
    path("newsletter/subscribe/", views.subscribe_newsletter, name="newsletter_subscribe"),
]
