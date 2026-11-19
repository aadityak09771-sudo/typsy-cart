from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Auto-creates default superuser admin if not present"

    def handle(self, *args, **options):
        User = get_user_model()
        username = "admin"
        password = "AKASH1234"
        email = "admin@tipsycart.in"

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email}
        )
        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{username}' created successfully!")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{username}' password synced successfully!")
            )
