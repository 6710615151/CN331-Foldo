from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Users and authentication for FOLDO (custom user model from day one)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"
