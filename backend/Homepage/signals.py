import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from products.models import Product, Category, Subcategory, ProductVariant, ProductImage
from Homepage.models import HeroBanner, StoreSetting

logger = logging.getLogger(__name__)

HOMEPAGE_CACHE_KEY = "tc_homepage_data_v2"


def purge_homepage_cache():
    """Purges the cached homepage context so visitors immediately see new products/banners."""
    try:
        cache.delete(HOMEPAGE_CACHE_KEY)
        logger.info("Homepage cache purged successfully.")
    except Exception as e:
        logger.warning("Failed to purge homepage cache: %s", e)


@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=Category)
@receiver([post_save, post_delete], sender=Subcategory)
@receiver([post_save, post_delete], sender=ProductVariant)
@receiver([post_save, post_delete], sender=ProductImage)
@receiver([post_save, post_delete], sender=HeroBanner)
@receiver([post_save, post_delete], sender=StoreSetting)
def invalidate_homepage_cache(sender, **kwargs):
    purge_homepage_cache()
