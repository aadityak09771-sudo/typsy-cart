
import os

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Reset an existing superuser password using a temporary environment variable."

    def handle(self, *args, **options):
        if os.environ.get("RESET_ADMIN_NOW") != "1":
            raise CommandError("Password reset was not enabled.")

        password = os.environ.get("RESET_ADMIN_PASSWORD")
        username = os.environ.get("RESET_ADMIN_USERNAME")

        if not password or not username:
            raise CommandError(
                "Set RESET_ADMIN_USERNAME and RESET_ADMIN_PASSWORD first."
            )

        User = get_user_model()

        try:
            user = User.objects.get(username=username, is_superuser=True)
        except User.DoesNotExist:
            raise CommandError(
                "No superuser with that username was found. No changes made."
            )

        user.set_password(password)
        user.save(update_fields=["password"])

        self.stdout.write(
            self.style.SUCCESS("Admin password reset successfully.")
        )
