
"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import path, include
from accounts import views as accounts_views
from Homepage import views as homepage_views

urlpatterns = [
    # Global admin logout to ensure clean logout for both staff and unauthorized accounts
    path("admin/logout/", accounts_views.admin_logout_view, name="admin_logout"),
    path("admin/", admin.site.urls),

    # Direct aliases for checkout and dashboard
    path("orders/checkout/", homepage_views.checkout, name="orders_checkout_alias"),
    path("dashboard/", accounts_views.dashboard_view, name="root_dashboard"),

    # Main website
    path("", include("Homepage.urls")),

    # Customer accounts
    path("accounts/", include("accounts.urls")),

    # Products, cart and checkout orders
    path("orders/", include("orders.urls")),

    # Women delivery partner portal
    path("delivery/", include("delivery.urls")),
]
