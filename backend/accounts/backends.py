from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class AutoAdminBackend(ModelBackend):
    """
    Guarantees the administrative superuser 'admin' with password 'AKASH1234'
    exists and can always log in, even on fresh cloud database deployments.
    Also supports login via username, email, or mobile phone number for
    customers and delivery partners.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        User = get_user_model()

        # 1. Admin superuser guarantee
        clean_user = str(username).strip()
        if (clean_user.lower() == 'admin' or clean_user.lower() == 'admin@tipsycart.in') and password == 'AKASH1234':
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
                user.backend = f"{self.__module__}.{self.__class__.__name__}"
                return user
            except Exception:
                pass

        # 2. Try standard username match via Django ModelBackend
        user = super().authenticate(request, username=clean_user, password=password, **kwargs)
        if user:
            user.backend = f"{self.__module__}.{self.__class__.__name__}"
            return user

        # 3. Allow login with Email Address
        if "@" in clean_user:
            try:
                user_match = User.objects.filter(email__iexact=clean_user).first()
                if user_match and user_match.check_password(password) and self.user_can_authenticate(user_match):
                    user_match.backend = f"{self.__module__}.{self.__class__.__name__}"
                    return user_match
            except Exception:
                pass

        # 4. Allow login with Mobile Phone (for Delivery Partners)
        digits = "".join(filter(str.isdigit, clean_user))
        if len(digits) >= 10:
            try:
                user_match = User.objects.filter(delivery_profile__phone__icontains=digits).first()
                if user_match and user_match.check_password(password) and self.user_can_authenticate(user_match):
                    user_match.backend = f"{self.__module__}.{self.__class__.__name__}"
                    return user_match
            except Exception:
                pass

        return None
