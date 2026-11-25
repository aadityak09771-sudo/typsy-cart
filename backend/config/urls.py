
"""
URL configuration for config project.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from accounts import views as accounts_views
from Homepage import views as homepage_views
from orders import views as order_views
from products import admin_views

urlpatterns = [
    # Global admin logout to ensure clean logout for both staff and unauthorized accounts
    path("admin/logout/", accounts_views.admin_logout_view, name="admin_logout"),

    # Real-time search autocomplete API alias
    path("api/search/", order_views.search_autocomplete, name="root_search_autocomplete"),
    path("search/", homepage_views.search_view, name="root_search_view"),

    # Custom Admin Management Views (Staff/Superuser protected)
    path("admin/inventory/", admin.site.admin_view(admin_views.inventory_view), name="admin_inventory"),
    path("admin/product-analytics/", admin.site.admin_view(admin_views.product_analytics_view), name="admin_product_analytics"),
    path("admin/cart-overview/", admin.site.admin_view(admin_views.cart_overview_view), name="admin_cart_overview"),
    path("admin/analytics/", admin.site.admin_view(admin_views.analytics_view), name="admin_analytics"),
    path("admin/products/api/subcategories/", admin.site.admin_view(admin_views.subcategories_api_view), name="admin_products_subcategories_api_alias"),

    path("admin/", admin.site.urls),

    # Production Operations & SEO
    path("health/", homepage_views.health_check, name="health_check"),
    path("robots.txt", homepage_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", homepage_views.sitemap_xml, name="sitemap_xml"),

    # Direct aliases for checkout, login, register, and dashboard
    path("orders/checkout/", homepage_views.checkout, name="orders_checkout_alias"),
    path("dashboard/", accounts_views.dashboard_view, name="root_dashboard"),
    path("login/", accounts_views.login_view, name="root_login"),
    path("register/", accounts_views.register_view, name="root_register"),

    # Main website
    path("", include("Homepage.urls")),

    # Customer accounts
    path("accounts/", include("accounts.urls")),

    # Products, cart and checkout orders
    path("orders/", include("orders.urls")),

    # Women delivery partner portal
    path("delivery/", include("delivery.urls")),

    # Media uploads serving (production and dev)
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
