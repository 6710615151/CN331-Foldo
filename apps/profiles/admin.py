from django.contrib import admin

from .models import MainProfile


@admin.register(MainProfile)
class MainProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "owner", "headline", "updated_at")
    search_fields = ("full_name", "owner__username", "owner__email", "contact_email")
    readonly_fields = ("created_at", "updated_at")
