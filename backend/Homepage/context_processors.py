import os
from django.conf import settings


def seo_context(request):
    """
    Supplies canonical URLs, production domain, and site metadata
    consistently across all templates.
    """
    custom_domain = os.getenv("CUSTOM_DOMAIN", "").strip().lower()
    if custom_domain:
        # Clean protocol and slashes if user pasted a full URL in environment
        custom_domain = custom_domain.replace("https://", "").replace("http://", "").strip("/")

    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip().lower()

    if custom_domain:
        canonical_base_url = f"https://{custom_domain}"
    elif render_host:
        canonical_base_url = f"https://{render_host}"
    elif request:
        scheme = "https" if request.is_secure() else "http"
        canonical_base_url = f"{scheme}://{request.get_host()}"
    else:
        canonical_base_url = "https://typsy-cart.onrender.com"

    path = request.path if request else "/"
    canonical_url = f"{canonical_base_url}{path}"

    return {
        "canonical_base_url": canonical_base_url,
        "canonical_url": canonical_url,
        "custom_domain_configured": bool(custom_domain),
        "site_name": "TipsyCart",
        "site_phone": "+91 80000 00000",
        "site_city": "Kanpur",
        "site_region": "Uttar Pradesh",
    }
