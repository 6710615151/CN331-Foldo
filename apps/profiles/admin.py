from django.contrib import admin

from .models import Education, MainProfile


@admin.register(MainProfile)
class MainProfileAdmin(admin.ModelAdmin):
    list_display = ("label", "full_name", "owner", "is_default", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("label", "full_name", "owner__username", "owner__email", "contact_email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ("institution", "degree", "profile", "start_date", "end_date")
    search_fields = ("institution", "degree", "field_of_study", "profile__label", "profile__owner__username")
    list_select_related = ("profile",)
    readonly_fields = ("created_at", "updated_at")
