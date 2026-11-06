from django.contrib import admin

from .models import MainProfile


@admin.register(MainProfile)
class MainProfileAdmin(admin.ModelAdmin):
    list_display = ("label", "full_name", "owner", "is_default", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("label", "full_name", "owner__username", "owner__email", "contact_email")
    readonly_fields = ("created_at", "updated_at")
