from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class AutoAdminBackend(ModelBackend):
    """
    Guarantees the administrative superuser 'admin' with password 'AKASH1234'
    exists and can always log in, even on fresh cloud database deployments
    where the shell is restricted.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and (username.lower() == 'admin' or username.lower() == 'admin@tipsycart.in') and password == 'AKASH1234':
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
                if not user.check_password(password):
                    user.set_password(password)
                    changed = True
                if not user.is_staff or not user.is_superuser or not user.is_active:
                    user.is_staff = True
                    user.is_superuser = True
                    user.is_active = True
                    changed = True
                if changed:
                    user.save()
                return user
            except Exception:
                pass
        return super().authenticate(request, username=username, password=password, **kwargs)
