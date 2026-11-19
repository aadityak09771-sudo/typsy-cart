from django.apps import AppConfig
from django.db.models.signals import post_migrate


def auto_create_admin(sender, **kwargs):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@tipsycart.in',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        changed = False
        if not user.check_password('AKASH1234'):
            user.set_password('AKASH1234')
            changed = True
        if not user.is_staff or not user.is_superuser or not user.is_active:
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            changed = True
        if changed:
            user.save()
    except Exception:
        pass


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        post_migrate.connect(auto_create_admin, sender=self)
