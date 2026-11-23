from .admin_views import get_admin_dashboard_metrics


def admin_ecommerce_context(request):
    """
    Supplies real-time e-commerce metrics and store settings to Admin templates.
    Only computes when user is authenticated staff/superuser and on an admin page.
    """
    if request.path.startswith("/admin/") and request.user.is_authenticated and request.user.is_staff:
        try:
            return {
                "ecom_metrics": get_admin_dashboard_metrics(),
            }
        except Exception:
            return {}
    return {}
