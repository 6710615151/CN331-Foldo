from django.contrib import admin

from .models import EducationEntry


@admin.register(EducationEntry)
class EducationEntryAdmin(admin.ModelAdmin):
    list_display = ("owner", "level", "institution", "subject", "grade", "updated_at")
    list_filter = ("level",)
    search_fields = ("owner__username", "institution", "subject")
    readonly_fields = ("created_at", "updated_at")
