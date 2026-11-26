from django.apps import AppConfig


class HomepageConfig(AppConfig):
    name = 'Homepage'

    def ready(self):
        try:
            import Homepage.signals  # noqa
        except Exception:
            pass
