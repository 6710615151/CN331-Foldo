from django.contrib import admin

from .models import Portfolio


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "profile", "template_key", "is_published", "updated_at")
    list_filter = ("is_published", "template_key")
    search_fields = ("title", "slug", "owner__username")
    readonly_fields = ("slug", "created_at", "updated_at")
