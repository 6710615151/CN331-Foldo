from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Shared shell for FOLDO: landing page, navigation, health check."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"
